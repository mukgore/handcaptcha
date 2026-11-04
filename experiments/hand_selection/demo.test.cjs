const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {HandSelector}=require('./selection.js');
const {SessionLog}=require('./session_log.js');
function setup(options={}){
  const draws=[],listeners={},elements={},tracks=[],downloads=[],blobs=[];
  function element(id){return elements[id]??={id,disabled:false,value:'',checked:false,hidden:false,
    width:640,height:480,readyState:2,videoWidth:640,videoHeight:480,textContent:'',files:[],playCount:0,
    async play(){this.playCount++;this.paused=false;},pause(){this.paused=true;},
    getContext:()=>({canvas:element(id),save(){},restore(){},translate(){},scale(){},clearRect(){},strokeRect(){},
      drawImage(image,...args){draws.push({id,image,args});}})};}
  element('mode').value='overlay';element('opacity').value='.4';element('guideHand').value='right';
  element('media').files=[{name:'private-name.mp4'}];
  let detector;
  class Hands{constructor(){detector=this;}setOptions(x){this.options=x;}onResults(f){this.callback=f;}
    async initialize(){if(options.initialize)await options.initialize();}async send(input){this.input=input;}}
  const getUserMedia=async()=>{
    const track={stopped:false,stop(){this.stopped=true;}};tracks.push(track);
    const stream={getTracks:()=>[track]};
    if(options.acquire)await options.acquire();return stream;
  };
  const sandbox={HandSelection:{HandSelector},HandGuidance:{SessionLog},Hands,Blob,
    document:{getElementById:element,createElement:()=>({click(){downloads.push(this.download);}}),body:{classList:{toggle(){}}}},
    navigator:{mediaDevices:{getUserMedia}},URL:{createObjectURL:b=>{blobs.push(b);return 'blob:local';},revokeObjectURL(){}},
    requestAnimationFrame:()=>1,cancelAnimationFrame(){},window:{addEventListener:(name,fn)=>listeners[name]=fn}};
  vm.runInNewContext(fs.readFileSync(__dirname+'/demo.js','utf8'),sandbox);
  return {elements,draws,tracks,listeners,downloads,blobs,get detector(){return detector;}};
}
function hand(){return Array.from({length:21},(_,i)=>({x:.1+(i%5)*.03,y:.1+Math.floor(i/5)*.03,z:0}));}
function stabilize(t){for(let i=0;i<8;i++)t.detector.callback({image:t.elements.cameraSource,multiHandLandmarks:[hand()]});}
async function begin(t){stabilize(t);t.elements.palmConfirmed.checked=true;t.elements.palmConfirmed.onchange();await t.elements.begin.onclick();}

test('preparation detects original camera but never plays or overlays the problem',async()=>{
  const t=setup();await t.elements.start.onclick();stabilize(t);
  assert.equal(t.detector.options.maxNumHands,2);
  assert.equal(t.detector.input.image,t.elements.cameraSource);
  assert.equal(t.elements.referenceSource.playCount,0);
  assert.ok(!t.draws.some(x=>x.image===t.elements.referenceSource));
  assert.equal(t.elements.begin.disabled,true);assert.match(t.elements.status.textContent,/손금/);
});
test('begin requires both a stable hand and an explicit palm self-report',async()=>{
  const t=setup();await t.elements.start.onclick();
  t.elements.palmConfirmed.checked=true;t.elements.palmConfirmed.onchange();
  await t.elements.begin.onclick();assert.equal(t.elements.referenceSource.playCount,0);
  stabilize(t);t.elements.palmConfirmed.checked=false;t.elements.palmConfirmed.onchange();
  await t.elements.begin.onclick();assert.equal(t.elements.referenceSource.playCount,0);
  t.elements.palmConfirmed.checked=true;t.elements.palmConfirmed.onchange();await t.elements.begin.onclick();
  assert.equal(t.elements.referenceSource.playCount,1);assert.equal(t.elements.preparation.hidden,true);
  t.detector.callback({image:t.elements.cameraSource,multiHandLandmarks:[hand()]});
  assert.ok(t.draws.some(x=>x.id==='camera'&&x.image===t.elements.referenceSource));
});
test('loss stops media and camera; replacement cannot resume until full preparation',async()=>{
  const t=setup();await t.elements.start.onclick();await begin(t);
  t.detector.callback({image:t.elements.cameraSource,multiHandLandmarks:[]});
  assert.ok(t.tracks[0].stopped);assert.ok(t.elements.referenceSource.paused);
  const status=t.elements.status.textContent;t.detector.callback({image:t.elements.cameraSource,multiHandLandmarks:[hand()]});
  assert.equal(t.elements.status.textContent,status);t.elements.reset.onclick();
  assert.equal(t.elements.palmConfirmed.checked,false);assert.equal(t.elements.begin.disabled,true);
  await t.elements.start.onclick();assert.equal(t.elements.referenceSource.playCount,1);
});
test('page exit during pending camera acquisition stops the late stream',async()=>{
  let resolve;const acquired=new Promise(r=>resolve=r);const t=setup({acquire:()=>acquired});
  const pending=t.elements.start.onclick();await new Promise(r=>setImmediate(r));
  t.listeners.pagehide();resolve();await pending;
  assert.equal(t.tracks[0].stopped,true);assert.equal(t.elements.cameraSource.srcObject,null);
});
test('reset during model initialization cannot start an obsolete camera run',async()=>{
  let resolve;const initialized=new Promise(r=>resolve=r);const t=setup({initialize:()=>initialized});
  const first=t.elements.start.onclick();t.elements.reset.onclick();const second=t.elements.start.onclick();
  resolve();await Promise.all([first,second]);assert.equal(t.tracks.length,1);
  assert.equal(t.tracks[0].stopped,false);t.listeners.pagehide();assert.equal(t.tracks[0].stopped,true);
});
test('finish exports only allowed local events and does not claim automatic palm detection',async()=>{
  const t=setup();t.elements.media.onchange();await t.elements.start.onclick();await begin(t);
  t.elements.finish.onclick();assert.equal(t.tracks[0].stopped,true);t.elements.exportLog.onclick();
  const report=JSON.parse(await t.blobs.at(-1).text());
  assert.equal(report.palm_assessment,'user_self_report_only');
  assert.equal(report.endpoint,'unscored_local_demo');
  assert.ok(report.events.some(x=>x.event==='palm_self_report'));
  assert.ok(report.events.some(x=>x.event==='attempt_finished'));
  const text=JSON.stringify(report);for(const secret of ['private-name','landmarks','participant_id'])assert.ok(!text.includes(secret));
  assert.deepEqual(t.downloads,['hand-guidance-local.json']);
});
test('reselection starts a new numbered trial without merging attempt events',async()=>{
  const t=setup();await t.elements.start.onclick();await begin(t);t.elements.reset.onclick();
  await t.elements.start.onclick();await begin(t);t.elements.finish.onclick();t.elements.exportLog.onclick();
  const report=JSON.parse(await t.blobs.at(-1).text());
  assert.deepEqual(report.events.filter(e=>e.event==='attempt_started').map(e=>e.trial_index),[1,2]);
  assert.equal(report.events.find(e=>e.event==='aborted').trial_index,1);
  assert.equal(report.events.find(e=>e.event==='attempt_finished').trial_index,2);
});
