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


# ---- locations
# (name, x0, z0, w, d, wall, roof, label)
BANKS = [("Bank", 82, 78, 6, 5, STONEBRICK, SMOOTH), ("Shop", 91, 78, 6, 5, PLANKS, ROOF), ("Exchange", 100, 78, 6, 5, BRICKS, ROOF)]
SHELLS = [("Shell Co. #1", 110, 90, 5, 5, QUARTZ, SMOOTH), ("Shell Co. #2", 110, 101, 5, 5, BRICKS, ROOF),
          ("Offshore Ltd", 99, 110, 5, 5, PLANKS, ROOF), ("Shell Co. #3", 86, 110, 5, 5, COBBLE, SMOOTH)]
BAKERY = ("Totally Legit Bakery", 112, 78, 6, 5, PLANKS, REDWOOL)
MANSION = (117, 94, 124, 104)       # x0, z0, x1, z1
HIDEOUT = (72, 100, 77, 105)
STASH = [(x, y, z) for y in (12, 13) for x in (79, 80) for z in (101, 102)]


def door_of(b):
    """Point on the street in front of a building (doors face the plaza)."""
    _, x0, z0, w, d = b[:5]
    cx, cz = x0 + w / 2, z0 + d / 2
    if z0 < 90 and x0 < 110:          # row along the north street: door on +z side
        return (cx, 12.0, z0 + d + 0.8)
    if x0 >= 110 and z0 < 110:        # east side: door on -x side
        return (x0 - 0.8, 12.0, cz)
    return (cx, 12.0, z0 - 0.8)       # south side: door on -z side


def top_of(b, dy=1.2):
    _, x0, z0, w, d = b[:5]
    return (x0 + w / 2, 17.0 + dy, z0 + d / 2)


def shop(g, b):
    _, x0, z0, w, d, wall, roof = b[:7]
    x1, z1 = x0 + w - 1, z0 + d - 1
    box_fill(g, x0, x1, 11, 11, z0, z1, SMOOTH)
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if x in (x0, x1) or z in (z0, z1):
                corner = x in (x0, x1) and z in (z0, z1)
                g[x, 12:16, z] = LOG if corner and wall in (PLANKS, COBBLE) else wall
    box_fill(g, x0, x1, 16, 16, z0, z1, roof)
    dx, _, dz = door_of(b)
    ix, iz = int(np.clip(math.floor(dx), x0, x1)), int(np.clip(math.floor(dz), z0, z1))
    g[ix, 12:14, iz] = AIR
    # windows
    if z0 < 90 and x0 < 110:
        g[x0 + 1, 13:15, z1] = GLASS
        g[x1 - 1, 13:15, z1] = GLASS
    else:
        g[x0 + w // 2, 14, z0] = GLASS


def red_flag_blocks(b):
    """Pole + red banner on a roof."""
    _, x0, z0, w, d = b[:5]
    x, z = x0 + w // 2, z0 + d // 2
    return [((x, 17, z), LOG), ((x, 18, z), LOG), ((x, 19, z), LOG), ((x + 1, 19, z), REDWOOL), ((x + 1, 18, z), REDWOOL)]


def mansion_blocks():
    x0, z0, x1, z1 = MANSION
    out = []
    for y in range(12, 19):
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                if not (x in (x0, x1) or z in (z0, z1)):
                    continue
                corner = x in (x0, x1) and z in (z0, z1)
                if y in (13, 14, 16, 17) and not corner and (x + z) % 2 == 0:
                    b = GLASS
                elif corner or y == 18:
                    b = GOLD
                else:
                    b = QUARTZ
                if x == x0 and z in (98, 99, 100) and y < 15:
                    continue
                out.append((x, y, z, b))
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            out.append((x, 19, z, QUARTZ))
    return out


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
        if math.hypot(x - PLAZA[0], z - PLAZA[1]) < 40:
            continue
        tree(g, int(x), int(H[x, z]), int(z), int(rng.integers(4, 6)))
        placed += 1
    box_fill(g, 72, 118, 11, 11, 85, 87, PATH)      # north street
    box_fill(g, 106, 108, 11, 11, 85, 110, PATH)    # east street
    box_fill(g, 78, 108, 11, 11, 106, 108, PATH)    # south street
    box_fill(g, 78, 80, 11, 11, 87, 106, PATH)      # west street
    for b in BANKS + SHELLS + [BAKERY]:
        shop(g, b)
    # hideout
    x0, z0, x1, z1 = HIDEOUT
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            if x in (x0, x1) or z in (z0, z1):
                g[x, 12:15, z] = COBBLE
    box_fill(g, x0, x1, 15, 15, z0, z1, OBSIDIAN)
    g[x1, 12:14, 102] = AIR
    g[78, 12, 104] = CHEST
    for p in STASH:
        g[p] = EMERALD
    # mansion plot marker
    x0, z0, x1, z1 = MANSION
    box_fill(g, x0, x1, 11, 11, z0, z1, SMOOTH)
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
    elif kind == "griefer":
        skin, hair, shirt, pants, shoe = (0.78, 0.58, 0.45), (0.1, 0.1, 0.12), (0.16, 0.16, 0.19), (0.1, 0.1, 0.12), (0.05, 0.05, 0.05)
        hf = head_front(skin, hair)
        hf[3:6, :] = (0.08, 0.08, 0.09)
        hf[4, 1] = hf[4, 6] = (0.95, 0.95, 0.95)
        hf[4, 2] = hf[4, 5] = (0.8, 0.1, 0.1)
        tie = None
    elif kind == "suitgriefer":
        skin, hair, shirt, pants, shoe = (0.78, 0.58, 0.45), (0.1, 0.1, 0.12), (0.85, 0.85, 0.88), (0.2, 0.2, 0.24), (0.05, 0.05, 0.05)
        hf = head_front(skin, hair, glasses=True)
        tie = True
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


def golem_set():
    body = (0.78, 0.76, 0.72)
    hf = solid(body, 8, 10, 50, 0.1)
    hf[4, 1:3] = hf[4, 5:7] = (0.55, 0.12, 0.1)
    hf[3, 1:7] = (0.6, 0.58, 0.55)
    vine = (0.3, 0.55, 0.2)
    bt = solid(body, 18, 12, 51, 0.12)
    r = np.random.default_rng(52)
    bt[r.random((12, 18)) < 0.12] = vine
    t6 = lambda w, h, seed: [solid(body, w, h, seed, 0.12)] * 6
    return dict(head=tex6(hf, solid(body, 8, 10, 53), solid(body, 8, 10, 53), solid(body, 8, 8, 53), solid(body, 8, 8, 53)),
                body=tex6(bt, bt, solid(body, 12, 12, 54), solid(body, 18, 12, 54), solid(body, 18, 12, 54)),
                arm=t6(4, 30, 55), leg=t6(6, 16, 56), nose=t6(2, 4, 57))


def iron_golem(sk, pos, yaw, walk=0.0):
    """~2.7 blocks tall, long swinging arms."""
    Ry = rot_y(yaw)
    sw = 0.45 * math.sin(walk) if walk else 0.0
    P = 1.0 / 16
    bx = []
    for side in (-1, 1):
        R = Ry @ rot_x(sw * side)
        piv = np.asarray(pos) + Ry @ (np.array((side * 3.5, 16, 0)) * P)
        bx.append(Box(piv + R @ (np.array((0, -8, 0)) * P), np.array((3, 8, 2.5)) * P, R, sk["leg"]))
    bx.append(Box(np.asarray(pos) + Ry @ (np.array((0, 27, 0)) * P), np.array((9, 11, 6)) * P, Ry, sk["body"]))
    for side in (-1, 1):
        R = Ry @ rot_x(-sw * side)
        piv = np.asarray(pos) + Ry @ (np.array((side * 11, 37, 0)) * P)
        bx.append(Box(piv + R @ (np.array((0, -15, 0)) * P), np.array((2, 15, 3)) * P, R, sk["arm"]))
    bx.append(Box(np.asarray(pos) + Ry @ (np.array((0, 43, -1)) * P), np.array((4, 5, 4)) * P, Ry, sk["head"]))
    bx.append(Box(np.asarray(pos) + Ry @ (np.array((0, 41, 4)) * P), np.array((1, 2, 1)) * P, Ry, sk["nose"]))
    return bx
