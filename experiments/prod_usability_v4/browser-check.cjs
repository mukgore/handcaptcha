// Development regression only. Synthetic camera/landmarks do not establish human usability.
const {chromium}=require(process.env.PLAYWRIGHT_CORE||'../../../qa/node_modules/playwright-core');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base='http://127.0.0.1:8771/experiments/prod_usability_v4/';
let browser;
(async()=>{
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,
    args:['--disable-gpu','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
  const context=await browser.newContext({viewport:{width:1280,height:900},acceptDownloads:true});
  const page=await context.newPage(),errors=[],failed=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()}));
  await page.goto(base);
  await page.waitForFunction(()=>typeof phase!=='undefined'&&phase==='detecting_hand'&&cv.readyState>=2,{},{timeout:60000});
  const guidance=page.locator('#statusBar');
  assert.match(await guidance.textContent(),/화면 중앙/);
  const stage=await page.locator('.camera-area').boundingBox(), prompt=await guidance.boundingBox();
  assert.ok(Math.abs(stage.y+stage.height/2-prompt.y-prompt.height/2)<2);
  assert.ok(Math.abs(stage.x+stage.width/2-prompt.x-prompt.width/2)<2);
  assert.equal(await page.locator('.header:visible, .intro-banner:visible, .trial-panel .panel-title:visible, #targetOpacity, #saveEvents, .layer-label').count(),0);
  assert.deepEqual(await page.locator('.hand-view h2').allTextContents(),['따라 할 손','나의 손']);
  const target=page.locator('.target-view'), own=page.locator('.own-view');
  async function assertLayout(primary, secondary, narrow=false){
    const a=await primary.boundingBox(), b=await secondary.boundingBox();
    assert.ok(a.width*a.height>b.width*b.height);
    assert.ok(narrow?a.y+a.height<=b.y:a.x+a.width<=b.x);
  }
  await assertLayout(target,own);
  console.log('PASS real page + pinned MediaPipe model + synthetic camera + local manifest');
  await page.evaluate(()=>{cancelAnimationFrame(animId);runFinished=true;});await page.waitForTimeout(500);
  await page.evaluate(()=>{
    runFinished=false;
    displayLoop();
    window.testPoints=Array.from({length:21},(_,i)=>[.25+(i%5)*.06,.2+Math.floor(i/5)*.1]);window.testTimer=setInterval(()=>{
      if(runInvalidated||runFinished)return;
      const desired=targetLm||window.testPoints;
      const points=window.testPoints=window.testPoints.map((p,i)=>[p[0]+(desired[i][0]-p[0])*.25,p[1]+(desired[i][1]-p[1])*.25]);
      const lm=points.map(p=>({x:p[0],y:p[1],z:0}));
      onRes({image:cv,multiHandLandmarks:[lm],multiHandedness:[{label:'Left',score:.99}]});
    },70);
  });
  await page.waitForFunction(()=>typeof keyframes!=='undefined'&&keyframes.length>0&&rv.readyState>=2,{},{timeout:20000});
  await page.waitForFunction(()=>hint.parentElement===panel&&hint.textContent.includes('같은 동작'));
  assert.equal(await page.locator('#screenTrial [role="status"]:visible, #matchInd:visible').count(),1);
  if(process.env.CAPTCHA_SCREENSHOT)await page.screenshot({path:process.env.CAPTCHA_SCREENSHOT});
  await page.waitForFunction(()=>videoPlaying&&!rv.paused&&rv.currentTime>0&&targetFrame.width>0);
  const swap=await page.evaluate(()=>{
    const before={stream:camStream,track:camStream.getVideoTracks()[0],src:rv.src,time:rv.currentTime,
      frames:curSegFrames,points:targetLm,epoch:attemptEpoch,index:kfIdx,mirror:targetFrame.style.transform};
    swapHandViews.click();
    return {sameCamera:camStream===before.stream&&cv.srcObject===before.stream&&camStream.getVideoTracks()[0]===before.track,
      sameAttempt:curSegFrames===before.frames&&targetLm===before.points&&attemptEpoch===before.epoch&&kfIdx===before.index,
      sameVideo:rv.src===before.src&&!rv.paused&&rv.currentTime>=before.time&&targetFrame.style.transform===before.mirror};
  });
  assert.deepEqual(swap,{sameCamera:true,sameAttempt:true,sameVideo:true});
  await assertLayout(own,target);
  assert.equal(await page.locator('#swapHandViews').textContent(),'따라 할 손 크게');
  assert.deepEqual(await page.locator('#targetFrame, #cameraCanvas').evaluateAll(nodes=>nodes.map(n=>getComputedStyle(n).objectFit)),['contain','contain']);
  if(process.env.CAPTCHA_OWN_SCREENSHOT)await page.screenshot({path:process.env.CAPTCHA_OWN_SCREENSHOT});
  console.log('PASS layout switch during playback preserves stream, attempt, video position and mirror');
  console.log('PASS centered acquisition prompt, one imitation instruction, requested controls absent');
  console.log('DISPLAY',await page.evaluate(()=>({canvas:[cc.width,cc.height],video:[rv.videoWidth,rv.videoHeight],camera:[cv.videoWidth,cv.videoHeight],pixel:[...ctx.getImageData(100,100,1,1).data]})));
  try{await page.waitForFunction(()=>runFinished&&document.getElementById('screenResult').classList.contains('active'),{},{timeout:60000});}
  catch(e){console.error(await page.evaluate(()=>({phase,runInvalidated,selectorState:selector.state,kfIdx,events:selectionEvents,body:document.body.innerText})));throw e;}
  const result=await page.evaluate(()=>({scores:saveableResult.scores,segments:saveableResult.segments.length,frames:saveableResult.sessionLog.length}));
  assert.ok(result.segments>0);assert.ok(result.frames>0);assert.ok(Number.isFinite(result.scores.captcha));
  console.log('PASS gate → real video playback → record → score → result',JSON.stringify(result));
  const download=page.waitForEvent('download');await page.locator('#saveResult').click();const d=await download;
  assert.ok(JSON.parse(fs.readFileSync(await d.path(),'utf8')).selection);console.log('PASS result JSON download');
  await page.evaluate(()=>clearInterval(window.testTimer));
  // Delay the next real MP4: cached masked frame must remain byte-identical until ready.
  let releaseVideo;const delayedVideo=new Promise(resolve=>{releaseVideo=resolve;});
  await page.route('**/*usability-delay=1',async route=>{await delayedVideo;await route.continue();});
  const held=await page.evaluate(()=>{
    const before=targetFrame.toDataURL();const last=keyframes[kfIdx];
    const video=last.clip.video_file.startsWith('custom01')?'custom02.mp4':'custom01.mp4';
    keyframes[kfIdx]={...last,time:.5,clip:{...last.clip,video_file:video+'?usability-delay=1'}};
    showKeyframeImage(kfIdx);rememberTarget();return before;
  });
  await page.waitForTimeout(500);
  assert.equal(await page.evaluate(()=>{rememberTarget();return targetFrame.toDataURL();}),held);
  assert.equal(await page.evaluate(()=>targetPending),true);releaseVideo();
  await page.waitForFunction(()=>{rememberTarget();return !targetPending;},{},{timeout:15000});
  assert.notEqual(await page.evaluate(()=>targetFrame.toDataURL()),held);
  console.log('PASS previous masked frame held through delayed next video and replaced when decoded');
  await page.reload();try{await page.waitForFunction(()=>typeof phase!=='undefined'&&phase==='detecting_hand'&&cv.readyState>=2,{},{timeout:60000});}catch(e){console.error(await page.locator('body').innerText());console.error(errors,failed);throw e;}
  await page.evaluate(()=>{cancelAnimationFrame(animId);runFinished=true;});await page.waitForTimeout(400);
  const routing=await page.evaluate(async()=>{
    runFinished=false;
    const a=Array.from({length:21},(_,i)=>({x:.15+(i%5)*.065,y:.15+Math.floor(i/5)*.1,z:0}));
    const b=Array.from({length:21},(_,i)=>({x:.7+(i%5)*.025,y:.3+Math.floor(i/5)*.04,z:0}));
    for(let i=0;i<7;i++){onRes({image:cv,multiHandLandmarks:i%2?[a,b]:[b,a],multiHandedness:i%2?[{label:'Left',score:.99},{label:'Right',score:.99}]:[{label:'Right',score:.99},{label:'Left',score:.99}]});await new Promise(r=>setTimeout(r,80));}
    const selected=sessionLog.filter(x=>x.detected),onlyA=selected.every(x=>Math.abs(x.lm[0][0]-.15)<.001);
    const sideSamples=handednessBuffer.every(x=>x.side==='right');
    keyframes=[{},{}];kfIdx=0;targetLm=a.map(p=>[p.x,p.y,p.z]);phase='matching';matchHoldStart=null;
    onRes({image:cv,multiHandLandmarks:[b,a],multiHandedness:[{label:'Right',score:.99},{label:'Left',score:.99}]});
    const selectedGate=matchHoldStart!==null;
    phase='recording';kfIdx=1;videoPlaying=true;curSegFrames=[];recStart=performance.now();
    onRes({image:cv,multiHandLandmarks:[b,a],multiHandedness:[]});
    const selectedRecording=Math.abs(curSegFrames.at(-1).lm[0][0]-.15)<.001;
    segments=[{frames:[{lm:[[1,1]]}]}];curSegFrames=[{lm:[[2,2]]}];matchHoldStart=performance.now();
    onRes({image:cv,multiHandLandmarks:[],multiHandedness:[]});
    const missingNull=sessionLog.at(-1).detected===false&&sessionLog.at(-1).lm===null&&matchHoldStart===null;
    const stream=camStream;await new Promise(r=>setTimeout(r,1800));
    return {onlyA,sideSamples,selectedGate,selectedRecording,count:selected.length,missingNull,invalidated:runInvalidated,phase,segments:segments.length,buffer:curSegFrames.length,hold:matchHoldStart,side:selectedHand,handedness:handednessBuffer.length,cameraKept:camStream===stream&&stream.getVideoTracks()[0].readyState==='live',notice:hint.textContent,selectorState:selector.state};
  });
  assert.ok(routing.onlyA&&routing.sideSamples&&routing.count>0&&routing.missingNull&&!routing.invalidated);
  assert.equal(routing.phase,'detecting_hand');assert.equal(routing.selectorState,'waiting');assert.ok(routing.cameraKept);assert.match(routing.notice,/1.5초 이상 이탈해 재시작/);
  assert.ok(routing.selectedGate&&routing.selectedRecording);
  assert.equal(routing.segments,0);assert.equal(routing.buffer,0);assert.equal(routing.hold,null);assert.equal(routing.side,null);assert.equal(routing.handedness,0);
  console.log('PASS selected-only routing, null missing frame, automatic reset preserving camera',JSON.stringify(routing));
  // A stale sequence response cannot overwrite the new attempt.
  const stale=await page.evaluate(async()=>{
    const oldLoader=loadClipLandmarks;let release;const pending=new Promise(r=>release=r);
    const sample=Object.values(landmarksCache)[0];loadClipLandmarks=async()=>{await pending;return sample;};
    selectedHand='right';const loading=genSequence();restartForHand('tracking_timeout');release();await loading;
    loadClipLandmarks=oldLoader;return {phase,count:keyframes.length};
  });
  assert.equal(stale.phase,'detecting_hand');assert.equal(stale.count,0);console.log('PASS stale async sequence cannot restore discarded attempt');
  await page.evaluate(()=>{
    window.returnPoints=Array.from({length:21},(_,i)=>[.25+(i%5)*.06,.2+Math.floor(i/5)*.1]);
    window.returnTimer=setInterval(()=>{
      const desired=targetLm||window.returnPoints;
      window.returnPoints=window.returnPoints.map((p,i)=>[p[0]+(desired[i][0]-p[0])*.25,p[1]+(desired[i][1]-p[1])*.25]);
      onRes({image:cv,multiHandLandmarks:[window.returnPoints.map(p=>({x:p[0],y:p[1],z:0}))],multiHandedness:[{label:'Left',score:.99}]});
    },70);
  });
  await page.waitForFunction(()=>keyframes.length>0&&(phase==='matching'||phase==='recording'),{},{timeout:15000});
  await page.evaluate(()=>{clearInterval(window.returnTimer);runFinished=true;});
  console.log('PASS returned hand starts fresh challenge without page reload');
  await page.locator('#restartAttempt').click();await page.waitForFunction(()=>typeof phase!=='undefined'&&phase==='detecting_hand'&&cv.readyState>=2,{},{timeout:30000});
  console.log('PASS restart returns to fresh camera and hand acquisition');
  await page.setViewportSize({width:390,height:844});
  await assertLayout(target,own,true);
  await page.locator('#swapHandViews').click();
  await assertLayout(own,target,true);
  if(process.env.CAPTCHA_NARROW_SCREENSHOT)await page.screenshot({path:process.env.CAPTCHA_NARROW_SCREENSHOT});
  console.log('PASS mobile layout; page errors:',JSON.stringify(errors),'failed requests:',JSON.stringify(failed));
  assert.equal(errors.length,0);
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();});
