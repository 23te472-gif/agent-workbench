import React,{useMemo,useState} from 'react';
import {catalog} from './style-catalog.mjs';
import {draftFromStyle,buildHumanStyle,roleFields,scenes} from './persona-editor.mjs';
import useDialog from './use-dialog.js';
export default function PersonaEditor({seat,style,onApply,onClose,locked,chat}){
 const [draft,setDraft]=useState(()=>draftFromStyle(style,chat?'chat':'work'));
 const generated=useMemo(()=>{try{return {style:buildHumanStyle(draft)};}catch(e){return {error:e.message};}},[draft]);
 const dialog=useDialog(onClose);
 function field(key,value){setDraft(v=>({...v,[key]:value}));}
 return <div className="memory-overlay"><section ref={dialog} className="persona-editor memory-panel" role="dialog" aria-modal="true" aria-label={`${seat} 角色编辑器`}><header><div><h2>{seat} · 角色编辑器</h2><p>从当前角色开始填写；应用后成为自定义风格，新建会话才生效。</p></div><button type="button" className="auto-close" aria-label="关闭角色编辑器" onClick={onClose}>×</button></header>
 <p>状态、缺陷与关系是表达设定；记忆仍需明确保存，不自动遗忘，也不虚构经历。</p>
 <div className="role-editor-grid"><label>名字<input aria-label="角色名字" value={draft.name} maxLength={60} disabled={locked} onChange={e=>field('name',e.target.value)}/></label><label>使用场景<select aria-label="角色使用场景" value={draft.scene} disabled={locked} onChange={e=>field('scene',e.target.value)}>{Object.entries(scenes).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
 {roleFields.map(([id,label,hint])=><label className={['rules','states','extra'].includes(id)?'wide':''} key={id}>{label}<textarea aria-label={`角色${label}`} value={draft[id]} disabled={locked} maxLength={id==='extra'?3000:1000} placeholder={hint} onChange={e=>field(id,e.target.value)}/></label>)}</div>
 <details className="persona-reference"><summary>通用模板原文与验收清单</summary><pre>{catalog.human_template}</pre></details>
 <details className="persona-reference"><summary>查看生成预览 {generated.style?`· ${generated.style.text.length}/3000 字`:''}</summary><pre aria-label="角色生成预览">{generated.style?.text||generated.error}</pre></details>
 <p className="role-editor-note">验收清单用于你试聊后检查；填写完成不代表已验证模型表现。取消不会改动原设定。</p>
 {generated.error&&<p className="auto-warning" role="status">{generated.error}</p>}
 <footer><button type="button" className="auto-button" onClick={onClose}>取消</button><button type="button" className="auto-button auto-primary" disabled={locked||!generated.style} onClick={()=>onApply(generated.style)}>应用为自定义风格</button></footer>
 </section></div>;
}
