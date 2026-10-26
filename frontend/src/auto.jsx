import React,{useEffect,useRef,useState} from 'react';
import {isActive,statusLabel,validatePlan,sameModel,canRetry,finalReply,stepLabel,buildProfilePayload,styleLabel} from './auto-model.mjs';
import './auto.css';
import GenerationHandoff from './handoff.jsx';
import SeatStyle from './seat-style.jsx';
import useDialog from './use-dialog.js';

export async function call(action,payload={}){
 if(!window.pywebview?.api?.call)throw Error('正在等待本地桌面服务。');
 const result=await window.pywebview.api.call(action,payload);
 if(!result.ok)throw Error(result.error||'操作未完成');
 return result.data;
}
const emptyProfile=()=>({id:'',name:'DeepSeek',kind:'deepseek',base_url:'https://api.deepseek.com',model:'deepseek-flash',api_key:''});
function Usage({usage}){return <span>{usage&&usage.known!==false&&Number.isFinite(usage.prompt_tokens)&&Number.isFinite(usage.completion_tokens)?`输入 ${usage.prompt_tokens.toLocaleString()} / 输出 ${usage.completion_tokens.toLocaleString()} Token`:'Token 用量未返回'}</span>;}
export function Settings({profiles,onProfiles,onRemove,onClose,locked}){
 const [draft,setDraft]=useState(emptyProfile),[busy,setBusy]=useState(''),[error,setError]=useState(''),[message,setMessage]=useState(''),[models,setModels]=useState([]);
 const [clientPath,setClientPath]=useState('');
 const [confirmDelete,setConfirmDelete]=useState(false);
 const dialog=useDialog(close,!!busy),first=useRef(null),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 useEffect(()=>{call('api_local_path').then(value=>{if(mounted.current)setClientPath(value.executable||'');}).catch(()=>{});},[]);
 function close(){if(busy)return;setDraft(emptyProfile());onClose();}
 function choose(id){const p=profiles.find(x=>x.id===id);setDraft(p?{...p,api_key:''}:emptyProfile());setError('');setMessage('');setModels([]);setConfirmDelete(false);}
 function change(key,value){setDraft(d=>({...d,[key]:value}));setError('');setMessage('');setConfirmDelete(false);if(key==='base_url'||key==='model')setModels([]);}
 async function perform(action){
  if(busy||locked)return;setBusy(action);setError('');setMessage('');if(action!=='remove')setConfirmDelete(false);
  try{
   if(action==='remove'){
    const result=await call('api_profile_delete',{id:draft.id});if(!mounted.current)return;
    onRemove(result.id);setDraft(emptyProfile());setModels([]);setConfirmDelete(false);setMessage('配置已删除，历史会话保留。');
   }else if(action==='path'){
    const value=await call('api_local_path',{executable:clientPath});if(!mounted.current)return;setClientPath(value.executable||'');setMessage('本机路径已保存，仅用于这台电脑。请重新检测。');
   }else if(action==='discover'){
    const result=await call('api_discover_local');if(!mounted.current)return;
    setModels((result.models||[]).map(m=>m.id));setMessage(result.message);
    if(result.state==='catalog')setDraft({...emptyProfile(),name:'本机 Codex',kind:'codex_local',base_url:'codex://local',model:result.models?.[0]?.id||''});
   }else if(action==='save'){
    const payload=buildProfilePayload(draft);setDraft(d=>({...d,api_key:''}));
    if(!draft.name.trim()||!draft.base_url.trim()||!draft.model.trim())throw Error('请填写配置名、接口地址和模型 ID。');
    const p=await call('api_profile_save',payload);if(!mounted.current)return;
    onProfiles(p);setDraft({...p,api_key:''});setMessage('配置已保存。密钥不会回读。');
   }else if(action==='test'){
    const result=await call('api_profile_test',{id:draft.id});if(!mounted.current)return;
    setModels(result.models||[]);setMessage(result.message||'已读取模型列表；这不代表生成能力已验证。');
   }else{
    const p=await call('api_profile_delete_key',{id:draft.id});if(!mounted.current)return;
    onProfiles(p);setDraft({...p,api_key:''});setMessage('已删除此配置的密钥。');
   }
  }catch(e){if(mounted.current)setError(e.message);}finally{if(mounted.current)setBusy('');}
 }
 const local=draft.kind==='codex_local',saved=profiles.find(x=>x.id===draft.id),dirty=!!saved&&['name','kind','base_url','model'].some(k=>draft[k]!==saved[k]);
 return <div className="auto-modal-backdrop"><section className="auto-modal" role="dialog" aria-modal="true" aria-labelledby="model-settings-title" ref={dialog}>
  <div className="auto-modal-head"><div><span className="auto-kicker">YOUR MODELS</span><h2 id="model-settings-title">模型设置</h2></div><button className="auto-close" aria-label="关闭模型设置" disabled={!!busy} onClick={close}>×</button></div>
  <div className="auto-modal-body"><p className="auto-description">连接本机已登录的 Codex，或使用你自己的 API 密钥。换一台电脑后重新检测客户端，密钥由使用者自行填写。</p>
  <div className="auto-discovery"><div><strong>本机模型入口</strong><p>检测安装、登录和目录，不发送生成任务。</p></div><button className="auto-button" disabled={!!busy||locked} onClick={()=>perform('discover')}>{busy==='discover'?'正在检测…':'检测本机 Codex'}</button></div>
  <details className="auto-client-path"><summary>没有检测到？手动指定客户端</summary><label className="auto-field">原生 Codex 路径<input aria-label="本机 Codex 路径" value={clientPath} disabled={!!busy||locked} placeholder="完整 codex.exe 路径；留空恢复自动检测" onChange={e=>setClientPath(e.target.value)}/></label><button className="auto-button" disabled={!!busy||locked} onClick={()=>perform('path')}>{busy==='path'?'保存中…':'保存本机路径'}</button><p className="auto-small">只保存在本机 host.json，不随模型配置或会话共享；不支持脚本或命令参数。</p></details>
  {locked&&<div className="auto-warning">协作运行中，结束后可修改配置或测试连接。</div>}
  <label className="auto-field">已保存配置<select ref={first} value={draft.id} disabled={!!busy||locked} onChange={e=>choose(e.target.value)}><option value="">＋ 新建配置</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.name} · {p.model}{p.kind==='codex_local'?' · 本机登录':p.has_key?' · 已配置密钥':' · 缺少密钥'}</option>)}</select></label>
  <div className="auto-form-grid"><label className="auto-field">配置名<input value={draft.name} disabled={!!busy||locked} onChange={e=>change('name',e.target.value)}/></label><label className="auto-field">服务商类型<select aria-label="通道类型" value={draft.kind} disabled={!!busy||locked} onChange={e=>{setDraft({...emptyProfile(),name:e.target.value==='codex_local'?'本机 Codex':'API 配置',kind:e.target.value,base_url:e.target.value==='codex_local'?'codex://local':'https://api.deepseek.com',model:''});setModels([]);setMessage('');setError('');}}><option value="deepseek">DeepSeek API</option><option value="compatible">兼容 API 接口</option><option value="codex_local">本机 Codex</option></select></label></div>
  {!local&&<label className="auto-field">接口地址<input aria-label="接口地址" type="url" value={draft.base_url} disabled={!!busy||locked} spellCheck={false} onChange={e=>change('base_url',e.target.value)}/></label>}
  <label className="auto-field">模型 ID<input aria-label="模型 ID" value={draft.model} list="auto-model-options" disabled={!!busy||locked} spellCheck={false} onChange={e=>change('model',e.target.value)}/><datalist id="auto-model-options">{models.map(m=><option key={m} value={m}/>)}</datalist></label>
  {!local&&<label className="auto-field">API 密钥 <span>{saved?.has_key?'已配置 · 留空保留；更换地址需输入新密钥':'尚未配置'}</span><input aria-label="API 密钥" type="password" autoComplete="new-password" value={draft.api_key} disabled={!!busy||locked} placeholder={saved?.has_key?'不会显示已保存的密钥':'输入你自己的 API 密钥'} onChange={e=>change('api_key',e.target.value)}/></label>}
  <p className="auto-small">{local?'由本机 Codex 管理登录，不读取或复制登录令牌。目录不代表生成权限；请先在 Codex 中登录。':'密钥由使用者手填，不从其他应用提取。保存后测试连接可读取模型列表，也可手填实际模型 ID。'} 检测与连接测试均不发起生成。</p>
  {error&&<div className="auto-warning" role="alert">{error}</div>}{message&&<div className="auto-feedback" role="status">{message}</div>}
  {confirmDelete&&saved&&<div className="auto-warning" role="group" aria-label="删除配置确认"><p>删除“{saved.name} · {saved.model}”及其已保存密钥？历史仍可回看；关联任务如需重新运行，请选择其他配置新建会话。</p><div className="profile-delete-confirm"><button className="auto-button" disabled={!!busy} onClick={()=>setConfirmDelete(false)}>取消</button><button className="auto-button auto-danger-text" disabled={locked||!!busy} onClick={()=>perform('remove')}>{busy==='remove'?'删除中…':'确认删除配置'}</button></div></div>}
  </div><div className="auto-modal-actions"><button className="auto-button auto-danger-text" disabled={locked||!!busy||!saved} onClick={()=>{setConfirmDelete(true);setError('');setMessage('');requestAnimationFrame(()=>dialog.current?.querySelector('[aria-label="删除配置确认"]')?.scrollIntoView({block:'nearest'}));}}>删除配置</button><button className="auto-button auto-danger-text" disabled={locked||!!busy||!saved?.has_key} onClick={()=>perform('delete')}>{busy==='delete'?'删除中…':'删除密钥'}</button><div><button className="auto-button" disabled={locked||!!busy||!draft.id||dirty||!!draft.api_key} onClick={()=>perform('test')}>{busy==='test'?'连接测试中…':'测试连接'}</button><button className="auto-button auto-primary" disabled={locked||!!busy} onClick={()=>perform('save')}>{busy==='save'?'保存中…':'保存配置'}</button></div></div>
 </section></div>;
}

export default function AutoWorkspace(){
 const [profiles,setProfiles]=useState([]),[sessions,setSessions]=useState([]),[session,setSession]=useState(null),[view,setView]=useState(null),[ready,setReady]=useState(false),[settings,setSettings]=useState(false),[busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[note,setNote]=useState('');
 const [plan,setPlan]=useState({task:'',primary_id:'',reviewer_id:'',rounds:1,call_limit:9,max_tokens:1024,context_count:0,persona:'conductor',seat_styles:{A:{preset:'lele',text:''},B:{preset:'jingshui',text:''}}});

 const alive=useRef(true),pollTimer=useRef(null),copyArea=useRef(null),loadSequence=useRef(0),actionLock=useRef(false);
 const active=isActive(session),display=view||session,history=!!view;
 function setField(k,v){setPlan(p=>({...p,[k]:v}));}
 function setSeatStyle(seat,patch){setPlan(p=>({...p,seat_styles:{...p.seat_styles,[seat]:{...p.seat_styles[seat],...patch}}}));}
 function remember(s){if(!s)return;setSessions(list=>[{id:s.id,title:s.title||s.task,status:s.status,updated:new Date().toISOString(),call_count:s.call_count,call_limit:s.call_limit},...list.filter(x=>x.id!==s.id)]);}
 async function bootstrap(){try{const data=await call('api_bootstrap');if(!alive.current)return;setProfiles(data.profiles||[]);setSessions(data.sessions||[]);setSession(data.active);setPlan(p=>({...p,context_count:data.room_available===false?0:p.context_count,primary_id:p.primary_id||(data.profiles?.[0]?.id||''),reviewer_id:p.reviewer_id||(data.profiles?.[1]?.id||data.profiles?.[0]?.id||'')}));setReady(true);setError('');}catch(e){if(alive.current)setError(e.message);}}
 useEffect(()=>{alive.current=true;const init=()=>bootstrap();if(window.pywebview?.api?.call)init();else window.addEventListener('pywebviewready',init,{once:true});return()=>{alive.current=false;loadSequence.current++;clearTimeout(pollTimer.current);window.removeEventListener('pywebviewready',init);};},[]);
 useEffect(()=>{
  if(!active)return;let cancelled=false;
  async function poll(){try{const s=await call('api_status',{id:session.id});if(cancelled||!alive.current)return;if(s){setSession(s);remember(s);}setError('');}catch(e){if(!cancelled&&alive.current)setError('状态读取失败：'+e.message);}finally{if(!cancelled&&alive.current)pollTimer.current=setTimeout(poll,600);}}
  pollTimer.current=setTimeout(poll,500);return()=>{cancelled=true;clearTimeout(pollTimer.current);};
 },[active,session?.id]);
 async function action(name,fn){if(actionLock.current)return;actionLock.current=true;setBusy(name);setError('');setNotice('');try{await fn();}catch(e){if(alive.current)setError(e.message);}finally{actionLock.current=false;if(alive.current)setBusy('');}}
 function removeProfile(id){setProfiles(list=>list.filter(p=>p.id!==id));setPlan(p=>({...p,primary_id:p.primary_id===id?'':p.primary_id,reviewer_id:p.reviewer_id===id?'':p.reviewer_id}));}
 function updateProfile(p){setProfiles(list=>[...list.filter(x=>x.id!==p.id),p]);setPlan(v=>({...v,primary_id:v.primary_id||p.id,reviewer_id:v.reviewer_id||p.id}));}
 async function start(){const message=validatePlan(plan,profiles);if(message){setError(message);return;}await action('start',async()=>{const s=await call('api_start',{...plan,task:plan.task.trim(),rounds:Number(plan.rounds),max_tokens:Number(plan.max_tokens),context_count:Number(plan.context_count)});if(!alive.current)return;loadSequence.current++;setView(null);setSession(s);remember(s);setNote('');});}
 async function reopen(id){const seq=++loadSequence.current;await action('history',async()=>{const s=await call('api_session',{id});if(alive.current&&seq===loadSequence.current)setView(s);});}
 async function copy(text){try{await navigator.clipboard.writeText(text);setNotice('已复制回复。');}catch{if(copyArea.current){copyArea.current.value=text;copyArea.current.focus();copyArea.current.select();try{if(document.execCommand('copy')){setNotice('已复制回复。');return;}}catch{}setNotice('自动复制不可用，回复已选中，请按 Ctrl+C。');}}}
 const A=profiles.find(p=>p.id===plan.primary_id),B=profiles.find(p=>p.id===plan.reviewer_id),validation=validatePlan(plan,profiles),final=finalReply(display);
 const completed=display?.steps?.filter(s=>s.state==='completed').length||0;
 return <div className="auto-shell">
  <aside className="auto-sidebar"><div className="auto-brand"><span>▦</span><div><strong>Agent 工作台</strong><small>AUTONOMOUS WORKSPACE</small></div></div><span className="auto-kicker">工作区</span>{history&&<button className="auto-button auto-return" onClick={()=>{loadSequence.current++;setView(null);}}>返回当前协作</button>}
   <div className="auto-history-title"><span className="auto-kicker">已保存会话</span><span>{sessions.length}</span></div><div className="auto-history">{sessions.length?sessions.map(s=><button key={s.id} className={display?.id===s.id?'selected':''} disabled={!!busy} onClick={()=>reopen(s.id)}><strong>{s.title||'未命名任务'}</strong><span>{statusLabel(s.status)} · {s.call_count}/{s.call_limit} 次</span></button>):<p>完成的思考会留在这里，<br/>随时重新打开。</p>}</div>
   <div className="auto-side-foot"><span className="auto-local-dot"/> 本机直连 · 公开回复<p>每个声部独立呈现<br/>有上限，也随时可以停下</p></div>
  </aside>
  <main className="auto-main"><header className="auto-header"><div><span className="auto-kicker">ONE TASK · TWO ROLES · A CLEAR FINISH</span><h1>把任务交给两个声部<span>。</span></h1><p>提案、审查、修订。输入一次任务，观察模型如何完成交接。</p></div><button className="auto-button" onClick={()=>setSettings(true)}>⚙ 模型设置</button></header>
   {error&&<div className="auto-warning" role="alert">{error}{!ready&&window.pywebview?.api?.call&&<button className="auto-link" onClick={bootstrap}>重新连接</button>}</div>}
   <div className="auto-layout"><section className="auto-compose auto-panel"><div className="auto-panel-heading"><div><span className="auto-kicker">THE BRIEF</span><h2>这次，一起做什么</h2></div><span className="auto-pill">文字协作</span></div>
    <label className="auto-task-label" htmlFor="auto-task">任务</label><textarea id="auto-task" aria-label="任务" className="auto-task" placeholder="例如：帮我把这个想法整理成一份简短方案，并检查遗漏。" value={plan.task} disabled={active||!!busy} onChange={e=>setField('task',e.target.value)}/>
    <div className="auto-roles">{[['A','主执行模型','primary_id'],['B','审查模型','reviewer_id']].map(([seat,label,key])=><div className={'auto-role role-'+seat} key={seat}><span className="auto-role-top"><b>{seat}</b><span>{label}<small>{seat==='A'?'提出方案 · 根据审查修订':'独立审查 · 指出问题'}</small></span></span><select aria-label={label} disabled={active||!!busy} value={plan[key]} onChange={e=>setField(key,e.target.value)}><option value="">选择模型配置</option>{profiles.map(p=><option key={p.id} value={p.id}>{p.name} · {p.model}{p.kind==='codex_local'?' · 本机':p.has_key?'':' · 未配密钥'}</option>)}</select><small className="auto-endpoint">{profiles.find(p=>p.id===plan[key])?.base_url||'先在模型设置中添加配置'}</small><SeatStyle seat={seat} style={plan.seat_styles[seat]} locked={active||!!busy} onChange={patch=>setSeatStyle(seat,patch)}/></div>)}</div>
    {sameModel(A,B)&&<div className="auto-same">同一模型、不同角色 · 两个席位分别生成真实回复</div>}
    {!profiles.length&&<button className="auto-setup" onClick={()=>setSettings(true)}>添加自己的模型与密钥 <span>→</span></button>}
    <div className="auto-options"><label className="auto-field">总请求上限<select aria-label="总请求上限" value={plan.call_limit} disabled={active||!!busy} onChange={e=>setField('call_limit',Number(e.target.value))}>{[3,6,9,15,30].map(n=><option key={n} value={n}>{n} 次</option>)}</select></label><label className="auto-field">轮数<input aria-label="轮数" type="number" min="1" max="10" value={plan.rounds} disabled={active||!!busy} onChange={e=>setField('rounds',e.target.value)}/></label><label className="auto-field">API 单次最大输出 Token<input aria-label="单次最大输出 Token" type="number" min="128" max="4096" value={plan.max_tokens} disabled={active||!!busy} onChange={e=>setField('max_tokens',e.target.value)}/></label></div>
    <p className="auto-small">两席仅围绕本次任务、已完成回复和你的补充意见协作。本机 Codex 的输出 Token 由客户端管理；Token 设置仅适用于 API。每次公开回复仍有字符限制。</p>
    <div className="auto-budget"><span className="auto-budget-icon">↔</span><div><strong>最多 {plan.call_limit} 次尝试 · 10 分钟</strong><p>当前计划 {Number(plan.rounds)>=1&&Number(plan.rounds)<=10?Number(plan.rounds)*3:'—'} 次生成请求：A 提案 → B 审查 → A 修订。达到上限自动结束，手动重试也计入总预算。</p></div></div>
    <div className="auto-start-row"><span>{!ready?'等待本地桌面服务…':active?'当前协作结束后，可开始新任务。':validation||'点击开始，即授权所选服务商接收本次任务与上下文。'}</span><button className="auto-button auto-primary" disabled={!ready||active||!!busy||!!validation} onClick={start}>{busy==='start'?'正在开始…':'开始协作'} <span>→</span></button></div>
   </section>
   <section className="auto-observe auto-panel"><div className="auto-panel-heading"><div><span className="auto-kicker">LIVE CONVERSATION</span><h2>{history?'会话回看':'观察协作'}</h2></div><span className={'auto-pill '+(active&&!history?'auto-live':'')}>{history?'只读记录':statusLabel(display?.status)}</span></div>
    {history&&<div className="auto-history-banner">正在查看已保存会话，原始回复只读。<button className="auto-link" onClick={()=>{loadSequence.current++;setView(null);}}>返回当前协作 →</button></div>}
    {display?<><div className="auto-session-brief"><h3>{display.title||display.task}</h3>{display.title&&display.title!==display.task&&<p>{display.task}</p>}<div className="auto-session-roles">{['A','B'].map(seat=><span key={seat}><b>{seat} · {seat==='A'?'主执行':'审查'}</b> {display.roles?.[seat]?.name} / {display.roles?.[seat]?.model} · 风格：{styleLabel(display.seat_styles?.[seat]?.preset||display.persona)}</span>)}</div>{sameModel(display.roles?.A,display.roles?.B)&&<small>同一模型、不同角色</small>}</div>
    <div className="auto-progress"><div><strong>{statusLabel(display.status)}</strong><span>{display.stage||'等待阶段'} · 已完成 {completed}/{display.planned_calls||display.rounds*3} 步</span></div><div><b>{display.call_count}/{display.call_limit}</b><span>尝试{isActive(display)&&!history?` · 剩余 ${Math.max(0,Math.ceil(display.seconds_left||0))} 秒`:''}</span></div><progress value={display.call_count} max={display.call_limit||9}/><small><Usage usage={display.usage}/></small></div>
    {display.error&&<div className="auto-warning" role="alert">{display.error}</div>}
    {!history&&active&&<div className="auto-stop-zone"><button className="auto-button auto-stop" disabled={busy==='stop'||display.status==='stopping'} onClick={()=>action('stop',async()=>{const s=await call('api_stop');if(alive.current&&s){setSession(s);remember(s);}})}>{display.status==='stopping'?'正在停止…':'停止协作'}</button><p>停止后不再发起下一次请求。已发送请求可能仍由服务商计费。</p></div>}
    <div className="auto-transcript">{(display.steps||[]).map(step=><article className={'auto-message role-'+step.seat} key={step.id}><div className="auto-message-head"><b className="auto-seat">{step.seat}</b><div><strong>{step.seat==='A'?'主执行':'审查'} · {step.stage}</strong><span>{step.model} · 第 {step.round} 轮</span></div><span className={'auto-step-state '+step.state}>{stepLabel(step)}</span></div><p className="auto-message-content">{step.content||(step.state==='running'?'等待服务商返回公开回复…':'未收到公开回复。')}</p>{step.error&&<p className="auto-step-error">{step.error}</p>}<div className="auto-message-meta"><span>{step.provider}{Number.isFinite(step.seconds)?` · ${step.seconds}s`:''}</span><Usage usage={step.usage}/><button className="auto-link" disabled={!step.content} onClick={()=>copy(step.content)}>复制</button></div></article>)}</div>
    {final&&<div className="auto-final"><span className="auto-kicker">COMPLETED REVISION · A</span><h3>最后修订</h3><p>{final.content}</p><button className="auto-link" onClick={()=>copy(final.content)}>复制完整修订 →</button></div>}
    {final&&<GenerationHandoff key={display.id} session={display} onCopy={copy}/>}
    {canRetry(display)&&<div className="auto-retry"><p>{history?'重新打开的中断任务可由你手动重试。':'交接已暂停，可手动重试失败步骤。'} 使用原有调用次数和首次开始的截止时间；不会重置预算。</p><button className="auto-button" disabled={!!busy||active} onClick={()=>action('retry',async()=>{const s=await call('api_retry',{id:display.id});if(alive.current){loadSequence.current++;setSession(s);setView(null);remember(s);}})}>手动重试</button></div>}
    {!history&&display.status==='running'&&<form className="auto-note" onSubmit={e=>{e.preventDefault();if(!note.trim())return;action('note',async()=>{const result=await call('api_note',{text:note.trim()});if(alive.current){setNote('');setNotice(result.message||'意见已加入下一次交接。');}});}}><label htmlFor="auto-note">可选插话 <span>在下次交接时生效</span></label><div><input id="auto-note" value={note} maxLength="1000" placeholder="没有补充也可以，模型会按计划继续。" onChange={e=>setNote(e.target.value)}/><button className="auto-button" disabled={!!busy||!note.trim()}>加入意见</button></div></form>}
    {!!display.notes?.length&&<details className="auto-notes"><summary>用户意见 · {display.notes.length} 条</summary>{display.notes.map((n,i)=><p key={i}>{n.text}</p>)}</details>}
    </>:<div className="auto-empty"><div><span>A</span><i>⇄</i><span>B</span></div><h3>留出空间，让观点相遇</h3><p>开始后，这里会呈现两个席位真实返回的公开回复。每一步有来源，每次交接看得见。</p><small>还没有模型发言</small></div>}
    {notice&&<div className="auto-feedback" role="status">{notice}</div>}<textarea ref={copyArea} className="auto-copy-fallback" aria-label="复制备用文本" readOnly tabIndex="-1"/>
    <footer className="auto-observe-footer"><span className="auto-local-dot"/> 公开回复按原文展示 · 未完成内容不作为最终结果</footer>
   </section></div>
  </main>{settings&&<Settings profiles={profiles} onProfiles={updateProfile} onRemove={removeProfile} onClose={()=>setSettings(false)} locked={active}/>}
 </div>;
}
