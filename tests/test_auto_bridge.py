import sys,tempfile,threading,time,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def fixture(base):
    base.mkdir(parents=True,exist_ok=True)
    return base
from backend import Bridge
from test_api import FakeClient

class AutoBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=fixture(Path(self.tmp.name)/'room-root');self.data=Path(self.tmp.name)/'app-data'
        self.client=FakeClient();self.bridge=Bridge(self.root,data_dir=self.data,api_client=self.client)
    def call(self,action,payload=None):
        response=self.bridge.call(action,payload);self.assertTrue(response['ok'],response);return response['data']
    def test_complete_via_registered_bridge_and_reopen(self):
        initial=self.call('api_bootstrap');self.assertEqual(initial['profiles'],[])
        profile=self.call('api_profile_save',dict(name='mock',kind='compatible',base_url='https://mock.invalid/v1',model='mock-model',api_key='fake-secret-bridge'))
        self.assertTrue(profile['has_key']);self.assertNotIn('fake-secret',json.dumps(profile))
        run=self.call('api_start',dict(task='简单测试',primary_id=profile['id'],reviewer_id=profile['id'],context_count=0))
        while self.bridge.busy():time.sleep(.01)
        complete=self.call('api_status',{'id':run['id']});self.assertEqual(complete['status'],'completed')
        self.assertNotIn('fake-secret',json.dumps(complete));self.assertFalse((self.root/'room/log.md').exists())
        reopened=Bridge(self.root,data_dir=self.data,api_client=self.client).call('api_session',{'id':run['id']})
        self.assertEqual(len(reopened['data']['steps']),3)
    def test_profile_edits_and_room_commands_cannot_overlap_model(self):
        class Slow(FakeClient):
            def complete(inner,profile,key,messages,max_tokens,cancel,on_chunk,deadline):
                cancel.wait(2)
                return super(Slow,inner).complete(profile,key,messages,max_tokens,cancel,on_chunk,deadline)
        self.bridge._api_client=Slow()
        p=self.call('api_profile_save',dict(name='mock',kind='compatible',base_url='https://mock.invalid',model='mock',api_key='fake-secret'))
        self.call('api_start',dict(task='测试停止',primary_id=p['id'],reviewer_id=p['id'],context_count=0))
        self.assertFalse(self.bridge.call('api_profile_delete_key',{'id':p['id']})['ok'])
        self.assertFalse(self.bridge.call('api_profile_delete',{'id':p['id']})['ok'])
        self.assertFalse(self.bridge.call('start_command',{'command':'status'})['ok'])
        self.call('api_stop')
        deadline=time.monotonic()+3
        while self.bridge.busy() and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.bridge.busy());self.assertEqual(self.call('api_status')['status'],'cancelled')
    def test_invalid_api_actions_and_session_ids(self):
        self.assertFalse(self.bridge.call('api_shell',{'command':'whoami'})['ok'])
        self.assertFalse(self.bridge.call('api_session',{'id':'../../providers'})['ok'])
    def test_delete_profile_removes_only_selected_config_and_keeps_history(self):
        first=self.call('api_profile_save',dict(name='duplicate',kind='compatible',base_url='https://mock.invalid',model='mock',api_key='fake-delete-key'))
        second=self.call('api_profile_save',dict(name='keep',kind='codex_local',model='mock-local'))
        run=self.call('api_start',dict(task='history stays',primary_id=first['id'],reviewer_id=first['id'],context_count=0))
        while self.bridge.busy():time.sleep(.01)
        result=self.call('api_profile_delete',{'id':first['id']})
        self.assertEqual(result['id'],first['id'])
        self.assertEqual([p['id'] for p in self.call('api_bootstrap')['profiles']],[second['id']])
        self.assertEqual(self.call('api_session',{'id':run['id']})['roles']['A']['name'],'duplicate')
        self.assertFalse(self.bridge.call('api_profile_delete',{'id':first['id']})['ok'])
        self.assertNotIn('fake-delete-key',(self.data/'providers.json').read_text(encoding='utf-8'))
        self.call('api_profile_delete',{'id':second['id']});self.assertEqual(self.call('api_bootstrap')['profiles'],[])
    def test_absent_shared_room_does_not_prevent_auto_collaboration(self):
        bridge=Bridge(Path(self.tmp.name)/'missing',data_dir=self.data,api_client=FakeClient())
        self.assertFalse(bridge.call('api_bootstrap')['data']['room_available'])
        p=bridge.call('api_profile_save',dict(name='mock',kind='compatible',base_url='https://mock.invalid',model='mock',api_key='fake-key'))['data']
        result=bridge.call('api_start',dict(task='portable test',primary_id=p['id'],reviewer_id=p['id']))
        self.assertTrue(result['ok'],result)
        while bridge.busy():time.sleep(.01)
        self.assertEqual(bridge.call('api_status')['data']['status'],'completed')
        self.assertEqual(bridge.call('api_status')['data']['context_count'],0)
    def test_collaboration_no_longer_reads_file_room_context_or_persona(self):
        self.call('api_bootstrap')
        def forbid(*args):raise AssertionError('File room must not be read by collaboration')
        from types import SimpleNamespace
        self.assertIsNone(self.bridge._auto.room)
        self.bridge._auto.room=SimpleNamespace(snapshot=forbid,read=forbid)
        p=self.call('api_profile_save',dict(name='mock',kind='compatible',base_url='https://mock.invalid',model='mock',api_key='fake-key'))
        run=self.call('api_start',dict(task='independent collaboration',primary_id=p['id'],reviewer_id=p['id'],context_count=6))
        while self.bridge.busy():time.sleep(.01)
        result=self.call('api_status',{'id':run['id']});self.assertEqual(result['status'],'completed');self.assertEqual(result['context_count'],0)

if __name__=='__main__':unittest.main()
