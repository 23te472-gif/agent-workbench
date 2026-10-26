import React,{useState} from 'react';
import {call} from './auto.jsx';
import useDialog from './use-dialog.js';
export default function StyleExport({chat,onClose,locked}){
 const [seat,setSeat]=useState('both'),[include,setInclude]=useState(true),[busy,setBusy]=useState(false),[status,setStatus]=useState(''),[error,setError]=useState('');
 const dialog=useDialog(onClose,busy);
 async function save(){if(busy||locked)return;setBusy(true);setError('');setStatus('');try{const value=await call('api_chat_export_save',{id:chat.id,seat,include_memory:include});setStatus(value.saved?'已导出风格包，可保存备份或用于后续数据整理。':'已取消保存');}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <div className="memory-overlay"><section ref={dialog} className="chat-delete-dialog style-export" role="dialog" aria-modal="true" aria-label="导出模型风格"><h2>把风格带走</h2><p>导出当前群聊保存的表达风格，以及现在的长期记忆。文件为可读 JSON，可附带记忆所标记的原话摘录，不包含模型连接配置、密钥或完整聊天记录。</p><label>导出成员<select aria-label="导出成员" value={seat} disabled={busy} onChange={e=>setSeat(e.target.value)}><option value="both">A 和 B</option><option value="A">仅 A</option><option value="B">仅 B</option></select></label><label className="export-memory"><input type="checkbox" checked={include} disabled={busy} onChange={e=>setInclude(e.target.checked)}/>包含长期记忆（所选席位及共享内容）</label><p>这是风格与记忆备份，不是训练完成的模型。文件可能包含你保存的个人资料，请自行决定分享范围。</p>{error&&<p className="auto-warning" role="alert">{error}</p>}{status&&<p role="status">{status}</p>}<div><button className="auto-button" disabled={busy} onClick={onClose}>关闭</button><button className="auto-button auto-primary" disabled={busy||locked} onClick={save}>{busy?'正在保存…':'选择位置并导出'}</button></div></section></div>;
}
