// THE LAST LANTERN — shot list, blocking, camera and lighting for every frame.
import * as THREE from 'three';
import { lerp, clamp, ease, easeOut, easeIn, smooth, range, noise1 } from './util.js';
import { petalsField, snowField, fireflyField, heartField, smokeField } from './props.js';

const V3 = (x, y, z) => new THREE.Vector3(x, y, z);
const PI = Math.PI;
export const DURATION = 300;

// ---------------- dialogue + supers ----------------
const SUBS = [
  [26.5, 30.0, 'juno', 'Grandma always said the last post waits...', true],
  [30.0, 34.0, 'juno', '...for someone worth lighting it for.', true],
  [49.6, 53.6, 'rowan', "Hi! Is this... Willow Lake? It isn't on any map."],
  [54.4, 57.6, 'juno', 'Then your map is wrong.'],
  [59.0, 62.0, 'rowan', "I'm Rowan. I draw maps."],
  [62.6, 65.2, 'juno', 'Juno. I make lanterns.'],
  [65.9, 69.6, 'rowan', 'Then maybe you can help me find my way.'],
  [74.0, 79.0, 'juno', 'This is the grove. Every tree here has a name.'],
  [86.0, 90.0, 'rowan', 'Rivers, ridges, roads... I can map all of it.'],
  [91.0, 94.0, 'juno', 'Not all of it.'],
  [99.6, 102.6, 'rowan', 'Mine looks like a potato.'],
  [103.4, 107.2, 'juno', "A glowing potato. It's perfect."],
  [124.0, 127.4, 'rowan', "The map's almost finished."],
  [128.6, 131.6, 'juno', '...And then you leave.'],
  [133.0, 137.4, 'rowan', "Cartographers always leave. It's the job."],
  [158.4, 161.2, 'rowan', "I'll come back."],
  [163.0, 165.8, 'juno', 'Everyone says that.'],
  [190.6, 194.6, 'juno', 'So you can find your way back.'],
  [247.6, 250.6, 'rowan', 'I finished the map.'],
  [251.2, 255.6, 'rowan', 'Turns out every road on it leads here.'],
  [257.0, 260.2, 'juno', 'You followed the lantern.'],
  [261.4, 264.2, 'rowan', 'I followed you.'],
];
const SUPERS = [
  [17.0, 22.5, 'Willow Lake. Spring.'],
  [197.5, 203.5, 'Winter.'],
  [227.5, 233.5, 'Spring.'],
];
export const talking = (who, t) => SUBS.some(([a, b, w]) => w === who && t >= a && t < b);

function overlays(t) {
  const texts = [];
  const barCenter = 1 - (1 - 1 / 2.39 * 16 / 9) / 4; // middle of the lower letterbox bar
  for (const [a, b, , text, italic] of SUBS) if (t >= a && t < b) {
    const al = clamp((t - a) / 0.2, 0, 1) * clamp((b - t) / 0.2, 0, 1);
    texts.push({ text, x: 0.5, y: barCenter, size: 38, font: 'Nunito', weight: '600', style: italic ? 'italic' : 'normal', alpha: al, color: '#f4efe6', shadow: false, spacing: 0.5 });
  }
  for (const [a, b, text] of SUPERS) if (t >= a && t < b) {
    const al = clamp((t - a) / 1.0, 0, 1) * clamp((b - t) / 1.0, 0, 1);
    texts.push({ text, x: 0.075, y: 0.76, size: 54, style: 'italic', weight: '400', alpha: al, align: 'left', spacing: 1 });
  }
  // opening title
  if (t >= 3.5 && t < 12.5) {
    const al = clamp((t - 3.5) / 2.2, 0, 1) * clamp((12.5 - t) / 1.6, 0, 1);
    texts.push({ text: 'THE LAST LANTERN', x: 0.5, y: 0.47, size: 104, weight: '600', alpha: al, spacing: 18 });
    const al2 = clamp((t - 5.5) / 2, 0, 1) * clamp((12.5 - t) / 1.6, 0, 1);
    texts.push({ text: 'a love story in blocks', x: 0.5, y: 0.56, size: 36, style: 'italic', weight: '400', alpha: al2 * 0.9, spacing: 4 });
  }
  // end title + credits
  if (t >= 285 && t < 292.5) {
    const al = clamp((t - 285.5) / 2, 0, 1) * clamp((292.5 - t) / 1.2, 0, 1);
    texts.push({ text: 'THE LAST LANTERN', x: 0.5, y: 0.5, size: 96, weight: '600', alpha: al, spacing: 16 });
  }
  const credits = [
    [292.8, 295.6, [['starring', 30, 'italic', '400', 0.44], ['JUNO  ·  ROWAN', 64, 'normal', '600', 0.53]]],
    [295.8, 298.4, [['written & directed by', 30, 'italic', '400', 0.44], ['CLAUDE', 64, 'normal', '600', 0.53]]],
    [298.5, 300.0, [['every block placed with love', 40, 'italic', '400', 0.5]]],
  ];
  for (const [a, b, lines] of credits) if (t >= a && t < b) {
    const al = clamp((t - a) / 0.6, 0, 1) * clamp((b - t) / 0.5, 0, 1);
    for (const [text, size, style, weight, y] of lines) texts.push({ text, x: 0.5, y, size, style, weight, alpha: al, spacing: size > 50 ? 12 : 3 });
  }
  return texts;
}

// ---------------- helpers ----------------
function makeHelpers(S) {
  const { world } = S;
  const gy = (x, z) => world.topAt(Math.floor(x), Math.floor(z)) + 1;
  const DECK = 21;

  function cam({ pos, look, fov = 35, shake = 0.02, t = 0, roll = 0 }) {
    const c = S.camera;
    const sx = noise1(t * 0.35, 1) * shake, sy = noise1(t * 0.3, 2) * shake, sz = noise1(t * 0.33, 3) * shake;
    c.position.set(pos.x + sx, pos.y + sy, pos.z + sz);
    c.up.set(Math.sin(roll), Math.cos(roll), 0);
    c.lookAt(look.x + sx * 0.5 + noise1(t * 0.27, 4) * shake * 0.6, look.y + noise1(t * 0.25, 5) * shake * 0.6, look.z + sz * 0.5);
    c.fov = fov; c.updateProjectionMatrix();
  }
  // interpolate between two camera keys with easing
  function move(a, b, k, t, shake = 0.02, fn = ease) {
    const e = fn(k);
    cam({ pos: a.pos.clone().lerp(b.pos, e), look: a.look.clone().lerp(b.look, e), fov: lerp(a.fov ?? 35, b.fov ?? 35, e), shake, t, roll: lerp(a.roll ?? 0, b.roll ?? 0, e) });
  }
  function spline(points, looks, k, t, fovs = [35], shake = 0.02, fn = ease) {
    const e = fn(k);
    const pc = new THREE.CatmullRomCurve3(points, false, 'centripetal');
    const lc = looks.length > 1 ? new THREE.CatmullRomCurve3(looks, false, 'centripetal') : null;
    const fov = fovs.length > 1 ? lerp(fovs[0], fovs[1], e) : fovs[0];
    cam({ pos: pc.getPoint(e), look: lc ? lc.getPoint(e) : looks[0], fov, shake, t });
  }
  function orbit(center, radius, height, a0, a1, k, t, fov = 35, lookDy = 0, fn = ease) {
    const a = lerp(a0, a1, fn(k));
    cam({ pos: V3(center.x + Math.sin(a) * radius, center.y + height, center.z + Math.cos(a) * radius), look: V3(center.x, center.y + lookDy, center.z), fov, shake: 0.015, t });
  }
  function walk(points, speed, lt, delay = 0) {
    const segs = []; let total = 0;
    for (let i = 0; i < points.length - 1; i++) { const l = Math.hypot(points[i + 1][0] - points[i][0], points[i + 1][2] - points[i][2]); segs.push(l); total += l; }
    const s = clamp((lt - delay) * speed, 0, total);
    let acc = 0, i = 0;
    while (i < segs.length - 1 && acc + segs[i] < s) { acc += segs[i]; i++; }
    const k = segs[i] > 0 ? (s - acc) / segs[i] : 0;
    const a = points[i], b = points[i + 1];
    const x = lerp(a[0], b[0], k), z = lerp(a[2], b[2], k);
    const y = a[1] === 'g' ? gy(x, z) : lerp(a[1], b[1], k);
    const moving = lt > delay && s < total;
    const ramp = Math.min(clamp((lt - delay) * 2, 0, 1), clamp((total - s) * 1.5, 0, 1));
    return { pos: [x, y, z], yaw: Math.atan2(b[0] - a[0], b[2] - a[2]), walk: s * 2.3, walkAmp: moving ? 0.75 * ramp : 0, done: s >= total };
  }
  const yawTo = (from, to) => Math.atan2(to[0] - from[0], to[2] - from[2]);
  const pose = (ch, t, p) => ch.pose({ time: t, talk: talking(ch.kind, t), ...p });
  // sitting helper: hips on the surface at height y
  const sitPos = (x, y, z) => [x, y - 12 / 16 + 0.02, z];
  return { gy, DECK, cam, move, spline, orbit, walk, yawTo, pose, sitPos };
}

function resetStage(S) {
  const { juno, rowan } = S;
  juno.root.visible = rowan.root.visible = false;
  juno.held(null, 'R'); juno.held(null, 'L'); rowan.held(null, 'R'); rowan.held(null, 'L');
  for (const m of [S.mapUnfinished, S.mapFinished, S.sketch]) if (m.parent) m.parent.remove(m);
  for (const l of S.lanterns) { l.group.visible = true; l.set(0, 0); }
  S.lastLantern.group.visible = false; S.lastLantern.set(0, 0);
  S.handLantern.set(0, 0); S.workLantern.set(0, 0); S.potato.set(0, 0);
  S.shelfLanterns.forEach((l) => l.set(0, 0));
  S.boat.group.visible = false; S.boat.lantern.set(0, 0); S.boat.lantern.group.scale.setScalar(1);
  S.sapling.visible = false; S.youngTree.visible = false;
  for (const k of ['petals', 'snow', 'fireflies', 'hearts', 'smoke']) S.fx[k].hide();
  S.fx.skyLanterns.update(0, 0);
  S.U.uSnow.value = 0; S.U.uWind.value = 1;
  S.dof.enabled = false; S.dof.uniforms.uAperture.value = 0;
  S.bloom.strength = 0.5; S.bloom.threshold = 0.9; S.bloom.radius = 0.65;
  S.renderer.toneMappingExposure = 1.0;
}

// ---------------- boat choreography ----------------
const DOCK = V3(93.8, 20, 98.2);
function boatArrive(t, t0, t1, from) {
  // glides along a curve and eases to a stop at the dock
  const r = range(t, t0, t1);
  const k = 1 - Math.pow(1 - r, 1.7);
  const curve = new THREE.CatmullRomCurve3([from, V3(from.x + 4, 20, lerp(from.z, DOCK.z, 0.5)), V3(DOCK.x + 1.5, 20, DOCK.z + 8), DOCK.clone()]);
  const p = curve.getPoint(k);
  const tan = curve.getTangent(Math.min(k, 0.999));
  return { p, yaw: Math.atan2(tan.x, tan.z), speed: 1 - k };
}
function boatLeave(t, t0, t1) {
  const k = easeIn(range(t, t0, t1)) * 0.6 + range(t, t0, t1) * 0.4;
  const curve = new THREE.CatmullRomCurve3([DOCK.clone(), V3(DOCK.x + 1, 20, DOCK.z + 10), V3(DOCK.x - 3, 20, 130), V3(DOCK.x - 8, 20, 160)]);
  const p = curve.getPoint(k);
  const tan = curve.getTangent(Math.max(0.001, k));
  return { p, yaw: Math.atan2(tan.x, tan.z), speed: range(t, t0, t0 + 3) };
}
function placeBoat(S, H, b, t, rowing, rowanYawOff = 0, rowanOn = true) {
  const g = S.boat.group;
  g.visible = true;
  g.position.set(b.p.x, 20.02 + Math.sin(t * 1.3) * 0.04, b.p.z);
  g.rotation.set(0, b.yaw, 0);
  S.boat.inner.rotation.set(Math.sin(t * 1.1) * 0.02, 0, Math.sin(t * 0.9) * 0.03);
  const stroke = t * 2.4;
  S.boat.oars.forEach(({ oar, side }) => {
    oar.rotation.y = side * (1.2 + (rowing ? Math.sin(stroke) * 0.5 : 0));
    oar.rotation.x = 0.35 + (rowing ? Math.cos(stroke) * 0.15 : 0);
  });
  if (rowanOn) {
    const off = new THREE.Vector3(0, 0, -0.35).applyAxisAngle(V3(0, 1, 0), b.yaw);
    const seatTop = g.position.y + 0.6;
    H.pose(S.rowan, t, {
      pos: H.sitPos(g.position.x + off.x, seatTop, g.position.z + off.z), yaw: b.yaw + rowanYawOff, sit: true,
      armL: rowing ? [-1.1 + Math.sin(stroke) * 0.45, 0.25] : [-0.2, 0.05], armR: rowing ? [-1.1 + Math.sin(stroke) * 0.45, -0.25] : [-0.2, -0.05],
      bodyPitch: rowing ? Math.sin(stroke) * 0.12 : 0,
    });
  }
}

// ---------------- the shots ----------------
// Each shot: [start, end, fn(S, H, lt, t) => env]
const PIER_END = [88.5, 21, 98.3];

const SHOTS = [
  // 1. DAWN — crane down over the misty lake to the village
  {
    start: 0, end: 14, fadeIn: 3, run(S, H, lt, t) {
      H.spline([V3(40, 70, 170), V3(62, 52, 150), V3(80, 34, 128), V3(86, 26, 112)], [V3(95, 30, 80), V3(90, 26, 70), V3(88, 23, 72)], lt / 14, t, [42, 38], 0.03, (k) => k * 0.25 + smooth(k) * 0.75);
      S.lanterns.forEach((l, i) => l.set(0.8, t, i));
      S.fx.smoke.points.visible = true; smokeField(S.fx.smoke, t, [[71.5, 34, 60.5], [103.5, 34, 51.5], [105.5, 33, 64.5]], 1);
      return { tod: 6.35, sunAz: -0.15, focus: V3(88, 24, 90), mist: 0.9, exposure: 1.05, shadowSize: 70, emit: 0.4 };
    },
  },
  // 2. EARLY MORNING — wide of the pier, Juno walks out with a lantern
  {
    start: 14, end: 24, run(S, H, lt, t) {
      const w = H.walk([[88.5, 21, 79], [88.5, 21, 93]], 1.4, lt, 0.3);
      H.pose(S.juno, t, { ...w, headYaw: Math.sin(lt * 0.9) * 0.35 });
      S.handLantern.set(0.55, t, 99); S.handLantern.group.position.set(0, -0.3, 0); S.juno.held(S.handLantern.group, 'R');
      S.lanterns.forEach((l, i) => l.set(0.3, t, i));
      H.move({ pos: V3(97, 22.4, 99), look: V3(88.5, 22.4, 84), fov: 30 }, { pos: V3(94.5, 22.8, 97.5), look: V3(88.5, 22.6, 90), fov: 28 }, lt / 10, t, 0.025);
      return { tod: 7.1, sunAz: -0.2, focus: V3(88.5, 22, 88), mist: 0.55, exposure: 1.0, shadowSize: 30, emit: 0.2 };
    },
  },
  // 3. END OF THE PIER — Juno and the empty post
  {
    start: 24, end: 36, run(S, H, lt, t) {
      const w = H.walk([[88.5, 21, 94], [88.5, 21, 98.2]], 1.3, lt, 0);
      const reach = smooth(range(lt, 4.5, 5.6)) * (1 - smooth(range(lt, 9.5, 10.8)));
      H.pose(S.juno, t, { ...w, yaw: 0, headPitch: -0.18 * smooth(range(lt, 3, 4)), armL: [-0.6 - reach * 1.9, 0.1], armR: w.walkAmp ? undefined : [0.05, -0.05] });
      S.handLantern.set(0.55, t, 99); S.handLantern.group.position.set(0, -0.3, 0); S.juno.held(S.handLantern.group, 'R');
      S.lanterns.forEach((l, i) => l.set(0.3, t, i));
      // slow push from a low 3/4 angle, then settle on her face
      H.move({ pos: V3(92.6, 22.4, 100.9), look: V3(88.6, 22.8, 98.4), fov: 32 }, { pos: V3(90.9, 22.95, 99.9), look: V3(88.55, 23.05, 98.5), fov: 28 }, lt / 12, t, 0.02);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(V3(88.5, 23, 98.4)); S.dof.uniforms.uAperture.value = 14;
      return { tod: 7.6, sunAz: -0.3, focus: V3(88.5, 22, 97), mist: 0.4, exposure: 1.0, shadowSize: 12, emit: 0.1 };
    },
  },
  // 4. THE LAKE — a boat emerges from the mist
  {
    start: 36, end: 46, run(S, H, lt, t) {
      const b = boatArrive(t, 36, 49, V3(82, 20, 148));
      placeBoat(S, H, b, t, true, 0);
      S.rowan.neck.rotation.y = Math.sin(t * 0.7) * 0.3;
      H.cam({ pos: V3(lerp(80, 81.5, lt / 10), 20.75, lerp(117, 115, lt / 10)), look: V3(b.p.x, 21.1, b.p.z), fov: lerp(22, 30, ease(lt / 10)), shake: 0.035, t });
      S.lanterns.forEach((l, i) => l.set(0.5, t, i));
      return { tod: 8.0, sunAz: -0.3, focus: b.p.clone(), mist: 0.6, exposure: 1.0, shadowSize: 18, emit: 0 };
    },
  },
  // 5. THE PIER — docking, Rowan nearly falls in
  {
    start: 46, end: 58, run(S, H, lt, t) {
      const b = boatArrive(t, 36, 49, V3(82, 20, 148));
      const out = range(t, 49.2, 50.3);
      placeBoat(S, H, b, t, t < 49.0, 0, out <= 0);
      S.lanterns.forEach((l, i) => l.set(0.5, t, i));
      const jPos = [89.9, 21, 97.8];
      const rDeck = [91.3, 21, 97.8];
      if (out > 0) {
        const seat = [b.p.x, 20.5, b.p.z + 0.35];
        const k = smooth(out);
        const hop = Math.sin(k * PI) * 0.6;
        const wob = range(t, 50.3, 52.0);
        const flail = wob > 0 && wob < 1 ? Math.sin(wob * 18) * (1 - wob) : 0;
        H.pose(S.rowan, t, {
          pos: [lerp(seat[0], rDeck[0], k), lerp(seat[1], 21, k) + hop, lerp(seat[2], rDeck[2], k)], yaw: lerp(PI, -PI / 2, smooth(range(t, 49.2, 50.8))),
          bodyRoll: flail * 0.35, armL: [-0.3 + flail * 0.5, 1.2 * Math.abs(flail) + 0.1], armR: [-0.3 - flail * 0.5, -1.2 * Math.abs(flail) - 0.1],
          headYaw: 0,
        });
      }
      const turn = smooth(range(t, 46.5, 48));
      H.pose(S.juno, t, { pos: jPos, yaw: lerp(0.3, PI / 2, turn), headPitch: 0, armR: [0, -0.05], armL: [0, 0.05] });
      S.handLantern.set(0.5, t, 99); S.handLantern.group.position.set(0, -0.3, 0); S.juno.held(S.handLantern.group, 'R');
      // over-the-shoulder from behind Juno
      if (t < 54) H.move({ pos: V3(86.4, 23.3, 96.1), look: V3(93.5, 22.2, 98.9), fov: 34 }, { pos: V3(86.9, 23.2, 96.5), look: V3(91.6, 22.7, 98.0), fov: 30 }, range(t, 46, 54), t, 0.02);
      else H.move({ pos: V3(93.6, 22.9, 99.6), look: V3(89.9, 22.8, 97.6), fov: 28 }, { pos: V3(93.3, 22.9, 99.3), look: V3(89.9, 22.9, 97.7), fov: 26 }, range(t, 54, 58), t, 0.015);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(t < 54 ? V3(91.3, 22.8, 97.8) : V3(89.9, 22.8, 97.8)); S.dof.uniforms.uAperture.value = 10;
      return { tod: 8.4, sunAz: -0.3, focus: V3(90.5, 22, 97.8), mist: 0.35, exposure: 1.0, shadowSize: 12 };
    },
  },
  // 6. TWO-SHOT — introductions, Rowan shows the map
  {
    start: 58, end: 70, run(S, H, lt, t) {
      const jPos = [89.6, 21, 98.0], rPos = [91.0, 21, 98.0];
      const show = smooth(range(t, 59.2, 60.2));
      const offer = smooth(range(t, 66, 67.5));
      H.pose(S.rowan, t, { pos: rPos, yaw: -PI / 2, armL: [-1.05 * show, 0.25 * show], armR: [-1.05 * show - offer * 0.2, -0.25 * show], headPitch: 0.1 * show });
      if (show > 0.01) { S.mapUnfinished.position.set(0.1, 1.25, 0.55); S.mapUnfinished.rotation.set(-0.2, 0.75, 0, 'YXZ'); S.mapUnfinished.scale.setScalar(show); S.rowan.root.add(S.mapUnfinished); }
      H.pose(S.juno, t, { pos: jPos, yaw: PI / 2, headPitch: 0.12 * show, headYaw: 0, armR: [0, -0.05], armL: [0, 0.05], headRoll: 0.12 * smooth(range(t, 66.5, 68)) });
      S.handLantern.set(0.5, t, 99); S.handLantern.group.position.set(0, -0.3, 0); S.juno.held(S.handLantern.group, 'R');
      S.lanterns.forEach((l, i) => l.set(0.5, t, i));
      const b = boatArrive(t, 36, 49, V3(82, 20, 148)); placeBoat(S, H, b, t, false, 0, false);
      H.move({ pos: V3(89.6, 22.6, 102.2), look: V3(90.3, 22.75, 98.0), fov: 30 }, { pos: V3(89.9, 22.8, 101.0), look: V3(90.3, 22.9, 98.0), fov: 30 }, lt / 12, t, 0.015);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(V3(90.3, 22.8, 98.0)); S.dof.uniforms.uAperture.value = 9;
      return { tod: 8.8, sunAz: -0.3, focus: V3(90.6, 22, 97.8), mist: 0.2, exposure: 1.0, shadowSize: 12 };
    },
  },
  // 7. CHERRY GROVE — midday orbit, petals
  {
    start: 70, end: 84, dissolve: 1.2, run(S, H, lt, t) {
      const j = H.walk([[54, 'g', 67], [46, 'g', 69], [39, 'g', 70.5]], 1.05, lt, 0.2);
      const r = H.walk([[55, 'g', 68.4], [47, 'g', 70.3], [40, 'g', 71.8]], 1.05, lt, 0.2);
      H.pose(S.juno, t, { ...j, headYaw: talking('juno', t) ? -0.6 : Math.sin(lt * 0.5) * 0.4, armL: talking('juno', t) ? [-1.3, 0.4] : undefined });
      H.pose(S.rowan, t, { ...r, headYaw: 0.5 + Math.sin(lt * 0.4) * 0.3, headPitch: -0.25 });
      const mid = V3((j.pos[0] + r.pos[0]) / 2, j.pos[1] + 1.2, (j.pos[2] + r.pos[2]) / 2);
      H.orbit(mid, 8.5, 1.2, -2.3, -0.9, lt / 14, t, 32, 0.1, (k) => k);
      S.fx.petals.points.visible = true; petalsField(S.fx.petals, t, V3(40, 22, 70), 16, 9, 1);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = 8.6; S.dof.uniforms.uAperture.value = 11;
      S.U.uWind.value = 1.3;
      return { tod: 12.4, sunAz: 0.2, focus: mid, exposure: 0.95, shadowSize: 22 };
    },
  },
  // 8. THE HILL — afternoon, Rowan sketches, crane up to reveal the valley
  {
    start: 84, end: 96, dissolve: 1.2, run(S, H, lt, t) {
      const top = S.HILLTOP;
      const rP = H.sitPos(top.x - 1.2, top.y, top.z + 1.2), jP = [top.x - 0.2, top.y, top.z - 0.5];
      H.pose(S.rowan, t, { pos: rP, yaw: -PI / 2 - 0.35, sit: true, armL: [-0.9, 0.2], armR: [-0.9 + Math.sin(t * 5) * 0.05, -0.2], headPitch: talking('rowan', t) ? -0.1 : 0.3 });
      S.sketch.position.set(0, 0.85, 0.42); S.sketch.rotation.set(-1.0, 0, 0); S.sketch.scale.setScalar(0.55); S.rowan.root.add(S.sketch);
      const point = smooth(range(t, 90.8, 91.6)) * (1 - smooth(range(t, 94.5, 95.5)));
      H.pose(S.juno, t, { pos: jP, yaw: -PI / 2 - 0.1 + point * 0.7, armR: [-1.6 * point, -0.1], headYaw: 0, headPitch: -0.05 });
      S.lanterns.forEach((l, i) => l.set(0, t, i));
      const c = V3(top.x - 0.6, top.y + 1.0, top.z + 0.4);
      H.spline([V3(top.x - 2.6, top.y + 1.1, top.z + 5.2), V3(top.x + 1.5, top.y + 3.5, top.z + 6.5), V3(top.x + 6, top.y + 8, top.z + 5)],
        [c, V3(top.x - 8, top.y - 1, top.z + 6), V3(top.x - 40, top.y - 12, top.z + 34)], lt / 12, t, [32, 42], 0.02);
      S.U.uWind.value = 1.6;
      return { tod: 15.4, sunAz: 0.1, focus: c, exposure: 0.95, shadowSize: 30 };
    },
  },
  // 9. THE WORKSHOP — the potato lantern
  {
    start: 96, end: 108, dissolve: 1.0, run(S, H, lt, t) {
      const jP = [82.5, 22, 60.4], rP = [83.6, 22, 60.4];
      const raise = smooth(range(t, 98.4, 99.4));
      const laugh = range(t, 103.2, 107.5);
      H.pose(S.juno, t, { pos: jP, yaw: 0.25, headYaw: 0.5, headPitch: laugh > 0 && laugh < 1 ? -0.25 + Math.sin(t * 14) * 0.08 : 0.2, armL: [-0.7, 0.1], armR: [-0.7 + (laugh > 0 && laugh < 1 ? 0 : Math.sin(t * 3) * 0.1), -0.1] , hipsDy: laugh > 0 && laugh < 1 ? Math.abs(Math.sin(t * 14)) * 0.03 : 0 });
      H.pose(S.rowan, t, { pos: rP, yaw: -0.15, headYaw: -0.2 - raise * 0.3, headPitch: raise * -0.15, armR: [-0.6 - raise * 1.0, -0.15], armL: [-0.6, 0.1] });
      S.potato.set(raise * 0.7, t, 42); S.potato.group.position.set(0, -0.12, 0.02); S.rowan.held(S.potato.group, 'R');
      S.workLantern.set(0.5, t, 5); S.shelfLanterns.forEach((l, i) => l.set(0.25, t, 7 + i));
      H.move({ pos: V3(83.1, 23.1, 65.2), look: V3(83.1, 23.1, 60.6), fov: 32 }, { pos: V3(83.1, 23.2, 64.2), look: V3(83.1, 23.2, 60.6), fov: 30 }, lt / 12, t, 0.015);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(V3(83.1, 23, 60.6)); S.dof.uniforms.uAperture.value = 10;
      return { tod: 16.9, sunAz: 0.1, focus: V3(82.5, 23, 61), exposure: 1.05, shadowSize: 14, emit: 0.1, lights: 0.5, bloom: 0.35 };
    },
  },
  // 10. THE HILL — golden hour, planting the sapling
  {
    start: 108, end: 120, dissolve: 1.0, run(S, H, lt, t) {
      const top = S.HILLTOP;
      const kneel = smooth(range(lt, 0.5, 1.5)) * (1 - smooth(range(lt, 8.5, 9.8)));
      const dig = kneel > 0.9 ? Math.sin(t * 5) * 0.2 : 0;
      H.pose(S.juno, t, { pos: H.sitPos(top.x + 0.5, top.y, top.z - 1.6), yaw: 0.1, sit: true, legs: [-1.35, -1.25], bodyPitch: 0.3 * kneel, armL: [-0.9 - 0.5 * kneel + dig, 0.15], armR: [-0.9 - 0.5 * kneel - dig, -0.15], headPitch: 0.35 * kneel + 0.1 });
      H.pose(S.rowan, t, { pos: H.sitPos(top.x + 0.5, top.y, top.z + 2.2), yaw: PI - 0.1, sit: true, legs: [-1.3, -1.35], bodyPitch: 0.3 * kneel, armL: [-0.9 - 0.5 * kneel - dig, 0.15], armR: [-0.9 - 0.5 * kneel + dig, -0.15], headPitch: 0.35 * kneel + 0.1 });
      S.sapling.visible = lt > 4.2;
      if (lt > 4.2) { const g = easeOut(range(lt, 4.2, 5.5)); S.sapling.scale.set(1, g, 1); }
      const c = V3(top.x + 0.5, top.y + 0.45, top.z + 0.3);
      H.move({ pos: V3(top.x + 5.5, top.y + 1.5, top.z - 3.0), look: c, fov: 30 }, { pos: V3(top.x + 5.8, top.y + 1.3, top.z + 3.2), look: c, fov: 30 }, lt / 12, t, 0.02, smooth);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(c); S.dof.uniforms.uAperture.value = 10;
      S.U.uWind.value = 1.4;
      return { tod: 17.7, sunAz: 0.3, focus: c, exposure: 1.1, shadowSize: 16 };
    },
  },
  // 11a. SUNSET — silhouettes, sun sinking into the lake
  {
    start: 120, end: 130, dissolve: 1.2, run(S, H, lt, t) {
      const top = S.HILLTOP;
      sitCouple(S, H, t, top, 0);
      S.sapling.visible = true; S.sapling.scale.set(1, 1, 1);
      const c = V3(top.x - 1.0, top.y + 0.8, top.z + 0.2);
      H.move({ pos: V3(top.x + 6.5, top.y + 1.3, top.z - 4.2), look: V3(top.x - 20, top.y - 1.5, top.z + 14), fov: 36 }, { pos: V3(top.x + 5.0, top.y + 1.2, top.z - 3.2), look: V3(top.x - 20, top.y - 1.2, top.z + 14), fov: 33 }, lt / 10, t, 0.02);
      S.lanterns.forEach((l, i) => l.set(0.9, t, i));
      return { tod: lerp(18.45, 18.75, lt / 10), sunAz: 0.24, focus: c, exposure: 0.95, shadowSize: 20, emit: 0.2, bloom: 0.7 };
    },
  },
  // 11b. SUNSET — profile two-shot for the hard conversation
  {
    start: 130, end: 140, run(S, H, lt, t) {
      const top = S.HILLTOP;
      sitCouple(S, H, t, top, 1);
      S.sapling.visible = true; S.sapling.scale.set(1, 1, 1);
      const c = V3(top.x - 0.9, top.y + 0.55, top.z + 0.35);
      H.move({ pos: V3(top.x - 4.3, top.y + 0.8, top.z - 3.2), look: c, fov: 28 }, { pos: V3(top.x - 3.7, top.y + 0.75, top.z - 2.6), look: c, fov: 26 }, lt / 10, t, 0.012);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(c); S.dof.uniforms.uAperture.value = 12;
      S.lanterns.forEach((l, i) => l.set(0.9, t, i));
      return { tod: lerp(18.75, 19.1, lt / 10), sunAz: 0.24, focus: c, exposure: 1.3, shadowSize: 12, emit: 0.4, bloom: 0.7 };
    },
  },
  // 12. DUSK — pier lanterns flicker on one by one; the last post stays dark
  {
    start: 140, end: 156, dissolve: 1.5, run(S, H, lt, t) {
      const order = [...S.lanterns.keys()].sort((a, b) => S.lanterns[a].group.position.z - S.lanterns[b].group.position.z);
      order.forEach((idx, n) => { const on = smooth(range(lt, 2 + n * 0.7, 2.4 + n * 0.7)); S.lanterns[idx].set(on, t, idx); });
      H.pose(S.juno, t, { pos: PIER_END.slice(), yaw: 0.05, headPitch: -0.28, armL: [0.02, 0.05], armR: [0.02, -0.05] });
      H.move({ pos: V3(80, 20.9, 118), look: V3(88.5, 22.6, 94), fov: 30 }, { pos: V3(82.5, 21.2, 112), look: V3(88.5, 22.8, 96), fov: 27 }, lt / 16, t, 0.03);
      return { tod: lerp(19.25, 19.55, lt / 16), sunAz: 0.6, focus: V3(88.5, 22, 92), exposure: 1.1, shadowSize: 30, emit: 0.9, mist: 0.25, lights: 1.1 };
    },
  },
  // 13. BLUE HOUR — Rowan rows away into the mist
  {
    start: 156, end: 172, fadeIn: 1.5, run(S, H, lt, t) {
      const b = boatLeave(t, 157, 176);
      placeBoat(S, H, b, t, t > 157.5, PI);
      S.boat.lantern.set(0.9, t, 77);
      S.lanterns.forEach((l, i) => l.set(0.7, t, i));
      H.pose(S.juno, t, { pos: [91.2, 21, 98.9], yaw: 0.45, headPitch: 0.05, armL: [0.05, 0.05], armR: [0.02 - smooth(range(t, 162.6, 163.2)) * (1 - smooth(range(t, 166, 167))) * 0.3, -0.05] });
      if (t < 161.8) H.move({ pos: V3(89.0, 23.1, 95.4), look: V3(96.5, 21.4, 102.5), fov: 32 }, { pos: V3(89.2, 23.0, 95.7), look: V3(96.5, 21.3, 104.5), fov: 29 }, range(t, 156, 161.8), t, 0.015);
      else H.move({ pos: V3(86.2, 21.0, 97.0), look: V3(93, 21.5, 108), fov: 34 }, { pos: V3(86.6, 21.1, 97.6), look: V3(95, 21.3, 118), fov: 30 }, range(t, 161.8, 172), t, 0.02);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(t < 161.8 ? b.p.clone().add(V3(0, 1.2, 0)) : V3(91.2, 22.5, 98.9)); S.dof.uniforms.uAperture.value = 6;
      return { tod: 5.25, sunAz: -0.2, focus: V3(92, 21, 104), exposure: 1.25, shadowSize: 20, emit: 0.7, mist: lerp(0.35, 1.0, smooth(range(t, 160, 168))), fogMul: 1.4, lights: 1 };
    },
  },
  // 14. THE WORKSHOP — night, Juno builds the finest lantern
  {
    start: 172, end: 184, dissolve: 1.2, run(S, H, lt, t) {
      const hammer = Math.max(0, Math.sin(t * 6)) ** 3;
      H.pose(S.juno, t, { pos: [82.6, 22, 60.3], yaw: 0.05, headPitch: 0.45, armR: [-0.9 - hammer * 0.5, -0.15], armL: [-0.9, 0.2] });
      S.workLantern.set(1, t, 5);
      S.handLantern.set(smooth(range(lt, 7, 9)) * 1.1, t, 99);
      S.handLantern.group.position.set(83.4, 23, 61.4); S.handLantern.group.rotation.set(0, 0, 0); S.handLantern.group.scale.setScalar(1.1);
      S.scene.add(S.handLantern.group);
      const c = V3(83.0, 23.2, 61.2);
      H.move({ pos: V3(84.6, 23.5, 63.8), look: c, fov: 30 }, { pos: V3(84.1, 23.4, 63.0), look: V3(83.2, 23.25, 61.3), fov: 26 }, lt / 12, t, 0.012);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(V3(83.3, 23.2, 61.4)); S.dof.uniforms.uAperture.value = 14;
      return { tod: 22.2, focus: c, exposure: 1.15, shadowSize: 12, emit: 1, lights: 1.2, bloom: 0.75 };
    },
  },
  // 15. END OF THE PIER — night, the last lantern is lit
  {
    start: 184, end: 196, dissolve: 1.2, run(S, H, lt, t) {
      const w = H.walk([[88.5, 21, 94], [88.5, 21, 98.3]], 1.2, lt, 0);
      const lift = smooth(range(lt, 3.6, 4.8));
      const hung = lt > 5.0;
      H.pose(S.juno, t, { ...w, yaw: 0, headPitch: -0.45 * lift, armR: [w.walkAmp ? -0.3 : -2.6 * lift * (hung ? 1 - smooth(range(lt, 5.6, 6.6)) : 1), -0.05], armL: [0.02, 0.05] });
      if (!hung) { S.handLantern.group.scale.setScalar(1); S.handLantern.group.rotation.set(0, 0, 0); S.handLantern.group.position.set(0, -0.3, 0); S.juno.held(S.handLantern.group, 'R'); S.handLantern.set(0.15, t, 99); }
      S.lastLantern.group.visible = hung;
      S.lastLantern.set(easeOut(range(lt, 5.6, 7.2)), t, 123);
      S.lanterns.forEach((l, i) => l.set(0.85, t, i));
      H.move({ pos: V3(86.2, 22.6, 101.6), look: V3(88.5, 23.3, 98.6), fov: 32 }, { pos: V3(86.9, 23.2, 101.0), look: V3(88.4, 23.5, 98.9), fov: 26 }, lt / 12, t, 0.015);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(V3(w.pos[0], 23.2, w.pos[2])); S.dof.uniforms.uAperture.value = 10;
      return { tod: 22.6, focus: V3(88.5, 22, 98), exposure: 1.2, shadowSize: 14, emit: 1, lights: 1.3, bloom: 0.8 };
    },
  },
  // 16a. WINTER — snowy village, smoke from chimneys
  {
    start: 196, end: 205, dissolve: 1.6, run(S, H, lt, t) {
      S.U.uSnow.value = 1;
      S.fx.snow.points.visible = true; snowField(S.fx.snow, t, V3(88, 20, 68), 34, 26, 1);
      smokeField(S.fx.smoke, t, [[71.5, 34, 60.5], [103.5, 34, 51.5], [105.5, 33, 64.5]], 1);
      S.lanterns.forEach((l, i) => l.set(0.7, t, i));
      S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
      H.move({ pos: V3(118, 38, 88), look: V3(88, 24, 62), fov: 38 }, { pos: V3(112, 33, 92), look: V3(88, 23.5, 66), fov: 36 }, lt / 9, t, 0.03);
      S.U.uWind.value = 0.4;
      return { tod: 13.5, sunAz: 0.2, focus: V3(88, 24, 65), exposure: 1.0, shadowSize: 50, emit: 0.35, overcast: 0.75, fogMul: 2.3 };
    },
  },
  // 16b. WINTER DUSK — Juno walks the snowy pier to the burning lantern
  {
    start: 205, end: 214, run(S, H, lt, t) {
      S.U.uSnow.value = 1;
      S.fx.snow.points.visible = true; snowField(S.fx.snow, t, V3(88.5, 20, 92), 16, 14, 1);
      const w = H.walk([[88.5, 21, 82], [88.5, 21, 95]], 1.25, lt, 0);
      H.pose(S.juno, t, { ...w, headPitch: 0.15 });
      S.lanterns.forEach((l, i) => l.set(0.9, t, i));
      S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
      const jp = V3(...w.pos);
      H.cam({ pos: V3(jp.x - 1.1, jp.y + 2.3, jp.z - 4.4), look: V3(88.5, 22.8, jp.z + 5), fov: 34, shake: 0.03, t });
      S.U.uWind.value = 0.4;
      return { tod: 18.9, sunAz: 0.5, focus: V3(88.5, 22, 92), exposure: 1.15, shadowSize: 20, emit: 0.9, overcast: 0.55, fogMul: 2.0, lights: 1.2 };
    },
  },
  // 17. WINTER NIGHT — Juno waits beneath the last lantern
  {
    start: 214, end: 226, dissolve: 1.2, run(S, H, lt, t) {
      S.U.uSnow.value = 1;
      S.fx.snow.points.visible = true; snowField(S.fx.snow, t, V3(88.5, 20, 100), 12, 10, 1);
      H.pose(S.juno, t, { pos: H.sitPos(87.35, 21, 99.35), yaw: 0, legs: [-0.35 + Math.sin(t * 1.2) * 0.12, -0.35 + Math.sin(t * 1.2 + 1.4) * 0.12], armL: [0.1, 0.25], armR: [0.1, -0.25], headPitch: 0.08, headYaw: Math.sin(t * 0.3) * 0.12 });
      S.lanterns.forEach((l, i) => l.set(0.9, t, i));
      S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
      const c = V3(87.6, 22.1, 99.7);
      H.move({ pos: V3(85.4, 20.9, 106.2), look: c, fov: 30 }, { pos: V3(86.1, 21.35, 103.3), look: V3(87.5, 22.35, 99.6), fov: 28 }, lt / 12, t, 0.02);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(c); S.dof.uniforms.uAperture.value = 10;
      S.U.uWind.value = 0.4;
      return { tod: 22.8, focus: c, exposure: 1.2, shadowSize: 14, emit: 1, lights: 1.3, bloom: 0.8, mist: 0.25 };
    },
  },
  // 18a. SPRING NIGHT — fireflies; a tiny light far out on the lake
  {
    start: 226, end: 233, dissolve: 2.0, run(S, H, lt, t) {
      H.pose(S.juno, t, { pos: H.sitPos(87.35, 21, 99.35), yaw: 0, legs: [-0.35 + Math.sin(t * 1.2) * 0.12, -0.35 + Math.sin(t * 1.2 + 1.4) * 0.12], armL: [0.1, 0.25], armR: [0.1, -0.25], headPitch: lerp(0.08, -0.05, smooth(range(lt, 3, 5))) });
      S.lanterns.forEach((l, i) => l.set(0.9, t, i));
      S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
      S.fx.fireflies.points.visible = true; fireflyField(S.fx.fireflies, t, V3(88, 20.5, 92), 18, 1);
      const b = boatArrive(t, 226, 247, V3(80, 20, 146));
      placeBoat(S, H, b, t, true, 0);
      S.boat.lantern.set(2.2, t, 77); S.boat.lantern.group.scale.setScalar(1.6);
      H.move({ pos: V3(86.3, 23.35, 96.8), look: V3(86, 21.6, 130), fov: 34 }, { pos: V3(87.0, 22.9, 97.0), look: V3(84, 21.3, 136), fov: 30 }, lt / 7, t, 0.012);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = 40; S.dof.uniforms.uAperture.value = 5;
      return { tod: 23.1, focus: V3(88.5, 22, 104), exposure: 1.25, shadowSize: 20, emit: 1, lights: 1.3, bloom: 0.85 };
    },
  },
  // 18b. SPRING NIGHT — Juno rises
  {
    start: 233, end: 240, run(S, H, lt, t) {
      const up = smooth(range(lt, 1.2, 2.6));
      const sitP = H.sitPos(87.35, 21, 99.35);
      H.pose(S.juno, t, {
        pos: [87.35, lerp(sitP[1], 21, up), lerp(99.35, 98.7, up)], yaw: 0,
        legs: up < 1 ? [lerp(-0.35, 0, up) * (1 - up) + (1 - up) * -1.2, lerp(-0.35, 0, up) * (1 - up) + (1 - up) * -1.2] : undefined,
        armL: [0.02, 0.05 + (1 - up) * 0.2], armR: [0.02 - smooth(range(lt, 3.5, 4.5)) * 0.6, -0.05], headPitch: -0.05, headYaw: 0,
      });
      S.lanterns.forEach((l, i) => l.set(0.9, t, i));
      S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
      S.fx.fireflies.points.visible = true; fireflyField(S.fx.fireflies, t, V3(88, 20.5, 96), 12, 1);
      const b = boatArrive(t, 226, 247, V3(80, 20, 146));
      placeBoat(S, H, b, t, true, 0);
      S.boat.lantern.set(2.2, t, 77); S.boat.lantern.group.scale.setScalar(1.6);
      const c = V3(87.35, lerp(22.2, 22.9, up), 99.0);
      H.move({ pos: V3(86.0, 22.0, 102.2), look: c, fov: 30 }, { pos: V3(86.2, 22.5, 101.4), look: V3(87.35, 22.9, 98.9), fov: 28 }, lt / 7, t, 0.012);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(c); S.dof.uniforms.uAperture.value = 12;
      return { tod: 23.2, focus: V3(88.5, 22, 99), exposure: 1.25, shadowSize: 14, emit: 1, lights: 1.3, bloom: 0.85 };
    },
  },
  // 19a. The boat glides in, following the lantern
  {
    start: 240, end: 247, run(S, H, lt, t) {
      const b = boatArrive(t, 226, 247, V3(80, 20, 146));
      placeBoat(S, H, b, t, t < 245.5, 0);
      S.rowan.neck.rotation.y = 0;
      S.boat.lantern.set(1.2, t, 77);
      S.lanterns.forEach((l, i) => l.set(0.9, t, i));
      S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
      H.pose(S.juno, t, { pos: [89.9, 21, 98.1], yaw: lerp(0.2, PI / 2 - 0.2, smooth(range(t, 243, 245))), armR: [0.02, -0.05], armL: [0.02, 0.05] });
      S.fx.fireflies.points.visible = true; fireflyField(S.fx.fireflies, t, V3(91, 20.5, 100), 12, 1);
      H.cam({ pos: V3(b.p.x - 3.6, 21.9, b.p.z + 4.8), look: V3(b.p.x - 0.8, 21.5, b.p.z - 1.2), fov: 32, shake: 0.03, t });
      return { tod: 23.3, focus: b.p.clone(), exposure: 1.25, shadowSize: 16, emit: 1, lights: 1.3, bloom: 0.85, mist: 0.2 };
    },
  },
  // 19b. "I finished the map."
  {
    start: 247, end: 250.6, run(S, H, lt, t) {
      coupleOnPier(S, H, t, 0.2);
      const show = smooth(range(t, 248.2, 249.2));
      H.pose(S.rowan, t, { pos: [91.1, 21, 98.1], yaw: -PI / 2, armL: [-1.05 * show, 0.25 * show], armR: [-1.05 * show, -0.25 * show], headPitch: 0.05 });
      if (show > 0.01) { S.mapFinished.position.set(0, 1.25, 0.55); S.mapFinished.rotation.set(-0.25, 0, 0); S.mapFinished.scale.setScalar(show); S.rowan.root.add(S.mapFinished); }
      H.move({ pos: V3(88.2, 23.0, 96.6), look: V3(91.1, 22.9, 98.2), fov: 30 }, { pos: V3(88.4, 23.0, 96.8), look: V3(91.1, 22.9, 98.2), fov: 28 }, lt / 3.6, t, 0.012);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(V3(91.1, 22.9, 98.1)); S.dof.uniforms.uAperture.value = 10;
      return { tod: 23.4, focus: V3(90.5, 22, 98), exposure: 1.25, shadowSize: 12, emit: 1, lights: 1.3, bloom: 0.8 };
    },
  },
  // 19c. INSERT — the map: HOME
  {
    start: 250.6, end: 256, run(S, H, lt, t) {
      coupleOnPier(S, H, t, 0.2);
      H.pose(S.rowan, t, { pos: [91.1, 21, 98.1], yaw: -PI / 2, armL: [-1.05, 0.25], armR: [-1.05, -0.25], headPitch: 0.1 });
      S.mapFinished.position.set(0, 1.25, 0.55); S.mapFinished.rotation.set(-0.25, 0, 0); S.mapFinished.scale.setScalar(1); S.rowan.root.add(S.mapFinished);
      S.rowan.root.updateMatrixWorld(true);
      const mc = new THREE.Vector3(); S.mapFinished.getWorldPosition(mc);
      const n = new THREE.Vector3(0, 0, 1).applyQuaternion(S.mapFinished.getWorldQuaternion(new THREE.Quaternion()));
      const k = lt / 5.4;
      const home = mc.clone().add(V3(0, -0.07, 0));
      H.move({ pos: mc.clone().addScaledVector(n, 1.25).add(V3(0, 0.1, 0)), look: mc, fov: 30 }, { pos: home.clone().addScaledVector(n, 0.55).add(V3(0, 0.05, 0)), look: home, fov: 30 }, k, t, 0.004);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(home); S.dof.uniforms.uAperture.value = 8;
      return { tod: 23.4, focus: mc, exposure: 1.3, shadowSize: 8, emit: 1, lights: 1.5, bloom: 0.8 };
    },
  },
  // 20a. "You followed the lantern." / "I followed you."
  {
    start: 256, end: 264.5, run(S, H, lt, t) {
      const step = smooth(range(t, 263.2, 264.4));
      H.pose(S.juno, t, { pos: [89.9 + step * 0.35, 21, 98.1], yaw: PI / 2, headPitch: 0.05, armR: [0.02, -0.05], armL: [0.02, 0.05], headRoll: talking('rowan', t) ? 0.1 : 0 });
      H.pose(S.rowan, t, { pos: [91.1 - step * 0.35, 21, 98.1], yaw: -PI / 2, headPitch: 0.05, armL: [-0.2, 0.05], armR: [-0.2, -0.05] });
      S.lanterns.forEach((l, i) => l.set(0.9, t, i));
      S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
      placeBoat(S, H, { p: DOCK.clone(), yaw: Math.PI }, t, false, 0, false); S.boat.lantern.set(1.0, t, 77);
      S.fx.fireflies.points.visible = true; fireflyField(S.fx.fireflies, t, V3(90, 20.5, 99), 10, 1);
      const juno = t < 261;
      const c = juno ? V3(89.9, 22.8, 98.1) : V3(91.1, 22.8, 98.1);
      if (juno) H.move({ pos: V3(92.5, 22.95, 99.4), look: c, fov: 28 }, { pos: V3(92.3, 22.95, 99.2), look: c, fov: 26 }, range(t, 256, 261), t, 0.01);
      else H.move({ pos: V3(88.5, 22.95, 96.8), look: c, fov: 28 }, { pos: V3(88.7, 22.95, 97.0), look: c, fov: 26 }, range(t, 261, 264.5), t, 0.01);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = S.camera.position.distanceTo(c); S.dof.uniforms.uAperture.value = 13;
      return { tod: 23.5, focus: V3(90.5, 22, 98), exposure: 1.25, shadowSize: 12, emit: 1, lights: 1.4, bloom: 0.85 };
    },
  },
  // 20b. The embrace — orbit, fireflies, hearts, sky lanterns rise
  {
    start: 264.5, end: 270, run(S, H, lt, t) {
      hug(S, H, t);
      const c = V3(90.5, 22.6, 98.1);
      H.orbit(c, 4.0, 0.5, 0.75, -0.3, lt / 5.5, t, 30, 0, (k) => k);
      S.dof.enabled = true; S.dof.uniforms.uFocus.value = 4.0; S.dof.uniforms.uAperture.value = 12;
      return { tod: 23.5, focus: c, exposure: 1.25, shadowSize: 12, emit: 1, lights: 1.4, bloom: 0.9 };
    },
  },
  // 21. Crane up to the stars
  {
    start: 270, end: 285, run(S, H, lt, t) {
      hug(S, H, t);
      S.youngTree.visible = true;
      const k = lt / 15;
      H.spline([V3(94.5, 22.4, 104), V3(97, 30, 112), V3(96, 48, 122), V3(92, 62, 128)], [V3(90.5, 22.5, 98.1), V3(90, 24, 94), V3(92, 32, 70), V3(100, 58, 30)], k, t, [32, 44], 0.02, (x) => smooth(x) * 0.8 + x * 0.2);
      return { tod: 23.6, focus: V3(90, 22, 90), exposure: 1.25, shadowSize: 40, emit: 1, lights: 1.4, bloom: 0.9 };
    },
  },
  // 22. Final wide — the whole valley glowing, title, fade out
  {
    start: 285, end: 300, dissolve: 1.5, run(S, H, lt, t) {
      hug(S, H, t);
      S.youngTree.visible = true;
      H.move({ pos: V3(78, 22.4, 134), look: V3(92, 27, 90), fov: 40 }, { pos: V3(79, 23.4, 128), look: V3(92, 28, 88), fov: 38 }, lt / 8, t, 0.02);
      return { tod: 23.7, focus: V3(90, 22, 96), exposure: 1.25, shadowSize: 40, emit: 1, lights: 1.4, bloom: 0.95, fadeOut: [290.5, 292.4] };
    },
  },
];

function sitCouple(S, H, t, top, variant) {
  const jP = H.sitPos(top.x - 0.9, top.y, top.z - 0.35), rP = H.sitPos(top.x - 0.9, top.y, top.z + 0.75);
  const yaw = -PI / 2 + 0.7;
  const lean = variant ? smooth(range(t, 132, 134)) : 0;
  H.pose(S.juno, t, { pos: jP, yaw, sit: true, legSwing: true, armL: [-0.5, 0.2], armR: [-0.5, -0.1], headYaw: talking('juno', t) || talking('rowan', t) ? -0.45 : 0, headPitch: variant ? 0.15 + lean * 0.12 : 0 });
  H.pose(S.rowan, t, { pos: rP, yaw, sit: true, legSwing: true, armL: [-0.5, 0.1], armR: [-0.5, -0.2], headYaw: talking('rowan', t) ? 0.45 : talking('juno', t) ? 0.35 : 0, headPitch: variant ? 0.1 : 0 });
}
function coupleOnPier(S, H, t) {
  H.pose(S.juno, t, { pos: [89.9, 21, 98.1], yaw: PI / 2, headPitch: 0.05, armR: [0.02, -0.05], armL: [0.02, 0.05] });
  S.lanterns.forEach((l, i) => l.set(0.9, t, i));
  S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
  placeBoat(S, H, { p: DOCK.clone(), yaw: Math.PI }, t, false, 0, false); S.boat.lantern.set(1.0, t, 77);
  S.fx.fireflies.points.visible = true; fireflyField(S.fx.fireflies, t, V3(90, 20.5, 99), 10, 1);
}
function hug(S, H, t) {
  const sway = Math.sin(t * 1.2) * 0.04;
  H.pose(S.juno, t, { pos: [90.22, 21, 98.1], yaw: PI / 2, bodyRoll: sway, armL: [-1.25, -0.45], armR: [-1.25, 0.45], headPitch: -0.1, headYaw: 0.25 });
  H.pose(S.rowan, t, { pos: [90.78, 21, 98.1], yaw: -PI / 2, bodyRoll: -sway, armL: [-1.35, -0.55], armR: [-1.35, 0.55], headPitch: 0.1, headYaw: -0.25 });
  S.lanterns.forEach((l, i) => l.set(0.9, t, i));
  S.lastLantern.group.visible = true; S.lastLantern.set(1, t, 123);
  placeBoat(S, H, { p: DOCK.clone(), yaw: Math.PI }, t, false, 0, false); S.boat.lantern.set(1.0, t, 77);
  S.fx.fireflies.points.visible = true; fireflyField(S.fx.fireflies, t, V3(90, 20.5, 97), 16, 1);
  S.fx.hearts.points.visible = true; heartField(S.fx.hearts, t, V3(90.5, 23.3, 98.1), clamp((t - 265) / 1, 0, 1) * clamp((278 - t) / 2, 0, 1));
  S.fx.skyLanterns.update(t - 262, 1);
}

// ---------------- apply ----------------
function applyShot(S, shot, lt, t) {
  const H = S._H ?? (S._H = makeHelpers(S));
  resetStage(S);
  const env = shot.run(S, H, lt, t);
  const sk = S.sky.set({ tod: env.tod, center: env.focus, sunAz: env.sunAz ?? 0, fogMul: env.fogMul ?? 1, shadowSize: env.shadowSize ?? 30, time: t, overcast: env.overcast ?? 0 });
  S.U.uEmit.value = env.emit ?? sk.night;
  S.mist.set(env.mist ?? 0, sk.k.fog.clone().lerp(new THREE.Color('#ffffff'), 0.35));
  S.renderer.toneMappingExposure = env.exposure ?? 1;
  if (env.bloom) S.bloom.strength = env.bloom;
  S.lightPool.assign(S.allLanterns, env.focus, env.lights ?? 1);
  if (S.dof.enabled && S.dof.uniforms.uAperture.value <= 0) S.dof.enabled = false;
  return { env, time: t };
}

export const FILM = {
  duration: DURATION,
  shots: SHOTS,
  applyShot(S, shot, lt, t) { return applyShot(S, shot, lt, t); },
  apply(S, t) {
    const i = SHOTS.findIndex((s) => t >= s.start && t < s.end);
    const shot = SHOTS[i === -1 ? SHOTS.length - 1 : i];
    const lt = t - shot.start;
    const { env } = applyShot(S, shot, lt, t);
    const plan = { time: t, texts: overlays(t), fade: 0 };
    if (shot.fadeIn) plan.fade = Math.max(plan.fade, 1 - smooth(lt / shot.fadeIn));
    if (env.fadeOut) plan.fade = Math.max(plan.fade, smooth(range(t, env.fadeOut[0], env.fadeOut[1])));
    if (t >= 292.4) plan.black = true;
    // dip to black before the blue-hour departure
    if (t > 154.5 && t < 156) plan.fade = Math.max(plan.fade, smooth(range(t, 154.5, 156)));
    if (shot.dissolve && lt < shot.dissolve && i > 0) {
      const prev = SHOTS[i - 1];
      plan.dissolveFrom = { shot: prev, t: t - prev.start, alpha: 1 - smooth(lt / shot.dissolve) };
    }
    return plan;
  },
};
