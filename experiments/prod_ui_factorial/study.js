/* Opt-in local research only. Raw paired files stay in this browser, never uploaded. */
(() => {
  'use strict';
  const config=UI_FACTORS,design=UIFactorial,preview=new URLSearchParams(location.search).get('preview')==='1';
  const area=document.querySelector('.ref-area'),camera=document.querySelector('.camera-area');
  const target=document.createElement('canvas');target.className='study-target';target.hidden=true;area.appendChild(target);
  const targetContext=target.getContext('2d'),cameraBase=document.createElement('canvas');
  const maskedFrame=document.createElement('canvas'),rawFrame=document.createElement('canvas');
  const urls=[],events=[];let dropped=0,raf=null,started=null,preludeStarted=null,preludeActive=false;
  let stopped=false,frozen=null,local=null,outcome='not_started',finalScores=null,ended=null;
  function record(event,fields={}){if(events.length===1000){events.shift();dropped++;}events.push({event,t_ms:performance.now(),...fields});}
  function snapshot(){return {schema_version:1,scope:preview?'synthetic_ui_preview':'local_ui_diagnostic',
    condition:{...config},hold_ms:500,fade_ms:500,common_prelude_ms:1000,overlay_opacity:design.overlay_opacity,
    source_family:local?.family??null,outcome,scores:finalScores,elapsed_ms:started===null?null:(ended??performance.now())-started,
    dropped_events:dropped,events:events.map(x=>({...x})),
    human_effects_verified:false};}
  function stop(reason){
    if(stopped)return;stopped=true;preludeActive=false;uiPreludeBlocked=false;target.hidden=true;selectionRunAborted=true;
    if(outcome!=='completed'){ended=performance.now();outcome=reason;record('attempt_ended',{outcome:reason});}
    if(raf!==null)cancelAnimationFrame(raf);if(animId)cancelAnimationFrame(animId);
    if(camStream)camStream.getTracks().forEach(track=>track.stop());rv.pause();stopGhostLoop();
    document.getElementById('statusBar').textContent='시도를 중단했습니다. 기록을 저장하거나 전체 다시 시작해 주세요.';
  }
  function drawContained(context,source,alpha=1,mirror=false){
    const w=source.videoWidth||source.width,h=source.videoHeight||source.height;
    if(!w||!h||('readyState' in source&&source.readyState<2))return;
    const cw=context.canvas.width,ch=context.canvas.height,scale=Math.min(cw/w,ch/h);
    context.save();context.globalAlpha=alpha;if(mirror){context.translate(cw,0);context.scale(-1,1);}
    context.drawImage(source,(cw-w*scale)/2,(ch-h*scale)/2,w*scale,h*scale);context.restore();
  }
  function elapsed(){return frozen??(preludeStarted===null?0:Math.max(0,performance.now()-preludeStarted));}
  function paintTarget(ms){
    const alpha=design.alpha(ms,config.reveal);
    targetContext.fillStyle='#0f172a';targetContext.fillRect(0,0,target.width,target.height);
    const mirror=!preview&&Boolean(keyframes[0]?.mirror);
    drawContained(targetContext,maskedFrame,1,mirror);if(alpha)drawContained(targetContext,rawFrame,alpha,mirror);
    target.dataset.revealAlpha=String(alpha);
  }
  function render(){
    if(stopped)return;
    if(preludeActive){
      const ms=elapsed();paintTarget(ms);
      if(preludeStarted!==null&&ms>=1000){preludeActive=false;uiPreludeBlocked=false;target.hidden=true;matchHoldStart=null;record('prelude_finished');}
    }
    if(config.overlay&&cameraBase.width&&cameraBase.height){
      ctx.clearRect(0,0,cc.width,cc.height);ctx.drawImage(cameraBase,0,0);
      const visibleTarget=preludeActive?target:(rv.style.display!=='none'&&rv.readyState>=2?rv:rc);
      drawContained(ctx,visibleTarget,design.overlay_opacity,!preludeActive&&!preview&&Boolean(keyframes[kfIdx]?.mirror));
    }
    raf=requestAnimationFrame(render);
  }
  function rememberCamera(){
    if(!cc.width||!cc.height)return;
    if(cameraBase.width!==cc.width||cameraBase.height!==cc.height){cameraBase.width=cc.width;cameraBase.height=cc.height;}
    cameraBase.getContext('2d').drawImage(cc,0,0);
  }
  if(config.overlay){
    document.body.classList.add('ui-overlay');
    const header=camera.closest('.trial-panel').querySelector('.panel-header');header.appendChild(document.getElementById('kfLabel'));
    camera.appendChild(document.getElementById('kfInfo'));camera.appendChild(document.getElementById('matchInd'));
  }
  const controls=document.createElement('div');controls.className='study-controls';
  controls.innerHTML='<span>연구용 비교</span><button id="studyExport" type="button">시도 기록 저장</button><button id="studyStop" type="button">중단</button><button id="studyRestart" type="button">전체 다시 시작</button>';
  document.getElementById('screenTrial').appendChild(controls);
  document.getElementById('studyRestart').onclick=()=>location.reload();
  document.getElementById('studyStop').onclick=()=>stop('user_aborted');
  document.getElementById('studyExport').onclick=()=>{
    const url=URL.createObjectURL(new Blob([JSON.stringify(snapshot(),null,2)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download='ui_diagnostic.private.json';link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  const nativeResults=onRes,nativeStart=startRealChallenge,nativeResult=showResult;
  onRes=function(result){
    if(stopped)return;
    nativeResults(result); // Original camera packet, never the mixed display canvas.
    if(selectionRunAborted){stop('selection_aborted');return;}
    rememberCamera();
  };
  showResult=function(){
    if(stopped)return;
    ended=performance.now();outcome='completed';finalScores=computeScores();record('attempt_ended',{outcome});
    selectionRunFinished=true;nativeResult();
    document.getElementById('redirectMsg').textContent='기록을 저장한 뒤 전체 다시 시작할 수 있습니다.';
    if(raf!==null)cancelAnimationFrame(raf);
  };
  function seekFrame(url,time){return new Promise((resolve,reject)=>{
    const video=document.createElement('video');video.muted=true;video.playsInline=true;video.preload='auto';
    const timer=setTimeout(()=>finish(Error('video_seek_timeout')),5000);
    function finish(error){clearTimeout(timer);video.onloadeddata=video.onseeked=video.onerror=null;
      if(error){video.pause();video.removeAttribute('src');video.load();reject(error);}else resolve(video);}
    video.onerror=()=>finish(Error('video_decode_failed'));
    video.onloadeddata=()=>{if(Math.abs(video.currentTime-time)<.001)finish();else video.currentTime=time;};
    video.onseeked=()=>finish();video.src=url;video.load();
  });}
  startRealChallenge=function(){
    if(stopped)return;preludeActive=true;uiPreludeBlocked=true;nativeStart();
    if(!keyframes.length){stop('input_error');return;}
    Promise.all([seekFrame(local.masked,keyframes[0].time),seekFrame(local.raw,keyframes[0].time)]).then(videos=>{
      if(stopped)return;
      [maskedFrame,rawFrame].forEach((canvas,index)=>{canvas.width=videos[index].videoWidth;canvas.height=videos[index].videoHeight;canvas.getContext('2d').drawImage(videos[index],0,0);videos[index].pause();videos[index].removeAttribute('src');videos[index].load();});
      target.width=maskedFrame.width;target.height=maskedFrame.height;preludeStarted=performance.now();target.hidden=false;
      record('prelude_started',{reveal:config.reveal,source_frame_index:keyframes[0].frameIdx});
    }).catch(()=>stop('technical_error'));
  };
  function loadScript(src,dataset){return new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=src;
    if(dataset)Object.assign(script.dataset,dataset);script.onload=resolve;script.onerror=()=>reject(Error('script_load_failed'));document.body.appendChild(script);});}
  function metadata(url){return new Promise((resolve,reject)=>{const v=document.createElement('video');
    const timer=setTimeout(()=>done(Error('metadata_timeout')),5000);v.onloadedmetadata=()=>done();v.onerror=()=>done(Error('metadata_error'));
    function done(error){clearTimeout(timer);const data={width:v.videoWidth,height:v.videoHeight,duration:v.duration};v.onloadedmetadata=v.onerror=null;v.removeAttribute('src');v.load();error?reject(error):resolve(data);}v.src=url;});}
  async function prepare(){
    const file=id=>document.getElementById(id).files[0];
    const masked=file('studyMasked'),raw=file('studyRaw'),points=file('studyLandmarks');
    const family=document.getElementById('studyFamily').value.trim();
    if(!masked||!raw||!points||!document.getElementById('studyReviewed').checked||!/^[A-Za-z0-9_-]{1,64}$/.test(family))throw Error('input_required');
    if(masked.size>250*1024**2||raw.size>250*1024**2||points.size>32*1024**2)throw Error('input_budget');
    const data=JSON.parse(await points.text()),info=data.video_info;
    if(!info||!['width','height','fps'].every(k=>typeof info[k]==='number'&&Number.isFinite(info[k])&&info[k]>0)||!Array.isArray(data.frames)||data.frames.length<2||data.frames.length>10000)throw Error('landmark_metadata');
    let previous=-1,detected=0;
    data.frames.forEach((frame,index)=>{
      const i=frame.frame_idx??index;if(!Number.isInteger(i)||i<=previous)throw Error('frame_order');previous=i;
      if(frame.detected){if(!frame.landmarks_px||!LN.every(n=>['x','y'].every(k=>typeof frame.landmarks_px[n]?.[k]==='number'&&Number.isFinite(frame.landmarks_px[n][k]))))throw Error('landmark_shape');detected++;}
    });if(detected<2)throw Error('insufficient_points');
    const maskedUrl=URL.createObjectURL(masked),rawUrl=URL.createObjectURL(raw);urls.push(maskedUrl,rawUrl);
    const [a,b]=await Promise.all([metadata(maskedUrl),metadata(rawUrl)]),duration=(previous+1)/info.fps;
    if([a,b].some(v=>v.width!==info.width||v.height!==info.height||!Number.isFinite(v.duration)||Math.abs(v.duration-duration)>Math.max(.1,2/info.fps))||Math.abs(a.duration-b.duration)>1/info.fps)throw Error('paired_metadata_mismatch');
    // This checks metadata, not semantic correspondence or consent. Operator review is explicit.
    local={masked:maskedUrl,raw:rawUrl,data,family,handedness:document.getElementById('studyHand').value};
    if(stopped)return;
    loadPoolManifest=async()=>{poolManifest={clips:[{clip_id:'local-pair',video_file:local.masked,landmarks_file:'local-points',handedness:local.handedness}]};};
    loadClipLandmarks=async()=>local.data;
    document.getElementById('studyError').textContent='카메라와 추적기를 준비하고 있습니다…';
    await loadScript('https://unpkg.com/@mediapipe/hands@0.4.1675469240/hands.js');
    if(stopped)return;
    await loadScript('https://unpkg.com/@mediapipe/drawing_utils@0.3.1675466124/drawing_utils.js');
    if(stopped)return;started=performance.now();outcome='running';record('attempt_started');
    setTimeout(dismissIntroBanner,8000);
    await bootstrap();
  }
  function setup(){
    document.getElementById('loadingOverlay').innerHTML=`<div class="study-setup"><h2>비공개 비교 자료 준비</h2><p>기존 prod 기반 연구용 화면입니다. 같은 촬영의 원본·가림본·좌표를 선택합니다. 파일은 이 브라우저에서만 읽습니다.</p><p>구성: ${config.condition_id} · 실제 사람 효과는 아직 측정하지 않았습니다.</p>
    <label>가림본 영상<input id="studyMasked" type="file" accept="video/*"></label><label>무가림 원본 영상<input id="studyRaw" type="file" accept="video/*"></label><label>대응 좌표 JSON<input id="studyLandmarks" type="file" accept=".json,application/json"></label>
    <label>원동작 계열 코드<input id="studyFamily" maxlength="64" autocomplete="off"></label><label>촬영한 손<select id="studyHand"><option>Right</option><option>Left</option></select></label>
    <label><input id="studyReviewed" type="checkbox">같은 촬영의 대응 자료이며 연구 사용 범위를 확인했습니다.</label><button id="studyBegin" type="button">이 자료로 비교 시작 · 카메라 사용</button><p id="studyError" class="study-error" role="status"></p></div>`;
    document.getElementById('studyBegin').onclick=async()=>{const button=document.getElementById('studyBegin');button.disabled=true;
      try{await prepare();}catch{document.getElementById('studyError').textContent='자료가 없거나 서로 맞지 않거나 준비에 실패했습니다. 입력을 확인하고 다시 시작해 주세요.';stop('technical_error');button.disabled=true;}};
  }
  function previewFixture(){
    document.getElementById('loadingOverlay').classList.add('hidden');document.getElementById('cameraPlaceholder').style.display='none';
    [cc,rc,maskedFrame,rawFrame,target].forEach(canvas=>{canvas.width=640;canvas.height=480;});
    for(const [canvas,masked,offset] of [[rawFrame,false,0],[maskedFrame,true,0],[cc,false,.1]]){
      const context=canvas.getContext('2d');context.fillStyle='#1e293b';context.fillRect(0,0,640,480);
      drawGhostSilhouette(FRAMING_GUIDE_POSE.map(p=>[(p[0]+offset)*640,p[1]*480]),context,640,480,{skipClear:true,fillStyle:'#cda888',palm:true});
      if(masked){context.fillStyle='#000';context.beginPath();context.arc(320,326,100,0,Math.PI*2);context.fill();}
    }
    rctx.drawImage(maskedFrame,0,0);framingGuideStartTime=performance.now();drawFramingGuideOverlay(performance.now());rememberCamera();
    document.getElementById('kfProgress').innerHTML='<div class="kf-dot active" id="kfd0">1</div><span class="kf-arrow">→</span><div class="kf-dot" id="kfd1">2</div>';
    document.getElementById('kfLabel').textContent='자세 1/2';document.getElementById('kfInfo').textContent='합성 미리보기';
    document.getElementById('statusBar').textContent='예시 손으로 화면만 비교합니다. 실제 카메라는 실행하지 않습니다.';
    phase='preview';frozen=0;preludeStarted=performance.now();preludeActive=true;uiPreludeBlocked=true;target.hidden=false;outcome='synthetic_preview';
  }
  window.UIStudy=Object.freeze({snapshot,config,preview,drawCameraOnly:result=>{
    const track=camStream?.getVideoTracks()[0],settings=track?.getSettings()??{};
    const mirror=settings.facingMode==='user'||Boolean(track?.label.toLowerCase().includes('front'));
    ctx.save();ctx.clearRect(0,0,cc.width,cc.height);if(mirror){ctx.translate(cc.width,0);ctx.scale(-1,1);}
    ctx.drawImage(result.image,0,0,cc.width,cc.height);drawFramingGuideOverlay(performance.now());ctx.restore();matchHoldStart=null;
  },getState:()=>({prelude_active:preludeActive,gate_blocked:uiPreludeBlocked,
    reveal_alpha:Number(target.dataset.revealAlpha??0),outcome}),freezeAt:ms=>{if(!preview)throw Error('Preview only');
      if(typeof ms!=='number'||!Number.isFinite(ms)||ms<0)throw Error('Invalid preview time');frozen=ms;preludeActive=ms<1000;uiPreludeBlocked=preludeActive;target.hidden=!preludeActive;paintTarget(ms);}});
  const hints=['copy','compare','guide'].filter(name=>config[name]);
  (async()=>{if(hints.length)await loadScript('experiments/prod_palm_variants/guidance.js',{palmVariants:hints.join(',')});
    if(preview)previewFixture();else setup();record('configured',{condition_id:config.condition_id});
    document.body.dataset.studyReady='true';raf=requestAnimationFrame(render);
  })().catch(()=>{document.getElementById('loadingOverlay').textContent='화면을 준비하지 못했습니다. 다시 열어 주세요.';});
  addEventListener('pagehide',()=>{stop('pagehide');urls.forEach(url=>URL.revokeObjectURL(url));},{once:true});
})();
