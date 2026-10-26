import http.client,json,sys,threading,time,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from provider_client import ProviderClient,ProviderError

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.mode='stream';owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                self.send_response(200);self.end_headers()
                self.wfile.write(json.dumps({'data':[{'id':'safe-model'},{'id':'echo-fake-secret-key'}]}).encode())
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length','0')))
                if owner.mode=='redirect':
                    self.send_response(302);self.send_header('Location','https://should-not-be-contacted.invalid');self.end_headers();return
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                if owner.mode=='stall':
                    self.wfile.write(b'data: ');self.wfile.flush();time.sleep(1);return
                pieces=['主张：你好。'] if owner.mode!='secret' else ['prefix fake-sec','ret-key suffix']
                for text in pieces:
                    event=dict(model='model',choices=[dict(delta={'content':text,'reasoning_content':'PRIVATE-REASONING'},finish_reason=None)])
                    self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode());self.wfile.flush()
                final=dict(choices=[dict(delta={},finish_reason='length' if owner.mode=='length' else 'stop')],usage={'prompt_tokens':3,'completion_tokens':2})
                self.wfile.write(('data: '+json.dumps(final)+'\n\ndata: [DONE]\n\n').encode());self.wfile.flush()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.client=ProviderClient(connection_factory=lambda host,port,timeout:http.client.HTTPConnection(host,port,timeout=timeout))
        self.profile=dict(base_url=f'https://127.0.0.1:{self.server.server_port}',model='model',kind='compatible')
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
    def complete(self,cancel=None):
        chunks=[];response=self.client.complete(self.profile,'fake-secret-key',[{'role':'user','content':'hello'}],128,cancel or threading.Event(),chunks.append,time.time()+5)
        return response,''.join(chunks)
    def test_sse_real_http_and_private_reasoning_not_retained(self):
        response,chunks=self.complete();self.assertEqual(response['content'],'主张：你好。');self.assertEqual(chunks,response['content'])
        self.assertNotIn('PRIVATE-REASONING',json.dumps(response)+chunks)
    def test_redirect_never_followed(self):
        self.mode='redirect'
        with self.assertRaisesRegex(ProviderError,'重定向'):self.complete()
    def test_model_list_never_returns_reflected_credential(self):
        self.assertEqual(self.client.models(self.profile,'fake-secret-key'),['safe-model'])
    def test_truncated_output_is_not_a_completed_reply(self):
        self.mode='length'
        with self.assertRaisesRegex(ProviderError,'截断'):self.complete()
    def test_secret_split_across_chunks_never_leaks(self):
        self.mode='secret';response,chunks=self.complete()
        self.assertNotIn('fake-secret-key',chunks);self.assertNotIn('fake-secret-key',response['content'])
    def test_cancel_interrupts_a_stalled_network_read(self):
        self.mode='stall';cancel=threading.Event()
        def stop():cancel.set();self.client.interrupt()
        timer=threading.Timer(.1,stop);timer.start();started=time.monotonic()
        try:
            with self.assertRaises(ProviderError):self.complete(cancel)
            self.assertLess(time.monotonic()-started,2)
        finally:timer.cancel()

if __name__=='__main__':unittest.main()
