"""World generation, buildings and blocky characters."""
import math
import numpy as np
from engine import *  # noqa: F401,F403
from engine import GX, GY, GZ, Box, rot_x, rot_y, solid, tex6

PLAZA = (94.0, 96.0)

# ------------------------------------------------------------------ terrain

def height_at(x, z):
    h = 12 + 2.6 * math.sin(x * 0.11) + 2.2 * math.cos(z * 0.093) + 1.6 * math.sin((x + z) * 0.052)
    d = math.hypot(x - PLAZA[0], z - PLAZA[1])
    w = min(1.0, max(0.0, (d - 30) / 12))
    w = w * w * (3 - 2 * w)
    h = 12 * (1 - w) + h * w
    ld = math.hypot(x - 140, z - 58)
    if ld < 20:
        k = 1 - ld / 20
        h = h * (1 - k) + 8 * k
    return int(round(h))


def box_fill(g, x0, x1, y0, y1, z0, z1, b):
    g[x0:x1 + 1, y0:y1 + 1, z0:z1 + 1] = b


def tree(g, x, y, z, hgt):
    for yy in range(y + hgt - 2, y + hgt):
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                if abs(dx) == 2 and abs(dz) == 2 and (x * 7 + z * 3 + yy) % 3 == 0:
                    continue
                g[x + dx, yy, z + dz] = LEAVES
    for yy in range(y + hgt, y + hgt + 2):
        for dx in range(-1, 2):
            for dz in range(-1, 2):
                if yy == y + hgt + 1 and abs(dx) + abs(dz) == 2:
                    continue
                g[x + dx, yy, z + dz] = LEAVES
    g[x, y:y + hgt, z] = LOG


def build_base():
    g = np.zeros((GX, GY, GZ), np.uint8)
    H = np.zeros((GX, GZ), np.int32)
    for x in range(GX):
        for z in range(GZ):
            h = height_at(x, z)
            H[x, z] = h
            g[x, :max(h - 4, 0), z] = STONE
            g[x, max(h - 4, 0):h - 1, z] = DIRT
            g[x, h - 1, z] = GRASS
            if h <= 11 and math.hypot(x - 140, z - 58) < 22:
                g[x, h - 1, z] = SAND if h >= 10 else DIRT
                if h < 11:
                    g[x, h:11, z] = WATER
    rng = np.random.default_rng(42)
    placed = 0
    while placed < 170:
        x, z = rng.integers(4, GX - 4, 2)
        if math.hypot(x - PLAZA[0], z - PLAZA[1]) < 36 or math.hypot(x - 140, z - 58) < 24:
            continue
        tree(g, int(x), int(H[x, z]), int(z), int(rng.integers(4, 6)))
        placed += 1

    # Steve's house: x 92..98, z 96..102
    steve_house(g)
    # tax office: x 108..116, z 82..90
    box_fill(g, 108, 116, 11, 11, 82, 90, STONEBRICK)
    for x in range(108, 117):
        for z in range(82, 91):
            if x in (108, 116) or z in (82, 90):
                g[x, 12:18, z] = STONEBRICK
    box_fill(g, 108, 116, 18, 18, 82, 90, STONEBRICK)
    for x in range(108, 117):
        for z in range(82, 91):
            if x in (108, 116) or z in (82, 90):
                g[x, 19, z] = GOLD if (x + z) % 2 == 0 else AIR
    g[108, 12:14, 86] = AIR  # door
    g[108, 14:16, 83:85] = AIR
    g[108, 14:16, 88:90] = AIR
    # nether portal: frame x 68..71 at z 96, interior x 69..70 y 12..14
    for x in range(68, 72):
        g[x, 11, 96] = OBSIDIAN
        g[x, 15, 96] = OBSIDIAN
    g[68, 12:15, 96] = OBSIDIAN
    g[71, 12:15, 96] = OBSIDIAN
    g[69:71, 12:15, 96] = PORTAL
    return g


HOUSE_ROOF_ORDER = []


def steve_house(g):
    x0, x1, z0, z1 = 92, 98, 96, 102
    box_fill(g, x0, x1, 11, 11, z0, z1, COBBLE)
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if x in (x0, x1) or z in (z0, z1):
                corner = x in (x0, x1) and z in (z0, z1)
                g[x, 12:16, z] = LOG if corner else PLANKS
    g[95, 12:14, 96] = AIR  # door
    g[x0, 13:15, 99] = AIR
    g[x1, 13:15, 99] = AIR
    g[93, 13:15, 96] = AIR
    g[97, 13:15, 96] = AIR
    for i, y in enumerate(range(16, 20)):
        box_fill(g, x0 - 1 + i, x1 + 1 - i, y, y, z0 - 1 + i, z1 + 1 - i, ROOF)
    g[93, 12, 94] = CHEST


# blocks that Steve "sells" (top layers of roof, top first)
def roof_sale_blocks():
    out = []
    for y in (19, 18):
        i = y - 16
        xs = range(91 + i, 100 - i)
        zs = range(95 + i, 104 - i)
        for z in zs:
            for x in xs:
                out.append((x, y, z))
    return out[:18]


def small_house(x0, z0, wall, roof, w=6):
    """Blocks of a small house in build order (bottom-up)."""
    blocks = []
    x1, z1 = x0 + w - 1, z0 + w - 1
    for y in range(12, 15):
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if x in (x0, x1) or z in (z0, z1):
                    corner = x in (x0, x1) and z in (z0, z1)
                    if y < 14 and z == z0 and x == x0 + 2:
                        continue
                    if y == 13 and x == x1 and z == z0 + 2:
                        continue
                    blocks.append((x, y, z, LOG if corner else wall))
    for i, y in enumerate(range(15, 18)):
        for x in range(x0 - 1 + i, x1 + 2 - i):
            for z in range(z0 - 1 + i, z1 + 2 - i):
                blocks.append((x, y, z, roof))
    return blocks


VILLAGE = (small_house(74, 84, PLANKS, ROOF) + small_house(104, 106, BRICKS, ROOF)
           + small_house(84, 74, COBBLE, ROOF) + small_house(80, 106, PLANKS, ROOF, 5))

# gold tower (Steve's paper fortune) + TNT
TOWER = [(x, y, z, GOLD) for y in range(12, 20) for x in range(84, 87) for z in range(88, 91)]
TNT_POS = (87, 12, 89)
BLAST_C = np.array((85.5, 14.5, 89.5))
BLAST_R = 4.8


def blast_mask():
    xs, ys, zs = np.meshgrid(np.arange(GX), np.arange(GY), np.arange(GZ), indexing="ij")
    return ((xs + 0.5 - BLAST_C[0]) ** 2 + (ys + 0.5 - BLAST_C[1]) ** 2
            + (zs + 0.5 - BLAST_C[2]) ** 2) < BLAST_R ** 2


# ------------------------------------------------------------------ characters
PX = 1.8 / 32  # one skin pixel in blocks

SKIN_TONE = (0.80, 0.60, 0.46)


def head_front(skin, hair, eyes=(0.29, 0.22, 0.62), glasses=False, beard=None):
    f = solid(skin, 8, 8, 1, 0.06)
    f[0:2] = hair
    f[2, 0] = f[2, 7] = hair
    f[4, 1] = f[4, 6] = (0.95, 0.95, 0.95)
    f[4, 2] = f[4, 5] = eyes
    f[5, 3:5] = np.array(skin) * 0.8
    f[6, 2:6] = (0.45, 0.25, 0.2)
    if glasses:
        f[4, 1:7] = (0.05, 0.05, 0.08)
    if beard is not None:
        f[6:8, 1:7] = beard
        f[6, 3:5] = (0.45, 0.25, 0.2)
    return f


def skin_set(kind):
    if kind == "steve":
        skin, hair, shirt, pants, shoe = SKIN_TONE, (0.29, 0.19, 0.11), (0.0, 0.66, 0.68), (0.26, 0.22, 0.62), (0.38, 0.38, 0.40)
        hf = head_front(skin, hair)
        tie = None
    elif kind == "taxman":
        skin, hair, shirt, pants, shoe = (0.86, 0.68, 0.55), (0.55, 0.55, 0.55), (0.12, 0.12, 0.15), (0.14, 0.14, 0.17), (0.05, 0.05, 0.05)
        hf = head_front(skin, hair, eyes=(0.15, 0.15, 0.15))
        tie = True
    elif kind == "rich":
        skin, hair, shirt, pants, shoe = (0.78, 0.58, 0.44), (0.9, 0.8, 0.3), (0.95, 0.78, 0.18), (0.90, 0.72, 0.15), (0.2, 0.2, 0.2)
        hf = head_front(skin, hair, glasses=True)
        tie = None
    else:
        raise ValueError(kind)
    head_side = solid(skin, 8, 8, 2, 0.06)
    head_side[0:3] = hair
    head_back = solid(hair, 8, 8, 3)
    head_top = solid(hair, 8, 8, 4)
    head_bot = solid(skin, 8, 8, 5)
    head = tex6(hf, head_back, head_side, head_top, head_bot)
    bf = solid(shirt, 8, 12, 6)
    if tie:
        bf[0:5, 3:5] = (0.95, 0.95, 0.95)
        bf[1:7, 3:5] = (0.75, 0.1, 0.1)
        bf[0, 3:5] = (0.95, 0.95, 0.95)
    body = tex6(bf, solid(shirt, 8, 12, 7), solid(shirt, 4, 12, 8), solid(shirt, 8, 4, 9), solid(shirt, 8, 4, 9))
    arm_side = solid(skin, 4, 12, 10)
    sleeve = 4 if kind == "steve" else 10
    arm_side[:sleeve] = solid(shirt, 4, sleeve, 11)
    arm = tex6(arm_side, arm_side, arm_side, solid(shirt, 4, 4, 12), solid(skin, 4, 4, 12))
    leg_side = solid(pants, 4, 12, 13)
    leg_side[10:] = shoe
    leg = tex6(leg_side, leg_side, leg_side, solid(pants, 4, 4, 14), solid(shoe, 4, 4, 14))
    return dict(head=head, body=body, arm=arm, leg=leg, kind=kind)


def villager_set(robe):
    skin = (0.74, 0.55, 0.42)
    hf = solid(skin, 8, 10, 20, 0.05)
    hf[0:2] = (0.25, 0.2, 0.15)
    hf[4, 1] = hf[4, 6] = (0.95, 0.95, 0.95)
    hf[4, 2] = hf[4, 5] = (0.1, 0.5, 0.2)
    hf[3, 1:7] = (0.3, 0.22, 0.15)
    hs = solid(skin, 8, 10, 21)
    head = tex6(hf, hs, hs, solid(skin, 8, 8, 22), solid(skin, 8, 8, 22))
    rf = solid(robe, 8, 12, 23)
    body = tex6(rf, solid(robe, 8, 12, 24), solid(robe, 6, 12, 25), solid(robe, 8, 6, 26), solid(robe, 8, 6, 26))
    ls = solid(robe, 6, 12, 27)
    ls[10:] = np.array(robe) * 0.6
    leg = tex6(ls, ls, ls, solid(robe, 6, 6, 28), solid(robe, 6, 6, 28))
    arms = tex6(solid(robe, 8, 4, 29), solid(robe, 8, 4, 29), solid(robe, 4, 8, 29), solid(robe, 8, 4, 29), solid(robe, 8, 4, 29))
    nose = tex6(solid(skin, 2, 4, 30), solid(skin, 2, 4, 30), solid(skin, 2, 4, 30), solid(skin, 2, 2, 30), solid(skin, 2, 2, 30))
    return dict(head=head, body=body, leg=leg, arms=arms, nose=nose, kind="villager")


def _part(pos, Ry, local_c, half, tex, Rp=None, tint=1.0, s=1.0):
    R = Ry if Rp is None else Ry @ Rp
    return Box(np.asarray(pos) + Ry @ (np.asarray(local_c, float) * PX * s), np.asarray(half, float) * PX * s, R, tex, tint)


def _limb(pos, Ry, pivot, half, tex, ang, tint, s, roll=0.0):
    Rl = rot_x(ang)
    if roll:
        from engine import rot_z
        Rl = rot_z(roll) @ Rl
    R = Ry @ Rl
    c = np.asarray(pos) + Ry @ (np.asarray(pivot, float) * PX * s) + R @ (np.array((0, -half[1], 0)) * PX * s)
    return Box(c, np.asarray(half, float) * PX * s, R, tex, tint)


def player(sk, pos, yaw, walk=0.0, arm_r=None, arm_l=None, head_yaw=0.0, head_pitch=0.0, tint=1.0, s=1.0, hat=False, crown=False):
    """walk: phase in radians (0 = standing). arm_* override arm pitch (negative = raise forward)."""
    Ry = rot_y(yaw)
    sw = 0.7 * math.sin(walk) if walk else 0.0
    boxes = [
        _limb(pos, Ry, (-2, 12, 0), (2, 6, 2), sk["leg"], sw, tint, s),
        _limb(pos, Ry, (2, 12, 0), (2, 6, 2), sk["leg"], -sw, tint, s),
        _part(pos, Ry, (0, 18, 0), (4, 6, 2), sk["body"], tint=tint, s=s),
        _limb(pos, Ry, (-6, 24, 0), (2, 6, 2), sk["arm"], arm_r if arm_r is not None else -sw, tint, s),
        _limb(pos, Ry, (6, 24, 0), (2, 6, 2), sk["arm"], arm_l if arm_l is not None else sw, tint, s),
    ]
    Rh = rot_y(head_yaw) @ rot_x(head_pitch)
    boxes.append(Box(np.asarray(pos) + Ry @ (np.array((0, 24, 0)) * PX * s) + (Ry @ Rh) @ (np.array((0, 4, 0)) * PX * s),
                     np.array((4, 4, 4)) * PX * s, Ry @ Rh, sk["head"], tint))
    Rhh = Ry @ Rh
    if hat:
        black = solid((0.06, 0.06, 0.07), 8, 8, 40)
        t6 = [black] * 6
        base = np.asarray(pos) + Ry @ (np.array((0, 24, 0)) * PX * s)
        boxes.append(Box(base + Rhh @ (np.array((0, 8.5, 0)) * PX * s), np.array((5.5, 0.5, 5.5)) * PX * s, Rhh, t6, tint))
        band = solid((0.06, 0.06, 0.07), 8, 8, 41)
        band[5:7] = (0.6, 0.1, 0.1)
        boxes.append(Box(base + Rhh @ (np.array((0, 12, 0)) * PX * s), np.array((3.6, 3.5, 3.6)) * PX * s, Rhh,
                         [band, band, black, black, band, band], tint))
    if crown:
        gold = solid((0.98, 0.82, 0.24), 8, 3, 42)
        gold[1, 1] = gold[1, 5] = (0.9, 0.1, 0.2)
        base = np.asarray(pos) + Ry @ (np.array((0, 24, 0)) * PX * s)
        boxes.append(Box(base + Rhh @ (np.array((0, 9.5, 0)) * PX * s), np.array((4.2, 1.5, 4.2)) * PX * s, Rhh, [gold] * 6, tint))
    return boxes


def villager(sk, pos, yaw, walk=0.0, head_yaw=0.0, tint=1.0, nod=0.0):
    Ry = rot_y(yaw)
    sw = 0.5 * math.sin(walk) if walk else 0.0
    boxes = [
        _limb(pos, Ry, (-2, 12, 0), (2, 6, 2), sk["leg"], sw, tint, 1.0),
        _limb(pos, Ry, (2, 12, 0), (2, 6, 2), sk["leg"], -sw, tint, 1.0),
        _part(pos, Ry, (0, 18, 0), (4, 6, 3), sk["body"], tint=tint),
        _part(pos, Ry, (0, 19, 3.5), (4, 2, 2), sk["arms"], tint=tint),
    ]
    Rh = Ry @ rot_y(head_yaw) @ rot_x(nod)
    base = np.asarray(pos) + Ry @ (np.array((0, 24, 0)) * PX)
    boxes.append(Box(base + Rh @ (np.array((0, 5, 0)) * PX), np.array((4, 5, 4)) * PX, Rh, sk["head"], tint))
    boxes.append(Box(base + Rh @ (np.array((0, 3, 5)) * PX), np.array((1, 2, 1)) * PX, Rh, sk["nose"], tint))
    return boxes
