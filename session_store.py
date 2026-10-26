"""Bounded local session snapshots and append-only public events."""
from pathlib import Path
from datetime import datetime,timezone
import json,re,threading
from credential_store import atomic_json

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')

class SessionStore:
    def __init__(self,base):self.base=Path(base).resolve();self.lock=threading.RLock()
    def _directory(self,identifier):
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{32}',identifier):raise ValueError('会话 ID 无效')
        path=(self.base/identifier).resolve()
        if path.parent!=self.base:raise ValueError('会话路径越界')
        return path
    def save(self,session):
        with self.lock:
            session['updated']=now();directory=self._directory(session['id'])
            if len(json.dumps(session,ensure_ascii=False,indent=2).encode('utf-8'))>8*1024*1024:raise ValueError('会话文件超过保存上限')
            atomic_json(directory/'session.json',session)
    def event(self,identifier,event):
        with self.lock:
            directory=self._directory(identifier)
            path=directory/'events.jsonl'
            if path.is_symlink() or path.resolve().parent!=directory:raise ValueError('事件记录路径无效')
            with path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(at=now(),**event),ensure_ascii=False)+'\n')
    def delete(self,identifier):
        with self.lock:
            directory=self._directory(identifier)
            if not directory.is_dir():raise ValueError('群聊不存在或已删除')
            files=list(directory.iterdir())
            if any(p.name not in ('session.json','events.jsonl') or p.is_symlink() or not p.is_file() or p.resolve().parent!=directory for p in files):
                raise ValueError('群聊目录含额外文件，未删除，请先检查')
            for path in files:path.unlink()
            directory.rmdir()
    def load(self,identifier):
        with self.lock:
            path=self._directory(identifier)/'session.json'
            if path.resolve().parent!=self._directory(identifier) or path.stat().st_size>8*1024*1024:raise ValueError('会话文件过大或路径异常')
            try:
                value=json.loads(path.read_text(encoding='utf-8'))
                if value.get('id')!=identifier or not isinstance(value.get('steps'),list):raise ValueError()
                return value
            except (ValueError,TypeError,AttributeError):raise ValueError('会话记录损坏，原文件保持不变') from None
    def list(self):
        with self.lock:
            if not self.base.exists():return []
            rows=[]
            for directory in self.base.iterdir():
                if not re.fullmatch('[a-f0-9]{32}',directory.name) or not directory.is_dir():continue
                try:
                    session=self.load(directory.name)
                    row={k:session[k] for k in ('id','title','status','updated','call_count','call_limit')}
                    if not all(isinstance(row[k],str) for k in ('title','status','updated')):raise ValueError()
                except (OSError,ValueError,KeyError,TypeError):
                    row=dict(id=directory.name,title='记录未完成或损坏（原文件已保留）',status='corrupt',updated='',call_count=0,call_limit=9)
                rows.append(row)
            return sorted(rows,key=lambda row:row['updated'],reverse=True)[:100]
    def recover_interrupted(self):
        with self.lock:
            for summary in self.list():
                if summary['status'] not in ('running','stopping'):continue
                session=self.load(summary['id']);session['status']='interrupted';session['error']='上次运行已中断，未自动重发请求'
                for step in session['steps']:
                    if step['state']=='running':step['state']='cancelled';step['error']='上次运行中断'
                self.save(session);self.event(session['id'],dict(type='interrupted'))
