import {useLayoutEffect,useRef} from 'react';

// One keyboard owner at a time, including a dialog opened above another dialog.
const layers=[];
let previousOverflow='';
export default function useDialog(onClose,blocked=false){
 const ref=useRef(null),latest=useRef({onClose,blocked});
 latest.current={onClose,blocked};
 useLayoutEffect(()=>{
  const dialog=ref.current;if(!dialog)return;
  const opener=document.activeElement,layer={dialog};
  const items=()=>[...dialog.querySelectorAll('button,input,select,textarea,summary,[tabindex]')].filter(el=>!el.disabled&&el.tabIndex>=0&&el.getClientRects().length);
  const focusFirst=()=>{(items()[0]||dialog).focus({preventScroll:true});};
  const top=()=>layers.at(-1)===layer;
  if(!layers.length){previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';}
  layers.push(layer);
  dialog.tabIndex=-1;focusFirst();
  function keyboard(event){
   if(!top())return;
   if(event.key==='Escape'){
    event.preventDefault();event.stopImmediatePropagation();
    if(!event.isComposing&&!latest.current.blocked)latest.current.onClose();
   }
   if(event.key==='Tab'){
    const list=items(),first=list[0],last=list.at(-1);
    if(!first){event.preventDefault();dialog.focus();return;}
    if(!dialog.contains(document.activeElement)||(!event.shiftKey&&document.activeElement===last)||(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog))){
     event.preventDefault();(event.shiftKey?last:first).focus();
    }
   }
  }
  function focus(event){if(top()&&!dialog.contains(event.target))focusFirst();}
  document.addEventListener('keydown',keyboard,true);
  document.addEventListener('focusin',focus);
  return()=>{
   const wasTop=top();layers.splice(layers.indexOf(layer),1);
   document.removeEventListener('keydown',keyboard,true);document.removeEventListener('focusin',focus);
   if(!layers.length)document.body.style.overflow=previousOverflow;
   if(wasTop&&opener?.isConnected)opener.focus({preventScroll:true});
  };
 },[]);
 return ref;
}
