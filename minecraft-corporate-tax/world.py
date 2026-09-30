"""Corporate campus world (Blockworks Inc.) and blocky characters."""
import math
import numpy as np
from engine import *  # noqa: F401,F403
from engine import GX, GY, GZ, Box, rot_x, rot_y, solid, tex6

PLAZA = (94.0, 96.0)


def height_at(x, z):
    h = 12 + 2.6 * math.sin(x * 0.11) + 2.2 * math.cos(z * 0.093) + 1.6 * math.sin((x + z) * 0.052)
    d = math.hypot(x - PLAZA[0], z - PLAZA[1])
    w = min(1.0, max(0.0, (d - 32) / 12))
    w = w * w * (3 - 2 * w)
    return int(round(12 * (1 - w) + h * w))


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


# ---- asset positions
VAULT = [(x, y, z) for y in (13, 12) for z in range(97, 102) for x in range(82, 87)]   # 50 diamond blocks, top layer first
IRON_PILE = [(x, y, z) for y in (13, 12) for z in range(87, 90) for x in range(87, 90)]  # 18 iron blocks
CHIMNEY = [(114, y, 94) for y in range(24, 18, -1)]
FACTORY_ROOF_SALE = [(x, 18, z) for x in range(107, 112) for z in range(93, 96)]
FURNACES = [(106, 12, z) for z in (93, 95, 97, 99)]
STALL = (78.5, 12.0, 90.5)
TAXDOOR = (76.5, 12.0, 103.5)


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
    rng = np.random.default_rng(42)
    placed = 0
    while placed < 170:
        x, z = rng.integers(4, GX - 4, 2)
        if math.hypot(x - PLAZA[0], z - PLAZA[1]) < 38:
            continue
        tree(g, int(x), int(H[x, z]), int(z), int(rng.integers(4, 6)))
        placed += 1
    # paths
    box_fill(g, 80, 106, 11, 11, 92, 94, PATH)
    box_fill(g, 94, 96, 11, 11, 80, 104, PATH)
    # HQ tower: quartz with glass bands
    x0, x1, z0, z1 = 96, 104, 104, 110
    for y in range(12, 28):
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if x in (x0, x1) or z in (z0, z1):
                    corner = x in (x0, x1) and z in (z0, z1)
                    win = (y % 3 != 0) and not corner and y > 12
                    g[x, y, z] = GLASS if win else QUARTZ
    box_fill(g, x0, x1, 28, 28, z0, z1, QUARTZ)
    g[99:102, 12:15, z0] = AIR
    g[99:102, 15, z0] = QUARTZ
    for x in range(x0, x1 + 1, 2):
        g[x, 29, z0] = GOLD
    # factory
    fx0, fx1, fz0, fz1 = 106, 116, 92, 100
    box_fill(g, fx0, fx1, 11, 11, fz0, fz1, SMOOTH)
    for x in range(fx0, fx1 + 1):
        for z in range(fz0, fz1 + 1):
            if x in (fx0, fx1) or z in (fz0, fz1):
                g[x, 12:18, z] = BRICKS
    box_fill(g, fx0, fx1, 18, 18, fz0, fz1, SMOOTH)
    for p in FURNACES:
        g[p] = FURNACE
    g[106, 14:16, 94:99] = GLASS
    for p in CHIMNEY:
        g[p] = COBBLE
    # diamond vault platform + blocks
    box_fill(g, 81, 87, 11, 11, 96, 102, QUARTZ)
    for p in VAULT:
        g[p] = DIAMOND
    box_fill(g, 86, 90, 11, 11, 86, 90, SMOOTH)
    for p in IRON_PILE:
        g[p] = IRON
    # market stall
    for px, pz in ((76, 89), (81, 89), (76, 92), (81, 92)):
        g[px, 12:15, pz] = LOG
    for x in range(76, 82):
        for z in range(89, 93):
            g[x, 15, z] = REDWOOL if (x + z) % 2 else WHITEWOOL
    g[77:81, 12, 89] = PLANKS
    g[79, 13, 89] = CHEST
    # tax office
    tx0, tx1, tz0, tz1 = 72, 80, 104, 110
    box_fill(g, tx0, tx1, 11, 11, tz0, tz1, STONEBRICK)
    for x in range(tx0, tx1 + 1):
        for z in range(tz0, tz1 + 1):
            if x in (tx0, tx1) or z in (tz0, tz1):
                g[x, 12:17, z] = STONEBRICK
    box_fill(g, tx0, tx1, 17, 17, tz0, tz1, STONEBRICK)
    for x in range(tx0, tx1 + 1, 2):
        g[x, 18, tz0] = GOLD
    g[76, 12:14, tz0] = AIR
    return g


# ------------------------------------------------------------------ characters
PX = 1.8 / 32
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
    elif kind == "ceo":
        skin, hair, shirt, pants, shoe = (0.82, 0.63, 0.5), (0.2, 0.14, 0.1), (0.14, 0.2, 0.42), (0.12, 0.16, 0.34), (0.08, 0.08, 0.08)
        hf = head_front(skin, hair, eyes=(0.2, 0.35, 0.6))
        tie = "blue"
    elif kind == "worker":
        skin, hair, shirt, pants, shoe = (0.7, 0.5, 0.38), (0.15, 0.1, 0.06), (0.95, 0.6, 0.1), (0.25, 0.3, 0.5), (0.3, 0.2, 0.1)
        hf = head_front(skin, hair)
        tie = None
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
        bf[1:7, 3:5] = (0.15, 0.4, 0.85) if tie == "blue" else (0.75, 0.1, 0.1)
        bf[0, 3:5] = (0.95, 0.95, 0.95)
    body = tex6(bf, solid(shirt, 8, 12, 7), solid(shirt, 4, 12, 8), solid(shirt, 8, 4, 9), solid(shirt, 8, 4, 9))
    arm_side = solid(skin, 4, 12, 10)
    sleeve = 4 if kind in ("steve", "worker") else 10
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
