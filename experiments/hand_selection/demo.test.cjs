const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {HandSelector}=require('./selection.js');
function setup(){
  const draws=[],listeners={},elements={},tracks=[{stopped:false,stop(){this.stopped=true;}}];
  function element(id){return elements[id]??=(Object.assign({id,disabled:false,value:'',checked:false,
    width:640,height:480,readyState:2,videoWidth:640,videoHeight:480,textContent:'',files:[],
    play:async()=>{},pause(){this.paused=true;},getContext:()=>({canvas:element(id),
      save(){},restore(){},translate(){},scale(){},clearRect(){},strokeRect(){},
      drawImage(image,...args){draws.push({id,image,args});}})},{}));}
  element('mode').value='overlay';element('opacity').value='.4';element('media').files=[{}];
  let detector,reloaded=false;
  class Hands{constructor(){detector=this;}setOptions(x){this.options=x;}onResults(f){this.callback=f;}
    async initialize(){}async send(input){this.input=input;}}
  const sandbox={HandSelection:{HandSelector},Hands,document:{getElementById:element,body:{classList:{toggle(){}}}},
    navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>tracks})}},
    URL:{createObjectURL:()=> 'blob:local-test',revokeObjectURL(){}},
    requestAnimationFrame:()=>1,cancelAnimationFrame(){},location:{reload(){reloaded=true;}},
    window:{addEventListener:(name,fn)=>listeners[name]=fn}};
  vm.runInNewContext(fs.readFileSync(__dirname+'/demo.js','utf8'),sandbox);
  return {elements,draws,tracks,listeners,get detector(){return detector;},get reloaded(){return reloaded;}};
}
function hand(){return Array.from({length:21},(_,i)=>({x:.1+(i%5)*.03,y:.1+Math.floor(i/5)*.03,z:0}));}
test('two-hand detector gets original camera; compositing stays in display canvases',async()=>{
  const t=setup();t.elements.media.onchange();t.elements.referenceSource.onloadeddata();
  await t.elements.start.onclick();
  assert.equal(t.detector.options.maxNumHands,2);
  assert.equal(t.detector.input.image,t.elements.cameraSource);
  for(let i=0;i<8;i++)t.detector.callback({image:t.elements.cameraSource,multiHandLandmarks:[hand()]});
  assert.match(t.elements.status.textContent,/초록/);
  assert.ok(t.draws.some(x=>x.id==='camera'&&x.image===t.elements.referenceSource));
  assert.ok(t.elements.mode.disabled);
});
test('loss stops media and camera, rejects replacement, and requires a full restart',async()=>{
  const t=setup();await t.elements.start.onclick();
  for(let i=0;i<8;i++)t.detector.callback({image:t.elements.cameraSource,multiHandLandmarks:[hand()]});
  t.detector.callback({image:t.elements.cameraSource,multiHandLandmarks:[]});
  assert.ok(t.tracks[0].stopped);assert.ok(t.elements.referenceSource.paused);
  const status=t.elements.status.textContent;
  t.detector.callback({image:t.elements.cameraSource,multiHandLandmarks:[hand()]});
  assert.equal(t.elements.status.textContent,status);
  t.elements.reset.onclick();assert.ok(t.reloaded);
});
test('leaving page releases camera and local media resources',async()=>{
  const t=setup();await t.elements.start.onclick();t.listeners.pagehide();
  assert.ok(t.tracks[0].stopped);assert.equal(t.elements.cameraSource.srcObject,null);
});
