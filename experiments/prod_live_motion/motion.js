'use strict';

// Both renderers use the same fixed-length, articulated 3D hand.
const LiveMotion = (() => {
  const WIDTH = 512, HEIGHT = 420, FPS = 30;
  const MASK = { x: WIDTH / 2, y: HEIGHT / 2, r: 95 };
  const HAND_SCALE = .76;
  const WRIST_Y = -114;
  // Buryanov & Kotiuk (2010), Table I. Lengths are rounded at roughly
  // 1.21 model units/mm, including the measured soft tissue at the fingertips.
  const FINGERS = [
    { base: 1, origin: [-33, -84, 8], lengths: [56, 38, 33], spread: -.94, fan: -.9, flexion: [9, 15, 9], width: 14 },
    { base: 5, origin: [-48, -7, 2], lengths: [48, 27, 24], spread: -.23, fan: -1, flexion: [21, 27, 20.8], width: 14 },
    { base: 9, origin: [-16, 0, 0], lengths: [54, 32, 26], spread: -.025, fan: -.1, flexion: [22, 28, 21], width: 14 },
    { base: 13, origin: [14, -8, -2], lengths: [50, 31, 26], spread: .14, fan: .55, flexion: [22, 28, 21], width: 13 },
    { base: 17, origin: [43, -20, -6], lengths: [40, 22, 24], spread: .24, fan: 1, flexion: [22, 25, 14.25], width: 12 },
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
    const yaw = motion.yaw, pitch = -.52 + motion.pitch;
    const xx = Math.cos(yaw) * x + Math.sin(yaw) * z;
    const zz = Math.cos(yaw) * z - Math.sin(yaw) * x;
    // Project around the wrist in model units before centering the palm.
    return { x: xx, y: -Math.cos(pitch) * (y - WRIST_Y) + Math.sin(pitch) * zz,
      z: Math.sin(pitch) * (y - WRIST_Y) + Math.cos(pitch) * zz };
  }

  function pose(motion) {
    const points = new Array(21);
    points[0] = project([0, WRIST_Y, 0], motion);
    for (const [fingerIndex, finger] of FINGERS.entries()) {
      let [x, y, z] = finger.origin, bend = 0;
      points[finger.base] = project([x, y, z], motion);
      for (const [segment, length] of finger.lengths.entries()) {
        const thumbTurn = finger.base === 1 ? [0, .17, .27][segment] : 0;
        const direction = finger.spread + finger.fan * motion.fan + thumbTurn;
        bend += rad(finger.flexion[segment]) * motion.flex[fingerIndex];
        const plane = Math.cos(bend);
        x += length * Math.sin(direction) * plane;
        y += length * Math.cos(direction) * plane;
        z += length * Math.sin(bend);
        points[finger.base + segment + 1] = project([x, y, z], motion);
      }
    }
    const palm = mixPoint(points[0], points[9], .5);
    return points.map(p => ({
      x: MASK.x + (p.x - palm.x) * HAND_SCALE,
      y: MASK.y + (p.y - palm.y) * HAND_SCALE,
      z: p.z * HAND_SCALE,
    }));
  }

  const distance = p => Math.hypot(p.x - MASK.x, p.y - MASK.y);
  // The landmark is now the skin endpoint. Reserve a 9 px strip behind
  // it beyond the circle so the cue includes part of the fingertip.
  const clearTip = p => distance(p) >= MASK.r + 9;

  function maskPasses(points) {
    const [mcp, pip] = points.slice(9, 11);
    const middleRadius = FINGERS[2].width * HAND_SCALE;
    // With the mask centered on the palm, protect the first segment and PIP.
    // The disk is convex, so both surrounding disks cover the full segment.
    const covered = [mcp, pip].every(p => distance(p) + middleRadius + 2 <= MASK.r);
    const visible = TIP_INDICES.filter(i => clearTip(points[i]));
    return covered && visible.length >= 2 && points.every(p =>
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

  function mixPoint(a, b, t) {
    return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t };
  }

  function palmOutline(points) {
    const [wrist, , thumbMcp] = points;
    const offset = (p, x, y) => ({ x: p.x + x, y: p.y + y, z: p.z });
    const outline = [offset(wrist, -31, 46)];
    const curve = (control, end) => {
      const first = outline.at(-1);
      for (let j = 1; j <= 5; j++) {
        const t = j / 5;
        outline.push(mixPoint(mixPoint(first, control, t), mixPoint(control, end, t), t));
      }
    };
    const index = points[5], little = points[17];
    curve(offset(wrist, -30, -8), offset(wrist, -45, -31));
    curve(offset(thumbMcp, -1, 19), offset(thumbMcp, 5, 3));
    curve(offset(thumbMcp, 19, -9), offset(index, -12, 30));
    curve(offset(index, -13, 12), offset(mixPoint(index, points[6], .30), -12, 0));
    // The visible finger web sits forward of the MCP centers. Approximate
    // the measured web height using part of each moving proximal segment.
    for (const base of [5, 9, 13]) {
      const left = mixPoint(points[base], points[base + 1], .37);
      const right = mixPoint(points[base + 4], points[base + 5], .37);
      curve(offset(left, -1, -3), offset(mixPoint(left, right, .5), 0, 3));
    }
    curve(offset(mixPoint(little, points[18], .32), 4, -5), offset(little, 12, 2));
    curve(offset(little, 18, 35), offset(wrist, 38, -22));
    curve(offset(wrist, 29, -4), offset(wrist, 32, 46));
    return outline;
  }

  // Landmarks store the visible fingertips. The center of the rounded
  // surface cap sits a radius inward, so the skin ends at the landmark.
  function fingerSurfaceJoints(points, base, width) {
    const joints = points.slice(base, base + 4);
    const a = joints[2], tip = joints[3];
    const length = Math.hypot(tip.x - a.x, tip.y - a.y, tip.z - a.z);
    joints[3] = mixPoint(tip, a, (width - 6) / length);
    return joints;
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

    return (ctx, points, outline) => {
      if (gl.isContextLost()) return false;
      const vertices = [];
      const connect = (bands, count) => {
        for (let row = 1; row < bands.length; row++) {
          const a = bands[row - 1], b = bands[row];
          for (let s = 0; s < count; s++) {
            const t = (s + 1) % count;
            vertices.push(...a[s], ...a[t], ...b[t], ...a[s], ...b[t], ...b[s]);
          }
        }
      };
      const center = mixPoint(points[0], points[9], .42);
      const palm = [0, .42, .74, 1].map(f => outline.map(edge => {
        const p = mixPoint(center, edge, f);
        return [p.x, p.y, p.z + 22 * (1 - f * f),
          f * (edge.x - center.x) / 65, f * (edge.y - center.y) / 75, 1 - .28 * f];
      }));
      connect(palm, outline.length);
      for (const { base, width } of FINGERS) {
        const joints = fingerSurfaceJoints(points, base, width).map(p => [p.x, p.y, p.z]);
        const axes = joints.map((_, i) => normalize(subtract(joints[Math.min(i + 1, 3)], joints[Math.max(i - 1, 0)])));
        // The palm skin covers the proximal end of each finger. Blend its
        // surface into the palm depth before letting the segment emerge.
        const root = [...joints[0]];
        root[2] -= base === 1 ? width + 15 : width + 7;
        const web = joints[0].map((v, i) => v + .36 * (joints[1][i] - v));
        web[2] -= base === 1 ? 11 : 5;
        const tipRadius = width - 6;
        const bands = [
          ring(root, axes[0], width, -Math.PI / 2),
          ring(root, axes[0], width),
          ring(web, axes[0], width - 1),
          ...joints.slice(1).map((joint, i) => ring(joint, axes[i + 1], width - 2 * (i + 1))),
          ...[Math.PI / 6, Math.PI / 3, Math.PI / 2].map(angle => ring(joints[3], axes[3], tipRadius, angle)),
        ];
        connect(bands, sides);
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

  function paint(canvas, clip, time, mirror, mode, maskOpacity = 1) {
    const index = clamp(Math.floor(time * FPS + 1e-6), 0, clip.frames.length - 1);
    // Draw the authored skin at its native scale, then apply the same uniform
    // scale as the projected landmarks. The circle stays in canvas pixels.
    const points = clip.frames[index].map(p => ({
      x: MASK.x + (p.x - MASK.x) / HAND_SCALE,
      y: MASK.y + (p.y - MASK.y) / HAND_SCALE,
      z: p.z / HAND_SCALE,
    }));
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

    if (maskOpacity === 1) {
      const path = new Path2D();
      path.rect(0, 0, WIDTH, HEIGHT);
      path.moveTo(MASK.x + MASK.r, MASK.y);
      path.arc(MASK.x, MASK.y, MASK.r, 0, 2 * Math.PI);
      ctx.save();
      ctx.clip(path, 'evenodd');
    }
    ctx.save();
    ctx.translate(MASK.x, MASK.y);
    ctx.scale(HAND_SCALE, HAND_SCALE);
    ctx.translate(-MASK.x, -MASK.y);
    const outline = palmOutline(points);
    if (depth && renderSurface === undefined) renderSurface = makeSurfaceRenderer();
    if (!depth || !renderSurface?.(ctx, points, outline)) {
      ctx.fillStyle = '#edba9e';
      ctx.beginPath();
      ctx.moveTo(outline[0].x, outline[0].y);
      for (const p of outline.slice(1)) ctx.lineTo(p.x, p.y);
      ctx.closePath();
      ctx.fill();
      if (depth) paintShadedStrokes(ctx, points);
      else paintFlatFingers(ctx, points);
    }
    ctx.restore();
    if (maskOpacity === 1) ctx.restore();
    if (maskOpacity > 0) {
      ctx.globalAlpha = maskOpacity;
      ctx.fillStyle = '#070b10';
      ctx.beginPath();
      ctx.arc(MASK.x, MASK.y, MASK.r, 0, 2 * Math.PI);
      ctx.fill();
    }
    ctx.restore();
  }

  function paintFlatFingers(ctx, points) {
    ctx.fillStyle = '#edba9e';
    for (const { base, width } of FINGERS) {
      const joints = fingerSurfaceJoints(points, base, width);
      const edges = joints.map(({ x, y }, i) => {
        const from = joints[Math.max(0, i - 1)], to = joints[Math.min(3, i + 1)];
        const dx = to.x - from.x, dy = to.y - from.y;
        const radius = width - 2 * i;
        const scale = radius / Math.hypot(dx, dy);
        const nx = -dy * scale, ny = dx * scale;
        const cap = i === 3 ? points[base + 3] : null;
        return { a: [x + nx, y + ny], b: [x - nx, y - ny],
          u: cap ? (cap.x - x) * 4 / 3 : dx * scale, v: cap ? (cap.y - y) * 4 / 3 : dy * scale };
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
    const segments = FINGERS.flatMap(({ base, width }) => {
      const joints = fingerSurfaceJoints(points, base, width);
      return [0, 1, 2].map(i => ({ a: joints[i], b: joints[i + 1], radius: width - 2 * (i + 1) }));
    });
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
