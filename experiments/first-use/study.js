const FIRST_USE_CLIPS = ['custom01', 'custom03'];
const firstUseStudy = new URLSearchParams(location.search).get('study') === 'first-use';
const studyEvents = [];

function orderFirstUseClips(clips) {
    return FIRST_USE_CLIPS.map(id => clips.find(clip => clip.clip_id === id)).filter(Boolean);
}

function markStudy(event, detail = {}) {
    const {at = performance.now(), ...fields} = detail;
    studyEvents.push({event, ms: Math.round(at), ...fields});
    if (firstUseStudy) performance.mark('handcaptcha:' + event, {startTime: at, detail: fields});
}
