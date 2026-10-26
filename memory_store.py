"""Small, bounded explicit memories. No embeddings, model calls or automatic extraction."""
from pathlib import Path
import json,re,threading,uuid
from credential_store import atomic_json
from session_store import now

class MemoryStore:
    LIMIT=1000;WARN=800;MAX_BYTES=4*1024*1024;MAX_TEXT=500;RETRIEVE=20;CONTEXT=6000
    def __init__(self,path):self.path=Path(path);self.lock=threading.RLock()
    def _load(self):
        if not self.path.exists():return []
        try:
            if self.path.stat().st_size>self.MAX_BYTES:raise ValueError()
            items=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(items,list) or len(items)>self.LIMIT:raise ValueError()
            seen=set()
            for row in items:
                if not isinstance(row,dict) or not re.fullmatch('[a-f0-9]{32}',row['id']) or row['id'] in seen:raise ValueError()
                seen.add(row['id']);self._fields(row)
                if not isinstance(row['updated'],str):raise ValueError()
            return items
        except (ValueError,KeyError,TypeError):raise ValueError('记忆文件损坏或超限，原文件未改动，请检查 memory.json') from None
    def _fields(self,row):
        if row.get('scope') not in ('A','B','shared') or row.get('kind') not in ('profile','preference','note'):raise ValueError('记忆范围或类型无效')
        if not isinstance(row.get('text'),str) or not 1<=len(row['text'].strip())<=self.MAX_TEXT:raise ValueError('每条记忆请输入 1–500 字')
        source=row.get('source')
        if source is not None:
            if not isinstance(source,dict) or any(not isinstance(source.get(k),str) or not re.fullmatch('[a-f0-9]{32}',source[k]) for k in ('chat_id','message_id')):raise ValueError('记忆来源无效')
            if source.get('seat') not in ('U','A','B') or not isinstance(source.get('excerpt'),str) or not 1<=len(source['excerpt'])<=500 or not isinstance(source.get('title'),str) or len(source['title'])>100:raise ValueError('记忆来源内容无效')
    def _write(self,rows):
        if len(json.dumps(rows,ensure_ascii=False,indent=2).encode('utf-8'))>self.MAX_BYTES:raise ValueError('记忆文件达到 4 MiB 上限，请先整理')
        atomic_json(self.path,rows)
    def snapshot(self):
        with self.lock:
            rows=self._load();size=self.path.stat().st_size if self.path.exists() else 0
            return dict(items=sorted(rows,key=lambda r:r['updated'],reverse=True),count=len(rows),limit=self.LIMIT,warn_at=self.WARN,bytes=size,max_bytes=self.MAX_BYTES,warning=len(rows)>=self.WARN or size>=self.MAX_BYTES*.8,retrieve_limit=self.RETRIEVE,context_limit=self.CONTEXT)
    def save(self,payload):
        self._fields(payload)
        with self.lock:
            rows=self._load();identifier=payload.get('id');old=next((r for r in rows if r['id']==identifier),None)
            if identifier and not old:raise ValueError('记忆不存在')
            if not identifier:
                duplicate=next((r for r in rows if r['scope']==payload['scope'] and r['kind']==payload['kind'] and r['text']==payload['text'].strip() and r.get('source')==payload.get('source')),None)
                if duplicate:return duplicate
                if len(rows)>=self.LIMIT:raise ValueError('已达 1000 条记忆上限，请先整理或删除；已有内容未被自动清除')
                identifier=uuid.uuid4().hex
            row=dict(id=identifier,scope=payload['scope'],kind=payload['kind'],text=payload['text'].strip(),updated=now())
            source=payload.get('source',old.get('source') if old else None)
            if source is not None:row['source']={k:source[k] for k in ('chat_id','message_id','seat','excerpt','title')}
            self._write([r for r in rows if r['id']!=identifier]+[row]);return row
    def delete(self,identifier):
        with self.lock:
            rows=self._load()
            if not any(r['id']==identifier for r in rows):raise ValueError('记忆不存在')
            self._write([r for r in rows if r['id']!=identifier]);return self.snapshot()
    def clear(self):
        with self.lock:self._write([]);return self.snapshot()
    @staticmethod
    def _tokens(text):
        text=text.lower();tokens=set(re.findall('[a-z0-9_]{2,}',text))
        for part in re.findall('[\u4e00-\u9fff]+',text):tokens.update(part[i:i+2] for i in range(len(part)-1))
        return tokens
    def relevant(self,seat,query):
        if seat not in ('A','B'):raise ValueError('记忆席位无效')
        with self.lock:
            tokens=self._tokens(query);ranked=[]
            for index,row in enumerate(self._load()):
                if row['scope'] not in (seat,'shared'):continue
                overlap=len(tokens & self._tokens(row['text']))
                if row['kind']=='note' and not overlap:continue
                ranked.append((row['kind']!='note',overlap,row['updated'],index,row))
            ranked.sort(key=lambda r:r[:4],reverse=True);selected=[];used=0
            for *_,row in ranked:
                if len(selected)>=self.RETRIEVE:break
                if used+len(row['text'])+3>self.CONTEXT:continue
                selected.append(row);used+=len(row['text'])+3
            return selected
