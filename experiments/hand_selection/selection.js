/* Experimental camera-space selection. Geometry is a heuristic, not identity. */
(function (root) {
  'use strict';
  const DEFAULTS = Object.freeze({stableFrames: 8, tieRatio: 1.1,
    maxTravel: 0.35, maxScaleRatio: 2, ambiguityMargin: 0.08});

  function candidate(points, index) {
    if (!Array.isArray(points) || points.length !== 21 || points.some(p =>
      !p || !Number.isFinite(p.x) || !Number.isFinite(p.y) ||
      !Number.isFinite(p.z) ||
      p.x < 0 || p.x > 1 || p.y < 0 || p.y > 1)) return null;
    const xs = points.map(p => p.x), ys = points.map(p => p.y);
    const box = {x: Math.min(...xs), y: Math.min(...ys),
      width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys)};
    const area = box.width * box.height;
    if (!(area > 1e-6)) return null;
    return {index, points: points.map(p => ({x:p.x,y:p.y,z:p.z})), box, area, cx: box.x + box.width / 2,
      cy: box.y + box.height / 2};
  }

  function distance(a, b, config) {
    const scaleRatio = Math.max(a.area, b.area) / Math.min(a.area, b.area);
    const travel = Math.hypot(a.cx - b.cx, a.cy - b.cy) / Math.sqrt(a.area);
    if (scaleRatio > config.maxScaleRatio || travel > config.maxTravel) return Infinity;
    // Relative shape helps avoid matching another same-side hand by label alone.
    let shape = 0;
    for (let i = 0; i < 21; i++) shape += Math.hypot(
      (a.points[i].x-a.cx)/Math.sqrt(a.area) - (b.points[i].x-b.cx)/Math.sqrt(b.area),
      (a.points[i].y-a.cy)/Math.sqrt(a.area) - (b.points[i].y-b.cy)/Math.sqrt(b.area));
    return travel + shape / 21;
  }

  class HandSelector {
    constructor(options = {}) {
      this.config = {...DEFAULTS, ...options};
      const c = this.config;
      if (!Number.isInteger(c.stableFrames) || c.stableFrames < 1 ||
        ![c.tieRatio,c.maxTravel,c.maxScaleRatio,c.ambiguityMargin].every(Number.isFinite) ||
        c.tieRatio <= 1 || c.maxTravel <= 0 || c.maxScaleRatio <= 1 || c.ambiguityMargin < 0)
        throw new Error('Invalid hand selection configuration');
      this.reset();
    }
    reset() { this.state = 'waiting'; this.previous = null; this.count = 0; }
    update(hands) {
      if (this.state === 'lost') return this.result(null, 'reselect_required');
      const candidates = (Array.isArray(hands) ? hands : [])
        .map(candidate).filter(Boolean);
      if (this.state === 'selected') {
        const ranked = candidates.map(c => ({c, d: distance(this.previous,c,this.config)}))
          .filter(x => Number.isFinite(x.d)).sort((a,b) => a.d-b.d);
        if (!ranked.length || (ranked.length > 1 &&
          ranked[1].d-ranked[0].d <= this.config.ambiguityMargin)) {
          this.state = 'lost';
          return this.result(null, 'reselect_required');
        }
        this.previous = ranked[0].c;
        return this.result(this.previous, 'tracking');
      }
      candidates.sort((a,b) => b.area-a.area);
      if (!candidates.length || (candidates.length > 1 &&
        candidates[0].area / candidates[1].area < this.config.tieRatio)) {
        this.previous = null; this.count = 0; this.state = 'waiting';
        return this.result(null, candidates.length ? 'similar_sizes' : 'no_valid_hand');
      }
      const largest = candidates[0];
      this.count = this.previous && Number.isFinite(distance(this.previous,largest,this.config))
        ? this.count + 1 : 1;
      this.previous = largest;
      this.state = this.count >= this.config.stableFrames ? 'selected' : 'stabilizing';
      return this.result(largest, this.state);
    }
    result(c, reason) {
      return {state: this.state, reason, index: c ? c.index : null,
        points: c ? c.points : null, box: c ? c.box : null,
        ready: this.state === 'selected', stableCount: this.count};
    }
  }
  const api = {HandSelector, candidate, DEFAULTS};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.HandSelection = api;
})(typeof globalThis === 'undefined' ? this : globalThis);
