"""Tiny numpy voxel ray-caster that renders a Minecraft-looking world.

Blocks are ray-cast with a vectorised DDA over a 3D grid of block ids.
Characters are oriented boxes (head / body / arms / legs) intersected
analytically on top of the voxel depth buffer.
"""
import math
import numpy as np

RW, RH = 640, 360          # internal render resolution (upscaled 3x later)
GX, GY, GZ = 192, 40, 192  # world size
FOG0, FOG1 = 55.0, 95.0
MAXT = 95.0

# ---------------------------------------------------------------- block ids
AIR, GRASS, DIRT, STONE, COBBLE, LOG, PLANKS, LEAVES, GOLD, EMERALD, DIAMOND, \
    OBSIDIAN, PORTAL, WATER, STONEBRICK, TNT, SAND, CHEST, ROOF, BRICKS, \
    TNT_LIT, WHITEWOOL = range(22)
NB = 22


def _rng(seed):
    return np.random.default_rng(seed)


def _speckle(col, amt, seed, levels=4):
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


def make_textures():
    T = np.zeros((NB, 3, 16, 16, 3), np.float32)  # [block, top/side/bottom]

    def all3(b, tex):
        T[b, 0] = T[b, 1] = T[b, 2] = tex

    dirt = _speckle((0.55, 0.39, 0.27), 0.45, 2)
    r = _rng(3)
    dirt[r.random((16, 16)) < 0.08] *= 0.7
    all3(DIRT, dirt)

    grass_top = _speckle((0.37, 0.64, 0.24), 0.35, 1)
    side = dirt.copy()
    r = _rng(4)
    gs = _speckle((0.37, 0.64, 0.24), 0.3, 5)
    for x in range(16):
        k = 3 + int(r.integers(0, 3))
        side[:k, x] = gs[:k, x]
    T[GRASS, 0], T[GRASS, 1], T[GRASS, 2] = grass_top, side, dirt

    all3(STONE, _speckle((0.5, 0.5, 0.5), 0.3, 6))

    cob = _speckle((0.52, 0.52, 0.52), 0.35, 7)
    cob[_voronoi_lines(8)] *= 0.55
    all3(COBBLE, cob)

    # log
    r = _rng(9)
    bark = np.zeros((16, 16, 3), np.float32)
    colv = r.random(16)
    for x in range(16):
        c = 0.75 + 0.35 * colv[x]
        bark[:, x] = np.array((0.40, 0.30, 0.18)) * c
    bark *= (0.85 + 0.15 * r.random((16, 16, 1)))
    yy, xx = np.mgrid[0:16, 0:16] + 0.5
    d = np.maximum(abs(xx - 8), abs(yy - 8))
    rings = np.where((np.floor(d) % 2) == 0, 1.0, 0.85)[..., None] * np.array((0.70, 0.56, 0.34))
    rings[d > 6.5] = bark[d > 6.5]
    T[LOG, 0], T[LOG, 1], T[LOG, 2] = rings, bark, rings

    def planks(col, seed):
        p = _speckle(col, 0.18, seed)
        yy, xx = np.mgrid[0:16, 0:16]
        p[yy % 4 == 3] *= 0.65
        offs = [3, 11, 6, 14]
        for band in range(4):
            p[band * 4:band * 4 + 3, offs[band]] *= 0.72
        return p
    all3(PLANKS, planks((0.70, 0.55, 0.33), 10))
    all3(ROOF, planks((0.42, 0.30, 0.18), 11))

    lv = _speckle((0.22, 0.50, 0.14), 0.6, 12)
    lv[_rng(13).random((16, 16)) < 0.22] *= 0.45
    all3(LEAVES, lv)

    def metal(col, seed):
        m = _speckle(col, 0.12, seed)
        m[0, :] = m[:, 0] = np.minimum(np.array(col) * 1.2, 1)
        m[15, :] = m[:, 15] = np.array(col) * 0.7
        r = _rng(seed + 1)
        for _ in range(6):
            y, x = r.integers(2, 13, 2)
            m[y, x:x + 3] = np.minimum(np.array(col) * 1.25, 1)
        return m
    all3(GOLD, metal((0.98, 0.82, 0.24), 14))
    all3(DIAMOND, metal((0.40, 0.88, 0.86), 16))
    em = metal((0.16, 0.78, 0.36), 18)
    yy, xx = np.mgrid[0:16, 0:16]
    em[(abs(xx - 7.5) + abs(yy - 7.5)) < 4] *= 1.15
    all3(EMERALD, np.clip(em, 0, 1))

    ob = _speckle((0.09, 0.06, 0.15), 0.6, 20)
    ob[_rng(21).random((16, 16)) < 0.1] = (0.28, 0.16, 0.42)
    all3(OBSIDIAN, ob)
    all3(PORTAL, _speckle((0.52, 0.12, 0.82), 0.5, 22))
    all3(WATER, _speckle((0.22, 0.38, 0.85), 0.25, 23))

    sb = _speckle((0.48, 0.48, 0.48), 0.2, 24)
    sb[yy % 8 == 7] *= 0.6
    sb[(yy < 8) & (xx == 0)] *= 0.6
    sb[(yy >= 8) & (xx == 8)] *= 0.6
    all3(STONEBRICK, sb)

    br = _speckle((0.62, 0.29, 0.22), 0.25, 25)
    br[yy % 4 == 3] = (0.72, 0.70, 0.66)
    for band in range(4):
        o = 0 if band % 2 == 0 else 4
        br[band * 4:band * 4 + 3, (o + 0) % 16] = (0.72, 0.70, 0.66)
        br[band * 4:band * 4 + 3, (o + 8) % 16] = (0.72, 0.70, 0.66)
    all3(BRICKS, br)

    all3(SAND, _speckle((0.86, 0.81, 0.60), 0.18, 26))
    all3(WHITEWOOL, _speckle((0.93, 0.93, 0.93), 0.1, 27))

    # TNT
    tside = _speckle((0.86, 0.22, 0.15), 0.2, 28)
    tside[5:11] = (0.92, 0.92, 0.9)
    letters = ["###.#..#.###",
               ".#..##.#..#.",
               ".#..#.##..#.",
               ".#..#..#..#."]
    for ry, row in enumerate(letters):
        for rx, ch in enumerate(row):
            if ch == "#":
                tside[6 + ry, 2 + rx] = (0.12, 0.12, 0.12)
    ttop = _speckle((0.75, 0.72, 0.70), 0.2, 29)
    ttop[6:10, 6:10] = (0.3, 0.3, 0.3)
    ttop[7:9, 7:9] = (0.9, 0.3, 0.1)
    T[TNT, 0], T[TNT, 1], T[TNT, 2] = ttop, tside, ttop
    T[TNT_LIT] = np.clip(T[TNT] * 0.4 + 0.65, 0, 1)

    # chest
    cs = planks((0.64, 0.45, 0.20), 30)
    cs[0, :] = cs[15, :] = cs[:, 0] = cs[:, 15] = (0.30, 0.20, 0.08)
    cs[5, :] = (0.30, 0.20, 0.08)
    cs[4:8, 7:9] = (0.75, 0.75, 0.78)
    ct = planks((0.64, 0.45, 0.20), 31)
    ct[0, :] = ct[15, :] = ct[:, 0] = ct[:, 15] = (0.30, 0.20, 0.08)
    T[CHEST, 0], T[CHEST, 1], T[CHEST, 2] = ct, cs, ct
    return T


TEX = make_textures()


# ---------------------------------------------------------------- camera
class Camera:
    def __init__(self, pos, target, fov=70.0):
        self.o = np.array(pos, np.float64)
        f = np.array(target, np.float64) - self.o
        self.f = f / np.linalg.norm(f)
        up = np.array((0.0, 1.0, 0.0))
        r = np.cross(up, self.f)
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.f, self.r)
        self.th = math.tan(math.radians(fov) / 2)
        self.aspect = RW / RH

    def rays(self):
        xs = (np.arange(RW) + 0.5) / RW * 2 - 1
        ys = 1 - (np.arange(RH) + 0.5) / RH * 2
        X, Y = np.meshgrid(xs, ys)
        D = (self.f[None, None, :] + X[..., None] * self.th * self.aspect * self.r
             + Y[..., None] * self.th * self.u)
        D = D.reshape(-1, 3)
        return D / np.linalg.norm(D, axis=1, keepdims=True)

    def project(self, p, W=RW, H=RH):
        """World point -> (sx, sy, depth) in a W x H image, or None if behind."""
        v = np.asarray(p, np.float64) - self.o
        z = v @ self.f
        if z <= 0.05:
            return None
        x = (v @ self.r) / (z * self.th * self.aspect)
        y = (v @ self.u) / (z * self.th)
        return ((x + 1) / 2 * W, (1 - y) / 2 * H, float(np.linalg.norm(v)))


# ---------------------------------------------------------------- ray casting
def raycast(grid, o, D):
    N = D.shape[0]
    hit_id = np.zeros(N, np.uint8)
    hit_t = np.full(N, np.inf)
    hit_ax = np.zeros(N, np.int8)
    Dd = D.copy()
    Dd[np.abs(Dd) < 1e-9] = 1e-9
    inv = 1.0 / Dd
    p = np.tile(np.floor(o).astype(np.int32), (N, 1))
    st = np.where(Dd > 0, 1, -1).astype(np.int32)
    td = np.abs(inv)
    tm = ((p + (st > 0)) - o) * inv
    act = np.arange(N)
    shape = np.array(grid.shape)
    for _ in range(260):
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
        keep = ~(hit | ~inb | (tt > MAXT))
        act, p, tm, td, st = act[keep], p[keep], tm[keep], td[keep], st[keep]
    return hit_id, hit_t, hit_ax


HORIZON = np.array((0.74, 0.85, 1.0))
ZENITH = np.array((0.45, 0.64, 1.0))


def sky(D, o, time, sun_dir):
    y = D[:, 1]
    k = np.clip(y, 0, 1)[:, None] ** 0.55
    col = HORIZON[None] * (1 - k) + ZENITH[None] * k
    # square sun
    L = np.array(sun_dir, np.float64)
    L /= np.linalg.norm(L)
    e1 = np.cross((0, 1, 0), L)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(L, e1)
    dl = D @ L
    with np.errstate(divide="ignore", invalid="ignore"):
        a = (D @ e1) / dl
        b = (D @ e2) / dl
    sun = (dl > 0) & (np.abs(a) < 0.06) & (np.abs(b) < 0.06)
    col[sun] = (1.0, 1.0, 0.88)
    glow = (dl > 0) & ~sun & (np.abs(a) < 0.1) & (np.abs(b) < 0.1)
    col[glow] = col[glow] * 0.5 + np.array((1.0, 0.98, 0.8)) * 0.5
    # blocky clouds
    up = y > 0.02
    tc = (120.0 - o[1]) / y[up]
    cx = np.floor((o[0] + D[up, 0] * tc + time * 1.2) / 12.0)
    cz = np.floor((o[2] + D[up, 2] * tc) / 12.0)
    h = np.modf(np.abs(np.sin(cx * 12.9898 + cz * 78.233) * 43758.5453))[0]
    al = np.where(h < 0.28, 0.9, 0.0) * np.clip(1 - tc / 900.0, 0, 1)
    col[up] = col[up] * (1 - al[:, None]) + al[:, None] * 1.0
    return col


def shade_for_normal(n):
    n2 = n * n
    return 0.62 * n2[..., 0] + 0.82 * n2[..., 2] + np.where(n[..., 1] > 0, 1.0, 0.5) * n2[..., 1]


def render(grid, cam, time, boxes=(), sun_dir=(-0.35, 0.6, 0.72)):
    D = cam.rays()
    o = cam.o
    hid, ht, hax = raycast(grid, o, D)
    col = sky(D, o, time, sun_dir)
    depth = np.full(D.shape[0], np.inf)
    m = hid > 0
    if m.any():
        Dm = D[m]
        t = ht[m]
        P = o[None] + Dm * t[:, None]
        ax = hax[m]
        st = np.sign(Dm[np.arange(len(ax)), ax])
        fx, fy, fz = np.modf(P[:, 0])[0] % 1, np.modf(P[:, 1])[0] % 1, np.modf(P[:, 2])[0] % 1
        u = np.where(ax == 0, fz, fx)
        v = np.where(ax == 1, fz, 1 - fy)
        ids = hid[m].astype(np.int64)
        # water / portal animation: scroll texture
        anim = (ids == WATER) | (ids == PORTAL)
        v = np.where(anim, (v + time * 0.35) % 1, v)
        face = np.where(ax == 1, np.where(st < 0, 0, 2), 1)
        tu = np.clip((u * 16).astype(np.int64), 0, 15)
        tv = np.clip((v * 16).astype(np.int64), 0, 15)
        c = TEX[ids, face, tv, tu]
        pm = ids == PORTAL
        if pm.any():
            w = 0.8 + 0.25 * np.sin(P[pm, 0] * 5 + P[pm, 1] * 7 + time * 4)
            c[pm] = np.clip(c[pm] * w[:, None], 0, 1)
        n = np.zeros((len(ax), 3))
        n[np.arange(len(ax)), ax] = -st
        c = c * shade_for_normal(n)[:, None]
        f = np.clip((t - FOG0) / (FOG1 - FOG0), 0, 1)[:, None]
        col[m] = c * (1 - f) + col[m] * f
        depth[m] = t
    for bx in boxes:
        bx.draw(cam, D, col, depth)
    return col.reshape(RH, RW, 3), depth.reshape(RH, RW)


# ---------------------------------------------------------------- entity boxes
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
    """Oriented textured box. tex: list of 6 arrays for faces +x,-x,+y,-y,+z,-z."""

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
                    p = self.c + self.R @ (self.h * (sx, sy, sz))
                    pr = cam.project(p)
                    if pr is None:
                        return None
                    xs.append(pr[0])
                    ys.append(pr[1])
        x0, x1 = max(0, int(min(xs)) - 1), min(RW, int(max(xs)) + 2)
        y0, y1 = max(0, int(min(ys)) - 1), min(RH, int(max(ys)) + 2)
        if x0 >= x1 or y0 >= y1:
            return np.zeros(0, np.int64)
        return (np.arange(y0, y1)[:, None] * RW + np.arange(x0, x1)[None, :]).ravel()

    def draw(self, cam, D, col, depth):
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
        P = ol[None] + dl * tn[:, None]
        sgn = -np.sign(dl[k, ax])
        q = (P + self.h) / (2 * self.h)  # 0..1 in local box
        q = np.clip(q, 0, 0.9999)
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
        out = out * shade_for_normal(nw)[:, None] * self.tint
        col[s] = np.clip(out, 0, 1)
        depth[s] = tn


def solid(col, w, h, seed=0, amt=0.08):
    r = _rng(seed)
    return np.clip(np.array(col, np.float32)[None, None, :] * (1 - amt / 2 + amt * r.random((h, w, 1))), 0, 1)


def tex6(front, back, side, top, bottom):
    # faces +x,-x,+y,-y,+z(front),-z(back)
    return [side, side, top, bottom, front, back]
