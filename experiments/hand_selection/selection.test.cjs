const test = require('node:test');
const assert = require('node:assert/strict');
const {HandSelector, candidate} = require('./selection.js');
function hand(x,y,size) { return Array.from({length:21}, (_,i) =>
  ({x:x+(i%5)/4*size, y:y+Math.floor(i/5)/4*size, z:0})); }
function selector() { return new HandSelector({stableFrames:2}); }
test('largest wins regardless of detector ordering; waits for stability', () => {
  const s=selector(), small=hand(.05,.1,.1), large=hand(.5,.1,.3);
  assert.equal(s.update([small,large]).ready,false);
  const r=s.update([large,small]); assert.equal(r.index,0); assert.equal(r.ready,true);
});
test('array reordering and a larger distant distractor cannot switch selection', () => {
  const s=selector(), h=hand(.1,.1,.2), other=hand(.6,.5,.15);
  s.update([h,other]); s.update([other,h]);
  assert.equal(s.update([hand(.55,.45,.4),hand(.11,.1,.2)]).index,1);
});
test('loss latches until explicit reset, even if another hand remains', () => {
  const s=selector(), h=hand(.1,.1,.2); s.update([h]); s.update([h]);
  assert.equal(s.update([hand(.7,.7,.2)]).state,'lost');
  assert.equal(s.update([h]).points,null);
  s.reset(); s.update([h]); assert.equal(s.update([h]).ready,true);
});
test('crossing indistinguishable candidates requires reselect', () => {
  const s=selector(), h=hand(.1,.1,.2); s.update([h]); s.update([h]);
  assert.equal(s.update([h,hand(.105,.1,.2)]).state,'lost');
});
test('ties do not use detector order as identity', () => {
  const s=selector(); assert.equal(s.update([hand(.1,.1,.2),hand(.6,.1,.2)]).state,'waiting');
});
test('nonfinite, cropped, malformed and degenerate hands are rejected', () => {
  for (const h of [[],hand(.9,.9,.3),hand(.1,.1,0),hand(.1,.1,.2).map(p=>({...p,x:NaN}))])
    assert.equal(candidate(h,0),null);
});
test('unstable initial candidate restarts count', () => {
  const s=selector(); s.update([hand(.1,.1,.2)]);
  assert.equal(s.update([hand(.6,.6,.3)]).ready,false);
});
test('single-hand tracking follows small movement', () => {
  const s=selector(), h=hand(.1,.1,.2); s.update([h]); s.update([h]);
  assert.equal(s.update([hand(.12,.11,.21)]).ready,true);
});
test('invalid policy fails immediately', () => {
  for (const config of [{stableFrames:0},{tieRatio:1},{maxTravel:NaN}])
    assert.throws(()=>new HandSelector(config));
});
test('detector reuse of point arrays cannot rewrite the previous observation', () => {
  const s=selector(), h=hand(.1,.1,.2);s.update([h]);s.update([h]);
  h.forEach(p=>p.x+=.5);
  assert.equal(s.update([h]).state,'lost');
});
