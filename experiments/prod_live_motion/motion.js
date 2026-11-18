'use strict';

// The 3D path follows motion_fixture/generate.py: fixed bone lengths, cumulative
// flexion, and a fixed camera. These are authored meshes, with no MANO assets.
const LiveMotion = (() => {
  const WIDTH = 512, HEIGHT = 420, FPS = 30, INTERVAL = 36;
  const MASK = { x: 258, y: 180, r: 69 };
  const FINGERS = [
    { base: 1, origin: [-47, -62], lengths: [31, 24, 22], spread: -.97, width: 14 },
    { base: 5, origin: [-59, -5], lengths: [44, 30, 23], spread: -.19, width: 14 },
    { base: 9, origin: [0, -1], lengths: [44, 31, 25], spread: 0, width: 15 },
    { base: 13, origin: [55, -9], lengths: [42, 29, 22], spread: .21, width: 14 },
    { base: 17, origin: [83, -26], lengths: [33, 23, 19], spread: .34, width: 12 },
  ];
  const KEYFRAMES = [0, INTERVAL, 2 * INTERVAL, 3 * INTERVAL];
  const clamp = (n, min, max) => Math.min(max, Math.max(min, n));

  function project(point, mode) {
    const [x, y, z] = point;
    if (mode === '2d') return { x: 258 + x, y: 225 - y, z: 0 };
    // Fixed oblique orthographic camera, after articulation in three dimensions.
    const yaw = -.14, pitch = .36;
    const xx = Math.cos(yaw) * x + Math.sin(yaw) * z;
    const zz = Math.cos(yaw) * z - Math.sin(yaw) * x;
    return { x: 258 + xx, y: 225 - (Math.cos(pitch) * y - Math.sin(pitch) * zz),
      z: Math.sin(pitch) * y + Math.cos(pitch) * zz };
  }

  function pose(flex, mode) {
    const points = new Array(21);
    points[0] = project([0, -126, 0], mode);
    for (const [fingerIndex, finger] of FINGERS.entries()) {
      let [x, y] = finger.origin, z = 0, bend = 0;
      points[finger.base] = project([x, y, z], mode);
      for (const [segment, length] of finger.lengths.entries()) {
        const value = flex[fingerIndex];
        bend += [.38, .67, .43][segment] * value;
        const direction = finger.spread + (mode === '2d' ? bend * [-.45, -.75, .48, .8, .48][fingerIndex] : 0);
        const plane = mode === '3d' ? Math.cos(bend) : 1;
        x += length * Math.sin(direction) * plane;
        y += length * Math.cos(direction) * plane;
        z += mode === '3d' ? length * Math.sin(bend) : 0;
        points[finger.base + segment + 1] = project([x, y, z], mode);
      }
    }
    return points;
  }

  function maskPasses(points) {
    const distance = p => Math.hypot(p.x - MASK.x, p.y - MASK.y);
    const middle = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
    const [mcp, pip, dip] = points.slice(9, 12);
    const inside = [pip, middle(mcp, pip), middle(pip, dip)]
      .every(p => distance(p) <= MASK.r * .85);
    // The protected first two capsules, including their rounded ends, fit
    // inside the circle with a 2px margin. A disk is convex.
    const covered = [mcp, pip, dip].every(p => distance(p) + 17 <= MASK.r);
    const visible = [4, 8, 16, 20].filter(i => distance(points[i]) >= MASK.r * 1.1 + 9);
    return inside && covered && visible.length >= 2 && points.every(p =>
      Number.isFinite(p.z) && p.x >= 16 && p.x <= WIDTH - 16 && p.y >= 16 && p.y <= HEIGHT - 16);
  }

  function makeClip(mode, random, slot) {
    const moving = slot === 0 ? 1 : 3;
    const neutral = [.09, .08, .1, .08, .08];
    const variants = [
      neutral,
      neutral.map((value, i) => i === moving || i === 2 ? .68 + random() * .13 : value),
      neutral.map((value, i) => i === 2 || i === 4 ? .45 + random() * .15 : value),
      neutral.map((value, i) => i === moving ? .42 + random() * .17 : value),
    ];
    const frames = Array.from({ length: KEYFRAMES.at(-1) + 1 }, (_, index) => {
      const interval = Math.min(2, Math.floor(index / INTERVAL));
      const fraction = (index - KEYFRAMES[interval]) / INTERVAL;
      const ease = fraction * fraction * (3 - 2 * fraction);
      return pose(variants[interval].map((v, i) => v + (variants[interval + 1][i] - v) * ease), mode);
    });
    return frames.every(maskPasses) ? frames : null;
  }

  function createChallenge(mode, names, random = Math.random) {
    if (!['2d', '3d'].includes(mode)) throw new Error('Unknown live rendering mode');
    const id = globalThis.crypto.randomUUID();
    return [0, 1].map(slot => {
      const frames = makeClip(mode, random, slot);
      if (!frames) throw new Error('Generated motion failed the mask check');
      return {
        clip_id: `live-${mode}-${id}-${slot + 1}`,
        handedness: 'Right', mode, frames, keyframeIndices: KEYFRAMES,
        landmarks: {
          video_info: { width: WIDTH, height: HEIGHT, fps: FPS },
          frames: frames.map((points, frame_idx) => ({
            frame_idx, detected: true,
            landmarks_px: Object.fromEntries(names.map((name, i) => [name, points[i]])),
          })),
        },
      };
    });
  }

  function paint(canvas, clip, time, mirror) {
    const index = clamp(Math.floor(time * FPS + 1e-6), 0, clip.frames.length - 1);
    const points = clip.frames[index];
    if (canvas.width !== WIDTH || canvas.height !== HEIGHT) {
      canvas.width = WIDTH;
      canvas.height = HEIGHT;
    }
    const ctx = canvas.getContext('2d', { alpha: false });
    const depth = clip.mode === '3d';
    ctx.save();
    ctx.setTransform(mirror ? -1 : 1, 0, 0, 1, mirror ? WIDTH : 0, 0);
    const background = ctx.createLinearGradient(0, 0, WIDTH, HEIGHT);
    background.addColorStop(0, '#243649');
    background.addColorStop(1, '#111b26');
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);

    const path = new Path2D();
    path.rect(0, 0, WIDTH, HEIGHT);
    path.moveTo(MASK.x + MASK.r, MASK.y);
    path.arc(MASK.x, MASK.y, MASK.r, 0, 2 * Math.PI);
    ctx.save();
    ctx.clip(path, 'evenodd');
    const [wrist, , , , , indexMcp, , , , middleMcp, , , , ringMcp, , , , pinkyMcp] = points;
    const palm = ctx.createLinearGradient(wrist.x - 48, 0, wrist.x + 65, 0);
    palm.addColorStop(0, depth ? '#bf8066' : '#dda489');
    palm.addColorStop(.5, '#f2bfa1');
    palm.addColorStop(1, '#d49a7f');
    ctx.fillStyle = palm;
    ctx.beginPath();
    ctx.moveTo(wrist.x - 36, HEIGHT);
    ctx.lineTo(wrist.x - 36, wrist.y + 13);
    ctx.bezierCurveTo(wrist.x - 45, wrist.y - 35, indexMcp.x - 24, indexMcp.y + 20, indexMcp.x - 13, indexMcp.y - 2);
    ctx.quadraticCurveTo(middleMcp.x, middleMcp.y - 15, ringMcp.x, ringMcp.y - 8);
    ctx.quadraticCurveTo(pinkyMcp.x + 21, pinkyMcp.y - 9, pinkyMcp.x + 11, pinkyMcp.y + 25);
    ctx.quadraticCurveTo(wrist.x + 61, wrist.y - 40, wrist.x + 34, wrist.y + 5);
    ctx.lineTo(wrist.x + 36, HEIGHT);
    ctx.closePath();
    ctx.fill();

    const segments = FINGERS.flatMap(({ base, width }) => [0, 1, 2].map(i => ({
      a: points[base + i], b: points[base + i + 1], radius: width - i * 2,
    })));
    if (depth) segments.sort((a, b) => a.a.z + a.b.z - b.a.z - b.b.z);
    ctx.lineCap = 'round';
    for (const { a, b, radius } of segments) {
      const length = Math.hypot(b.x - a.x, b.y - a.y) || 1;
      const nx = (b.y - a.y) / length * radius, ny = (a.x - b.x) / length * radius;
      const light = ctx.createLinearGradient(a.x - nx, a.y - ny, a.x + nx, a.y + ny);
      light.addColorStop(0, depth ? '#b47860' : '#daa082');
      light.addColorStop(.55, '#f8caab');
      light.addColorStop(1, '#dfa285');
      ctx.strokeStyle = light;
      ctx.lineWidth = 2 * radius;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
    ctx.restore();
    ctx.fillStyle = '#070b10';
    ctx.beginPath();
    ctx.arc(MASK.x, MASK.y, MASK.r, 0, 2 * Math.PI);
    ctx.fill();
    ctx.restore();
  }

  return { createChallenge, maskPasses, paint };
})();

if (typeof module !== 'undefined') module.exports = LiveMotion;
