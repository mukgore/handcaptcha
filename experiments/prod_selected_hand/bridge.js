/* Integrate the existing selector with the existing production state machine. */
(() => {
  'use strict';
  const policy = Object.freeze({version:'selected_hand_gate_v1', maxGateGapMs:200,
    maxTrackingGapMs:500, maxTrialMs:60000, maxEvents:1000});
  const selector = new HandSelection.HandSelector();
  const originalResults = onRes, originalStatus = setS, originalStart = startRealChallenge,
    originalResult = showResult, originalTransition = onTransitionMatched;
  let previousTime = null, firstSelected = null, deadline = null, complete = false;
  const events = []; let dropped = 0;
  function record(event, reason) {
    if(events.length===policy.maxEvents){events.shift();dropped++;}
    events.push({event, reason, t_ms:performance.now(), phase});
  }
  const panel = document.querySelector('.camera-area').closest('.trial-panel');
  const controls = document.createElement('div'); controls.className='palm-ui-hint';
  controls.innerHTML='<span id="selectionState"></span> <button class="palm-ui-help" id="selectionRestart" type="button">시도 전체 다시 시작</button> <button class="palm-ui-help" id="selectionExport" type="button">시도 기록 저장</button>';
  panel.appendChild(controls);
  const label = document.getElementById('selectionState');
  label.textContent='큰 손 하나를 카메라에 비춰 주세요.';
  document.getElementById('selectionRestart').addEventListener('click', () => location.reload());
  document.getElementById('selectionExport').addEventListener('click', () => {
    const payload={schema_version:1, scope:'local_selection_events_only', policy,
      dropped_events:dropped, events:events.map(x=>({...x})), aborted:selectionRunAborted};
    const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='selection_trial_events.json';a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  function halt(reason) {
    if(selectionRunAborted || complete)return;
    record('aborted',reason); selectionRunAborted=true; phase='aborted';
    clearTimeout(deadline); matchHoldStart=null; handednessBuffer=[]; selectedHand=null;
    targetLm=null;keyframes=[];curSegFrames=[];segments=[];
    if(animId)cancelAnimationFrame(animId);
    stopGhostLoop();rv.pause();
    if(camStream)camStream.getTracks().forEach(t=>t.stop());
    label.textContent='시도가 중단됐습니다. 전체 다시 시작을 눌러 주세요.';
    originalStatus('waiting',reason==='timeout'?'시간이 지나 시도를 중단했습니다. 다시 시작해 주세요.':'선택한 손을 유지할 수 없어 시도를 중단했습니다. 다시 시작해 주세요.');
  }
  setS=function(type,text){if(!selectionRunAborted)originalStatus(type,text);};
  startRealChallenge=function(){if(!selectionRunAborted)originalStart();};
  onTransitionMatched=function(){if(!selectionRunAborted)originalTransition();};
  showResult=function(){
    if(selectionRunAborted || complete)return;
    complete=true;selectionRunFinished=true;clearTimeout(deadline);record('completed','original_score_flow');originalResult();
  };
  onRes=function(result){
    if(selectionRunAborted || complete)return;
    const now=performance.now();
    if(firstSelected!==null && previousTime!==null && now-previousTime>policy.maxTrackingGapMs){halt('tracking_gap');return;}
    if(previousTime!==null && now-previousTime>=policy.maxGateGapMs){matchHoldStart=null;record('gate_reset','callback_gap');}
    previousTime=now;
    const selected=selector.update(result.multiHandLandmarks);
    if(selected.state==='lost'){
      sessionLog.push({t:now-sessionStart,phase,detected:false,lm:null,selection_reason:'lost_or_ambiguous'});
      halt('hand_lost_or_ambiguous');return;
    }
    if(selected.ready && firstSelected===null){
      firstSelected=now;deadline=setTimeout(()=>halt('timeout'),policy.maxTrialMs);
      label.textContent='선택한 손을 유지하며 목표 자세를 따라 해 주세요.';
      record('selected','stable_largest_hand');
    }
    if(!selected.ready){
      handednessBuffer=[];matchHoldStart=null;
      label.textContent=selected.reason==='similar_sizes'?'손 하나만 더 가까이 비춰 주세요.':'큰 손 하나를 안정적으로 비춰 주세요.';
    }
    const index=selected.index;
    const previousHold=matchHoldStart, previousPhase=phase;
    originalResults({...result,
      multiHandLandmarks:selected.ready?[selected.points]:[],
      multiHandedness:selected.ready && result.multiHandedness?.[index]?[result.multiHandedness[index]]:[],
      multiHandWorldLandmarks:selected.ready && result.multiHandWorldLandmarks?.[index]?[result.multiHandWorldLandmarks[index]]:[]});
    if(previousHold===null && matchHoldStart!==null)record('gate_hold_started','original_gate');
    if(previousHold!==null && matchHoldStart===null)record('gate_hold_reset','original_gate');
    if(previousPhase!==phase)record('phase_changed','original_flow');
  };
  addEventListener('pagehide',()=>halt('pagehide'),{once:true});
})();
