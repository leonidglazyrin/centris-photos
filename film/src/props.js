import * as THREE from 'three';
import { PX, pix, tex, paintedBox } from './characters.js';
import { Voxels, meshVoxels, B } from './world.js';
import { U } from './materials.js';
import { hash2, mulberry32, clamp, noise1 } from './util.js';

// ---------------- lantern ----------------
export class Lantern {
  constructor() {
    this.group = new THREE.Group();
    const metal = new THREE.MeshLambertMaterial({ color: '#3a3330' });
    this.coreMat = new THREE.MeshLambertMaterial({ color: '#ffe0a0', emissive: new THREE.Color('#ffb04a'), emissiveIntensity: 0 });
    const add = (w, h, d, x, y, z, m) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w * PX, h * PX, d * PX), m); b.position.set(x * PX, y * PX, z * PX); b.castShadow = true; this.group.add(b); return b; };
    add(6, 1, 6, 0, 0.5, 0, metal);
    this.core = add(4, 5, 4, 0, 3.5, 0, this.coreMat); this.core.castShadow = false;
    for (const [x, z] of [[-2.5, -2.5], [2.5, -2.5], [-2.5, 2.5], [2.5, 2.5]]) add(1, 5, 1, x, 3.5, z, metal);
    add(6, 1, 6, 0, 6.5, 0, metal);
    add(4, 1, 4, 0, 7.5, 0, metal);
    add(2, 1, 1, 0, 8.5, 0, metal);
    this.on = 0;
    this.worldPos = new THREE.Vector3();
  }
  set(on, t, seed = 0) {
    this.on = on;
    const fl = 1 + noise1(t * 6, seed) * 0.08 + noise1(t * 17, seed + 3) * 0.04;
    this.flicker = fl;
    this.coreMat.emissiveIntensity = on * 4.5 * fl;
    this.coreMat.color.set(on > 0.05 ? '#ffe7b0' : '#8a7a60');
  }
}

// Pool of real point lights assigned to the lanterns nearest the action.
export class LightPool {
  constructor(scene, n = 4) {
    this.lights = [];
    for (let i = 0; i < n; i++) {
      const l = new THREE.PointLight('#ffae55', 0, 14, 1.6);
      scene.add(l); this.lights.push(l);
    }
  }
  assign(lanterns, focus, strength = 1) {
    const lit = lanterns.filter((l) => l.on > 0.02 && l.group.visible && l.group.parent);
    lit.forEach((l) => { l.core.getWorldPosition(l.worldPos); l._d = l.worldPos.distanceTo(focus); });
    lit.sort((a, b) => a._d - b._d);
    this.lights.forEach((pl, i) => {
      const l = lit[i];
      if (!l) { pl.intensity = 0; return; }
      pl.position.copy(l.worldPos);
      pl.intensity = 4.5 * l.on * (l.flicker ?? 1) * strength;
    });
  }
}

// ---------------- boat ----------------
export function buildBoat(materials) {
  const V = new Voxels(5, 3, 9);
  for (let z = 0; z < 9; z++) {
    const half = z === 0 || z === 8 ? 0 : z === 1 || z === 7 ? 1 : 2;
    for (let x = 2 - half; x <= 2 + half; x++) {
      V.set(x, 0, z, B.dark_planks);
      if (x === 2 - half || x === 2 + half || z === 0 || z === 8) V.set(x, 1, z, B.planks);
    }
  }
  V.set(1, 1, 4, B.planks); V.set(2, 1, 4, B.planks); V.set(3, 1, 4, B.planks); // seat
  const { opaque } = meshVoxels(V, 0, 0, 5, 9, 0, 3);
  const mesh = new THREE.Mesh(opaque, materials.opaque);
  mesh.castShadow = true; mesh.receiveShadow = true;
  const s = 0.62;
  mesh.position.set(-2.5 * s, -0.45, -4.5 * s);
  mesh.scale.set(s, s, s);
  const g = new THREE.Group();
  const inner = new THREE.Group(); inner.add(mesh); g.add(inner);
  const oarMat = new THREE.MeshLambertMaterial({ color: '#9b7048' });
  const oars = [];
  for (const side of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(side * 1.5, 0.78, 0.1);
    const shaft = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.07, 1.9), oarMat); shaft.position.set(0, 0, 0);
    const blade = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.36, 0.2), oarMat); blade.position.set(0, -0.05, 0.95);
    const oar = new THREE.Group(); oar.add(shaft, blade); oar.rotation.y = side * 1.2; oar.rotation.x = 0.35;
    oar.traverse((o) => { if (o.isMesh) o.castShadow = true; });
    pivot.add(oar); inner.add(pivot); oars.push({ pivot, oar, side });
  }
  const lantern = new Lantern();
  lantern.group.position.set(0, 0.17, 2.2);
  inner.add(lantern.group);
  return { group: g, inner, oars, lantern };
}

// ---------------- the map ----------------
export function mapTexture(finished) {
  const W = 512, H = 360;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const c = cv.getContext('2d');
  const r = mulberry32(finished ? 7 : 3);
  // parchment
  const g = c.createRadialGradient(W / 2, H / 2, 40, W / 2, H / 2, W * 0.7);
  g.addColorStop(0, '#f6e7c4'); g.addColorStop(1, '#d9bb87');
  c.fillStyle = g; c.fillRect(0, 0, W, H);
  for (let i = 0; i < 3000; i++) { c.fillStyle = `rgba(120,80,40,${r() * 0.06})`; c.fillRect(r() * W, r() * H, 2, 2); }
  c.strokeStyle = '#7a5230'; c.lineWidth = 4; c.strokeRect(10, 10, W - 20, H - 20);
  c.lineWidth = 1.5; c.strokeRect(18, 18, W - 36, H - 36);
  const ink = '#5a3a22';
  const reveal = finished ? 1 : 0.45; // unfinished map only shows the western half
  c.save();
  if (!finished) { c.beginPath(); c.rect(0, 0, W * reveal, H); c.clip(); }
  // mountains
  c.strokeStyle = ink; c.lineWidth = 2;
  for (let i = 0; i < 16; i++) {
    const a = i / 16 * Math.PI * 2, x = W / 2 + Math.cos(a) * 205, y = H / 2 + 30 + Math.sin(a) * 135;
    c.beginPath(); c.moveTo(x - 14, y + 8); c.lineTo(x, y - 12); c.lineTo(x + 14, y + 8); c.stroke();
  }
  // lake
  c.fillStyle = 'rgba(90,150,190,0.55)'; c.beginPath(); c.ellipse(W / 2, H / 2 + 60, 120, 70, 0, 0, Math.PI * 2); c.fill();
  c.strokeStyle = '#3f6f8f'; c.lineWidth = 2; c.stroke();
  for (let i = 0; i < 8; i++) { c.beginPath(); const x = W / 2 - 80 + i * 22, y = H / 2 + 50 + (i % 3) * 16; c.moveTo(x, y); c.quadraticCurveTo(x + 5, y - 4, x + 10, y); c.stroke(); }
  // grove
  c.fillStyle = '#e59ab4';
  for (let i = 0; i < 9; i++) { c.beginPath(); c.arc(95 + (i % 3) * 20 + r() * 6, 130 + Math.floor(i / 3) * 18, 8, 0, 7); c.fill(); }
  c.fillStyle = ink; c.font = 'italic 15px Georgia'; c.fillText('Cherry Grove', 70, 205);
  // village + pier
  c.fillStyle = '#b8583f';
  for (const [x, y] of [[236, 100], [262, 92], [284, 104], [250, 118]]) { c.fillRect(x, y, 14, 10); c.beginPath(); c.moveTo(x - 2, y); c.lineTo(x + 7, y - 7); c.lineTo(x + 16, y); c.fill(); }
  c.fillStyle = '#7a5230'; c.fillRect(W / 2 - 3, 128, 6, 72);
  c.fillStyle = '#ffb04a'; c.beginPath(); c.arc(W / 2, 204, 5, 0, 7); c.fill();
  // path
  c.setLineDash([6, 6]); c.strokeStyle = ink; c.lineWidth = 2;
  c.beginPath(); c.moveTo(130, 160); c.quadraticCurveTo(190, 110, 250, 118); c.stroke();
  c.beginPath(); c.moveTo(290, 110); c.quadraticCurveTo(360, 90, 410, 110); c.stroke();
  c.setLineDash([]);
  // hill + tree
  c.beginPath(); c.moveTo(380, 130); c.quadraticCurveTo(412, 88, 444, 130); c.stroke();
  c.fillStyle = '#e59ab4'; c.beginPath(); c.arc(412, 94, 9, 0, 7); c.fill();
  c.fillStyle = ink; c.font = 'italic 15px Georgia'; c.fillText('Our tree', 386, 150);
  c.restore();
  // title + compass
  c.fillStyle = ink; c.font = 'bold 26px Georgia'; c.textAlign = 'center';
  c.fillText('Willow Lake', W / 2, 52);
  c.save(); c.translate(W - 64, H - 70); c.strokeStyle = ink; c.lineWidth = 2;
  c.beginPath(); c.moveTo(0, -26); c.lineTo(7, 0); c.lineTo(0, 26); c.lineTo(-7, 0); c.closePath(); c.stroke();
  c.font = 'bold 13px Georgia'; c.fillText('N', 0, -30); c.restore();
  if (finished) {
    c.fillStyle = '#b8323a'; c.font = 'bold 30px Georgia'; c.textAlign = 'center';
    c.fillText('HOME', W / 2, 250);
    c.beginPath(); const hx = W / 2 + 56, hy = 238;
    c.moveTo(hx, hy + 8); c.bezierCurveTo(hx - 14, hy - 2, hx - 6, hy - 12, hx, hy - 4); c.bezierCurveTo(hx + 6, hy - 12, hx + 14, hy - 2, hx, hy + 8); c.fill();
  } else {
    c.fillStyle = 'rgba(90,58,34,0.6)'; c.font = 'italic 16px Georgia'; c.textAlign = 'center';
    c.fillText('unexplored', W * 0.72, H / 2 + 10);
  }
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  return t;
}
export function buildMap(finished) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.63), new THREE.MeshLambertMaterial({ map: mapTexture(finished), side: THREE.DoubleSide }));
  m.castShadow = true; m.receiveShadow = true;
  return m;
}

// ---------------- particles ----------------
const pointsVS = `
  attribute float aSize; attribute vec3 aCol; attribute float aAlpha;
  varying vec3 vCol; varying float vAlpha;
  uniform float uScale;
  #include <fog_pars_vertex>
  void main(){
    vCol = aCol; vAlpha = aAlpha;
    vec4 mvPosition = modelViewMatrix * vec4(position,1.0);
    gl_PointSize = aSize * uScale / -mvPosition.z;
    gl_Position = projectionMatrix * mvPosition;
    #include <fog_vertex>
  }`;
function pointsFS(kind) {
  return `
  varying vec3 vCol; varying float vAlpha;
  #include <fog_pars_fragment>
  void main(){
    vec2 q = gl_PointCoord - 0.5;
    ${kind === 'square' ? 'if (max(abs(q.x),abs(q.y)) > 0.5) discard; float a = vAlpha;' : ''}
    ${kind === 'glow' ? 'float d = length(q); float a = smoothstep(0.5, 0.0, d); a = a*a*vAlpha;' : ''}
    ${kind === 'soft' ? 'float d = length(q); float a = smoothstep(0.5, 0.1, d) * vAlpha;' : ''}
    ${kind === 'heart' ? `vec2 p = floor((gl_PointCoord) * 7.0);
      int x = int(p.x); int y = int(p.y);
      bool on = (y==1 && (x==1||x==2||x==4||x==5)) || (y==2 && x>=0 && x<=6) || (y==3 && x>=0 && x<=6) || (y==4 && x>=1 && x<=5) || (y==5 && x>=2 && x<=4) || (y==6 && x==3);
      if (!on) discard; float a = vAlpha;` : ''}
    gl_FragColor = vec4(vCol, a);
    #include <fog_fragment>
  }`;
}
export class Particles {
  constructor(scene, n, kind, { additive = false } = {}) {
    this.n = n;
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(n * 3); this.size = new Float32Array(n); this.col = new Float32Array(n * 3); this.alpha = new Float32Array(n);
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3));
    g.setAttribute('aSize', new THREE.BufferAttribute(this.size, 1));
    g.setAttribute('aCol', new THREE.BufferAttribute(this.col, 3));
    g.setAttribute('aAlpha', new THREE.BufferAttribute(this.alpha, 1));
    this.geo = g;
    this.uniforms = THREE.UniformsUtils.merge([THREE.UniformsLib.fog, { uScale: { value: 800 } }]);
    this.mat = new THREE.ShaderMaterial({
      uniforms: this.uniforms, vertexShader: pointsVS, fragmentShader: pointsFS(kind), transparent: true, depthWrite: false, fog: true,
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
    this.points = new THREE.Points(g, this.mat);
    this.points.frustumCulled = false;
    this.points.visible = false;
    scene.add(this.points);
  }
  update(fn) {
    for (let i = 0; i < this.n; i++) fn(i, this);
    this.geo.attributes.position.needsUpdate = true; this.geo.attributes.aSize.needsUpdate = true;
    this.geo.attributes.aCol.needsUpdate = true; this.geo.attributes.aAlpha.needsUpdate = true;
  }
  hide() { this.points.visible = false; }
}

const PINKS = [[1.0, 0.72, 0.8], [1.0, 0.8, 0.86], [0.95, 0.62, 0.74], [1, 0.9, 0.93]];
export function petalsField(p, t, center, radius, height, strength = 1) {
  p.points.visible = strength > 0;
  if (!p.points.visible) return;
  p.update((i, P) => {
    const h1 = hash2(i, 1, 9), h2 = hash2(i, 2, 9), h3 = hash2(i, 3, 9);
    const fall = 0.55 + h3 * 0.5;
    const cyc = height / fall;
    const life = ((t + h1 * cyc) % cyc) / cyc;
    const x = center.x + (h1 - 0.5) * radius * 2 + Math.sin(t * 0.9 + i) * 0.6 + life * 3;
    const z = center.z + (h2 - 0.5) * radius * 2 + Math.cos(t * 0.7 + i * 1.3) * 0.6;
    const y = center.y + height * (1 - life);
    P.pos.set([x, y, z], i * 3);
    P.size[i] = 0.09 * (0.7 + h2 * 0.6);
    P.col.set(PINKS[i % 4], i * 3);
    P.alpha[i] = strength * clamp(life * 8, 0, 1) * clamp((1 - life) * 8, 0, 1);
  });
}
export function snowField(p, t, center, radius, height, strength = 1) {
  p.points.visible = strength > 0;
  if (!p.points.visible) return;
  p.update((i, P) => {
    const h1 = hash2(i, 4, 3), h2 = hash2(i, 5, 3), h3 = hash2(i, 6, 3);
    const fall = 1.1 + h3 * 0.6;
    const cyc = height / fall;
    const life = ((t + h1 * cyc) % cyc) / cyc;
    const x = center.x + (h1 - 0.5) * radius * 2 + Math.sin(t * 0.8 + i * 0.7) * 0.5 + life * 2.5;
    const z = center.z + (h2 - 0.5) * radius * 2 + Math.cos(t * 0.6 + i) * 0.5;
    P.pos.set([x, center.y + height * (1 - life), z], i * 3);
    P.size[i] = 0.055 * (0.6 + h2 * 0.8);
    P.col.set([1, 1, 1], i * 3);
    P.alpha[i] = strength * 0.95;
  });
}
export function fireflyField(p, t, center, radius, strength = 1) {
  p.points.visible = strength > 0;
  if (!p.points.visible) return;
  p.update((i, P) => {
    const h1 = hash2(i, 7, 1), h2 = hash2(i, 8, 1), h3 = hash2(i, 9, 1);
    const x = center.x + (h1 - 0.5) * radius * 2 + noise1(t * 0.25, i * 3) * 2;
    const z = center.z + (h2 - 0.5) * radius * 2 + noise1(t * 0.25, i * 3 + 1) * 2;
    const y = center.y + h3 * 3.5 + noise1(t * 0.3, i * 3 + 2) * 0.8;
    P.pos.set([x, y, z], i * 3);
    P.size[i] = 0.35;
    P.col.set([2.4, 2.6, 0.9], i * 3);
    const blink = clamp(Math.sin(t * (0.8 + h1) + i * 2.1) * 1.4 + 0.2, 0, 1);
    P.alpha[i] = strength * blink;
  });
}
export function heartField(p, t, origin, strength = 1) {
  p.points.visible = strength > 0;
  if (!p.points.visible) return;
  p.update((i, P) => {
    const h1 = hash2(i, 12, 2), h2 = hash2(i, 13, 2);
    const cyc = 3.2;
    const life = ((t + h1 * cyc) % cyc) / cyc;
    P.pos.set([origin.x + (h1 - 0.5) * 1.4 + Math.sin(t * 2 + i) * 0.15, origin.y + life * 1.8, origin.z + (h2 - 0.5) * 1.0], i * 3);
    P.size[i] = 0.22;
    P.col.set([1.6, 0.35, 0.45], i * 3);
    P.alpha[i] = strength * clamp(life * 6, 0, 1) * clamp((1 - life) * 3, 0, 1);
  });
}
export function smokeField(p, t, chimneys, strength = 1) {
  p.points.visible = strength > 0;
  if (!p.points.visible) return;
  const per = Math.floor(p.n / chimneys.length);
  p.update((i, P) => {
    const c = chimneys[Math.min(chimneys.length - 1, Math.floor(i / per))];
    const k = i % per, h1 = hash2(i, 14, 2);
    const cyc = 6;
    const life = ((t + k / per * cyc) % cyc) / cyc;
    P.pos.set([c[0] + life * 2.2 + noise1(t * 0.5, i) * 0.3, c[1] + life * 5, c[2] + (h1 - 0.5) * 0.5 + life * 0.6], i * 3);
    P.size[i] = 0.35 + life * 1.3;
    P.col.set([0.85, 0.85, 0.88], i * 3);
    P.alpha[i] = strength * 0.35 * clamp(life * 5, 0, 1) * (1 - life);
  });
}

// Sky lanterns: instanced glowing paper cubes that drift up into the night.
export class SkyLanterns {
  constructor(scene, n = 70) {
    this.n = n;
    const geo = new THREE.BoxGeometry(0.42, 0.55, 0.42);
    this.mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(3.2, 1.7, 0.7), fog: true, toneMapped: true });
    this.mesh = new THREE.InstancedMesh(geo, this.mat, n);
    this.mesh.frustumCulled = false; this.mesh.visible = false;
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3);
    scene.add(this.mesh);
    const r = mulberry32(55);
    this.seeds = Array.from({ length: n }, () => ({ x: 70 + r() * 40, z: 44 + r() * 30, start: r() * 14, speed: 0.55 + r() * 0.35, ph: r() * 6 }));
    this.m4 = new THREE.Matrix4(); this.q = new THREE.Quaternion(); this.v = new THREE.Vector3(); this.s = new THREE.Vector3(1, 1, 1);
  }
  update(t, strength = 1) {
    this.mesh.visible = strength > 0;
    if (!this.mesh.visible) return;
    const c = new THREE.Color();
    this.seeds.forEach((s, i) => {
      const lt = t - s.start;
      const up = lt > 0 ? lt * s.speed + 0.03 * lt * lt : -100;
      this.v.set(s.x + Math.sin(lt * 0.4 + s.ph) * 1.2 + lt * 0.35, 23 + up, s.z + Math.cos(lt * 0.3 + s.ph) * 1.2 + lt * 0.5);
      this.q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), s.ph + lt * 0.2);
      const sc = lt > 0 ? 1 : 0.0001;
      this.s.set(sc, sc, sc);
      this.m4.compose(this.v, this.q, this.s);
      this.mesh.setMatrixAt(i, this.m4);
      const fl = 0.85 + 0.15 * Math.sin(t * 8 + s.ph * 5);
      c.setRGB(fl * strength, fl * strength, fl * strength);
      this.mesh.setColorAt(i, c);
    });
    this.mesh.instanceMatrix.needsUpdate = true;
    this.mesh.instanceColor.needsUpdate = true;
  }
}

// Low mist layers that hug the lake surface.
export function createMist(scene) {
  const uniforms = { uTime: U.uTime, uColor: { value: new THREE.Color('#ffffff') }, uDensity: { value: 0 }, uLayer: { value: 0 } };
  const layers = [];
  for (let i = 0; i < 4; i++) {
    const m = new THREE.ShaderMaterial({
      uniforms: { ...uniforms, uLayer: { value: i } }, transparent: true, depthWrite: false, side: THREE.DoubleSide,
      vertexShader: `varying vec2 vP; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vP = w.xz; gl_Position = projectionMatrix*viewMatrix*w; }`,
      fragmentShader: `uniform float uTime, uDensity, uLayer; uniform vec3 uColor; varying vec2 vP;
        float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
        float n(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.0-2.0*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y); }
        void main(){ vec2 p = vP*0.06 + vec2(uTime*0.02 + uLayer*3.1, uTime*0.013);
          float v = n(p)*0.5 + n(p*2.1)*0.3 + n(p*4.3)*0.2;
          float a = smoothstep(0.35, 0.8, v) * uDensity * (0.55 - uLayer*0.08);
          float edge = smoothstep(95.0, 55.0, length(vP - vec2(88.0,112.0)));
          gl_FragColor = vec4(uColor, a*edge); }`,
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(260, 260), m);
    mesh.rotation.x = -Math.PI / 2; mesh.position.set(88, 20.25 + i * 0.55, 112);
    mesh.renderOrder = 5;
    scene.add(mesh); layers.push(mesh);
  }
  return {
    set(density, color) { layers.forEach((l) => { l.visible = density > 0; l.material.uniforms.uDensity.value = density; l.material.uniforms.uColor.value.copy(color); }); },
  };
}
