"""Direct HTTPS/SSE client. No redirects, model tools or reasoning persistence."""
from contextlib import contextmanager
from urllib.parse import urlsplit
import http.client,json,socket,ssl,threading,time
from credential_store import validate_url

class ProviderError(ValueError):pass
class Cancelled(ProviderError):pass

def usage_fields(value):
    if not isinstance(value,dict):return None
    if not all(type(value.get(k)) is int and 0<=value[k]<=10**9 for k in ('prompt_tokens','completion_tokens')):return None
    return {k:value[k] for k in ('prompt_tokens','completion_tokens')}

class ProviderClient:
    def __init__(self,connection_factory=None):
        self.factory=connection_factory;self.lock=threading.Lock();self.sock=None
    def interrupt(self):
        with self.lock:sock=self.sock
        if sock:
            try:sock.shutdown(socket.SHUT_RDWR)
            except OSError:pass
    @contextmanager
    def request(self,profile,key,method,suffix,payload,cancel,deadline):
        url=urlsplit(validate_url(profile['base_url']));remaining=deadline-time.time()
        if cancel.is_set():raise Cancelled('已停止')
        if remaining<=0:raise ProviderError('已达到 10 分钟时间上限')
        timeout=max(.1,min(15,remaining))
        connection=(self.factory(url.hostname,url.port,timeout) if self.factory else http.client.HTTPSConnection(url.hostname,url.port,timeout=timeout,context=ssl.create_default_context()))
        response=None
        try:
            connection.connect()
            with self.lock:self.sock=connection.sock
            if cancel.is_set():raise Cancelled('已停止')
            body=json.dumps(payload,ensure_ascii=False).encode('utf-8') if payload is not None else None
            connection.request(method,(url.path.rstrip('/')+suffix) or '/',body=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'text/event-stream, application/json','User-Agent':'LocalAgentWorkbench/2'})
            response=connection.getresponse()
            if response.status!=200:
                messages={400:'请求参数被接口拒绝，请检查模型 ID 或输出设置',401:'密钥无效或已失效',402:'API 余额不足',403:'接口无访问权限',404:'接口或模型不存在，请检查基础地址',429:'接口限流或配额不足，请稍后手动重试'}
                if 300<=response.status<400:raise ProviderError('接口返回重定向，已拒绝携带密钥跳转；请填写最终 HTTPS 地址')
                raise ProviderError(messages.get(response.status,f'服务商返回 HTTP {response.status}，本轮已停止'))
            yield response
        except (ProviderError,Cancelled):raise
        except (OSError,http.client.HTTPException,ssl.SSLError):
            if cancel.is_set():raise Cancelled('已停止') from None
            raise ProviderError('连接失败或读取超时，请检查网络、证书和接口配置；未自动重试') from None
        finally:
            with self.lock:self.sock=None
            if response:response.close()
            connection.close()
    def models(self,profile,key):
        with self.request(profile,key,'GET','/models',None,threading.Event(),time.time()+15) as response:
            raw=response.read(256*1024+1)
            if len(raw)>256*1024:raise ProviderError('模型列表响应过大')
            try:rows=json.loads(raw).get('data')
            except (ValueError,AttributeError):raise ProviderError('接口未返回有效模型列表') from None
            if not isinstance(rows,list):raise ProviderError('接口未返回有效模型列表')
            return [r['id'] for r in rows[:200] if isinstance(r,dict) and isinstance(r.get('id'),str) and len(r['id'])<=200 and (not key or key not in r['id'])]
    def complete(self,profile,key,messages,max_tokens,cancel,on_chunk,deadline):
        payload=dict(model=profile['model'],messages=messages,max_tokens=max_tokens,stream=True,stream_options={'include_usage':True})
        if profile['kind']=='deepseek':payload['thinking']={'type':'disabled'}
        content='';pending='';usage=None;finish=None;model=profile['model'];wire=0
        def accept(value,stream=True):
            nonlocal content,pending,usage,finish,model
            if not isinstance(value,dict):raise ProviderError('模型响应格式无效')
            usage=usage_fields(value.get('usage')) or usage
            if isinstance(value.get('model'),str) and len(value['model'])<=200:model=value['model'].replace(key,'[已隐藏密钥]') if key else value['model']
            choices=value.get('choices')
            if not isinstance(choices,list):raise ProviderError('模型响应缺少 choices')
            if not choices:return
            row=choices[0]
            if not isinstance(row,dict):raise ProviderError('模型响应格式无效')
            message=row.get('delta' if stream else 'message',{})
            if not isinstance(message,dict):raise ProviderError('模型回复不是文本消息')
            if message.get('tool_calls') or message.get('function_call'):raise ProviderError('本会话仅支持文字回复，不执行模型工具调用')
            delta=message.get('content') or ''
            if not isinstance(delta,str):raise ProviderError('模型回复不是文本')
            # Private reasoning fields are intentionally never read or retained.
            if delta:
                pending+=delta
                if key:pending=pending.replace(key,'[已隐藏密钥]')
                if len(content)+len(pending)>20000:raise ProviderError('单次公开回复超过 20000 字符上限，已停止交接')
                # Retain a tail so a credential split across SSE deltas cannot leak.
                keep=max(0,len(key)-1)
                if len(pending)>keep:
                    safe=pending[:-keep] if keep else pending
                    pending=pending[-keep:] if keep else ''
                    content+=safe;on_chunk(safe)
            finish=row.get('finish_reason') or finish
        try:
            with self.request(profile,key,'POST','/chat/completions',payload,cancel,deadline) as response:
                if 'text/event-stream' not in (response.getheader('Content-Type') or ''):
                    raw=response.read(1024*1024+1)
                    if len(raw)>1024*1024:raise ProviderError('模型响应过大')
                    accept(json.loads(raw),False)
                else:
                    while True:
                        if cancel.is_set():raise Cancelled('已停止')
                        if time.time()>=deadline:raise ProviderError('已达到 10 分钟时间上限')
                        line=response.readline(65537);wire+=len(line)
                        if not line:break
                        if len(line)>65536 or wire>2*1024*1024:raise ProviderError('流式响应超过大小上限，已停止')
                        line=line.decode('utf-8').strip()
                        if not line.startswith('data:'):continue
                        data=line[5:].strip()
                        if data=='[DONE]':break
                        if data:accept(json.loads(data))
        except (ValueError,UnicodeError) as exc:
            if isinstance(exc,ProviderError):raise
            raise ProviderError('模型返回了无效的 JSON 或 UTF-8 数据，已停止交接') from None
        if cancel.is_set():raise Cancelled('已停止')
        if finish!='stop':raise ProviderError('模型输出被截断或未正常结束，未交给下一席；请调整单次输出上限后新建会话')
        if pending:content+=pending;on_chunk(pending)
        if not content.strip():raise ProviderError('模型未返回公开文字，已停止交接')
        return dict(content=content,usage=usage,model=model,finish_reason=finish)
