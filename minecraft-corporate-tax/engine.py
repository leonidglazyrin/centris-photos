"""Numpy voxel ray-caster with swappable texture packs, sun shadows,
smooth ambient occlusion, colour grading and optional toon outlines.
"""
import math
import numpy as np

RW, RH = 360, 780          # internal render resolution (portrait, upscaled 3x)
GX, GY, GZ = 192, 48, 192
MAXT = 95.0

(AIR, GRASS, DIRT, STONE, COBBLE, LOG, PLANKS, LEAVES, GOLD, EMERALD, DIAMOND,
 OBSIDIAN, PORTAL, WATER, STONEBRICK, TNT, SAND, CHEST, ROOF, BRICKS, TNT_LIT,
 WHITEWOOL, QUARTZ, GLASS, IRON, FURNACE, REDWOOL, PATH, SMOOTH, DIAMOND_ORE) = range(30)
NB = 30

# ================================================================== packs
PACKS = {
    "faithful": dict(
        title="Faithful HD", res=32, noise=0.75, sat=1.05, pastel=0.0,
        shadows=True, ao=0.18, shading="sun", outline=False,
        sun=(-0.45, 0.62, 0.64), sun_col=(1.0, 0.97, 0.9), amb_col=(0.55, 0.6, 0.7),
        horizon=(0.76, 0.86, 1.0), zenith=(0.42, 0.62, 0.98), fog=(60, 95),
        grade=dict(contrast=1.05, sat=1.08, tint=(1.0, 1.0, 1.0)),
    ),
    "barebones": dict(
        title="Bare Bones (clean)", res=16, noise=0.18, sat=1.1, pastel=0.05,
        shadows=False, ao=0.14, shading="mc", outline=False,
        sun=(-0.35, 0.7, 0.62), sun_col=(1, 1, 1), amb_col=(1, 1, 1),
        horizon=(0.72, 0.87, 1.0), zenith=(0.36, 0.64, 1.0), fog=(65, 95),
        grade=dict(contrast=1.08, sat=1.15, tint=(1.0, 1.0, 1.0)),
    ),
    "shaders": dict(
        title="Shaders (golden hour)", res=32, noise=0.7, sat=1.0, pastel=0.0,
        shadows=True, ao=0.22, shading="sun", outline=False,
        sun=(-0.75, 0.33, 0.57), sun_col=(1.25, 0.98, 0.72), amb_col=(0.42, 0.48, 0.66),
        horizon=(1.0, 0.78, 0.55), zenith=(0.38, 0.55, 0.9), fog=(50, 95),
        grade=dict(contrast=1.12, sat=1.18, tint=(1.04, 1.0, 0.94)),
    ),
    "toon": dict(
        title="Toon (outlined)", res=16, noise=0.08, sat=1.2, pastel=0.08,
        shadows=True, ao=0.1, shading="sun", outline=True,
        sun=(-0.4, 0.7, 0.6), sun_col=(0.95, 0.93, 0.88), amb_col=(0.62, 0.65, 0.75),
        horizon=(0.78, 0.9, 1.0), zenith=(0.4, 0.7, 1.0), fog=(65, 95),
        grade=dict(contrast=1.05, sat=1.2, tint=(1.0, 1.0, 1.0)),
    ),
    "pastel": dict(
        title="Cozy Pastel", res=32, noise=0.35, sat=0.9, pastel=0.14,
        shadows=True, ao=0.16, shading="sun", outline=False,
        sun=(-0.3, 0.75, 0.6), sun_col=(1.0, 0.95, 0.95), amb_col=(0.7, 0.68, 0.78),
        horizon=(1.0, 0.88, 0.92), zenith=(0.62, 0.74, 1.0), fog=(55, 95),
        grade=dict(contrast=0.95, sat=1.0, tint=(1.02, 0.99, 1.02)),
    ),
    "comic": dict(
        title="Comic HD", res=32, noise=0.3, sat=1.3, pastel=0.0, posterize=7, tex_border=0.72,
        shadows=True, ao=0.12, shading="sun", outline=True,
        sun=(-0.4, 0.7, 0.6), sun_col=(1.0, 0.97, 0.9), amb_col=(0.62, 0.66, 0.78),
        horizon=(0.7, 0.88, 1.0), zenith=(0.25, 0.58, 1.0), fog=(65, 95),
        grade=dict(contrast=1.12, sat=1.25, tint=(1.0, 1.0, 1.0)),
    ),
    "realistic": dict(
        title="Realistic 64x", res=64, noise=1.25, sat=0.82, pastel=0.0,
        shadows=True, ao=0.24, shading="sun", outline=False,
        sun=(-0.55, 0.52, 0.66), sun_col=(1.12, 1.04, 0.92), amb_col=(0.46, 0.52, 0.64),
        horizon=(0.8, 0.86, 0.94), zenith=(0.4, 0.56, 0.84), fog=(45, 95),
        grade=dict(contrast=1.14, sat=0.95, tint=(1.02, 1.0, 0.97)),
    ),
    "retro": dict(
        title="Retro 8-bit", res=8, noise=1.0, sat=1.2, pastel=0.0,
        shadows=False, ao=0.0, shading="mc", outline=False,
        sun=(-0.35, 0.7, 0.62), sun_col=(1, 1, 1), amb_col=(1, 1, 1),
        horizon=(0.62, 0.78, 1.0), zenith=(0.45, 0.62, 1.0), fog=(70, 95),
        grade=dict(contrast=1.1, sat=1.2, tint=(1.0, 1.0, 1.0)),
    ),
    "autumn": dict(
        title="Autumn", res=32, noise=0.6, sat=1.1, pastel=0.0,
        tints={"LEAVES": (3.4, 0.95, 0.9), "GRASS": (1.3, 0.92, 0.8)},
        shadows=True, ao=0.2, shading="sun", outline=False,
        sun=(-0.6, 0.45, 0.66), sun_col=(1.2, 0.95, 0.7), amb_col=(0.5, 0.48, 0.6),
        horizon=(1.0, 0.84, 0.66), zenith=(0.46, 0.6, 0.9), fog=(50, 95),
        grade=dict(contrast=1.08, sat=1.12, tint=(1.05, 0.99, 0.9)),
    ),
    "medieval": dict(
        title="Medieval (overcast)", res=32, noise=1.0, sat=0.62, pastel=0.0,
        tints={"GRASS": (0.9, 0.9, 0.8), "LEAVES": (0.85, 0.85, 0.75), "QUARTZ": (0.8, 0.77, 0.72)},
        shadows=True, ao=0.26, shading="sun", outline=False,
        sun=(-0.3, 0.8, 0.5), sun_col=(0.55, 0.55, 0.55), amb_col=(0.62, 0.63, 0.66),
        horizon=(0.72, 0.74, 0.76), zenith=(0.5, 0.54, 0.6), fog=(40, 85),
        grade=dict(contrast=1.15, sat=0.85, tint=(1.03, 1.0, 0.94)),
    ),
    "keyart": dict(
        title="Key Art (official promo look)", res=32, noise=0.55, sat=1.05, pastel=0.0, bevel=0.1,
        tints={"GRASS": (1.0, 1.06, 0.78), "LEAVES": (1.0, 1.1, 0.8)},
        shadows=True, soft_shadow=3, ao=0.3, shading="sun", outline=False,
        sun=(-0.55, 0.62, 0.56), sun_col=(1.2, 1.08, 0.9), amb_col=(0.5, 0.62, 0.86),
        horizon=(0.72, 0.9, 1.0), zenith=(0.2, 0.55, 1.0), fog=(60, 95),
        dof=0.7, bloom=0.28, vignette=0.25,
        grade=dict(contrast=1.1, sat=1.08, tint=(1.03, 1.0, 0.95)),
    ),
    "plastic": dict(
        title="Plastic (glossy)", res=32, noise=0.06, sat=1.3, pastel=0.04, bevel=0.22, spec=0.45,
        shadows=True, ao=0.14, shading="sun", outline=False,
        sun=(-0.45, 0.66, 0.6), sun_col=(1.0, 1.0, 1.0), amb_col=(0.66, 0.7, 0.8),
        horizon=(0.78, 0.9, 1.0), zenith=(0.3, 0.6, 1.0), fog=(65, 95),
        grade=dict(contrast=1.06, sat=1.18, tint=(1.0, 1.0, 1.0)),
    ),
}
P = PACKS["faithful"]
TEX = None


def configure(w=None, h=None, pack=None):
    global RW, RH, P, TEX
    if w:
        RW, RH = w, h
    if pack:
        P = PACKS[pack]
        TEX = make_textures(P)


# ================================================================== textures
def _rng(seed):
    return np.random.default_rng(seed)


_NOISE = 1.0


def _speckle(col, amt, seed, levels=4):
    amt = amt * _NOISE
    r = _rng(seed)
    n = r.integers(0, levels, (16, 16, 1)) / (levels - 1)
    return np.clip(np.array(col, np.float32)[None, None, :] * (1 - amt / 2 + amt * n), 0, 1)


def _voronoi_lines(seed, npts=7):
    r = _rng(seed)
    pts = r.random((npts, 2)) * 16
    yy, xx = np.mgrid[0:16, 0:16] + 0.5
    ds = []
    for px, py in pts:
        for ox in (-16, 0, 16):
            for oy in (-16, 0, 16):
                ds.append(np.hypot(xx - px - ox, yy - py - oy))
    ds = np.sort(np.stack(ds), axis=0)
    return (ds[1] - ds[0]) < 1.3


def _design16():
    T = np.zeros((NB, 3, 16, 16, 3), np.float32)
    yy, xx = np.mgrid[0:16, 0:16]

    def all3(b, tex):
        T[b, 0] = T[b, 1] = T[b, 2] = tex

    dirt = _speckle((0.55, 0.39, 0.27), 0.45, 2)
    dirt[_rng(3).random((16, 16)) < 0.08 * _NOISE] *= 0.75
    all3(DIRT, dirt)
    grass_top = _speckle((0.40, 0.66, 0.26), 0.35, 1)
    side = dirt.copy()
    r = _rng(4)
    gs = _speckle((0.40, 0.66, 0.26), 0.3, 5)
    for x in range(16):
        k = 3 + int(r.integers(0, 3))
        side[:k, x] = gs[:k, x]
    T[GRASS, 0], T[GRASS, 1], T[GRASS, 2] = grass_top, side, dirt
    all3(STONE, _speckle((0.52, 0.52, 0.53), 0.3, 6))
    all3(SMOOTH, _speckle((0.66, 0.66, 0.67), 0.08, 60))
    T[SMOOTH, 1][[0, 15]] *= 0.85
    cob = _speckle((0.52, 0.52, 0.52), 0.35, 7)
    cob[_voronoi_lines(8)] *= 0.55
    all3(COBBLE, cob)

    r = _rng(9)
    bark = np.zeros((16, 16, 3), np.float32)
    colv = r.random(16)
    for x in range(16):
        bark[:, x] = np.array((0.40, 0.30, 0.18)) * (1 - 0.35 * _NOISE / 2 + 0.35 * _NOISE * colv[x])
    d = np.maximum(abs(xx + 0.5 - 8), abs(yy + 0.5 - 8))
    rings = np.where((np.floor(d) % 2) == 0, 1.0, 0.88)[..., None] * np.array((0.70, 0.56, 0.34))
    rings[d > 6.5] = bark[d > 6.5]
    T[LOG, 0], T[LOG, 1], T[LOG, 2] = rings, bark, rings

    def planks(col, seed):
        p = _speckle(col, 0.18, seed)
        p[yy % 4 == 3] *= 0.7
        for band, o in enumerate([3, 11, 6, 14]):
            p[band * 4:band * 4 + 3, o] *= 0.75
        return p
    all3(PLANKS, planks((0.72, 0.57, 0.35), 10))
    all3(ROOF, planks((0.42, 0.30, 0.19), 11))
    lv = _speckle((0.24, 0.52, 0.16), 0.6, 12)
    lv[_rng(13).random((16, 16)) < 0.22 * max(_NOISE, 0.3)] *= 0.55
    all3(LEAVES, lv)

    def metal(col, seed, shine=6):
        m = _speckle(col, 0.12, seed)
        m[0, :] = m[:, 0] = np.minimum(np.array(col) * 1.2, 1)
        m[15, :] = m[:, 15] = np.array(col) * 0.72
        r = _rng(seed + 1)
        for _ in range(shine):
            y, x = r.integers(2, 13, 2)
            m[y, x:x + 3] = np.minimum(np.array(col) * 1.25, 1)
        return m
    all3(GOLD, metal((0.98, 0.82, 0.24), 14))
    all3(DIAMOND, metal((0.38, 0.88, 0.86), 16))
    all3(IRON, metal((0.86, 0.86, 0.86), 18, 3))
    T[IRON][:, yy % 5 == 4] *= 0.85
    em = metal((0.16, 0.78, 0.36), 18)
    em[(abs(xx - 7.5) + abs(yy - 7.5)) < 4] *= 1.15
    all3(EMERALD, np.clip(em, 0, 1))
    ore = _speckle((0.52, 0.52, 0.53), 0.3, 61)
    r = _rng(62)
    for _ in range(5):
        y, x = r.integers(1, 14, 2)
        ore[y:y + 2, x:x + 2] = (0.45, 0.95, 0.92)
    all3(DIAMOND_ORE, ore)

    ob = _speckle((0.09, 0.06, 0.15), 0.6, 20)
    all3(OBSIDIAN, ob)
    all3(PORTAL, _speckle((0.52, 0.12, 0.82), 0.5, 22))
    all3(WATER, _speckle((0.22, 0.40, 0.85), 0.25, 23))
    sb = _speckle((0.50, 0.50, 0.51), 0.2, 24)
    sb[yy % 8 == 7] *= 0.65
    sb[(yy < 8) & (xx == 0)] *= 0.65
    sb[(yy >= 8) & (xx == 8)] *= 0.65
    all3(STONEBRICK, sb)
    br = _speckle((0.64, 0.30, 0.23), 0.25, 25)
    mortar = (0.74, 0.72, 0.68)
    br[yy % 4 == 3] = mortar
    for band in range(4):
        o = 0 if band % 2 == 0 else 4
        br[band * 4:band * 4 + 3, o % 16] = mortar
        br[band * 4:band * 4 + 3, (o + 8) % 16] = mortar
    all3(BRICKS, br)
    all3(SAND, _speckle((0.87, 0.82, 0.62), 0.18, 26))
    all3(WHITEWOOL, _speckle((0.94, 0.94, 0.94), 0.1, 27))
    all3(REDWOOL, _speckle((0.78, 0.2, 0.18), 0.12, 28))
    path = _speckle((0.62, 0.52, 0.34), 0.25, 29)
    T[PATH, 0] = path
    T[PATH, 1] = dirt
    T[PATH, 2] = dirt
    q = _speckle((0.93, 0.91, 0.88), 0.05, 30)
    q[0, :] = q[:, 0] = (0.97, 0.96, 0.94)
    q[15, :] = q[:, 15] = (0.8, 0.78, 0.75)
    all3(QUARTZ, q)
    g = np.zeros((16, 16, 3), np.float32) + np.array((0.62, 0.84, 0.95))
    g[0, :] = g[15, :] = g[:, 0] = g[:, 15] = (0.88, 0.95, 1.0)
    for i in range(3):
        g[3 + i, 9 - i] = g[4 + i, 9 - i] = (1, 1, 1)
    g[10, 4] = g[11, 3] = (1, 1, 1)
    all3(GLASS, g)
    fu = cob.copy()
    fu[8:13, 4:12] = (0.12, 0.12, 0.12)
    fu[10:13, 5:11] = (1.0, 0.6, 0.15)
    fu[11:13, 6:10] = (1.0, 0.85, 0.3)
    T[FURNACE, 1] = fu
    T[FURNACE, 0] = T[FURNACE, 2] = _speckle((0.45, 0.45, 0.45), 0.2, 31)

    tside = _speckle((0.86, 0.22, 0.15), 0.2, 32)
    tside[5:11] = (0.92, 0.92, 0.9)
    ttop = _speckle((0.75, 0.72, 0.70), 0.2, 33)
    T[TNT, 0], T[TNT, 1], T[TNT, 2] = ttop, tside, ttop
    T[TNT_LIT] = np.clip(T[TNT] * 0.4 + 0.65, 0, 1)
    cs = planks((0.64, 0.45, 0.20), 34)
    cs[0, :] = cs[15, :] = cs[:, 0] = cs[:, 15] = (0.30, 0.20, 0.08)
    cs[5, :] = (0.30, 0.20, 0.08)
    cs[4:8, 7:9] = (0.75, 0.75, 0.78)
    T[CHEST, 0] = T[CHEST, 2] = planks((0.64, 0.45, 0.20), 35)
    T[CHEST, 1] = cs
    return T


def make_textures(pack):
    global _NOISE
    _NOISE = pack["noise"]
    T = _design16()
    for name, mul in pack.get("tints", {}).items():
        T[globals()[name]] *= np.array(mul, np.float32)
    T = np.clip(T, 0, 1)
    res = pack["res"]
    if res < 16:
        k = 16 // res
        T = T.reshape(NB, 3, res, k, res, k, 3).mean((3, 5))
    elif res != 16:
        k = res // 16
        T = T.repeat(k, axis=2).repeat(k, axis=3)
        # soften blocky design pixels a little and add fine grain
        sm = T.copy()
        sm[:, :, 1:-1, :] = (T[:, :, :-2] + 2 * T[:, :, 1:-1] + T[:, :, 2:]) / 4
        sm[:, :, :, 1:-1] = (sm[:, :, :, :-2] + 2 * sm[:, :, :, 1:-1] + sm[:, :, :, 2:]) / 4
        T = T * 0.45 + sm * 0.55
        grain = _rng(99).random(T.shape[:4] + (1,)).astype(np.float32)
        T = T * (1 - 0.07 * pack["noise"] + 0.14 * pack["noise"] * grain)
    lum = T.mean(-1, keepdims=True)
    T = lum + (T - lum) * pack["sat"]
    T = T * (1 - pack["pastel"]) + pack["pastel"]
    if pack.get("bevel"):
        # smooth rounded-edge look: light top/left rim, dark bottom/right rim
        bv = pack["bevel"]
        w = max(2, res // 10)
        ramp = np.linspace(1, 0, w, dtype=np.float32)
        for i in range(w):
            T[:, :, i] *= 1 + bv * ramp[i]
            T[:, :, :, i] *= 1 + bv * 0.6 * ramp[i]
            T[:, :, -1 - i] *= 1 - bv * ramp[i]
            T[:, :, :, -1 - i] *= 1 - bv * 0.6 * ramp[i]
    if pack.get("posterize"):
        n = pack["posterize"]
        T = np.round(np.clip(T, 0, 1) * n) / n
    if pack.get("tex_border"):
        b = max(1, res // 16)
        T[:, :, :b] *= pack["tex_border"]
        T[:, :, -b:] *= pack["tex_border"]
        T[:, :, :, :b] *= pack["tex_border"]
        T[:, :, :, -b:] *= pack["tex_border"]
    return np.clip(T, 0, 1).astype(np.float32)


# ================================================================== camera
class Camera:
    def __init__(self, pos, target, fov=80.0):
        self.o = np.array(pos, np.float64)
        f = np.array(target, np.float64) - self.o
        self.f = f / np.linalg.norm(f)
        r = np.cross((0.0, 1.0, 0.0), self.f)
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.f, self.r)
        self.th = math.tan(math.radians(fov) / 2)   # vertical
        self.focus = float(np.linalg.norm(np.array(target, np.float64) - self.o))
        self.aspect = RW / RH

    def rays(self):
        xs = (np.arange(RW) + 0.5) / RW * 2 - 1
        ys = 1 - (np.arange(RH) + 0.5) / RH * 2
        X, Y = np.meshgrid(xs, ys)
        D = (self.f[None, None] + X[..., None] * self.th * self.aspect * self.r
             + Y[..., None] * self.th * self.u).reshape(-1, 3)
        return D / np.linalg.norm(D, axis=1, keepdims=True)

    def project(self, p, W=None, H=None):
        W = W or RW
        H = H or RH
        v = np.asarray(p, np.float64) - self.o
        z = v @ self.f
        if z <= 0.05:
            return None
        x = (v @ self.r) / (z * self.th * self.aspect)
        y = (v @ self.u) / (z * self.th)
        return ((x + 1) / 2 * W, (1 - y) / 2 * H, float(np.linalg.norm(v)))


# ================================================================== DDA
def raycast(grid, O, D, maxt=MAXT, steps=260):
    """O: (3,) or (N,3) origins."""
    N = D.shape[0]
    O = np.broadcast_to(np.asarray(O, np.float64), (N, 3))
    hit_id = np.zeros(N, np.uint8)
    hit_t = np.full(N, np.inf)
    hit_ax = np.zeros(N, np.int8)
    Dd = D.copy()
    Dd[np.abs(Dd) < 1e-9] = 1e-9
    inv = 1.0 / Dd
    p = np.floor(O).astype(np.int32)
    st = np.where(Dd > 0, 1, -1).astype(np.int32)
    td = np.abs(inv)
    tm = ((p + (st > 0)) - O) * inv
    act = np.arange(N)
    shape = np.array(grid.shape)
    for _ in range(steps):
        n = act.shape[0]
        if n == 0:
            break
        ax = np.argmin(tm, axis=1)
        idx = np.arange(n)
        tt = tm[idx, ax]
        p[idx, ax] += st[idx, ax]
        tm[idx, ax] += td[idx, ax]
        inb = (p >= 0).all(1) & (p < shape).all(1)
        b = np.zeros(n, np.uint8)
        pi = p[inb]
        b[inb] = grid[pi[:, 0], pi[:, 1], pi[:, 2]]
        hit = b > 0
        if hit.any():
            a = act[hit]
            hit_id[a] = b[hit]
            hit_t[a] = tt[hit]
            hit_ax[a] = ax[hit]
        keep = ~(hit | ~inb | (tt > maxt))
        act, p, tm, td, st = act[keep], p[keep], tm[keep], td[keep], st[keep]
    return hit_id, hit_t, hit_ax


def sky(D, o, time):
    y = D[:, 1]
    k = np.clip(y, 0, 1)[:, None] ** 0.55
    hz, zn = np.array(P["horizon"]), np.array(P["zenith"])
    col = hz[None] * (1 - k) + zn[None] * k
    L = np.array(P["sun"], np.float64)
    L /= np.linalg.norm(L)
    e1 = np.cross((0, 1, 0), L)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(L, e1)
    dl = D @ L
    with np.errstate(divide="ignore", invalid="ignore"):
        a = (D @ e1) / dl
        b = (D @ e2) / dl
    sun = (dl > 0) & (np.abs(a) < 0.05) & (np.abs(b) < 0.05)
    glow = np.clip(dl, 0, 1) ** 24 * 0.45
    col = col + glow[:, None] * np.array(P["sun_col"])[None]
    col[sun] = (1.0, 1.0, 0.9)
    up = y > 0.02
    tc = (130.0 - o[1]) / y[up]
    cx = np.floor((o[0] + D[up, 0] * tc + time * 1.2) / 12.0)
    cz = np.floor((o[2] + D[up, 2] * tc) / 12.0)
    h = np.modf(np.abs(np.sin(cx * 12.9898 + cz * 78.233) * 43758.5453))[0]
    al = np.where(h < 0.28, 0.85, 0.0) * np.clip(1 - tc / 900.0, 0, 1)
    ccol = np.array((1.0, 1.0, 1.0)) * 0.8 + 0.2 * np.array(P["sun_col"])
    col[up] = col[up] * (1 - al[:, None]) + al[:, None] * ccol
    return np.clip(col, 0, 1.2)


def light_for_normal(n, shadow=None):
    """n: (N,3) world normals -> (N,3) light multiplier."""
    if P["shading"] == "mc":
        n2 = n * n
        s = 0.62 * n2[:, 0] + 0.82 * n2[:, 2] + np.where(n[:, 1] > 0, 1.0, 0.5) * n2[:, 1]
        return s[:, None] * np.ones((1, 3))
    L = np.array(P["sun"], np.float64)
    L /= np.linalg.norm(L)
    ndl = np.clip(n @ L, 0, 1)
    if shadow is not None:
        ndl = ndl * shadow
    sky_amt = 0.75 + 0.25 * n[:, 1]
    return np.array(P["amb_col"])[None] * sky_amt[:, None] + np.array(P["sun_col"])[None] * (ndl[:, None] * 0.75)


def _solid(grid, q):
    inb = (q >= 0).all(1) & (q < np.array(grid.shape)).all(1)
    out = np.zeros(len(q), bool)
    qi = q[inb]
    g = grid[qi[:, 0], qi[:, 1], qi[:, 2]]
    out[inb] = (g > 0) & (g != GLASS) & (g != PORTAL)
    return out


def ambient_occlusion(grid, Pt, ax, nrm):
    """Minecraft-style smooth AO -> (N,) factor in [0,1]."""
    N = len(ax)
    cell = np.floor(Pt - nrm * 0.01).astype(np.int32)
    A = cell + nrm.astype(np.int32)
    t1 = np.where(ax == 0, 2, 0)
    t2 = np.where(ax == 1, 2, 1)
    e1 = np.zeros((N, 3), np.int32)
    e2 = np.zeros((N, 3), np.int32)
    e1[np.arange(N), t1] = 1
    e2[np.arange(N), t2] = 1
    f1 = Pt[np.arange(N), t1] % 1
    f2 = Pt[np.arange(N), t2] % 1
    s1m, s1p = _solid(grid, A - e1), _solid(grid, A + e1)
    s2m, s2p = _solid(grid, A - e2), _solid(grid, A + e2)

    def corner(sa, sb, dc):
        c = _solid(grid, A + dc)
        occ = np.where(sa & sb, 3, sa.astype(int) + sb.astype(int) + c.astype(int))
        return 1 - occ * P["ao"]
    vmm = corner(s1m, s2m, -e1 - e2)
    vpm = corner(s1p, s2m, e1 - e2)
    vmp = corner(s1m, s2p, -e1 + e2)
    vpp = corner(s1p, s2p, e1 + e2)
    return (vmm * (1 - f1) + vpm * f1) * (1 - f2) + (vmp * (1 - f1) + vpp * f1) * f2


def grade(col):
    g = P["grade"]
    col = (col - 0.5) * g["contrast"] + 0.5
    lum = col.mean(-1, keepdims=True)
    col = lum + (col - lum) * g["sat"]
    return col * np.array(g["tint"])


def _depth_blur(v, dep, r):
    """Separable box blur that only mixes pixels at similar depth."""
    for axis in (0, 1):
        acc = np.zeros_like(v)
        wsum = np.zeros_like(v)
        for o in range(-r, r + 1):
            vv = np.roll(v, o, axis)
            dd = np.roll(dep, o, axis)
            w = (np.abs(dd - dep) < 0.08 * dep + 0.3).astype(v.dtype)
            acc += vv * w
            wsum += w
        v = acc / np.maximum(wsum, 1e-6)
    return v


def _box_blur(img, r):
    """Fast separable box blur on an (H, W, C) image via cumulative sums."""
    out = img
    for axis in (0, 1):
        pad = [(0, 0)] * out.ndim
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(out, pad, mode="edge"), axis=axis)
        hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
        lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
        out = (hi - lo) / (2 * r + 1)
    return out


def post(col, depth, cam):
    """Depth of field, bloom and vignette for the promo-art look."""
    if P.get("dof"):
        b = _box_blur(_box_blur(col, 2), 2)
        d = np.where(np.isfinite(depth), depth, 1e3)
        coc = np.clip((np.abs(d - cam.focus) / (cam.focus * 0.9)) ** 1.3, 0, 1)[..., None] * P["dof"]
        col = col * (1 - coc) + b * coc
    if P.get("bloom"):
        br = np.clip(col - 0.78, 0, None)
        col = col + _box_blur(_box_blur(br, 6), 6) * P["bloom"] * 2.2
    if P.get("vignette"):
        yy, xx = np.mgrid[0:RH, 0:RW]
        r2 = ((xx / RW - 0.5) * 1.6) ** 2 + ((yy / RH - 0.5) * 1.1) ** 2
        col = col * (1 - P["vignette"] * np.clip(r2, 0, 1))[..., None]
    return col


def draw_flowers(col, depth, cam, flowers):
    """Tiny billboard flowers (stem + petals) with depth test. col: (RH*RW, 3) flat."""
    img = col.reshape(RH, RW, 3)
    for p, c in flowers:
        base = cam.project(p)
        if base is None:
            continue
        x, y, dist = base
        if dist > 40:
            continue
        s = 0.42 / (dist * cam.th) * RH / 2
        if s < 1.2:
            continue
        xi, yi = int(x), int(y)
        stem_h, head = max(1, int(s * 1.3)), max(1, int(s * 0.9))
        dz = depth.reshape(RH, RW)
        if not (0 <= xi < RW and 0 <= yi < RH) or dz[min(RH - 1, yi), xi] < dist - 0.6 \
                or dz[max(0, yi - stem_h - head // 2), xi] < dist - 0.25:
            continue
        w = max(1, int(s * 0.18))
        img[max(0, yi - stem_h):yi, max(0, xi - w // 2):xi + w // 2 + 1] = (0.22, 0.6, 0.18)
        y0 = yi - stem_h - head
        img[max(0, y0):max(0, y0 + head), max(0, xi - head // 2):xi + head // 2 + 1] = c
        cc = max(1, head // 3)
        img[max(0, y0 + head // 2 - cc // 2):max(0, y0 + head // 2 + cc // 2 + 1), max(0, xi - cc // 2):xi + cc // 2 + 1] = (1.0, 0.9, 0.3)


def render(grid, cam, time, boxes=(), blobs=(), flowers=()):
    """blobs: list of (x, z, radius) soft contact shadows under characters."""
    D = cam.rays()
    o = cam.o
    hid, ht, hax = raycast(grid, o, D)
    col = sky(D, o, time)
    depth = np.full(D.shape[0], np.inf)
    normals = np.zeros((D.shape[0], 3))
    m = hid > 0
    if m.any():
        Dm = D[m]
        t = ht[m]
        Pt = o[None] + Dm * t[:, None]
        ax = hax[m]
        k = np.arange(len(ax))
        st = np.sign(Dm[k, ax])
        fx, fy, fz = Pt[:, 0] % 1, Pt[:, 1] % 1, Pt[:, 2] % 1
        u = np.where(ax == 0, fz, fx)
        v = np.where(ax == 1, fz, 1 - fy)
        ids = hid[m].astype(np.int64)
        anim = (ids == WATER) | (ids == PORTAL)
        v = np.where(anim, (v + time * 0.35) % 1, v)
        face = np.where(ax == 1, np.where(st < 0, 0, 2), 1)
        R = TEX.shape[2]
        tu = np.clip((u * R).astype(np.int64), 0, R - 1)
        tv = np.clip((v * R).astype(np.int64), 0, R - 1)
        c = TEX[ids, face, tv, tu].astype(np.float64)
        n = np.zeros((len(ax), 3))
        n[k, ax] = -st
        shadow = None
        if P["shadows"]:
            L = np.array(P["sun"], np.float64)
            L /= np.linalg.norm(L)
            facing = (n @ L) > 0
            shadow = np.zeros(len(ax))
            if facing.any():
                O2 = Pt[facing] + n[facing] * 0.003
                sid, _, _ = raycast(grid, O2, np.broadcast_to(L, (facing.sum(), 3)).copy(), maxt=40, steps=90)
                shadow[facing] = (sid == 0).astype(float)
            for bx, bz, br in blobs:
                d2 = (Pt[:, 0] - bx) ** 2 + (Pt[:, 2] - bz) ** 2
                near = (n[:, 1] > 0) & (d2 < br * br) & (np.abs(Pt[:, 1] - 12) < 0.05)
                shadow[near] *= np.clip(np.sqrt(d2[near]) / br, 0.25, 1)
        if shadow is not None and P.get("soft_shadow"):
            full = np.ones(D.shape[0])
            full[m] = shadow
            tfull = np.full(D.shape[0], 1e4)
            tfull[m] = t
            full = _depth_blur(full.reshape(RH, RW), tfull.reshape(RH, RW), P["soft_shadow"]).ravel()
            shadow = full[m]
        lit = light_for_normal(n, shadow)
        if P["shading"] == "mc":
            for bx, bz, br in blobs:
                d2 = (Pt[:, 0] - bx) ** 2 + (Pt[:, 2] - bz) ** 2
                near = (n[:, 1] > 0) & (d2 < br * br)
                lit[near] *= np.clip(np.sqrt(d2[near]) / br, 0.55, 1)[:, None]
        if P["ao"] > 0:
            lit *= ambient_occlusion(grid, Pt, ax, n)[:, None]
        c = c * lit
        if P.get("spec"):
            # glossy highlight (Blinn-Phong) for the plastic look
            L = np.array(P["sun"], np.float64)
            L /= np.linalg.norm(L)
            hv = L[None] - Dm
            hv /= np.linalg.norm(hv, axis=1, keepdims=True)
            sp = np.clip((n * hv).sum(1), 0, 1) ** 30 * P["spec"]
            if shadow is not None:
                sp = sp * shadow
            c = c + sp[:, None]
        pm = ids == PORTAL
        c[pm] = np.clip(c[pm] * 1.3, 0, 1)
        f0, f1 = P["fog"]
        f = np.clip((t - f0) / (f1 - f0), 0, 1)[:, None]
        col[m] = c * (1 - f) + col[m] * f
        depth[m] = t
        normals[m] = n
    for bx in boxes:
        bx.draw(cam, D, col, depth, normals)
    if flowers:
        draw_flowers(col, depth, cam, flowers)
    col = grade(col).reshape(RH, RW, 3)
    depth = depth.reshape(RH, RW)
    col = post(col, depth, cam)
    if P["outline"]:
        col = outline(col, depth, normals.reshape(RH, RW, 3))
    return col, depth


def outline(col, depth, nrm):
    d = np.where(np.isfinite(depth), depth, 1e4)
    e = np.zeros(depth.shape, bool)
    for sy, sx in ((0, 1), (1, 0)):
        d2 = np.roll(d, (-sy, -sx), (0, 1))
        n2 = np.roll(nrm, (-sy, -sx), (0, 1))
        both_sky = (d >= 1e4) & (d2 >= 1e4)
        edge = ((np.abs(d - d2) > 0.06 * np.minimum(d, d2)) | ((nrm * n2).sum(-1) < 0.5)) & ~both_sky
        e |= edge
    e[-1, :] = e[:, -1] = False
    col = col.copy()
    col[e] *= 0.28
    return col


# ================================================================== boxes
def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array(((c, 0, s), (0, 1, 0), (-s, 0, c)))


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array(((1, 0, 0), (0, c, -s), (0, s, c)))


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array(((c, -s, 0), (s, c, 0), (0, 0, 1)))


class Box:
    """Oriented textured box. tex: 6 arrays for faces +x,-x,+y,-y,+z,-z."""

    def __init__(self, c, h, R, tex, tint=1.0):
        self.c = np.asarray(c, np.float64)
        self.h = np.asarray(h, np.float64)
        self.R = R
        self.tex = tex
        self.tint = tint

    def _screen_sel(self, cam):
        xs, ys = [], []
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    pr = cam.project(self.c + self.R @ (self.h * (sx, sy, sz)))
                    if pr is None:
                        return None
                    xs.append(pr[0])
                    ys.append(pr[1])
        x0, x1 = max(0, int(min(xs)) - 1), min(RW, int(max(xs)) + 2)
        y0, y1 = max(0, int(min(ys)) - 1), min(RH, int(max(ys)) + 2)
        if x0 >= x1 or y0 >= y1:
            return np.zeros(0, np.int64)
        return (np.arange(y0, y1)[:, None] * RW + np.arange(x0, x1)[None, :]).ravel()

    def draw(self, cam, D, col, depth, normals):
        sel = self._screen_sel(cam)
        if sel is None:
            sel = np.arange(D.shape[0])
        if sel.size == 0:
            return
        ol = self.R.T @ (cam.o - self.c)
        dl = D[sel] @ self.R
        dl[np.abs(dl) < 1e-9] = 1e-9
        t1 = (-self.h - ol) / dl
        t2 = (self.h - ol) / dl
        tmin = np.minimum(t1, t2)
        tmax = np.maximum(t1, t2)
        tn = tmin.max(1)
        tf = tmax.min(1)
        ax = tmin.argmax(1)
        hit = (tn < tf) & (tn > 0.02) & (tn < depth[sel])
        if not hit.any():
            return
        s = sel[hit]
        tn, ax, dl = tn[hit], ax[hit], dl[hit]
        k = np.arange(len(ax))
        Pl = ol[None] + dl * tn[:, None]
        sgn = -np.sign(dl[k, ax])
        q = np.clip((Pl + self.h) / (2 * self.h), 0, 0.9999)
        faces = ax * 2 + (sgn < 0)
        out = np.zeros((len(ax), 3))
        for fi in range(6):
            fm = faces == fi
            if not fm.any():
                continue
            tx = self.tex[fi]
            th, tw = tx.shape[:2]
            a = fi // 2
            if a == 0:
                u, v = q[fm, 2], 1 - q[fm, 1]
                if fi == 0:
                    u = 1 - u
            elif a == 1:
                u, v = q[fm, 0], q[fm, 2]
            else:
                u, v = q[fm, 0], 1 - q[fm, 1]
                if fi == 4:
                    u = 1 - u
            out[fm] = tx[np.clip((v * th).astype(int), 0, th - 1), np.clip((u * tw).astype(int), 0, tw - 1)]
        nl = np.zeros((len(ax), 3))
        nl[k, ax] = sgn
        nw = nl @ self.R.T
        out = out * light_for_normal(nw) * self.tint
        col[s] = np.clip(out, 0, 1.2)
        depth[s] = tn
        normals[s] = nw


def solid(col, w, h, seed=0, amt=0.08):
    r = _rng(seed)
    return np.clip(np.array(col, np.float32)[None, None, :] * (1 - amt / 2 + amt * r.random((h, w, 1))), 0, 1)


def tex6(front, back, side, top, bottom):
    return [side, side, top, bottom, front, back]


configure(pack="faithful")
