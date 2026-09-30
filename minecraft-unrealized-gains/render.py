#!/usr/bin/env python3
"""Minecraft-style explainer: why taxing unrealized capital gains doesn't work.

    python3 render.py            # full render -> unrealized_gains_minecraft.mp4
    python3 render.py --preview  # a handful of still frames in build/preview/
"""
import asyncio
import json
import math
import os
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import engine as E
import world as W

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "unrealized_gains_minecraft.mp4")
FONT_PATH = os.path.join(HERE, "assets", "PixelifySans.ttf")
FPS = 30
OW, OH = 1920, 1080
SR = 44100
VOICE = "en-US-AndrewNeural"
RATE = "+10%"


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


FFMPEG = ffmpeg_exe()

# ============================================================== narration
SCENES = [
    ("intro", ["Some politicians want to tax unrealized capital gains.",
               "That means taxing stuff that went up in value, even if you never sold it.",
               "Here's why that breaks down."]),
    ("paper", ["Steve bought this plot for ten emeralds.",
               "The village grew, and now it's worth a hundred. On paper.",
               "But his chest? Still empty. He hasn't earned a single emerald."]),
    ("taxman", ["Then the tax collector shows up: twenty percent of that ninety emerald gain, please.",
                "Steve has no cash, so he has to sell part of what he owns, just to pay tax on money he never received."]),
    ("appraise", ["And what is his house actually worth?",
                  "Ask three appraisers, get three answers.",
                  "Without a sale, there's no real price. Just guesses, and endless fights over them."]),
    ("crash", ["Then the market crashes.",
               "Steve's paper fortune goes up in smoke, but the tax he already paid is gone.",
               "And refunding paper losses would make government revenue swing wildly."]),
    ("leave", ["Meanwhile, the richest players just move their money, or themselves, somewhere else.",
               "That's why most European countries that tried wealth taxes have repealed them."]),
    ("outro", ["The better way? Tax gains when they're real: when you actually sell."]),
]
LEAD, GAP, SGAP, TAIL = 0.7, 0.28, 0.55, 2.2


def tts_all():
    os.makedirs(os.path.join(BUILD, "tts"), exist_ok=True)
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):  # sandbox proxy
        import certifi
        certifi.where = lambda: ca
    import edge_tts

    async def go():
        for si, (_, sents) in enumerate(SCENES):
            for k, s in enumerate(sents):
                mp3 = os.path.join(BUILD, "tts", f"{si}_{k}.mp3")
                meta = mp3 + ".txt"
                if os.path.exists(mp3) and os.path.exists(meta) and open(meta).read() == s + VOICE + RATE:
                    continue
                await edge_tts.Communicate(s, VOICE, rate=RATE).save(mp3)
                open(meta, "w").write(s + VOICE + RATE)
    asyncio.run(go())


def load_audio(path):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32).copy()
    # trim silence at the ends
    nz = np.nonzero(np.abs(a) > 0.01)[0]
    return a[max(0, nz[0] - 400):nz[-1] + 1200] if len(nz) else a


def timeline():
    """-> list of scenes: dict(name, t0, t1, sents=[(start,end,text,audio_path)]) (absolute times)."""
    scenes = []
    t = LEAD
    for si, (name, sents) in enumerate(SCENES):
        info = []
        for k, s in enumerate(sents):
            p = os.path.join(BUILD, "tts", f"{si}_{k}.mp3")
            d = len(load_audio(p)) / SR
            info.append((t, t + d, s, p))
            t += d + GAP
        scenes.append(dict(name=name, sents=info))
        t += SGAP - GAP
    for i, sc in enumerate(scenes):
        sc["t0"] = 0.0 if i == 0 else sc["sents"][0][0] - 0.35
    for i, sc in enumerate(scenes):
        sc["t1"] = scenes[i + 1]["t0"] if i + 1 < len(scenes) else sc["sents"][-1][1] + TAIL
    return scenes


# ============================================================== 2D overlay helpers
_FONT = None


def font():
    global _FONT
    if _FONT is None:
        _FONT = ImageFont.truetype(FONT_PATH, 13)
    return _FONT


@lru_cache(maxsize=2048)
def text_img(text, color=(255, 255, 255), scale=3, shadow=True, bg=0):
    f = font()
    asc, desc = f.getmetrics()
    w = max(1, int(f.getlength(text)) + 2)
    h = asc + desc
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.fontmode = "1"
    d.text((0, 0), text, font=f, fill=255)
    arr = np.array(m) > 0
    pad = 2 if bg else 0
    out = np.zeros((h + 1 + 2 * pad, w + 1 + 2 * pad, 4), np.uint8)
    if bg:
        out[..., 3] = bg
    if shadow:
        sc = tuple(int(c * 0.25) for c in color)
        out[pad + 1:pad + 1 + h, pad + 1:pad + 1 + w][arr] = (*sc, 255)
    out[pad:pad + h, pad:pad + w][arr] = (*color, 255)
    im = Image.fromarray(out, "RGBA")
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def put(frame, img, x, y, anchor="mm", alpha=1.0):
    if alpha <= 0:
        return
    if alpha < 1:
        img = img.copy()
        a = np.array(img.getchannel("A"), np.float32) * alpha
        img.putalpha(Image.fromarray(a.astype(np.uint8)))
    w, h = img.size
    x0 = int(x - (w / 2 if anchor[0] == "m" else (w if anchor[0] == "r" else 0)))
    y0 = int(y - (h / 2 if anchor[1] == "m" else (h if anchor[1] == "b" else 0)))
    frame.paste(img, (x0, y0), img)


def wrap(text, maxw, scale):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if font().getlength(t) * scale > maxw and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def sprite(rows, pal):
    h, w = len(rows), max(len(r) for r in rows)
    a = np.zeros((h, w, 4), np.uint8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch in pal:
                a[y, x] = (*pal[ch], 255)
    return Image.fromarray(a, "RGBA")


EMERALD = sprite([
    "......####......",
    ".....#aabb#.....",
    "....#aabbbb#....",
    "...#aabbbbbc#...",
    "..#aabbbbbbcc#..",
    ".#abbbbbbbbbcc#.",
    ".#abbbbbbbbbcc#.",
    ".#bbbbbbbbbbcc#.",
    "..#bbbbbbbbcc#..",
    "...#bbbbbbcc#...",
    "....#bbbbcc#....",
    ".....#bccc#.....",
    "......####......",
], {"#": (10, 70, 30), "a": (170, 255, 190), "b": (40, 205, 95), "c": (18, 140, 60)})

SWORD = sprite([
    ".............##.",
    "............#ab#",
    "...........#ab#.",
    "..........#ab#..",
    ".........#ab#...",
    "........#ab#....",
    ".......#ab#.....",
    "..##..#ab#......",
    "..#c##ab#.......",
    "...#cc#.........",
    "...#dc#.........",
    "..#d##c#........",
    ".#d#..##........",
    "#d#.............",
    "##..............",
], {"#": (20, 20, 20), "a": (170, 255, 250), "b": (60, 200, 190), "c": (90, 60, 30), "d": (130, 90, 45)})

PICK = sprite([
    "...######.......",
    "..#aaaaaa##.....",
    "...##bbbbaa#....",
    ".....##cc#ba#...",
    ".......#dc#ba#..",
    "......#dc#.#b#..",
    ".....#dc#..#b#..",
    "....#dc#....#...",
    "...#dc#.........",
    "..#dc#..........",
    ".#dc#...........",
    "#dc#............",
    "##..............",
], {"#": (20, 20, 20), "a": (170, 255, 250), "b": (60, 200, 190), "c": (90, 60, 30), "d": (130, 90, 45)})

HEART = sprite([
    ".##...##.",
    "#ab#.#aa#",
    "#abb#bbb#",
    "#bbbbbbb#",
    ".#bbbbb#.",
    "..#bbb#..",
    "...#b#...",
    "....#....",
], {"#": (30, 5, 5), "a": (255, 200, 200), "b": (220, 20, 20)})


def block_icon(bid):
    """Tiny isometric-looking block icon from the texture atlas (16px)."""
    t = (E.TEX[bid, 1] * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([t, np.full((16, 16), 255, np.uint8)]), "RGBA")


def big(img, s):
    return img.resize((img.width * s, img.height * s), Image.NEAREST)


@lru_cache(maxsize=1)
def hud_img():
    s = 4
    hud = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    d = ImageDraw.Draw(hud)
    bw, bh = 182 * s, 22 * s
    x0, y0 = (OW - bw) // 2, OH - bh - 6
    d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=(20, 20, 20, 150), outline=(0, 0, 0, 220), width=s)
    for i in range(9):
        sx = x0 + s + i * 20 * s
        d.rectangle([sx, y0 + s, sx + 20 * s, y0 + 21 * s], outline=(120, 120, 120, 200), width=s)
    d.rectangle([x0 - s, y0 - s, x0 + 22 * s, y0 + 23 * s], outline=(255, 255, 255, 255), width=s)
    items = [SWORD, PICK, block_icon(E.DIRT), block_icon(E.PLANKS), block_icon(E.COBBLE), None, None, None, EMERALD]
    for i, it in enumerate(items):
        if it is None:
            continue
        ic = big(it, s)
        hud.alpha_composite(ic, (x0 + 3 * s + i * 20 * s + (16 * s - ic.width) // 2, y0 + 3 * s + (16 * s - ic.height) // 2))
    # "0" emeralds
    z = text_img("0", (255, 90, 90), 3)
    hud.alpha_composite(z, (x0 + 8 * 20 * s + 14 * s, y0 + 11 * s))
    # xp bar
    yx = y0 - 7 * s
    d.rectangle([x0, yx, x0 + bw, yx + 5 * s], fill=(10, 10, 10, 220))
    d.rectangle([x0 + s, yx + s, x0 + int(bw * 0.35), yx + 4 * s], fill=(128, 255, 32, 255))
    # hearts
    hh = big(HEART, s)
    for i in range(10):
        hud.alpha_composite(hh, (x0 + i * 8 * s, yx - 10 * s))
    return hud


def tooltip_panel(w, h):
    im = Image.new("RGBA", (w, h), (16, 0, 16, 235))
    d = ImageDraw.Draw(im)
    d.rectangle([4, 4, w - 5, h - 5], outline=(80, 0, 255, 255), width=4)
    d.rectangle([0, 0, w - 1, h - 1], outline=(16, 0, 16, 255), width=4)
    return im


@lru_cache(maxsize=1)
def chest_gui():
    s = 4
    w, h = 176, 166
    g = Image.new("RGBA", (w, h), (198, 198, 198, 255))
    d = ImageDraw.Draw(g)
    d.rectangle([0, 0, w - 1, h - 1], outline=(0, 0, 0, 255))
    d.line([1, 1, w - 3, 1], fill=(255, 255, 255, 255), width=2)
    d.line([1, 1, 1, h - 3], fill=(255, 255, 255, 255), width=2)
    d.line([2, h - 2, w - 2, h - 2], fill=(85, 85, 85, 255), width=2)
    d.line([w - 2, 2, w - 2, h - 2], fill=(85, 85, 85, 255), width=2)

    def slot(x, y):
        d.rectangle([x, y, x + 17, y + 17], fill=(139, 139, 139, 255))
        d.line([x, y, x + 16, y], fill=(55, 55, 55, 255))
        d.line([x, y, x, y + 16], fill=(55, 55, 55, 255))
        d.line([x + 1, y + 17, x + 17, y + 17], fill=(255, 255, 255, 255))
        d.line([x + 17, y + 1, x + 17, y + 17], fill=(255, 255, 255, 255))
    for r in range(3):
        for c in range(9):
            slot(7 + c * 18, 17 + r * 18)
    for r in range(3):
        for c in range(9):
            slot(7 + c * 18, 83 + r * 18)
    for c in range(9):
        slot(7 + c * 18, 141)
    g = big(g, s)
    g.alpha_composite(text_img("Steve's Chest", (64, 64, 64), s, shadow=False), (8 * s, 3 * s))
    g.alpha_composite(text_img("Inventory", (64, 64, 64), s, shadow=False), (8 * s, 70 * s))
    for i, it in enumerate([SWORD, PICK, block_icon(E.DIRT), block_icon(E.PLANKS), block_icon(E.COBBLE)]):
        g.alpha_composite(big(it, s), ((8 + i * 18) * s, 142 * s))
    return g


# ============================================================== audio
def piano(freq, dur, sr=SR, vel=1.0):
    t = np.arange(int(dur * sr)) / sr
    y = np.zeros_like(t)
    for k in range(1, 7):
        y += (1 / k ** 1.6) * np.sin(2 * np.pi * freq * k * t) * np.exp(-t * (1.2 + 0.9 * k))
    y *= np.minimum(1, t / 0.004)
    return y * vel


def reverb(x, sr=SR, secs=2.2, wet=0.3):
    rng = np.random.default_rng(5)
    n = int(secs * sr)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / sr * 3.2)
    ir /= np.sqrt((ir ** 2).sum())
    L = len(x) + n
    nfft = 1 << (L - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:len(x)]
    return x * (1 - wet) + y * wet * 3


def music(dur):
    rng = np.random.default_rng(11)
    out = np.zeros(int((dur + 4) * SR))
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    chords = [[48, 55, 64, 71], [45, 52, 60, 67], [41, 48, 57, 64], [43, 50, 59, 62]]
    scale = [60, 62, 64, 67, 69, 72, 74, 76, 79]
    t, ci = 0.0, 0
    while t < dur:
        for k, n in enumerate(chords[ci % 4]):
            s = int((t + k * 0.06) * SR)
            nt = piano(midi(n), 4.0, vel=0.35)
            out[s:s + len(nt)] += nt[:len(out) - s]
        for b in range(8):
            if rng.random() < 0.55:
                s = int((t + b * 0.5 + rng.random() * 0.03) * SR)
                nt = piano(midi(scale[rng.integers(len(scale))]), 2.5, vel=0.45)
                out[s:s + len(nt)] += nt[:len(out) - s]
        t += 4.0
        ci += 1
    out = reverb(out)
    return out[:int(dur * SR)]


def sfx_pop(pitch=1.0):
    t = np.arange(int(0.09 * SR)) / SR
    f = 700 * pitch * (1 + 2 * np.exp(-t * 60))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 40) * 0.35


def sfx_boom():
    rng = np.random.default_rng(3)
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    # crude low-pass by cumulative averaging
    for _ in range(3):
        x = np.convolve(x, np.ones(18) / 18, mode="same")
    x = x / np.abs(x).max()
    thump = np.sin(2 * np.pi * 45 * t * (1 - 0.3 * t)) * np.exp(-t * 4)
    return (x * np.exp(-t * 2.8) * 0.9 + thump * 0.8) * np.minimum(1, t / 0.005)


def sfx_hiss(dur):
    rng = np.random.default_rng(4)
    n = int(dur * SR)
    x = rng.standard_normal(n) * 0.06
    return x - np.convolve(x, np.ones(6) / 6, mode="same")


def sfx_whoosh():
    rng = np.random.default_rng(6)
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    x = np.convolve(x, np.ones(40) / 40, mode="same")
    env = np.sin(np.pi * t / 1.4) ** 2
    wob = np.sin(2 * np.pi * (220 + 180 * t) * t) * 0.3
    return (x * 2.0 + wob) * env * 0.35


def sfx_levelup():
    out = np.zeros(int(1.2 * SR))
    for i, n in enumerate([72, 76, 79, 84]):
        s = int(i * 0.09 * SR)
        f = 440 * 2 ** ((n - 69) / 12)
        t = np.arange(int(0.8 * SR)) / SR
        y = (np.sign(np.sin(2 * np.pi * f * t)) * 0.3 + np.sin(2 * np.pi * f * t)) * np.exp(-t * 5) * 0.18
        out[s:s + len(y)] += y[:len(out) - s]
    return out


def sfx_click():
    t = np.arange(int(0.03 * SR)) / SR
    return np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 200) * 0.25


# ============================================================== scene helpers
def ss(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return np.asarray(a, float) * (1 - k) + np.asarray(b, float) * k


def path(lt, keys):
    """keys: [(t, pos, target, fov)] -> Camera with smooth interpolation."""
    if lt <= keys[0][0]:
        k0 = keys[0]
        return E.Camera(k0[1], k0[2], k0[3])
    for a, b in zip(keys, keys[1:]):
        if lt <= b[0]:
            k = ss((lt - a[0]) / (b[0] - a[0]))
            return E.Camera(lerp(a[1], b[1], k), lerp(a[2], b[2], k), a[3] * (1 - k) + b[3] * k)
    k1 = keys[-1]
    return E.Camera(k1[1], k1[2], k1[3])


def yaw_to(a, b):
    return math.atan2(b[0] - a[0], b[2] - a[2])


def fade(lt, t0, t1, f=0.25):
    if lt < t0 or lt > t1:
        return 0.0
    return min(1.0, (lt - t0) / f, (t1 - lt) / f)


STEVE = (96.5, 12.0, 93.0)
DOOR = (107.3, 12.0, 86.5)
MEET = (98.4, 12.0, 92.2)
STEVE_SK = W.skin_set("steve")
TAX_SK = W.skin_set("taxman")
RICH_SK = W.skin_set("rich")
APPR_SK = [W.villager_set((0.47, 0.32, 0.18)), W.villager_set((0.45, 0.22, 0.55)), W.villager_set((0.22, 0.46, 0.26))]
APPR_POS = [(92.9, 12.0, 90.9), (95.5, 12.0, 90.0), (98.1, 12.0, 90.9)]


class Worlds:
    def __init__(self):
        self.base = W.build_base()
        self.village = self.base.copy()
        for x, y, z, b in W.VILLAGE:
            self.village[x, y, z] = b
        self.sale = W.roof_sale_blocks()
        self.sold = self.village.copy()
        for x, y, z in self.sale:
            self.sold[x, y, z] = E.AIR
        self.tower = self.sold.copy()
        for x, y, z, b in W.TOWER:
            self.tower[x, y, z] = b
        self.tower[W.TNT_POS] = E.TNT
        self.blast = self.tower.copy()
        m = W.blast_mask()
        m[:, :6, :] = False
        self.blast[m] = E.AIR


def burst(t_since, seed, center, n, colors, speed=4.0, life=1.2, size=0.18, grav=-6.0, up=2.0):
    if t_since < 0 or t_since > life:
        return []
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        v = rng.standard_normal(3)
        v = v / np.linalg.norm(v) * speed * (0.4 + rng.random())
        v[1] += up
        lt = life * (0.6 + 0.4 * rng.random())
        if t_since > lt:
            continue
        p = np.asarray(center) + v * t_since + np.array((0, 0.5 * grav * t_since ** 2, 0))
        out.append((p, colors[i % len(colors)], size * (1 - 0.5 * t_since / lt)))
    return out


# ============================================================== scenes
def scene_intro(lt, S, wd):
    D = S["dur"]
    cam = path(lt, [(0, (66, 27, 64), (94, 14, 96), 70), (D, (83, 17.5, 79), (96, 13.5, 96), 66)])
    boxes = W.player(STEVE_SK, STEVE, math.pi, head_yaw=0.3 * math.sin(lt * 0.8))
    boxes += W.player(TAX_SK, DOOR, -math.pi / 2, hat=True)
    title_a = fade(lt, 0.35, D - 0.2, 0.4)
    ov = []

    def title(fr):
        s = 1 + 0.03 * math.sin(lt * 5)
        put(fr, text_img("TAXING UNREALIZED", (225, 225, 225), 8), OW / 2, 190, alpha=title_a)
        put(fr, text_img("GAINS", (225, 225, 225), 11), OW / 2, 320, alpha=title_a)
        sp = text_img("Why it doesn't work!", (255, 255, 0), 4)
        sp = sp.resize((int(sp.width * s), int(sp.height * s)), Image.NEAREST).rotate(14, expand=True, resample=Image.NEAREST)
        put(fr, sp, OW / 2 + 470, 390, alpha=title_a)
    ov.append(title)
    return dict(cam=cam, boxes=boxes, grid=wd.base, hud=False, overlays=ov,
                labels=[(np.add(DOOR, (0, 2.3, 0)), "Tax_Collector"), (np.add(STEVE, (0, 2.3, 0)), "Steve")])


def scene_paper(lt, S, wd):
    s0, s1, s2 = S["st"]
    D = S["dur"]
    cam = path(lt, [(0, (100.0, 14.6, 85.5), (95.5, 14.2, 95), 68), (s1 - 0.2, (100.3, 14.6, 85.8), (95.5, 14.2, 95), 68),
                    (s1 + 2.6, (104, 25, 70), (91, 13, 92), 72), (s2 - 0.1, (104, 25, 70), (91, 13, 92), 72),
                    (s2 + 0.9, (95.8, 14.3, 90.0), (93.5, 12.4, 94.5), 66), (D, (95.7, 14.2, 90.2), (93.5, 12.4, 94.5), 66)])
    # village grows block by block
    nb = len(W.VILLAGE)
    k = int(nb * ss((lt - s1 - 0.2) / 3.0))
    g = wd.base.copy()
    for x, y, z, b in W.VILLAGE[:k]:
        g[x, y, z] = b
    wave = lt < s1 + 0.2
    boxes = W.player(STEVE_SK, STEVE, math.pi, arm_r=(-2.7 + 0.35 * math.sin(lt * 9)) if wave else None,
                     head_yaw=0.0 if lt < s2 else -0.6)
    boxes += W.player(TAX_SK, DOOR, -math.pi / 2, hat=True)
    sign = (95.0, 21.5, 99.0)
    labels = [(np.add(STEVE, (0, 2.3, 0)), "Steve")]
    vals = []
    if lt < s1 + 1.6:
        vals.append((sign, [("Bought for: 10", (85, 255, 85))]))
    else:
        vals.append((sign, [("Worth now: 100", (255, 215, 60)), ("(on paper)", (200, 200, 200))]))
    ov = []
    ga = fade(lt, s2 + 0.8, D + 1, 0.2)

    def chest(fr):
        if ga <= 0:
            return
        dim = Image.new("RGBA", (OW, OH), (0, 0, 0, int(110 * ga)))
        fr.paste(dim, (0, 0), dim)
        g_ = chest_gui()
        g_ = g_.resize((int(g_.width * 0.85), int(g_.height * 0.85)), Image.NEAREST)
        put(fr, g_, OW / 2, 420, alpha=ga)
        put(fr, text_img("EMPTY", (255, 85, 85), 6), OW / 2, 80, alpha=ga)
    ov.append(chest)
    chats = [(S["t0"] + s2 + 1.4, "<Steve> 0 emeralds. It's all on paper...", (255, 255, 255))]
    sfx = [(S["t0"] + s1 + 0.2 + 3.0 * i / 12, "pop", 0.8 + 0.05 * i) for i in range(12)]
    sfx.append((S["t0"] + s2 + 0.8, "click", 1))
    return dict(cam=cam, boxes=boxes, grid=g, hud=True, labels=labels, values=vals, overlays=ov,
                chats=chats, sfx=sfx, icons=[(sign, 2.2)] if True else [])


def taxman_pos(lt, arrive):
    k = min(1.0, max(0.0, lt / arrive))
    p = lerp(DOOR, MEET, k)
    walking = 0 < lt < arrive
    return p, (lt * 9 if walking else 0.0)


def scene_taxman(lt, S, wd):
    s0, s1 = S["st"]
    D = S["dur"]
    arrive = s0 + 2.8
    cam = path(lt, [(0, (101.5, 15.2, 82.0), (101, 13, 90.5), 68), (arrive, (100.5, 15.0, 84.5), (97.8, 13.3, 92.5), 66),
                    (s1 + 0.2, (100.8, 15.0, 84.7), (97.8, 13.3, 92.5), 66), (s1 + 1.6, (103, 22.5, 82), (96, 15, 97), 68),
                    (D, (102.5, 22.5, 82.5), (96, 15, 97), 68)])
    tp, walk = taxman_pos(lt, arrive)
    tyaw = yaw_to(DOOR, MEET) if lt < arrive else yaw_to(MEET, STEVE)
    boxes = W.player(TAX_SK, tp, tyaw, walk=walk, hat=True,
                     arm_r=-1.4 if arrive < lt < s1 + 0.3 else None)
    syaw = yaw_to(STEVE, tp) if lt > 0.8 else math.pi
    boxes += W.player(STEVE_SK, STEVE, syaw, arm_r=-0.5 + 0.25 * math.sin(lt * 7) if lt > s1 else None)
    # selling roof blocks, one per emerald
    t_sale0, t_sale = s1 + 1.3, 3.8
    n = len(wd.sale)
    g = wd.village.copy()
    parts, sprites_, sfx = [], [], []
    done = 0
    for i, (x, y, z) in enumerate(wd.sale):
        ti = t_sale0 + t_sale * i / n
        if lt >= ti:
            g[x, y, z] = E.AIR
            done += 1
            c = np.array((x + 0.5, y + 0.5, z + 0.5))
            parts += burst(lt - ti, 100 + i, c, 10, [(0.42, 0.3, 0.18), (0.3, 0.21, 0.12)], speed=2.0, life=0.7, size=0.14)
            fly = (lt - ti) / 0.9
            if fly < 1:
                end = np.add(tp, (0, 1.2, 0))
                p = lerp(c, end, fly) + np.array((0, 2.5 * math.sin(math.pi * fly), 0))
                sprites_.append((p, 0.45))
        sfx.append((S["t0"] + ti, "pop", 1.0 + 0.03 * i))
    labels = [(np.add(STEVE, (0, 2.3, 0)), "Steve"), (np.add(tp, (0, 2.75, 0)), "Tax_Collector")]
    vals = []
    if lt > arrive:
        vals.append((np.add(tp, (0, 3.35, 0)), [("TAX BILL: 18", (255, 85, 85))]))
    if lt > t_sale0 - 0.2:
        vals.append(((95.0, 21.8, 99.0), [(f"Roof blocks sold: {done}/18", (255, 255, 255))]))
    chats = [(S["t0"] + arrive + 0.1, "<Tax_Collector> 20% of your 90 emerald gain = 18. Pay up.", (255, 255, 255)),
             (S["t0"] + s1 + 0.4, "<Steve> But I never sold anything!", (255, 255, 255))]
    return dict(cam=cam, boxes=boxes, grid=g, hud=True, labels=labels, values=vals, particles=parts,
                sprites=sprites_, chats=chats, sfx=sfx,
                icons=[(np.add(tp, (0, 3.35, 0)), 2.0)] if lt > arrive else [])


def scene_appraise(lt, S, wd):
    s0, s1, s2 = S["st"]
    D = S["dur"]
    cam = path(lt, [(0, (95.5, 18.5, 80.5), (95.5, 16, 97), 66), (s1 - 0.1, (95.5, 16.5, 83.0), (95.5, 15, 96), 66),
                    (s1 + 1.2, (95.5, 14.6, 84.6), (95.5, 13.6, 93), 64), (D, (96.0, 14.6, 85.2), (95.5, 13.6, 93), 62)])
    boxes = []
    for i, (sk, p) in enumerate(zip(APPR_SK, APPR_POS)):
        hy = 0.0
        if lt > s2:
            hy = 0.5 * math.sin(lt * 3 + i * 2)
        boxes += W.villager(sk, p, math.pi, head_yaw=hy, nod=0.2 * math.sin(lt * 6 + i) if lt > s2 else 0.0)
    tp = (100.8, 12.0, 91.4)
    boxes += W.player(TAX_SK, tp, yaw_to(tp, APPR_POS[2]), hat=True)
    boxes += W.player(STEVE_SK, (90.3, 12, 91.6), yaw_to((90.3, 12, 91.6), APPR_POS[0]), head_yaw=0.3 * math.sin(lt * 2))
    base = ["80?", "150?", "400?!"]
    cols = [(85, 255, 85), (255, 215, 60), (255, 85, 85)]
    rng = np.random.default_rng(int(lt * 3))
    vals, sfx = [], []
    for i in range(3):
        ti = s1 + 0.15 + i * 0.75
        sfx.append((S["t0"] + ti, "click", 1))
        if lt > ti:
            txt = base[i]
            if lt > s2 + 0.3:
                txt = f"{int(rng.integers(40, 500))}?!"
            vals.append((np.add(APPR_POS[i], (0, 2.9, 0)), [(txt, cols[i])]))
    labels = [(np.add(p, (0, 2.45, 0)), "Appraiser") for p in APPR_POS]
    labels += [(np.add(tp, (0, 2.3, 0)), "Tax_Collector")]
    if lt > s2 + 1.4:
        vals.append((np.add(tp, (0, 2.9, 0)), [("Tax on 400!", (255, 85, 85))]))
    chats = [(S["t0"] + s2 + 0.3, "<Appraiser_1> 80 emeralds, tops.", (255, 255, 255)),
             (S["t0"] + s2 + 1.3, "<Appraiser_3> It's clearly worth 400!", (255, 255, 255)),
             (S["t0"] + s2 + 2.4, "<Tax_Collector> We'll use the 400.", (255, 255, 255)),
             (S["t0"] + s2 + 3.4, "<Steve> See you in court.", (255, 255, 255))]
    return dict(cam=cam, boxes=boxes, grid=wd.sold, hud=True, labels=labels, values=vals, chats=chats, sfx=sfx)


def scene_crash(lt, S, wd):
    s0, s1, s2 = S["st"]
    D = S["dur"]
    tb = s0 + 1.5
    shake = np.zeros(3)
    if 0 < lt - tb < 0.7:
        r = np.random.default_rng(int(lt * 60))
        shake = r.standard_normal(3) * 0.25 * (1 - (lt - tb) / 0.7)
    cam = path(lt, [(0, (95.5, 17.0, 79.0), (85.5, 15.2, 89.5), 68), (tb, (94.5, 16.6, 80.0), (85.5, 15.2, 89.5), 68),
                    (D, (93.0, 17.5, 79.5), (86, 14.5, 90), 70)])
    cam = E.Camera(cam.o + shake, cam.o + shake + cam.f, 68)
    if lt < tb:
        g = wd.tower.copy()
        if int(lt / 0.2) % 2 == 1 and lt > s0:
            g[W.TNT_POS] = E.TNT_LIT
    else:
        g = wd.blast
    sp = (91.4, 12.0, 86.0)
    boxes = W.player(STEVE_SK, sp, yaw_to(sp, W.BLAST_C),
                     arm_r=-2.9 if tb < lt < tb + 1.5 else None, arm_l=-2.9 if tb < lt < tb + 1.5 else None)
    parts = burst(lt - tb, 7, W.BLAST_C, 110, [(0.9, 0.9, 0.9), (0.6, 0.6, 0.6), (0.98, 0.82, 0.24), (0.3, 0.3, 0.3)],
                  speed=7, life=1.6, size=0.45, grav=-4, up=2)
    parts += burst(lt - tb - 0.1, 8, W.BLAST_C, 60, [(0.5, 0.5, 0.5), (0.8, 0.8, 0.8)], speed=2.5, life=2.4, size=0.9, grav=1.5, up=1)
    top = (85.5, 21.8, 89.5)
    vals = [(top, [("Steve's paper fortune: 100", (255, 215, 60))])] if lt < tb else \
        [(top, [("Paper fortune: 40", (255, 85, 85)), ("Tax already paid: 18 (gone)", (255, 255, 255))])]
    flash = max(0.0, 0.8 * (1 - (lt - tb) / 0.35)) if lt > tb else 0.0
    ov = []

    def chart(fr):
        a = fade(lt, 0.2, D + 1)
        if a <= 0:
            return
        pw, ph = 560, 330
        panel = tooltip_panel(pw, ph)
        d = ImageDraw.Draw(panel)
        if lt < s2:
            panel.alpha_composite(text_img("Steve's stuff (on paper)", (255, 255, 255), 3), (22, 14))
            pts = [(0, 10), (1, 25), (2, 55), (3, 100)]
            if lt > tb:
                pts.append((3 + ss((lt - tb) / 0.4), 100 - 60 * ss((lt - tb) / 0.4)))
            xy = [(40 + x * 120, ph - 30 - y * 2.3) for x, y in pts]
            d.line(xy, fill=(85, 255, 85, 255) if lt < tb else (255, 85, 85, 255), width=8)
            for x, y in xy:
                d.rectangle([x - 6, y - 6, x + 6, y + 6], fill=(255, 255, 255, 255))
        else:
            panel.alpha_composite(text_img("Tax revenue, year by year", (255, 255, 255), 3), (22, 14))
            bars = [40, -30, 55, -45, 25, -60, 70, -35]
            mid = 200
            d.line([(24, mid), (pw - 24, mid)], fill=(160, 160, 160, 255), width=3)
            nshow = int(1 + (lt - s2) / 0.35)
            for i, b in enumerate(bars[:nshow]):
                x = 40 + i * 62
                y0, y1 = (mid - b * 1.8, mid) if b > 0 else (mid, mid - b * 1.8)
                d.rectangle([x, y0, x + 40, y1], fill=(85, 255, 85, 255) if b > 0 else (255, 85, 85, 255))
            panel.alpha_composite(text_img("refunds!", (255, 85, 85), 2), (pw - 150, ph - 44))
        put(fr, panel, OW - 40, 40, "rt", alpha=a)
    ov.append(chart)
    chats = [(S["t0"] + s1 + 0.9, "<Steve> Can I get my 18 emeralds back?", (255, 255, 255)),
             (S["t0"] + s1 + 2.6, "<Tax_Collector> ...Refunds? Uh. Let me check.", (255, 255, 255))]
    sfx = [(S["t0"] + tb, "boom", 1), (S["t0"] + s0, "hiss", tb - s0)]
    return dict(cam=cam, boxes=boxes, grid=g, hud=True, particles=parts, values=vals, overlays=ov,
                flash=flash, chats=chats, sfx=sfx, labels=[(np.add(sp, (0, 2.3, 0)), "Steve")],
                icons=[] if lt > tb else [(top, 2.8)])


RICH = [("Rich_Player1", (70.5, 12.0, 85.5), 0.0), ("Big_Investor", (66.5, 12.0, 84.0), 0.9),
        ("Moneybags99", (69.0, 12.0, 81.5), 1.8)]
PORTAL_IN = (69.95, 12.0, 96.6)


def scene_leave(lt, S, wd):
    s0, s1 = S["st"]
    D = S["dur"]
    cam = path(lt, [(0, (61.0, 17.0, 80.5), (70, 13.5, 95), 66), (s1, (62.5, 16.0, 85.5), (70, 13.8, 95), 64),
                    (D, (63.0, 16.0, 86.5), (70, 13.8, 95), 62)])
    boxes, labels, parts, chats, sfx = [], [], [], [], []
    for i, (name, start, delay) in enumerate(RICH):
        t = lt - delay - 0.2
        dist = np.linalg.norm(np.subtract(PORTAL_IN, start))
        speed = 3.2
        tin = dist / speed
        if t < tin:
            k = max(0.0, t) / tin
            p = lerp(start, PORTAL_IN, k)
            boxes += W.player(RICH_SK, p, yaw_to(start, PORTAL_IN), walk=t * 9 if t > 0 else 0.0, crown=True,
                              arm_r=-0.9 if i == 1 else None)
            labels.append((np.add(p, (0, 2.55, 0)), name))
        else:
            parts += burst(t - tin, 300 + i, (69.95, 13.4, 96.2), 40, [(0.6, 0.2, 0.9), (0.8, 0.5, 1.0)],
                           speed=1.5, life=1.4, size=0.13, grav=0.8, up=0.5)
        chats.append((S["t0"] + delay + 0.2 + tin, f"{name} left the game", (255, 255, 85)))
        sfx.append((S["t0"] + delay + 0.2 + tin - 0.3, "whoosh", 1))
    vals = [((69.95, 16.8, 96.0), [("To: Low-Tax Server", (200, 120, 255))])]
    ov = []

    def bars(fr):
        a = fade(lt, s1 + 0.2, D + 1)
        if a <= 0:
            return
        pw, ph = 720, 330
        panel = tooltip_panel(pw, ph)
        d = ImageDraw.Draw(panel)
        panel.alpha_composite(text_img("OECD countries with a wealth tax", (255, 255, 255), 3), (22, 14))
        k = ss((lt - s1 - 0.4) / 1.2)
        for j, (yr, n, c) in enumerate([("1990", 12, (255, 215, 60)), ("2017", 4, (255, 85, 85))]):
            y = 90 + j * 100
            panel.alpha_composite(text_img(yr, (220, 220, 220), 3), (22, y + 8))
            wv = int(n * 30 * k)
            d.rectangle([130, y, 130 + wv, y + 60], fill=(*c, 255))
            panel.alpha_composite(text_img(str(int(round(n * k))), (255, 255, 255), 3), (140 + wv, y + 8))
        panel.alpha_composite(text_img("Source: OECD (2018)", (170, 170, 170), 2), (22, ph - 44))
        put(fr, panel, OW - 40, 40, "rt", alpha=a)
    ov.append(bars)
    return dict(cam=cam, boxes=boxes, grid=wd.blast, hud=True, labels=labels, particles=parts, values=vals,
                overlays=ov, chats=chats, sfx=sfx)


def scene_outro(lt, S, wd):
    D = S["dur"]
    a = 0.25 * lt
    c = np.array((95.5, 13.5, 95.0))
    cam = E.Camera(c + np.array((10 * math.sin(math.pi + 0.35 - a * 0.3), 4.5 + 0.8 * lt, 10 * math.cos(math.pi + 0.35 - a * 0.3))),
                   c + (0, 1.2, 0), 68)
    boxes = W.player(STEVE_SK, STEVE, yaw_to(STEVE, cam.o), arm_r=-2.7 + 0.35 * math.sin(lt * 9))
    ta = fade(lt, 0.3, D + 5, 0.4)
    ov = []

    def title(fr):
        put(fr, text_img("TAX GAINS WHEN", (230, 230, 230), 8), OW / 2, 200, alpha=ta)
        put(fr, text_img("THEY'RE REAL", (85, 255, 85), 10), OW / 2, 330, alpha=ta)
        sp = text_img("...when you actually SELL!", (255, 255, 0), 4).rotate(12, expand=True, resample=Image.NEAREST)
        put(fr, sp, OW / 2 + 430, 450, alpha=ta)
    ov.append(title)
    black = min(1.0, max(0.0, (lt - (D - 0.8)) / 0.8))
    return dict(cam=cam, boxes=boxes, grid=wd.blast, hud=False, overlays=ov, black=black,
                sfx=[(S["t0"] + 0.35, "levelup", 1)], labels=[(np.add(STEVE, (0, 2.3, 0)), "Steve")])


SCENE_FN = dict(intro=scene_intro, paper=scene_paper, taxman=scene_taxman, appraise=scene_appraise,
                crash=scene_crash, leave=scene_leave, outro=scene_outro)


# ============================================================== frame composition
def scene_at(t, scenes):
    for sc in scenes:
        if sc["t0"] <= t < sc["t1"]:
            return sc
    return scenes[-1]


def prep(scenes):
    for sc in scenes:
        sc["dur"] = sc["t1"] - sc["t0"]
        sc["st"] = [s[0] - sc["t0"] for s in sc["sents"]]
    return scenes


def all_chats(scenes, wd):
    out = []
    for sc in scenes:
        for probe in (sc["dur"] - 0.01,):
            r = SCENE_FN[sc["name"]](probe, sc, wd)
            out += r.get("chats", [])
    return sorted(out)


def draw_particles(img, depth, cam, parts):
    for p, c, size in parts:
        pr = cam.project(p)
        if pr is None:
            continue
        x, y, dist = pr
        px = max(1, int(size / (dist * cam.th) * E.RH / 2))
        xi, yi = int(x), int(y)
        if not (0 <= xi < E.RW and 0 <= yi < E.RH) or depth[yi, xi] < dist:
            continue
        img[max(0, yi - px // 2):yi + (px + 1) // 2, max(0, xi - px // 2):xi + (px + 1) // 2] = c


def compose(t, scenes, wd, chats):
    sc = scene_at(t, scenes)
    lt = t - sc["t0"]
    r = SCENE_FN[sc["name"]](lt, sc, wd)
    cam = r["cam"]
    img, depth = E.render(r["grid"], cam, t, r.get("boxes", []))
    draw_particles(img, depth, cam, r.get("particles", []))
    img = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    img = np.repeat(np.repeat(img, 3, 0), 3, 1)
    fr = Image.fromarray(img, "RGB")
    S3 = 3
    # emerald sprites in 3D
    for p, size in r.get("sprites", []):
        pr = cam.project(p, OW, OH)
        if pr is None:
            continue
        px = int(size / (pr[2] * cam.th) * OH / 2)
        if px >= 4:
            put(fr, EMERALD.resize((px, px * 13 // 16), Image.NEAREST), pr[0], pr[1])
    # nameplates
    for p, name in r.get("labels", []):
        pr = cam.project(p, OW, OH)
        if pr is None:
            continue
        sc_ = 3 if pr[2] < 9 else 2
        put(fr, text_img(name, (255, 255, 255), sc_, shadow=False, bg=70), pr[0], pr[1], "mb")
    # value labels (floating signs)
    icon_at = {tuple(np.round(p, 2)): s for p, s in r.get("icons", [])}
    for p, lines in r.get("values", []):
        pr = cam.project(p, OW, OH)
        if pr is None:
            continue
        y = pr[1]
        for i, (txt, col) in enumerate(lines):
            im = text_img(txt, col, 3 if i == 0 else 2, bg=120)
            put(fr, im, pr[0], y, "mb")
            if i == 0 and tuple(np.round(p, 2)) in icon_at:
                put(fr, big(EMERALD, 3), pr[0] + im.width / 2 + 30, y - im.height / 2)
            y -= im.height + 4
        # stack upwards: first line lowest
    if r.get("hud"):
        h = hud_img()
        fr.paste(h, (0, 0), h)
    # chat
    active = [(ct, txt, col) for ct, txt, col in chats if ct <= t < ct + 5.0]
    y = 800
    for ct, txt, col in reversed(active[-5:]):
        a = min(1.0, (ct + 5.0 - t) / 1.0)
        im = text_img(txt, col, 3, bg=110)
        put(fr, im, 16, y, "lb", alpha=a)
        y -= im.height
    for fn in r.get("overlays", []):
        fn(fr)
    # captions (action bar)
    for s0, s1, txt, _ in sc["sents"]:
        if s0 - 0.05 <= t <= s1 + 0.2:
            lines = wrap(txt, 1500, 3)
            base = 915 if r.get("hud") else 1000
            for i, ln in enumerate(reversed(lines)):
                put(fr, text_img(ln, (255, 255, 255), 3, bg=90), OW / 2, base - i * 50, "mb")
    arr = np.asarray(fr).astype(np.float32)
    if r.get("flash"):
        arr = arr * (1 - r["flash"]) + 255 * r["flash"]
    if t < 0.4:
        arr *= t / 0.4
    if r.get("black"):
        arr *= 1 - r["black"]
    return np.clip(arr, 0, 255).astype(np.uint8)


# ============================================================== parallel render
def _worker(args):
    idx, f0, f1, scenes = args
    wd = Worlds()
    chats = all_chats(scenes, wd)
    path_ = os.path.join(BUILD, f"part{idx:02d}.mp4")
    p = subprocess.Popen([FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                          "-pix_fmt", "yuv420p", path_], stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(compose(f / FPS, scenes, wd, chats).tobytes())
        if (f - f0) % 60 == 0:
            print(f"[part {idx}] frame {f - f0}/{f1 - f0}", flush=True)
    p.stdin.close()
    p.wait()
    return path_


def build_audio(scenes, total, wd):
    mix = np.zeros(int((total + 1) * SR))

    def add(sig, t, gain=1.0):
        s = int(t * SR)
        if s >= len(mix):
            return
        n = min(len(sig), len(mix) - s)
        mix[s:s + n] += sig[:n] * gain
    for sc in scenes:
        for s0, s1, _, p in sc["sents"]:
            add(load_audio(p), s0, 1.0)
    m = music(total)
    m = m / np.abs(m).max() * 0.12
    k = int(0.8 * SR)
    m[-k:] *= np.linspace(1, 0, k)
    add(m, 0)
    # sfx collected from scenes
    ev = set()
    for sc in scenes:
        for probe in np.arange(0, sc["dur"], 0.5):
            r = SCENE_FN[sc["name"]](probe, sc, wd)
            for e in r.get("sfx", []):
                ev.add((round(e[0], 3), e[1], round(e[2], 3)))
    for t, kind, arg in sorted(ev):
        if kind == "pop":
            add(sfx_pop(arg), t, 0.6)
        elif kind == "boom":
            add(sfx_boom(), t, 0.8)
        elif kind == "hiss":
            add(sfx_hiss(arg), t, 1.0)
        elif kind == "whoosh":
            add(sfx_whoosh(), t, 0.8)
        elif kind == "levelup":
            add(sfx_levelup(), t, 1.0)
        elif kind == "click":
            add(sfx_click(), t, 1.0)
    for ct, _, _ in all_chats(scenes, wd):
        add(sfx_click(), ct, 0.5)
    mix = mix[:int(total * SR)]
    mix = mix / max(1.0, np.abs(mix).max() / 0.95)
    wav = os.path.join(BUILD, "audio.f32")
    mix.astype(np.float32).tofile(wav)
    return wav


def main():
    os.makedirs(BUILD, exist_ok=True)
    tts_all()
    scenes = prep(timeline())
    total = scenes[-1]["t1"]
    print(f"total duration {total:.2f}s")
    for sc in scenes:
        print(f"  {sc['name']:9s} {sc['t0']:6.2f} -> {sc['t1']:6.2f}")
    if "--preview" in sys.argv:
        wd = Worlds()
        chats = all_chats(scenes, wd)
        os.makedirs(os.path.join(BUILD, "preview"), exist_ok=True)
        ts = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1:]] or \
             [sc["t0"] + sc["dur"] * k for sc in scenes for k in (0.3, 0.8)]
        for t in ts:
            Image.fromarray(compose(t, scenes, wd, chats)).save(os.path.join(BUILD, "preview", f"t{t:06.2f}.png"))
            print("preview", t)
        return
    nframes = int(total * FPS)
    nproc = int(os.environ.get("JOBS", os.cpu_count() or 4))
    chunk = math.ceil(nframes / nproc)
    jobs = [(i, i * chunk, min(nframes, (i + 1) * chunk), scenes) for i in range(nproc) if i * chunk < nframes]
    with Pool(len(jobs)) as pool:
        parts = pool.map(_worker, jobs)
    wav = build_audio(scenes, total, Worlds())
    lst = os.path.join(BUILD, "parts.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT],
                   check=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
