// Development regression only. Synthetic camera/landmarks do not establish human usability.
const {chromium}=require(process.env.PLAYWRIGHT_CORE||'../../../qa/node_modules/playwright-core');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base='http://127.0.0.1:8770/experiments/prod_usability/';
let browser;
(async()=>{
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,
    args:['--disable-gpu','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
  const context=await browser.newContext({viewport:{width:1280,height:900},acceptDownloads:true});
  const page=await context.newPage(),errors=[],failed=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()}));
  await page.goto(base);
  await page.waitForFunction(()=>typeof phase!=='undefined'&&phase==='detecting_hand'&&cv.readyState>=2,{},{timeout:60000});
  console.log('PASS real page + pinned MediaPipe model + synthetic camera + local manifest');
  await page.evaluate(()=>{cancelAnimationFrame(animId);runFinished=true;});await page.waitForTimeout(500);
  await page.evaluate(()=>{
    runFinished=false;window.testPoints=Array.from({length:21},(_,i)=>[.25+(i%5)*.06,.2+Math.floor(i/5)*.1]);window.testTimer=setInterval(()=>{
      if(runInvalidated||runFinished)return;
      const desired=targetLm||window.testPoints;
      const points=window.testPoints=window.testPoints.map((p,i)=>[p[0]+(desired[i][0]-p[0])*.25,p[1]+(desired[i][1]-p[1])*.25]);
      const lm=points.map(p=>({x:p[0],y:p[1],z:0}));
      onRes({image:cv,multiHandLandmarks:[lm],multiHandedness:[{label:'Left',score:.99}]});
    },70);
  });
  await page.waitForFunction(()=>typeof keyframes!=='undefined'&&keyframes.length>0&&rv.readyState>=2,{},{timeout:20000});
  await page.waitForTimeout(800);await page.screenshot({path:path.join(__dirname,'preview.png')});
  console.log('DISPLAY',await page.evaluate(()=>({canvas:[cc.width,cc.height],video:[rv.videoWidth,rv.videoHeight],camera:[cv.videoWidth,cv.videoHeight],pixel:[...ctx.getImageData(100,100,1,1).data]})));
  try{await page.waitForFunction(()=>runFinished&&document.getElementById('screenResult').classList.contains('active'),{},{timeout:60000});}
  catch(e){console.error(await page.evaluate(()=>({phase,runInvalidated,selectorState:selector.state,kfIdx,events:selectionEvents,body:document.body.innerText})));throw e;}
  const result=await page.evaluate(()=>({scores:saveableResult.scores,segments:saveableResult.segments.length,frames:saveableResult.sessionLog.length}));
  assert.ok(result.segments>0);assert.ok(result.frames>0);assert.ok(Number.isFinite(result.scores.captcha));
  console.log('PASS gate → real video playback → record → score → result',JSON.stringify(result));
  const download=page.waitForEvent('download');await page.locator('#saveResult').click();const d=await download;
  assert.ok(JSON.parse(fs.readFileSync(await d.path(),'utf8')).selection);console.log('PASS result JSON download');
  await page.evaluate(()=>clearInterval(window.testTimer));
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
    await new Promise(r=>setTimeout(r,650));
    return {onlyA,sideSamples,selectedGate,selectedRecording,count:selected.length,missingNull,invalidated:runInvalidated,phase,segments:segments.length,buffer:curSegFrames.length,hold:matchHoldStart,side:selectedHand,handedness:handednessBuffer.length};
  });
  assert.ok(routing.onlyA&&routing.sideSamples&&routing.count>0&&routing.missingNull&&routing.invalidated);
  assert.ok(routing.selectedGate&&routing.selectedRecording);
  assert.equal(routing.segments,0);assert.equal(routing.buffer,0);assert.equal(routing.hold,null);assert.equal(routing.side,null);assert.equal(routing.handedness,0);
  console.log('PASS selected-only routing, null missing frame, atomic invalidation',JSON.stringify(routing));
  await page.locator('#restartAttempt').click();await page.waitForFunction(()=>typeof phase!=='undefined'&&phase==='detecting_hand'&&cv.readyState>=2,{},{timeout:30000});
  console.log('PASS restart returns to fresh camera and hand acquisition');
  await page.setViewportSize({width:390,height:844});assert.ok(await page.locator('.camera-area').isVisible());
  console.log('PASS mobile layout; page errors:',JSON.stringify(errors),'failed requests:',JSON.stringify(failed));
  assert.equal(errors.length,0);
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();});
