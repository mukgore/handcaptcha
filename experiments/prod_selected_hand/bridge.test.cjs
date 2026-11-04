const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const HandSelection=require('../hand_selection/selection.js');
const source=fs.readFileSync(__dirname+'/bridge.js','utf8');
function hand(x,y,size){return Array.from({length:21},(_,i)=>({x:x+(i%5)/4*size,y:y+Math.floor(i/5)/4*size,z:0}));}
function setup(){
  const elements={},timers=new Map(),listeners={},calls=[];let time=0,next=1,stopped=0,started=0,scored=0,reloaded=0;
  function element(id){return elements[id]??=( {textContent:'',className:'',addEventListener(t,f){this[t]=f;},appendChild(){},click(){this.click?.();}} );}
  const panel={appendChild(){}};
  const context={HandSelection,performance:{now:()=>time},
    document:{querySelector:()=>({closest:()=>panel}),createElement:()=>({}),getElementById:element},
    setTimeout:(f,ms)=>{const id=next++;timers.set(id,{f,ms});return id;},clearTimeout:id=>timers.delete(id),
    cancelAnimationFrame(){},stopGhostLoop(){},rv:{pause(){}},
    camStream:{getTracks:()=>[{stop(){stopped++;}}]},
    selectionRunAborted:false,selectionRunFinished:false,phase:'matching',matchHoldStart:null,
    handednessBuffer:[],selectedHand:'left',targetLm:{},keyframes:[1],curSegFrames:[1],segments:[1],
    animId:1,sessionStart:0,sessionLog:[],
    onRes:r=>calls.push(r),setS(){},startRealChallenge(){started++;},showResult(){scored++;},onTransitionMatched(){},
    addEventListener:(t,f)=>listeners[t]=f,location:{reload(){reloaded++;}},
    URL:{createObjectURL:()=>'',revokeObjectURL(){}},Blob:class{}};
  vm.createContext(context);vm.runInContext(source,context);
  const tick=(hands,labels,delta=33)=>{time+=delta;context.onRes({image:{},multiHandLandmarks:hands,multiHandedness:labels});};
  const select=()=>{for(let i=0;i<8;i++)tick([hand(.1,.1,.2)],[{label:'Left',score:.99}]);};
  return {context,calls,timers,elements,listeners,tick,select,get stopped(){return stopped;},get started(){return started;},get scored(){return scored;},get reloaded(){return reloaded;}};
}
test('selected points and corresponding handedness follow reordered detector results',()=>{
  const s=setup(),small=hand(.6,.5,.1),large=hand(.1,.1,.2);
  for(let i=0;i<8;i++)s.tick([small,large],[{label:'Right'},{label:'Left'}]);
  assert.equal(s.calls[6].multiHandLandmarks.length,0);
  assert.equal(s.calls[7].multiHandLandmarks[0][0].x,.1);
  assert.equal(s.calls[7].multiHandedness[0].label,'Left');
  s.tick([large,small],[{label:'Left'},{label:'Right'}]);
  assert.equal(s.calls.at(-1).multiHandedness[0].label,'Left');
});
test('loss aborts entire attempt and late sequence/result cannot resume it',()=>{
  const s=setup();s.select();s.context.phase='recording';s.tick([],[]);
  assert.equal(s.context.selectionRunAborted,true);assert.equal(s.context.phase,'aborted');
  assert.equal(s.context.selectedHand,null);assert.equal(s.context.segments.length,0);
  assert.equal(s.context.sessionLog.at(-1).detected,false);assert.equal(s.stopped,1);
  const count=s.calls.length;s.select();assert.equal(s.calls.length,count);
  s.context.startRealChallenge();s.context.showResult();assert.equal(s.started,0);assert.equal(s.scored,0);
  s.elements.selectionRestart.click();assert.equal(s.reloaded,1);
});
test('unobserved callback gap resets hold before forwarding the same selected hand',()=>{
  const s=setup();s.select();s.context.matchHoldStart=100;
  s.tick([hand(.1,.1,.2)],[{label:'Left'}],200);
  assert.equal(s.context.matchHoldStart,null);assert.equal(s.context.selectionRunAborted,false);
});
test('long tracking gap stops instead of silently preserving hand identity',()=>{
  const s=setup();s.select();s.tick([hand(.1,.1,.2)],[{label:'Left'}],501);
  assert.equal(s.context.selectionRunAborted,true);assert.equal(s.stopped,1);
});
test('trial deadline and page exit stop the active attempt',()=>{
  const s=setup();s.select();[...s.timers.values()].find(t=>t.ms===60000).f();
  assert.equal(s.context.selectionRunAborted,true);assert.equal(s.stopped,1);
  const second=setup();second.select();second.listeners.pagehide();assert.equal(second.stopped,1);
});
test('completion runs original scoring once and blocks subsequent callbacks',()=>{
  const s=setup();s.select();s.context.showResult();s.context.showResult();
  assert.equal(s.scored,1);assert.equal(s.context.selectionRunFinished,true);
  assert.equal(s.context.selectionRunAborted,false);
  const count=s.calls.length;s.select();assert.equal(s.calls.length,count);
});
