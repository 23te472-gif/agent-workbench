"""Per-app mutex plus authenticated loopback show-only IPC; never matches a console title."""
from pathlib import Path
import ctypes,ctypes.wintypes as wt
import hashlib,hmac,json,os,secrets,socket,threading,time

class SingleInstance:
    def __init__(self,base,on_show):
        self.base=Path(base);self.path=self.base/'data/instance.json';self.on_show=on_show
        self.token=secrets.token_urlsafe(32);self.socket=None;self.handle=None;self.closed=False
        self.api=ctypes.WinDLL('kernel32',use_last_error=True)
        self.api.CreateMutexW.argtypes=[wt.LPVOID,wt.BOOL,wt.LPCWSTR];self.api.CreateMutexW.restype=wt.HANDLE
        self.api.CloseHandle.argtypes=[wt.HANDLE];self.api.CloseHandle.restype=wt.BOOL
    def acquire(self):
        name='Local\\PersonalToolCenterV2-'+hashlib.sha256(str(self.base.resolve()).casefold().encode()).hexdigest()[:16]
        self.handle=self.api.CreateMutexW(None,False,name)
        if not self.handle:raise OSError('不能创建工具中心启动锁')
        if ctypes.get_last_error()==183:
            for _ in range(20):
                try:
                    row=json.loads(self.path.read_text(encoding='utf-8'))
                    with socket.create_connection(('127.0.0.1',int(row['port'])),timeout=.25) as sock:
                        sock.settimeout(1);sock.sendall(json.dumps(dict(token=row['token'],action='show')).encode()+b'\n')
                        if json.loads(sock.recv(1024)).get('service')=='personal-tool-center-v2':return False
                except (OSError,ValueError,KeyError,TypeError):time.sleep(.1)
            raise OSError('工具中心正在启动或忙碌，请稍候；没有重复打开新窗口。')
        self.base.joinpath('data').mkdir(parents=True,exist_ok=True)
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM);self.socket.bind(('127.0.0.1',0));self.socket.listen(4);self.socket.settimeout(1)
        self.path.write_text(json.dumps(dict(port=self.socket.getsockname()[1],token=self.token,pid=os.getpid())),encoding='utf-8')
        threading.Thread(target=self._listen,name='tool-center-window-ipc',daemon=True).start();return True
    def _listen(self):
        while not self.closed:
            try:conn,_=self.socket.accept()
            except socket.timeout:continue
            except OSError:break
            with conn:
                try:
                    conn.settimeout(.5);raw=conn.recv(1024);data=json.loads(raw)
                    if not isinstance(data,dict) or data.get('action')!='show' or not isinstance(data.get('token'),str):continue
                    if not hmac.compare_digest(data['token'],self.token):continue
                    conn.sendall(b'{"service":"personal-tool-center-v2"}')
                    self.on_show()
                except (OSError,ValueError,TypeError):continue
    def close(self):
        self.closed=True
        if self.socket:self.socket.close()
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None
        try:
            if self.path.exists() and json.loads(self.path.read_text()).get('token')==self.token:self.path.unlink()
        except (OSError,ValueError):pass
