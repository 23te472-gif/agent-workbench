"""API feature boundary, isolated from the shared manual collaboration room."""
from pathlib import Path
from credential_store import ProfileStore
from session_store import SessionStore
from orchestrator import Orchestrator,LIMITS
from provider_client import ProviderClient
from model_channels import ModelChannels

class AutoService:
    def __init__(self,data_dir,room,gate,client=None):
        self.profiles=ProfileStore(data_dir);self.sessions=SessionStore(Path(data_dir)/'sessions');self.room=room
        self.sessions.recover_interrupted();self.gate=gate
        if client:self.client=client
        else:
            from codex_channel import CodexChannel
            self.client=ModelChannels(local=CodexChannel(host_file=Path(data_dir)/'host.json'))
        self.engine=Orchestrator(self.sessions,self.profiles,self.client,self._persona,gate)
        from chat_service import ChatService
        self.chat=ChatService(data_dir,self.profiles,self.client,gate)
    def _persona(self,name):
        conductor='仅表达当前席位的公开意见：主张、依据或要点、反对意见、置信度。如实说明限制，不替其他席位发言。'
        if name=='conductor':return conductor
        text='温和、清醒、有主见，表达自然，幽默适度；先给明确判断，再说明依据与不确定性。不空泛赞美，不迎合，不编造事实或经历。'
        return conductor+'\n保持以上席位与真实来源格式，同时采用以下表达风格：\n'+text
    def call(self,action,payload):
        if action.startswith('api_chat_'):return self.chat.call(action,payload)
        if action=='api_bootstrap':return dict(profiles=self.profiles.list(),sessions=self.sessions.list(),active=self.engine.status(),limits=LIMITS,personas=['lele','jingshui'],room_available=False)
        if action=='api_status':return self.engine.status(payload.get('id'))
        if action=='api_session':return self.engine.status(payload['id'])
        if action=='api_stop':return self.engine.stop()
        if action=='api_note':return self.engine.note(payload.get('text'))
        if action=='api_discover_local':
            if not self.gate.acquire(blocking=False):raise ValueError('协作运行中，请结束后再检测本机客户端')
            try:
                from codex_channel import CodexChannel
                return getattr(self.client,'local',None).discover() if isinstance(self.client,ModelChannels) else CodexChannel().discover()
            finally:self.gate.release()
        if action=='api_local_path':
            if not self.gate.acquire(blocking=False):raise ValueError('协作运行中，请结束后再设置本机路径')
            try:
                local=getattr(self.client,'local',None)
                if local is None:raise ValueError('当前通道不支持本机路径设置')
                if 'executable' not in payload:return getattr(local,'settings',lambda:{'executable':''})()
                return local.set_executable(payload.get('executable',''))
            finally:self.gate.release()
        if action=='api_start':
            Orchestrator.validate(payload)
            return self.engine.start({**payload,'context_count':0},[])
        if action=='api_retry':return self.engine.retry(payload.get('id'))
        if action not in ('api_profile_save','api_profile_delete_key','api_profile_delete','api_profile_test'):raise ValueError('不支持的 API 操作')
        if not self.gate.acquire(blocking=False):raise ValueError('已有操作进行中，结束后再修改模型配置')
        try:
            if action=='api_profile_save':return self.profiles.save(payload)
            if action=='api_profile_delete_key':return self.profiles.delete_key(payload.get('id'))
            if action=='api_profile_delete':return self.profiles.delete(payload.get('id'))
            profile,key=self.profiles.credentials(payload.get('id'))
            models=self.client.models(profile,key)
            return dict(models=models,message='已读取模型列表；尚未进行生成验证')
        finally:self.gate.release()
