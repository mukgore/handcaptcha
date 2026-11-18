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
function liveTime() {
  return Math.min(liveTarget.end, liveTarget.start + (performance.now() - liveTarget.startedAt) / 1000);
}

function setLiveTarget(keyframe, end = keyframe.time) {
  if (!liveTarget || liveTarget.epoch !== attemptEpoch) presentedModes.clear();
  liveTarget = { keyframe, start: keyframe.time, end, startedAt: performance.now(), epoch: attemptEpoch, drawnAt: -1, drawnMode: null };
  rememberTarget();
}

const rememberRecordedTarget = rememberTarget;
rememberTarget = function () {
  if (motionMode === 'recorded') {
    rememberRecordedTarget();
    return;
  }
  if (!liveTarget || liveTarget.epoch !== attemptEpoch) return;
  const { keyframe } = liveTarget;
  const time = Math.floor(liveTime() * keyframe.fps + 1e-6) / keyframe.fps;
  if (time === liveTarget.drawnAt && motionMode === liveTarget.drawnMode) return;
  LiveMotion.paint(targetFrame, keyframe.clip, time, keyframe.mirror, motionMode);
  liveTarget.drawnAt = time;
  liveTarget.drawnMode = motionMode;
  presentedModes.add(motionMode);
  targetPending = false;
  targetPlaceholder.hidden = true;
};
