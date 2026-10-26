"""Transport routing keeps API secrets away from the local Codex process."""
from provider_client import ProviderClient
from codex_channel import CodexChannel

class ModelChannels:
    def __init__(self,api=None,local=None):self.api=api or ProviderClient();self.local=local or CodexChannel()
    def _client(self,profile):return self.local if profile['kind']=='codex_local' else self.api
    def complete(self,profile,key,*args):return self._client(profile).complete(profile,'' if profile['kind']=='codex_local' else key,*args)
    def models(self,profile,key):return self._client(profile).models(profile,'' if profile['kind']=='codex_local' else key)
    def interrupt(self):
        for client in (self.api,self.local):
            method=getattr(client,'interrupt',None)
            if method:method()
