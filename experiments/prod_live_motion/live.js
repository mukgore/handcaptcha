'use strict';

const motionModes = { '3d': '실시간 3D', '2d': '실시간 2D', recorded: '기존 촬영 영상' };
const modeUrl = new URL(location.href);
const requestedMode = modeUrl.searchParams.get('motion');
const motionMode = Object.hasOwn(motionModes, requestedMode) ? requestedMode : '3d';
document.getElementById('screenTrial').classList.add('live-motion');
const modeControl = document.createElement('label');
modeControl.className = 'motion-control';
modeControl.append('목표 영상 ');
const modeSelect = document.createElement('select');
for (const [value, text] of Object.entries(motionModes)) modeSelect.add(new Option(text, value));
modeSelect.value = motionMode;
modeSelect.addEventListener('change', () => {
  modeUrl.searchParams.set('motion', modeSelect.value);
  location.assign(modeUrl);
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
  liveTarget = { keyframe, start: keyframe.time, end, startedAt: performance.now(), epoch: attemptEpoch, drawnAt: -1 };
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
  if (time === liveTarget.drawnAt) return;
  LiveMotion.paint(targetFrame, keyframe.clip, time, keyframe.mirror);
  liveTarget.drawnAt = time;
  targetPending = false;
  targetPlaceholder.hidden = true;
};
