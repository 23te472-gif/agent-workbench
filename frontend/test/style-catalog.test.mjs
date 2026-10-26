import test from 'node:test';
import assert from 'node:assert/strict';
import {catalog,toggleTrait,customFromTraits} from '../src/style-catalog.mjs';
test('sample personas resolve into editable style and traits remain bounded',()=>{
 assert.equal(catalog.presets.length,2);
 assert.match(customFromTraits({preset:'lele'},[{dimension:'语气',value:'温和'}]).text,/明快助手/);
 let p=[];for(const d of ['a','b','c','d'])p=toggleTrait(p,d,'x');
 assert.throws(()=>toggleTrait(p,'e','x'),/4/);
 assert.throws(()=>customFromTraits({preset:'custom',text:'字'.repeat(3000)},[{dimension:'a',value:'x'}]),/3000/);
});
