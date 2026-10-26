"""Local Codex app-server adapter. No auth-file reads or shell command strings."""
from pathlib import Path
from contextlib import contextmanager
import json,os,queue,shutil,subprocess,tempfile,threading,time,sys
from provider_client import ProviderError,Cancelled
from credential_store import atomic_json

FLAGS={name:False for name in ('shell_tool','unified_exec','code_mode','multi_agent','multi_agent_v2','apps','plugins','hooks','image_generation','view_image','in_app_browser','workspace_dependencies','skill_search','sleep_tool','goals','unbounded_connection_retries')}
FLAGS.update(environment_access=True,skip_host_skill_discovery=True)
CONFIG=dict(features=FLAGS,web_search='disabled',notify=[],agents={'enabled':False},tools={'view_image':False})

def find_codex(preferred=''):
    """Use host-relative installation locations; never persist a user's absolute path."""
    native='codex.exe' if os.name=='nt' else 'codex'
    if preferred:return str(Path(preferred).resolve()) if Path(preferred).is_file() else None
    candidates=[shutil.which(native),str(Path(sys.executable).parent/native)]
    if os.name=='nt':
        base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'OpenAI/Codex/bin'
        if base.is_dir():candidates.extend(str(p) for p in sorted(base.glob('*/codex.exe'),key=lambda p:p.stat().st_mtime,reverse=True))
    else:candidates.extend(str(Path.home()/p/native) for p in ('.local/bin','bin'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and Path(candidate).suffix.lower() not in ('.cmd','.bat','.ps1'):
            return str(Path(candidate).resolve())
    return None

def command(executable):
    arguments=[executable,'app-server','--listen','stdio://']
    for key,value in CONFIG.items():
        if isinstance(value,dict):
            for sub,setting in value.items():arguments+=['-c',key+'.'+sub+'='+json.dumps(setting,separators=(',',':'))]
        else:arguments+=['-c',key+'='+json.dumps(value,separators=(',',':'))]
    return arguments

class Rpc:
    def __init__(self,args,cwd,cancel,deadline):
        self.cancel=cancel;self.deadline=deadline;self.sequence=0;self.events=queue.Queue(maxsize=256)
        self.process=subprocess.Popen(args,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.closed=threading.Event()
        def read():
            total=0
            try:
                while not self.closed.is_set():
                    raw=self.process.stdout.readline(262145);total+=len(raw)
                    if not raw:break
                    if len(raw)>262144 or total>4*1024*1024:raise ValueError()
                    value=json.loads(raw)
                    if not isinstance(value,dict):raise ValueError()
                    self.events.put_nowait(value)
            except Exception:
                self.bad_protocol=True
            finally:
                try:self.events.put_nowait(None)
                except queue.Full:pass
        self.bad_protocol=False;self.reader=threading.Thread(target=read,name='codex-public-events',daemon=True);self.reader.start()
    def send(self,method,params=None,notify=False):
        self.sequence+=1;value=dict(method=method,params=params or {})
        if not notify:value['id']=self.sequence
        try:self.process.stdin.write((json.dumps(value,ensure_ascii=False)+'\n').encode());self.process.stdin.flush()
        except (OSError,ValueError):raise ProviderError('Codex 客户端连接已中断') from None
        return self.sequence
    def receive(self):
        while True:
            if self.cancel.is_set():raise Cancelled('已停止')
            if time.time()>=self.deadline:raise ProviderError('Codex 操作超时，已停止')
            if self.bad_protocol:raise ProviderError('Codex 响应过大或协议无效，已停止')
            try:value=self.events.get(timeout=.05)
            except queue.Empty:
                if self.process.poll() is not None:raise ProviderError('Codex 客户端已退出，请检查安装、登录或版本')
                continue
            if value is None:raise ProviderError('Codex 客户端已退出，请检查安装、登录或版本')
            if 'method' in value and 'id' in value:
                # Never approve commands, file edits, tokens, permissions or dynamic tools.
                try:
                    self.process.stdin.write((json.dumps(dict(id=value['id'],error=dict(code=-32601,message='Text-only client: request denied')))+'\n').encode());self.process.stdin.flush()
                except (OSError,ValueError):pass
                raise ProviderError('Codex 请求了当前文字协作不支持的工具或授权，已停止')
            return value
    def request(self,method,params=None):
        identifier=self.send(method,params)
        while True:
            value=self.receive()
            if value.get('id')!=identifier:continue
            if 'error' in value:raise ProviderError('Codex 拒绝了 '+method+'，请检查登录状态、模型权限或客户端版本')
            result=value.get('result')
            if not isinstance(result,dict):raise ProviderError('Codex 返回了无效协议结果')
            return result
    def close(self):
        if self.closed.is_set():return
        self.closed.set()
        try:
            if self.process.poll() is None:self.process.terminate()
            self.process.wait(timeout=1)
        except (OSError,subprocess.TimeoutExpired):
            try:self.process.kill();self.process.wait(timeout=1)
            except (OSError,subprocess.TimeoutExpired):pass
        for stream in (self.process.stdin,self.process.stdout):
            try:stream.close()
            except (OSError,ValueError):pass
        self.reader.join(timeout=1)

class CodexChannel:
    def __init__(self,finder=None,command_factory=command,host_file=None):
        self.host_file=Path(host_file) if host_file else None
        self.finder=finder or (lambda:find_codex(self.settings()['executable']));self.command_factory=command_factory;self.lock=threading.Lock();self.rpc=None
    def settings(self):
        if not self.host_file or not self.host_file.exists():return {'executable':''}
        try:
            if self.host_file.stat().st_size>16384:raise ValueError()
            value=json.loads(self.host_file.read_text(encoding='utf-8'))['executable']
            if not isinstance(value,str):raise ValueError()
            return {'executable':value}
        except (ValueError,KeyError,OSError,TypeError):raise ProviderError('本机客户端路径配置损坏，请重新设置或检查 host.json') from None
    def set_executable(self,path):
        if not self.host_file:raise ValueError('当前客户端未启用本机路径设置')
        if not isinstance(path,str) or len(path)>4096:raise ValueError('本机 Codex 路径无效')
        if path:
            target=Path(path)
            if any(ord(c)<32 for c in path) or not target.is_absolute() or not target.is_file() or target.name.lower() not in ('codex.exe','codex'):raise ValueError('请选择已存在的原生 codex.exe 或 codex 文件，不要填写命令参数或脚本')
            path=str(target.resolve())
        atomic_json(self.host_file,{'executable':path});return self.settings()
    def interrupt(self):
        with self.lock:rpc=self.rpc
        if rpc:rpc.close()
    def _open(self,folder,cancel,deadline):
        executable=self.finder()
        if not executable:raise ProviderError('未找到本机 Codex，请安装原生客户端并加入 PATH 后重新检测')
        try:rpc=Rpc(self.command_factory(executable),folder,cancel,deadline)
        except OSError:raise ProviderError('无法启动本机 Codex，请检查安装或权限') from None
        with self.lock:self.rpc=rpc
        rpc.request('initialize',dict(clientInfo=dict(name='personal_agent_workbench',title='Agent 工作台',version='0.3.0'),capabilities=dict(experimentalApi=True)))
        rpc.send('initialized',notify=True)
        return rpc,executable
    def _close(self):
        with self.lock:rpc=self.rpc;self.rpc=None
        if rpc:rpc.close()
    @contextmanager
    def _session(self,cancel,deadline):
        with tempfile.TemporaryDirectory(prefix='agent-codex-') as folder:
            try:
                rpc,executable=self._open(folder,cancel,deadline)
                yield rpc,executable,folder
            finally:self._close()
    def discover(self):
        try:
            if not self.finder():return dict(state='not_installed',installed=False,logged_in=False,models=[],generation_verified=False,message='未找到本机 Codex。可手动指定原生客户端路径，或安装并登录后重新检测；API 配置仍可使用。')
            with self._session(threading.Event(),time.time()+20) as (rpc,executable,folder):
                account=rpc.request('account/read',{'refreshToken':False}).get('account')
                if not isinstance(account,dict):return dict(state='login_required',installed=True,logged_in=False,models=[],generation_verified=False,message='已安装 Codex，请先在 Codex 中登录，再重新检测。')
                rows=[];cursor=None;seen=set()
                for _ in range(10):
                    result=rpc.request('model/list',dict(limit=100,includeHidden=False,**({'cursor':cursor} if cursor else {})))
                    for row in result.get('data',[]):
                        if not isinstance(row,dict):continue
                        identifier=row.get('model') or row.get('id')
                        if isinstance(identifier,str) and 0<len(identifier)<=200 and identifier not in seen:
                            rows.append(dict(id=identifier,name=str(row.get('displayName') or identifier)[:200]));seen.add(identifier)
                    cursor=result.get('nextCursor')
                    if not cursor:break
                return dict(state='catalog',installed=True,logged_in=True,auth_type=str(account.get('type','unknown'))[:40],models=rows,generation_verified=False,message='已读取本机 Codex 模型目录；实际调用权限需要完成一次生成才能确认。')
        except (ProviderError,OSError) as exc:return dict(state='unavailable',installed=True,logged_in=False,models=[],generation_verified=False,message=str(exc) if isinstance(exc,ProviderError) else '本机 Codex 检测失败，请检查安装与权限')
        finally:self._close()
    def models(self,profile,key):
        result=self.discover()
        if result['state']!='catalog':raise ProviderError(result['message'])
        return [m['id'] for m in result['models']]
    def complete(self,profile,key,messages,max_tokens,cancel,on_chunk,deadline):
        try:
            with self._session(cancel,deadline) as (rpc,executable,folder):
                if not rpc.request('account/read',{'refreshToken':False}).get('account'):raise ProviderError('本机 Codex 尚未登录，请先在 Codex 中登录')
                configuration=rpc.request('config/read',{'includeLayers':False}).get('config',{})
                config={**CONFIG,'mcp_servers':{name:{'enabled':False} for name in configuration.get('mcp_servers',{})}}
                result=rpc.request('thread/start',dict(model=profile['model'],ephemeral=True,cwd=folder,sandbox='read-only',approvalPolicy='untrusted',approvalsReviewer='user',environments=[],dynamicTools=[],config=config,baseInstructions='只进行文字协作，不运行工具、读取文件、搜索网页或委派代理。',developerInstructions='\n'.join(m['content'] for m in messages if m['role']=='system'),allowProviderModelFallback=False))
                if result.get('model')!=profile['model']:raise ProviderError('Codex 返回模型身份与所选配置不同，已停止')
                if result.get('sandbox',{}).get('type')!='readOnly':raise ProviderError('Codex 未确认只读隔离策略，已停止')
                thread=result['thread']['id'];text='\n\n'.join(('你此前的公开回复：\n' if m['role']=='assistant' else '用户或带来源的上下文消息：\n')+m['content'] for m in messages if m['role']!='system')
                result=rpc.request('turn/start',dict(threadId=thread,input=[dict(type='text',text=text,text_elements=[])],effort='low'))
                turn=result['turn']['id'];content='';items={}
                allowed={'item/started','item/completed','item/agentMessage/delta','item/reasoning/summaryTextDelta','item/reasoning/summaryPartAdded','item/reasoning/textDelta','turn/completed','turn/started','thread/started','thread/status/changed','thread/readState/changed','thread/tokenUsage/updated','thread/compacted','thread/settings/updated','thread/name/updated','account/updated','account/rateLimits/updated','model/verification','model/safetyBuffering/updated','turn/moderationMetadata','warning','configWarning','deprecationNotice','windows/worldWritableWarning','windowsSandbox/setupCompleted','modelProvider/authRecoveryStarted','modelProvider/authRecoveryCompleted','error'}
                while True:
                    event=rpc.receive();method=event.get('method','');params=event.get('params',{})
                    if method not in allowed:
                        self.last_method=method
                        raise ProviderError('Codex 返回未知或不受支持的协议事件，已停止')
                    if params.get('threadId') not in (None,thread):continue
                    if params.get('turnId') not in (None,turn):continue
                    if method in ('item/started','item/completed'):
                        item=params.get('item',{});kind=item.get('type')
                        if params.get('threadId')!=thread or params.get('turnId')!=turn or not isinstance(item.get('id'),str) or not item['id']:raise ProviderError('Codex 消息缺少当前会话来源，已停止')
                        if kind not in ('agentMessage','reasoning','userMessage','contextCompaction'):
                            self.last_item_type=kind
                            raise ProviderError('Codex 产生了当前文字通道不支持的事件，已停止')
                        if kind=='agentMessage':items[item.get('id')]=True
                    if method=='item/agentMessage/delta':
                        if params.get('threadId')!=thread or params.get('turnId')!=turn or params.get('itemId') not in items:raise ProviderError('Codex 公开回复缺少当前会话来源，已停止')
                        delta=params.get('delta','')
                        if not isinstance(delta,str) or len(content)+len(delta)>20000:raise ProviderError('公开回复超过 20000 字符，已停止')
                        content+=delta;on_chunk(delta)
                    if method=='turn/completed' and params.get('turn',{}).get('id')==turn:
                        if params['turn'].get('status')!='completed' or not content.strip():raise ProviderError('Codex 未返回完整公开回复，已停止交接')
                        return dict(content=content,model=profile['model'],usage=None,finish_reason='stop')
                    if method=='error':raise ProviderError('Codex 调用出错，未继续交接；请检查模型权限、额度或网络')
        finally:self._close()
