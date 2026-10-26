import json,sys,tempfile,time,unittest,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import Bridge
from test_api import FakeClient

class ChatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.client=FakeClient();self.bridge=Bridge(self.base/'missing-room',data_dir=self.base/'data',api_client=self.client)
        self.a=self.call('api_profile_save',dict(name='model A',kind='compatible',base_url='https://mock.invalid',model='alpha',api_key='fake-secret'))
        self.b=self.call('api_profile_save',dict(name='model B',kind='compatible',base_url='https://mock.invalid',model='beta',api_key='fake-secret'))
    def call(self,action,payload=None):
        result=self.bridge.call(action,payload);self.assertTrue(result['ok'],result);return result['data']
    def create(self):return self.call('api_chat_create',dict(primary_id=self.a['id'],reviewer_id=self.b['id'],seat_styles={'A':{'preset':'custom','text':'A_STYLE 温和'},'B':{'preset':'custom','text':'B_STYLE 活泼'}}))
    def done(self,identifier):
        end=time.monotonic()+4
        while self.bridge.busy() and time.monotonic()<end:time.sleep(.01)
        self.assertFalse(self.bridge.busy());return self.call('api_chat_status',{'id':identifier})
    def test_hello_group_reply_and_continued_history(self):
        chat=self.create();self.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'));chat=self.done(chat['id'])
        self.assertEqual(chat['status'],'idle');self.assertEqual([m['seat'] for m in chat['messages']],['U','A','B'])
        self.assertIn('reply-1',json.dumps(self.client.calls[1]));self.assertNotIn('本步骤：',self.client.calls[0][0]['content'])
        self.assertIn('A_STYLE',self.client.calls[0][0]['content']);self.assertNotIn('B_STYLE',self.client.calls[0][0]['content'])
        self.call('api_chat_send',dict(id=chat['id'],text='接着聊',target='B'));chat=self.done(chat['id'])
        self.assertEqual(chat['call_count'],3);self.assertEqual(chat['messages'][-1]['seat'],'B')
        self.assertIn('hello',json.dumps(self.client.calls[-1]));self.assertIn('reply-2',json.dumps(self.client.calls[-1]))
        self.assertNotIn('fake-secret',json.dumps(chat));self.assertFalse((self.base/'data/sessions').exists())
        other=Bridge(self.base/'missing',data_dir=self.base/'data',api_client=FakeClient())
        self.assertEqual(len(other.call('api_chat_status',{'id':chat['id']})['data']['messages']),5)
    def test_failure_never_invokes_second_seat_and_no_retry(self):
        self.client.fail_at=1;chat=self.create();self.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'));chat=self.done(chat['id'])
        self.assertEqual(chat['status'],'failed');self.assertEqual(len(self.client.calls),1)
        self.assertEqual(chat['messages'][-1]['state'],'failed')
    def test_budget_validated_before_user_message_is_added(self):
        chat=self.create();service=self.bridge._auto.chat
        chat['call_count']=29;service.sessions.save(chat)
        result=self.bridge.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'));self.assertFalse(result['ok'])
        self.assertEqual(self.call('api_chat_status',{'id':chat['id']})['messages'],[])
        self.call('api_chat_send',dict(id=chat['id'],text='hello',target='A'));chat=self.done(chat['id'])
        self.assertEqual(chat['call_count'],30)
        self.assertFalse(self.bridge.call('api_chat_send',dict(id=chat['id'],text='again',target='A'))['ok'])
    def test_cancel_and_shared_lock(self):
        class Slow(FakeClient):
            def complete(self,profile,key,messages,max_tokens,cancel,on_chunk,deadline):
                cancel.wait(3);return super().complete(profile,key,messages,max_tokens,cancel,on_chunk,deadline)
        self.bridge._auto.chat.client=Slow();chat=self.create();self.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'))
        self.assertFalse(self.bridge.call('api_profile_delete',{'id':self.a['id']})['ok'])
        self.assertFalse(self.bridge.call('api_start',dict(task='busy',primary_id=self.a['id'],reviewer_id=self.b['id']))['ok'])
        self.assertTrue(self.bridge._api_active());self.bridge._stop_api();chat=self.done(chat['id'])
        self.assertEqual(chat['status'],'cancelled');self.assertEqual(chat['call_count'],1)
    def test_stop_keeps_shared_gate_until_transport_interrupt_finishes(self):
        class PausedInterrupt(FakeClient):
            entered=threading.Event();release=threading.Event()
            def complete(self,profile,key,messages,max_tokens,cancel,on_chunk,deadline):
                cancel.wait(3)
                from provider_client import Cancelled
                raise Cancelled('stopped')
            def interrupt(self):self.entered.set();self.release.wait(2)
        client=PausedInterrupt();self.bridge._auto.chat.client=client
        chat=self.create();self.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'))
        stopper=threading.Thread(target=lambda:self.bridge.call('api_chat_stop'));stopper.start()
        try:
            self.assertTrue(client.entered.wait(1));end=time.monotonic()+.2
            while self.bridge.busy() and time.monotonic()<end:time.sleep(.01)
            held=self.bridge.busy()
        finally:client.release.set();stopper.join(3);self.done(chat['id'])
        self.assertTrue(held,'Transport interrupt must finish before a new operation can acquire the gate')

    def test_explicit_memory_scope_reuse_and_clear(self):
        for scope,text in [('A','A_PRIVATE'),('B','B_PRIVATE'),('shared','SHARED_INFO')]:
            self.call('api_chat_memory_save',dict(scope=scope,kind='profile',text=text))
        chat=self.create();self.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'));chat=self.done(chat['id'])
        a=json.dumps(self.client.calls[0]);b=json.dumps(self.client.calls[1])
        self.assertIn('A_PRIVATE',a);self.assertNotIn('B_PRIVATE',a)
        self.assertIn('B_PRIVATE',b);self.assertNotIn('A_PRIVATE',b)
        self.assertIn('SHARED_INFO',a);self.assertIn('SHARED_INFO',b)
        self.assertEqual(len(chat['memory_used']['A']),2)
        self.assertFalse(self.bridge.call('api_chat_memory_clear',{})['ok'])
        self.call('api_chat_memory_clear',{'confirm':True})
        self.assertEqual(self.call('api_chat_memory')['count'],0)
        self.assertEqual(len(self.call('api_chat_status',{'id':chat['id']})['messages']),3)
        new=self.create();self.call('api_chat_send',dict(id=new['id'],text='hello',target='A'));self.done(new['id'])
        self.assertNotIn('SHARED_INFO',json.dumps(self.client.calls[-1]))

    def test_discussion_is_finite_and_budget_checked_before_send(self):
        chat=self.create()
        for rounds in (0,3,True,7):self.assertFalse(self.bridge.call('api_chat_discuss',dict(id=chat['id'],text='topic',target='AB',rounds=rounds))['ok'])
        self.call('api_chat_discuss',dict(id=chat['id'],text='topic',target='BA',rounds=2));chat=self.done(chat['id'])
        self.assertEqual(chat['call_count'],4);self.assertEqual(chat['status'],'idle')
        self.assertEqual([m['seat'] for m in chat['messages']],['U','B','A','B','A'])
        self.assertIn('reply-3',json.dumps(self.client.calls[-1]))
        chat['call_count']=27;self.bridge._auto.chat.sessions.save(chat)
        self.assertFalse(self.bridge.call('api_chat_discuss',dict(id=chat['id'],text='extra',target='AB',rounds=2))['ok'])
        self.assertEqual(len(self.bridge._auto.chat.sessions.load(chat['id'])['messages']),5)

    def test_failed_discussion_stops_before_next_round(self):
        self.client.fail_at=2;chat=self.create()
        self.call('api_chat_discuss',dict(id=chat['id'],text='topic',target='AB',rounds=6));chat=self.done(chat['id'])
        self.assertEqual(chat['status'],'failed');self.assertEqual(chat['call_count'],2)

    def test_delete_requires_confirmation_removes_only_target_and_clears_active(self):
        first=self.create();second=self.create()
        self.call('api_chat_memory_save',dict(scope='shared',kind='profile',text='KEEP_MEMORY'))
        self.assertFalse(self.bridge.call('api_chat_delete',{'id':second['id']})['ok'])
        self.call('api_chat_delete',{'id':first['id'],'confirm':True})
        self.assertEqual(self.call('api_chat_status')['id'],second['id'])
        self.assertFalse((self.base/'data/chats'/first['id']).exists())
        self.call('api_chat_delete',{'id':second['id'],'confirm':True})
        self.assertIsNone(self.call('api_chat_status'))
        self.assertEqual(self.call('api_chat_bootstrap')['sessions'],[])
        self.assertEqual(self.call('api_chat_memory')['count'],1)
        self.assertFalse(self.bridge.call('api_chat_delete',{'id':'../outside','confirm':True})['ok'])

    def test_delete_rejects_busy_and_unexpected_directory_contents(self):
        chat=self.create();service=self.bridge._auto.chat
        self.bridge._command_lock.acquire()
        try:self.assertFalse(self.bridge.call('api_chat_delete',{'id':chat['id'],'confirm':True})['ok'])
        finally:self.bridge._command_lock.release()
        extra=self.base/'data/chats'/chat['id']/'keep.txt';extra.write_text('keep')
        self.assertFalse(self.bridge.call('api_chat_delete',{'id':chat['id'],'confirm':True})['ok'])
        self.assertTrue(extra.exists());self.assertTrue((extra.parent/'session.json').exists())

    def test_continue_adds_exactly_one_round_without_fabricated_user_message(self):
        chat=self.create()
        self.assertFalse(self.bridge.call('api_chat_continue',{'id':chat['id']})['ok'])
        self.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'));self.done(chat['id'])
        self.call('api_chat_continue',dict(id=chat['id'],target='BA'));chat=self.done(chat['id'])
        self.assertEqual(chat['call_count'],4)
        self.assertEqual([m['seat'] for m in chat['messages']],['U','A','B','B','A'])
        self.assertIn('reply-2',json.dumps(self.client.calls[-2]))

    def test_reply_validates_source_and_keeps_quote_in_request(self):
        chat=self.create();self.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'));chat=self.done(chat['id'])
        source=chat['messages'][1]
        self.assertFalse(self.bridge.call('api_chat_send',dict(id=chat['id'],text='agree',target='A',reply_to='bad-id'))['ok'])
        self.call('api_chat_send',dict(id=chat['id'],text='agree',target='A',reply_to=source['id']));chat=self.done(chat['id'])
        self.assertEqual(chat['messages'][-2]['reply_to'],source['id'])
        prompt=json.dumps(self.client.calls[-1],ensure_ascii=False)
        self.assertIn('引用 A',prompt);self.assertIn('reply-1',prompt)

    def test_export_styles_and_scoped_memory_without_credentials(self):
        chat=self.create()
        for scope,text in [('A','A_MEMORY'),('B','B_MEMORY'),('shared','COMMON')]:self.call('api_chat_memory_save',dict(scope=scope,kind='profile',text=text))
        exported=self.call('api_chat_export',dict(id=chat['id'],seat='A',include_memory=True))
        content=json.loads(exported['text'])
        self.assertEqual(content['schema'],'agent-workbench-style');self.assertEqual(content['version'],1)
        self.assertEqual(set(content['styles']),{'A'});self.assertIn('A_STYLE',content['styles']['A']['text'])
        self.assertEqual({r['scope'] for r in content['memories']},{'A','shared'})
        self.assertNotIn('B_MEMORY',exported['text']);self.assertNotIn('fake-secret',exported['text'])
        self.assertNotIn('mock.invalid',exported['text']);self.assertNotIn('messages',content)
        both=self.call('api_chat_export',dict(id=chat['id'],seat='both',include_memory=False))
        self.assertEqual(json.loads(both['text'])['memories'],[])
        self.assertEqual(len(self.client.calls),0)

    def test_export_save_callback_and_cancel(self):
        chat=self.create();payload=dict(id=chat['id'],seat='both',include_memory=False)
        self.bridge.export_saver=lambda filename,text:False
        self.assertFalse(self.call('api_chat_export_save',payload)['saved'])
        written=[];self.bridge.export_saver=lambda filename,text:written.append((filename,json.loads(text))) or True
        self.assertTrue(self.call('api_chat_export_save',payload)['saved'])
        self.assertEqual(written[0][0],'agent-style-both.json')
        self.assertEqual(set(written[0][1]['styles']),{'A','B'})

    def test_memory_source_is_explicit_validated_and_preserved_after_chat_deleted(self):
        chat=self.create();self.call('api_chat_send',dict(id=chat['id'],text='hello',target='A'));chat=self.done(chat['id'])
        message=chat['messages'][-1];source=dict(chat_id=chat['id'],message_id=message['id'],excerpt=message['content'][:5])
        payload=dict(scope='A',kind='preference',text='喜欢这种简洁表达',source=source)
        memory=self.call('api_chat_memory_save',payload)['items'][0]
        self.assertEqual(memory['source']['seat'],'A');self.assertEqual(memory['source']['excerpt'],source['excerpt'])
        self.assertFalse(self.bridge.call('api_chat_memory_save',dict(payload,source=dict(source,excerpt='NOT ACTUAL WORDS')))['ok'])
        self.assertFalse(self.bridge.call('api_chat_memory_save',dict(payload,source=dict(source,message_id='wrong')))['ok'])
        self.call('api_chat_delete',dict(id=chat['id'],confirm=True))
        edited=self.call('api_chat_memory_save',dict(memory,text='我偏好简洁表达'))['items'][0]
        self.assertEqual(edited['source'],memory['source'])
        self.assertEqual(self.call('api_chat_memory')['count'],1)

    def test_new_personas_and_library_reach_model_and_export_snapshot(self):
        chat=self.call('api_chat_create',dict(primary_id=self.a['id'],reviewer_id=self.b['id'],seat_styles={'A':{'preset':'lele'},'B':{'preset':'jingshui'}}))
        snapshot=chat['seat_styles']['A']['resolved_text']
        self.call('api_chat_send',dict(id=chat['id'],text='hello',target='AB'));self.done(chat['id'])
        self.assertIn('你是「明快助手」',self.client.calls[0][0]['content'])
        self.assertIn('你是「沉稳助手」',self.client.calls[1][0]['content'])
        self.assertIn('性格形容词库',self.client.calls[1][0]['content'])
        exported=json.loads(self.call('api_chat_export',dict(id=chat['id'],seat='A',include_memory=False))['text'])
        self.assertEqual(exported['styles']['A']['resolved_text'],snapshot)

if __name__=='__main__':unittest.main()
