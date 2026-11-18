'use strict';
let runInvalidated=false,runFinished=false,saveableResult=null;
const selectionEvents=[];
const selector=new UsabilitySelection.Selector();
const nativeResults=onRes,nativeStart=startRealChallenge,nativeResult=showResult;
const cameraArea=document.querySelector('.camera-area');
const panel=cameraArea.closest('.trial-panel');
panel.querySelector('.panel-title').textContent='목표 영상 + 내 카메라';
panel.querySelector('.panel-header').appendChild(document.getElementById('kfLabel'));
cameraArea.append(document.getElementById('kfInfo'),document.getElementById('matchInd'));
const layerLabel=document.createElement('div');layerLabel.className='layer-label';layerLabel.textContent='목표 42% · 내 카메라';cameraArea.append(layerLabel);
const hint=document.createElement('div');hint.id='selectionState';hint.setAttribute('role','status');hint.textContent='손 전체를 화면 중앙에 크게 보여 주세요. 가장 큰 손이 안정되면 선택합니다.';panel.append(hint);
const controls=document.createElement('div');controls.className='usability-controls';
controls.innerHTML='<label>목표 투명도 <input id="targetOpacity" aria-label="목표 투명도" type="range" min="20" max="65" value="42"> <output id="opacityValue">42%</output></label><button id="restartAttempt" type="button">처음부터 다시 시작</button><button id="saveEvents" type="button">선택 기록 저장</button>';
document.getElementById('screenTrial').append(controls);
const saveButton=document.createElement('button');saveButton.id='saveResult';saveButton.className='btn btn-secondary';saveButton.textContent='결과 JSON 저장';saveButton.disabled=true;
document.querySelector('#screenResult .btn-row').prepend(saveButton);
document.querySelector('#introBanner span').textContent='손을 중앙에 크게 보여 주세요. 초록 테두리로 선택되면 겹쳐 보이는 가림 목표 영상을 따라 하세요.';
const opacity=document.getElementById('targetOpacity');
opacity.oninput=()=>{document.getElementById('opacityValue').value=opacity.value+'%';layerLabel.textContent='목표 '+opacity.value+'% · 내 카메라';};
function download(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
saveButton.onclick=()=>{if(saveableResult)download(saveableResult,'hand_captcha_result.json');};
document.getElementById('saveEvents').onclick=()=>download({policy:UsabilitySelection.DEFAULTS,events:selectionEvents},'hand_selection_events.json');
document.getElementById('restartAttempt').onclick=()=>location.reload();
function recordSelection(reason){if(selectionEvents.length>=500)selectionEvents.shift();selectionEvents.push({reason,t_ms:performance.now(),phase});}
function clearAttempt(){
  matchHoldStart=null;handednessBuffer=[];selectedHand=null;lastLm=null;targetLm=null;
  curSegFrames=[];segments=[];sessionLog=[];keyframes=[];kfIdx=0;
  recStart=0;videoPlaying=false;fading=false;handLostSince=null;stopGhostLoop();rv.pause();
}
function invalidateAttempt(reason){
  if(runInvalidated||runFinished)return;
  recordSelection(reason);runInvalidated=true;clearAttempt();phase='invalidated';
  if(animId)cancelAnimationFrame(animId);if(camStream)camStream.getTracks().forEach(t=>t.stop());
  hint.textContent='선택한 손을 잃었거나 구분하기 어렵습니다. 현재 시도를 폐기했습니다. 처음부터 다시 시작해 주세요.';
  setS('waiting','선택 해제 · 이전 관문과 기록 초기화 완료');updateMatchIndicator('waiting','처음부터 다시 시작해 주세요');
}
function showAssetError(error){
  console.error(error);document.getElementById('loadingOverlay').classList.add('hidden');
  document.getElementById('cameraPlaceholder').textContent='모델·문제 자산을 불러오지 못했습니다. 서버 실행과 인터넷 연결을 확인한 뒤 다시 시작하세요.';
  setS('waiting','자산 로딩 실패: '+String(error.message||error));
}
startRealChallenge=function(){if(!runInvalidated)nativeStart();};
showResult=function(){if(runInvalidated||runFinished)return;runFinished=true;rv.pause();nativeResult();};
rv.addEventListener('error',()=>{if(!runInvalidated){invalidateAttempt('target_video_error');hint.textContent='목표 영상 로딩 실패. 서버 자산을 확인한 뒤 다시 시작하세요.';}});
function drawContained(source,alpha,mirror){
  const w=source.videoWidth||source.width,h=source.videoHeight||source.height;if(!w||!h)return;
  const s=Math.min(cc.width/w,cc.height/h);ctx.save();ctx.globalAlpha=alpha;
  if(mirror){ctx.translate(cc.width,0);ctx.scale(-1,1);}
  ctx.drawImage(source,(cc.width-w*s)/2,(cc.height-h*s)/2,w*s,h*s);ctx.restore();
}
let previousReason=null,lastCallback=null;
const cameraBase=document.createElement('canvas');
let displayedHand=null;
function paintComposite(){
  if(!cameraBase.width||!cameraBase.height)return;
  ctx.clearRect(0,0,cc.width,cc.height);ctx.drawImage(cameraBase,0,0);
  if(rv.style.display!=='none'&&rv.readyState>=2)drawContained(rv,Number(opacity.value)/100,Boolean(keyframes[kfIdx]?.mirror));
  if(displayedHand){
    const b=displayedHand.box;const track=camStream?.getVideoTracks()[0],settings=track?.getSettings()||{};
    const front=settings.facingMode==='user'||track?.label.toLowerCase().includes('front');
    ctx.save();ctx.strokeStyle='#00ff88';ctx.lineWidth=3;ctx.strokeRect((front?1-b.x-b.width:b.x)*cc.width,b.y*cc.height,b.width*cc.width,b.height*cc.height);ctx.restore();
  }
}
let displayRaf;
function displayLoop(){if(runInvalidated||runFinished)return;paintComposite();displayRaf=requestAnimationFrame(displayLoop);}
displayRaf=requestAnimationFrame(displayLoop);
onRes=function(result){
  if(runInvalidated||runFinished)return;
  const now=performance.now();
  if(lastCallback!==null&&now-lastCallback>=200)matchHoldStart=null;
  lastCallback=now;
  const chosen=selector.update(result.multiHandLandmarks,now);
  if(chosen.reason!==previousReason){recordSelection(chosen.reason);previousReason=chosen.reason;}
  if(chosen.state==='lost'){invalidateAttempt(chosen.reason);return;}
  if(!chosen.ready){matchHoldStart=null;handednessBuffer=[];}
  const hand=chosen.ready?chosen.hand:null,index=hand?.index;
  // Filter ALL data before invoking the original production gate/record/scoring path.
  nativeResults({...result,multiHandLandmarks:hand?[hand.points]:[],
    multiHandedness:hand&&result.multiHandedness?.[index]?[result.multiHandedness[index]]:[],
    multiHandWorldLandmarks:hand&&result.multiHandWorldLandmarks?.[index]?[result.multiHandWorldLandmarks[index]]:[]});
  if(runFinished||runInvalidated)return;
  displayedHand=hand;
  if(cameraBase.width!==cc.width||cameraBase.height!==cc.height){cameraBase.width=cc.width;cameraBase.height=cc.height;}
  cameraBase.getContext('2d').drawImage(cc,0,0);
  hint.textContent=hand?'초록 테두리 손을 선택했습니다. 목표 동작을 따라 하세요.':chosen.reason==='similar_sizes'?'손 하나를 다른 손보다 더 가까이 보여 주세요.':chosen.reason==='missing_or_small'?'선택한 손을 다시 크게 보여 주세요. 누락은 정상 관측으로 사용하지 않습니다.':chosen.state==='stabilizing'?'큰 손을 잠시 안정적으로 유지해 주세요.':'손 전체를 조금 더 가까이 보여 주세요.';
  // Render only; inference always receives cv, never this composite.
  paintComposite();
};
const watchdog=setInterval(()=>{if(!runInvalidated&&!runFinished&&selector.state==='selected'&&performance.now()-selector.lastSeen>UsabilitySelection.DEFAULTS.missingMs)invalidateAttempt('tracking_timeout');},100);
addEventListener('pagehide',()=>{clearInterval(watchdog);cancelAnimationFrame(displayRaf);if(camStream)camStream.getTracks().forEach(t=>t.stop());rv.pause();},{once:true});
