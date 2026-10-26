import React,{useEffect,useState} from 'react';
import {call} from './auto.jsx';
export default function ThemePicker(){
 const [theme,setTheme]=useState('mint'),[ready,setReady]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState('');
 useEffect(()=>{let live=true;async function load(){try{const v=await call('api_appearance_get');if(live)setTheme(v.theme);}catch(e){if(live)setError('配色读取失败，可重新选择。');}finally{if(live)setReady(true);}}if(window.pywebview?.api?.call)load();else window.addEventListener('pywebviewready',load,{once:true});return()=>{live=false;window.removeEventListener('pywebviewready',load);};},[]);
 useEffect(()=>{document.documentElement.dataset.theme=theme;},[theme]);
 async function change(value){if(saving)return;setSaving(true);setError('');try{const v=await call('api_appearance_save',{theme:value});setTheme(v.theme);}catch(e){setError('配色未保存，请重试。');}finally{setSaving(false);}}
 return <label className="theme-picker"><span className="theme-swatch" aria-hidden="true"/><span>配色</span><select aria-label="界面配色" value={theme} disabled={!ready||saving} onChange={e=>change(e.target.value)}><option value="mint">薄荷绿</option><option value="blue">雾蓝</option><option value="lavender">浅紫</option><option value="apricot">暖杏</option></select>{error&&<small role="status">{error}</small>}</label>;
}
