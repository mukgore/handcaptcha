// Study A and B resolve the original clips from the same checkout.
const POOL_BASE = new URL('../../', location.href);
const MATCH_ANGLE_THRESH = 38;
// 한 프레임의 우연한 일치로 즉시 통과하지 않도록, 일치 상태가 이 시간 이상
// 연속 유지되어야 매칭으로 인정한다.
const MATCH_HOLD_MS = 200;
const THRESHOLD = 0.25;
const W2 = {da:0.38, ac:0.37, a:0.25};
const MX = {angle:46.9413, dtw_angle:44.0014, accel:0.1926};
const AT = [[0,5,6],[5,6,7],[6,7,8],[0,9,10],[9,10,11],[10,11,12],[0,13,14],[13,14,15],[14,15,16],[0,17,18],[17,18,19],[18,19,20],[0,1,2],[1,2,3],[2,3,4]];
const LN = ['WRIST','THUMB_CMC','THUMB_MCP','THUMB_IP','THUMB_TIP','INDEX_MCP','INDEX_PIP','INDEX_DIP','INDEX_TIP','MIDDLE_MCP','MIDDLE_PIP','MIDDLE_DIP','MIDDLE_TIP','RING_MCP','RING_PIP','RING_DIP','RING_TIP','PINKY_MCP','PINKY_PIP','PINKY_DIP','PINKY_TIP'];
// ===== 결과 전송 설정 =====
// 전체 JSON 업로드용 Google Apps Script 웹앱 URL. 비워두면 업로드를 건너뛴다.
// Apps Script > 배포 > 새 배포 > 웹앱(액세스: 모든 사용자) 의 /exec URL을 넣을 것.
const UPLOAD_URL = ''; // 예: 'https://script.google.com/macros/s/AKfy.../exec'
// 결과 JSON을 로컬 파일로도 내려받을지 여부. 자동(스크립트 트리거) 다운로드는
// 브라우저가 "다른 이름으로 저장" 대화상자를 강제로 띄우는 경우가 있어(특히
// 전시/키오스크 환경) 매 회차마다 진행을 막을 수 있다. false로 두면 로컬
// 다운로드를 건너뛴다(UPLOAD_URL 서버 전송은 계속 동작).
const SAVE_LOCAL_JSON = false;

// MediaPipe Hands labels handedness assuming the input image is already
// selfie-mirrored. This app always sends the raw (unmirrored) camera frame
// to hands.send(), so the label must be swapped to match the true hand.
// Re-verify against @mediapipe/hands@0.4.1675469240 on-device before shipping.
const HANDEDNESS_SWAP = {Left:'right', Right:'left'};
const HANDEDNESS_MIN_SCORE = 0.7;
const PALM_FACING_MIN = 0.65;
const PALM_HOLD_MS = 450;
const PALM_SAMPLE_GAP_MS = 300;
const PALM_EXAMPLE_MS = 1500;
const MASK_INSTRUCTION_MS = 2000;
const PALM_HINT = '손바닥을 보여주면 곧 시작해요.';
const MASK_HINT = '검은 원 밖으로 보이는 손가락을 보고, 영상 속 손동작을 따라 해 주세요.';

let selectedHand = null;
const pid = 'user_' + Date.now().toString().slice(-4);
let targetLm = null;
let hands = null, camStream = null, animId = null;
let poolManifest = null, landmarksCache = {};
let keyframes = [], kfIdx = 0;
let phase = 'intro';
let recStart = null, segments = [], curSegFrames = [];
let matchHoldStart = null;
let videoPlaying = false;
let palmHold = null;
let sessionLog = [], sessionStart = null;

const byId = id => document.getElementById(id);
const rv = byId('refVideo');
const cv = byId('cameraVideo');

// ===== DATA LOADING (manifest-driven challenge pool, spec §0 "챌린지 풀 확장") =====
// pool_manifest.json only lists clip metadata (clip_id/handedness/paths) --
// each clip's own (potentially large) landmark JSON is fetched lazily, only
// for the handful of clips actually drawn for a session, so this scales to
// however many thousand clips the pool grows to without a large upfront load.
async function loadPoolManifest(){
    const response = await fetch(new URL('pool_manifest.json', POOL_BASE), {signal: AbortSignal.timeout(MEDIA_TIMEOUT_MS)});
    if (!response.ok) throw new Error('Challenge manifest unavailable');
    poolManifest = await response.json();
}
async function loadClipLandmarks(clip){
    if(landmarksCache[clip.clip_id]) return landmarksCache[clip.clip_id];
    const response = await fetch(new URL(clip.landmarks_file, POOL_BASE), {signal: AbortSignal.timeout(MEDIA_TIMEOUT_MS)});
    if (!response.ok) throw new Error(`Landmarks unavailable: ${clip.landmarks_file}`);
    landmarksCache[clip.clip_id] = await response.json();
    return landmarksCache[clip.clip_id];
}
function getBaseFromLandmarkData(d, mirror){
    // mirror: the pool no longer keeps a separately-recorded clip per hand --
    // each clip is recorded once (see clip.handedness) and horizontally
    // mirrored at serve time for users of the opposite hand. Mirroring the
    // COORDINATE DATA itself (not just what's displayed) is required so the
    // pose-matching/scoring comparison is against the same thing the user
    // actually sees on screen, not the original unmirrored recording.
    const info = d.video_info||{}, w=info.width||720, h=info.height||720;
    // 미검출 프레임을 걸러내면 배열 인덱스가 원본 비디오 프레임 번호와 어긋난다.
    // 랜드마크 배열(frames)과 원본 프레임 번호(origIdx)를 나란히 반환해서,
    // 비디오 시킹(time = origIdx/fps)이 항상 실제 영상 프레임과 일치하게 한다.
    const frames=[], origIdx=[];
    d.frames.forEach((f,i)=>{
        if(!f.detected||!f.landmarks_px) return;
        const lm=f.landmarks_px;
        frames.push(LN.map(n => mirror ? [1 - lm[n].x/w, lm[n].y/h] : [lm[n].x/w, lm[n].y/h]));
        origIdx.push(f.frame_idx !== undefined ? f.frame_idx : i);
    });
    return {frames, origIdx};
}
function getInfoFromLandmarkData(d){
    const info = d.video_info || {};
    return {width: info.width||720, height: info.height||720, fps: info.fps||24};
}
function findKeyframes(baseLm){
    if(!baseLm||baseLm.length<10) return [0, Math.floor(baseLm.length/2), baseLm.length-1];
    const vel=[];
    for(let i=1;i<baseLm.length;i++){
        let s=0; for(let j=0;j<21;j++){ const dx=baseLm[i][j][0]-baseLm[i-1][j][0], dy=baseLm[i][j][1]-baseLm[i-1][j][1]; s+=Math.sqrt(dx*dx+dy*dy); }
        vel.push(s/21);
    }
    const w=5, sm=[];
    for(let i=0;i<vel.length;i++){ let s=0,c=0; for(let j=Math.max(0,i-w);j<=Math.min(vel.length-1,i+w);j++){s+=vel[j];c++;} sm.push(s/c); }
    const mins=[0];
    for(let i=5;i<sm.length-5;i++) if(sm[i]<sm[i-1]&&sm[i]<sm[i+1]&&sm[i]<0.005&&(mins.length===0||i-mins[mins.length-1]>15)) mins.push(i);
    mins.push(baseLm.length-1);
    if(mins.length<=4) return mins;
    const step=Math.floor(mins.length/3);
    return [mins[0], mins[step], mins[step*2], mins[mins.length-1]];
}

// ===== POSE MATCHING =====
function ang(p1,j,p2){
    const v1=[p1[0]-j[0],p1[1]-j[1]], v2=[p2[0]-j[0],p2[1]-j[1]];
    const dot=v1[0]*v2[0]+v1[1]*v2[1], m1=Math.sqrt(v1[0]*v1[0]+v1[1]*v1[1])+1e-8, m2=Math.sqrt(v2[0]*v2[0]+v2[1]*v2[1])+1e-8;
    return Math.acos(Math.max(-1,Math.min(1,dot/(m1*m2))))*180/Math.PI;
}
function ppSingle(lm){
    const w=lm[0], n=lm.map(p=>[p[0]-w[0],p[1]-w[1]]);
    const dx=n[9][0],dy=n[9][1],h=Math.max(Math.sqrt(dx*dx+dy*dy),1e-6);
    return n.map(p=>[p[0]/h,p[1]/h]);
}
function angleErr(uLm, tLm){
    let tot=0,c=0; for(const[p,j,d]of AT){ tot+=Math.abs(ang(uLm[p],uLm[j],uLm[d])-ang(tLm[p],tLm[j],tLm[d])); c++; }
    return tot/c;
}

function updateProgress(step) {
    progressBar.setAttribute('aria-valuemax', keyframes.length);
    progressBar.setAttribute('aria-valuenow', step);
    progressBar.firstElementChild.style.width = `${step / keyframes.length * 100}%`;
}
const motionMessages = {
    waiting: ['자세를 맞춰 주세요', '영상 속 손과 같은 자세를 보여 주세요.'],
    missing: ['손이 보이지 않아요', '손 전체가 카메라에 보이게 해 주세요.'],
    loading: ['다음 동작을 준비하고 있어요', ''],
    playing: ['영상 재생 중', '움직이는 손을 함께 따라 해 주세요.'],
    matched: ['자세가 맞았어요', ''],
    complete: ['모든 동작을 완료했어요', '']
};

const PROGRESS_ATTENTION_DELAY_MS = 3000;
let progressAttentionTimer;

function clearProgressAttention() {
    clearTimeout(progressAttentionTimer);
    delete progressBar.dataset.attention;
}

function setMotionStatus(state) {
    const status = byId('motionStatus');
    if (status.dataset.status === state) return;
    clearProgressAttention();
    const [title, detail] = motionMessages[state];
    status.dataset.status = state;
    byId('motionTitle').textContent = title;
    byId('motionDetail').textContent = detail;
    if (state === 'waiting' || state === 'missing') {
        progressAttentionTimer = setTimeout(() => {
            if (trial.dataset.stage === 'perform') progressBar.dataset.attention = '';
        }, PROGRESS_ATTENTION_DELAY_MS);
    }
}

function onTransitionMatched(){
    segments.push({
        fromKf: kfIdx-1, toKf: kfIdx,
        fromClip: keyframes[kfIdx-1].clip.clip_id, toClip: keyframes[kfIdx].clip.clip_id,
        frames: curSegFrames.slice(),
        duration: curSegFrames.length>0 ? curSegFrames[curSegFrames.length-1].t : 0
    });
    if(kfIdx >= keyframes.length-1){
        phase = 'done';
        setMotionStatus('complete');
        markStudy('attempt_completed');
        stopCamera();
        setTimeout(showResult, 500);
    } else {
        beginNextTransition();
    }
}

function showScr(id){ document.querySelectorAll('.screen,.trial-container').forEach(s => s.classList.remove('active')); document.getElementById(id).classList.add('active'); }

// ===== METRICS =====
function pp(f){ if(!f||f.length<3)return null; return f.map(fr=>{ const w=fr[0],n=fr.map(p=>[p[0]-w[0],p[1]-w[1]]); const dx=n[9][0],dy=n[9][1],h=Math.max(Math.sqrt(dx*dx+dy*dy),1e-6); return n.map(p=>[p[0]/h,p[1]/h]); }); }
function rs(d,n){ if(!d||d.length<3)return null; if(d.length===n)return d; const r=[]; for(let t=0;t<n;t++){ const s=t/(n-1)*(d.length-1),lo=Math.floor(s),hi=Math.min(lo+1,d.length-1),f=s-lo; r.push(d[lo].map((p,i)=>[p[0]*(1-f)+d[hi][i][0]*f,p[1]*(1-f)+d[hi][i][1]*f])); } return r; }
function mA(t,b){ const tr=rs(t,b.length); if(!tr)return null; let tot=0,c=0; for(const[p,j,d]of AT){ let s=0; for(let i=0;i<b.length;i++) s+=Math.abs(ang(b[i][p],b[i][j],b[i][d])-ang(tr[i][p],tr[i][j],tr[i][d])); tot+=s/b.length;c++; } return tot/c; }
function mDA(t,b){ if(!t||t.length<3||!b||b.length<3)return null; const tr=rs(t,Math.round(b.length*1.2)); if(!tr)return null; let best=1e9; for(let sh=0;sh<=tr.length-b.length;sh++){ const s=tr.slice(sh,sh+b.length); let tot=0,c=0; for(const[p,j,d]of AT){ let sm=0; for(let i=0;i<b.length;i++) sm+=Math.abs(ang(b[i][p],b[i][j],b[i][d])-ang(s[i][p],s[i][j],s[i][d])); tot+=sm/b.length;c++; } best=Math.min(best,tot/c); } return best; }
function mAc(t,b){ const tr=rs(t,b.length); if(!tr||b.length<5)return null; function ac(d){ const r=[]; for(let i=1;i<d.length-1;i++){ let s=0,c=0; for(let j=1;j<21;j++){ const ax=d[i+1][j][0]-2*d[i][j][0]+d[i-1][j][0],ay=d[i+1][j][1]-2*d[i][j][1]+d[i-1][j][1]; s+=Math.sqrt(ax*ax+ay*ay);c++; } r.push(s/c); } return r; } const ba=ac(b),ta=ac(tr); if(ba.length!==ta.length)return null; let s=0; for(let i=0;i<ba.length;i++)s+=Math.abs(ba[i]-ta[i]); return s/ba.length; }
function es(raw,mx,dr,hi=false){ if(raw===null)return 0; const n=mx>0?raw/mx:0; return Math.max(0,Math.min(1,hi?dr*Math.min(1,n):dr*Math.max(0,1-n))); }

function computeScores(){
    let allUserLm=[], allBaseLm=[];
    for(const seg of segments){
        const det=seg.frames.filter(f=>f.lm!==null).map(f=>f.lm);
        if(det.length<3) continue;
        const fromKf=keyframes[seg.fromKf], toKf=keyframes[seg.toKf];
        let baseSeg;
        if(fromKf.clip.clip_id===toKf.clip.clip_id) baseSeg=fromKf.allBaseLm.slice(fromKf.frameIdx, toKf.frameIdx+1);
        else baseSeg=[...fromKf.allBaseLm.slice(fromKf.frameIdx), ...toKf.allBaseLm.slice(0,toKf.frameIdx+1)];
        allUserLm.push(...det); allBaseLm.push(...baseSeg);
    }
    const tF=segments.reduce((s,seg)=>s+seg.frames.length,0), dC=allUserLm.length, dR=tF>0?dC/tF:0;
    const bPP=pp(allBaseLm), tPP=pp(allUserLm);
    let rA=null, rDA=null, rAc=null;
    if(tPP&&bPP&&tPP.length>=3){ rA=mA(tPP,bPP); rDA=mDA(tPP,bPP); rAc=mAc(tPP,bPP); }
    const sA=es(rA,MX.angle,dR), sDA=es(rDA,MX.dtw_angle,dR), sAc=es(rAc,MX.accel,dR);
    const fin=sDA*W2.da+sAc*W2.ac+sA*W2.a;
    return { totalSegments:segments.length, tF, dC, dR, rA, rDA, rAc, sA, sDA, sAc, captcha:fin };
}

function showResult(){
    const s = computeScores();
    document.getElementById('resSegments').textContent = `${s.totalSegments}개 전환 구간`;
    document.getElementById('resDetection').textContent = `${s.dC}/${s.tF} (${(s.dR*100).toFixed(0)}%)`;
    document.getElementById('resDtwAngle').textContent = s.sDA.toFixed(3);
    document.getElementById('resAccel').textContent = s.sAc.toFixed(3);
    document.getElementById('resAngle').textContent = s.sA.toFixed(3);
    document.getElementById('resFinal').textContent = s.captcha.toFixed(3);

    const v = document.getElementById('verdict');
    if(s.captcha >= THRESHOLD){
        v.className = 'verdict pass';
        v.textContent = `✅ 통과 (${s.captcha.toFixed(3)} ≥ ${THRESHOLD})`;
    } else {
        v.className = 'verdict fail';
        v.textContent = `❌ 차단 (${s.captcha.toFixed(3)} < ${THRESHOLD})`;
    }

    const result = {
        experimentInfo: {participantId: pid, selectedHand, timestamp: Date.now(), version: 'prod_v2_pool_first_use'},
        keyframes: keyframes.map(kf => ({clip: kf.clip.clip_id, frameIdx: kf.frameIdx})),
        segments: segments.map(seg => ({
            fromKf: seg.fromKf, toKf: seg.toKf,
            fromClip: seg.fromClip, toClip: seg.toClip,
            totalFrames: seg.frames.length,
            detectedFrames: seg.frames.filter(f => f.lm !== null).length,
            duration: seg.duration,
            frames: seg.frames
        })),
        scores: {
            detectionRate: s.dR, totalFrames: s.tF, detectedFrames: s.dC,
            raw: {angle: s.rA, dtw_angle: s.rDA, accel: s.rAc},
            estimated: {angle: s.sA, dtw_angle: s.sDA, accel: s.sAc},
            captcha: s.captcha, threshold: THRESHOLD, passed: s.captcha >= THRESHOLD,
            weights: W2
        },
        firstUseEvents: studyEvents.slice(),
        sessionLog
    };

    if(SAVE_LOCAL_JSON){
        const blob = new Blob([JSON.stringify(result, null, 2)], {type: 'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `hand_captcha_${selectedHand}_${pid}_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    showScr('screenResult');

    // 업로드는 백그라운드 best-effort -- 완료를 기다리지 않는다. sendBeacon/keepalive
    // fetch 모두 페이로드 상한(브라우저별 대략 64KB)이 있어 그보다 큰 세션 로그는
    // 끊길 수 있다 -- 그래서 로컬 다운로드를 항상 백업으로 남긴다.
    sendResult(JSON.stringify(result));

    // 설문으로 이동하는 대신, 결과를 잠시 보여준 뒤 CAPTCHA 시작 화면으로 되돌아간다.
    document.getElementById('redirectMsg').textContent = '잠시 후 CAPTCHA를 다시 시작합니다...';
    setTimeout(() => location.reload(), 3000);
}

// 결과 JSON을 서버로 전송(설정된 경우). sendBeacon 우선, 실패 시(주로 페이로드가
// 브라우저별 상한을 넘을 때) keepalive fetch로 폴백해 페이지 이동 후에도 전송이
// 이어지게 한다. no-cors + text/plain으로 보내 CORS preflight를 피한다
// (Apps Script는 e.postData.contents로 원문을 그대로 받아 JSON.parse 하면 됨).
function sendResult(payload){
    if(!UPLOAD_URL) return;
    try{
        const blob = new Blob([payload], {type: 'text/plain;charset=utf-8'});
        if(navigator.sendBeacon && navigator.sendBeacon(UPLOAD_URL, blob)) return;
    }catch(e){}
    fetch(UPLOAD_URL, {
        method: 'POST', mode: 'no-cors', keepalive: true,
        headers: {'Content-Type': 'text/plain;charset=utf-8'},
        body: payload
    }).catch(() => {});
}

const trial = byId('screenTrial');
const cameraButton = byId('cameraButton');
const retryButton = byId('retryButton');
const prepareHint = byId('prepareHint');
const palmExample = byId('palmExample');
const palmMask = byId('palmMask');
const progressBar = byId('kfProgress');
const demo = byId('demoVideo');
const demoFallback = byId('demoFallback');
const MEDIA_TIMEOUT_MS = 12000;
const HANDS_BASE = 'https://unpkg.com/@mediapipe/hands@0.4.1675469240/';
let operation = new AbortController();
let trackingFrame = null;
let tracking = Promise.resolve();
let displayMirrored = false;
let preparationReady = false;
let trialNumber = 0;

function showDemo() {
    const fallback = () => {
        demo.hidden = true;
        demoFallback.hidden = false;
    };
    demo.onerror = fallback;
    demo.onplaying = () => {
        if (phase !== 'intro' && phase !== 'connecting') return;
        demo.hidden = false;
        demoFallback.hidden = true;
    };
    demo.hidden = true;
    demo.src = 'demo.mp4';
    demo.play().catch(fallback);
}

function afterPaint() {
    return new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

function waitForGuide(ms, signal) {
    return new Promise(resolve => {
        const finish = () => {
            clearTimeout(timer);
            signal.removeEventListener('abort', finish);
            resolve();
        };
        const timer = setTimeout(finish, ms);
        signal.addEventListener('abort', finish, {once: true});
    });
}

function withMediaTimeout(promise, signal) {
    return new Promise((resolve, reject) => {
        const cleanup = () => {
            clearTimeout(timeout);
            signal?.removeEventListener('abort', abort);
        };
        const fail = error => { cleanup(); reject(error); };
        const abort = () => fail(signal.reason);
        const timeout = setTimeout(() => fail(new Error('Media operation timed out')), MEDIA_TIMEOUT_MS);
        signal?.addEventListener('abort', abort, {once: true});
        if (signal?.aborted) abort();
        promise.then(value => { cleanup(); resolve(value); }, fail);
    });
}

function waitForMedia(video, ready, signal) {
    return new Promise((resolve, reject) => {
        const events = ['loadedmetadata', 'loadeddata', 'canplay', 'seeked', 'playing', 'error'];
        const finish = error => {
            clearTimeout(timeout);
            events.forEach(event => video.removeEventListener(event, check));
            signal.removeEventListener('abort', abort);
            if (error) reject(error);
            else resolve();
        };
        const abort = () => finish(signal.reason);
        const check = () => {
            if (video.error) finish(video.error);
            else if (ready()) finish();
        };
        const timeout = setTimeout(() => finish(new Error('Media readiness timed out')), MEDIA_TIMEOUT_MS);
        events.forEach(event => video.addEventListener(event, check));
        signal.addEventListener('abort', abort, {once: true});
        if (signal.aborted) abort();
        else check();
    });
}

function cancelOperation() {
    operation.abort();
    operation = new AbortController();
    return operation.signal;
}

function stopCamera() {
    if (animId !== null) cancelAnimationFrame(animId);
    animId = null;
    const stream = camStream;
    camStream = null;
    if (stream) stream.getTracks().forEach(track => track.stop());
    cv.srcObject = null;
}

function resetAttempt() {
    sessionStart = null;
    sessionLog = [];
    segments = [];
    curSegFrames = [];
    recStart = null;
    matchHoldStart = null;
    videoPlaying = false;
    kfIdx = 0;
    selectedHand = null;
    palmHold = null;
}

function showPreparation(text = '') {
    trial.dataset.stage = 'prepare';
    delete trial.dataset.pending;
    delete trial.dataset.masked;
    palmExample.removeAttribute('aria-hidden');
    prepareHint.textContent = PALM_HINT;
    byId('trialTitle').textContent = '‘내 손’ 화면에 손바닥이 보이게 해 주세요.';
    byId('referenceTitle').textContent = '손바닥 예시';
    byId('trialStatus').textContent = text;
    retryButton.hidden = true;
    showScr('screenTrial');
}

function showChallenge() {
    trial.dataset.stage = 'perform';
    palmExample.setAttribute('aria-hidden', 'true');
    byId('trialTitle').textContent = '영상이 움직이면 함께 따라 해 주세요.';
    byId('referenceTitle').textContent = '따라 할 동작';
    byId('trialStatus').textContent = '';
}

function reportFailure(reason, text, reconnect = false) {
    const started = sessionStart !== null;
    markStudy(started ? 'attempt_incomplete' : 'technical_error', {reason, trial: trialNumber});
    cancelOperation();
    clearProgressAttention();
    delete byId('motionStatus').dataset.status;
    rv.pause();
    preparationReady = false;
    resetAttempt();
    phase = reconnect ? 'camera_error' : 'video_error';
    if (reconnect) {
        stopCamera();
        byId('cameraStatus').textContent = text;
        cameraButton.textContent = '다시 연결';
        cameraButton.disabled = false;
        showScr('screenIntro');
        return;
    }
    showPreparation(text);
    retryButton.hidden = false;
}

async function connectCamera() {
    if (phase !== 'intro' && phase !== 'camera_error') return;
    const signal = cancelOperation();
    phase = 'connecting';
    cameraButton.disabled = true;
    byId('cameraStatus').textContent = '카메라 연결 중…';
    markStudy('camera_requested');
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {facingMode: 'user', width: {ideal: 640}, height: {ideal: 480}}
        });
        if (signal.aborted) {
            stream.getTracks().forEach(track => track.stop());
            return;
        }
        camStream = stream;
        const track = stream.getVideoTracks()[0];
        if (!track || track.readyState !== 'live') throw new Error('No live camera track');
        track.addEventListener('ended', () => {
            if (camStream === stream) reportFailure('camera_disconnected', CAMERA_ERROR, true);
        }, {once: true});
        stream.addEventListener('inactive', () => {
            if (camStream === stream) reportFailure('camera_disconnected', CAMERA_ERROR, true);
        }, {once: true});
        displayMirrored = track.getSettings().facingMode === 'user' || track.label.toLowerCase().includes('front');
        cv.style.transform = displayMirrored ? 'scaleX(-1)' : 'none';
        cv.srcObject = stream;
        await Promise.all([withMediaTimeout(cv.play(), signal), waitForMedia(cv, () => cv.readyState >= 2, signal)]);
        if (signal.aborted) return;
        demo.pause();
        showPreparation('동작을 준비하는 중…');
        await afterPaint();
        if (signal.aborted) return;
        markStudy('camera_preview_shown');
        await prepareChallenge();
    } catch (error) {
        if (signal.aborted) return;
        const denied = error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError';
        reportFailure(denied ? 'permission_denied' : 'camera_error',
            denied ? '브라우저에서 카메라를 허용해 주세요.' : CAMERA_ERROR, true);
    }
}

const CAMERA_ERROR = '카메라를 연결할 수 없어요. 연결 상태를 확인해 주세요.';
const VIDEO_LOAD_ERROR = '문제 영상을 불러오지 못했어요.';
const VIDEO_PLAY_ERROR = '문제 영상을 재생할 수 없어요.';
const TRACKING_ERROR = '손 추적을 시작할 수 없어요. 잠시 후 다시 시도해 주세요.';

let initializingTracker;
function initTracking() {
    if (hands) return;
    initializingTracker ??= loadTracker().finally(() => { initializingTracker = null; });
    return initializingTracker;
}

async function loadTracker() {
    if (!window.Hands) {
        const script = document.createElement('script');
        script.src = HANDS_BASE + 'hands.js';
        script.crossOrigin = 'anonymous';
        const loaded = new Promise((resolve, reject) => {
            script.onload = resolve;
            script.onerror = reject;
            document.head.append(script);
        });
        try { await withMediaTimeout(loaded); }
        finally { script.remove(); }
    }
    const tracker = new Hands({locateFile: file => HANDS_BASE + file});
    tracker.setOptions({maxNumHands: 1, modelComplexity: 1, minDetectionConfidence: .35, minTrackingConfidence: .4});
    tracker.onResults(result => {
        const frame = trackingFrame;
        if (frame && frame.stream === camStream && tracker === hands) onRes(result, frame.at);
    });
    await withMediaTimeout(tracker.initialize());
    hands = tracker;
}

function startTracking(stream) {
    if (animId !== null) return;
    const loop = async () => {
        await tracking.catch(() => {});
        if (stream !== camStream) return;
        const tracker = hands;
        if (!tracker) {
            animId = null;
            return;
        }
        if (cv.readyState >= 2) {
            trackingFrame = {stream, at: performance.now()};
            tracking = Promise.resolve().then(() => tracker.send({image: cv}));
            try {
                await tracking;
            } catch {
                if (stream === camStream) {
                    hands = null;
                    animId = null;
                    reportFailure('tracking_error', TRACKING_ERROR);
                }
            } finally {
                trackingFrame = null;
                tracking = Promise.resolve();
            }
        }
        if (stream === camStream && hands) animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
}

async function loadSequence(signal) {
    if (sequence.length) return;
    if (!poolManifest) await loadPoolManifest();
    const clips = orderFirstUseClips(poolManifest?.clips || []);
    if (clips.length !== FIRST_USE_CLIPS.length) throw new Error('First-use clips unavailable');
    const loaded = await Promise.all(clips.map(async clip => {
        const landmarks = await loadClipLandmarks(clip);
        if (!getBaseFromLandmarkData(landmarks, false).frames.length) throw new Error('Clip has no landmarks');
        return {clip, landmarks};
    }));
    if (!signal.aborted) sequence = loaded;
}

let sequence = [];
function configureSequence(hand) {
    const handLabel = hand === 'left' ? 'Left' : 'Right';
    keyframes = sequence.flatMap(({clip, landmarks}) => {
        const mirror = clip.handedness !== handLabel;
        const {frames, origIdx} = getBaseFromLandmarkData(landmarks, mirror);
        const {fps} = getInfoFromLandmarkData(landmarks);
        return findKeyframes(frames).map(frameIdx => ({
            clip, mirror, frameIdx, time: origIdx[frameIdx] / fps,
            baseLm: frames[frameIdx], allBaseLm: frames, fps
        }));
    });
}

async function seekKeyframe(kf, signal) {
    rv.pause();
    const src = new URL(kf.clip.video_file, POOL_BASE).href;
    if (rv.src !== src || rv.error) {
        rv.src = src;
        rv.load();
    }
    await waitForMedia(rv, () => rv.readyState >= 1, signal);
    if (Math.abs(rv.currentTime - kf.time) > .001) rv.currentTime = kf.time;
    await waitForMedia(rv, () => rv.readyState >= 2 && !rv.seeking, signal);
}

async function prepareChallenge() {
    const signal = cancelOperation();
    phase = 'preparing';
    preparationReady = false;
    palmHold = null;
    showPreparation('동작을 준비하는 중…');
    const model = Promise.resolve(initTracking()).then(() => {
        if (!signal.aborted) startTracking(camStream);
        return true;
    }, () => false);
    try {
        await loadSequence(signal);
        if (signal.aborted) return;
        configureSequence('right');
        await seekKeyframe(keyframes[0], signal);
        const modelReady = await model;
        if (signal.aborted) return;
        if (!modelReady) {
            reportFailure('tracking_error', TRACKING_ERROR);
            return;
        }
        preparationReady = true;
        showPreparation();
    } catch {
        if (!signal.aborted) reportFailure('video_load_failed', VIDEO_LOAD_ERROR);
    }
}

function facingPalm(result, aspect) {
    const handedness = result.multiHandedness?.[0];
    const side = HANDEDNESS_SWAP[handedness?.label];
    if (!side || !(handedness.score > HANDEDNESS_MIN_SCORE)) return null;
    const landmarks = result.multiHandLandmarks?.[0];
    const wrist = landmarks?.[0], index = landmarks?.[5], pinky = landmarks?.[17];
    if (!wrist || !index || !pinky) return null;
    // Raw camera coordinates: x right, y down, z away from the camera.
    // Normalized x and z use the image width, while normalized y uses height.
    const ax = index.x - wrist.x, ay = (index.y - wrist.y) * aspect, az = index.z - wrist.z;
    const bx = pinky.x - wrist.x, by = (pinky.y - wrist.y) * aspect, bz = pinky.z - wrist.z;
    const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
    const facing = (side === 'right' ? -nz : nz) / Math.hypot(nx, ny, nz);
    return facing >= PALM_FACING_MIN ? side : null;
}

function observePalm(result, capturedAt) {
    const side = facingPalm(result, cv.videoHeight / cv.videoWidth);
    if (!side) {
        if (palmHold) byId('trialStatus').textContent = '';
        palmHold = null;
        return;
    }
    if (palmHold?.side !== side || capturedAt - palmHold.last > PALM_SAMPLE_GAP_MS) {
        palmHold = {side, first: capturedAt, last: capturedAt};
        byId('trialStatus').textContent = '손바닥 확인 중…';
        return;
    }
    palmHold.last = capturedAt;
    if (capturedAt - palmHold.first >= PALM_HOLD_MS) startChallenge(side);
}

function showTarget(index) {
    const kf = keyframes[index];
    targetLm = kf.baseLm;
    rv.style.transform = kf.mirror ? 'scaleX(-1)' : 'none';
    byId('kfLabel').textContent = `자세 ${index + 1}/${keyframes.length}`;
    updateProgress(index + 1);
}

async function startChallenge(side) {
    if (phase !== 'preparing' || !preparationReady || !camStream) return;
    const {signal} = operation;
    phase = 'starting';
    byId('trialStatus').textContent = '';
    prepareHint.textContent = '손바닥을 확인했어요.';
    trialNumber++;
    markStudy('palm_confirmed', {trial: trialNumber});
    selectedHand = side;
    configureSequence(selectedHand);
    try {
        await waitForGuide(PALM_EXAMPLE_MS, signal);
        if (signal.aborted) return;
        trial.dataset.masked = '';
        await Promise.allSettled(palmMask.getAnimations().map(animation => animation.finished));
        if (signal.aborted) return;
        prepareHint.textContent = MASK_HINT;
        markStudy('mask_instruction_shown', {trial: trialNumber});
        await waitForGuide(MASK_INSTRUCTION_MS, signal);
        if (signal.aborted) return;
        // The first prod target is a paused frame. Movement starts after its match.
        await seekKeyframe(keyframes[0], signal);
        if (signal.aborted) return;
        showTarget(0);
        setMotionStatus('waiting');
        requestAnimationFrame(() => {
            if (signal.aborted) return;
            // Reveal and arm the attempt in the rendering callback for this frame.
            showChallenge();
            sessionStart = performance.now();
            markStudy('problem_shown', {trial: trialNumber, at: sessionStart, clip: keyframes[0].clip.clip_id});
            phase = 'matching';
        });
    } catch {
        if (!signal.aborted) reportFailure('video_load_failed', VIDEO_LOAD_ERROR);
    }
}

function waitForPlaybackFrame(signal) {
    if (!rv.requestVideoFrameCallback) return afterPaint();
    return new Promise((resolve, reject) => {
        const finish = error => {
            clearTimeout(timeout);
            signal.removeEventListener('abort', abort);
            if (error) {
                rv.cancelVideoFrameCallback(callback);
                reject(error);
            } else resolve();
        };
        const abort = () => finish(signal.reason);
        const callback = rv.requestVideoFrameCallback(() => finish());
        const timeout = setTimeout(() => finish(new Error('Playback frame timed out')), 3000);
        signal.addEventListener('abort', abort, {once: true});
    });
}

function beginRecording() {
    recStart = performance.now();
    curSegFrames = [];
    matchHoldStart = null;
    phase = 'recording';
}

async function beginNextTransition() {
    const {signal} = operation;
    phase = 'transition';
    const from = keyframes[kfIdx++];
    const to = keyframes[kfIdx];
    try {
        if (from.clip.clip_id !== to.clip.clip_id) {
            setMotionStatus('loading');
            trial.dataset.pending = '';
            await seekKeyframe(to, signal);
            if (signal.aborted) return;
            showTarget(kfIdx);
            delete trial.dataset.pending;
            await afterPaint();
            if (signal.aborted) return;
            setMotionStatus('waiting');
            beginRecording();
            return;
        }

        showTarget(kfIdx);
        setMotionStatus('playing');
        await seekKeyframe(from, signal);
        if (signal.aborted) return;
        await withMediaTimeout(rv.play(), signal);
        if (signal.aborted) return;
        if (from === keyframes[0]) markStudy('play_accepted', {trial: trialNumber});
        await waitForPlaybackFrame(signal);
        if (signal.aborted) return;
        videoPlaying = true;
        beginRecording();
        const deadline = recStart + (to.time - from.time) * 1000 + 3000;
        const check = () => {
            if (signal.aborted) return;
            if (rv.currentTime >= to.time - .05) {
                rv.pause();
                videoPlaying = false;
                setMotionStatus('waiting');
            } else if (rv.error || rv.ended || performance.now() > deadline) {
                reportFailure('video_play_failed', VIDEO_PLAY_ERROR);
            } else requestAnimationFrame(check);
        };
        check();
    } catch {
        if (!signal.aborted) reportFailure('video_play_failed', VIDEO_PLAY_ERROR);
    }
}

function onRes(result, capturedAt) {
    if (phase === 'preparing') {
        if (preparationReady) observePalm(result, capturedAt);
        return;
    }
    if (sessionStart === null || capturedAt < sessionStart || !['matching', 'recording'].includes(phase)) return;
    const lm = result.multiHandLandmarks?.[0];
    // Preserve prod's scoring coordinate convention independently of the CSS.
    const userLm = lm?.map(point => [displayMirrored ? 1 - point.x : point.x, point.y, point.z]) || null;
    sessionLog.push({t: capturedAt - sessionStart, phase, detected: Boolean(userLm), lm: userLm});
    if (phase === 'recording') {
        if (capturedAt < recStart) return;
        curSegFrames.push({t: capturedAt - recStart, lm: userLm});
        if (videoPlaying) return;
    }
    const matched = userLm && angleErr(ppSingle(userLm), ppSingle(targetLm)) < MATCH_ANGLE_THRESH;
    if (!matched) {
        matchHoldStart = null;
        setMotionStatus(userLm ? 'waiting' : 'missing');
        return;
    }
    matchHoldStart ??= capturedAt;
    setMotionStatus('matched');
    if (capturedAt - matchHoldStart < MATCH_HOLD_MS) return;
    matchHoldStart = null;
    if (phase === 'matching') beginNextTransition();
    else onTransitionMatched();
}

cameraButton.addEventListener('click', connectCamera);
retryButton.addEventListener('click', () => {
    if (phase === 'video_error') prepareChallenge();
});
rv.addEventListener('error', () => {
    if (phase === 'matching' || phase === 'recording') reportFailure('video_play_failed', VIDEO_PLAY_ERROR);
});
window.addEventListener('pagehide', () => {
    if (sessionStart !== null && phase !== 'done') markStudy('attempt_incomplete', {reason: 'page_left', trial: trialNumber});
    cancelOperation();
    clearProgressAttention();
    stopCamera();
});
markStudy('intro_shown');
showDemo();
