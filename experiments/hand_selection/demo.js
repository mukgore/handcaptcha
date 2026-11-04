'use strict';
const $=id=>document.getElementById(id);
const selector=new HandSelection.HandSelector(),eventLog=new HandGuidance.SessionLog();
const camera=$('camera'),reference=$('reference'),ctx=camera.getContext('2d'),ref=reference.getContext('2d');
const source=$('cameraSource'),clip=$('referenceSource');
let stream=null,detector=null,detectorInitialization=null,frameId=null,active=false,objectUrl=null,run=0;
let phase='idle',selected=false,lastChoice=null,starting=false,trialIndex=0;
function logEvent(event,fields={}){eventLog.record(event,{...(trialIndex?{trial_index:trialIndex}:{}),...fields});}
function status(message){if($('status').textContent!==message)$('status').textContent=message;}
function config(){return {ui_condition:$('mode').value,guide_hand:$('guideHand').value,
  mirror:$('mirror').checked,opacity:Number($('opacity').value)};}
function controls(){
  for(const id of ['mode','opacity','mirror','media','start','guideHand'])$(id).disabled=active;
  $('start').disabled=active||clip.readyState<2;
  $('begin').disabled=phase!=='preparing'||!selected||!$('palmConfirmed').checked||starting;
  $('palmConfirmed').disabled=phase!=='preparing';
  $('finish').disabled=phase!=='running';
  $('preparation').hidden=phase==='running';
}
function contain(context,video,alpha=1,mirror=false){
  if(video.readyState<2||!video.videoWidth||!video.videoHeight)return;
  const w=context.canvas.width,h=context.canvas.height,scale=Math.min(w/video.videoWidth,h/video.videoHeight);
  const dw=video.videoWidth*scale,dh=video.videoHeight*scale;
  context.save();context.globalAlpha=alpha;
  if(mirror){context.translate(w,0);context.scale(-1,1);}
  context.drawImage(video,(w-dw)/2,(h-dh)/2,dw,dh);context.restore();
}
function stopCamera(){
  if(frameId!==null)cancelAnimationFrame(frameId);frameId=null;
  if(stream)for(const track of stream.getTracks())track.stop();
  stream=null;source.srcObject=null;
}
function halt(next,event,reason,outcome){
  active=false;starting=false;++run;clip.pause();stopCamera();phase=next;
  if(event)logEvent(event,{reason,outcome});controls();
}
function render(result){
  const choice=selector.update(result.multiHandLandmarks||[]);
  selected=choice.ready;
  if(choice.state!==lastChoice){
    if(choice.state==='selected')logEvent('selected');
    if(choice.state==='stabilizing')logEvent('selection_stabilizing');
    lastChoice=choice.state;
  }
  ctx.clearRect(0,0,camera.width,camera.height);
  ctx.save();ctx.translate(camera.width,0);ctx.scale(-1,1);
  ctx.drawImage(result.image,0,0,camera.width,camera.height);
  if(choice.box){const b=choice.box;ctx.strokeStyle=choice.ready?'#00ee99':'#ffcf66';ctx.lineWidth=3;
    ctx.strokeRect(b.x*camera.width,b.y*camera.height,b.width*camera.width,b.height*camera.height);}
  ctx.restore();ref.clearRect(0,0,reference.width,reference.height);
  if(phase==='running'){
    contain(ref,clip,1,$('mirror').checked);
    if($('mode').value==='overlay')contain(ctx,clip,Number($('opacity').value),$('mirror').checked);
  }
  if(choice.state==='lost'){
    logEvent('lost');halt('lost','aborted','selection_lost','aborted');
    status('선택한 손을 놓쳤습니다. 다시 준비를 눌러 처음부터 시작해 주세요.');return;
  }
  if(phase==='preparing')status(choice.ready
    ?'초록 테두리의 손을 사용합니다. 손금 쪽이 렌즈를 향하는지 확인하고 움직임 시작을 눌러 주세요.'
    :'손금이 보이는 쪽을 카메라 렌즈로 향해 주세요. 사용할 손을 가까이 보여 주세요.');
  else status('초록 테두리의 손으로 가려진 영상의 손모양과 움직임을 따라 해 보세요.');
  controls();
}
$('mode').onchange=()=>{document.body.classList.toggle('overlay',$('mode').value==='overlay');logEvent('ui_configured',config());};
$('guideHand').onchange=()=>{document.body.classList.toggle('left-hand',$('guideHand').value==='left');logEvent('ui_configured',config());};
$('media').onchange=()=>{
  if(objectUrl)URL.revokeObjectURL(objectUrl);
  const file=$('media').files[0];objectUrl=file?URL.createObjectURL(file):null;
  clip.src=objectUrl||'';$('start').disabled=true;
  status(file?'영상 확인 중...':'가림 완료 영상을 선택해 주세요.');
};
clip.onloadeddata=()=>{controls();status('영상이 준비됐습니다. 카메라로 손바닥 준비를 눌러 주세요.');};
clip.onerror=()=>{halt('error','technical_error','camera_or_detector_error','technical_error');
  $('start').disabled=true;status('영상을 재생할 수 없습니다. 다른 MP4 또는 WebM을 선택해 주세요.');};
$('palmConfirmed').onchange=()=>{
  if(phase!=='preparing'){ $('palmConfirmed').checked=false;return; }
  logEvent('palm_self_report',{palm_confirmed:$('palmConfirmed').checked});controls();
};
$('start').onclick=async()=>{
  if(active||clip.readyState<2)return;
  const generation=++run;++trialIndex;active=true;phase='preparing';selected=false;lastChoice=null;
  selector.reset();$('palmConfirmed').checked=false;controls();
  logEvent('preparation_started',config());
  try{
    if(!detector){
      detector=new Hands({locateFile:f=>`https://unpkg.com/@mediapipe/hands@0.4.1675469240/${f}`});
      detector.setOptions({maxNumHands:2,modelComplexity:1,minDetectionConfidence:.35,minTrackingConfidence:.4});
      detectorInitialization=detector.initialize();
    }
    await detectorInitialization;
    if(!active||generation!==run)return;
    detector.onResults(r=>{if(active&&generation===run)render(r);});
    const acquired=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640},height:{ideal:480}},audio:false});
    if(!active||generation!==run){acquired.getTracks().forEach(t=>t.stop());return;}
    stream=acquired;source.srcObject=stream;await source.play();
    if(!active||generation!==run)return;
    camera.width=reference.width=source.videoWidth;camera.height=reference.height=source.videoHeight;
    ref.clearRect(0,0,reference.width,reference.height);clip.pause();clip.currentTime=0;
    status('손금이 보이는 쪽을 카메라 렌즈로 향해 주세요.');
    async function tick(){
      if(!active||generation!==run)return;
      try{if(source.readyState>=2)await detector.send({image:source});}
      catch(error){if(generation!==run)return;halt('error','technical_error','detector_error','technical_error');
        status('손 검출을 중단했습니다. 다시 준비를 눌러 주세요.');return;}
      if(active&&generation===run)frameId=requestAnimationFrame(tick);
    }
    tick();
  }catch(error){
    if(generation!==run)return;
    halt('error','technical_error','camera_or_detector_error','technical_error');detector=null;detectorInitialization=null;
    status('카메라 또는 검출기를 시작하지 못했습니다. 권한과 네트워크를 확인해 주세요.');
  }
};
$('begin').onclick=async()=>{
  if(phase!=='preparing'||!active||!selected||!$('palmConfirmed').checked||starting)return;
  const generation=run;starting=true;controls();
  try{
    clip.currentTime=0;await clip.play();
    if(!active||generation!==run||phase!=='preparing'){clip.pause();return;}
    phase='running';starting=false;logEvent('attempt_started',config());controls();
    status('초록 테두리의 손으로 손모양과 움직임을 따라 해 보세요.');
  }catch(error){if(generation!==run)return;halt('error','technical_error','camera_or_detector_error','technical_error');
    status('문제 재생을 시작하지 못했습니다. 다시 준비해 주세요.');}
};
$('finish').onclick=()=>{
  if(phase!=='running')return;
  halt('finished','attempt_finished','user_finished','demo_finished');
  status('시연을 마쳤습니다. 다시 준비하거나, 원하면 기기 내 기록을 내려받을 수 있습니다.');
};
$('reset').onclick=()=>{
  if(active)halt('idle','aborted','user_reset','aborted');else {++run;phase='idle';clip.pause();stopCamera();}
  logEvent('reselect');selector.reset();selected=false;lastChoice=null;$('palmConfirmed').checked=false;
  clip.currentTime=0;controls();status('손금 쪽을 렌즈로 향하게 하고 카메라로 손바닥 준비를 눌러 주세요.');
};
$('exportLog').onclick=()=>{
  const blob=new Blob([JSON.stringify(eventLog.snapshot(),null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=url;a.download='hand-guidance-local.json';a.click();URL.revokeObjectURL(url);
};
window.addEventListener('pagehide',()=>{
  if(active)halt('idle','aborted','pagehide','aborted');else {++run;stopCamera();}
  if(objectUrl)URL.revokeObjectURL(objectUrl);
});
