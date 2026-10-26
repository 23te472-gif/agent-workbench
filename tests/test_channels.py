import json,sys,tempfile,threading,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from credential_store import ProfileStore
from codex_channel import CodexChannel
from provider_client import ProviderError

class ChannelsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.profiles=ProfileStore(self.base,encrypt=lambda s:'mock:'+s,decrypt=lambda s:s[5:])
        self.server=self.base/'fake.py'
        self.server.write_text('''import json,sys,time
mode=sys.argv[1]
def send(v):print(json.dumps(v),flush=True)
for line in sys.stdin:
 v=json.loads(line);m=v.get('method');i=v.get('id')
 if m=='initialize':r={'userAgent':'mock'}
 elif m=='initialized':continue
 elif m=='account/read':r={'account':None if mode=='logout' else {'type':'chatgpt','email':'private@example.invalid'}}
 elif m=='config/read':r={'config':{'mcp_servers':{'mock':{'command':'must-not-run'}}}}
 elif m=='model/list':
  r={'data':[{'id':'gpt-6.1-sol','model':'gpt-6.1-sol','displayName':'Sol','supportedReasoningEfforts':[{'reasoningEffort':'low'}]}],'nextCursor':None}
 elif m=='thread/start':
  assert v['params']['ephemeral'] is True
  assert v['params']['sandbox']=='read-only'
  assert v['params']['config']['mcp_servers']['mock']['enabled'] is False
  r={'thread':{'id':'thread-test'},'model':'wrong-model' if mode=='identity' else 'gpt-6.1-sol','sandbox':{'type':'readOnly'}}
 elif m=='turn/start':
  send({'id':i,'result':{'turn':{'id':'turn-test','status':'inProgress'}}})
  if mode=='stall':time.sleep(10);continue
  if mode=='tool':send({'id':90,'method':'item/commandExecution/requestApproval','params':{}});continue
  send({'method':'item/started','params':{'threadId':'thread-test','turnId':'turn-test','item':{'type':'contextCompaction','id':'context'}}})
  if mode=='unknown':send({'method':'mystery/new-event','params':{}})
  if mode=='unbound':send({'method':'item/agentMessage/delta','params':{'delta':'unbound text'}})
  send({'method':'item/reasoning/textDelta','params':{'threadId':'thread-test','turnId':'turn-test','itemId':'reason','delta':'PRIVATE-REASONING'}})
  send({'method':'item/started','params':{'threadId':'thread-test','turnId':'turn-test','item':{'type':'agentMessage','id':'message-1','text':''}}})
  send({'method':'item/agentMessage/delta','params':{'threadId':'thread-test','turnId':'turn-test','itemId':'message-1','delta':'public reply'}})
  send({'method':'turn/completed','params':{'threadId':'thread-test','turn':{'id':'turn-test','status':'failed' if mode=='fail' else 'completed'}}})
  continue
 else:r={}
 send({'id':i,'result':r})
''',encoding='utf-8')
    def channel(self,mode='ok',found=True):
        return CodexChannel(finder=lambda:sys.executable if found else None,command_factory=lambda exe:[exe,'-X','utf8','-u',str(self.server),mode])
    def test_local_profile_needs_no_api_key_and_does_not_save_host_path(self):
        row=self.profiles.save(dict(name='Local',kind='codex_local',model='gpt-6.1-sol',base_url='C:/another-host/codex.exe'))
        self.assertFalse(row['has_key']);self.assertFalse(row['requires_key'])
        self.assertEqual(row['base_url'],'codex://local')
        self.assertEqual(self.profiles.credentials(row['id'])[1],'')
        self.assertNotIn('another-host',self.profiles.path.read_text(encoding='utf-8'))
        reopened=ProfileStore(self.base,encrypt=lambda s:s,decrypt=lambda s:s)
        self.assertEqual(reopened.list()[0]['kind'],'codex_local')
    def test_discovery_does_not_generate_and_removes_account_identity(self):
        result=self.channel().discover()
        self.assertEqual(result['state'],'catalog');self.assertEqual(result['models'][0]['id'],'gpt-6.1-sol')
        self.assertNotIn('private@',json.dumps(result));self.assertFalse(result['generation_verified'])
    def test_absent_client_and_logged_out_are_actionable(self):
        self.assertEqual(self.channel(found=False).discover()['state'],'not_installed')
        self.assertEqual(self.channel('logout').discover()['state'],'login_required')
    def generate(self,mode='ok',cancel=None):
        chunks=[];channel=self.channel(mode)
        result=channel.complete({'model':'gpt-6.1-sol'},'',[{'role':'system','content':'instructions'},{'role':'user','content':'test'}],128,cancel or threading.Event(),chunks.append,time.time()+4)
        return result,''.join(chunks)
    def test_public_reply_only_and_successful_finish(self):
        result,chunks=self.generate();self.assertEqual(result['content'],'public reply');self.assertEqual(result['finish_reason'],'stop')
        self.assertNotIn('PRIVATE',json.dumps(result)+chunks)
    def test_failed_turn_tool_request_and_identity_change_stop(self):
        for mode in ('fail','tool','identity','unknown','unbound'):
            with self.subTest(mode=mode),self.assertRaises(ProviderError):self.generate(mode)
    def test_explicit_native_path_is_host_only_and_validated(self):
        channel=CodexChannel(host_file=self.base/'host.json');native=self.base/'codex.exe';native.write_bytes(b'test native placeholder')
        channel.set_executable(str(native))
        self.assertEqual(channel.settings()['executable'],str(native.resolve()))
        self.assertEqual(channel.finder(),str(native.resolve()))
        for bad in ('codex.exe --anything',str(self.base/'missing.exe'),str(self.server)):
            with self.assertRaises(ValueError):channel.set_executable(bad)
        channel.set_executable('');self.assertEqual(channel.settings()['executable'],'')
    def test_cancel_stalled_child_without_waiting_for_completion(self):
        cancel=threading.Event();timer=threading.Timer(.15,cancel.set);timer.start();started=time.monotonic()
        try:
            with self.assertRaises(ProviderError):self.generate('stall',cancel)
            self.assertLess(time.monotonic()-started,2)
        finally:timer.cancel()

if __name__=='__main__':unittest.main()
