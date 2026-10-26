"""User-bound DPAPI storage; public profile views never include a secret."""
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,unquote
import base64,ctypes,json,os,re,threading,uuid

class Blob(ctypes.Structure):
    _fields_=[('size',ctypes.c_uint32),('data',ctypes.POINTER(ctypes.c_ubyte))]

def _crypt(data,decrypt=False):
    if os.name!='nt':raise ValueError('密钥安全保存需要 Windows DPAPI')
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));output=Blob()
    api=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=api.CryptUnprotectData if decrypt else api.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(Blob)];fn.restype=ctypes.c_bool
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):raise ValueError('密钥加解密失败，请在当前 Windows 用户下重新填写')
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel.LocalFree(output.data)

def protect(secret):return 'dpapi-v1:'+base64.b64encode(_crypt(secret.encode('utf-8'))).decode('ascii')
def unprotect(value):
    try:
        if not value.startswith('dpapi-v1:'):raise ValueError()
        return _crypt(base64.b64decode(value[9:],validate=True),True).decode('utf-8')
    except Exception:raise ValueError('密钥读取失败，请在当前 Windows 用户下重新填写') from None

def validate_url(value):
    if not isinstance(value,str) or len(value)>1000 or re.search(r'[\s\x00-\x1f\x7f]',value):raise ValueError('接口地址无效')
    try:
        url=urlsplit(value);port=url.port
        if url.scheme.lower()!='https' or not url.hostname or url.username is not None or url.password is not None or url.query or url.fragment:raise ValueError()
        host=url.hostname.encode('idna').decode().lower();host='['+host+']' if ':' in host else host
        netloc=host+(f':{port}' if port is not None else '')
        path=url.path.rstrip('/')
        if any(part in ('.','..') for part in unquote(path).split('/')) or '\\' in unquote(path) or path.endswith(('/chat/completions','/models')):raise ValueError()
        return urlunsplit(('https',netloc,path,'',''))
    except (ValueError,UnicodeError):raise ValueError('请填写 HTTPS 基础地址，不含账号、查询参数或 /chat/completions') from None

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name('.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)

class ProfileStore:
    def __init__(self,base,encrypt=protect,decrypt=unprotect):
        self.path=Path(base)/'providers.json';self.encrypt=encrypt;self.decrypt=decrypt;self.lock=threading.RLock()
    def _load(self):
        if not self.path.exists():return []
        try:
            if self.path.stat().st_size>256*1024:raise ValueError()
            rows=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(rows,list) or len(rows)>32:raise ValueError()
            ids=set()
            for p in rows:
                if not isinstance(p,dict) or not re.fullmatch('[a-f0-9]{32}',p['id']) or p['id'] in ids or p['kind'] not in ('deepseek','compatible','codex_local'):raise ValueError()
                ids.add(p['id'])
                if p['kind']=='codex_local':
                    if p['base_url']!='codex://local' or p['encrypted_key']:raise ValueError()
                else:validate_url(p['base_url'])
                if not all(isinstance(p[k],str) for k in ('name','model','encrypted_key')):raise ValueError()
            return rows
        except Exception:raise ValueError('模型配置损坏，原文件保持不变；请检查 providers.json') from None
    @staticmethod
    def public(p):return {**{k:p[k] for k in ('id','name','kind','base_url','model')},'has_key':bool(p['encrypted_key']),'requires_key':p['kind']!='codex_local'}
    def list(self):
        with self.lock:return [self.public(p) for p in self._load()]
    def save(self,payload):
        with self.lock:
            rows=self._load();identifier=payload.get('id') or uuid.uuid4().hex
            old=next((p for p in rows if p['id']==identifier),None)
            if payload.get('id') and not old:raise ValueError('配置不存在')
            name=payload.get('name','');model=payload.get('model','');kind=payload.get('kind')
            if not isinstance(name,str) or not 1<=len(name.strip())<=80 or not isinstance(model,str) or not 1<=len(model.strip())<=200 or kind not in ('deepseek','compatible','codex_local'):raise ValueError('配置名或模型 ID 无效')
            base='codex://local' if kind=='codex_local' else validate_url(payload.get('base_url'));secret=payload.get('api_key','')
            if kind=='codex_local' and secret:raise ValueError('本机 Codex 不接收 API 密钥，请在 Codex 中登录')
            if not isinstance(secret,str) or len(secret)>4096 or (secret and (not secret.isascii() or re.search(r'[\x00-\x20\x7f]',secret))):raise ValueError('API 密钥格式无效，请勿包含空格或换行')
            if old and old['base_url']!=base and not secret:raise ValueError('接口地址已变更，请重新填写对应密钥，不会把旧密钥发送到新地址')
            encrypted='' if kind=='codex_local' else (self.encrypt(secret) if secret else (old['encrypted_key'] if old else ''))
            row=dict(id=identifier,name=name.strip(),kind=kind,base_url=base,model=model.strip(),encrypted_key=encrypted)
            if not old and len(rows)>=32:raise ValueError('模型配置最多 32 项')
            rows=[p for p in rows if p['id']!=identifier]+[row];atomic_json(self.path,rows);return self.public(row)
    def credentials(self,identifier):
        with self.lock:
            p=next((p for p in self._load() if p['id']==identifier),None)
            if p is None:raise ValueError('模型配置不存在')
            if p['kind']=='codex_local':return self.public(p),''
            if not p['encrypted_key']:raise ValueError('请先为所选模型保存 API 密钥')
            return self.public(p),self.decrypt(p['encrypted_key'])
    def delete_key(self,identifier):
        with self.lock:
            rows=self._load();row=next((p for p in rows if p['id']==identifier),None)
            if row is None:raise ValueError('配置不存在')
            row['encrypted_key']='';atomic_json(self.path,rows);return self.public(row)
    def delete(self,identifier):
        with self.lock:
            rows=self._load()
            if not any(p['id']==identifier for p in rows):raise ValueError('配置不存在')
            atomic_json(self.path,[p for p in rows if p['id']!=identifier])
            return dict(id=identifier,deleted=True)
