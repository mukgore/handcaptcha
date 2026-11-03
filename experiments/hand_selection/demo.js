'use strict';
const $ = id => document.getElementById(id);
const selector = new HandSelection.HandSelector();
const camera = $('camera'), reference = $('reference');
const ctx = camera.getContext('2d'), ref = reference.getContext('2d');
const source = $('cameraSource'), clip = $('referenceSource');
let stream=null, detector=null, frameId=null, active=false, objectUrl=null, run=0;
const messages={waiting:'사용할 손을 카메라 가까이에 보여 주세요.',
  stabilizing:'큰 손을 선택하고 있습니다. 잠깐 유지해 주세요.',
  selected:'초록 테두리로 표시된 손을 사용합니다.',
  lost:'선택한 손을 놓쳤습니다. 손 다시 선택을 눌러 처음부터 시작해 주세요.'};
function status(message) { if ($('status').textContent!==message) $('status').textContent=message; }
function contain(context,video,alpha=1,mirror=false) {
  if (video.readyState<2) return;
  const w=context.canvas.width,h=context.canvas.height;
  const scale=Math.min(w/video.videoWidth,h/video.videoHeight);
  const dw=video.videoWidth*scale,dh=video.videoHeight*scale;
  context.save(); context.globalAlpha=alpha;
  if(mirror){context.translate(w,0);context.scale(-1,1);}
  context.drawImage(video,(w-dw)/2,(h-dh)/2,dw,dh); context.restore();
}
function render(result) {
  const choice=selector.update(result.multiHandLandmarks||[]);
  ctx.clearRect(0,0,camera.width,camera.height);
  // Mirror only the camera view and its selected-hand outline.
  ctx.save();ctx.translate(camera.width,0);ctx.scale(-1,1);
  ctx.drawImage(result.image,0,0,camera.width,camera.height);
  if(choice.box){const b=choice.box;ctx.strokeStyle=choice.ready?'#00ee99':'#ffcf66';ctx.lineWidth=3;
    ctx.strokeRect(b.x*camera.width,b.y*camera.height,b.width*camera.width,b.height*camera.height);}
  ctx.restore();
  ref.clearRect(0,0,reference.width,reference.height);
  contain(ref,clip,1,$('mirror').checked);
  if($('mode').value==='overlay')contain(ctx,clip,Number($('opacity').value),$('mirror').checked);
  status(messages[choice.state]);
  if(choice.state==='lost'){active=false;clip.pause();stopCamera();}
}
function stopCamera(){
  if(frameId!==null)cancelAnimationFrame(frameId);frameId=null;
  if(stream)for(const track of stream.getTracks())track.stop();stream=null;source.srcObject=null;
}
function setControls(disabled){for(const id of ['mode','opacity','mirror','media','start'])$(id).disabled=disabled;}
$('mode').onchange=()=>document.body.classList.toggle('overlay',$('mode').value==='overlay');
$('media').onchange=()=>{
  if(objectUrl)URL.revokeObjectURL(objectUrl);
  const file=$('media').files[0];objectUrl=file?URL.createObjectURL(file):null;
  clip.src=objectUrl||'';$('start').disabled=true;
  status(file?'영상 확인 중...':'가림 완료 영상을 선택해 주세요.');
};
clip.onloadeddata=()=>{$('start').disabled=active;status('영상을 준비했습니다. 카메라 켜고 시작을 눌러 주세요.');
  ref.clearRect(0,0,reference.width,reference.height);contain(ref,clip,1,$('mirror').checked);};
clip.onerror=()=>{$('start').disabled=true;status('영상을 재생할 수 없습니다. MP4 또는 WebM을 확인해 주세요.');};
$('start').onclick=async()=>{
  if(active)return; const generation=++run;active=true;setControls(true);
  try{
    if(!detector){
      detector=new Hands({locateFile:f=>`https://unpkg.com/@mediapipe/hands@0.4.1675469240/${f}`});
      detector.setOptions({maxNumHands:2,modelComplexity:1,minDetectionConfidence:.35,minTrackingConfidence:.4});
      detector.onResults(r=>{if(active&&generation===run)render(r);});
      await detector.initialize();
    }else detector.onResults(r=>{if(active&&generation===run)render(r);});
    if(!active||generation!==run)return;
    const acquired=await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:640},height:{ideal:480}},audio:false});
    if(!active||generation!==run){acquired.getTracks().forEach(t=>t.stop());return;}
    stream=acquired;source.srcObject=stream;await source.play();
    camera.width=reference.width=source.videoWidth;camera.height=reference.height=source.videoHeight;
    clip.currentTime=0;await clip.play();selector.reset();
    async function tick(){
      if(!active||generation!==run)return;
      try{if(source.readyState>=2)await detector.send({image:source});}
      catch(error){active=false;stopCamera();clip.pause();status('손 검출을 중단했습니다. 처음부터 다시 선택해 주세요.');return;}
      if(active&&generation===run)frameId=requestAnimationFrame(tick);
    }
    tick();
  }catch(error){active=false;stopCamera();clip.pause();setControls(false);
    $('start').disabled=clip.readyState<2;status('카메라 또는 검출기를 시작하지 못했습니다. 권한과 네트워크를 확인해 주세요.');}
};
$('reset').onclick=()=>location.reload();
window.addEventListener('pagehide',()=>{active=false;++run;stopCamera();if(objectUrl)URL.revokeObjectURL(objectUrl);});
