import React,{useState} from 'react';
import {catalog,toggleTrait,customFromTraits} from './style-catalog.mjs';
import './seat-style.css';
import PersonaEditor from './persona-editor.jsx';
export default function SeatStyle({seat,style={preset:'lele',text:''},onChange,locked,chat=false}){
 const [traits,setTraits]=useState([]),[error,setError]=useState(''),[editor,setEditor]=useState(false);
 const preset=catalog.presets.find(p=>p.id===style.preset);
 function pick(d,v){try{setTraits(toggleTrait(traits,d,v));setError('');}catch(e){setError(e.message);}}
 function apply(){try{onChange(customFromTraits(style,traits));setTraits([]);setError('');}catch(e){setError(e.message);}}
 return <div className="seat-style-controls"><label className="auto-field">{seat} 席表达风格<select aria-label={`${seat} 席表达风格`} value={style.preset} disabled={locked} onChange={e=>{onChange({preset:e.target.value});setTraits([]);setError('');}}>{catalog.presets.map(p=><option key={p.id} value={p.id}>{p.name} · {p.summary}</option>)}{['conductor','qinghe'].includes(style.preset)&&<option value={style.preset}>原会话风格 · {style.preset==='qinghe'?'清和':'总谱'}</option>}<option value="custom">自定义风格</option></select></label>
 <div className="persona-editor-entry"><button type="button" className="auto-button" disabled={locked} onClick={()=>setEditor(true)}>角色编辑器</button><small>关系、动机、状态与行为规则</small></div>
 {editor&&<PersonaEditor seat={seat} style={style} locked={locked} chat={chat} onClose={()=>setEditor(false)} onApply={value=>{onChange(value);setEditor(false);setTraits([]);setError('');}}/>}
 {preset&&<div className="persona-summary"><b>{preset.name}</b><span>{preset.summary}</span><details><summary>查看完整设定</summary><pre>{preset.text}</pre></details></div>}
 {style.preset==='custom'&&<label className="auto-field">风格说明<textarea aria-label={`${seat} 席自定义风格`} value={style.text||''} maxLength={3000} disabled={locked} placeholder="写下语气、回答习惯与边界，也可以用下方词库组合。" onChange={e=>onChange({text:e.target.value})}/><small>{(style.text||'').length}/3000 · {chat?'调整这位成员的表达方式':'仅调整表达，不改变本席职责'}</small></label>}
 <details className="persona-library"><summary>性格词库 <small>{catalog.dimensions.length} 个维度 · 最多选 4 项</small></summary><p>选词后生成可编辑的自定义风格，新建会话后生效。</p><div className="persona-dimensions">{catalog.dimensions.map(d=><section key={d.name}><b>{d.name}</b><div>{d.options.map(v=><button key={v} type="button" className="trait-chip" aria-pressed={traits.some(t=>t.dimension===d.name&&t.value===v)} disabled={locked} onClick={()=>pick(d.name,v)}>{v}</button>)}</div></section>)}</div>{error&&<p role="alert">{error}</p>}<div className="persona-apply"><span>已选 {traits.length}/4</span><button className="auto-button" type="button" disabled={locked||!traits.length} onClick={apply}>用选词生成自定义风格</button><button className="auto-button" type="button" disabled={locked||!traits.length} onClick={()=>{setTraits([]);setError('');}}>清空选词</button></div><details><summary>查看完整词库与配方</summary><pre>{catalog.lexicon}</pre></details></details>
 </div>;
}
