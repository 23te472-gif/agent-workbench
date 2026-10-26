"""Validate per-seat styles independently of transport and task authority."""
from persona_catalog import resolve_style
def styles_for(payload):
    legacy=payload.get('persona','conductor')
    if legacy not in ('conductor','qinghe','lele','jingshui'):raise ValueError('不支持的人格选项')
    choices=payload.get('seat_styles',{})
    if not isinstance(choices,dict) or set(choices)-{'A','B'}:raise ValueError('表达风格仅支持 A、B 两个席位')
    result={}
    for seat in ('A','B'):
        style=choices.get(seat,{'preset':legacy})
        if not isinstance(style,dict) or style.get('preset') not in ('conductor','qinghe','lele','jingshui','custom'):raise ValueError(seat+' 席表达风格无效')
        preset=style['preset'];text=style.get('text','')
        if not isinstance(text,str) or len(text)>3000 or (preset=='custom' and not text.strip()):raise ValueError(seat+' 席自定义风格需为 1–3000 字')
        result[seat]=dict(preset=preset,text=text.strip() if preset=='custom' else '')
        if preset in ('lele','jingshui'):
            resolved=style.get('resolved_text',resolve_style(preset))
            if not isinstance(resolved,str) or not 1<=len(resolved)<=12000:raise ValueError('性格设定长度无效')
            result[seat]['resolved_text']=resolved
    return result
