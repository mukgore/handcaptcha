'use strict';

// Both renderers use the same fixed-length, articulated 3D hand.
const LiveMotion = (() => {
  const WIDTH = 512, HEIGHT = 420, FPS = 30;
  const MASK = { x: 258, y: 210, r: 90 };
  const FINGERS = [
    { base: 1, origin: [-63, -65], lengths: [36, 27, 19], spread: -1.05, fan: -.9, flexion: [9, 15, 9], width: 15 },
    { base: 5, origin: [-60, -1], lengths: [45, 32, 25], spread: -.23, fan: -1, flexion: [21, 27, 20.8], width: 14 },
    { base: 9, origin: [-10, 2], lengths: [43, 30, 24], spread: -.025, fan: -.1, flexion: [22, 28, 21], width: 15 },
    { base: 13, origin: [34, -5], lengths: [42, 31, 23], spread: .14, fan: .55, flexion: [22, 28, 21], width: 14 },
    { base: 17, origin: [83, -19], lengths: [36, 25, 19], spread: .39, fan: 1, flexion: [22, 25, 14.25], width: 12 },
  ];
  // Adjacent digits participate together. In particular, there is no trajectory
  // that asks the ring finger to curl strongly while its neighbors stay rigid.
  const MOTIONS = [
    { name: 'soft-curl', flex: [.16, .76, .88, .86, .47], fan: 1 },
    { name: 'index-led', flex: [.14, .91, .63, .48, .35], fan: .75 },
    { name: 'outside-led', flex: [.12, .34, .64, .88, .56], fan: .85 },
    { name: 'open-and-close', flex: [.19, .68, .71, .72, .43], fan: 1.2 },
  ];
  const TIP_INDICES = [4, 8, 16, 20];
  const rad = degrees => degrees * Math.PI / 180;
  const clamp = (n, min, max) => Math.min(max, Math.max(min, n));

  function project(point, motion) {
    const [x, y, z] = point;
    const yaw = -.14 + motion.yaw, pitch = .25 + motion.pitch;
    const xx = Math.cos(yaw) * x + Math.sin(yaw) * z;
    const zz = Math.cos(yaw) * z - Math.sin(yaw) * x;
    // Turn around the wrist, keeping its projected location stable.
    return { x: 258 + xx, y: 350 - Math.cos(pitch) * (y + 126) + Math.sin(pitch) * zz,
      z: Math.sin(pitch) * (y + 126) + Math.cos(pitch) * zz };
  }

  function pose(motion) {
    const points = new Array(21);
    points[0] = project([0, -126, 0], motion);
    for (const [fingerIndex, finger] of FINGERS.entries()) {
      let [x, y] = finger.origin, z = 0, bend = 0;
      points[finger.base] = project([x, y, z], motion);
      const direction = finger.spread + finger.fan * motion.fan;
      for (const [segment, length] of finger.lengths.entries()) {
        bend += rad(finger.flexion[segment]) * motion.flex[fingerIndex];
        const plane = Math.cos(bend);
        x += length * Math.sin(direction) * plane;
        y += length * Math.cos(direction) * plane;
        z += length * Math.sin(bend);
        points[finger.base + segment + 1] = project([x, y, z], motion);
      }
    }
    return points;
  }

  const distance = p => Math.hypot(p.x - MASK.x, p.y - MASK.y);
  const clearTip = p => distance(p) >= MASK.r * 1.1 + 9;

  function maskPasses(points) {
    const middle = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
    const [mcp, pip, dip] = points.slice(9, 12);
    const inside = [pip, middle(mcp, pip), middle(pip, dip)]
      .every(p => distance(p) <= MASK.r * .85);
    // The protected first two capsules, including their rounded ends, fit
    // inside the circle with a 2px margin. A disk is convex.
    const covered = [mcp, pip, dip].every(p => distance(p) + 17 <= MASK.r);
    const visible = TIP_INDICES.filter(i => clearTip(points[i]));
    return inside && covered && visible.length >= 2 && points.every(p =>
      Number.isFinite(p.z) && p.x >= 16 && p.x <= WIDTH - 16 && p.y >= 16 && p.y <= HEIGHT - 16);
  }

  function makeClip(pattern, random) {
    const sample = (low, high) => low + (high - low) * random();
    const strength = sample(.82, 1);
    const yaw = rad(sample(-4, 4));
    const pitch = rad(sample(2, 6));
    const variants = [
      { curl: .16, fan: .85, turn: -.25 },
      { curl: 1, fan: .12, turn: 1 },
      { curl: sample(.44, .61), fan: .55, turn: .45 },
      { curl: .24, fan: 1, turn: -.45 },
    ];
    const keyframes = [0];
    for (let i = 1; i < variants.length; i++) keyframes.push(keyframes[i - 1] + Math.round(sample(43, 56)));
    const frames = Array.from({ length: keyframes.at(-1) + 1 }, (_, index) => {
      const interval = index < keyframes[1] ? 0 : index < keyframes[2] ? 1 : 2;
      const u = (index - keyframes[interval]) / (keyframes[interval + 1] - keyframes[interval]);
      const ease = u ** 3 * (10 + u * (-15 + 6 * u));
      const from = variants[interval], to = variants[interval + 1];
      const interpolate = key => from[key] + (to[key] - from[key]) * ease;
      return pose({
        flex: pattern.flex.map(weight => .12 + weight * strength * .87 * interpolate('curl')),
        fan: rad(5) * pattern.fan * interpolate('fan'),
        yaw: yaw * interpolate('turn'),
        pitch: pitch * interpolate('turn'),
      });
    });
    const poses = keyframes.map(i => frames[i]);
    const visiblyMoves = poses.slice(1).every((next, i) => TIP_INDICES.some(tip => {
      const a = poses[i][tip], b = next[tip];
      return (clearTip(a) || clearTip(b)) && Math.hypot(a.x - b.x, a.y - b.y) >= 5;
    }));
    return frames.every(maskPasses) && visiblyMoves ? { frames, keyframes } : null;
  }

  function createChallenge(names, random = Math.random) {
    const id = globalThis.crypto.randomUUID();
    const candidates = [...MOTIONS];
    const clips = [];
    while (clips.length < 2 && candidates.length) {
      const [pattern] = candidates.splice(Math.floor(random() * candidates.length), 1);
      let result = null;
      for (let attempt = 0; attempt < 8 && !result; attempt++) result = makeClip(pattern, random);
      if (!result) continue;
      const { frames, keyframes } = result;
      clips.push({
        clip_id: `live-${id}-${clips.length + 1}`,
        handedness: 'Right', motion: pattern.name, frames, keyframeIndices: keyframes,
        landmarks: {
          video_info: { width: WIDTH, height: HEIGHT, fps: FPS },
          frames: frames.map((points, frame_idx) => ({
            frame_idx, detected: true,
            landmarks_px: Object.fromEntries(names.map((name, i) => [name, points[i]])),
          })),
        },
      });
    }
    if (clips.length < 2) throw new Error('Generated motion failed the mask and visibility checks');
    return clips;
  }

  function makeSurfaceRenderer() {
    const surface = document.createElement('canvas');
    surface.width = WIDTH;
    surface.height = HEIGHT;
    const gl = surface.getContext('webgl', { alpha: true, antialias: true });
    if (!gl) return null;

    const program = gl.createProgram();
    const shaders = [
      [gl.VERTEX_SHADER, `
        attribute vec3 point;
        attribute vec3 normal;
        varying vec3 n;
        void main() {
          gl_Position = vec4(2.0 * point.x / 512.0 - 1.0, 1.0 - 2.0 * point.y / 420.0,
                             -point.z / 420.0, 1.0);
          n = normal;
        }`],
      [gl.FRAGMENT_SHADER, `
        precision mediump float;
        varying vec3 n;
        void main() {
          vec3 unitNormal = normalize(n);
          vec3 light = normalize(vec3(-0.5, -0.6, 0.85));
          float shade = max(0.0, dot(unitNormal, light));
          gl_FragColor = vec4(mix(vec3(0.67, 0.40, 0.31), vec3(0.99, 0.78, 0.66), shade), 1.0);
        }`],
    ];
    for (const [type, source] of shaders) {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return null;
      gl.attachShader(program, shader);
      gl.deleteShader(shader);
    }
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
    gl.useProgram(program);
    gl.enable(gl.DEPTH_TEST);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    for (const [name, offset] of [['point', 0], ['normal', 12]]) {
      const attribute = gl.getAttribLocation(program, name);
      gl.enableVertexAttribArray(attribute);
      gl.vertexAttribPointer(attribute, 3, gl.FLOAT, false, 24, offset);
    }
    const subtract = (a, b) => a.map((v, i) => v - b[i]);
    const normalize = vector => {
      const length = Math.hypot(...vector);
      return vector.map(v => v / length);
    };
    const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
    const sides = 16;
    const circle = Array.from({ length: sides }, (_, i) => [Math.cos(2 * Math.PI * i / sides), Math.sin(2 * Math.PI * i / sides)]);
    const ring = (center, axis, radius, angle = 0) => {
      const tangent = normalize(cross(axis, [1, 0, 0]));
      const bitangent = cross(axis, tangent);
      return circle.map(([c, s]) => {
        const normal = tangent.map((v, i) => (c * v + s * bitangent[i]) * Math.cos(angle) + axis[i] * Math.sin(angle));
        return [...center.map((v, i) => v + radius * normal[i]), ...normal];
      });
    };

    return (ctx, points) => {
      if (gl.isContextLost()) return false;
      const vertices = [];
      for (const { base, width } of FINGERS) {
        const joints = points.slice(base, base + 4).map(p => [p.x, p.y, p.z]);
        const axes = joints.map((_, i) => normalize(subtract(joints[Math.min(i + 1, 3)], joints[Math.max(i - 1, 0)])));
        const tipRadius = width - 6;
        const bands = [
          ...[-Math.PI / 2, -Math.PI / 3, -Math.PI / 6].map(angle => ring(joints[0], axes[0], width, angle)),
          ...joints.map((joint, i) => ring(joint, axes[i], width - 2 * i)),
          ...[Math.PI / 6, Math.PI / 3, Math.PI / 2].map(angle => ring(joints[3], axes[3], tipRadius, angle)),
        ];
        for (let row = 1; row < bands.length; row++) {
          for (let s = 0; s < sides; s++) {
            const t = (s + 1) % sides;
            const a = bands[row - 1], b = bands[row];
            vertices.push(...a[s], ...a[t], ...b[t], ...a[s], ...b[t], ...b[s]);
          }
        }
      }
      gl.viewport(0, 0, WIDTH, HEIGHT);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STREAM_DRAW);
      gl.drawArrays(gl.TRIANGLES, 0, vertices.length / 6);
      ctx.drawImage(surface, 0, 0);
      return true;
    };
  }

  let renderSurface;

  function paint(canvas, clip, time, mirror, mode) {
    const index = clamp(Math.floor(time * FPS + 1e-6), 0, clip.frames.length - 1);
    const points = clip.frames[index];
    if (canvas.width !== WIDTH || canvas.height !== HEIGHT) {
      canvas.width = WIDTH;
      canvas.height = HEIGHT;
    }
    const ctx = canvas.getContext('2d', { alpha: false });
    const depth = mode === '3d';
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
    ctx.fillStyle = depth ? palm : '#edba9e';
    ctx.beginPath();
    ctx.moveTo(wrist.x - 36, HEIGHT);
    ctx.lineTo(wrist.x - 36, wrist.y + 13);
    ctx.bezierCurveTo(wrist.x - 45, wrist.y - 35, indexMcp.x - 24, indexMcp.y + 20, indexMcp.x - 13, indexMcp.y - 2);
    ctx.quadraticCurveTo(middleMcp.x, middleMcp.y - 15, ringMcp.x, ringMcp.y - 8);
    ctx.bezierCurveTo(ringMcp.x + 16, ringMcp.y + 2, pinkyMcp.x + 14, pinkyMcp.y - 8, pinkyMcp.x + 12, pinkyMcp.y + 8);
    ctx.bezierCurveTo(pinkyMcp.x + 10, pinkyMcp.y + 55, wrist.x + 42, wrist.y - 27, wrist.x + 36, wrist.y + 9);
    ctx.lineTo(wrist.x + 36, HEIGHT);
    ctx.closePath();
    ctx.fill();

    if (depth) {
      if (renderSurface === undefined) renderSurface = makeSurfaceRenderer();
      if (!renderSurface?.(ctx, points)) paintShadedStrokes(ctx, points);
    } else {
      paintFlatFingers(ctx, points);
    }
    ctx.restore();
    ctx.fillStyle = '#070b10';
    ctx.beginPath();
    ctx.arc(MASK.x, MASK.y, MASK.r, 0, 2 * Math.PI);
    ctx.fill();
    ctx.restore();
  }

  function paintFlatFingers(ctx, points) {
    ctx.fillStyle = '#edba9e';
    for (const { base, width } of FINGERS) {
      const joints = points.slice(base, base + 4);
      const edges = joints.map(({ x, y }, i) => {
        const from = joints[Math.max(0, i - 1)], to = joints[Math.min(3, i + 1)];
        const dx = to.x - from.x, dy = to.y - from.y;
        const radius = width - 2 * i;
        const scale = radius / Math.hypot(dx, dy);
        const nx = -dy * scale, ny = dx * scale;
        return { a: [x + nx, y + ny], b: [x - nx, y - ny], u: dx * scale, v: dy * scale };
      });
      const [root, , , tip] = edges;
      const curve = side => {
        for (let i = 1; i < side.length - 1; i++) {
          const [x, y] = side[i], [nx, ny] = side[i + 1];
          ctx.quadraticCurveTo(x, y, (x + nx) / 2, (y + ny) / 2);
        }
        ctx.lineTo(...side.at(-1));
      };
      ctx.beginPath();
      ctx.moveTo(...root.a);
      curve(edges.map(edge => edge.a));
      ctx.bezierCurveTo(tip.a[0] + tip.u, tip.a[1] + tip.v, tip.b[0] + tip.u, tip.b[1] + tip.v, ...tip.b);
      curve(edges.map(edge => edge.b).reverse());
      ctx.bezierCurveTo(root.b[0] - root.u, root.b[1] - root.v, root.a[0] - root.u, root.a[1] - root.v, ...root.a);
      ctx.closePath();
      ctx.fill();
    }
  }

  function paintShadedStrokes(ctx, points) {
    const segments = FINGERS.flatMap(({ base, width }) => [0, 1, 2].map(i => ({
      a: points[base + i], b: points[base + i + 1], radius: width - i * 2,
    })));
    segments.sort((a, b) => a.a.z + a.b.z - b.a.z - b.b.z);
    ctx.lineCap = 'round';
    for (const { a, b, radius } of segments) {
      const length = Math.hypot(b.x - a.x, b.y - a.y) || 1;
      const nx = (b.y - a.y) / length * radius, ny = (a.x - b.x) / length * radius;
      const light = ctx.createLinearGradient(a.x - nx, a.y - ny, a.x + nx, a.y + ny);
      light.addColorStop(0, '#b47860');
      light.addColorStop(.55, '#f8caab');
      light.addColorStop(1, '#dfa285');
      ctx.strokeStyle = light;
      ctx.lineWidth = 2 * radius;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
  }

  return { createChallenge, maskPasses, paint, mask: Object.freeze(MASK) };
})();

if (typeof module !== 'undefined') module.exports = LiveMotion;
