import test from 'node:test';
import assert from 'node:assert/strict';
import {inputHeightFor} from '../src/chat-layout.mjs';
test('dragging down gives space to messages and respects viewport bounds',()=>{
 assert.equal(inputHeightFor(100,50,800),50);
 assert.equal(inputHeightFor(100,2000,800),44);
 assert.equal(inputHeightFor(100,-2000,800),220);
 assert.equal(inputHeightFor(100,-2000,500),140);
});
