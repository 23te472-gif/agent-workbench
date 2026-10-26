export function inputHeightFor(start,delta,viewportHeight){
 const max=Math.max(44,Math.min(220,Math.round(viewportHeight*.28)));
 return Math.min(max,Math.max(44,Math.round(start-delta)));
}
