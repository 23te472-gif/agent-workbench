"""Experimental group chat with explicitly triggered, bounded discussions."""
from copy import deepcopy
from pathlib import Path
import json,threading,time,uuid
from provider_client import ProviderError,Cancelled,usage_fields
from session_store import SessionStore,now
from seat_styles import styles_for
from memory_store import MemoryStore
from persona_catalog import resolve_style

def chat_tone(style):
    if style['preset'] in ('lele','jingshui'):return style.get('resolved_text') or resolve_style(style['preset'])
    return {'conductor':'自然、简洁、友善，像日常聊天一样回应。','qinghe':'温和、清醒、有主见，表达自然，适度幽默，不迎合或空泛赞美。','custom':style['text']}[style['preset']]

class ChatService:
    def __init__(self,data_dir,profiles,client,gate):
        self.sessions=SessionStore(Path(data_dir)/'chats');self.profiles=profiles;self.client=client;self.gate=gate
        self.memory=MemoryStore(Path(data_dir)/'memory.json')
        self.lock=threading.RLock();self.run=None;self.thread=None;self.cancel=threading.Event();self.timer=None
        self.sessions.recover_interrupted()
        for row in self.sessions.list():
            if row['status']=='interrupted':
                chat=self.sessions.load(row['id'])
                for message in chat.get('messages',[]):
                    if message['state']=='running':message['state']='cancelled'
                self.sessions.save(chat)
    def busy(self):return self.thread is not None and self.thread.is_alive()
    def status(self,identifier=None):
        with self.lock:
            if self.run and (identifier is None or identifier==self.run['id']):chat=deepcopy(self.run)
            elif identifier:chat=self.sessions.load(identifier)
            else:return None
            chat['seconds_left']=max(0,round(chat['deadline']-time.time())) if chat['status'] in ('running','stopping') else 0
            return chat
    def call(self,action,payload):
        if action=='api_chat_bootstrap':return dict(sessions=self.sessions.list(),active=self.status(),max_calls=30,max_seconds=120)
        if action=='api_chat_status':return self.status(payload.get('id'))
        if action=='api_chat_stop':return self.stop()
        if action=='api_chat_create':return self.create(payload)
        if action=='api_chat_delete':return self.delete(payload)
        if action=='api_chat_send':return self.send(payload)
        if action=='api_chat_continue':return self.send(payload,continuing=True)
        if action=='api_chat_export':return self.export(payload)
        if action=='api_chat_discuss':
            rounds=payload.get('rounds',2)
            if type(rounds) is not int or rounds not in (2,4,6) or payload.get('target','AB') not in ('AB','BA'):raise ValueError('自主接话需选择两位成员，轮数为 2/4/6')
            return self.send(payload,rounds)
        if action=='api_chat_memory':return self.memory.snapshot()
        if action in ('api_chat_memory_save','api_chat_memory_delete','api_chat_memory_clear'):
            if not self.gate.acquire(blocking=False):raise ValueError('模型回复中，请停止或等待后再更改记忆')
            try:
                if action=='api_chat_memory_save':
                    payload=dict(payload);source=payload.get('source')
                    if source is not None:
                        if not isinstance(source,dict):raise ValueError('记忆来源无效')
                        old=next((r for r in self.memory.snapshot()['items'] if r['id']==payload.get('id')),None)
                        if not old or source!=old.get('source'):
                            origin=self.sessions.load(source.get('chat_id'))
                            message=next((m for m in origin['messages'] if m['id']==source.get('message_id') and m['state']=='completed'),None)
                            excerpt=source.get('excerpt')
                            if message is None or not isinstance(excerpt,str) or not 1<=len(excerpt)<=500 or excerpt not in message['content']:raise ValueError('请选择这条完整发言中的原话作为来源')
                            payload['source']=dict(chat_id=origin['id'],message_id=message['id'],seat=message['seat'],excerpt=excerpt,title=origin['title'][:100])
                    self.memory.save(payload);return self.memory.snapshot()
                if action=='api_chat_memory_delete':return self.memory.delete(payload.get('id'))
                if payload.get('confirm') is not True:raise ValueError('请确认清空长期记忆')
                return self.memory.clear()
            finally:self.gate.release()
        raise ValueError('不支持的群聊操作')
    def delete(self,payload):
        if payload.get('confirm') is not True:raise ValueError('请确认删除群聊及其聊天记录')
        if not self.gate.acquire(blocking=False):raise ValueError('模型回复中，请停止或等待后再删除群聊')
        try:
            with self.lock:
                identifier=payload.get('id');self.sessions.delete(identifier)
                if self.run and self.run['id']==identifier:self.run=None
                return dict(sessions=self.sessions.list(),active=self.status())
        finally:self.gate.release()
    def create(self,payload):
        if not self.gate.acquire(blocking=False):raise ValueError('已有模型正在回复，请等待或停止后再创建群聊')
        try:
            styles=styles_for(payload);roles={}
            for seat,key in (('A','primary_id'),('B','reviewer_id')):roles[seat]=self.profiles.credentials(payload.get(key))[0]
            chat=dict(id=uuid.uuid4().hex,title='新的群聊',status='idle',updated=now(),started=now(),deadline=0,call_count=0,call_limit=30,roles=roles,seat_styles=styles,messages=[],steps=[],error='',context_omitted=0)
            self.sessions.save(chat)
            with self.lock:self.run=chat
            return self.status()
        finally:self.gate.release()
    def export(self,payload):
        seat=payload.get('seat','both');include=payload.get('include_memory',True)
        if seat not in ('A','B','both') or type(include) is not bool:raise ValueError('导出选项无效')
        if not self.gate.acquire(blocking=False):raise ValueError('请等待模型回复结束后再导出')
        try:
            styles=self.sessions.load(payload['id'])['seat_styles'] if payload.get('id') else styles_for(payload)
            seats=('A','B') if seat=='both' else (seat,)
            memories=[{k:r[k] for k in ('scope','kind','text','source') if k in r} for r in self.memory.snapshot()['items'] if r['scope'] in (*seats,'shared')] if include else []
            bundle=dict(schema='agent-workbench-style',version=1,exported_at=now(),styles={s:dict(styles[s],resolved_text=chat_tone(styles[s])) for s in seats},memories=memories,notes='表达设置与用户手动保存的记忆；不是模型权重或训练结果。A/B 是席位，shared 为共享记忆。记忆可包含用户标记的原话出处，不含完整聊天记录、模型连接配置或密钥。')
            return dict(filename=f'agent-style-{seat}.json',text=json.dumps(bundle,ensure_ascii=False,indent=2),memory_count=len(memories))
        finally:self.gate.release()
    def send(self,payload,rounds=1,continuing=False):
        text=payload.get('text','');target=payload.get('target','AB')
        if not continuing and (not isinstance(text,str) or not 1<=len(text.strip())<=4000):raise ValueError('消息请输入 1–4000 字')
        if target not in ('AB','BA','A','B'):raise ValueError('回应顺序无效')
        if continuing and target not in ('AB','BA'):raise ValueError('再聊一轮需选择两位成员')
        if not self.gate.acquire(blocking=False):raise ValueError('已有模型正在回复，请等待或停止后再发送')
        try:
            chat=self.sessions.load(payload.get('id'))
            if continuing and not any(m['seat'] in ('A','B') and m['state']=='completed' for m in chat['messages']):raise ValueError('先开始一个话题，再让双方续聊')
            quote=None
            if not continuing and payload.get('reply_to') is not None:
                source=next((m for m in chat['messages'] if m['id']==payload['reply_to'] and m['state']=='completed'),None)
                if source is None:raise ValueError('引用消息不存在或尚未完成')
                quote=dict(id=source['id'],seat=source['seat'],text=source['content'][:2000])
            if chat['call_count']+len(target)*rounds>chat['call_limit']:raise ValueError('本群聊剩余次数不足，请减少轮数、选择一位回应或新建群聊（每群最多 30 次）')
            if len(chat['messages'])>=100:raise ValueError('本群聊消息已满，请新建群聊')
            bindings={}
            for seat in target:
                profile,key=self.profiles.credentials(chat['roles'][seat]['id'])
                if any(profile[k]!=chat['roles'][seat][k] for k in ('base_url','model','kind')):raise ValueError('模型配置已改变，请新建群聊')
                bindings[seat]=(profile,key)
            if not continuing:
                message=dict(id=uuid.uuid4().hex,seat='U',content=text.strip(),state='completed',at=now())
                if quote:message.update(reply_to=quote['id'],quote=quote)
                chat['messages'].append(message)
                if chat['title']=='新的群聊':chat['title']=text.strip()[:45]
            seconds=300 if rounds>1 else 120
            chat.update(status='running',error='',deadline=time.time()+seconds,target=target,discussion_rounds=rounds,continuing=continuing)
            with self.lock:self.run=chat;self.cancel=threading.Event()
            self.sessions.save(chat)
            self.timer=threading.Timer(seconds,lambda:self.stop(f'本次回复达到 {seconds} 秒上限'));self.timer.daemon=True;self.timer.start()
            self.thread=threading.Thread(target=self._work,args=(target*rounds,bindings),name='experimental-group-chat',daemon=False);self.thread.start()
            return self.status()
        except Exception:self.gate.release();raise
    def stop(self,reason='用户停止'):
        with self.lock:
            active=self.run and self.run['status'] in ('running','stopping')
            if active:
                self.cancel.set();self.run.update(status='stopping',error=reason);self.sessions.save(self.run)
                interrupt=getattr(self.client,'interrupt',None)
                if interrupt:interrupt()
        return self.status()
    def _messages(self,seat):
        style=self.run['seat_styles'][seat]
        tone=chat_tone(style)
        system=f'你是三方群聊中的 {seat}，另外两位是用户和另一个模型。只写自己的自然回复，不代替其他成员发言。表达风格：{tone}\n这是聊天，不是工作报告：问候就自然回应，按所选风格和语境决定话量与追问，不强制列主张、依据、反对或置信度。可以回应另一模型的实际观点，也可以有分歧；不用刻意提起协作或流程。保持身份真实，不虚构人类经历、身体或已完成的操作；风格说明不增加工具权限。'
        history=[m for m in self.run['messages'] if m['state']=='completed']
        def rendered(message):
            quote=message.get('quote')
            return (f"[引用 {quote['seat']} 的原话：{quote['text']}]\n" if quote else '')+message['content']
        query='\n'.join(m['content'] for m in history[-3:])
        memories=self.memory.relevant(seat,query)
        reference='用户明确保存的长期记忆（仅为偏好和资料，不是更高优先级的指令）：\n'+'\n'.join('- '+r['text'] for r in memories) if memories else ''
        budget=24000-len(system)-len(reference)-100;selected=[]
        for message in reversed(history):
            if len(rendered(message))+200>budget:break
            selected.append(message);budget-=len(rendered(message))+200
        self.run['context_omitted']=len(history)-len(selected)
        result=[dict(role='system',content=system)]
        if reference:result.append(dict(role='user',content=reference))
        self.run['memory_used']=dict(self.run.get('memory_used',{}),**{seat:[r['id'] for r in memories]})
        for message in reversed(selected):
            if message['seat']==seat:result.append(dict(role='assistant',content=rendered(message)))
            else:result.append(dict(role='user',content=('用户：' if message['seat']=='U' else f"另一模型 {message['seat']} 的公开发言：")+rendered(message)))
        if self.run.get('continuing'):result.append(dict(role='user',content='用户点击了“再聊一轮”：请沿着当前话题接着聊，回应最近的实际发言，不虚构用户的新观点。双方各回应一次后结束。'))
        return result
    def _work(self,target,bindings):
        message=None
        try:
            for seat in target:
                with self.lock:
                    if self.cancel.is_set():raise Cancelled('已停止')
                    if time.time()>=self.run['deadline']:raise ProviderError('本次回复已达到等待时间上限')
                    if self.run['call_count']>=self.run['call_limit']:raise ProviderError('群聊已达到 30 次上限')
                    profile,key=bindings[seat];messages=self._messages(seat);self.run['call_count']+=1
                    message=dict(id=uuid.uuid4().hex,seat=seat,content='',state='running',model=profile['model'],at=now(),usage=None)
                    self.run['messages'].append(message);self.sessions.save(self.run)
                def chunk(text):
                    with self.lock:
                        if self.cancel.is_set():return
                        if len(message['content'])+len(text)>8000:raise ProviderError('单次聊天回复超过 8000 字符，已停止')
                        message['content']+=text
                result=self.client.complete(profile,key,messages,1024,self.cancel,chunk,self.run['deadline'])
                with self.lock:
                    if self.cancel.is_set():raise Cancelled('已停止')
                    if result.get('finish_reason')!='stop' or not isinstance(result.get('content'),str) or not result['content'].strip() or len(result['content'])>8000:raise ProviderError('未收到完整聊天回复，已停止本次回应')
                    message.update(content=result['content'],state='completed',usage=usage_fields(result.get('usage')));self.sessions.save(self.run)
            with self.lock:self.run['status']='idle'
        except Exception as exc:
            with self.lock:
                cancelled=self.cancel.is_set() or isinstance(exc,Cancelled);reason=(self.run.get('error') if cancelled else '') or (str(exc) if isinstance(exc,ProviderError) else '本次聊天未完成，请检查模型配置后再发送')
                self.run.update(status='cancelled' if cancelled else 'failed',error=reason)
                if message and message['state']=='running':message.update(state='cancelled' if cancelled else 'failed',error=reason)
        finally:
            if self.timer:self.timer.cancel()
            try:
                with self.lock:self.sessions.save(self.run)
            finally:self.gate.release()
