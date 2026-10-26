import test from 'node:test';
import assert from 'node:assert/strict';
import {generationPrompt} from '../src/handoff-model.mjs';

const session={id:'demo',status:'completed',task:'制作一份10页的人工智能演示稿',notes:[{text:'面向大学生，加入案例'}],roles:{A:{api_key:'SECRET',base_url:'PRIVATE-URL'}},instructions:'PRIVATE-SYSTEM',steps:[
 {seat:'B',stage:'审查',state:'completed',content:'旧的审查意见'},
 {seat:'B',stage:'审查',state:'completed',content:'最新审查：避免夸大技术能力'},
 {seat:'A',stage:'修订',state:'completed',content:'最终方案：先介绍概念，再讲案例。'},
 {seat:'A',stage:'修订',state:'cancelled',content:'不完整内容'}]};
test('handoff preserves task, user notes, latest complete review and revision without private configuration',()=>{
 const text=generationPrompt(session);
 for(const piece of [session.task,session.notes[0].text,'最新审查：避免夸大技术能力','最终方案：先介绍概念，再讲案例。'])assert.ok(text.includes(piece));
 for(const omitted of ['SECRET','PRIVATE-URL','PRIVATE-SYSTEM','旧的审查意见','不完整内容'])assert.ok(!text.includes(omitted));
 assert.match(text,/未附带/);assert.match(text,/不要伪造/);assert.match(text,/不代表.*一致/);
});
test('failed, interrupted and incomplete sessions do not produce a final handoff',()=>{
 for(const status of ['running','failed','cancelled','interrupted'])assert.equal(generationPrompt({...session,status}),'');
 assert.equal(generationPrompt({...session,steps:[]}),'');assert.equal(generationPrompt(null),'');
});
test('output formats give concrete file or text requirements, unknown format falls back to original task',()=>{
 assert.match(generationPrompt(session,'ppt'),/\.pptx/);
 assert.match(generationPrompt(session,'ppt'),/逐页/);
 assert.match(generationPrompt(session,'word'),/\.docx/);
 assert.match(generationPrompt(session,'text'),/完整正文/);
 assert.match(generationPrompt(session,'unexpected'),/原任务/);
});
test('no-review and no-note historical sessions remain usable',()=>{
 const text=generationPrompt({...session,notes:[],steps:[session.steps[2]]},'text');
 assert.match(text,/完整正文/);assert.ok(!text.includes('undefined'));assert.ok(text.includes(session.task));
});
