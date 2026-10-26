import catalog from '../../persona_catalog.json' with {type:'json'};
export {catalog};
export function toggleTrait(selected,dimension,value){
 if(selected.some(t=>t.dimension===dimension&&t.value===value))return selected.filter(t=>t.dimension!==dimension);
 const next=selected.filter(t=>t.dimension!==dimension);
 if(next.length>=4)throw Error('一次最多选择 4 个维度，先取消一个再试。');
 return [...next,{dimension,value}];
}
export function customFromTraits(style,traits){
 if(!traits.length)throw Error('请先选择性格词。');
 const preset=catalog.presets.find(p=>p.id===style.preset);
 const prompt=preset?.text.match(/```\s*([\s\S]*?)```/)?.[1]?.trim();
 const base=style.preset==='custom'?style.text.trim():prompt||preset?.text||'';
 const text=[base,'补充性格维度：'+traits.map(t=>`${t.dimension}：${t.value}`).join('；')+'。','自然聊天，不机械重复口头禅；只调整表达，不虚构事实或替用户做决定。'].filter(Boolean).join('\n');
 if(text.length>3000)throw Error('加入后超过 3000 字，请先精简自定义说明。');
 return {preset:'custom',text};
}
