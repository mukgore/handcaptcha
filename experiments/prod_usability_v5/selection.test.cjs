const {test}=require('node:test'),assert=require('node:assert/strict');
const {Selector,candidate}=require('./selector.js');
function hand(x=.2,y=.2,w=.25,h=.35){return Array.from({length:21},(_,i)=>({x:x+(i%5)/4*w,y:y+Math.floor(i/5)/4*h,z:i*.001}));}
function acquire(s,h,t=0){let r;for(let n=0;n<=4;n++)r=s.update(h,t+n*100);return r;}
test('reject invalid, nonfinite, off-frame and tiny hands',()=>{
  assert.equal(candidate(hand().slice(1),0),null);
  const bad=hand();bad[0].z=NaN;assert.equal(candidate(bad,0),null);
  assert.equal(candidate(hand(.95),0),null);
  assert.equal(acquire(new Selector(),[hand(.2,.2,.05,.1)]).ready,false);
});
test('largest valid hand stabilizes by elapsed time, not array index or labels',()=>{
  const s=new Selector(),a=hand(),b=hand(.65,.2,.1,.2);
  assert.equal(acquire(s,[b,a]).hand.index,1);
  const next=s.update([a,b],500);assert.equal(next.hand.index,0);assert.equal(next.ready,true);
});
test('ties do not acquire and long callback gaps cannot accumulate stability',()=>{
  const s=new Selector();assert.equal(acquire(s,[hand(),hand(.6)]).ready,false);
  const slow=new Selector();for(let t=0;t<2000;t+=300)assert.equal(slow.update([hand()],t).ready,false);
});
test('a larger distractor never replaces the selected hand',()=>{
  const s=new Selector(),a=hand();acquire(s,[a]);
  const r=s.update([hand(.6,.1,.35,.6),a],500);assert.equal(r.hand.points,a);assert.equal(r.hand.index,1);
});
test('a brief crossing skips ambiguous frames and resumes the same hand',()=>{
  const s=new Selector(),a=hand();acquire(s,[a]);
  const ambiguous=s.update([a,hand(.205)],500);
  assert.equal(ambiguous.reason,'ambiguous_crossing');
  assert.equal(ambiguous.hand,null);
  assert.equal(s.update([a],600).hand.points,a);
});
test('persistent crossing times out without handing over the attempt',()=>{
  const s=new Selector(),a=hand(),b=hand(.205);acquire(s,[a]);
  assert.equal(s.update([a,b],500).hand,null);
  assert.equal(s.update([b,a],1800).hand,null);
  assert.equal(s.update([b,a],2000).state,'lost');
  assert.equal(s.update([a],2100).ready,false);
});
test('curling fingers can shrink the bounding box without losing a steady palm',()=>{
  const palmPoints=new Set([0,5,9,13,17]);
  const open=hand(.25,.25,.25,.45).map((p,i)=>palmPoints.has(i)?{...p,x:.29+i%5*.02,y:.50+i%4*.02}:p);
  const closed=open.map((p,i)=>palmPoints.has(i)?p:{...p,x:.28+i%5*.024,y:.46+i%4*.048});
  assert.ok(candidate(open,0).area/candidate(closed,0).area>2.4);
  assert.ok(candidate(closed,0).area<.024);
  const s=new Selector();assert.ok(acquire(s,[open]).ready);
  assert.equal(s.update([closed],500).hand.points,closed);
  assert.equal(s.update([closed],2050).state,'lost'); // a long inference gap still resets
});
test('short loss returns null observations, reacquires same geometry; long loss invalidates',()=>{
  const s=new Selector(),a=hand();acquire(s,[a]);
  const miss=s.update([],500);assert.equal(miss.ready,false);assert.equal(miss.hand,null);
  assert.equal(s.update([a],600).ready,true);
  assert.equal(s.update([a],2200).state,'lost');
});
test('entry/exit hysteresis tolerates size boundary and rejects sustained small hand',()=>{
  const s=new Selector();acquire(s,[hand(.2,.2,.2,.2)]);
  assert.equal(s.update([hand(.2,.2,.18,.18)],500).ready,true);
  assert.equal(s.update([hand(.2,.2,.14,.14)],600).ready,false);
  assert.equal(s.update([hand(.2,.2,.14,.14)],2100).state,'lost');
});
test('production scoring functions and constants are byte-identical in generated copy',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const base=fs.readFileSync(path.join(__dirname,'../../hand_captcha_prod.html'),'utf8');
  const copy=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
  for(const marker of ['const MATCH_ANGLE_THRESH','const MATCH_HOLD_MS','const THRESHOLD','const W2','const MX']){
    const line=base.split('\n').find(x=>x.startsWith(marker));assert.ok(copy.includes(line));
  }
  const metrics=s=>s.slice(s.indexOf('function pp(f)'),s.indexOf('function showResult()'));
  assert.equal(metrics(base),metrics(copy));
  // Fixed, nontrivial input through the original and generated scoring paths.
  const vm=require('node:vm');
  const evaluate=s=>{
    const context={};vm.createContext(context);
    const config=s.slice(s.indexOf('const W2'),s.indexOf('const LN'));
    const frames=Array.from({length:12},(_,t)=>hand().map((p,i)=>[p.x+Math.sin(i+t)*.01,p.y+Math.cos(i-t)*.02]));
    const angle=s.slice(s.indexOf('function ang('),s.indexOf('function ppSingle('));
    vm.runInContext(config+'\n'+angle+'\n'+metrics(s)+`\nvar keyframes=[{clip:{clip_id:'a'},allBaseLm:${JSON.stringify(frames)},frameIdx:0},{clip:{clip_id:'a'},frameIdx:11}];var segments=[{fromKf:0,toKf:1,frames:${JSON.stringify(frames.map((lm,t)=>({lm:t===5?null:lm,t})))} }];var result=computeScores();`,context);
    return JSON.parse(JSON.stringify(context.result));
  };
  assert.deepEqual(evaluate(base),evaluate(copy));
});
