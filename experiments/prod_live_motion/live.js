'use strict';

const motionModes = { '3d': '실시간 3D', '2d': '실시간 2D', recorded: '기존 촬영 영상' };
const modeUrl = new URL(location.href);
const requestedMode = modeUrl.searchParams.get('motion');
let motionMode = Object.hasOwn(motionModes, requestedMode) ? requestedMode : '3d';
const presentedModes = new Set();
document.getElementById('screenTrial').classList.add('live-motion');
const modeControl = document.createElement('label');
modeControl.className = 'motion-control';
modeControl.append('목표 영상 ');
const modeSelect = document.createElement('select');
for (const [value, text] of Object.entries(motionModes)) modeSelect.add(new Option(text, value));
modeSelect.value = motionMode;
modeSelect.addEventListener('change', () => {
  const nextMode = modeSelect.value;
  modeUrl.searchParams.set('motion', nextMode);
  if (motionMode === 'recorded' || nextMode === 'recorded') {
    location.assign(modeUrl);
    return;
  }
  motionMode = nextMode;
  history.replaceState(null, '', modeUrl);
  rememberTarget();
});
modeControl.append(modeSelect);
controls.prepend(modeControl);
const experimentLabel = document.createElement('p');
experimentLabel.className = 'motion-caption';
experimentLabel.textContent = '가림 손동작 체험 · 결과는 이 브라우저에서 계산됩니다';
controls.after(experimentLabel);

let liveTarget = null;
const openingPreviewMs = 500;
const openingFadeMs = 500;

function targetPreviewActive() {
  return liveTarget?.epoch === attemptEpoch && liveTarget.drawnOpacity !== 1;
}

function liveTime() {
  return Math.min(liveTarget.end, liveTarget.start + (performance.now() - liveTarget.startedAt) / 1000);
}

function setLiveTarget(keyframe, end = keyframe.time) {
  const newAttempt = liveTarget?.epoch !== attemptEpoch;
  if (newAttempt) presentedModes.clear();
  const openingPose = newAttempt && keyframe === keyframes[0] && end === keyframe.time;
  liveTarget = { keyframe, start: keyframe.time, end, startedAt: performance.now(), epoch: attemptEpoch,
    previewStartedAt: openingPose ? null : undefined, drawnAt: -1, drawnMode: null, drawnOpacity: null };
  rememberTarget();
}

const showV5Guidance = showGuidance;
showGuidance = function () {
  // V5 checks the MP4 element for buffering. Generated frames use the canvas.
  if (motionMode !== 'recorded' && phase === 'recording' && videoPlaying && !targetPending &&
      frameSelection?.ready && !runInvalidated && !runFinished && !assetError) {
    showHint('따라 할 손을 보고 같은 동작을 해보세요.','playing');
    return;
  }
  showV5Guidance();
};

const rememberRecordedTarget = rememberTarget;
rememberTarget = function () {
  if (motionMode === 'recorded') {
    rememberRecordedTarget();
    return;
  }
  if (!liveTarget || liveTarget.epoch !== attemptEpoch) return;
  const { keyframe } = liveTarget;
  const time = Math.floor(liveTime() * keyframe.fps + 1e-6) / keyframe.fps;
  const start = liveTarget.previewStartedAt;
  const opacity = start === undefined ? 1 : start === null ? 0 :
    Math.min(1, Math.max(0, (performance.now() - start - openingPreviewMs) / openingFadeMs));
  if (time === liveTarget.drawnAt && motionMode === liveTarget.drawnMode && opacity === liveTarget.drawnOpacity) return;
  LiveMotion.paint(targetFrame, keyframe.clip, time, keyframe.mirror, motionMode, opacity);
  if (start === null) liveTarget.previewStartedAt = performance.now();
  liveTarget.drawnAt = time;
  liveTarget.drawnMode = motionMode;
  liveTarget.drawnOpacity = opacity;
  presentedModes.add(motionMode);
  targetPending = false;
  targetPlaceholder.hidden = true;
};
