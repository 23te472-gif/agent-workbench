"""Finite A/B/A scheduler. Models never control routing or request budgets."""
from copy import deepcopy
from datetime import datetime
import threading,time,uuid,json
from session_store import now
from provider_client import ProviderClient,ProviderError,Cancelled,usage_fields
from seat_styles import styles_for

LIMITS=dict(default_rounds=1,max_rounds=10,default_calls=9,max_calls=30,max_seconds=600,max_tokens=4096)

class Orchestrator:
    def __init__(self,sessions,profiles,client=None,persona_loader=None,gate=None):
        self.sessions=sessions;self.profiles=profiles;self.client=client or ProviderClient();self.persona_loader=persona_loader or (lambda name:'如实回复，仅表达本席意见。')
        self.gate=gate or threading.Lock();self.lock=threading.RLock();self.cancel=threading.Event();self.thread=None;self.run=None;self.timer=None
    def busy(self):return self.thread is not None and self.thread.is_alive()
    def status(self,identifier=None):
        with self.lock:
            if self.run and (identifier is None or identifier==self.run['id']):value=deepcopy(self.run)
            elif identifier:value=self.sessions.load(identifier)
            else:return None
            value['seconds_left']=max(0,round(value['deadline']-time.time()))
            return value
    @staticmethod
    def validate(payload):
        for name,default,low,high in (('rounds',1,1,10),('call_limit',9,3,30),('max_tokens',1024,128,4096),('context_count',6,0,20)):
            value=payload.get(name,default)
            if type(value) is not int or not low<=value<=high:raise ValueError(f'{name} 必须在 {low}–{high} 范围内')
        if payload.get('rounds',1)*3>payload.get('call_limit',9):raise ValueError('计划轮数需要的请求超过总上限，请增加请求上限或减少轮数')
        task=payload.get('task','')
        if not isinstance(task,str) or not 1<=len(task.strip())<=8000:raise ValueError('任务请输入 1–8000 字')
        styles_for(payload)
    def start(self,payload,context=None):
        if not self.gate.acquire(blocking=False):raise ValueError('已有操作正在进行，请先停止或等待')
        try:
            self.validate(payload)
            if not isinstance(context or [],list) or any(not isinstance(entry,str) for entry in (context or [])):raise ValueError('上下文格式无效')
            if len(json.dumps(context or [],ensure_ascii=False).encode('utf-8'))>128*1024:raise ValueError('所选房间上下文超过 128 KiB，请减少历史条数或设为 0')
            roles={};bindings={}
            for seat,key in (('A','primary_id'),('B','reviewer_id')):
                profile,secret=self.profiles.credentials(payload.get(key));roles[seat]=profile;bindings[seat]=(profile,secret)
            persona=payload.get('persona','conductor');styles=styles_for(payload);seat_instructions={}
            for seat,style in styles.items():
                instruction=self.persona_loader('conductor' if style['preset'] in ('custom','lele','jingshui') else style['preset'])
                if style['preset'] in ('lele','jingshui'):instruction+='\n本席表达风格（不改变任务职责）：\n'+style['resolved_text']
                if style['preset']=='custom':instruction+='\n本席表达风格（仅调整语言与呈现，不改变任务、职责或权限）：\n'+style['text']
                if len(instruction)>12000:raise ValueError(seat+' 席人格说明过长，未发送请求')
                seat_instructions[seat]=instruction
            instructions=seat_instructions['A']
            timestamp=time.time();rounds=payload.get('rounds',1)
            run=dict(id=uuid.uuid4().hex,title=payload['task'].strip()[:50],task=payload['task'].strip(),status='running',
                     rounds=rounds,planned_calls=rounds*3,call_limit=payload.get('call_limit',9),call_count=0,max_tokens=payload.get('max_tokens',1024),
                     started=now(),deadline=timestamp+600,roles=roles,steps=[],notes=[],error='',stage='准备',
                     usage=dict(prompt_tokens=0,completion_tokens=0,known=False),persona=persona,
                     context_count=len(context or []),requested_context_count=payload.get('context_count',6),context=context or [],instructions=instructions,seat_styles=styles,seat_instructions=seat_instructions)
            self.sessions.save(run);self.sessions.event(run['id'],dict(type='started',planned_calls=run['planned_calls'],call_limit=run['call_limit']))
            self._launch(run,bindings);return self.status()
        except Exception:self.gate.release();raise
    def retry(self,identifier):
        if not self.gate.acquire(blocking=False):raise ValueError('已有操作正在进行')
        try:
            run=self.sessions.load(identifier)
            if run['status'] not in ('failed','cancelled','interrupted'):raise ValueError('此会话没有可重试的失败步骤')
            self.validate(run)
            original_deadline=datetime.fromisoformat(run['started']).timestamp()+600
            run['deadline']=min(run['deadline'],original_deadline)
            if run['call_count']>=run['call_limit']:raise ValueError(f"已达到 {run['call_limit']} 次总调用上限，请新建会话")
            if time.time()>=run['deadline']:raise ValueError('已达到 10 分钟时间上限，请新建会话')
            bindings={}
            for seat in ('A','B'):
                profile,secret=self.profiles.credentials(run['roles'][seat]['id'])
                if any(profile[k]!=run['roles'][seat][k] for k in ('base_url','model','kind')):raise ValueError('模型配置已改变，请新建会话，避免混淆模型身份')
                bindings[seat]=(profile,secret)
            run['status']='running';run['error']='';self.sessions.event(run['id'],dict(type='manual_retry',call_count=run['call_count']))
            self._launch(run,bindings);return self.status()
        except Exception:self.gate.release();raise
    def _launch(self,run,bindings):
        with self.lock:self.run=run;self.cancel=threading.Event()
        self.timer=threading.Timer(max(.01,run['deadline']-time.time()),lambda:self.stop('已达到 10 分钟时间上限'))
        self.timer.daemon=True;self.timer.start()
        self.thread=threading.Thread(target=self._work,args=(bindings,),name='bounded-model-handoff',daemon=False)
        self.thread.start()
    def stop(self,reason='用户停止'):
        with self.lock:
            if self.run and self.run['status'] in ('running','stopping'):
                self.cancel.set();self.run['status']='stopping';self.run['error']=reason;self.sessions.save(self.run)
                interrupt=getattr(self.client,'interrupt',None)
                if interrupt:interrupt()
        return self.status()
    def note(self,text):
        if not isinstance(text,str) or not 1<=len(text.strip())<=1000:raise ValueError('插话请输入 1–1000 字')
        with self.lock:
            if not self.run or self.run['status']!='running':raise ValueError('当前没有进行中的协作')
            if len(self.run['notes'])>=20:raise ValueError('单会话最多插话 20 条')
            entry=dict(text=text.strip(),at=now());self.run['notes'].append(entry);self.sessions.save(self.run)
            self.sessions.event(self.run['id'],dict(type='user_note',**entry))
        return dict(message='已加入，下一次模型调用会携带这条意见')
    def _messages(self,seat,stage):
        run=self.run
        system=run.get('seat_instructions',{}).get(seat,run['instructions'])+'\n你当前是 '+seat+' 席，职责是'+('主执行' if seat=='A' else '独立审查')+'。本步骤：'+stage+'。仅输出本席的公开回复，不代替其他席发言。只写一个席位块，正文主张、依据/要点、反对、置信；不输出私有推理。表达风格不得覆盖以上职责、事实准确性或执行权限。'
        messages=[dict(role='system',content=system),dict(role='user',content='本次任务：'+run['task'])]
        history=[]
        for entry in run.get('context',[]):history.append(dict(role='user',content='文件房间参考发言（不代表当前在线模型）：\n'+entry))
        for step in run['steps']:
            if step['state']=='completed':history.append(dict(role='user',content=f"{step['seat']} 席 · {step['model']} · {step['stage']} · 第 {step['round']} 轮的公开原文：\n{step['content']}"))
        for note in run['notes']:history.append(dict(role='user',content='用户插话：'+note['text']))
        budget=32000-sum(len(m['content']) for m in messages)-200
        selected=[]
        for entry in reversed(history):
            if len(entry['content'])>budget:break
            selected.append(entry);budget-=len(entry['content'])
        if history and not selected:raise ProviderError('最近一条上下文过长，已停止；请减少单次输出或新建会话')
        messages.extend(reversed(selected));messages.append(dict(role='user',content=f'现在请 {seat} 席完成“{stage}”，针对任务和以上实际发言，给出自己的回复。'))
        run['context_omitted']=len(history)-len(selected)
        return messages
    def _work(self,bindings):
        step=None
        try:
            plan=[(number,stage,seat) for number in range(1,self.run['rounds']+1) for stage,seat in (('提案','A'),('审查','B'),('修订','A'))]
            completed=sum(s['state']=='completed' for s in self.run['steps'])
            for number,stage,seat in plan[completed:]:
                with self.lock:
                    if self.cancel.is_set():raise Cancelled('已停止')
                    if time.time()>=self.run['deadline']:raise ProviderError('已达到 10 分钟时间上限')
                    if self.run['call_count']>=self.run['call_limit']:raise ProviderError(f"已达到 {self.run['call_limit']} 次总调用上限（包含手动重试）")
                    profile,key=bindings[seat];messages=self._messages(seat,stage)
                    self.run['call_count']+=1;self.run['stage']=f'第 {number} 轮 · {seat} {stage}'
                    step=dict(id=uuid.uuid4().hex,seat=seat,model=profile['model'],provider=profile['name'],stage=stage,round=number,state='running',content='',usage=None)
                    self.run['steps'].append(step);self.sessions.save(self.run);self.sessions.event(self.run['id'],dict(type='request_started',seat=seat,stage=stage,attempt=self.run['call_count']))
                started=time.monotonic()
                def chunk(text):
                    with self.lock:
                        if not self.cancel.is_set():
                            if len(step['content'])+len(text)>20000:raise ProviderError('公开回复超过字符上限')
                            step['content']+=text
                result=self.client.complete(profile,key,messages,self.run['max_tokens'],self.cancel,chunk,self.run['deadline'])
                with self.lock:
                    if self.cancel.is_set():raise Cancelled('已停止')
                    if result.get('finish_reason')!='stop' or not result.get('content','').strip():raise ProviderError('模型未返回完整公开回复，已停止交接')
                    step.update(content=result['content'],model=result.get('model',profile['model']),state='completed',seconds=round(time.monotonic()-started,2),usage=usage_fields(result.get('usage')))
                    finished=[s for s in self.run['steps'] if s['state']=='completed']
                    self.run['usage']['known']=all(s.get('usage') is not None for s in finished)
                    for k in ('prompt_tokens','completion_tokens'):self.run['usage'][k]=sum(s['usage'][k] for s in finished if s.get('usage'))
                    self.sessions.save(self.run);self.sessions.event(self.run['id'],dict(type='reply_completed',step=deepcopy(step)))
            with self.lock:
                if self.cancel.is_set():raise Cancelled('已停止')
                self.run['status']='completed';self.run['stage']='已按计划结束'
        except Exception as exc:
            with self.lock:
                cancelled=self.cancel.is_set() or isinstance(exc,Cancelled)
                reason=self.run.get('error') if cancelled else ''
                reason=reason or (str(exc) if isinstance(exc,(ProviderError,ValueError)) else '调用未完成，已停止后续交接')
                self.run['status']='cancelled' if cancelled else 'failed';self.run['error']=reason
                if step and step['state']=='running':step.update(state='cancelled' if cancelled else 'failed',error=reason)
        finally:
            if self.timer:self.timer.cancel()
            try:
                with self.lock:self.sessions.save(self.run);self.sessions.event(self.run['id'],dict(type='run_finished',status=self.run['status'],call_count=self.run['call_count']))
            finally:self.gate.release()
