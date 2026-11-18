const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const source = path.join(__dirname, '../prod_usability_v4/index.html');
const baseline = fs.readFileSync(source, 'utf8').replaceAll('\r\n', '\n');
const digest = crypto.createHash('sha256').update(baseline).digest('hex');
if (digest !== '5d06d5d7c129585c068bd60ff25fab3c2bb2c007699a7ca4055d547319fe0ae8') {
  throw new Error('Review changes to the V4 baseline before rebuilding');
}
let html = baseline;

function replace(original, replacement) {
  if (html.split(original).length !== 2) throw new Error('V4 hook changed: ' + original);
  html = html.replace(original, replacement);
}

replace('<title>손 동작 CAPTCHA</title>', '<title>손동작 CAPTCHA · 실시간 생성</title>');
replace('    <base href="../../">', '    <base href="../../">\n    <link rel="stylesheet" href="experiments/prod_live_motion/live.css">');
replace('    if(landmarksCache[clip.clip_id])', '    if(clip.landmarks) return clip.landmarks;\n    if(landmarksCache[clip.clip_id])');
replace('    const candidates = poolManifest && poolManifest.clips || [];',
  "    const candidates = motionMode === 'recorded' ? poolManifest.clips : LiveMotion.createChallenge(LN);");
replace('    const shuffled = [...candidates].sort(() => Math.random()-0.5);',
  "    const shuffled = motionMode === 'recorded' ? [...candidates].sort(() => Math.random()-0.5) : candidates;");
replace('const kfIdxs = findKeyframes(baseLm);', 'const kfIdxs = clip.keyframeIndices ?? findKeyframes(baseLm);');
replace('    const src = POOL_BASE + kf.clip.video_file;', `    if(kf.clip.frames){
        setLiveTarget(kf);
        updateDots(idx);
        return;
    }
    const src = POOL_BASE + kf.clip.video_file;`);
replace('        rv.currentTime = fromKf.time;\n        rv.play();', `        if(toKf.clip.frames){
            setLiveTarget(fromKf, toKf.time);
        } else {
            rv.currentTime = fromKf.time;
            rv.play().catch(error => {
                if(transitionEpoch === attemptEpoch && !runInvalidated && !runFinished) showAssetError(error);
            });
        }`);
replace('            if(rv.currentTime >= stopTime - 0.05 || rv.error || performance.now() > playDeadline){', `            const arrived = toKf.clip.frames ? liveTime() >= stopTime : rv.currentTime >= stopTime - 0.05 || rv.error;
            if(arrived || performance.now() > playDeadline){`);
replace("                rv.pause();\n                videoPlaying = false;", `                if(toKf.clip.frames) setLiveTarget(toKf);
                else rv.pause();
                videoPlaying = false;`);
replace("version: 'prod_usability_v4'",
  "version: 'prod_live_motion_v3', motion_source: motionMode, motion_sources: [...presentedModes]");
replace('    await loadPoolManifest();\n    if(!poolManifest || !Array.isArray(poolManifest.clips) || poolManifest.clips.length<2) throw Error("pool_manifest.json: at least two clips required");', `    if(motionMode === 'recorded'){
        await loadPoolManifest();
        if(!poolManifest || !Array.isArray(poolManifest.clips) || poolManifest.clips.length<2) throw Error("pool_manifest.json: at least two clips required");
    }`);
replace('<script>bootstrap().catch(showAssetError);</script>', `<script src="experiments/prod_live_motion/motion.js?v=3"></script>
<script src="experiments/prod_live_motion/live.js?v=2"></script>
<script>bootstrap().catch(showAssetError);</script>`);
fs.writeFileSync(path.join(__dirname, 'index.html'), html);
