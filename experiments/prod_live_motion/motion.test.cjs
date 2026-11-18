const assert = require('node:assert/strict');
const test = require('node:test');
const { createChallenge, maskPasses, mask } = require('./motion.js');

const names = Array.from({ length: 21 }, (_, i) => 'joint' + i);
function randomFromSeed(seed) {
  return () => {
    seed = (Math.imul(1664525, seed) + 1013904223) >>> 0;
    return seed / 2 ** 32;
  };
}

test('randomized challenges keep both clips covered, visible, and articulated in three dimensions', () => {
  assert.deepEqual(mask, { x: 258, y: 210, r: 90 });
  const patterns = new Set(), durations = new Set();
  let frameCount = 0;
  for (let seed = 0; seed < 128; seed++) {
    const clips = createChallenge(names, randomFromSeed(seed));
    assert.equal(clips.length, 2);
    assert.notEqual(clips[0].motion, clips[1].motion);
    for (const clip of clips) {
      patterns.add(clip.motion);
      durations.add(clip.frames.length);
      assert.ok(clip.frames.every(maskPasses));
      assert.equal(clip.frames.length, clip.keyframeIndices.at(-1) + 1);
      assert.deepEqual(clip.landmarks.frames.at(-1).landmarks_px.joint20, clip.frames.at(-1)[20]);
      const [start, peak] = clip.keyframeIndices.map(index => clip.frames[index]);
      assert.ok(peak.some((p, i) => Math.abs(p.x - start[i].x) > 2 && Math.abs(p.z - start[i].z) > 10));
      for (const points of [start, peak]) {
        const a = points[9], b = points[10];
        assert.ok(Math.abs(Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) - 43) < 1e-9);
      }
      frameCount += clip.frames.length;
    }
  }
  assert.equal(patterns.size, 4);
  assert.ok(durations.size > 10);
  assert.ok(frameCount > 35000);
});
