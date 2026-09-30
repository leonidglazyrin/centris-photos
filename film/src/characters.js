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
    const [fw, fh] = dims[k].map((v) => Math.max(1, Math.ceil(v)));
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

// ---------------- skins (styled after the couple in the reference photo) ----------------
const JUNO = {
  skin: '#f2ccb3', blush: '#e9a693', hair: '#3a2319', hairD: '#26150e', hairL: '#5c3a27', eye: '#6d8a58', lash: '#2a1a14', mouth: '#bf7068',
  frame: '#2a3a48', frameL: '#56707f', hood: '#dcdad6', hoodD: '#c2bfba', tee: '#a6e3da', zip: '#7a7874', chain: '#dcbb6c',
  leg: '#3b4660', legD: '#2f3950', shoe: '#ecebe6',
};
const ROWAN = {
  skin: '#f0c5a8', blush: '#e39e8a', hair: '#8c6641', hairD: '#6b4b2d', hairL: '#b08a5c', eye: '#5a3c28', lash: '#2a1c14', mouth: '#b56e62',
  frame: '#232b25', frameL: '#4a574f', cap: '#27324f', capD: '#1d2640', capL: '#3d4c70',
  top: '#2f6b3d', topD: '#265a33', script: '#efe6c8', badge: '#e8c440', leg: '#4a5670', legD: '#3d485f', shoe: '#3b2e26',
};

function headPainter(S, kind, blink) {
  const juno = kind === 'juno';
  return (face, { put, rect, w, h }) => {
    rect(0, 0, w, h, S.skin);
    if (face === 'top') {
      rect(0, 0, w, h, juno ? S.hair : S.cap);
      for (let i = 0; i < 8; i++) put((i * 3) % 8, i, juno ? S.hairL : S.capL);
      return;
    }
    if (face === 'bottom') return;
    if (face === 'back') {
      rect(0, 0, w, h, S.hair);
      for (let x = 0; x < 8; x++) put(x, (x * 5) % 8, S.hairD);
      if (!juno) { rect(0, 0, 8, 3, S.cap); rect(3, 2, 2, 1, S.capD); }  // cap back strap
      return;
    }
    if (face === 'left' || face === 'right') {
      const back = face === 'left' ? [0, 1, 2, 3, 4] : [3, 4, 5, 6, 7];
      if (juno) {
        rect(0, 0, 8, 2, S.hair);
        for (const x of back) rect(x, 0, 1, 8, S.hair);
        for (let y = 0; y < 8; y++) put(back[(y * 2) % 5], y, y % 2 ? S.hairD : S.hairL);
        // glasses arm
        rect(face === 'left' ? 5 : 0, 3, 3, 1, S.frame);
      } else {
        rect(0, 0, 8, 3, S.cap); rect(0, 2, 8, 1, S.capD);
        for (const x of back) rect(x, 3, 1, 5, S.hair);
        put(back[2], 5, S.hairL); put(back[4], 6, S.hairD);
        rect(face === 'left' ? 5 : 0, 3, 3, 1, S.frame);
      }
      put(face === 'left' ? 4 : 3, 4, juno ? S.hair : '#e5b598');
      return;
    }
    // front
    if (juno) {
      // curtain bangs parted in the middle, curls framing the face
      rect(0, 0, 8, 2, S.hair);
      rect(0, 2, 1, 6, S.hair); rect(7, 2, 1, 6, S.hair);
      put(1, 2, S.hair); put(2, 2, S.hairD); put(5, 2, S.hairD); put(6, 2, S.hair); put(1, 1, S.hairL); put(6, 1, S.hairL);
      put(0, 4, S.hairL); put(7, 5, S.hairL); put(0, 7, S.hairD); put(7, 7, S.hairD);
    } else {
      rect(0, 0, 8, 2, S.cap); put(3, 0, S.capL); put(4, 0, S.capL);
      put(0, 2, S.hair); put(7, 2, S.hair); put(0, 3, S.hair); put(7, 3, S.hair); put(1, 2, S.hairL);
    }
    // glasses: dark frames around the eyes (Juno's are big and square, Rowan's rectangular)
    rect(1, 3, 2, 1, S.frame); rect(5, 3, 2, 1, S.frame); put(3, 3, S.frameL); put(4, 3, S.frameL);
    put(1, 5, S.frameL); put(6, 5, S.frameL);
    if (juno) { put(1, 2, S.frame); put(6, 2, S.frame); }
    if (blink) { rect(1, 4, 2, 1, S.lash); rect(5, 4, 2, 1, S.lash); }
    else { put(1, 4, '#ffffff'); put(2, 4, S.eye); put(5, 4, S.eye); put(6, 4, '#ffffff'); }
    put(1, 6, S.blush); put(6, 6, S.blush);
    put(3, 6, S.mouth); put(4, 6, S.mouth);
  };
}

function bodyPainter(S, kind) {
  return (face, { put, rect, w, h }) => {
    if (kind === 'juno') {
      rect(0, 0, w, h, S.hood);
      if (face === 'front') {
        rect(3, 0, 2, 9, S.tee);                 // open zip hoodie over a mint tee
        put(3, 0, S.skin); put(4, 0, S.skin); put(3, 1, S.chain); put(4, 2, S.chain);
        rect(2, 0, 1, 12, S.hoodD); rect(5, 0, 1, 12, S.hoodD);
        rect(3, 9, 2, 3, S.zip); put(3, 10, S.hoodD);
        put(1, 8, S.hoodD); put(6, 8, S.hoodD); rect(0, 11, 8, 1, S.hoodD);
      }
      if (face === 'back') { rect(1, 0, 6, 5, S.hair); rect(2, 5, 4, 1, S.hairD); rect(0, 11, 8, 1, S.hoodD); }
      if (face === 'top') { rect(0, 0, w, h, S.hood); rect(3, 0, 2, h, S.tee); }
      if (face === 'left' || face === 'right') rect(0, 11, w, 1, S.hoodD);
    } else {
      rect(0, 0, w, h, S.top);
      if (face === 'front') {
        rect(3, 0, 2, 1, S.skin); put(2, 0, S.topD); put(5, 0, S.topD);
        // small badge + a cream script wordmark across the chest (generic)
        put(5, 3, S.badge); put(6, 3, '#f4f1e6'); put(5, 4, '#f4f1e6'); put(6, 4, S.badge);
        for (const [x, y] of [[0, 7], [1, 6], [1, 7], [2, 7], [3, 6], [3, 7], [4, 7], [5, 6], [5, 7], [6, 7], [7, 6], [2, 8], [6, 8]]) put(x, y, S.script);
      }
      rect(0, 11, w, 1, S.topD);
      if (face === 'top') rect(0, 0, w, h, S.top);
    }
  };
}
function armPainter(S, kind) {
  return (face, { rect, w, h }) => {
    if (kind === 'juno') {
      rect(0, 0, w, h, S.hood); rect(0, 9, w, 1, S.hoodD); rect(0, 10, w, 2, S.skin);  // long hoodie sleeves
      if (face === 'bottom') rect(0, 0, w, h, S.skin);
    } else {
      rect(0, 0, w, h, S.skin); rect(0, 0, w, 4, S.top); rect(0, 3, w, 1, S.topD);   // t-shirt sleeves
      if (face === 'top') rect(0, 0, w, h, S.top);
    }
  };
}
function legPainter(S) {
  return (face, { rect, put, w, h }) => {
    rect(0, 0, w, h, S.leg);
    put(1, 4, S.legD); put(2, 8, S.legD);
    rect(0, 10, w, 2, S.shoe);
    if (face === 'bottom') rect(0, 0, w, h, S.shoe);
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
      // big curly hair: volume on top, curls at the sides, falling past the shoulders at the back
      const curl = (f, c) => { c.rect(0, 0, c.w, c.h, S.hair); for (let i = 0; i < c.w * c.h; i += 3) c.put(i % c.w, Math.floor(i / c.w), (i * 7) % 5 < 2 ? S.hairD : (i % 4 === 0 ? S.hairL : S.hair)); };
      const back = paintedBox(9, 9, 2, curl); back.position.set(0, -1.5 * PX, -4.6 * PX); this.neck.add(back);
      for (const side of [-1, 1]) {
        const sideCurl = paintedBox(1, 7, 3.5, curl); sideCurl.position.set(side * 4.45 * PX, 1.2 * PX, -2.4 * PX); this.neck.add(sideCurl);
      }
      const top = paintedBox(8.6, 1, 8.2, curl); top.position.set(0, 8.4 * PX, -0.5 * PX); this.neck.add(top);
    } else {
      // navy ball cap with a curved brim, hair poking out at the back
      const cap = paintedBox(8.6, 2.2, 8.6, (f, c) => { c.rect(0, 0, c.w, c.h, S.cap); if (f === 'top') { c.put(4, 4, S.capD); } else c.rect(0, c.h - 1, c.w, 1, S.capD); });
      cap.position.set(0, 7.3 * PX, 0); this.neck.add(cap);
      const brim = paintedBox(8, 0.7, 4, (f, c) => { c.rect(0, 0, c.w, c.h, S.capD); if (f === 'top') c.rect(1, 0, c.w - 2, c.h - 1, S.cap); });
      brim.position.set(0, 6.4 * PX, 5.6 * PX); brim.rotation.x = 0.12; this.neck.add(brim);
      const hairBack = paintedBox(8, 3, 1, (f, c) => { c.rect(0, 0, c.w, c.h, S.hair); c.put(2, 1, S.hairL); c.put(5, 2, S.hairD); });
      hairBack.position.set(0, 0.2 * PX, -4.4 * PX); this.neck.add(hairBack);
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
