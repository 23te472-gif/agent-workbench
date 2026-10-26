import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import './base.css';
import AutoWorkspace from './auto.jsx';
import GroupChat from './group-chat.jsx';
import ThemePicker from './theme-picker.jsx';
import './theme.css';
import './finish.css';
function App(){const [mode,setMode]=useState('work');return <><nav className="mode-switch" aria-label="工作台模式"><button className={mode==='work'?'selected':''} onClick={()=>setMode('work')}>协作工作</button><button className={mode==='chat'?'selected':''} onClick={()=>setMode('chat')}>实验群聊 <small>LAB</small></button><ThemePicker/></nav>{mode==='work'?<AutoWorkspace/>:<GroupChat/>}</>;}
createRoot(document.getElementById('root')).render(<App/>);
