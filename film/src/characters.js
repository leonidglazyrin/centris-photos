import * as THREE from 'three';
import { hexToRgb } from './util.js';

const PX = 1 / 16;

// A tiny pixel canvas helper
function pix(w, h, fn) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
  const ctx = cv.getContext('2d');
  const put = (x, y, c) => { if (!c) return; ctx.fillStyle = c; ctx.fillRect(x, y, 1, 1); };
  const rect = (x, y, rw, rh, c) => { ctx.fillStyle = c; ctx.fillRect(x, y, rw, rh); };
  fn({ put, rect, w, h, ctx });
  return cv;
}
function shadeHex(hex, f) {
  const [r, g, b] = hexToRgb(hex);
  const c = (v) => Math.max(0, Math.min(255, Math.round(v * f))).toString(16).padStart(2, '0');
  return '#' + c(r) + c(g) + c(b);
}
// subtle per-pixel noise so flat colours feel like painted pixels
function noisy(ctx, w, h, amt = 0.06, seed = 1) {
  const id = ctx.getImageData(0, 0, w, h);
  let s = seed;
  for (let i = 0; i < id.data.length; i += 4) {
    s = (s * 16807) % 2147483647;
    const f = 1 + ((s / 2147483647) - 0.5) * amt * 2;
    id.data[i] *= f; id.data[i + 1] *= f; id.data[i + 2] *= f;
  }
  ctx.putImageData(id, 0, 0);
}
function tex(cv) {
  const t = new THREE.CanvasTexture(cv);
  t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestFilter; t.generateMipmaps = false;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// BoxGeometry face order: +x, -x, +y, -y, +z, -z  (character faces +z, so +x is its left)
function paintedBox(w, h, d, faces, mats) {
  const g = new THREE.BoxGeometry(w * PX, h * PX, d * PX);
  const order = ['left', 'right', 'top', 'bottom', 'front', 'back'];
  const dims = { left: [d, h], right: [d, h], top: [w, d], bottom: [w, d], front: [w, h], back: [w, h] };
  const materials = order.map((k) => {
    const [fw, fh] = dims[k];
    const cv = pix(fw, fh, (c) => faces(k, c));
    noisy(cv.getContext('2d'), fw, fh, 0.05, fw * 7 + fh * 13 + k.length);
    const m = new THREE.MeshLambertMaterial({ map: tex(cv) });
    if (mats) mats[k] = m;
    return m;
  });
  const mesh = new THREE.Mesh(g, materials);
  mesh.castShadow = true; mesh.receiveShadow = true;
  return mesh;
}

// ---------------- skins (original characters) ----------------
const JUNO = {
  skin: '#f3c9a8', blush: '#eba08f', hair: '#b9552f', hairD: '#933f21', hairL: '#d4743f', eye: '#3f8a5a', lash: '#3a2420', mouth: '#b8615a',
  top: '#8fae7c', topD: '#76965f', apron: '#f2e7d0', belt: '#7a4f2e', leg: '#f2e7d0', boot: '#6b4028', flower: '#f59ac0',
};
const ROWAN = {
  skin: '#c58a62', blush: '#b8705a', hair: '#2f2320', hairD: '#1f1714', hairL: '#4a372e', eye: '#4a2e1e', lash: '#20150f', mouth: '#8a4f3f',
  top: '#2f4a74', topD: '#253b5e', button: '#dcb65a', scarf: '#c2433f', scarfD: '#9f3432', strap: '#7a4f2e', leg: '#5b5048', boot: '#3b2a20',
};

function headPainter(S, kind, blink) {
  return (face, { put, rect, w, h }) => {
    rect(0, 0, w, h, S.skin);
    if (face === 'top') { rect(0, 0, w, h, S.hair); for (let i = 0; i < 8; i++) put((i * 3) % 8, i, S.hairL); return; }
    if (face === 'bottom') { rect(0, 0, w, h, S.skin); return; }
    if (face === 'back') {
      rect(0, 0, w, h, S.hair);
      for (let x = 0; x < 8; x++) put(x, (x * 5) % 8, S.hairD);
      if (kind === 'rowan') rect(0, 7, 8, 1, S.skin);
      return;
    }
    if (face === 'left' || face === 'right') {
      // 8 wide (depth) x 8 tall; x=0 is back for 'left'(+x) as seen from +x... paint symmetric-ish
      rect(0, 0, 8, 3, S.hair);
      const backSide = face === 'left' ? [0, 1, 2, 3] : [4, 5, 6, 7];
      for (const x of backSide) rect(x, 0, 1, kind === 'juno' ? 8 : 6, S.hair);
      for (let y = 0; y < 8; y++) put(backSide[0] + (y % 2), y, S.hairD);
      if (kind === 'juno' && face === 'left') { put(4, 2, S.flower); put(5, 2, S.flower); put(4, 1, shadeHex(S.flower, 1.15)); put(5, 3, shadeHex(S.flower, 0.85)); }
      const ear = face === 'left' ? 4 : 3;
      put(ear, 4, shadeHex(S.skin, 0.9));
      return;
    }
    // front
    rect(0, 0, 8, 2, S.hair);
    if (kind === 'juno') { rect(0, 2, 1, 6, S.hair); rect(7, 2, 1, 6, S.hair); put(1, 2, S.hair); put(2, 2, S.hairL); put(6, 2, S.hair); put(5, 1, S.hairL); put(3, 1, S.hairD); }
    else { put(0, 2, S.hair); put(7, 2, S.hair); put(2, 2, S.hair); put(5, 2, S.hairL); put(3, 0, S.hairL); put(6, 1, S.hairD); }
    if (blink) {
      rect(1, 4, 2, 1, S.lash); rect(5, 4, 2, 1, S.lash);
    } else {
      put(1, 4, '#ffffff'); put(2, 4, S.eye); put(5, 4, S.eye); put(6, 4, '#ffffff');
      put(2, 3, S.lash); put(5, 3, S.lash);
      if (kind === 'juno') { put(1, 3, S.lash); put(6, 3, S.lash); }
    }
    put(1, 5, S.blush); put(6, 5, S.blush);
    put(3, 6, S.mouth); put(4, 6, S.mouth);
    if (kind === 'rowan') { put(2, 3, S.hairD); put(5, 3, S.hairD); }
  };
}

function bodyPainter(S, kind) {
  return (face, { put, rect, w, h }) => {
    if (kind === 'juno') {
      rect(0, 0, w, h, S.top);
      if (face === 'front') {
        rect(1, 3, 6, 9, S.apron); rect(0, 6, 8, 1, S.belt); put(2, 3, S.apron);
        put(3, 0, S.skin); put(4, 0, S.skin); put(3, 1, S.skin); put(4, 1, S.skin);
        put(2, 8, shadeHex(S.apron, 0.9)); put(5, 9, shadeHex(S.apron, 0.9)); // pocket
        put(3, 8, shadeHex(S.apron, 0.9)); put(4, 8, shadeHex(S.apron, 0.9));
      }
      if (face === 'back') { rect(1, 0, 6, 6, S.hair); rect(2, 6, 4, 1, S.hairD); rect(0, 6, 8, 1, S.belt); rect(3, 6, 2, 2, S.apron); }
      if (face === 'left' || face === 'right') { rect(0, 6, 4, 1, S.belt); }
      for (let y = 7; y < 12; y++) put((y * 3) % w, y, S.topD);
    } else {
      rect(0, 0, w, h, S.top);
      if (face === 'front') {
        rect(0, 0, 8, 2, S.scarf); put(2, 2, S.scarf); put(2, 3, S.scarfD); put(2, 4, S.scarf);
        rect(4, 2, 1, 10, S.topD);
        put(5, 4, S.button); put(5, 7, S.button); put(5, 10, S.button);
        for (let i = 0; i < 8; i++) put(i, 2 + i, S.strap);
      }
      if (face === 'back') { rect(0, 0, 8, 2, S.scarf); for (let i = 0; i < 8; i++) put(7 - i, 2 + i, S.strap); }
      if (face === 'top') rect(0, 0, w, h, S.scarf);
      if (face === 'left' || face === 'right') { rect(0, 0, 4, 2, S.scarf); }
      rect(0, 11, w, 1, S.topD);
    }
  };
}
function armPainter(S, kind) {
  return (face, { put, rect, w, h }) => {
    const sleeve = kind === 'juno' ? 5 : 10;
    rect(0, 0, w, h, S.top);
    rect(0, sleeve, w, h - sleeve, S.skin);
    if (kind === 'rowan') rect(0, sleeve - 1, w, 1, S.topD);
    if (kind === 'juno') rect(0, sleeve - 1, w, 1, S.topD);
    if (face === 'top') rect(0, 0, w, h, S.top);
    if (face === 'bottom') rect(0, 0, w, h, S.skin);
  };
}
function legPainter(S, kind) {
  return (face, { put, rect, w, h }) => {
    if (kind === 'juno') { rect(0, 0, w, h, S.top); rect(0, 5, w, 4, S.leg); rect(0, 9, w, 3, S.boot); rect(0, 4, w, 1, S.topD); }
    else { rect(0, 0, w, h, S.leg); rect(0, 9, w, 3, S.boot); rect(0, 0, w, 3, S.top); }
    if (face === 'bottom') rect(0, 0, w, h, S.boot);
    if (face === 'top') rect(0, 0, w, h, kind === 'juno' ? S.top : S.leg);
  };
}

export class Character {
  constructor(kind) {
    this.kind = kind;
    const S = kind === 'juno' ? JUNO : ROWAN;
    this.root = new THREE.Group();
    this.hips = new THREE.Group(); this.hips.position.y = 12 * PX; this.root.add(this.hips);
    const headMats = {};
    this.body = paintedBox(8, 12, 4, bodyPainter(S, kind)); this.body.position.y = 6 * PX; this.hips.add(this.body);
    this.neck = new THREE.Group(); this.neck.position.y = 12 * PX; this.hips.add(this.neck);
    this.head = paintedBox(8, 8, 8, headPainter(S, kind, false), headMats); this.head.position.y = 4 * PX; this.neck.add(this.head);
    const blinkCv = pix(8, 8, (c) => headPainter(S, kind, true)('front', c));
    noisy(blinkCv.getContext('2d'), 8, 8, 0.05, 8 * 7 + 8 * 13 + 5);
    this.faceOpen = headMats.front.map; this.faceBlink = tex(blinkCv); this.faceMat = headMats.front;
    if (kind === 'juno') {
      // long hair falling down the back
      const hairBack = paintedBox(8, 7, 1, (f, c) => { c.rect(0, 0, c.w, c.h, S.hair); for (let i = 0; i < 8; i++) c.put(i, (i * 3) % 7, S.hairD); c.put(3, 6, S.hairL); });
      hairBack.position.set(0, -1.5 * PX, -4.5 * PX); this.neck.add(hairBack);
    } else {
      // tousled hair on top
      const tuft = paintedBox(8, 1, 8, (f, c) => { c.rect(0, 0, c.w, c.h, S.hair); for (let i = 0; i < 8; i++) c.put(i, (i * 5) % 8, S.hairL); });
      tuft.position.set(0, 8.5 * PX, -0.2 * PX); tuft.scale.set(1.04, 1, 1.04); this.neck.add(tuft);
    }
    const mkArm = (side) => {
      const g = new THREE.Group(); g.position.set(side * 6 * PX, 10 * PX, 0); this.hips.add(g);
      const m = paintedBox(4, 12, 4, armPainter(S, kind)); m.position.y = -4 * PX; g.add(m);
      const hand = new THREE.Group(); hand.position.y = -10 * PX; g.add(hand);
      g.userData.hand = hand;
      return g;
    };
    this.armL = mkArm(1); this.armR = mkArm(-1);
    const mkLeg = (side) => {
      const g = new THREE.Group(); g.position.set(side * 2 * PX, 12 * PX, 0); this.root.add(g);
      const m = paintedBox(4, 12, 4, legPainter(S, kind)); m.position.y = -6 * PX; g.add(m);
      return g;
    };
    this.legL = mkLeg(1); this.legR = mkLeg(-1);
    if (kind === 'rowan') {
      // satchel on the hip
      const bag = paintedBox(5, 4, 2, (f, c) => { c.rect(0, 0, c.w, c.h, '#8a5a34'); c.rect(0, 0, c.w, 1, '#6d4527'); c.put(2, 2, '#dcb65a'); });
      bag.position.set(-4.5 * PX, 1 * PX, 1.8 * PX); bag.rotation.y = 0.35; this.hips.add(bag);
    }
    this.root.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  }

  held(obj, side = 'R') {
    const hand = (side === 'R' ? this.armR : this.armL).userData.hand;
    for (const c of [...hand.children]) hand.remove(c);
    if (obj) hand.add(obj);
  }

  // p: {pos:[x,y,z], yaw, walk, walkAmp, headYaw, headPitch, armL:[x,z], armR:[x,z], legs:[l,r], sit, blink, time, talk, bodyPitch}
  pose(p) {
    const t = p.time ?? 0;
    this.root.visible = p.visible ?? true;
    this.root.position.set(p.pos[0], p.pos[1], p.pos[2]);
    this.root.rotation.set(0, p.yaw ?? 0, 0);
    const amp = p.walkAmp ?? 0;
    const sw = Math.sin(p.walk ?? 0) * amp;
    const breathe = Math.sin(t * 1.6) * 0.012;
    const bob = Math.abs(Math.cos(p.walk ?? 0)) * amp * 0.05;
    this.hips.position.y = 12 * PX + bob + (p.hipsDy ?? 0);
    this.hips.rotation.x = p.bodyPitch ?? 0;
    this.hips.rotation.z = p.bodyRoll ?? 0;
    this.legL.rotation.set(sw, 0, 0); this.legR.rotation.set(-sw, 0, 0);
    this.legL.position.y = this.legR.position.y = 12 * PX + bob + (p.hipsDy ?? 0);
    if (p.sit) { this.legL.rotation.x = this.legR.rotation.x = -Math.PI / 2 + (p.legSwing ? Math.sin(t * 1.5) * 0.15 : 0); this.legR.rotation.x += p.legSwing ? Math.sin(t * 1.5 + 1.3) * 0.15 : 0; }
    if (p.legs) { this.legL.rotation.x = p.legs[0]; this.legR.rotation.x = p.legs[1]; }
    const aL = p.armL ?? [-sw * 0.9 + breathe, 0.04], aR = p.armR ?? [sw * 0.9 - breathe, -0.04];
    this.armL.rotation.set(aL[0], aL[2] ?? 0, aL[1]);
    this.armR.rotation.set(aR[0], aR[2] ?? 0, aR[1]);
    const talk = p.talk ? Math.sin(t * 9) * 0.035 + Math.sin(t * 5.3) * 0.02 : 0;
    this.neck.rotation.set((p.headPitch ?? 0) + talk + breathe * 0.5, p.headYaw ?? 0, p.headRoll ?? 0, 'YXZ');
    // blink every few seconds, deterministic
    const bt = (t + (this.kind === 'juno' ? 0 : 1.7)) % 3.7;
    const blink = p.blink ?? (bt < 0.12);
    this.faceMat.map = blink ? this.faceBlink : this.faceOpen;
  }
}

export { PX, pix, tex, paintedBox, shadeHex };
