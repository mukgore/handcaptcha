/* Camera-space continuity heuristic, never an identity or distance estimate. */
(function(root){
  'use strict';
  const DEFAULTS = Object.freeze({minArea:0.035, exitArea:0.024, stableMs:350,
    missingMs:1500, tieRatio:1.12, maxTravel:0.65, maxScaleRatio:2.4, ambiguityMargin:0.12});
  function candidate(points,index){
    if(!Array.isArray(points)||points.length!==21||points.some(p=>!p||
      ![p.x,p.y,p.z].every(Number.isFinite)||p.x<0||p.x>1||p.y<0||p.y>1))return null;
    const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
    const box={x:Math.min(...xs),y:Math.min(...ys),width:Math.max(...xs)-Math.min(...xs),height:Math.max(...ys)-Math.min(...ys)};
    const area=box.width*box.height;
    return area>1e-6?{points,index,box,area,cx:box.x+box.width/2,cy:box.y+box.height/2}:null;
  }
  function distance(a,b,c){
    const ratio=Math.max(a.area,b.area)/Math.min(a.area,b.area);
    const travel=Math.hypot(a.cx-b.cx,a.cy-b.cy)/Math.sqrt(a.area);
    if(ratio>c.maxScaleRatio||travel>c.maxTravel)return Infinity;
    let shape=0;
    for(let i=0;i<21;i++)shape+=Math.hypot((a.points[i].x-a.cx)/Math.sqrt(a.area)-(b.points[i].x-b.cx)/Math.sqrt(b.area),
      (a.points[i].y-a.cy)/Math.sqrt(a.area)-(b.points[i].y-b.cy)/Math.sqrt(b.area));
    return travel+shape/21;
  }
  class Selector{
    constructor(options={}){this.config={...DEFAULTS,...options};this.reset();}
    reset(){this.state='waiting';this.previous=null;this.since=null;this.lastSeen=null;this.lastTime=null;}
    update(hands,now){
      if(!Number.isFinite(now)||this.lastTime!==null&&now<this.lastTime)throw Error('Monotonic time required');
      const gap=this.lastTime===null?0:now-this.lastTime;this.lastTime=now;
      const c=this.config,all=(hands||[]).map(candidate).filter(Boolean);
      const out=(hand,reason)=>({state:this.state,ready:this.state==='selected'&&!!hand,hand,reason});
      if(this.state==='lost')return out(null,'restart_required');
      if(this.state==='selected'){
        if(now-this.lastSeen>c.missingMs){this.state='lost';return out(null,'tracking_timeout');}
        const ranked=all.map(hand=>({hand,d:distance(this.previous,hand,c)})).filter(x=>Number.isFinite(x.d)).sort((a,b)=>a.d-b.d);
        if(ranked.length>1&&ranked[1].d-ranked[0].d<=c.ambiguityMargin){this.state='lost';return out(null,'ambiguous_crossing');}
        if(!ranked.length||ranked[0].hand.area<c.exitArea)return out(null,'missing_or_small');
        this.previous=ranked[0].hand;this.lastSeen=now;return out(this.previous,'tracking');
      }
      const valid=all.filter(h=>h.area>=c.minArea).sort((a,b)=>b.area-a.area);
      if(!valid.length||valid.length>1&&valid[0].area/valid[1].area<c.tieRatio){
        this.state='waiting';this.previous=null;this.since=null;return out(null,valid.length?'similar_sizes':'too_small_or_absent');
      }
      const largest=valid[0];
      // Acquisition also requires an unambiguous match: do not accumulate across a crossing.
      const near=this.previous?all.filter(h=>Number.isFinite(distance(this.previous,h,c))):[];
      if(!this.previous||gap>200||!Number.isFinite(distance(this.previous,largest,c))||near.length>1)this.since=now;
      this.previous=largest;this.state=now-this.since>=c.stableMs?'selected':'stabilizing';
      if(this.state==='selected')this.lastSeen=now;
      return out(largest,this.state);
    }
  }
  const api={Selector,candidate,DEFAULTS};
  if(typeof module!=='undefined')module.exports=api;else root.UsabilitySelection=api;
})(globalThis);
