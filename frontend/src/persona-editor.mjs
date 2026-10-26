import {catalog} from './style-catalog.mjs';
export const roleFields=[
 ['relation','关系','如何称呼用户、距离与玩笑边界'],['want','想要','用行为说明动机，例如冷场时先接一句'],['fear','怕','哪些情况会改变表达'],['refusal','不肯','再熟也不做的事'],
 ['rules','规则','开场、应答、被反驳、出错、收尾时怎么做'],['fingerprint','语言指纹','句长、称呼、标点；口头禅最多 3 个并标密度'],['states','状态档','平日 / 兴致高 / 累了 / 被冒犯：各写触发与表现'],
 ['memory','记忆','偏好与约定如何引用；不改变实际存储'],['flaw','缺陷与代价','表达上的局限及补救方式，不故意说错事实'],['boundaries','边界','玩笑、决定权与信息完整性的界限'],['forbidden','禁用句','想避免的套话，不能妨碍必要的真实说明'],['tactics','对话习惯','赞同、反对、被夸、改口怎么说'],['extra','附加说明','已有自定义风格会保留在这里']
];
export const scenes={chat:'陪聊',work:'多席协作',creative:'角色创作',service:'服务问答'};
const sceneGuidance={chat:'优先自然接话和上下文，不机械列提纲。',work:'优先明确立场、事实和必要证据，不改变协作职责或交接上限。',creative:'在明确的虚构场景内表现语言与性格，区分故事和实际操作。',service:'优先清晰准确与必要前提，不编造办理进度或已完成操作。'};
const marker='<!-- agent-human-role:v1 -->';
export function draftFromStyle(style,defaultScene='chat'){
 const preset=catalog.presets.find(p=>p.id===style.preset),text=style.preset==='custom'?style.text||'':preset?.text||'';
 const draft=Object.fromEntries(roleFields.map(([id])=>[id,'']));
 Object.assign(draft,{name:preset?.name||'新角色',scene:scenes[defaultScene]?defaultScene:'chat'});
 if(style.preset==='custom'&&!text.startsWith(marker)){draft.extra=text;return draft;}
 draft.name=preset?.name||text.match(/^#\s+([^\n]+)/m)?.[1]?.trim()||'新角色';
 const labels=Object.fromEntries(roleFields.map(([id,label])=>[label,id]));
 for(const m of text.matchAll(/\*\*([^*]+)\*\*\s*([\s\S]*?)(?=\n\*\*[^*]+\*\*|$)/g)){
  if(labels[m[1]])draft[labels[m[1]]]=m[2].trim();
  if(m[1]==='场景')draft.scene=Object.keys(scenes).find(k=>scenes[k]===m[2].trim())||'chat';
  if(m[1]==='拟人表达约束'&&m[2].trim().startsWith(catalog.human_guidance)){
   const appended=m[2].trim().slice(catalog.human_guidance.length).trim();
   if(appended)draft.extra=[draft.extra,appended].filter(Boolean).join('\n');
  }
 }
 return draft;
}
export function buildHumanStyle(draft){
 if(!draft.name?.trim())throw Error('请填写角色名字。');
 if(!draft.rules?.trim()&&!draft.extra?.trim())throw Error('至少填写行为规则，或保留一段已有自定义设定。');
 const fields=roleFields.filter(([id])=>draft[id]?.trim()).map(([id,label])=>`**${label}**\n${draft[id].trim()}`);
 const text=[marker,'# '+draft.name.trim(),'**场景**\n'+(scenes[draft.scene]||scenes.chat),'**场景侧重**\n'+(sceneGuidance[draft.scene]||sceneGuidance.chat),...fields,'**拟人表达约束**\n'+catalog.human_guidance].join('\n\n');
 if(text.length>3000)throw Error(`生成后 ${text.length} 字，超过 3000 字，请精简后应用。`);
 return {preset:'custom',text};
}
