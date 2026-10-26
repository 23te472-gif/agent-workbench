import test from 'node:test';
import assert from 'node:assert/strict';
import {draftFromStyle,buildHumanStyle} from '../src/persona-editor.mjs';
import {customFromTraits} from '../src/style-catalog.mjs';
test('existing preset fills concrete role fields and yields editable bounded custom style',()=>{
 const draft=draftFromStyle({preset:'lele'});
 assert.equal(draft.name,'明快助手');assert.match(draft.rules,/答完就停/);
 const result=buildHumanStyle(draft);assert.equal(result.preset,'custom');assert.ok(result.text.length<=3000);
 assert.match(result.text,/礼貌和适度距离/);assert.match(result.text,/不会删除存储/);
});
test('custom free text is retained and oversized input is never silently truncated',()=>{
 const draft=draftFromStyle({preset:'custom',text:'保留我的原始设定'});
 assert.equal(draft.extra,'保留我的原始设定');
 assert.match(buildHumanStyle({...draft,name:'小禾',rules:'不确定时说明限制'}).text,/保留我的原始设定/);
 assert.throws(()=>buildHumanStyle({...draft,name:'小禾',rules:'规则',extra:'字'.repeat(3000)}),/3000/);
});
test('filled role can be reopened without losing fields or custom notes',()=>{
 const draft={...draftFromStyle({preset:'jingshui'}),name:'小禾',refusal:'不替我决定',extra:'附加的习惯'};
 const reopened=draftFromStyle(buildHumanStyle(draft));
 assert.equal(reopened.name,'小禾');assert.equal(reopened.refusal,'不替我决定');assert.equal(reopened.extra,'附加的习惯');
});
test('word-library additions survive reopening the human editor',()=>{
 const filled=buildHumanStyle(draftFromStyle({preset:'lele'}));
 const withTraits=customFromTraits(filled,[{dimension:'幽默',value:'冷幽默'}]);
 const reopened=draftFromStyle(withTraits);
 assert.match(reopened.extra,/幽默：冷幽默/);
 assert.match(buildHumanStyle(reopened).text,/幽默：冷幽默/);
});
