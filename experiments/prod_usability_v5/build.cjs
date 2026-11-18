// One reproducible prod copy; fail closed when upstream hooks change.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const original = fs.readFileSync(path.join(root,'hand_captcha_prod.html'),'utf8');
const sourceSha256=crypto.createHash('sha256').update(original).digest('hex');
if(sourceSha256!=='0d82dd439fe7976f8b860eb82e654e6f5637b2d7a3fcce2d02f2f99e5f5bea11')throw Error('Baseline prod changed; review provenance before rebuilding');
let html = original;
function once(a,b) {
  if(html.split(a).length !== 2) throw Error('Prod hook changed: '+a.slice(0,80));
  html = html.replace(a,b);
}
once('<head>', '<head>\n    <base href="../../">\n    <link rel="stylesheet" href="experiments/prod_usability_v5/ui.css">');
once("const POOL_BASE = 'https://mukgore.github.io/handcaptcha/';", "const POOL_BASE = new URL('./', document.baseURI).href;");
once('maxNumHands:1','maxNumHands:4');
once('hands.onResults(onRes);','hands.onResults(result => onRes(result));');
once('await loadPoolManifest();', 'await loadPoolManifest();\n    if(!poolManifest || !Array.isArray(poolManifest.clips) || poolManifest.clips.length<2) throw Error("pool_manifest.json: at least two clips required");');
once('const SAVE_LOCAL_JSON = false;', 'const SAVE_LOCAL_JSON = false; // Explicit result-save button below.');
once("version: 'prod_v2_pool'", "version: 'prod_usability_v5'");
// Sequence loading must never publish a previous attempt after an automatic reset.
const sequenceStart=html.indexOf('async function genSequence(){');
const sequenceEnd=html.indexOf('// ===== FRAMING GUIDE',sequenceStart);
const sequence=html.slice(sequenceStart,sequenceEnd);
const isolated=sequence.replace('async function genSequence(){','async function genSequence(){\n    const sequenceEpoch=attemptEpoch;')
  .replace('keyframes = [];','let nextKeyframes = [];').replaceAll('keyframes.push','nextKeyframes.push')
  .replace('const {frames: baseLm, origIdx} = getBaseFromLandmarkData(d, mirror);','if(sequenceEpoch!==attemptEpoch || runInvalidated)return;\n        const {frames: baseLm, origIdx} = getBaseFromLandmarkData(d, mirror);')
  .replace("    const prog = document.getElementById('kfProgress');", "    if(sequenceEpoch!==attemptEpoch || runInvalidated)return;\n    keyframes=nextKeyframes;\n    const prog = document.getElementById('kfProgress');");
html=html.slice(0,sequenceStart)+isolated+html.slice(sequenceEnd);
once('genSequence().then(startRealChallenge);', 'const loadEpoch=attemptEpoch; genSequence().then(() => { if(loadEpoch===attemptEpoch && !runInvalidated) startRealChallenge(); }).catch(error => { if(loadEpoch===attemptEpoch)showAssetError(error); });');
once('function beginNextTransition(){','function beginNextTransition(){\n    const transitionEpoch=attemptEpoch;');
once('const checkLoop = () => {', 'const checkLoop = () => {\n            if(runInvalidated || runFinished || transitionEpoch!==attemptEpoch) return;');
once('setTimeout(showResult, 500);', 'const completionEpoch=attemptEpoch; setTimeout(() => { if(!runInvalidated && completionEpoch===attemptEpoch) showResult(); }, 500);');
once('(async function loop(){ if(cv.readyState>=2) await hands.send({image:cv}); animId = requestAnimationFrame(loop); })();', '(async function loop(){ if(runInvalidated || runFinished)return; try { if(cv.readyState>=2) await hands.send({image:cv}); } catch(e) { invalidateAttempt("inference_error"); return; } if(!runInvalidated && !runFinished) animId = requestAnimationFrame(loop); })();');
once("}catch(e){ document.getElementById('cameraPlaceholder').textContent = '카메라 접근이 거부되었습니다.'; }", "}catch(e){ document.getElementById('cameraPlaceholder').style.display='none'; showHint('카메라를 열 수 없습니다 ('+e.name+'). 주소창 카메라 권한·다른 앱 사용 여부를 확인한 뒤 다시 시작하세요.','waiting',true); }");
once('await initCam();','showGuidance();\n    await initCam();');
once('drawFramingGuideOverlay(performance.now());', '/* Display uses only the existing masked video; no extra pose overlay. */');
once('maybeShowGhostFallback();', '/* Do not expose the hidden target as a landmark ghost. */');
once('sendResult(JSON.stringify(result));', 'saveableResult = {...result, selection: {policy: UsabilitySelection.DEFAULTS, events: selectionEvents.slice()}};\n    document.getElementById("saveResult").disabled = false;\n    sendResult(JSON.stringify(result));');
once("setTimeout(() => location.reload(), 3000);", "document.getElementById('redirectMsg').textContent = '결과 JSON 저장 후 다시 시작할 수 있습니다. 이 실행본은 서버로 전송하지 않습니다.';");
once('\nbootstrap();', '\n/* bootstrap starts after selection and display integration */');
once('</body>', '<script src="experiments/prod_usability_v5/selector.js"></script>\n<script src="experiments/prod_usability_v5/app.js"></script>\n<script>bootstrap().catch(showAssetError);</script>\n</body>');
fs.writeFileSync(path.join(__dirname,'index.html'),html);
fs.writeFileSync(path.join(__dirname,'baseline.json'), JSON.stringify({
  repository:'mukgore/handcaptcha', branch:'work/todo-consolidation-20261103',
  commit:'e03bcfa602500ce7346169181a2344999a07c3d5',
  source:'hand_captcha_prod.html', sha256:sourceSha256
},null,2)+'\n');
console.log('Built experiments/prod_usability_v5/index.html');
