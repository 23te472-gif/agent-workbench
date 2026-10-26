"""Small UI-only preference file, independent of credentials and conversations."""
import json,threading
from pathlib import Path
from credential_store import atomic_json

class AppearanceStore:
    THEMES=('mint','blue','lavender','apricot')
    def __init__(self,path):self.path=Path(path);self.lock=threading.RLock()
    def get(self):
        with self.lock:
            try:
                if self.path.stat().st_size>4096:return dict(theme='mint')
                value=json.loads(self.path.read_text(encoding='utf-8'))
                return dict(theme=value['theme'] if value['theme'] in self.THEMES else 'mint')
            except (OSError,ValueError,KeyError,TypeError):return dict(theme='mint')
    def save(self,theme):
        if not isinstance(theme,str) or theme not in self.THEMES:raise ValueError('配色选项无效')
        with self.lock:atomic_json(self.path,dict(theme=theme));return dict(theme=theme)
