'use strict';
let runInvalidated=false,runFinished=false,saveableResult=null;
let attemptEpoch=0,restartNoticeUntil=0;
const selectionEvents=[];
const selector=new UsabilitySelection.Selector();
const nativeResults=onRes,nativeStart=startRealChallenge,nativeResult=showResult,nativeKeyframe=showKeyframeImage;
const cameraArea=document.querySelector('.camera-area');
const panel=cameraArea.closest('.trial-panel');
panel.querySelector('.panel-title').remove();
panel.querySelector('.panel-header').appendChild(document.getElementById('kfLabel'));
const views=document.createElement('div');
views.className='hand-views';
views.dataset.primary='target';
views.innerHTML=`
  <section class="hand-view target-view" aria-labelledby="targetLabel">
    <h2 id="targetLabel">따라 할 손</h2>
    <div class="target-surface">
      <canvas id="targetFrame" width="0" height="0" aria-labelledby="targetLabel"></canvas>
      <p id="targetPlaceholder">손이 선택되면 시범이 시작됩니다.</p>
    </div>
  </section>
  <section class="hand-view own-view" aria-labelledby="ownLabel">
    <h2 id="ownLabel">나의 손</h2>
  </section>`;
cameraArea.before(views);
views.querySelector('.own-view').append(cameraArea);
cc.setAttribute('aria-labelledby','ownLabel');
const hint=document.getElementById('statusBar');
hint.setAttribute('role','status');
const controls=document.createElement('div');controls.className='usability-controls';
controls.innerHTML='<button id="swapHandViews" type="button">내 손 크게</button><button id="restartAttempt" type="button">처음부터 다시 시작</button>';
document.getElementById('screenTrial').append(controls);
const swapHandViews=document.getElementById('swapHandViews');
swapHandViews.addEventListener('click',()=>{
  const ownIsPrimary=views.dataset.primary==='own';
  views.dataset.primary=ownIsPrimary?'target':'own';
  swapHandViews.textContent=ownIsPrimary?'내 손 크게':'따라 할 손 크게';
});
const saveButton=document.createElement('button');saveButton.id='saveResult';saveButton.className='btn btn-secondary';saveButton.textContent='결과 JSON 저장';saveButton.disabled=true;
document.querySelector('#screenResult .btn-row').prepend(saveButton);
function download(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
saveButton.onclick=()=>{if(saveableResult)download(saveableResult,'hand_captcha_result.json');};
document.getElementById('restartAttempt').onclick=()=>location.reload();
let restartNotice='', frameSelection=null, assetError=false;
function showHint(text, tone='waiting', centered=false){
  const container=centered?cameraArea:panel;
  if(hint.parentElement!==container)container.append(hint);
  hint.className='status-bar '+tone+(centered?' center-hint':'');
  if(hint.textContent!==text)hint.textContent=text;
}
function showGuidance(){
  if(runInvalidated||runFinished||assetError)return;
  if(phase==='detecting_hand'){
    if(restartNotice&&performance.now()<restartNoticeUntil&&!frameSelection?.ready){showHint(restartNotice,'waiting',true);return;}
    if(frameSelection?.ready&&selectedHand){showHint('따라 할 손 영상을 준비하고 있어요.','waiting',true);return;}
    if(frameSelection?.reason==='similar_sizes'){showHint('따라 할 손 하나를 카메라에 더 가까이 보여 주세요.','waiting',true);return;}
    if(frameSelection?.reason==='stabilizing'||frameSelection?.ready){showHint('손을 고르는 동안 지금 위치에 잠시 유지해 주세요.','waiting',true);return;}
    showHint('손 전체를 화면 중앙에 크게 비춰 주세요.','waiting',true);
    return;
  }
  if(phase!=='matching'&&phase!=='recording')return;
  if(frameSelection?.reason==='missing_or_small'){
    showHint('계속하려면 초록 테두리로 선택했던 손을 다시 비춰 주세요. 1.5초 이상 벗어나면 처음부터 시작합니다.');
  }else if(targetPending){
    showHint('다음 목표 화면을 준비하고 있어요. 초록 테두리의 손을 유지해 주세요.');
  }else if(videoPlaying){
    showHint('따라 할 손을 보고 같은 동작을 해보세요.','playing');
  }else if(matchHoldStart!==null){
    showHint('자세가 맞았어요. 잠시 유지해 주세요.','complete');
  }else{
    showHint('따라 할 손을 보고 같은 동작을 해보세요.');
  }
}
// Keep production error and completion messages in the same status area.
setS=function(tone,text){
  if(phase==='idle'||phase==='invalidated'||tone==='complete')showHint(text.replace(/^✅\s*/,''),tone);
};
function recordSelection(reason){if(selectionEvents.length>=500)selectionEvents.shift();selectionEvents.push({reason,t_ms:performance.now(),phase});}
function clearAttempt(){
  matchHoldStart=null;handednessBuffer=[];selectedHand=null;lastLm=null;targetLm=null;
  curSegFrames=[];segments=[];sessionLog=[];keyframes=[];kfIdx=0;
  recStart=0;videoPlaying=false;fading=false;handLostSince=null;stopGhostLoop();rv.pause();
}
function invalidateAttempt(reason){
  if(runInvalidated||runFinished)return;
  if(reason==='tracking_timeout'||reason==='ambiguous_crossing'){restartForHand(reason);return;}
  recordSelection(reason);runInvalidated=true;clearAttempt();phase='invalidated';
  if(animId)cancelAnimationFrame(animId);if(camStream)camStream.getTracks().forEach(t=>t.stop());
  showHint('손 추적을 계속할 수 없습니다. 처음부터 다시 시작해 주세요.');
}
function restartForHand(reason){
  recordSelection(reason);attemptEpoch++;
  clearAttempt();selector.reset();previousReason=null;lastCallback=null;
  saveableResult=null;saveButton.disabled=true;sessionStart=performance.now();phase='detecting_hand';
  targetFrame.width=0;targetPending=false;rv.oncanplay=null;rv.removeAttribute('src');rv.load();
  targetPlaceholder.hidden=false;
  rv.style.display='none';document.getElementById('kfProgress').innerHTML='';
  document.getElementById('kfLabel').textContent='손 선택 대기';document.getElementById('kfInfo').textContent='';
  document.getElementById('frameCounter').textContent='0 프레임';
  restartNoticeUntil=performance.now()+4000;
  const notice=reason==='ambiguous_crossing'?'선택한 손을 구분하기 어려워 재시작합니다.':'손이 1.5초 이상 이탈해 재시작합니다.';
  restartNotice=notice+' 손 전체를 화면 중앙에 보여 주세요.';
  frameSelection=null;showGuidance();
  // Keep the original camera/model loop running; the next packet begins fresh acquisition.
}
function showAssetError(error){
  assetError=true;
  console.error(error);document.getElementById('loadingOverlay').classList.add('hidden');
  document.getElementById('cameraPlaceholder').style.display='none';
  showHint('문제나 모델을 불러오지 못했습니다. 연결을 확인한 뒤 다시 시작해 주세요.','waiting',true);
}
startRealChallenge=function(){if(!runInvalidated)nativeStart();};
showResult=function(){if(runInvalidated||runFinished)return;runFinished=true;rv.pause();nativeResult();};
rv.addEventListener('error',()=>{if(!runInvalidated){invalidateAttempt('target_video_error');showHint('목표 영상 로딩 실패. 서버 자산을 확인한 뒤 다시 시작하세요.');}});
let previousReason=null,lastCallback=null;
const targetFrame=document.getElementById('targetFrame');
const targetPlaceholder=document.getElementById('targetPlaceholder');
let targetPending=false,targetExpectedTime=0;
function rememberTarget(){
  if(rv.readyState<2||rv.seeking||rv.style.display==='none')return;
  if(targetPending&&Math.abs(rv.currentTime-targetExpectedTime)>.08)return;
  targetPending=false;
  if(targetFrame.width!==rv.videoWidth||targetFrame.height!==rv.videoHeight){targetFrame.width=rv.videoWidth;targetFrame.height=rv.videoHeight;}
  targetFrame.getContext('2d').drawImage(rv,0,0);
  targetFrame.style.transform=rv.style.transform;
  targetPlaceholder.hidden=true;
}
showKeyframeImage=function(index){
  rememberTarget();targetPending=true;targetExpectedTime=keyframes[index].time;
  nativeKeyframe(index);
};
function drawSelectedHand(hand){
  const b=hand.box;
  const track=camStream.getVideoTracks()[0];
  const front=track.getSettings().facingMode==='user'||track.label.toLowerCase().includes('front');
  const x=front?1-b.x-b.width:b.x;
  ctx.save();
  ctx.strokeStyle='#00ff88';ctx.lineWidth=3;
  ctx.strokeRect(x*cc.width,b.y*cc.height,b.width*cc.width,b.height*cc.height);
  ctx.restore();
}
let displayRaf;
function displayLoop(){if(runInvalidated||runFinished)return;rememberTarget();displayRaf=requestAnimationFrame(displayLoop);}
displayRaf=requestAnimationFrame(displayLoop);
onRes=function(result){
  if(runInvalidated||runFinished)return;
  const now=performance.now();
  if(lastCallback!==null&&now-lastCallback>=200)matchHoldStart=null;
  lastCallback=now;
  const chosen=selector.update(result.multiHandLandmarks,now);
  frameSelection=chosen;
  if(chosen.reason!==previousReason){recordSelection(chosen.reason);previousReason=chosen.reason;}
  if(chosen.state==='lost'){invalidateAttempt(chosen.reason);return;}
  if(!chosen.ready){matchHoldStart=null;handednessBuffer=[];}
  const hand=chosen.ready?chosen.hand:null,index=hand?.index;
  // Filter ALL data before invoking the original production gate/record/scoring path.
  nativeResults({...result,multiHandLandmarks:hand?[hand.points]:[],
    multiHandedness:hand&&result.multiHandedness?.[index]?[result.multiHandedness[index]]:[],
    multiHandWorldLandmarks:hand&&result.multiHandWorldLandmarks?.[index]?[result.multiHandWorldLandmarks[index]]:[]});
  if(runFinished||runInvalidated)return;
  if(hand)drawSelectedHand(hand);
  showGuidance();
};
const watchdog=setInterval(()=>{if(!runInvalidated&&!runFinished&&selector.state==='selected'&&performance.now()-selector.lastSeen>UsabilitySelection.DEFAULTS.missingMs)invalidateAttempt('tracking_timeout');},100);
addEventListener('pagehide',()=>{clearInterval(watchdog);cancelAnimationFrame(displayRaf);if(camStream)camStream.getTracks().forEach(t=>t.stop());rv.pause();},{once:true});
