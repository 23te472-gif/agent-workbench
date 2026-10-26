import test from 'node:test';
import assert from 'node:assert/strict';
import {preferenceSegments,preferencesByMessage} from '../src/chat-markers.mjs';
test('marks actual source excerpts without changing text, including overlaps',()=>{
 const parts=preferenceSegments('这句很自然，也很简洁。',[{text:'喜欢自然',source:{excerpt:'很自然'}},{text:'喜欢简洁',source:{excerpt:'自然，也很简洁'}}]);
 assert.equal(parts.map(p=>p.text).join(''),'这句很自然，也很简洁。');
 assert.ok(parts.some(p=>p.text==='自然'&&p.labels.length===2));
 assert.ok(parts.some(p=>p.text==='这句'&&p.labels.length===0));
});
test('deleted or legacy memories do not leave fabricated highlights',()=>{
 assert.deepEqual(preferenceSegments('hello',[{text:'legacy'}]),[{text:'hello',labels:[]}]);
 assert.deepEqual(preferenceSegments('hello',[{text:'missing',source:{excerpt:'absent'}}]),[{text:'hello',labels:[]}]);
});
test('legacy preferences without a source are safe before any chat is selected',()=>{
 const rows=[{kind:'preference',text:'legacy preference'},{kind:'preference',source:{chat_id:'room',message_id:'message',excerpt:'hello'},text:'new preference'}];
 assert.deepEqual(preferencesByMessage(rows,null),{});
 assert.deepEqual(preferencesByMessage(rows,'other'),{});
 assert.equal(preferencesByMessage(rows,'room').message[0].text,'new preference');
});
