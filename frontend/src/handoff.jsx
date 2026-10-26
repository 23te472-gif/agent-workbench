import React,{useState} from 'react';
import {deliveryFormats,generationPrompt} from './handoff-model.mjs';
import './handoff.css';

export default function GenerationHandoff({session,onCopy}){
 const [format,setFormat]=useState('auto');
 const prompt=generationPrompt(session,format);
 if(!prompt)return null;
 return <section className="generation-handoff" aria-label="最终生成指令">
  <div className="generation-heading"><div><span className="auto-kicker">READY TO CREATE</span><h3>生成指令</h3></div><span className="auto-pill">复制后继续制作</span></div>
  <p>已整理原始需求、补充意见、最近审查和最终修订。贴到 DeepSeek 或 Codex，让它继续制作成品。</p>
  <label className="auto-field">交付形式<select aria-label="生成指令交付形式" value={format} onChange={e=>setFormat(e.target.value)}>{deliveryFormats.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
  <details className="generation-preview"><summary>预览完整指令 · {prompt.length.toLocaleString()} 字符</summary><textarea aria-label="生成指令预览" readOnly value={prompt} spellCheck={false}/></details>
  <div className="generation-actions"><small>本地整理，不额外调用模型。文件生成取决于接收端能力。</small><button className="auto-button auto-primary" onClick={()=>onCopy(prompt)}>复制生成指令 →</button></div>
 </section>;
}
