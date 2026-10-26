import test from 'node:test';
import assert from 'node:assert/strict';
import {validatePlan,sameModel,canRetry,finalReply,stepLabel,buildProfilePayload} from '../src/auto-model.mjs';
const profiles=[{id:'p',base_url:'https://api.deepseek.com',model:'deepseek-flash',has_key:true}];
const plan={task:'检查一个想法',primary_id:'p',reviewer_id:'p',rounds:1,max_tokens:1024,context_count:6,persona:'conductor'};
test('plan requires both configured keys and integer bounded budgets',()=>{
 assert.equal(validatePlan(plan,profiles),'');
 assert.match(validatePlan({...plan,rounds:4},profiles),/轮数/);
 assert.match(validatePlan({...plan,max_tokens:4097},profiles),/Token/);
 assert.match(validatePlan({...plan,context_count:-1},profiles),/上下文/);
 assert.match(validatePlan({...plan,rounds:1.5},profiles),/轮数/);
 assert.match(validatePlan({...plan,task:' '},profiles),/任务/);
 assert.match(validatePlan(plan,[{...profiles[0],has_key:false}]),/密钥/);
});
test('equivalent endpoint and model makes role identity explicit',()=>{
 assert.equal(sameModel(profiles[0],{...profiles[0],id:'other',base_url:'https://api.deepseek.com/'}),true);
 assert.equal(sameModel(profiles[0],{...profiles[0],model:'different'}),false);
});
test('retry retains original call and time budgets and requires recoverable state',()=>{
 const s={status:'failed',call_count:2,call_limit:3,seconds_left:100};
 assert.equal(canRetry(s),true);
 for(const change of [{call_count:3},{seconds_left:0},{status:'completed'},{status:'running'}])assert.equal(canRetry({...s,...change}),false);
 assert.equal(canRetry({...s,status:'interrupted'}),true);
});
test('partial content cannot become a final result',()=>{
 const steps=[{stage:'修订',state:'completed',content:'完整修订'},{stage:'修订',state:'cancelled',content:'半段'}];
 assert.equal(finalReply({status:'cancelled',steps}),null);
 assert.equal(finalReply({status:'completed',steps}),steps[0]);
 assert.match(stepLabel(steps[1]),/未完成/);
});
test('profile writes never refill or retain an empty password in payload',()=>{
 const draft={id:'p',name:'服务',kind:'deepseek',base_url:'https://api.deepseek.com',model:'deepseek-flash',api_key:''};
 assert.equal(Object.hasOwn(buildProfilePayload(draft),'api_key'),false);
 assert.equal(buildProfilePayload({...draft,api_key:' entered '}).api_key,'entered');
});
test('local Codex needs no API key and stored profiles contain no host path',()=>{
 const local={id:'c',kind:'codex_local',has_key:false,base_url:'codex://local',model:'gpt-6.1-sol'};
 assert.equal(validatePlan({...plan,primary_id:'c'},[...profiles,local]),'');
 const payload=buildProfilePayload({...local,name:'本机 Codex',base_url:'C:/someone/codex.exe',api_key:'must-not-forward'});
 assert.equal(payload.base_url,'codex://local');
 assert.equal(Object.hasOwn(payload,'api_key'),false);
});
test('each role can choose a separate custom style with bounded nonempty text',()=>{
 const seat_styles={A:{preset:'custom',text:'温和解释'},B:{preset:'qinghe',text:''}};
 assert.equal(validatePlan({...plan,seat_styles},profiles),'');
 assert.match(validatePlan({...plan,seat_styles:{...seat_styles,A:{preset:'custom',text:' '}}},profiles),/A.*风格/);
 assert.match(validatePlan({...plan,seat_styles:{...seat_styles,B:{preset:'custom',text:'字'.repeat(3001)}}},profiles),/B.*风格/);
});
test('request budget supports thirty and limits planned rounds and retries',()=>{
 assert.equal(validatePlan({...plan,rounds:10,call_limit:30},profiles),'');
 assert.match(validatePlan({...plan,rounds:3,call_limit:6},profiles),/上限/);
 assert.match(validatePlan({...plan,call_limit:31},profiles),/上限/);
 assert.equal(canRetry({status:'failed',call_count:12,call_limit:15,seconds_left:100}),true);
 assert.equal(canRetry({status:'failed',call_count:15,call_limit:15,seconds_left:100}),false);
});
