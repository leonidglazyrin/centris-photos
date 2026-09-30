#!/usr/bin/env python3
"""Minecraft-style vertical explainer: taxing corporations on unrealized gains.

    python3 render.py                 # full render -> corporate_unrealized_gains_minecraft.mp4
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

PACK = os.environ.get("PACK", "barebones")
IW, IH = 360, 780            # internal render size
OW, OH = 1080, 2340          # iPhone 15 Pro aspect (19.5:9)
E.configure(IW, IH, PACK)

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "corporate_unrealized_gains_minecraft.mp4")
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
    ("intro", ["What if companies had to pay tax on gains they haven't cashed in yet? Here's why that gets messy, fast."]),
    ("business", ["Meet Blockworks. It makes diamond tools in its factory, and sells them at the market.",
                  "This year it sold 300 emeralds of tools, paid its workers and materials, and made 100 emeralds of profit.",
                  "It pays normal tax on that profit, and keeps 80 emeralds of cash."]),
    ("vault", ["It also keeps a vault of 50 diamond blocks, the raw material for next year's tools.",
               "This year, diamond prices doubled. On paper, the vault went from 1,000 emeralds to 2,000."]),
    ("bill", ["Under an unrealized gains tax, that 1,000 emerald paper gain gets taxed too: 20 percent, so 200 emeralds.",
              "But the gain isn't cash. Blockworks only has 80 emeralds, and those were meant for wages and new equipment."]),
    ("sell", ["So it has to sell things it needs: diamonds, iron, even part of its factory, just to cover the missing 120."]),
    ("cycle", ["Next year, with fewer materials and a smaller factory, it makes fewer tools and earns less.",
               "If diamond prices rise again, there's a new paper gain, a new tax bill bigger than its cash, and more selling."]),
    ("cost", ["Year after year, the company shrinks: less production, fewer jobs, less investment, to pay tax on value it never actually received."]),
    ("outro", ["Today, companies pay tax on a gain when they sell the asset, because that's when the money is real."]),
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
    col = (255, 90, 90) if count == 0 else (255, 255, 255)
    t = ptext(str(count), col, 4)
    im.alpha_composite(t, (20 * s - t.width - 4, 20 * s - t.height + 2))
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


CEO_SK = W.skin_set("ceo")
TAX_SK = W.skin_set("taxman")
WORKER_SK = W.skin_set("worker")
BUYER_SK = W.villager_set((0.47, 0.32, 0.18))
CEO_POS = (89.6, 12.0, 96.4)
TAX_ROUTE = [(76.5, 12.0, 103.0), (78.2, 12.0, 94.6), (88.2, 12.0, 94.4)]
TAX_MEET = TAX_ROUTE[-1]
BUYER_POS = (78.5, 12.0, 90.6)
STALL_TOP = (78.5, 13.6, 89.5)


def block_box(bid, pos, size=0.32, spin=0.0):
    tex = [E.TEX[bid, 1], E.TEX[bid, 1], E.TEX[bid, 0], E.TEX[bid, 2], E.TEX[bid, 1], E.TEX[bid, 1]]
    return E.Box(pos, (size, size, size), E.rot_y(spin) @ E.rot_x(spin * 0.5), tex)


# Sales: (block list, block id, emerald value each)
def sales_round(round_):
    if round_ == 1:
        return ([(p, E.DIAMOND, 40) for p in W.VAULT[:1]] + [(p, E.IRON, 10) for p in W.IRON_PILE[:4]]
                + [(p, E.COBBLE, 8) for p in W.CHIMNEY[:5]])
    return ([(p, E.DIAMOND, 50) for p in W.VAULT[1:3]] + [(p, E.IRON, 10) for p in W.IRON_PILE[4:7]]
            + [(p, E.SMOOTH, 8) for p in W.FACTORY_ROOF_SALE[:6]])


SALE1 = sales_round(1)
SALE2 = sales_round(2)


class Worlds:
    def __init__(self):
        self.base = W.build_base()
        self.after1 = self.base.copy()
        for p, _, _ in SALE1:
            self.after1[p] = E.AIR
        self.after2 = self.after1.copy()
        for p, _, _ in SALE2:
            self.after2[p] = E.AIR
        self.dark = self.after2.copy()
        for p in W.FURNACES:
            self.dark[p] = E.COBBLE


def run_sales(lt, t_start, dur, sale, grid, sale_seed):
    """Animate a round of sales. Returns (grid, boxes, sprites, particles, paid, sold_ids, sfx_times)."""
    g = grid.copy()
    boxes, sprites_, parts, sfx = [], [], [], []
    paid = 0
    sold = []
    n = len(sale)
    for i, (p, bid, val) in enumerate(sale):
        ti = t_start + dur * i / n
        sfx.append((ti, "pop", 0.9 + 0.03 * i))
        sfx.append((ti + 0.8, "coin", 1.0 + 0.02 * i))
        if lt < ti:
            continue
        g[p] = E.AIR
        sold.append(bid)
        c = np.array(p, float) + 0.5
        parts += burst(lt - ti, sale_seed + i, c, 8, [tuple(E.TEX[bid, 1].mean((0, 1)))], speed=1.5, life=0.6, size=0.12)
        k = (lt - ti) / 0.8
        if k < 1:
            q = lerp(c, STALL_TOP, k) + np.array((0, 3.0 * math.sin(math.pi * k), 0))
            boxes.append(block_box(bid, q, 0.28, lt * 6))
        k2 = (lt - ti - 0.8) / 0.7
        if 0 <= k2 < 1:
            q = lerp(np.add(STALL_TOP, (0, 0.4, 0)), np.add(TAX_MEET, (0, 1.3, 0)), k2) + np.array((0, 2.0 * math.sin(math.pi * k2), 0))
            sprites_.append((q, 0.5))
        if k2 >= 1:
            paid += val
    return g, boxes, sprites_, parts, paid, sold, sfx


def people(lt, tax_pos=None, tax_yaw=None, tax_walk=0.0, ceo_arms=None, buyer=True):
    b = []
    ceo_yaw = yaw_to(CEO_POS, tax_pos) if tax_pos is not None else math.pi * 0.9
    b += W.player(CEO_SK, CEO_POS, ceo_yaw, arm_r=ceo_arms, arm_l=ceo_arms, head_yaw=0.15 * math.sin(lt * 1.3))
    if tax_pos is not None:
        b += W.player(TAX_SK, tax_pos, tax_yaw, walk=tax_walk, hat=True)
    if buyer:
        b += W.villager(BUYER_SK, BUYER_POS, math.pi, head_yaw=0.3 * math.sin(lt))
    blobs = [(CEO_POS[0], CEO_POS[2], 0.6), (BUYER_POS[0], BUYER_POS[2], 0.6)]
    if tax_pos is not None:
        blobs.append((tax_pos[0], tax_pos[2], 0.6))
    return b, blobs


# ============================================================== scenes
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

FACTORY_OUT = (105.4, 13.6, 96.0)
HQ_DOOR = (100.0, 13.4, 103.2)
WORKERS = [(104.3, 12.0, 94.2), (104.4, 12.0, 97.8), (103.9, 12.0, 96.0)]


def word_t(S, prefix, k=0):
    """Local time of the k-th spoken word starting with prefix."""
    hits = [w[0] for s in S["sents"] for w in s["words"] if w[2].lower().strip(",.:?!'\"").startswith(prefix)]
    return hits[min(k, len(hits) - 1)] - S["t0"] if hits else 0.0


def shot_cam(lt, shots, blend=0.5, push=0.06):
    """shots: [(t_start, cam_pos, target, fov)]. Eases between shots, gentle push-in within a shot."""
    shots = sorted(shots, key=lambda x: x[0])

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


def books_panel(title, rows, alpha):
    """rows: [(label, value, color)] -> MC tooltip-style ledger."""
    h = 110 + 78 * len(rows)
    p = tooltip(860, h)
    p.alpha_composite(ptext(title, (255, 226, 60), 4), (40, 26))
    for i, (lab, val, col) in enumerate(rows):
        y = 100 + i * 78
        p.alpha_composite(ptext(lab, (220, 220, 220), 4), (40, y))
        v = ptext(val, col, 4)
        p.alpha_composite(v, (820 - v.width, y))
    if alpha < 1:
        a = np.array(p.getchannel("A"), np.float32) * alpha
        p.putalpha(Image.fromarray(a.astype(np.uint8)))
    return p


def arc(a, b, k, h=2.5):
    return lerp(a, b, k) + np.array((0, h * math.sin(math.pi * k), 0))


def trade_flow(lt, t_start, t_end, every=0.45):
    """Tools fly factory -> market stall, emeralds fly stall -> HQ."""
    spr = []
    n = int((min(lt, t_end) - t_start) / every) + 1 if lt > t_start else 0
    for i in range(max(0, n - 6), n):
        ti = t_start + i * every
        k = (lt - ti) / 1.6
        if 0 <= k < 1:
            spr.append((arc(FACTORY_OUT, STALL_TOP, k, 3.5), 0.55, PICK))
        k2 = (lt - ti - 1.6) / 1.4
        if 0 <= k2 < 1:
            spr.append((arc(np.add(STALL_TOP, (0, 0.4, 0)), HQ_DOOR, k2, 3.0), 0.45, EMERALD))
    return spr


def workers(lt, busy=True):
    b, blobs = [], []
    for i, p in enumerate(WORKERS):
        arm = (-1.2 + 0.5 * math.sin(lt * 7 + i * 2)) if busy else None
        b += W.player(WORKER_SK, p, math.pi / 2, arm_r=arm)
        blobs.append((p[0], p[2], 0.6))
    return b, blobs


def scene_intro(lt, S, wd):
    D = S["dur"]
    cam = path(lt, [(0, (72, 36, 70), (96, 16, 100), 78), (D, (86, 25, 77), (95, 16, 100), 76)])
    boxes, blobs = people(lt)
    wb, wbl = workers(lt)
    a = fade(lt, 0.3, D - 0.15, 0.35)

    def title(fr):
        put(fr, ptext("TAXING COMPANIES", (235, 235, 235), 7), OW / 2, 330, alpha=a)
        put(fr, ptext("ON UNREALIZED", (235, 235, 235), 7), OW / 2, 460, alpha=a)
        put(fr, ptext("GAINS", (255, 226, 60), 11), OW / 2, 620, alpha=a)
    return dict(cam=cam, boxes=boxes + wb, blobs=blobs + wbl, grid=wd.base, overlays=[title],
                labels=[((100, 30.6, 104), "BLOCKWORKS INC.", (255, 215, 60))])


def inv_counts(dia, iron, em=0, flash=0.0):
    return [(block_icon(E.DIAMOND), dia, 0.0), (block_icon(E.IRON), iron, 0.0), (EMERALD, em, flash)]


def scene_business(lt, S, wd):
    D = S["dur"]
    t_fac, t_sells, t_sold = word_t(S, "factory"), word_t(S, "sells"), word_t(S, "sold")
    t_work, t_profit, t_tax, t_keeps = word_t(S, "workers"), word_t(S, "profit"), word_t(S, "tax"), word_t(S, "keeps")
    shots = [(0, (97.5, 22, 80), (95, 14, 98), 78),
             (t_fac - 0.15, (99.0, 16.8, 90.0), (107, 14.2, 96), 70),
             (t_sells - 0.15, (85.0, 16.8, 83.5), (78.8, 13.5, 90.5), 70),
             (t_sold - 0.15, (94.0, 27.0, 78.0), (93.0, 13.0, 95.0), 80),
             (t_keeps - 0.15, (93.0, 16.8, 89.5), (96.5, 15.5, 102.0), 72)]
    cam = shot_cam(lt, shots)
    boxes, blobs = people(lt)
    wb, wbl = workers(lt)
    spr = trade_flow(lt, t_sells, D)
    rows = []
    if lt > t_sold:
        rows.append(("Tool sales", "+300", (85, 255, 85)))
    if lt > t_work:
        rows.append(("Wages + materials", "-200", (255, 120, 120)))
    if lt > t_profit:
        rows.append(("Profit", "100", (255, 255, 255)))
    if lt > t_tax:
        rows.append(("Normal profit tax", "-20", (255, 120, 120)))
    if lt > t_keeps:
        rows.append(("Cash left", "80", (85, 255, 85)))
    pa = fade(lt, t_sold - 0.1, D + 1, 0.25)

    def ledger(fr):
        if rows and pa > 0:
            put(fr, books_panel("BLOCKWORKS: YEAR 1", rows, pa), OW / 2, 470)
    vals = []
    if t_fac < lt < t_sells:
        vals.append(((108, 19.6, 96), [("Makes diamond tools", (255, 255, 255))], None))
    if t_sells < lt < t_sold:
        vals.append(((78.5, 16.8, 90.5), [("Sells them here", (255, 255, 255))], None))
    cash = int(80 * ss((lt - t_keeps) / 0.8))
    sfx = [(S["t0"] + t_sells + 1.6 + i * 0.45, "coin", 1.0 + 0.03 * (i % 6)) for i in range(int((D - t_sells - 1.6) / 0.45))]
    return dict(cam=cam, boxes=boxes + wb, blobs=blobs + wbl, grid=wd.base, sprites=spr, overlays=[ledger], values=vals,
                labels=[((100, 30.6, 104), "BLOCKWORKS INC.", (255, 215, 60))],
                inv=inv_counts(50, 18, cash) if lt > t_keeps - 0.3 else None, sfx=sfx)


def scene_vault(lt, S, wd):
    D = S["dur"]
    t_dbl, t_paper = word_t(S, "doubled"), word_t(S, "paper")
    shots = [(0, (90.0, 17.0, 90.0), (84.5, 13.2, 99.5), 72), (t_dbl - 0.2, (89.0, 16.2, 91.2), (84.5, 13.4, 99.5), 70)]
    cam = shot_cam(lt, shots)
    boxes, blobs = people(lt)
    vals, parts = [], []
    if lt < t_dbl - 0.2:
        vals.append(((84.5, 15.4, 99.5), [("Raw material for next year", (255, 255, 255))], None))
    else:
        k = ss((lt - t_dbl) / 1.4)
        price = int(round(1000 + 1000 * k, -1))
        vals.append(((84.5, 15.4, 99.5), [(f"Vault value: {price:,}", (85, 255, 255) if k < 1 else (85, 255, 85))], EMERALD))
        parts += sparkles(lt, 3, (82, 14, 97), (87, 16.5, 102))
    pa = fade(lt, t_paper - 0.1, D + 1, 0.2)

    def panel(fr):
        if pa <= 0:
            return
        p = tooltip(860, 230)
        p.alpha_composite(ptext("Unrealized gain", (200, 200, 200), 4), (40, 22))
        p.alpha_composite(ptext("+1,000 emeralds", (85, 255, 85), 5), (40, 80))
        p.alpha_composite(ptext("on paper: nothing was sold", (255, 226, 60), 3), (40, 165))
        put(fr, p, OW / 2, 400, alpha=pa)
    return dict(cam=cam, boxes=boxes, blobs=blobs, grid=wd.base, values=vals, particles=parts, overlays=[panel],
                inv=inv_counts(50, 18, 80), sfx=[(S["t0"] + t_dbl, "chime", 1)])


def scene_bill(lt, S, wd):
    D = S["dur"]
    t_200, t_only = word_t(S, "200"), word_t(S, "only")
    arrive = path_len(TAX_ROUTE) / 3.0
    t_walk0 = max(0.0, t_200 - arrive + 0.3)
    tp, tyaw, twalk = walk_path(max(0.0, lt - t_walk0), TAX_ROUTE)
    if lt >= t_walk0 + arrive:
        tyaw = yaw_to(TAX_MEET, CEO_POS)
    cam = path(lt, [(0, (94.2, 16.2, 88.2), (88.5, 13.4, 96), 72), (D, (93.4, 15.6, 89.0), (88.0, 13.4, 95.5), 70)])
    shrug = -0.9 + 0.3 * math.sin(lt * 6) if lt > t_only else None
    boxes, blobs = people(lt, tp, tyaw, twalk if lt < t_walk0 + arrive else 0.0, shrug)
    vals = []
    if lt >= t_walk0 + arrive - 0.2:
        vals.append((np.add(tp, (0, 3.0, 0)), [("TAX BILL: 200", (255, 85, 85)), ("20% of +1,000", (230, 230, 230))], EMERALD))
    labels = [(np.add(CEO_POS, (0, 2.3, 0)), "Blockworks_CEO", (255, 255, 255)),
              (np.add(tp, (0, 2.45, 0)), "Tax_Collector", (255, 255, 255))]
    fl = 0.5 + 0.5 * math.sin(lt * 10) if lt > t_only else 0.0
    rows = [("Tax bill", "200", (255, 120, 120))]
    if lt > t_only:
        rows += [("Cash on hand", "80", (255, 255, 255)), ("Missing", "120", (255, 85, 85))]
    pa = fade(lt, t_200 - 0.1, D + 1, 0.25)

    def panel(fr):
        if pa > 0:
            put(fr, books_panel("CAN IT PAY?", rows, pa), OW / 2, 420)
    return dict(cam=cam, boxes=boxes, blobs=blobs, grid=wd.base, values=vals, labels=labels, overlays=[panel],
                inv=inv_counts(50, 18, 80, fl), sfx=[(S["t0"] + t_walk0 + arrive, "thud", 1)])


def scene_sell(lt, S, wd):
    D = S["dur"]
    t_dia, t_fac = word_t(S, "diamonds"), word_t(S, "factory")
    cam = path(lt, [(0, (90, 26, 80), (88, 12, 95), 80), (1.2, (84.5, 28, 77), (89, 11.5, 93), 82),
                    (D, (84.5, 28.5, 76.5), (89, 11.5, 93), 82)])
    g, sb, spr, parts, paid, sold, sfx = run_sales(lt, t_dia, max(2.5, t_fac + 0.8 - t_dia), SALE1, wd.base, 100)
    boxes, blobs = people(lt, np.array(TAX_MEET), yaw_to(TAX_MEET, BUYER_POS))
    boxes += sb
    dia = 50 - sum(1 for b in sold if b == E.DIAMOND)
    iron = 18 - sum(1 for b in sold if b == E.IRON)
    total = 80 + paid
    vals = [(np.add(TAX_MEET, (0, 3.0, 0)), [(f"Paid: {total}/200", (85, 255, 85) if total >= 200 else (255, 255, 255))], EMERALD)]
    labels = [(np.add(BUYER_POS, (0, 2.5, 0)), "Buyer", (255, 255, 255))]
    return dict(cam=cam, boxes=boxes, blobs=blobs, grid=g, values=vals, labels=labels, particles=parts,
                sprites=[(q, s_, EMERALD) for q, s_ in spr], inv=inv_counts(dia, iron, 0), sfx=[(S["t0"] + a, k, p) for a, k, p in sfx])


CYCLE_STEPS = ["Prices rise", "Tax bill > cash", "Sell assets", "Less revenue"]


def cycle_diagram(active, alpha):
    W_, H_ = 940, 760
    im = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W_ - 1, H_ - 1], 40, fill=(12, 12, 20, 205))
    cx, cy, r = W_ / 2, H_ / 2 + 20, 230
    pos = [(cx, cy - r), (cx + r * 1.25, cy), (cx, cy + r), (cx - r * 1.25, cy)]
    for i in range(4):
        a0 = -math.pi / 2 + i * math.pi / 2 + 0.42
        a1 = a0 + math.pi / 2 - 0.84
        pts = [(cx + 1.25 * r * math.cos(a0 + (a1 - a0) * k / 20), cy + r * math.sin(a0 + (a1 - a0) * k / 20)) for k in range(21)]
        col = (255, 226, 60, 255) if i == active else (170, 170, 190, 255)
        d.line(pts, fill=col, width=10)
        ex, ey = pts[-1]
        px, py = pts[-4]
        ang = math.atan2(ey - py, ex - px)
        d.polygon([(ex + 26 * math.cos(ang), ey + 26 * math.sin(ang)),
                   (ex + 20 * math.cos(ang + 2.3), ey + 20 * math.sin(ang + 2.3)),
                   (ex + 20 * math.cos(ang - 2.3), ey + 20 * math.sin(ang - 2.3))], fill=col)
    f = cfont(40, "Bold")
    for i, (x, y) in enumerate(pos):
        on = i == active
        tw = f.getlength(CYCLE_STEPS[i])
        x = min(max(x, tw / 2 + 36), W_ - tw / 2 - 36)
        d.rounded_rectangle([x - tw / 2 - 22, y - 42, x + tw / 2 + 22, y + 42], 22,
                            fill=(255, 226, 60, 255) if on else (40, 40, 60, 255), outline=(255, 255, 255, 255), width=4)
        d.text((x, y), CYCLE_STEPS[i], font=f, fill=(20, 20, 20) if on else (255, 255, 255), anchor="mm")
    t = ctext("THE LOOP", 50, stroke=0)
    im.alpha_composite(t, (int(cx - t.width / 2), 28))
    if alpha < 1:
        a = np.array(im.getchannel("A"), np.float32) * alpha
        im.putalpha(Image.fromarray(a.astype(np.uint8)))
    return im


def scene_cycle(lt, S, wd):
    D = S["dur"]
    t_rise, t_bill, t_sell = word_t(S, "rise"), word_t(S, "bill"), word_t(S, "selling")
    ang = 0.2 * lt
    c = np.array((92.0, 13.0, 96.0))
    cam = E.Camera(c + np.array((-14 * math.sin(0.6 + ang), 17, -18 * math.cos(0.6 + ang))), c, 78)
    g, sb, spr, parts, paid, sold, sfx = run_sales(lt, t_sell, 2.6, SALE2, wd.after1, 300)
    boxes, blobs = people(lt, np.array(TAX_MEET), yaw_to(TAX_MEET, BUYER_POS))
    wb, wbl = workers(lt)
    boxes += sb + wb
    blobs += wbl
    spr = [(q, s_, EMERALD) for q, s_ in spr] + trade_flow(lt, 0.3, t_rise, every=0.8)
    if t_rise < lt < t_sell:
        parts += sparkles(lt, 7, (82, 13, 97), (87, 15.5, 102))
    dia = 49 - sum(1 for b in sold if b == E.DIAMOND)
    iron = 14 - sum(1 for b in sold if b == E.IRON)
    vals = []
    if lt > t_bill:
        vals.append((np.add(TAX_MEET, (0, 3.0, 0)), [("NEW TAX BILL", (255, 85, 85))], None))
    if lt < t_rise:
        step = 3
    elif lt < t_bill:
        step = 0
    elif lt < t_sell:
        step = 1
    elif lt < t_sell + 1.2:
        step = 2
    else:
        step = 3 + int((lt - t_sell - 1.2) / 0.5) % 4
        step %= 4
    da = fade(lt, 0.1, D + 1, 0.3)
    ra = fade(lt, 0.3, t_rise, 0.25)

    def diagram(fr):
        if ra > 0:
            put(fr, books_panel("YEAR 2", [("Tool sales", "240 (was 300)", (255, 120, 120))], ra), OW / 2, 380)
        if lt > t_rise - 0.3 and da > 0:
            put(fr, cycle_diagram(step, min(da, fade(lt, t_rise - 0.3, D + 1, 0.3))), OW / 2, 520)
    return dict(cam=cam, boxes=boxes, blobs=blobs, grid=g, values=vals, particles=parts, sprites=spr,
                overlays=[diagram], inv=inv_counts(dia, iron, 0), sfx=[(S["t0"] + a, k, p) for a, k, p in sfx])


def scene_cost(lt, S, wd):
    D = S["dur"]
    cam = path(lt, [(0, (98.5, 17.5, 86.0), (109, 15, 96), 74), (D, (97.0, 18.5, 84.5), (109, 15, 96), 76)])
    boxes, blobs = [], []
    t_jobs = word_t(S, "jobs")
    for i, st in enumerate(WORKERS):
        tw = lt - (t_jobs - 0.3 + i * 0.5)
        end = (st[0] - 16, 12.0, st[2] - 10)
        if tw > 0:
            p, yw, ph = walk_path(tw, [st, end], 2.6)
        else:
            p, yw, ph = np.array(st), math.pi / 2, 0.0
        boxes += W.player(WORKER_SK, p, yw, walk=ph)
        blobs.append((p[0], p[2], 0.6))
    t_prod = word_t(S, "production")
    g = wd.after2 if lt < t_prod else wd.dark
    items = [("Production", "production"), ("Jobs", "jobs"), ("Investment", "investment")]

    def panel(fr):
        for i, (name, key) in enumerate(items):
            a = fade(lt, word_t(S, key) - 0.15, D + 1, 0.25)
            if a <= 0:
                continue
            row = Image.new("RGBA", (720, 120), (0, 0, 0, 0))
            d = ImageDraw.Draw(row)
            d.rounded_rectangle([0, 0, 719, 119], 28, fill=(15, 15, 22, 215))
            d.polygon([(620, 38), (680, 38), (650, 88)], fill=(255, 80, 80))
            row.alpha_composite(ctext(name, 60, stroke=0), (40, 22))
            put(fr, row, OW / 2, 330 + i * 150, alpha=a)
    return dict(cam=cam, boxes=boxes, blobs=blobs, grid=g, overlays=[panel], inv=inv_counts(47, 11, 0),
                labels=[((105.8, 16.8, 96), "Factory: half closed", (255, 120, 120))] if lt > t_prod else [],
                sfx=[(S["t0"] + t_prod, "thud", 1)])


def scene_outro(lt, S, wd):
    D = S["dur"]
    c = np.array((92.0, 14.0, 97.0))
    a = 0.2 * lt
    cam = E.Camera(c + np.array((10 * math.sin(3.4 + a), 8 + 1.5 * lt, 12 * math.cos(3.4 + a))), c + (0, 2, 0), 76)
    boxes, blobs = people(lt, buyer=False)
    ta = fade(lt, 0.3, D + 5, 0.4)

    def title(fr):
        put(fr, ptext("TAX GAINS WHEN", (235, 235, 235), 7), OW / 2, 360, alpha=ta)
        put(fr, ptext("THEY'RE REAL", (85, 255, 85), 9), OW / 2, 510, alpha=ta)
        put(fr, ctext("when the asset is actually sold", 54), OW / 2, 650, alpha=ta)
    black = min(1.0, max(0.0, (lt - (D - 0.8)) / 0.8))
    return dict(cam=cam, boxes=boxes, blobs=blobs, grid=wd.dark, overlays=[title], black=black,
                sfx=[(S["t0"] + 0.35, "chime", 1)])


SCENE_FN = dict(intro=scene_intro, business=scene_business, vault=scene_vault, bill=scene_bill, sell=scene_sell,
                cycle=scene_cycle, cost=scene_cost, outro=scene_outro)



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
    for p, size, spr_img in r.get("sprites", []):
        pr = cam.project(p, OW, OH)
        if pr is None:
            continue
        px = int(size / (pr[2] * cam.th) * OH / 2)
        if px >= 6:
            put(fr, spr_img.resize((px, px * spr_img.height // spr_img.width), Image.NEAREST), pr[0], pr[1])
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
        slots = [slot_img(ic, n, fl) for ic, n, fl in items]
        sw = slots[0].width
        gap = 14
        total = len(slots) * sw + (len(slots) - 1) * gap
        x0 = (OW - total) // 2
        y0 = 1840
        lab = ptext("BLOCKWORKS INVENTORY", (255, 255, 255), 3, bg=110)
        put(fr, lab, OW / 2, y0 - 16, "mb")
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
                if sc["t0"] - 0.05 <= e[0] < sc["t1"]:
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
