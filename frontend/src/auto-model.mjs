export const isActive=s=>s?.status==='running'||s?.status==='stopping';
export const statusLabel=s=>({running:'协作中',stopping:'正在停止',completed:'已完成',failed:'已停止 · 出错',cancelled:'已取消',interrupted:'已中断',corrupt:'记录损坏 · 原文件保留'}[s]||'等待开始');
export function validatePlan(p,profiles){
 if(!p.task.trim())return '请先填写任务。';
 for(const [key,min,max,label] of [['rounds',1,10,'轮数'],['max_tokens',128,4096,'单次 Token 上限'],['context_count',0,20,'上下文条数']]){
  if(!Number.isInteger(Number(p[key]))||Number(p[key])<min||Number(p[key])>max||p[key]==='')return `${label}需为 ${min}–${max} 的整数。`;
 }
 const cap=Number(p.call_limit??9);
 if(!Number.isInteger(cap)||cap<3||cap>30)return '请求上限需为 3–30 的整数。';
 if(Number(p.rounds)*3>cap)return '当前轮数所需请求超过上限，请提高上限或减少轮数。';
 for(const seat of ['A','B']){
  const style=p.seat_styles?.[seat];if(!style)continue;
  if(!['conductor','qinghe','lele','jingshui','custom'].includes(style.preset))return `${seat} 席表达风格无效。`;
  if(typeof style.text!=='string'||style.text.length>3000||(style.preset==='custom'&&!style.text.trim()))return `${seat} 席自定义风格需为 1–3000 字。`;
 }
 if(![p.primary_id,p.reviewer_id].every(id=>{const row=profiles.find(x=>x.id===id);return row?.kind==='codex_local'||row?.has_key;}))return '请为两个角色选择本机 Codex 或已配置密钥的 API 模型。';
 return '';
}
export function sameModel(a,b){return !!a&&!!b&&a.base_url.replace(/\/+$/,'')===b.base_url.replace(/\/+$/,'')&&a.model===b.model;}
export function canRetry(s){return !!s&&['failed','interrupted'].includes(s.status)&&s.call_count<Math.min(s.call_limit,30)&&s.seconds_left>0;}
export function finalReply(s){return s?.status==='completed'?[...(s.steps||[])].reverse().find(x=>x.stage==='修订'&&x.state==='completed'&&x.content):null;}
export function stepLabel(s){return ({running:'正在接收 · 未完成',completed:'完整回复',failed:'失败 · 未完成内容',cancelled:'已中断 · 未完成内容'}[s.state]||'未完成内容');}
export const styleLabel=p=>({conductor:'总谱',qinghe:'清和',lele:'明快助手',jingshui:'沉稳助手',custom:'自定义'}[p]||'总谱');
export function buildProfilePayload(d){const local=d.kind==='codex_local',p={name:d.name.trim(),kind:d.kind,base_url:local?'codex://local':d.base_url.trim(),model:d.model.trim()};if(d.id)p.id=d.id;if(!local&&d.api_key.trim())p.api_key=d.api_key.trim();return p;}
