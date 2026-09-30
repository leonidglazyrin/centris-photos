// Voxel world: storage, the Willow Lake valley generator and an AO mesher.
import * as THREE from 'three';
import { T } from './textures.js';
import { mulberry32, fbm, valueNoise, hash2, smooth, range, lerp } from './util.js';

export const W = 176, D = 176, H = 72;
export const WATER_Y = 20; // water surface height (top of layer 19)

// ---------------- block registry ----------------
export const B = {};
const REG = [null];
function def(name, o) {
  const b = { id: REG.length, name, shape: 'cube', cutout: false, wave: 0, ...o };
  const t = o.tex;
  if (typeof t === 'string') b.faces = { top: T[t], bottom: T[t], side: T[t] };
  else b.faces = { top: T[t.top], bottom: T[t.bottom ?? t.top], side: T[t.side] };
  B[name] = b.id; REG.push(b);
}
def('grass', { tex: { top: 'grass_top', bottom: 'dirt', side: 'grass_side' } });
def('dirt', { tex: 'dirt' });
def('stone', { tex: 'stone' });
def('cobble', { tex: 'cobble' });
def('mossy', { tex: 'mossy' });
def('gravel', { tex: 'gravel' });
def('sand', { tex: 'sand' });
def('path', { tex: { top: 'path', bottom: 'dirt', side: 'dirt' }, shape: 'path' });
def('planks', { tex: 'planks' });
def('dark_planks', { tex: 'dark_planks' });
def('pier', { tex: 'pier' });
def('oak_log', { tex: { top: 'log_top', side: 'oak_log' } });
def('cherry_log', { tex: { top: 'log_top', side: 'cherry_log' } });
def('birch_log', { tex: { top: 'log_top', side: 'birch_log' } });
def('oak_leaves', { tex: 'oak_leaves', cutout: true, wave: 0.6 });
def('cherry_leaves', { tex: 'cherry_leaves', cutout: true, wave: 0.6 });
def('plaster', { tex: 'plaster' });
def('timber', { tex: 'timber' });
def('roof_red', { tex: 'roof_red' });
def('roof_teal', { tex: 'roof_teal' });
def('roof_red_slab', { tex: 'roof_red', shape: 'slab' });
def('roof_teal_slab', { tex: 'roof_teal', shape: 'slab' });
def('window', { tex: { top: 'dark_planks', side: 'window' } });
def('door', { tex: { top: 'dark_planks', side: 'door' } });
def('bench', { tex: { top: 'bench_top', bottom: 'planks', side: 'bench_side' } });
def('hay', { tex: { top: 'hay', side: 'hay' } });
def('bookshelf', { tex: { top: 'planks', side: 'bookshelf' } });
def('wool_cream', { tex: 'wool_cream' });
def('wool_rose', { tex: 'wool_rose' });
def('post', { tex: 'dark_planks', shape: 'post' });
def('pier_post', { tex: { top: 'log_top', side: 'oak_log' }, shape: 'post' });
def('tall_grass', { tex: 'tall_grass', shape: 'cross', cutout: true, wave: 1 });
def('flower_red', { tex: 'flower_red', shape: 'cross', cutout: true, wave: 0.7 });
def('flower_yellow', { tex: 'flower_yellow', shape: 'cross', cutout: true, wave: 0.7 });
def('flower_blue', { tex: 'flower_blue', shape: 'cross', cutout: true, wave: 0.7 });
def('flower_pink', { tex: 'flower_pink', shape: 'cross', cutout: true, wave: 0.7 });
def('flower_white', { tex: 'flower_white', shape: 'cross', cutout: true, wave: 0.7 });
def('sapling', { tex: 'sapling', shape: 'cross', cutout: true, wave: 0.5 });
def('reeds', { tex: 'reeds', shape: 'cross', cutout: true, wave: 0.8 });
def('lily', { tex: 'lily', shape: 'flat', cutout: true });
export const REGISTRY = REG;

const isFullOpaque = (id) => id > 0 && REG[id].shape === 'cube' && !REG[id].cutout;
const isAOSolid = (id) => id > 0 && REG[id].shape === 'cube';

// ---------------- voxel container ----------------
export class Voxels {
  constructor(w, h, d) { this.w = w; this.h = h; this.d = d; this.data = new Uint8Array(w * h * d); }
  idx(x, y, z) { return (y * this.d + z) * this.w + x; }
  get(x, y, z) {
    if (x < 0 || y < 0 || z < 0 || x >= this.w || y >= this.h || z >= this.d) return 0;
    return this.data[this.idx(x, y, z)];
  }
  set(x, y, z, id) {
    if (x < 0 || y < 0 || z < 0 || x >= this.w || y >= this.h || z >= this.d) return;
    this.data[this.idx(x, y, z)] = typeof id === 'string' ? B[id] : id;
  }
}

// ---------------- world generation ----------------
export const LAKE = { x: 88, z: 112, rx: 46, rz: 34 };
export const VILLAGE = { x: 88, z: 58 };
export const HILL = { x: 142, z: 66 };
export const GROVE = { x: 36, z: 70 };
export const PIER = { x: 88, z0: 70, z1: 99 };

function terrainHeight(x, z) {
  let h = 21.5 + (fbm(x * 0.035, z * 0.035, 4, 1) - 0.5) * 6;
  // lake basin
  const dx = (x - LAKE.x) / LAKE.rx, dz = (z - LAKE.z) / LAKE.rz;
  const wob = (valueNoise(x * 0.08, z * 0.08, 5) - 0.5) * 0.18;
  const d = Math.sqrt(dx * dx + dz * dz) + wob;
  const lakeK = smooth(range(d, 0.82, 1.12));
  h = lerp(13 + d * 6, h, lakeK);
  // the hill: a smooth dome with a flat plateau on top
  const hd2 = (x - HILL.x) ** 2 + (z - HILL.z) ** 2;
  const hillK = Math.exp(-hd2 / (2 * 19 * 19));
  h = lerp(h, 21.5, hillK * 0.85);
  h += 14 * hillK;
  // mountain ring enclosing the valley
  const r = Math.hypot(x - 88, z - 98);
  h += smooth(range(r, 66, 90)) * (18 + fbm(x * 0.05, z * 0.05, 4, 9) * 22);
  // flatten village + grove
  const vdz = z - VILLAGE.z;
  const vk = 1 - smooth(range(Math.hypot(x - VILLAGE.x, vdz * (vdz > 0 ? 1.6 : 1.0)), 24, 34));
  h = lerp(h, 21.5, vk);
  const gk = 1 - smooth(range(Math.hypot(x - GROVE.x, z - GROVE.z), 14, 24));
  h = lerp(h, 22.2, gk * 0.7);
  // flat top for the hill so the sapling has a home
  const hk = 1 - smooth(range(Math.sqrt(hd2), 6, 11));
  h = lerp(h, 35.3, hk);
  return { h, lakeK, r };
}

export function generateWorld() {
  const V = new Voxels(W, H, D);
  const rng = mulberry32(2024);
  const heights = new Int16Array(W * D);
  for (let z = 0; z < D; z++) for (let x = 0; x < W; x++) {
    const { h, lakeK, r } = terrainHeight(x, z);
    const top = Math.floor(h);
    heights[z * W + x] = top;
    const beach = top <= WATER_Y + 0 && lakeK < 1;
    const rocky = top > 40 || (r > 74 && fbm(x * 0.1, z * 0.1, 2, 3) > 0.55);
    for (let y = 0; y <= top; y++) {
      let id = B.stone;
      if (y === top) id = rocky ? B.stone : top < WATER_Y ? (hash2(x, z, 4) < 0.3 ? B.gravel : B.sand) : beach ? B.sand : B.grass;
      else if (y > top - 4) id = rocky ? B.stone : (beach || top < WATER_Y) ? B.sand : B.dirt;
      if (rocky && y === top && hash2(x, z, 8) < 0.2) id = B.cobble;
      V.set(x, y, z, id);
    }
  }
  const topAt = (x, z) => heights[z * W + x];

  // --- paths: village -> grove, village -> hill ---
  const drawPath = (pts) => {
    for (let i = 0; i < pts.length - 1; i++) {
      const [ax, az] = pts[i], [bx, bz] = pts[i + 1];
      const n = Math.ceil(Math.hypot(bx - ax, bz - az) * 2);
      for (let k = 0; k <= n; k++) {
        const x = ax + (bx - ax) * k / n, z = az + (bz - az) * k / n;
        for (let ox = -1; ox <= 1; ox++) for (let oz = -1; oz <= 1; oz++) {
          const px = Math.round(x + ox), pz = Math.round(z + oz);
          if (Math.abs(ox) + Math.abs(oz) > 1 && hash2(px, pz, 2) < 0.6) continue;
          const t = topAt(px, pz);
          if (V.get(px, t, pz) === B.grass) V.set(px, t, pz, B.path);
        }
      }
    }
  };
  drawPath([[88, 70], [88, 60], [74, 62], [58, 66], [44, 70]]);
  drawPath([[88, 60], [104, 60], [118, 64], [130, 66], [138, 66]]);
  drawPath([[88, 60], [88, 44]]);

  // --- houses ---
  const house = (x0, z0, w, d, wallH, roof, doorSide, opts = {}) => {
    const y0 = 22; // floor level (ground top block is 21)
    for (let x = x0 - 1; x <= x0 + w; x++) for (let z = z0 - 1; z <= z0 + d; z++) {
      for (let y = topAt(Math.min(W - 1, Math.max(0, x)), Math.min(D - 1, Math.max(0, z))) + 1; y < y0; y++) V.set(x, y, z, B.cobble);
    }
    for (let x = x0; x < x0 + w; x++) for (let z = z0; z < z0 + d; z++) {
      V.set(x, y0 - 1, z, B.cobble);
      for (let y = y0; y < y0 + wallH + 12; y++) V.set(x, y, z, 0);
      const edge = x === x0 || x === x0 + w - 1 || z === z0 || z === z0 + d - 1;
      if (!edge) { V.set(x, y0 - 1, z, B.planks); continue; }
      const corner = (x === x0 || x === x0 + w - 1) && (z === z0 || z === z0 + d - 1);
      for (let y = y0; y < y0 + wallH; y++) {
        let id = corner ? B.oak_log : (y === y0 ? B.cobble : B.timber);
        if (!corner && y === y0 + 1 && ((x - x0) % 3 === 2 || (z - z0) % 3 === 2) && y0 + wallH - 1 > y) id = B.window;
        V.set(x, y, z, id);
      }
    }
    // door
    const dc = doorSide === 'z0' || doorSide === 'z1' ? [x0 + Math.floor(w / 2), doorSide === 'z0' ? z0 : z0 + d - 1] : [doorSide === 'x0' ? x0 : x0 + w - 1, z0 + Math.floor(d / 2)];
    V.set(dc[0], y0, dc[1], B.door); V.set(dc[0], y0 + 1, dc[1], B.door);
    // gable roof along x, sloping in z
    const full = roof === 'red' ? B.roof_red : B.roof_teal;
    const slab = roof === 'red' ? B.roof_red_slab : B.roof_teal_slab;
    const top = y0 + wallH;
    for (let k = 0; ; k++) {
      const za = z0 - 1 + k, zb = z0 + d - k;
      if (za > zb) break;
      for (let x = x0 - 1; x <= x0 + w; x++) {
        V.set(x, top + k, za, full); V.set(x, top + k, zb, full);
        if (za + 1 <= zb - 1 && za + 1 !== zb) { V.set(x, top + k + 1, za, slab); V.set(x, top + k + 1, zb, slab); }
        if (x === x0 - 1 || x === x0 + w) continue;
      }
      // gable wall fill
      for (let z = za + 1; z < zb; z++) { V.set(x0, top + k, z, B.plaster); V.set(x0 + w - 1, top + k, z, B.plaster); }
      if (za === zb || za + 1 === zb) {
        for (let x = x0 - 1; x <= x0 + w; x++) { V.set(x, top + k + 1, za, slab); V.set(x, top + k + 1, zb, slab); }
        break;
      }
    }
    // chimney
    if (opts.chimney) {
      const [cx, cz] = opts.chimney;
      for (let y = y0; y < top + Math.ceil(d / 2) + 3; y++) V.set(cx, y, cz, B.cobble);
    }
    return { door: dc, top };
  };
  const houses = [];
  houses.push(house(70, 58, 9, 7, 4, 'red', 'z1', { chimney: [71, 60] }));   // Juno's cottage
  houses.push(house(97, 49, 8, 7, 4, 'teal', 'z1', { chimney: [103, 51] }));
  houses.push(house(76, 44, 7, 6, 3, 'teal', 'z1'));
  houses.push(house(100, 62, 7, 7, 3, 'red', 'x0', { chimney: [105, 64] }));
  houses.push(house(58, 50, 7, 6, 3, 'teal', 'x1'));

  // Juno's open workshop pavilion, attached to the east of her cottage
  const wx0 = 80, wz0 = 60, ww = 5, wd = 5;
  for (let x = wx0; x < wx0 + ww; x++) for (let z = wz0; z < wz0 + wd; z++) {
    V.set(x, 21, z, B.planks);
    for (let y = 22; y < 28; y++) V.set(x, y, z, 0);
  }
  for (const [px, pz] of [[wx0, wz0], [wx0 + ww - 1, wz0], [wx0, wz0 + wd - 1], [wx0 + ww - 1, wz0 + wd - 1]]) for (let y = 22; y < 25; y++) V.set(px, y, pz, B.oak_log);
  for (let x = wx0 - 1; x <= wx0 + ww; x++) for (let z = wz0 - 1; z <= wz0 + wd; z++) {
    const edge = x === wx0 - 1 || x === wx0 + ww || z === wz0 - 1 || z === wz0 + wd;
    V.set(x, 25, z, edge ? B.roof_red_slab : B.dark_planks);
  }
  for (let x = wx0; x < wx0 + ww; x++) for (let z = wz0; z < wz0 + wd; z++) if (x > wx0 && x < wx0 + ww - 1 && z > wz0 && z < wz0 + wd - 1) V.set(x, 26, z, B.roof_red_slab);
  // workbench + shelves
  V.set(82, 22, 61, B.bench); V.set(83, 22, 61, B.bench);
  V.set(81, 22, 60, B.bookshelf); V.set(84, 22, 60, B.hay);

  // --- pier ---
  for (let z = PIER.z0; z <= PIER.z1; z++) {
    const wide = z >= 95;
    for (let x = PIER.x - (wide ? 3 : 2); x <= PIER.x + (wide ? 3 : 2); x++) {
      if (topAt(x, z) >= 21) continue;
      V.set(x, 20, z, B.pier);
      for (let y = 21; y < 24; y++) V.set(x, y, z, 0);
    }
    if ((z % 4 === 2) || z === PIER.z1) for (const x of [PIER.x - (wide ? 3 : 2), PIER.x + (wide ? 3 : 2)]) {
      for (let y = topAt(x, z) + 1; y < 20; y++) V.set(x, y, z, B.pier_post);
    }
  }
  const lanternPosts = [];
  for (let z = 78; z <= 94; z += 4) for (const x of [PIER.x - 2, PIER.x + 2]) {
    V.set(x, 21, z, B.post); V.set(x, 22, z, B.post);
    lanternPosts.push([x + 0.5, 23, z + 0.5]);
  }
  for (const x of [PIER.x - 3, PIER.x + 3]) { V.set(x, 21, 95, B.post); V.set(x, 22, 95, B.post); lanternPosts.push([x + 0.5, 23, 95.5]); }
  // "the last post"
  V.set(PIER.x, 21, PIER.z1, B.post); V.set(PIER.x, 22, PIER.z1, B.post); V.set(PIER.x, 23, PIER.z1, B.post);
  const lastPost = [PIER.x + 0.5, 24, PIER.z1 + 0.5];

  // --- trees ---
  const leafBall = (cx, cy, cz, rx, ry, rz, id, holes = 0.12) => {
    for (let x = -rx; x <= rx; x++) for (let y = -ry; y <= ry; y++) for (let z = -rz; z <= rz; z++) {
      const d = (x / (rx + 0.5)) ** 2 + (y / (ry + 0.5)) ** 2 + (z / (rz + 0.5)) ** 2;
      if (d > 1) continue;
      if (d > 0.6 && hash2(cx + x + y * 31, cz + z, 11) < holes) continue;
      if (V.get(cx + x, cy + y, cz + z) === 0) V.set(cx + x, cy + y, cz + z, id);
    }
  };
  const oak = (x, z, r) => {
    const y = topAt(x, z) + 1, h = 4 + Math.floor(r() * 3);
    if (V.get(x, y - 1, z) !== B.grass) return;
    leafBall(x, y + h - 1, z, 2, 2, 2, B.oak_leaves);
    for (let i = 0; i < h; i++) V.set(x, y + i, z, B.oak_log);
    V.set(x, y + h + 1, z, B.oak_leaves);
  };
  const birch = (x, z, r) => {
    const y = topAt(x, z) + 1, h = 5 + Math.floor(r() * 3);
    if (V.get(x, y - 1, z) !== B.grass) return;
    leafBall(x, y + h - 1, z, 2, 2, 2, B.oak_leaves, 0.2);
    for (let i = 0; i < h; i++) V.set(x, y + i, z, B.birch_log);
  };
  const cherry = (x, z, r, V2 = V, yBase = null) => {
    const y = yBase ?? topAt(x, z) + 1, h = 4 + Math.floor(r() * 2);
    const lean = r() < 0.5 ? 1 : -1;
    for (let i = 0; i < h; i++) V2.set(x + (i >= h - 1 ? lean : 0), y + i, z, B.cherry_log);
    const cx = x + lean, cy = y + h;
    for (let lx = -3; lx <= 3; lx++) for (let lz = -3; lz <= 3; lz++) for (let ly = -1; ly <= 1; ly++) {
      const d = Math.hypot(lx, lz) + Math.abs(ly) * 1.4;
      if (d > 3.4 + (ly === 0 ? 0.5 : 0)) continue;
      if (d > 2.6 && hash2(cx + lx + ly * 7, cz(lz), 13) < 0.3) continue;
      if (V2.get(cx + lx, cy + ly, z + lz) === 0) V2.set(cx + lx, cy + ly, z + lz, B.cherry_leaves);
    }
    function cz(lz) { return z + lz; }
    // drooping petals
    for (let k = 0; k < 6; k++) {
      const lx = Math.floor(r() * 7) - 3, lz = Math.floor(r() * 7) - 3;
      if (Math.hypot(lx, lz) < 3.2 && V2.get(cx + lx, cy - 2, z + lz) === 0) V2.set(cx + lx, cy - 2, z + lz, B.cherry_leaves);
    }
  };
  // cherry grove
  const groveTrees = [[30, 64], [40, 62], [36, 74], [26, 76], [46, 72], [33, 84], [44, 82], [22, 66], [52, 62]];
  for (const [x, z] of groveTrees) cherry(x, z, rng);
  // scatter oaks/birches
  for (let i = 0; i < 260; i++) {
    const x = 6 + Math.floor(rng() * (W - 12)), z = 6 + Math.floor(rng() * (D - 12));
    const top = topAt(x, z);
    const { lakeK, r } = terrainHeight(x, z);
    if (top < 22 || lakeK < 1 || r > 84 || top > 42) continue;
    if (Math.hypot(x - VILLAGE.x, z - VILLAGE.z) < 26) continue;
    if (Math.hypot(x - GROVE.x, z - GROVE.z) < 22) continue;
    if (Math.hypot(x - HILL.x, z - HILL.z) < 17) continue;
    if (Math.abs(x - 88) < 4 && z > 60) continue;
    (rng() < 0.3 ? birch : oak)(x, z, rng);
  }
  // a few village trees
  oak(66, 70, rng); oak(108, 58, rng); cherry(95, 72, rng); oak(64, 44, rng); cherry(112, 70, rng);

  // --- ground cover ---
  for (let z = 1; z < D - 1; z++) for (let x = 1; x < W - 1; x++) {
    const t = topAt(x, z);
    const id = V.get(x, t, z);
    if (V.get(x, t + 1, z) !== 0) continue;
    const r = hash2(x, z, 77);
    if (id === B.grass) {
      const flowerField = fbm(x * 0.07, z * 0.07, 2, 21);
      if (r < 0.2) V.set(x, t + 1, z, B.tall_grass);
      else if (r < 0.2 + flowerField * 0.14) {
        const f = hash2(x, z, 91);
        const near = Math.hypot(x - GROVE.x, z - GROVE.z) < 24;
        V.set(x, t + 1, z, near ? (f < 0.5 ? B.flower_pink : B.flower_white) : f < 0.3 ? B.flower_red : f < 0.55 ? B.flower_yellow : f < 0.75 ? B.flower_blue : f < 0.9 ? B.flower_white : B.flower_pink);
      }
    } else if (id === B.sand && t === WATER_Y - 1 && r < 0.35) {
      V.set(x, t + 1, z, B.reeds);
    } else if ((id === B.sand || id === B.gravel) && t < WATER_Y - 1 && t > WATER_Y - 5 && r < 0.04) {
      V.set(x, WATER_Y, z, B.lily);
    }
  }
  // keep the hilltop clear for the sapling
  for (let x = HILL.x - 9; x <= HILL.x + 9; x++) for (let z = HILL.z - 9; z <= HILL.z + 9; z++) {
    const t = topAt(x, z), id = V.get(x, t + 1, z);
    const d = Math.hypot(x - HILL.x, z - HILL.z);
    if (d > 9) continue;
    if (id === B.tall_grass || (d < 3 && REG[id]?.shape === 'cross')) V.set(x, t + 1, z, 0);
  }

  return { V, topAt, lanternPosts, lastPost, houses, cherryAt: cherry };
}

// ---------------- mesher ----------------
const FACES = [
  { n: [1, 0, 0], c: [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]], k: 'side' },
  { n: [-1, 0, 0], c: [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]], k: 'side' },
  { n: [0, 1, 0], c: [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]], k: 'top' },
  { n: [0, -1, 0], c: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], k: 'bottom' },
  { n: [0, 0, 1], c: [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], k: 'side' },
  { n: [0, 0, -1], c: [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]], k: 'side' },
];
const UVS = [[0, 0], [1, 0], [1, 1], [0, 1]];
const AO_CURVE = [0.42, 0.62, 0.8, 1.0];

class Buf {
  constructor() { this.p = []; this.n = []; this.uv = []; this.c = []; this.d = []; this.i = []; }
  quad(verts, norm, uvs, layer, aos, waves, flip = false) {
    const b = this.p.length / 3;
    for (let k = 0; k < 4; k++) {
      this.p.push(...verts[k]); this.n.push(...norm); this.uv.push(...uvs[k]);
      const a = aos ? aos[k] : 1; this.c.push(a, a, a);
      this.d.push(layer, waves ? waves[k] : 0, 0);
    }
    if (flip) this.i.push(b + 1, b + 2, b + 3, b + 1, b + 3, b);
    else this.i.push(b, b + 1, b + 2, b, b + 2, b + 3);
  }
  geometry() {
    if (!this.i.length) return null;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.p, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(this.n, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
    g.setAttribute('color', new THREE.Float32BufferAttribute(this.c, 3));
    g.setAttribute('aData', new THREE.Float32BufferAttribute(this.d, 3));
    g.setIndex(this.i);
    g.computeBoundingSphere(); g.computeBoundingBox();
    return g;
  }
}

function boxFaces(buf, V, x, y, z, b, [x0, y0, z0, x1, y1, z1], cullNeighbors = true) {
  for (const f of FACES) {
    const [nx, ny, nz] = f.n;
    const touching = (nx === 1 && x1 === 1) || (nx === -1 && x0 === 0) || (ny === 1 && y1 === 1) || (ny === -1 && y0 === 0) || (nz === 1 && z1 === 1) || (nz === -1 && z0 === 0);
    if (cullNeighbors && touching && isFullOpaque(V.get(x + nx, y + ny, z + nz))) continue;
    const verts = f.c.map(([cx, cy, cz]) => [x + (cx ? x1 : x0), y + (cy ? y1 : y0), z + (cz ? z1 : z0)]);
    // uv from the sub-box so textures aren't squashed
    const uvs = f.c.map(([cx, cy, cz], k) => {
      if (ny !== 0) return [cx ? x1 : x0, cz ? z1 : z0];
      const u = nx !== 0 ? (cz ? z1 : z0) : (cx ? x1 : x0);
      return [nx === 1 || nz === -1 ? 1 - u : u, cy ? y1 : y0];
    });
    buf.quad(verts, f.n, uvs, b.faces[f.k], null, null);
  }
}

export function meshVoxels(V, x0, z0, x1, z1, yMin = 0, yMax = V.h) {
  const opaque = new Buf(), cut = new Buf();
  for (let y = yMin; y < yMax; y++) for (let z = z0; z < z1; z++) for (let x = x0; x < x1; x++) {
    const id = V.get(x, y, z);
    if (!id) continue;
    const b = REG[id];
    if (b.shape === 'cube') {
      const buf = b.cutout ? cut : opaque;
      for (const f of FACES) {
        const [nx, ny, nz] = f.n;
        const nb = V.get(x + nx, y + ny, z + nz);
        if (isFullOpaque(nb)) continue;
        if (b.cutout && nb === id && hash2(x * 3 + nx, z * 5 + nz + y * 17, 3) < 0.55) continue;
        const ax = [0, 1, 2].filter((a) => f.n[a] === 0);
        const aos = f.c.map((c) => {
          const s = [0, 0, 0];
          const p = [x + nx, y + ny, z + nz];
          const o1 = [0, 0, 0], o2 = [0, 0, 0];
          o1[ax[0]] = c[ax[0]] ? 1 : -1; o2[ax[1]] = c[ax[1]] ? 1 : -1;
          const s1 = isAOSolid(V.get(p[0] + o1[0], p[1] + o1[1], p[2] + o1[2])) ? 1 : 0;
          const s2 = isAOSolid(V.get(p[0] + o2[0], p[1] + o2[1], p[2] + o2[2])) ? 1 : 0;
          const cc = isAOSolid(V.get(p[0] + o1[0] + o2[0], p[1] + o1[1] + o2[1], p[2] + o1[2] + o2[2])) ? 1 : 0;
          void s;
          return AO_CURVE[s1 && s2 ? 0 : 3 - (s1 + s2 + cc)];
        });
        const verts = f.c.map(([cx, cy, cz]) => [x + cx, y + cy, z + cz]);
        const waves = b.wave ? f.c.map(() => b.wave * 0.5) : null;
        buf.quad(verts, f.n, UVS, b.faces[f.k], aos, waves, aos[0] + aos[2] < aos[1] + aos[3]);
      }
    } else if (b.shape === 'cross') {
      const j = (hash2(x, z, 5) - 0.5) * 0.4, k2 = (hash2(z, x, 6) - 0.5) * 0.4;
      const hgt = 0.85 + hash2(x, z, 7) * 0.3;
      const cx = x + 0.5 + j, cz = z + 0.5 + k2, r = 0.45;
      const layer = b.faces.side;
      const w = [0, 0, b.wave, b.wave];
      cut.quad([[cx - r, y, cz - r], [cx + r, y, cz + r], [cx + r, y + hgt, cz + r], [cx - r, y + hgt, cz - r]], [0.7, 0, -0.7], UVS, layer, [0.8, 0.8, 1, 1], w);
      cut.quad([[cx - r, y, cz + r], [cx + r, y, cz - r], [cx + r, y + hgt, cz - r], [cx - r, y + hgt, cz + r]], [0.7, 0, 0.7], UVS, layer, [0.8, 0.8, 1, 1], w);
    } else if (b.shape === 'flat') {
      const yy = y + 0.02;
      cut.quad([[x, yy, z + 1], [x + 1, yy, z + 1], [x + 1, yy, z], [x, yy, z]], [0, 1, 0], UVS, b.faces.top, null, [0.15, 0.15, 0.15, 0.15]);
    } else if (b.shape === 'slab') boxFaces(opaque, V, x, y, z, b, [0, 0, 0, 1, 0.5, 1]);
    else if (b.shape === 'path') boxFaces(opaque, V, x, y, z, b, [0, 0, 0, 1, 15 / 16, 1]);
    else if (b.shape === 'post') {
      boxFaces(opaque, V, x, y, z, b, [6 / 16, 0, 6 / 16, 10 / 16, 1, 10 / 16], false);
    }
  }
  return { opaque: opaque.geometry(), cutout: cut.geometry() };
}
