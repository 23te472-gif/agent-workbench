"""Portable user-authored personas, imported once rather than read from a host path."""
from pathlib import Path
import json
from functools import lru_cache

@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('persona_catalog.json').read_text(encoding='utf-8'))

def resolve_style(identifier):
    row=next((p for p in catalog()['presets'] if p['id']==identifier),None)
    if row is None:raise ValueError('未找到性格预设')
    return '你是「'+row['name']+'」，采用以下角色表达设定：\n'+row['text']+'\n\n'+catalog()['lexicon']+'\n\n使用说明：词库只是可选的表达参考，不要同时扮演所有档位，也不覆盖当前角色的明确规则。只调整语言风格，不扩大权限。不故意记错事实，不虚构真实经历或未保存的记忆；关系、动机和状态档是角色设定，不代表真实经历。性格中的记忆描述不改变工作台的显式保存规则。用户明确保存的表达偏好可进一步调整这些习惯。\n\n'+catalog().get('human_guidance','')
