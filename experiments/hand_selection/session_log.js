/* Local, bounded, coordinate-free evaluation events. Export requires a click. */
(function(root) {
  'use strict';
  const events=new Set(['preparation_started','selection_stabilizing','selected','lost',
    'palm_self_report','attempt_started','attempt_finished','technical_error','aborted','reselect','ui_configured']);
  const reasons=new Set(['camera_or_detector_error','detector_error','user_reset','pagehide','selection_lost','user_finished']);
  const outcomes=new Set(['demo_finished','aborted','technical_error']);
  const validators={reason:v=>reasons.has(v),outcome:v=>outcomes.has(v),
    trial_index:v=>Number.isInteger(v)&&v>0&&v<=1000000,
    ui_condition:v=>['split','overlay'].includes(v),guide_hand:v=>['left','right'].includes(v),
    mirror:v=>typeof v==='boolean',palm_confirmed:v=>typeof v==='boolean',
    opacity:v=>Number.isFinite(v)&&v>=0&&v<=1};
  class SessionLog {
    constructor({clock=()=>performance.now(),limit=1000}={}) {
      if(!Number.isInteger(limit)||limit<1)throw Error('Invalid event limit');
      this.clock=clock;this.start=clock();this.limit=limit;this.events=[];this.truncated=false;
    }
    record(event,fields={}) {
      if(!events.has(event))throw Error('Unknown event');
      for(const [key,value] of Object.entries(fields))
        if(!validators[key]||!validators[key](value))throw Error('Unexpected event field');
      if(this.events.length>=this.limit){this.truncated=true;return;}
      const elapsed=this.clock()-this.start;
      if(!Number.isFinite(elapsed))throw Error('Invalid monotonic clock');
      const t_ms=Math.max(0,this.events.at(-1)?.t_ms||0,Math.round(elapsed));
      this.events.push({t_ms,event,...fields});
    }
    snapshot() {
      return JSON.parse(JSON.stringify({schema_version:1,protocol_version:'palm_guidance_v1',
        endpoint:'unscored_local_demo',palm_assessment:'user_self_report_only',
        truncated:this.truncated,events:this.events}));
    }
  }
  const api={SessionLog};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.HandGuidance=api;
})(typeof globalThis==='undefined'?this:globalThis);
