// "Willow" — an original, procedurally painted 16x16 cozy texture pack.
// Every tile is generated from code with a seeded RNG; no external assets.
import * as THREE from 'three';
import { mulberry32, hash2, valueNoise, hexToRgb } from './util.js';

const S = 16;
const tiles = [];          // {name, data: Uint8ClampedArray(S*S*4)}
export const T = {};       // name -> layer index

const P = (list) => list.map(hexToRgb);
const pick = (rng, pal) => pal[Math.floor(rng() * pal.length)];
const mixc = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const mul = (c, f) => [c[0] * f, c[1] * f, c[2] * f];

function tile(name, fn, seed = tiles.length * 97 + 11) {
  const rng = mulberry32(seed);
  const data = new Uint8ClampedArray(S * S * 4);
  const px = (x, y) => {
    const i = (y * S + x) * 4;
    return { get: () => [data[i], data[i + 1], data[i + 2], data[i + 3]], set: (c, a = 255) => { data[i] = c[0]; data[i + 1] = c[1]; data[i + 2] = c[2]; data[i + 3] = a; } };
  };
  // default: fill via per-pixel function
  const res = fn({ rng, px, data });
  if (typeof res === 'function') {
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      const out = res(x, y);
      px(x, y).set(out, out[3] ?? 255);
    }
  }
  T[name] = tiles.length;
  tiles.push({ name, data });
}

// ---------- palettes ----------
const GRASS = P(['#6fbf4e', '#79c957', '#83cf5f', '#67b649', '#5eab43', '#8bd566']);
const DIRT = P(['#8d5d3d', '#7f5236', '#99693f', '#735035', '#86583a']);
const STONE = P(['#9a9ca0', '#8b8e92', '#a6a8ac', '#7f8286']);
const PLANK = P(['#c99d61', '#c19459', '#d1a86b', '#bb8e53']);
const DPLANK = P(['#7a5233', '#6f4a2e', '#86603b', '#654229']);
const LEAF = P(['#4f9a3c', '#5aa843', '#468c35', '#63b04a', '#3f8531']);
const CHERRY = P(['#ffb3c8', '#ffc4d4', '#f79ab8', '#ffd6e2', '#fca8c2', '#ffe2ec']);
const SAND = P(['#ead9a6', '#e3d09a', '#f0e0b2', '#dcc790']);

tile('grass_top', ({ rng }) => (x, y) => {
  const n = valueNoise(x * 0.35, y * 0.35, 3);
  let c = pick(rng, GRASS);
  c = mul(c, 0.92 + n * 0.16);
  if (rng() < 0.06) c = mixc(c, [190, 230, 120], 0.35);
  return c;
});
tile('grass_side', ({ rng }) => {
  const depth = Array.from({ length: S }, () => 3 + Math.floor(rng() * 3));
  return (x, y) => {
    if (y < depth[x]) return mul(pick(rng, GRASS), y === depth[x] - 1 ? 0.85 : 1);
    return mul(pick(rng, DIRT), 0.95 + rng() * 0.1);
  };
});
tile('dirt', ({ rng }) => (x, y) => {
  let c = pick(rng, DIRT);
  if (rng() < 0.07) c = mul(c, 0.75);
  if (rng() < 0.04) c = [170, 140, 110];
  return c;
});
tile('path', ({ rng }) => (x, y) => {
  let c = mixc(pick(rng, DIRT), [196, 160, 110], 0.45);
  if (rng() < 0.08) c = mul(c, 0.85);
  if (rng() < 0.05) c = [150, 150, 140];
  return c;
});
tile('stone', ({ rng }) => (x, y) => {
  let c = pick(rng, STONE);
  const n = valueNoise(x * 0.5, y * 0.9, 7);
  if (n > 0.78) c = mul(c, 0.8);
  return c;
});
function cellTile(name, pal, edge, seed, count = 7) {
  tile(name, ({ rng }) => {
    const pts = Array.from({ length: count }, () => [rng() * S, rng() * S, pick(rng, pal)]);
    return (x, y) => {
      let d1 = 1e9, d2 = 1e9, c = null;
      for (const [px, py, pc] of pts) for (let ox = -S; ox <= S; ox += S) for (let oy = -S; oy <= S; oy += S) {
        const d = (x + 0.5 - px - ox) ** 2 + (y + 0.5 - py - oy) ** 2;
        if (d < d1) { d2 = d1; d1 = d; c = pc; } else if (d < d2) d2 = d;
      }
      const e = Math.sqrt(d2) - Math.sqrt(d1);
      let out = e < 1.1 ? edge : mul(c, 0.95 + rng() * 0.1);
      if (e >= 1.1 && e < 2 && (x + y) % 3 === 0) out = mul(out, 1.08);
      return out;
    };
  }, seed);
}
cellTile('cobble', P(['#a1a3a6', '#8f9195', '#b0b2b5', '#999b9f']), hexToRgb('#5f6164'), 501, 8);
cellTile('mossy', P(['#a1a3a6', '#7fa06a', '#8f9195', '#6f9a5a']), hexToRgb('#4f5a4c'), 502, 8);
cellTile('gravel', P(['#9c928a', '#857c75', '#b0a79f', '#766f69', '#a59a8f']), hexToRgb('#6b645e'), 503, 14);

function planks(name, pal, seed) {
  tile(name, ({ rng }) => {
    const seams = [3, 11, 6, 13].map((s) => s + Math.floor(rng() * 2));
    return (x, y) => {
      const row = Math.floor(y / 4);
      let c = mul(pal[row % pal.length], 0.96 + valueNoise(x * 0.8, y * 3, seed) * 0.08);
      if (y % 4 === 3) c = mul(c, 0.7);
      if (x === seams[row]) c = mul(c, 0.78);
      if (rng() < 0.04) c = mul(c, 0.9);
      return c;
    };
  }, seed);
}
planks('planks', PLANK, 601);
planks('dark_planks', DPLANK, 602);
planks('pier', P(['#9b7048', '#8e6641', '#a57a51', '#88603c']), 603);

function logSide(name, pal, seed) {
  tile(name, ({ rng }) => {
    const cols = Array.from({ length: S }, () => pick(rng, pal));
    return (x, y) => {
      let c = cols[x];
      if (valueNoise(x * 2.1, y * 0.35, seed) > 0.7) c = mul(c, 0.78);
      return mul(c, 0.95 + rng() * 0.1);
    };
  }, seed);
}
logSide('oak_log', P(['#6e4c2f', '#5e3f26', '#7b5737', '#664529']), 701);
logSide('cherry_log', P(['#5b3435', '#4b2a2c', '#6a3e3d', '#533031']), 702);
tile('birch_log', ({ rng }) => (x, y) => {
  let c = mixc([236, 231, 219], [220, 214, 200], rng());
  if (valueNoise(x * 0.6, y * 1.7, 9) > 0.72) c = [52, 48, 46];
  return c;
});
tile('log_top', () => (x, y) => {
  const d = Math.max(Math.abs(x - 7.5), Math.abs(y - 7.5));
  if (d > 6.5) return [108, 76, 47];
  const ring = Math.floor(d) % 2;
  return ring ? [196, 152, 98] : [178, 136, 86];
});
function leaves(name, pal, holes, seed) {
  tile(name, ({ rng }) => (x, y) => {
    if (rng() < holes) return [0, 0, 0, 0];
    let c = pick(rng, pal);
    const n = valueNoise(x * 0.6, y * 0.6, seed);
    c = mul(c, 0.82 + n * 0.3);
    return [...c, 255];
  }, seed);
}
leaves('oak_leaves', LEAF, 0.16, 801);
leaves('cherry_leaves', CHERRY, 0.1, 802);
tile('sand', ({ rng }) => (x, y) => mul(pick(rng, SAND), 0.97 + rng() * 0.06));
tile('snow', ({ rng }) => (x, y) => {
  const c = [244, 248, 255];
  return mul(c, 0.94 + rng() * 0.06);
});
tile('plaster', ({ rng }) => (x, y) => {
  let c = [240, 228, 202];
  c = mul(c, 0.95 + valueNoise(x * 0.5, y * 0.5, 4) * 0.07);
  if (rng() < 0.03) c = mul(c, 0.93);
  return c;
});
// timber frame plaster with a cross beam
tile('timber', ({ rng }) => (x, y) => {
  if (x === 0 || x === 15 || y === 0 || y === 15) return mul([112, 76, 46], 0.95 + rng() * 0.1);
  let c = mul([240, 228, 202], 0.95 + valueNoise(x * 0.5, y * 0.5, 5) * 0.07);
  return c;
});
function roof(name, base, seed) {
  const pal = P(base);
  tile(name, ({ rng }) => (x, y) => {
    const row = Math.floor(y / 4);
    const off = row % 2 ? 2 : 0;
    const col = Math.floor((x + off) / 4);
    let c = mul(pal[(row * 3 + col) % pal.length], 0.95 + rng() * 0.08);
    if (y % 4 === 3) c = mul(c, 0.72);
    if ((x + off) % 4 === 0) c = mul(c, 0.85);
    return c;
  }, seed);
}
roof('roof_red', ['#b8583f', '#a94f39', '#c46a4b', '#9f4834'], 901);
roof('roof_teal', ['#3f7d86', '#377078', '#4a8b93', '#326870'], 902);
// window: dark-oak frame, warm glass. alpha=0 marks emissive pixels (night glow)
tile('window', ({ rng }) => (x, y) => {
  if (x < 2 || x > 13 || y < 2 || y > 13 || x === 7 || x === 8 || y === 7 || y === 8) return mul([98, 66, 40], 0.92 + rng() * 0.1);
  const hl = (x + y) % 9 === 0 || (x + y) % 9 === 1;
  return [...(hl ? [214, 232, 240] : [150, 186, 204]), 0];
});
tile('door', ({ rng }) => (x, y) => {
  if (x === 0 || x === 15) return [92, 62, 38];
  let c = mul([150, 104, 62], 0.94 + valueNoise(x * 3, y * 0.4, 12) * 0.1);
  if (x % 5 === 0) c = mul(c, 0.8);
  if (x === 12 && y === 8) c = [214, 180, 90];
  return c;
});
tile('bench_top', ({ rng }) => (x, y) => {
  if (x === 0 || y === 0 || x === 15 || y === 15) return [96, 64, 40];
  let c = mul(pick(rng, PLANK), 0.95);
  if (x > 3 && x < 12 && (y === 5 || y === 10)) c = [120, 120, 126];
  return c;
});
tile('bench_side', ({ rng }) => (x, y) => {
  if (y < 3) return mul([96, 64, 40], 0.95 + rng() * 0.1);
  let c = mul(pick(rng, PLANK), 0.9);
  if ((x === 3 || x === 12) && y > 2) c = [96, 64, 40];
  if (y > 5 && y < 9 && x > 4 && x < 11) c = [80, 80, 86]; // hanging tool
  return c;
});
tile('hay', ({ rng }) => (x, y) => {
  let c = mixc([222, 186, 80], [196, 158, 60], rng());
  if (y === 4 || y === 11) c = [150, 60, 40];
  return c;
});
tile('bookshelf', ({ rng }) => (x, y) => {
  if (y < 1 || y > 14 || y === 7 || y === 8) return mul(pick(rng, PLANK), 0.9);
  const colors = P(['#8a3d3d', '#3d5a8a', '#4f7a3c', '#b8903c', '#6d4a8a']);
  const book = Math.floor(x / 2) + (y > 7 ? 3 : 0);
  return mul(colors[book % colors.length], x % 2 ? 0.85 : 1);
});
tile('wool_cream', ({ rng }) => (x, y) => mul([236, 224, 200], 0.92 + rng() * 0.08));
tile('wool_rose', ({ rng }) => (x, y) => mul([214, 120, 140], 0.92 + rng() * 0.08));

// ---- cutout sprites ----
function sprite(name, fn, seed) {
  tile(name, ({ rng }) => {
    const img = Array.from({ length: S * S }, () => [0, 0, 0, 0]);
    fn(rng, (x, y, c) => { if (x >= 0 && x < S && y >= 0 && y < S) img[y * S + x] = [...c, 255]; });
    return (x, y) => img[y * S + x];
  }, seed);
}
sprite('tall_grass', (rng, put) => {
  for (let b = 0; b < 7; b++) {
    let x = 1 + Math.floor(rng() * 14);
    const h = 6 + Math.floor(rng() * 9);
    for (let i = 0; i < h; i++) {
      put(x, 15 - i, mul(pick(rng, GRASS), 0.8 + i / h * 0.35));
      if (rng() < 0.2) x += rng() < 0.5 ? -1 : 1;
    }
  }
}, 1001);
function flower(name, petal, center, seed) {
  sprite(name, (rng, put) => {
    for (let y = 7; y < 16; y++) put(7 + (y > 12 ? 1 : 0), y, [72, 140, 54]);
    put(6, 11, [86, 160, 64]); put(5, 10, [86, 160, 64]); put(9, 12, [86, 160, 64]); put(10, 11, [86, 160, 64]);
    const p = hexToRgb(petal);
    for (const [dx, dy] of [[0, -1], [-1, 0], [1, 0], [0, 1], [-1, -1], [1, -1], [-1, 1], [1, 1], [0, -2], [-2, 0], [2, 0]]) put(7 + dx, 5 + dy, mul(p, dx * dy ? 0.85 : 1));
    put(7, 5, hexToRgb(center));
  }, seed);
}
flower('flower_red', '#e2434b', '#f5d142', 1101);
flower('flower_yellow', '#f7d23e', '#e28a2a', 1102);
flower('flower_blue', '#5b8ee6', '#f0f0f0', 1103);
flower('flower_pink', '#f59ac0', '#fff3a0', 1104);
flower('flower_white', '#f4f4f0', '#f2c230', 1105);
sprite('sapling', (rng, put) => {
  for (let y = 9; y < 16; y++) put(7, y, [92, 58, 50]);
  for (let i = 0; i < 22; i++) {
    const a = rng() * Math.PI * 2, r = rng() * 4;
    put(Math.round(7 + Math.cos(a) * r), Math.round(6 + Math.sin(a) * r * 0.8), pick(rng, CHERRY));
  }
}, 1201);
sprite('reeds', (rng, put) => {
  for (let b = 0; b < 5; b++) {
    const x = 2 + b * 3;
    const h = 9 + Math.floor(rng() * 6);
    for (let i = 0; i < h; i++) put(x, 15 - i, mul([96, 140, 70], 0.85 + i / h * 0.3));
    for (let i = 0; i < 3; i++) put(x, 15 - h - i + 2, [120, 80, 50]);
  }
}, 1202);
sprite('lily', (rng, put) => {
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const d = Math.hypot(x - 7.5, y - 7.5);
    if (d < 7 && !(x > 7 && Math.abs(y - 7.5) < 1.5)) put(x, y, mul([74, 140, 60], 0.85 + hash2(x, y, 5) * 0.25));
  }
  put(5, 5, [250, 200, 220]); put(6, 5, [250, 220, 230]); put(5, 6, [250, 220, 230]);
}, 1203);

export function buildTileArray() {
  const n = tiles.length;
  const data = new Uint8Array(S * S * 4 * n);
  tiles.forEach((t, i) => {
    // flip vertically so v=1 is the top of the painted tile
    for (let y = 0; y < S; y++) data.set(t.data.subarray((S - 1 - y) * S * 4, (S - y) * S * 4), i * S * S * 4 + y * S * 4);
  });
  const tex = new THREE.DataArrayTexture(data, S, S, n);
  tex.format = THREE.RGBAFormat;
  tex.type = THREE.UnsignedByteType;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.magFilter = THREE.NearestFilter;
  tex.minFilter = THREE.NearestMipmapLinearFilter;
  tex.generateMipmaps = true;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  tex.needsUpdate = true;
  return tex;
}

export function tileAverage(name) {
  const d = tiles[T[name]].data;
  let r = 0, g = 0, b = 0, c = 0;
  for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 0) { r += d[i]; g += d[i + 1]; b += d[i + 2]; c++; }
  return [r / c, g / c, b / c];
}

// Debug: paint the whole pack to a canvas (used for the texture-pack sheet)
export function packSheet(scale = 4) {
  const cols = 8, rows = Math.ceil(tiles.length / cols);
  const cv = document.createElement('canvas');
  cv.width = cols * S * scale; cv.height = rows * S * scale;
  const ctx = cv.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  tiles.forEach((t, i) => {
    const c2 = document.createElement('canvas'); c2.width = c2.height = S;
    c2.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(t.data), S, S), 0, 0);
    ctx.drawImage(c2, (i % cols) * S * scale, Math.floor(i / cols) * S * scale, S * scale, S * scale);
  });
  return cv;
}
