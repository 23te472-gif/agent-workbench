"""Registered bridge for bounded model collaboration, group chat and explicit memory."""
from pathlib import Path
import json,threading
DEFAULT_ROOM=None

class Bridge:
    def __init__(self,root=DEFAULT_ROOM,executor=None,opener=None,data_dir=None,api_client=None):
        self.store=None
        self._command_lock=threading.Lock();self._state_lock=threading.Lock();self._job=None
        self._data_dir=Path(data_dir) if data_dir is not None else Path(__file__).parent/'data'
        self._api_client=api_client;self._auto=None;self._auto_init=threading.Lock();self.export_saver=None
        from appearance_store import AppearanceStore
        self.appearance=AppearanceStore(self._data_dir/'appearance.json')
    def busy(self):return self._command_lock.locked()
    def call(self,action,payload=None):
        try:
            room_actions=()
            api_actions=('api_bootstrap','api_status','api_session','api_start','api_retry','api_stop','api_note','api_profile_save','api_profile_delete_key','api_profile_delete','api_profile_test','api_discover_local','api_local_path')
            api_actions+=('api_chat_bootstrap','api_chat_create','api_chat_delete','api_chat_send','api_chat_status','api_chat_stop','api_chat_discuss','api_chat_memory','api_chat_memory_save','api_chat_memory_delete','api_chat_memory_clear')
            api_actions+=('api_chat_continue','api_chat_export','api_chat_export_save')
            api_actions+=('api_appearance_get','api_appearance_save')
            if not isinstance(action,str) or action not in room_actions+api_actions:raise ValueError('不支持的操作')
            if payload is None:payload={}
            if not isinstance(payload,dict) or len(json.dumps(payload,ensure_ascii=False))>32768:raise ValueError('参数无效或过大')
            if action=='api_appearance_get':return dict(ok=True,data=self.appearance.get())
            if action=='api_appearance_save':return dict(ok=True,data=self.appearance.save(payload.get('theme')))
            if action in api_actions:
                with self._auto_init:
                    if self._auto is None:
                        from auto_service import AutoService
                        self._auto=AutoService(self._data_dir,self.store,self._command_lock,self._api_client)
                if action=='api_chat_export_save':
                    if self.export_saver is None:raise ValueError('保存窗口尚未就绪')
                    export=self._auto.chat.export(payload)
                    return dict(ok=True,data=dict(saved=bool(self.export_saver(export['filename'],export['text']))))
                return dict(ok=True,data=self._auto.call(action,payload))
            return dict(ok=True,data=getattr(self,'_'+action)(payload))
        except (ValueError,OSError,TypeError,KeyError,UnicodeError) as exc:return dict(ok=False,error=str(exc) or '操作失败')
        except Exception:return dict(ok=False,error='操作未完成，请刷新后重试')
    def _api_active(self):return self._auto is not None and (self._auto.engine.busy() or self._auto.chat.busy())
    def _stop_api(self):
        if self._auto:
            if self._auto.engine.busy():self._auto.engine.stop('用户关闭窗口')
            if self._auto.chat.busy():self._auto.chat.stop('用户关闭窗口')
