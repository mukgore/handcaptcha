const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const html=fs.readFileSync(__dirname+'/index.html','utf8');
const source=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
function setup(){
  const elements={};let stopped=0,played=0,scheduled=0,requests=0;
  const stream={getTracks:()=>[{stop(){stopped++;}}]};
  const element=id=>elements[id]??={style:{},classList:{add(){}},getContext:()=>({}),addEventListener(){},
    readyState:0,videoWidth:640,videoHeight:480,play:async()=>{played++;}};
  const media=deferred();
  const context={document:{getElementById:element},performance:{now:()=>0},
    setTimeout(){return 1;},clearTimeout(){},requestAnimationFrame(){scheduled++;return 1;},
    navigator:{mediaDevices:{getUserMedia:()=>{requests++;return media.promise;}}},console};
  vm.createContext(context);vm.runInContext(source,context);
  return {context,elements,media,stream,run:code=>vm.runInContext(code,context),get stopped(){return stopped;},get played(){return played;},get scheduled(){return scheduled;},get requests(){return requests;}};
}
test('actual initCam stops a camera stream that arrives after abort without starting video',async()=>{
  const s=setup(),pending=s.run('initCam()');s.run('selectionRunAborted=true');s.media.resolve(s.stream);
  await pending;assert.equal(s.stopped,1);assert.equal(s.played,0);assert.equal(s.scheduled,0);
});
test('actual bootstrap cannot acquire a camera after model initialization finishes on an aborted page',async()=>{
  const s=setup(),model=deferred();let pools=0;
  s.context.model=model.promise;s.context.loadPools=()=>{pools++;};
  s.run('initMP=()=>model;loadPoolManifest=async()=>loadPools()');
  const pending=s.run('bootstrap()');s.run('selectionRunAborted=true');model.resolve();await pending;
  assert.equal(s.requests,0);assert.equal(pools,0);
});
test('actual camera loop cannot reschedule an in-flight inference after completion',async()=>{
  const s=setup(),frame=deferred();s.context.nextFrame=()=>frame.promise;
  s.elements.cameraVideo.readyState=2;s.run('hands={send:()=>nextFrame()}');
  const pending=s.run('initCam()');s.media.resolve(s.stream);await pending;
  s.run('selectionRunFinished=true');frame.resolve();await new Promise(setImmediate);
  assert.equal(s.scheduled,0);
});
