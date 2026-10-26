export function preferencesByMessage(memories,chatId){
 const result={};
 if(!chatId)return result;
 for(const row of memories||[]){
  const source=row?.source;
  if(row?.kind==='preference'&&source&&source.chat_id===chatId&&typeof source.message_id==='string')
   (result[source.message_id]??=[]).push(row);
 }
 return result;
}
export function preferenceSegments(text,memories=[]){
 const ranges=memories.flatMap(m=>{const quote=m.source?.excerpt;if(!quote)return [];const start=text.indexOf(quote);return start<0?[]:[{start,end:start+quote.length,label:m.text}];});
 const points=[...new Set([0,text.length,...ranges.flatMap(r=>[r.start,r.end])])].sort((a,b)=>a-b);
 return points.slice(0,-1).map((start,i)=>({text:text.slice(start,points[i+1]),labels:ranges.filter(r=>r.start<=start&&r.end>=points[i+1]).map(r=>r.label)}));
}
