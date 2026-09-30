#!/usr/bin/env python3
"""Minecraft-style vertical explainer: how money laundering works (and gets caught).

    python3 render.py                 # full render -> money_laundering_minecraft.mp4
    python3 render.py --preview [t…]  # still frames in build/preview/
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

PACK = os.environ.get("PACK", "faithful")
IW, IH = 360, 780            # internal render size
OW, OH = 1080, 2340          # iPhone 15 Pro aspect (19.5:9)
E.configure(IW, IH, PACK)

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "money_laundering_minecraft.mp4")
PIXEL_FONT = os.path.join(HERE, "assets", "PixelifySans.ttf")
CAPTION_FONT = os.path.join(HERE, "assets", "Montserrat.ttf")
FPS = 30
SR = 44100
VOICE = "en-US-AndrewNeural"
RATE = "+6%"


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


FFMPEG = ffmpeg_exe()

# ============================================================== narration
SCENES = [
    ("intro", ["Money laundering is how criminals make dirty money look clean. It usually happens in three steps."]),
    ("dirty", ["A griefer steals a stack of emeralds. But spending them is risky, because everyone knows they're stolen."]),
    ("place", ["Step one: placement. He sneaks the emeralds into the system in small amounts, spread across different banks and shops."]),
    ("layer", ["Step two: layering. The emeralds bounce between fake companies and accounts, again and again, until the trail is a mess."]),
    ("integ", ["Step three: integration. The money comes back as profits from a legit-looking bakery, and he spends it on a mansion."]),
    ("flags", ["But banks look for red flags: lots of small deposits, businesses earning way more than they should, and money going in circles."]),
    ("caught", ["Investigators follow the trail back, and the whole scheme falls apart."]),
]
LEAD, GAP, SGAP, TAIL = 0.6, 0.25, 0.5, 2.0


def tts_all():
    os.makedirs(os.path.join(BUILD, "tts"), exist_ok=True)
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        import certifi
        certifi.where = lambda: ca
    import edge_tts

    async def one(text, mp3, js):
        c = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
        audio, words = bytearray(), []
        async for ch in c.stream():
            if ch["type"] == "audio":
                audio += ch["data"]
            elif ch["type"] == "WordBoundary":
                words.append((ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]))
        open(mp3, "wb").write(audio)
        json.dump(dict(key=text + VOICE + RATE, words=words), open(js, "w"))

    async def go():
        for si, (_, sents) in enumerate(SCENES):
            for k, s in enumerate(sents):
                mp3 = os.path.join(BUILD, "tts", f"{si}_{k}.mp3")
                js = mp3 + ".json"
                if os.path.exists(js) and json.load(open(js))["key"] == s + VOICE + RATE:
                    continue
                await one(s, mp3, js)
    asyncio.run(go())


def load_audio(path, with_trim=False):
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32).copy()
    nz = np.nonzero(np.abs(a) > 0.01)[0]
    s0 = max(0, nz[0] - 400) if len(nz) else 0
    out = a[s0:nz[-1] + 1200] if len(nz) else a
    return (out, s0 / SR) if with_trim else out


def attach_punct(sentence, words):
    """Map boundary words back onto the sentence so punctuation is kept."""
    out, cur = [], 0
    for off, dur, w in words:
        i = sentence.find(w, cur)
        if i < 0:
            out.append((off, dur, w))
            continue
        j = i + len(w)
        while j < len(sentence) and sentence[j] in ".,:;?!'\"":
            j += 1
        out.append((off, dur, sentence[i:j]))
        cur = j
    return out


def timeline():
    scenes, t = [], LEAD
    for si, (name, sents) in enumerate(SCENES):
        info = []
        for k, s in enumerate(sents):
            p = os.path.join(BUILD, "tts", f"{si}_{k}.mp3")
            a, trim = load_audio(p, True)
            d = len(a) / SR
            words = json.load(open(p + ".json"))["words"]
            words = [(t + off - trim, t + off - trim + dur, w) for off, dur, w in attach_punct(s, words)]
            info.append(dict(t0=t, t1=t + d, text=s, path=p, words=words))
            t += d + GAP
        scenes.append(dict(name=name, sents=info))
        t += SGAP - GAP
    for i, sc in enumerate(scenes):
        sc["t0"] = 0.0 if i == 0 else sc["sents"][0]["t0"] - 0.3
    for i, sc in enumerate(scenes):
        sc["t1"] = scenes[i + 1]["t0"] if i + 1 < len(scenes) else sc["sents"][-1]["t1"] + TAIL
        sc["dur"] = sc["t1"] - sc["t0"]
        sc["st"] = [s["t0"] - sc["t0"] for s in sc["sents"]]
        sc["en"] = [s["t1"] - sc["t0"] for s in sc["sents"]]
    return scenes


def caption_chunks(scenes):
    """Group words into short TikTok-style chunks: [(t0, t1, [(ws, we, word)])]."""
    chunks = []
    for sc in scenes:
        for s in sc["sents"]:
            cur = []
            for w in s["words"]:
                cur.append(w)
                text = " ".join(x[2] for x in cur)
                if len(cur) >= 4 or len(text) >= 20 or w[2][-1] in ".?!:":
                    chunks.append(cur)
                    cur = []
            if cur:
                chunks.append(cur)
    out = []
    for i, ch in enumerate(chunks):
        end = ch[-1][1] + 0.35
        if i + 1 < len(chunks):
            end = min(end, chunks[i + 1][0][0])
        out.append((ch[0][0] - 0.05, end, ch))
    return out


# ============================================================== 2D helpers
_PF = None
_CF = {}


def pfont():
    global _PF
    if _PF is None:
        _PF = ImageFont.truetype(PIXEL_FONT, 13)
    return _PF


def cfont(size, weight="ExtraBold"):
    k = (size, weight)
    if k not in _CF:
        f = ImageFont.truetype(CAPTION_FONT, size)
        f.set_variation_by_name(weight)
        _CF[k] = f
    return _CF[k]


@lru_cache(maxsize=2048)
def ptext(text, color=(255, 255, 255), scale=3, shadow=True, bg=0):
    """Minecraft-style pixel text (used for in-world labels and titles)."""
    f = pfont()
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


def big(img, s):
    return img.resize((img.width * s, img.height * s), Image.NEAREST)


@lru_cache(maxsize=32)
def block_icon(bid):
    """Small isometric block icon built from the pack's textures."""
    R = E.TEX.shape[2]
    top = Image.fromarray((E.TEX[bid, 0] * 255).astype(np.uint8)).resize((16, 16), Image.NEAREST)
    side = Image.fromarray((E.TEX[bid, 1] * 255).astype(np.uint8)).resize((16, 16), Image.NEAREST)
    S = 96
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c = S / 2

    def face(img, quad, shade):
        a = np.asarray(img, np.float32) * shade
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
        # quad: target corners TL, TR, BR, BL -> use perspective transform
        coeffs = _persp(quad, [(0, 0), (16, 0), (16, 16), (0, 16)])
        w = img.transform((S, S), Image.PERSPECTIVE, coeffs, Image.NEAREST)
        mask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(mask).polygon(quad, fill=255)
        out.paste(w, (0, 0), mask)
    h = S * 0.25
    face(top, [(c, 4), (S - 6, 4 + h), (c, 4 + 2 * h), (6, 4 + h)], 1.0)
    face(side, [(6, 4 + h), (c, 4 + 2 * h), (c, S - 4), (6, S - 4 - h)], 0.72)
    face(side, [(c, 4 + 2 * h), (S - 6, 4 + h), (S - 6, S - 4 - h), (c, S - 4)], 0.86)
    return out


def _persp(pa, pb):
    """Coefficients mapping output quad pa -> input quad pb (for PIL PERSPECTIVE)."""
    m = []
    for (x, y), (u, v) in zip(pa, pb):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    A = np.array(m, float)
    B = np.array(pb, float).reshape(8)
    return np.linalg.solve(A, B).tolist()


def slot_img(icon, count, flash=0.0, label=None):
    s = 6
    im = Image.new("RGBA", (20 * s, 20 * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 20 * s - 1, 20 * s - 1], fill=(139, 139, 139, 235))
    d.rectangle([0, 0, 20 * s - 1, s - 1], fill=(55, 55, 55, 255))
    d.rectangle([0, 0, s - 1, 20 * s - 1], fill=(55, 55, 55, 255))
    d.rectangle([0, 19 * s, 20 * s - 1, 20 * s - 1], fill=(255, 255, 255, 255))
    d.rectangle([19 * s, 0, 20 * s - 1, 20 * s - 1], fill=(255, 255, 255, 255))
    if flash > 0:
        d.rectangle([s, s, 19 * s - 1, 19 * s - 1], fill=(255, 60, 60, int(160 * flash)))
    ic = icon.resize((16 * s - 12, 16 * s - 12), Image.NEAREST) if icon.width != 16 * s - 12 else icon
    im.alpha_composite(ic, ((20 * s - ic.width) // 2, (20 * s - ic.height) // 2 - 4))
    col = (255, 90, 90) if count in (0, "??") else (255, 255, 255)
    t = ptext(str(count), col, 4)
    im.alpha_composite(t, (20 * s - t.width - 4, 20 * s - t.height + 2))
    if label:
        lab = ptext(label, (255, 255, 255), 3, bg=110)
        out = Image.new("RGBA", (max(im.width, lab.width), im.height + lab.height + 6), (0, 0, 0, 0))
        out.alpha_composite(im, ((out.width - im.width) // 2, 0))
        out.alpha_composite(lab, ((out.width - lab.width) // 2, im.height + 6))
        return out
    return im


def tooltip(w, h):
    im = Image.new("RGBA", (w, h), (16, 0, 16, 235))
    d = ImageDraw.Draw(im)
    d.rectangle([5, 5, w - 6, h - 6], outline=(80, 0, 255, 255), width=5)
    return im


def ctext(text, size, fill=(255, 255, 255), stroke=8, weight="ExtraBold"):
    f = cfont(size, weight)
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - l, 2 - t), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
    return im


def draw_caption(fr, t, chunks, y=1600):
    for c0, c1, words in chunks:
        if c0 <= t < c1:
            f = cfont(74)
            space = f.getlength(" ")
            widths = [f.getlength(w[2]) for w in words]
            # wrap to <= 900px
            lines, cur, cw = [], [], 0
            for i, wd in enumerate(widths):
                if cur and cw + space + wd > 900:
                    lines.append(cur)
                    cur, cw = [], 0
                cw += (space if cur else 0) + wd
                cur.append(i)
            lines.append(cur)
            pop = min(1.0, (t - c0) / 0.08)
            layer = Image.new("RGBA", (OW, 400), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            lh = 92
            for li, idxs in enumerate(lines):
                lw = sum(widths[i] for i in idxs) + space * (len(idxs) - 1)
                x = OW / 2 - lw / 2
                for i in idxs:
                    ws, we, w = words[i]
                    active = ws <= t < max(we, ws + 0.12)
                    fill = (255, 226, 60) if active else (255, 255, 255)
                    d.text((x, 20 + li * lh), w, font=f, fill=fill, stroke_width=9, stroke_fill=(0, 0, 0))
                    x += widths[i] + space
            s = 0.9 + 0.1 * pop
            if s < 1:
                layer = layer.resize((int(OW * s), int(400 * s)), Image.BILINEAR)
            put(fr, layer, OW / 2, y + 200 * s - 100, "mm")
            return


# ============================================================== audio
def piano(freq, dur, vel=1.0):
    t = np.arange(int(dur * SR)) / SR
    y = np.zeros_like(t)
    for k in range(1, 7):
        y += (1 / k ** 1.6) * np.sin(2 * np.pi * freq * k * t) * np.exp(-t * (1.2 + 0.9 * k))
    return y * np.minimum(1, t / 0.004) * vel


def reverb(x, secs=2.2, wet=0.3):
    rng = np.random.default_rng(5)
    n = int(secs * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 3.2)
    ir /= np.sqrt((ir ** 2).sum())
    nfft = 1 << (len(x) + n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft), nfft)[:len(x)]
    return x * (1 - wet) + y * wet * 3


def music(dur):
    rng = np.random.default_rng(21)
    out = np.zeros(int((dur + 4) * SR))
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    chords = [[45, 52, 60, 64], [41, 48, 57, 64], [48, 55, 64, 67], [43, 50, 59, 62]]
    scale = [57, 60, 62, 64, 67, 69, 72, 74, 76]
    t, ci = 0.0, 0
    while t < dur:
        for k, n in enumerate(chords[ci % 4]):
            s = int((t + k * 0.05) * SR)
            nt = piano(midi(n), 4.0, 0.35)
            out[s:s + len(nt)] += nt[:len(out) - s]
        for b in range(8):
            if rng.random() < 0.6:
                s = int((t + b * 0.5) * SR)
                nt = piano(midi(scale[rng.integers(len(scale))]), 2.2, 0.42)
                out[s:s + len(nt)] += nt[:len(out) - s]
        t += 4.0
        ci += 1
    return reverb(out)[:int(dur * SR)]


def sfx_pop(pitch=1.0):
    t = np.arange(int(0.09 * SR)) / SR
    f = 700 * pitch * (1 + 2 * np.exp(-t * 60))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 40) * 0.35


def sfx_coin(pitch=1.0):
    t = np.arange(int(0.25 * SR)) / SR
    y = np.sin(2 * np.pi * 1318 * pitch * t) * (t < 0.07) + np.sin(2 * np.pi * 1760 * pitch * t) * (t >= 0.07)
    return y * np.exp(-t * 14) * 0.18


def sfx_chime():
    out = np.zeros(int(1.2 * SR))
    for i, n in enumerate([72, 76, 79, 84]):
        s = int(i * 0.08 * SR)
        t = np.arange(int(0.8 * SR)) / SR
        f = 440 * 2 ** ((n - 69) / 12)
        y = np.sin(2 * np.pi * f * t) * np.exp(-t * 5) * 0.2
        out[s:s + len(y)] += y[:len(out) - s]
    return out


def sfx_thud():
    t = np.arange(int(0.5 * SR)) / SR
    return np.sin(2 * np.pi * 70 * t * (1 - 0.4 * t)) * np.exp(-t * 9) * 0.7


def sfx_whoosh():
    rng = np.random.default_rng(6)
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    x = np.convolve(rng.standard_normal(n), np.ones(30) / 30, mode="same")
    return x * np.sin(np.pi * t / 0.7) ** 2 * 1.2


# ============================================================== scene helpers
def ss(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return np.asarray(a, float) * (1 - k) + np.asarray(b, float) * k


def path(lt, keys):
    if lt <= keys[0][0]:
        return E.Camera(keys[0][1], keys[0][2], keys[0][3])
    for a, b in zip(keys, keys[1:]):
        if lt <= b[0]:
            k = ss((lt - a[0]) / (b[0] - a[0]))
            return E.Camera(lerp(a[1], b[1], k), lerp(a[2], b[2], k), a[3] * (1 - k) + b[3] * k)
    return E.Camera(keys[-1][1], keys[-1][2], keys[-1][3])


def walk_path(lt, pts, speed=3.0):
    """Position/yaw/phase along a polyline starting at lt=0."""
    d = lt * speed
    for a, b in zip(pts, pts[1:]):
        seg = float(np.linalg.norm(np.subtract(b, a)))
        if d <= seg:
            k = d / seg
            return lerp(a, b, k), yaw_to(a, b), lt * 9
        d -= seg
    return np.asarray(pts[-1], float), yaw_to(pts[-2], pts[-1]), 0.0


def path_len(pts):
    return sum(float(np.linalg.norm(np.subtract(b, a))) for a, b in zip(pts, pts[1:]))


def yaw_to(a, b):
    return math.atan2(b[0] - a[0], b[2] - a[2])


def fade(lt, t0, t1, f=0.25):
    if lt < t0 or lt > t1:
        return 0.0
    return min(1.0, (lt - t0) / f, (t1 - lt) / f)


def burst(t_since, seed, center, n, colors, speed=3.0, life=1.0, size=0.15, grav=-5.0, up=1.5):
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


def sparkles(lt, seed, lo, hi, n=26, color=(0.7, 1.0, 1.0)):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        ph = rng.random() * 2
        k = ((lt + ph) % 2.0) / 2.0
        p = lerp(lo, hi, rng.random(3))
        p[1] = lo[1] + k * (hi[1] - lo[1]) * 1.5
        out.append((p, color, 0.12 * (1 - k) + 0.04))
    return out


GRIEFER_SK = W.skin_set("griefer")
SUIT_SK = W.skin_set("suitgriefer")
GOLEM_SK = W.golem_set()
VILL_SK = [W.villager_set((0.47, 0.32, 0.18)), W.villager_set((0.25, 0.45, 0.28))]
STASH_C = (80.5, 13.0, 101.5)
G_HOME = (82.4, 12.0, 99.0)


def dirty_emerald():
    a = np.asarray(EMERALD).astype(np.float32)
    rgb = a[..., :3] * np.array((0.55, 0.45, 0.45)) + np.array((70, 0, 0))
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a[..., 3]]).astype(np.uint8), "RGBA")


DIRTY = dirty_emerald()


def inv(dirty, clean, fd=0.0, fc=0.0):
    return [(DIRTY, dirty, fd, "DIRTY"), (EMERALD, clean, fc, "CLEAN")]


def word_t(S, prefix, k=0):
    """Local time of the k-th spoken word starting with prefix."""
    hits = [w[0] for s in S["sents"] for w in s["words"] if w[2].lower().strip(",.:?!'\"").startswith(prefix)]
    return hits[min(k, len(hits) - 1)] - S["t0"] if hits else 0.0


def step_card(n, name, alpha):
    im = Image.new("RGBA", (820, 250), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 819, 249], 36, fill=(12, 12, 20, 215))
    im.alpha_composite(ctext(f"STEP {n} OF 3", 44, (255, 226, 60), stroke=0, weight="Bold"), (48, 30))
    im.alpha_composite(ctext(name, 86, stroke=0, weight="Black"), (44, 92))
    for i in range(3):
        x = 700 + (i - 1) * 50
        d.ellipse([x - 14, 48, x + 14, 76], fill=(255, 226, 60) if i < n else (80, 80, 100))
    if alpha < 1:
        a = np.array(im.getchannel("A"), np.float32) * alpha
        im.putalpha(Image.fromarray(a.astype(np.uint8)))
    return im


def shot_cam(lt, shots, blend=0.5, push=0.16):
    """shots: [(t_start, cam_pos, target, fov)] sorted. Eases between shots, slow push-in within a shot."""
    def at(i):
        t0, pos, tgt, fov = shots[i]
        pos, tgt = np.asarray(pos, float), np.asarray(tgt, float)
        k = 1 - push * ss((lt - t0) / 4.0)
        return tgt + (pos - tgt) * k, tgt, fov
    i = 0
    while i + 1 < len(shots) and lt >= shots[i + 1][0]:
        i += 1
    pos, tgt, fov = at(i)
    if i > 0 and lt - shots[i][0] < blend:
        k = ss((lt - shots[i][0]) / blend)
        p0, t0_, f0 = at(i - 1)
        pos, tgt, fov = lerp(p0, pos, k), lerp(t0_, tgt, k), f0 * (1 - k) + fov * k
    return E.Camera(pos, tgt, fov)


def around(subject, yaw, dist, height, look_up=0.0):
    """Camera placed `dist` blocks from subject in direction `yaw`, looking at it."""
    s_ = np.asarray(subject, float)
    return (s_ + np.array((math.sin(yaw) * dist, height, math.cos(yaw) * dist)), s_ + np.array((0, look_up, 0)))


def arc(a, b, k, h=2.5):
    return lerp(a, b, k) + np.array((0, h * math.sin(math.pi * k), 0))


def scene_intro(lt, S, wd):
    D = S["dur"]
    gy = math.pi * 0.85
    face = np.add(G_HOME, (0, 1.55, 0))
    tc, td, t3 = word_t(S, "criminals"), word_t(S, "dirty"), word_t(S, "three")
    shots = [(0, (66, 40, 70), (96, 14, 96), 80), (0.01, (74, 36, 74), (94, 14, 96), 80),
             (tc - 0.1, *around(face, gy, 2.4, 0.25), 58),
             (td - 0.1, *around(STASH_C, 2.35, 5.4, 2.2), 62),
             (t3 - 0.2, (80, 30, 80), (96, 14, 96), 78)]
    cam = shot_cam(lt, shots)
    boxes = W.player(GRIEFER_SK, G_HOME, gy, head_yaw=0.25 * math.sin(lt * 2))
    a = fade(lt, 0.3, tc - 0.1, 0.3)

    def title(fr):
        put(fr, ptext("MONEY", (235, 235, 235), 12), OW / 2, 330, alpha=a)
        put(fr, ptext("LAUNDERING", (85, 255, 85), 10), OW / 2, 500, alpha=a)
        put(fr, ctext("explained in 3 steps", 58), OW / 2, 640, alpha=a)
    return dict(cam=cam, boxes=boxes, blobs=[(G_HOME[0], G_HOME[2], 0.6)], grid=wd.base, overlays=[title])


def scene_dirty(lt, S, wd):
    D = S["dur"]
    look = lt > word_t(S, "everyone") - 0.3
    gy0 = yaw_to(G_HOME, (88, 12, 93))
    face = np.add(G_HOME, (0, 1.55, 0))
    vmid = (86.0, 13.6, 98.6)
    shots = [(0, *around(face, gy0, 2.6, 0.3), 58),
             (word_t(S, "stack") - 0.1, *around(STASH_C, 2.35, 3.8, 1.5), 60),
             (word_t(S, "risky") - 0.1, *around(face, gy0, 3.6, 0.8), 62),
             (word_t(S, "everyone") - 0.25, (83.4, 13.9, 96.6), vmid, 62),
             (word_t(S, "stolen") - 0.1, (88.5, 16.5, 91.5), (81, 13.2, 100.5), 70)]
    cam = shot_cam(lt, shots)
    boxes = W.player(GRIEFER_SK, G_HOME, yaw_to(G_HOME, (88, 12, 93)), head_yaw=0.5 * math.sin(lt * 3) if look else 0.0)
    vpos = [(85.6, 12.0, 99.8), (86.4, 12.0, 97.4)]
    for i, (sk, p) in enumerate(zip(VILL_SK, vpos)):
        yw = yaw_to(p, G_HOME) if look else yaw_to(p, (95, 12, 90))
        boxes += W.villager(sk, p, yw)
    vals = [((80.5, 14.9, 101.5), [("STOLEN EMERALDS", (255, 85, 85))], DIRTY)]
    if look:
        for p in vpos:
            vals.append((np.add(p, (0, 2.9, 0)), [("!", (255, 226, 60))], None))
    labels = [(np.add(G_HOME, (0, 2.3, 0)), "Griefer", (255, 255, 255))]
    blobs = [(G_HOME[0], G_HOME[2], 0.6)] + [(p[0], p[2], 0.6) for p in vpos]
    return dict(cam=cam, boxes=boxes, blobs=blobs, grid=wd.base, values=vals, labels=labels,
                inv=inv(64, 0) if lt > 0.6 else None, sfx=[(S["t0"] + word_t(S, "everyone"), "thud", 1)])


PLACE_ROUTE = [(79.5, 12.0, 88.5), (84.0, 12.0, 85.6), (94.0, 12.0, 85.6), (103.2, 12.0, 85.6)]


def scene_place(lt, S, wd):
    D = S["dur"]
    t_small, t_diff, t_shops = word_t(S, "small"), word_t(S, "different"), word_t(S, "shops")
    doors = [W.door_of(b) for b in W.BANKS]
    stand = [np.add(d, (-0.9, 0, 0.5)) for d in doors]
    route = [(79.5, 12.0, 88.5), (82.0, 12.0, 85.9), tuple(stand[0])]
    speed = path_len(route) / max(1.0, t_small - 0.5)
    visits = [(t_small, 0), (t_diff, 1), (t_shops, 2)]
    if lt < t_small:
        gp, gyaw, gw = walk_path(max(0.0, lt - 0.3), route, speed)
    else:
        vi = max(i for tt, i in visits if lt >= tt - 0.05)
        gp, gyaw, gw = np.array(stand[vi]), yaw_to(stand[vi], doors[vi]), 0.0
    shots = [(0, gp + np.array((1.4, 2.4, 5.0)), gp + np.array((0.8, 1.2, -2.0)), 64)]
    for tt, i in visits:
        d = np.array(doors[i])
        shots.append((tt - 0.12, d + np.array((1.2, 1.7, 4.4)), d + np.array((-0.9, 1.1, -0.6)), 62))
    shots.append((S["en"][0] - 0.2, (94.0, 20.5, 96.5), (94.0, 14.0, 81.0), 70))
    cam = shot_cam(lt, shots, blend=0.35)
    boxes = W.player(GRIEFER_SK, gp, gyaw, walk=gw)
    sprites_, vals, sfx = [], [], []
    dirty = 64
    for tt, i in visits:
        door = doors[i]
        for j in range(4):
            tj = tt + 0.15 + j * 0.14
            k = (lt - tj) / 0.55
            if 0 <= k < 1:
                sprites_.append((arc(np.add(stand[i], (0.2, 1.2, 0)), np.add(door, (0, 1.0, -1.2)), k, 0.9), 0.3, DIRTY))
            sfx.append((S["t0"] + tj + 0.5, "coin", 0.9 + 0.05 * j))
            if lt > tj + 0.55:
                dirty -= 4
        if lt > tt + 0.4:
            vals.append((W.top_of(W.BANKS[i], -1.2), [("+ small deposit", (255, 255, 255))], None))
    labels = [(np.add(gp, (0, 2.3, 0)), "Griefer", (255, 255, 255))]
    for b in W.BANKS:
        labels.append((W.top_of(b, 1.0), b[0], (255, 226, 60)))
    ca = fade(lt, 0.1, D + 1, 0.3)

    def card(fr):
        put(fr, step_card(1, "PLACEMENT", ca), OW / 2, 330)
    return dict(cam=cam, boxes=boxes, blobs=[(gp[0], gp[2], 0.6)], grid=wd.base, values=vals, labels=labels,
                sprites=sprites_, overlays=[card], inv=inv(dirty, 0), sfx=sfx)


NODES = [W.BANKS[0], W.SHELLS[0], W.SHELLS[2], W.BANKS[2], W.SHELLS[1], W.SHELLS[3], W.BANKS[1], W.SHELLS[0],
         W.SHELLS[2], W.SHELLS[1], W.BANKS[0], W.SHELLS[3]]


def scene_layer(lt, S, wd):
    D = S["dur"]
    sprites_, sfx, segs = [], [], []
    lead = None
    hop = 0.55
    for stream in range(3):
        off = stream * 4
        t_s = lt - 0.5 - stream * 0.35
        if t_s < 0:
            continue
        n = int(t_s / hop)
        k = (t_s % hop) / hop
        for h in range(n + 1):
            a_ = NODES[(off + h) % len(NODES)]
            b_ = NODES[(off + h + 1) % len(NODES)]
            if h == n:
                q = arc(W.top_of(a_, 0), W.top_of(b_, 0), k, 4.0)
                sprites_.append((q, 0.9, DIRTY))
                if stream == 0:
                    lead = q
            else:
                segs.append((W.top_of(a_, 0), W.top_of(b_, 0), t_s - (h + 1) * hop))
        if k < 0.1 and stream == 0:
            sfx.append((S["t0"] + lt, "whoosh", 1))
    for h in range(40):
        sfx.append((S["t0"] + 0.5 + h * hop, "coin", 0.8 + 0.02 * (h % 8)))
    labels = [(W.top_of(b, 1.8), b[0], (255, 226, 60) if "Shell" in b[0] or "Offshore" in b[0] else (255, 255, 255))
              for b in W.SHELLS + W.BANKS]
    if lead is None:
        lead = np.array(W.top_of(NODES[0], 0))
    c = np.array((97.0, 12.0, 95.0))
    a = 0.18 * lt
    chase = (lead + np.array((5.5, 3.5, -6.0)), lead)
    s1 = W.SHELLS[0]
    fac = np.array(W.door_of(s1))
    shots = [(0, *chase, 66), (word_t(S, "fake") - 0.15, fac + np.array((-8.5, 4.5, -4.0)), fac + np.array((2.5, 2.2, 0)), 66),
             (word_t(S, "again") - 0.15, *chase, 66),
             (word_t(S, "trail") - 0.2, c + np.array((-20 * math.sin(0.5 + a), 36, -20 * math.cos(0.5 + a))), c, 80)]
    cam = shot_cam(lt, shots, blend=0.45, push=0.0)
    ca = fade(lt, 0.1, D + 1, 0.3)

    def web(fr):
        lay = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for p, q, age in segs:
            a1, b1 = cam.project(p, OW, OH), cam.project(q, OW, OH)
            if a1 is None or b1 is None:
                continue
            al = int(230 * max(0.35, 1 - age / 6))
            d.line([a1[:2], b1[:2]], fill=(255, 70, 70, al), width=7)
        fr.paste(lay, (0, 0), lay)
        put(fr, step_card(2, "LAYERING", ca), OW / 2, 330)
    return dict(cam=cam, boxes=[], grid=wd.base, labels=labels, sprites=sprites_, overlays=[web],
                inv=inv("??", 0), sfx=sfx)


def scene_integ(lt, S, wd):
    D = S["dur"]
    t_bak = word_t(S, "profits")
    t_spend = word_t(S, "spends")
    t_man = word_t(S, "mansion")
    bak_door = W.door_of(W.BAKERY)
    route = [(bak_door[0] - 1.0, 12.0, bak_door[2]), (108.8, 12.0, 88.0), (109.5, 12.0, 98.5), (115.2, 12.0, 99.0)]
    tw = lt - t_spend
    gp, gyaw, gw = walk_path(max(0.0, tw), route, 3.2)
    if tw < 0:
        gyaw = yaw_to(route[0], bak_door)
    bd = np.array(bak_door)
    shots = [(0, bd + np.array((-4.8, 2.2, 3.4)), bd + np.array((0.2, 1.2, 0)), 62),
             (word_t(S, "legit") - 0.15, (103.8, 17.0, 86.0), (113.5, 14.2, 80.5), 66),
             (t_spend - 0.15, gp + np.array((-1.6, 1.9, 3.6)), gp + np.array((0, 1.45, 0)), 58),
             (t_man - 0.2, (103.8, 23.5, 97.6), (119.5, 14.5, 99.0), 76)]
    cam = shot_cam(lt, shots, blend=0.45)
    boxes = W.player(SUIT_SK, gp, gyaw, walk=gw if tw > 0 else 0.0)
    sprites_, sfx = [], []
    clean = 0
    for j in range(8):
        tj = word_t(S, "money") + 0.1 + j * 0.2
        k = (lt - tj) / 0.6
        if 0 <= k < 1:
                sprites_.append((arc(np.add(bak_door, (1.0, 1.2, 0)), np.add(route[0], (0, 1.2, 0)), k, 1.5), 0.3, EMERALD))
        if lt > tj + 0.6:
            clean += 8
        sfx.append((S["t0"] + tj + 0.6, "coin", 1.0 + 0.04 * j))
    g = wd.base
    mb = W.mansion_blocks()
    kb = int(len(mb) * ss((lt - t_man + 0.6) / 3.2))
    if kb > 0:
        g = wd.base.copy()
        for x, y, z, b in mb[:kb]:
            g[x, y, z] = b
    for i in range(0, 12):
        sfx.append((S["t0"] + t_man - 0.6 + i * 0.27, "pop", 0.9 + 0.03 * i))
    vals = [(W.top_of(W.BAKERY, 1.9), [(W.BAKERY[0], (255, 226, 60))], None)]
    if lt > t_bak:
        vals.append((W.top_of(W.BAKERY, 0.5), [("'Profits': +64", (85, 255, 85))], EMERALD))
    if kb > 40:
        vals.append(((120.5, 21.5, 99.0), [("New mansion", (255, 255, 255))], None))
    ca = fade(lt, 0.1, D + 1, 0.3)

    def card(fr):
        put(fr, step_card(3, "INTEGRATION", ca), OW / 2, 330)
    labels = [(np.add(gp, (0, 2.3, 0)), "Griefer", (255, 255, 255))]
    return dict(cam=cam, boxes=boxes, blobs=[(gp[0], gp[2], 0.6)], grid=g, values=vals, labels=labels,
                sprites=sprites_, overlays=[card], inv=inv(0, min(64, clean)), sfx=sfx)


FLAG_ROWS = [("Lots of small deposits", "red", W.BANKS),
             ("Earning way more than it should", "earning", [W.BAKERY]),
             ("Money going in circles", "circles", W.SHELLS)]


def scene_flags(lt, S, wd):
    D = S["dur"]
    shots = [(0, (89.5, 15.0, 91.5), (85.5, 14.5, 80.5), 62),
             (word_t(S, "red") - 0.15, (90.2, 20.8, 88.0), (85.8, 17.6, 80.4), 62),
             (word_t(S, "small") - 0.15, (94.0, 23.0, 94.0), (94.0, 15.0, 80.0), 70),
             (word_t(S, "earning") - 0.15, (109.5, 20.0, 86.8), (115.5, 17.5, 80.4), 60),
             (word_t(S, "circles") - 0.15, (98.0, 33.0, 96.0), (108.5, 14.0, 99.0), 78)]
    cam = shot_cam(lt, shots, blend=0.4)
    g = wd.mansion.copy()
    sfx, vals = [], []
    for name, key, blds in FLAG_ROWS:
        tk = word_t(S, key) - 0.2
        sfx.append((S["t0"] + tk, "thud", 1))
        if lt > tk:
            for b in blds:
                for p, bid in W.red_flag_blocks(b):
                    g[p] = bid
                vals.append((W.top_of(b, 3.3), [("RED FLAG", (255, 85, 85))], None))

    def panel(fr):
        for i, (name, key, _) in enumerate(FLAG_ROWS):
            a = fade(lt, word_t(S, ("small", "earning", "circles")[i]) - 0.2, D + 1, 0.25)
            if a <= 0:
                continue
            row = Image.new("RGBA", (980, 120), (0, 0, 0, 0))
            d = ImageDraw.Draw(row)
            d.rounded_rectangle([0, 0, 979, 119], 28, fill=(15, 15, 22, 220))
            d.rectangle([40, 26, 46, 96], fill=(230, 230, 230))
            d.polygon([(46, 26), (100, 40), (46, 56)], fill=(235, 50, 50))
            row.alpha_composite(ctext(name, 46, stroke=0, weight="Bold"), (126, 32))
            put(fr, row, OW / 2, 300 + i * 145, alpha=a)
    return dict(cam=cam, boxes=W.player(SUIT_SK, (115.2, 12.0, 99.0), -math.pi / 2), grid=g, values=vals,
                overlays=[panel], inv=inv(0, 64), sfx=sfx)


def scene_caught(lt, S, wd):
    D = S["dur"]
    en = S["en"][0]
    gpos = np.array((115.2, 12.0, 99.0))
    route = [(100.0, 12.0, 92.0), (109.0, 12.0, 95.5), (113.0, 12.0, 98.4)]
    gp_, gyaw, gw = walk_path(lt, route, 3.2)
    fwd = np.array((math.sin(gyaw), 0, math.cos(gyaw)))
    gface = gp_ + np.array((0, 2.6, 0))
    shots = [(0, gface + fwd * 4.4 + np.array((0.8, 0.3, 0)), gface - np.array((0, 0.4, 0)), 60),
             (word_t(S, "trail") - 0.15, (103.8, 16.6, 97.6), (115.5, 14.2, 99.0), 68),
             (word_t(S, "scheme") - 0.15, (103.4, 23.0, 97.6), (119.5, 15.0, 99.0), 76)]
    cam = shot_cam(lt, shots, blend=0.45)
    boxes = W.iron_golem(GOLEM_SK, gp_, gyaw, gw * 0.6)
    arrive = path_len(route) / 3.2
    boxes += W.player(SUIT_SK, gpos, yaw_to(gpos, gp_), arm_r=-2.9 if lt > arrive else None, arm_l=-2.9 if lt > arrive else None)
    g = wd.flags
    mb = W.mansion_blocks()
    t_fall = word_t(S, "falls") - 0.2
    parts, sfx = [], [(S["t0"] + t_fall, "thud", 1)]
    kb = int(len(mb) * ss((lt - t_fall) / 1.6))
    if kb > 0:
        g = wd.flags.copy()
        for x, y, z, b in mb[::-1][:kb]:
            g[x, y, z] = E.AIR
        parts = burst(lt - t_fall, 9, (120.5, 16, 99), 70, [(0.95, 0.93, 0.88), (0.98, 0.82, 0.24)], speed=5, life=1.6, size=0.3)
    seized = lt > t_fall
    labels = [(np.add(gp_, (0, 3.0, 0)), "Investigator", (255, 255, 255)), (np.add(gpos, (0, 2.3, 0)), "Griefer", (255, 255, 255))]
    vals = [(np.add(gpos, (0, 2.9, 0)), [("SEIZED", (255, 85, 85))], None)] if seized else []
    ta = fade(lt, en + 0.2, D + 5, 0.4)

    def title(fr):
        put(fr, ptext("FOLLOW", (235, 235, 235), 11), OW / 2, 360, alpha=ta)
        put(fr, ptext("THE MONEY", (85, 255, 85), 10), OW / 2, 520, alpha=ta)
    black = min(1.0, max(0.0, (lt - (D - 0.8)) / 0.8))
    fl = 0.5 + 0.5 * math.sin(lt * 10) if seized else 0.0
    return dict(cam=cam, boxes=boxes, blobs=[(gp_[0], gp_[2], 0.9), (gpos[0], gpos[2], 0.6)], grid=g, labels=labels,
                values=vals, particles=parts, overlays=[title], black=black, inv=inv(0, 0 if seized else 64, 0, fl),
                sfx=sfx + [(S["t0"] + en + 0.2, "chime", 1)])


class Worlds:
    def __init__(self):
        self.base = W.build_base()
        self.mansion = self.base.copy()
        for x, y, z, b in W.mansion_blocks():
            self.mansion[x, y, z] = b
        self.flags = self.mansion.copy()
        for _, _, blds in FLAG_ROWS:
            for b in blds:
                for p, bid in W.red_flag_blocks(b):
                    self.flags[p] = bid


SCENE_FN = dict(intro=scene_intro, dirty=scene_dirty, place=scene_place, layer=scene_layer,
                integ=scene_integ, flags=scene_flags, caught=scene_caught)



# ============================================================== composition
def scene_at(t, scenes):
    for sc in scenes:
        if sc["t0"] <= t < sc["t1"]:
            return sc
    return scenes[-1]


def draw_particles(img, depth, cam, parts):
    for p, c, size in parts:
        pr = cam.project(p)
        if pr is None:
            continue
        x, y, dist = pr
        px = max(1, int(size / (dist * cam.th) * IH / 2))
        xi, yi = int(x), int(y)
        if not (0 <= xi < IW and 0 <= yi < IH) or depth[yi, xi] < dist:
            continue
        img[max(0, yi - px // 2):yi + (px + 1) // 2, max(0, xi - px // 2):xi + (px + 1) // 2] = c


def compose(t, scenes, wd, chunks):
    sc = scene_at(t, scenes)
    lt = t - sc["t0"]
    r = SCENE_FN[sc["name"]](lt, sc, wd)
    cam = r["cam"]
    img, depth = E.render(r["grid"], cam, t, r.get("boxes", []), r.get("blobs", []))
    draw_particles(img, depth, cam, r.get("particles", []))
    img = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    fr = Image.fromarray(np.repeat(np.repeat(img, 3, 0), 3, 1), "RGB")
    for p, size, spr in r.get("sprites", []):
        pr = cam.project(p, OW, OH)
        if pr is None:
            continue
        px = int(size / (pr[2] * cam.th) * OH / 2)
        if px >= 6:
            put(fr, spr.resize((px, px * 13 // 16), Image.NEAREST), pr[0], pr[1])
    for p, name, col in r.get("labels", []):
        pr = cam.project(p, OW, OH)
        if pr is None:
            continue
        put(fr, ptext(name, col, 3 if pr[2] < 14 else 2, shadow=False, bg=80), pr[0], pr[1], "mb")
    for p, lines, icon in r.get("values", []):
        pr = cam.project(p, OW, OH)
        if pr is None:
            continue
        y = pr[1]
        for i, (txt, col) in enumerate(lines):
            im = ptext(txt, col, 4 if i == 0 else 3, bg=130)
            x = min(max(pr[0], im.width / 2 + 20), OW - im.width / 2 - 20 - (60 if icon is not None and i == 0 else 0))
            put(fr, im, x, y, "mb")
            if i == 0 and icon is not None:
                put(fr, big(icon, 3), x + im.width / 2 + 34, y - im.height / 2)
            y -= im.height + 6
    if r.get("inv"):
        items = r["inv"]
        slots = [slot_img(ic, n, fl, lb) for ic, n, fl, lb in items]
        sw = slots[0].width
        gap = 40
        total = len(slots) * sw + (len(slots) - 1) * gap
        x0 = (OW - total) // 2
        y0 = 1840
        for i, s_ in enumerate(slots):
            fr.paste(s_, (x0 + i * (sw + gap), y0), s_)
    for fn in r.get("overlays", []):
        fn(fr)
    draw_caption(fr, t, chunks, 1560)
    arr = np.asarray(fr).astype(np.float32)
    if t < 0.4:
        arr *= t / 0.4
    if r.get("black"):
        arr *= 1 - r["black"]
    return np.clip(arr, 0, 255).astype(np.uint8)


def _worker(args):
    idx, f0, f1, scenes = args
    E.configure(IW, IH, PACK)
    wd = Worlds()
    chunks = caption_chunks(scenes)
    out = os.path.join(BUILD, f"part{idx:02d}.mp4")
    p = subprocess.Popen([FFMPEG, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(compose(f / FPS, scenes, wd, chunks).tobytes())
        if (f - f0) % 60 == 0:
            print(f"[part {idx}] frame {f - f0}/{f1 - f0}", flush=True)
    p.stdin.close()
    p.wait()
    return out


def build_audio(scenes, total, wd):
    mix = np.zeros(int((total + 1) * SR))

    def add(sig, t, gain=1.0):
        s = int(t * SR)
        if s >= len(mix) or s < 0:
            return
        n = min(len(sig), len(mix) - s)
        mix[s:s + n] += sig[:n] * gain
    for sc in scenes:
        for s in sc["sents"]:
            add(load_audio(s["path"]), s["t0"])
    m = music(total)
    m = m / np.abs(m).max() * 0.11
    k = int(0.8 * SR)
    m[-k:] *= np.linspace(1, 0, k)
    add(m, 0)
    ev = set()
    for sc in scenes:
        for probe in np.arange(0, sc["dur"], 0.5):
            for e in SCENE_FN[sc["name"]](probe, sc, wd).get("sfx", []):
                ev.add((round(e[0], 3), e[1], round(e[2], 3)))
    for t, kind, arg in sorted(ev):
        sig = dict(pop=lambda: sfx_pop(arg), coin=lambda: sfx_coin(arg), chime=sfx_chime,
                   thud=sfx_thud, whoosh=sfx_whoosh)[kind]()
        add(sig, t, 0.6 if kind == "pop" else 1.0)
    mix = mix[:int(total * SR)]
    mix = mix / max(1.0, np.abs(mix).max() / 0.95)
    wav = os.path.join(BUILD, "audio.f32")
    mix.astype(np.float32).tofile(wav)
    return wav


def main():
    os.makedirs(BUILD, exist_ok=True)
    tts_all()
    scenes = timeline()
    total = scenes[-1]["t1"]
    print(f"total duration {total:.2f}s")
    for sc in scenes:
        print(f"  {sc['name']:7s} {sc['t0']:6.2f} -> {sc['t1']:6.2f}")
    if "--preview" in sys.argv:
        wd = Worlds()
        chunks = caption_chunks(scenes)
        os.makedirs(os.path.join(BUILD, "preview"), exist_ok=True)
        ts = [float(x) for x in sys.argv[sys.argv.index("--preview") + 1:]] or \
             [sc["t0"] + sc["dur"] * k for sc in scenes for k in (0.35, 0.8)]
        for t in ts:
            Image.fromarray(compose(t, scenes, wd, chunks)).save(os.path.join(BUILD, "preview", f"t{t:06.2f}.png"))
            print("preview", round(t, 2), flush=True)
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
    master = os.path.join(BUILD, "master.mp4")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", master], check=True)
    # two-pass encode to a shareable size (~25 MB)
    common = [FFMPEG, "-y", "-v", "error", "-i", master, "-c:v", "libx264", "-preset", "slow", "-b:v", "3200k"]
    subprocess.run(common + ["-pass", "1", "-passlogfile", os.path.join(BUILD, "x264"), "-an", "-f", "mp4", os.devnull], check=True)
    subprocess.run(common + ["-pass", "2", "-passlogfile", os.path.join(BUILD, "x264"), "-pix_fmt", "yuv420p",
                             "-c:a", "copy", "-movflags", "+faststart", OUT], check=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
