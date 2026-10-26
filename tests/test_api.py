import unittest,tempfile,sys,time,threading,json
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from credential_store import ProfileStore,protect,unprotect,validate_url
from session_store import SessionStore
from orchestrator import Orchestrator
from provider_client import ProviderError

def await_done(engine):
    deadline=time.monotonic()+4
    while engine.busy() and time.monotonic()<deadline:time.sleep(.01)
    if engine.busy():raise AssertionError('Engine did not stop')
    return engine.status()
class FakeClient:
    def __init__(self,fail_at=0,cancel_at=0):self.calls=[];self.fail_at=fail_at;self.cancel_at=cancel_at
    def complete(self,profile,key,messages,max_tokens,cancel,on_chunk,deadline):
        self.calls.append(messages)
        if len(self.calls)==self.fail_at:raise ProviderError('模拟错误')
        text='主张：reply-'+str(len(self.calls));on_chunk(text)
        if len(self.calls)==self.cancel_at:cancel.set()
        return dict(content=text,model=profile['model'],usage={'prompt_tokens':10,'completion_tokens':5},finish_reason='stop')
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.profiles=ProfileStore(self.base,encrypt=lambda s:'encrypted:'+s.encode().hex(),decrypt=lambda s:bytes.fromhex(s.removeprefix('encrypted:')).decode())
        self.a=self.profiles.save(dict(name='A provider',kind='deepseek',base_url='https://api.deepseek.com',model='deepseek-flash',api_key='fake-secret-A'))
        self.b=self.profiles.save(dict(name='B provider',kind='compatible',base_url='https://example.com/v1',model='reviewer',api_key='fake-secret-B'))
        self.sessions=SessionStore(self.base/'sessions')
    def engine(self,client):return Orchestrator(self.sessions,self.profiles,client,persona_loader=lambda name:'以固定席位格式表达真实意见。')
    def payload(self,**changes):return dict(task='给一个简单建议',primary_id=self.a['id'],reviewer_id=self.b['id'],rounds=1,max_tokens=1024,context_count=0,persona='conductor',**changes)
    def test_profile_never_returns_secret_and_origin_change_needs_new_key(self):
        self.assertNotIn('fake-secret',json.dumps(self.profiles.list()))
        self.assertNotIn('fake-secret',(self.base/'providers.json').read_text(encoding='utf-8'))
        self.assertEqual(self.profiles.credentials(self.a['id'])[1],'fake-secret-A')
        with self.assertRaises(ValueError):self.profiles.save(dict(self.a,base_url='https://other.example',api_key=''))
        result=self.profiles.delete_key(self.a['id']);self.assertFalse(result['has_key'])
    def test_urls_reject_userinfo_query_http_and_redirect_tricks(self):
        for bad in ('http://api.deepseek.com','https://name:pass@example.com','https://example.com?key=x','https://example.com/#x','file:///x','https://example.com/chat/completions'):
            with self.assertRaises(ValueError,msg=bad):validate_url(bad)
        self.assertEqual(validate_url('https://api.deepseek.com/'),'https://api.deepseek.com')
    def test_real_contribution_chain_and_finite_default(self):
        client=FakeClient();engine=self.engine(client);engine.start(self.payload());run=await_done(engine)
        self.assertEqual(run['status'],'completed');self.assertEqual(run['call_count'],3)
        self.assertEqual([s['seat'] for s in run['steps']],['A','B','A'])
        self.assertIn('reply-1',json.dumps(client.calls[1],ensure_ascii=False));self.assertIn('reply-2',json.dumps(client.calls[2],ensure_ascii=False))
        self.assertNotIn('fake-secret',json.dumps(run));self.assertEqual(run['usage']['completion_tokens'],15)
        loaded=self.sessions.load(run['id']);self.assertEqual(len(loaded['steps']),3)
    def test_each_seat_uses_its_own_style_and_revision_keeps_a_style(self):
        client=FakeClient();engine=self.engine(client);payload=self.payload()
        payload['seat_styles']={'A':{'preset':'custom','text':'A_STYLE 温和解释'},'B':{'preset':'custom','text':'B_STYLE 直接审查'}}
        engine.start(payload);run=await_done(engine)
        for number,own,other in [(0,'A_STYLE','B_STYLE'),(1,'B_STYLE','A_STYLE'),(2,'A_STYLE','B_STYLE')]:
            self.assertIn(own,client.calls[number][0]['content']);self.assertNotIn(other,client.calls[number][0]['content'])
        self.assertEqual(run['seat_styles']['B']['text'],'B_STYLE 直接审查')
    def test_custom_styles_validate_before_start(self):
        for invalid in [{'A':{'preset':'custom','text':''}}, {'A':{'preset':'custom','text':'x'*3001}}, {'A':{'preset':'missing'}}, {'A':'bad'}, {'C':{'preset':'conductor'}}]:
            payload=self.payload();payload['seat_styles']=invalid
            with self.subTest(value=str(invalid)[:40]),self.assertRaises(ValueError):self.engine(FakeClient()).start(payload)
    def test_new_personas_work_in_collaboration_and_save_frozen_instructions(self):
        client=FakeClient();engine=self.engine(client);payload=self.payload()
        payload['seat_styles']={'A':{'preset':'lele'},'B':{'preset':'jingshui'}}
        engine.start(payload);run=await_done(engine)
        self.assertEqual(run['status'],'completed')
        self.assertIn('你是「明快助手」',client.calls[0][0]['content'])
        self.assertIn('你是「沉稳助手」',client.calls[1][0]['content'])
        self.assertIn('性格形容词库',run['seat_instructions']['A'])
    def test_legacy_retry_uses_saved_shared_instructions(self):
        client=FakeClient(fail_at=1);engine=self.engine(client);engine.start(self.payload());run=await_done(engine)
        run.pop('seat_styles');run.pop('seat_instructions');run['instructions']='LEGACY_SHARED_STYLE';self.sessions.save(run)
        engine.persona_loader=lambda name:(_ for _ in ()).throw(AssertionError('Legacy retry must use saved instructions'))
        engine.retry(run['id']);run=await_done(engine)
        self.assertEqual(run['status'],'completed')
        for messages in client.calls[1:]:self.assertIn('LEGACY_SHARED_STYLE',messages[0]['content'])
    def test_maximum_nine_calls_and_invalid_limits(self):
        client=FakeClient();engine=self.engine(client)
        payload=self.payload();payload['rounds']=3;engine.start(payload);run=await_done(engine)
        self.assertEqual(run['call_count'],9);self.assertEqual(len(client.calls),9)
        with self.assertRaises(ValueError):engine.retry(run['id'])
        for key,value in [('rounds',4),('rounds',True),('max_tokens',100000),('max_tokens',True)]:
            payload=self.payload();payload[key]=value
            with self.assertRaises(ValueError):engine.start(payload)
    def test_selectable_budget_allows_thirty_and_rejects_invalid_plan(self):
        client=FakeClient();engine=self.engine(client);payload=self.payload();payload.update(rounds=10,call_limit=30)
        engine.start(payload);run=await_done(engine)
        self.assertEqual(run['call_count'],30);self.assertEqual(run['call_limit'],30);self.assertEqual(run['status'],'completed')
        for changes in ({'call_limit':31},{'call_limit':True},{'rounds':11,'call_limit':30},{'rounds':3,'call_limit':6}):
            payload=self.payload();payload.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):engine.start(payload)
    def test_retry_obeys_selected_lower_budget(self):
        client=FakeClient(fail_at=1);engine=self.engine(client);payload=self.payload();payload['call_limit']=3
        engine.start(payload);run=await_done(engine)
        for _ in range(2):
            client.fail_at=len(client.calls)+1;engine.retry(run['id']);run=await_done(engine)
        with self.assertRaisesRegex(ValueError,'3 次'):engine.retry(run['id'])
        self.assertEqual(run['call_count'],3)
    def test_error_stops_without_auto_retry(self):
        client=FakeClient(fail_at=2);engine=self.engine(client);engine.start(self.payload());run=await_done(engine)
        self.assertEqual(run['status'],'failed');self.assertEqual(run['call_count'],2);self.assertEqual(len(client.calls),2)
        self.assertEqual(run['steps'][0]['state'],'completed')
        engine.retry(run['id']);run=await_done(engine)
        self.assertEqual(run['status'],'completed');self.assertEqual(run['call_count'],4)
    def test_cancel_does_not_hand_partial_to_next_model(self):
        client=FakeClient(cancel_at=1);engine=self.engine(client);engine.start(self.payload());run=await_done(engine)
        self.assertEqual(run['status'],'cancelled');self.assertEqual(len(client.calls),1);self.assertEqual(run['steps'][0]['state'],'cancelled')
    def test_deadline_budget_is_not_reset_by_retry(self):
        client=FakeClient(fail_at=1);engine=self.engine(client);engine.start(self.payload());run=await_done(engine)
        run['deadline']=time.time()-1;self.sessions.save(run)
        with self.assertRaises(ValueError):engine.retry(run['id'])
        self.assertEqual(len(client.calls),1)
    def test_restart_never_automatically_resends(self):
        client=FakeClient();engine=self.engine(client);engine.start(self.payload());run=await_done(engine)
        run['status']='running';self.sessions.save(run)
        recovered=SessionStore(self.base/'sessions');recovered.recover_interrupted()
        self.assertEqual(recovered.load(run['id'])['status'],'interrupted');self.assertEqual(len(client.calls),3)
    def test_session_path_escape_is_rejected(self):
        with self.assertRaises(ValueError):self.sessions.load('../providers')
    def test_damaged_session_does_not_block_other_history_or_new_tasks(self):
        empty=self.sessions.base/('a'*32);empty.mkdir(parents=True)
        damaged=self.sessions.base/('b'*32);damaged.mkdir();(damaged/'session.json').write_text('{broken',encoding='utf-8')
        self.sessions.recover_interrupted()
        self.assertEqual([r['status'] for r in self.sessions.list()],['corrupt','corrupt'])
        engine=self.engine(FakeClient());engine.start(self.payload());run=await_done(engine)
        self.assertEqual(self.sessions.load(run['id'])['status'],'completed')
        self.assertEqual(len(self.sessions.list()),3)
        self.assertEqual((damaged/'session.json').read_text(encoding='utf-8'),'{broken')
    def test_oversized_context_is_rejected_before_creating_session(self):
        engine=self.engine(FakeClient())
        with self.assertRaisesRegex(ValueError,'上下文'):engine.start(self.payload(),['字'*300000])
        self.assertEqual(self.sessions.list(),[])
    def test_usage_is_unknown_when_any_completed_stage_omits_usage(self):
        class MixedClient(FakeClient):
            def complete(self,*args):
                result=super().complete(*args)
                if len(self.calls)==2:result['usage']=None
                return result
        engine=self.engine(MixedClient());engine.start(self.payload());run=await_done(engine)
        self.assertFalse(run['usage']['known'])
    def test_manual_failures_share_nine_attempt_budget(self):
        class FailingClient(FakeClient):
            def complete(self,*args):self.calls.append(args);raise ProviderError('模拟失败')
        client=FailingClient();engine=self.engine(client);engine.start(self.payload());run=await_done(engine)
        for _ in range(8):engine.retry(run['id']);run=await_done(engine)
        self.assertEqual(run['call_count'],9)
        with self.assertRaisesRegex(ValueError,'9 次'):engine.retry(run['id'])
        self.assertEqual(len(client.calls),9)
    def test_watchdog_cancels_pending_request_without_handoff(self):
        class SlowClient(FakeClient):
            def complete(self,*args):
                self.calls.append(args);args[4].wait(2)
                raise ProviderError('模拟读取结束')
        timer=threading.Timer;client=SlowClient();engine=self.engine(client)
        with patch('orchestrator.threading.Timer',side_effect=lambda seconds,callback:timer(.05,callback)):
            engine.start(self.payload());run=await_done(engine)
        self.assertEqual(run['status'],'cancelled');self.assertIn('时间上限',run['error']);self.assertEqual(len(client.calls),1)
    def test_real_windows_dpapi_roundtrip(self):
        encrypted=protect('test-only-no-real-secret')
        self.assertNotIn('test-only',encrypted);self.assertEqual(unprotect(encrypted),'test-only-no-real-secret')

if __name__=='__main__':unittest.main()
