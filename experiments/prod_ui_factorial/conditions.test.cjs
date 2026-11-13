const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const api=require('./conditions.js');
test('all 64 combinations exist exactly once and each factor is balanced',()=>{
 const rows=api.order().map(api.condition);assert.equal(new Set(rows.map(r=>r.condition_id)).size,64);
 for(const factor of api.factors)assert.equal(rows.filter(r=>r[factor]).length,32);
 for(let a=0;a<6;a++)for(let b=a+1;b<6;b++)for(const x of [false,true])for(const y of [false,true])assert.equal(rows.filter(r=>r[api.factors[a]]===x&&r[api.factors[b]]===y).length,16);
 assert.equal(api.order()[0],0);assert.deepEqual(new Set(api.order().slice(1,7)),new Set([1,2,4,8,16,32]));
});
test('every combination has the same one-second gate wait and correct exposure curve',()=>{
 for(let n=0;n<64;n++){const c=api.condition(n);for(const [ms,expected] of [[0,1],[499,1],[500,1],[750,.5],[1000,0],[1001,0]])assert.equal(api.alpha(ms,c.reveal),c.reveal?expected:0);}
 assert.equal(api.common_prelude_ms,1000);
});
test('unknown configurations and invalid clocks cannot silently select a baseline',()=>{
 for(const n of [-1,64,1.5,'1',true,NaN])assert.throws(()=>api.condition(n));
 for(const search of ['?condition=64','?condition=NaN','?condition=01','?condition=-1'])assert.throws(()=>api.fromSearch(search));
 for(const value of [-1,NaN,Infinity,'1'])assert.throws(()=>api.alpha(value,true));
 for(let n=0;n<64;n++)assert.equal(api.fromSearch('?condition='+n).mask,n);
});
test('generated design agrees with the switchable implementation and private setup',()=>{
 const design=JSON.parse(fs.readFileSync(path.join(__dirname,'design.json'),'utf8'));
 assert.equal(design.conditions.length,64);assert.deepEqual(design.factors,api.factors);
 for(const row of design.conditions)assert.deepEqual(row,{...api.condition(row.mask)});
 const html=fs.readFileSync(path.join(__dirname,'run.html'),'utf8');
 assert.ok(html.includes("const UPLOAD_URL = '';"));assert.ok(!html.includes('<script src="https://'));
 assert.ok(!html.includes('\nbootstrap();'));assert.ok(html.includes('if(UI_FACTORS.selection)'));
});
test('production scoring, gate/recording body and original inline styles stay identical',()=>{
 const original=fs.readFileSync(path.join(__dirname,'../../hand_captcha_prod.html'),'utf8').replace(/\r\n/g,'\n');
 const generated=fs.readFileSync(path.join(__dirname,'run.html'),'utf8').replace(/\r\n/g,'\n');
 for(const [start,end] of [['function computeScores(){','function showResult(){'],['function onRes(r){','function showScr(id)']]){
   assert.ok(original.includes(start)&&original.includes(end));
   assert.equal(generated.slice(generated.indexOf(start),generated.indexOf(end)),original.slice(original.indexOf(start),original.indexOf(end)));
 }
 assert.equal(generated.match(/<style>([\s\S]*?)<\/style>/)[1],original.match(/<style>([\s\S]*?)<\/style>/)[1]);
});
