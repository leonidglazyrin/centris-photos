"""Original score for THE LAST LANTERN, synthesized from scratch with numpy.

Piano, strings, pads, bells and a little nature ambience, cued to the picture.
Writes out/score.wav (44.1 kHz stereo).
"""
import numpy as np
import wave
import os

SR = 44100
DUR = 300.0
N = int(SR * DUR)
rng = np.random.default_rng(7)
BPM = 72
BEAT = 60 / BPM
BAR = BEAT * 4

L = np.zeros(N)
R = np.zeros(N)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def add(sig, t0, pan=0.0, gain=1.0):
    i0 = int(t0 * SR)
    if i0 >= N:
        return
    if i0 < 0:
        sig = sig[-i0:]
        i0 = 0
    sig = sig[: N - i0]
    lg = np.cos((pan + 1) * np.pi / 4) * gain
    rg = np.sin((pan + 1) * np.pi / 4) * gain
    L[i0:i0 + len(sig)] += sig * lg
    R[i0:i0 + len(sig)] += sig * rg


# ---------------- instruments ----------------
def piano(note, dur, vel=0.6):
    f = midi(note)
    ring = max(dur + 1.2, 3.5 if note < 60 else 2.8)
    t = np.arange(int(ring * SR)) / SR
    out = np.zeros_like(t)
    B = 0.00035
    for n in range(1, 11):
        fn = n * f * np.sqrt(1 + B * n * n)
        if fn > 16000:
            break
        amp = (1 / n ** 1.25) * (0.6 + 0.4 * vel) ** (n * 0.3)
        dec = 0.55 + n * 0.32 + f / 900
        out += amp * np.exp(-t * dec) * np.sin(2 * np.pi * fn * t + n * 0.3)
    att = np.minimum(1, t / 0.004)
    rel = np.clip((ring - t) / 0.35, 0, 1)
    damp = np.where(t > dur + 0.25, np.exp(-(t - dur - 0.25) * 3.0), 1.0)
    hammer = rng.standard_normal(len(t)) * np.exp(-t * 90) * 0.04
    return (out * att * rel * damp + hammer) * vel * 0.35


def pad(notes, dur, bright=0.5, att=1.6):
    t = np.arange(int((dur + 2.0) * SR)) / SR
    out = np.zeros_like(t)
    for note in notes:
        f = midi(note)
        for det in (-0.12, 0.0, 0.11):
            fd = f * 2 ** (det / 12)
            ph = rng.random() * 6.28
            vib = 1 + 0.002 * np.sin(2 * np.pi * 4.6 * t + ph)
            for n in range(1, 9):
                if n * fd > 9000:
                    break
                out += (1 / n ** (2.2 - bright)) * np.sin(2 * np.pi * n * fd * t * vib + ph * n)
    env = np.minimum(1, t / att) * np.clip((dur + 2.0 - t) / 2.0, 0, 1)
    return out * env / (len(notes) * 3) * 0.3


def strings(note, dur, vel=0.5):
    f = midi(note)
    t = np.arange(int((dur + 1.2) * SR)) / SR
    vib = 1 + 0.0035 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.8)
    out = np.zeros_like(t)
    for det in (-0.07, 0.06):
        fd = f * 2 ** (det / 12)
        for n in range(1, 12):
            if n * fd > 12000:
                break
            out += (1 / n ** 1.45) * np.sin(2 * np.pi * n * fd * t * vib + n)
    env = np.minimum(1, t / 0.45) * np.clip((dur + 1.2 - t) / 1.2, 0, 1)
    return out * env * vel * 0.12


def pluck(note, vel=0.5):
    f = midi(note)
    t = np.arange(int(1.4 * SR)) / SR
    out = np.zeros_like(t)
    for n in range(1, 9):
        out += (1 / n ** 1.1) * np.exp(-t * (3 + n * 2.2)) * np.sin(2 * np.pi * n * f * t)
    return out * np.minimum(1, t / 0.002) * vel * 0.25


def bell(note, vel=0.5):
    f = midi(note)
    t = np.arange(int(4.5 * SR)) / SR
    out = np.zeros_like(t)
    for ratio, amp, dec in ((1, 1, 0.9), (2.0, 0.35, 1.4), (2.76, 0.45, 1.8), (5.4, 0.25, 3.0), (8.93, 0.12, 5.0)):
        out += amp * np.exp(-t * dec) * np.sin(2 * np.pi * f * ratio * t)
    return out * np.minimum(1, t / 0.002) * vel * 0.18


# ---------------- harmony ----------------
F, C, D, E, G, A, Bb = 53, 48, 50, 52, 55, 57, 46  # bass register
CH = {
    'F': [53, 60, 65, 69], 'C/E': [52, 60, 64, 67], 'Dm': [50, 57, 62, 65], 'Bb': [46, 58, 62, 65],
    'F/A': [45, 60, 65, 69], 'Gm': [43, 58, 62, 67], 'C': [48, 55, 64, 67], 'Csus': [48, 55, 65, 67],
    'A': [45, 57, 61, 64], 'Dm/C': [48, 57, 62, 65], 'Am': [45, 57, 60, 64], 'Bbmaj7': [46, 57, 62, 65],
}
PROG = ['F', 'C/E', 'Dm', 'Bb', 'F/A', 'Gm', 'C', 'Csus']
MINOR = ['Dm', 'Bb', 'F', 'C', 'Gm', 'Dm', 'A', 'A']

# melodies: (beat offset, midi, beats)
THEME_A = [
    [(0, 69, 1), (1, 72, 1), (2, 77, 2)],
    [(0, 76, 1.5), (1.5, 74, 0.5), (2, 72, 2)],
    [(0, 74, 1), (1, 77, 1), (2, 81, 2)],
    [(0, 79, 1), (1, 77, 1), (2, 74, 2)],
    [(0, 72, 1), (1, 77, 1), (2, 81, 1), (3, 79, 1)],
    [(0, 77, 1.5), (1.5, 76, 0.5), (2, 74, 2)],
    [(0, 76, 1), (1, 74, 1), (2, 72, 2)],
    [(0, 67, 4)],
]
THEME_B = [
    [(0, 72, .5), (.5, 74, .5), (1, 77, 1), (2, 77, .5), (2.5, 79, .5), (3, 81, 1)],
    [(0, 79, 1), (1, 76, 1), (2, 72, 2)],
    [(0, 69, .5), (.5, 72, .5), (1, 74, 1), (2, 74, .5), (2.5, 76, .5), (3, 77, 1)],
    [(0, 77, 1), (1, 74, 1), (2, 70, 2)],
    [(0, 72, .5), (.5, 77, .5), (1, 81, 1), (2, 81, .5), (2.5, 82, .5), (3, 84, 1)],
    [(0, 82, 1), (1, 81, 1), (2, 79, 2)],
    [(0, 76, 1), (1, 77, .5), (1.5, 79, .5), (2, 76, 2)],
    [(0, 72, 4)],
]
THEME_MINOR = [
    [(0, 69, 2), (2, 74, 2)], [(0, 77, 3), (3, 76, 1)], [(0, 72, 4)], [(0, 76, 2), (2, 67, 2)],
    [(0, 70, 2), (2, 74, 2)], [(0, 77, 3), (3, 76, 1)], [(0, 73, 2), (2, 76, 2)], [(0, 69, 4)],
]


def bar_t(b):
    return b * BAR


def play_melody(theme, bar0, inst='piano', vel=0.55, octave=0, pan=0.1, gain=1.0):
    for i, bar in enumerate(theme):
        for (o, n, d) in bar:
            t0 = bar_t(bar0 + i) + o * BEAT
            if inst == 'piano':
                add(piano(n + octave, d * BEAT, vel), t0, pan, gain)
            elif inst == 'strings':
                add(strings(n + octave, d * BEAT, vel), t0, pan, gain)
            elif inst == 'bell':
                add(bell(n + octave, vel), t0, pan, gain)


def play_arps(prog, bar0, vel=0.35, pattern=(0, 2, 1, 3, 2, 1), pan=-0.2, gain=1.0, sub=0.5):
    for i, ch in enumerate(prog):
        notes = CH[ch]
        add(piano(notes[0] - 12 if notes[0] > 50 else notes[0], BAR * 0.9, vel * 1.1), bar_t(bar0 + i), -0.3, gain)
        steps = int(4 / sub)
        for s in range(steps):
            n = notes[1 + pattern[s % len(pattern)] % 3]
            add(piano(n, sub * BEAT * 1.5, vel * (0.85 if s % 2 else 1)), bar_t(bar0 + i) + s * sub * BEAT, pan, gain)


def play_pads(prog, bar0, gain=1.0, bright=0.5, bars_each=1):
    for i, ch in enumerate(prog):
        add(pad(CH[ch], BAR * bars_each, bright), bar_t(bar0 + i * bars_each) - 0.2, 0, gain)


def play_strings_chords(prog, bar0, vel=0.45, gain=1.0):
    for i, ch in enumerate(prog):
        notes = CH[ch]
        for k, n in enumerate(notes[1:]):
            add(strings(n, BAR, vel), bar_t(bar0 + i), -0.4 + k * 0.4, gain)
        add(strings(notes[0] - 12, BAR, vel * 0.9), bar_t(bar0 + i), 0, gain)


# ---------------- the cue sheet ----------------
# I. Dawn + the pier (0:00 – 1:10)
play_pads(['F', 'F', 'Bb', 'C'], 0, gain=0.9, bright=0.3)
for i, n in enumerate([77, 72, 69, 72, 74, 72]):
    add(piano(n, 2 * BEAT, 0.35), 1.5 + i * 1.6, 0.2)
play_arps(PROG, 4, vel=0.25)
play_melody(THEME_A, 4, vel=0.5)
play_pads(PROG, 4, gain=0.5, bright=0.3)
play_arps(PROG[:7] + ['C'], 12, vel=0.27)
play_melody(THEME_A[:7], 12, vel=0.55)
play_strings_chords(PROG, 12, vel=0.3, gain=0.6)
add(pad(CH['Csus'], BAR * 1.2, 0.4), bar_t(20), 0, 0.8)

# II. Montage: grove, hill, workshop, sapling (1:10 – 2:00)
for b in range(21, 36):
    ch = CH[PROG[(b - 21) % 8]]
    for s in range(8):
        add(pluck(ch[1 + [0, 2, 1, 2][s % 4] % 3] + 12, 0.35 if s % 2 else 0.45), bar_t(b) + s * BEAT / 2, 0.35 * (1 if s % 2 else -1), 0.8)
play_arps(PROG, 21, vel=0.22, sub=1)
play_melody(THEME_B, 21, vel=0.55)
play_strings_chords(PROG, 21, vel=0.35, gain=0.7)
play_arps(PROG[:7], 29, vel=0.24, sub=1)
play_melody(THEME_A[:7], 29, inst='strings', vel=0.5, gain=0.9)
play_melody(THEME_A[:7], 29, vel=0.4, octave=12, gain=0.6)
play_pads(PROG[:7], 29, gain=0.6, bright=0.4)

# III. Sunset & dusk — the minor turn (2:00 – 2:36)
play_pads(MINOR, 36, gain=0.8, bright=0.3)
play_melody(THEME_MINOR, 36, vel=0.5)
play_arps(MINOR, 36, vel=0.2, sub=1, pattern=(0, 1, 2, 1))
play_pads(['Dm', 'Bb', 'A'], 44, gain=0.7, bright=0.25)
for i, n in enumerate([74, 77, 81, 79, 77, 76]):
    add(bell(n, 0.35), bar_t(44) + i * 1.6, 0.3 * (-1) ** i)   # lanterns flickering on

# IV. Departure + the new lantern (2:36 – 3:16)
play_pads(['Dm', 'Bb', 'F', 'C'], 47, gain=0.55, bright=0.2, bars_each=2)
play_melody(THEME_MINOR[:4], 47, vel=0.42)
play_melody([[(0, 74, 2), (2, 72, 2)], [(0, 70, 4)], [(0, 69, 2), (2, 67, 2)], [(0, 69, 4)]], 51, vel=0.38)
play_arps(['Dm', 'Bb', 'Gm', 'C'], 55, vel=0.24, sub=1)
play_melody([[(0, 69, 1), (1, 72, 1), (2, 74, 2)], [(0, 70, 2), (2, 74, 2)], [(0, 74, 1), (1, 72, 1), (2, 70, 2)], [(0, 72, 4)]], 55, vel=0.45)
add(pad(CH['F'], BAR * 2, 0.5), bar_t(57.1), 0, 1.0)      # the lantern is lit
add(strings(77, BAR * 1.6, 0.4), bar_t(57.1), 0.2, 0.9)
add(strings(81, BAR * 1.6, 0.35), bar_t(57.1), -0.2, 0.9)

# V. Winter (3:16 – 3:46)
play_pads(['Dm', 'Dm/C', 'Bb', 'A'], 59, gain=0.6, bright=0.15, bars_each=2)
play_pads(['Dm', 'Bb'], 67, gain=0.5, bright=0.15)
for b in range(59, 68):
    ch = CH[['Dm', 'Dm', 'Dm/C', 'Dm/C', 'Bb', 'Bb', 'A', 'A', 'Dm'][b - 59]]
    for s, k in enumerate([3, 2, 1, 2]):
        if (b + s) % 3 == 0:
            continue
        add(bell(ch[k] + 12, 0.3), bar_t(b) + s * BEAT, 0.5 * (-1) ** s)
play_melody([[(0, 81, 3), (3, 79, 1)], [(0, 77, 4)], [(0, 76, 2), (2, 74, 2)], [(0, 73, 4)]], 61, vel=0.3)

# VI. Spring — the light on the lake, the return (3:46 – 4:44)
play_pads(PROG, 68, gain=0.55, bright=0.35)
for b in range(68, 76):
    for s in range(4):
        add(bell(CH[PROG[b - 68]][1 + s % 3] + 24, 0.12), bar_t(b) + s * BEAT + 0.5 * BEAT, 0.6 * (-1) ** s)   # fireflies
play_melody(THEME_A, 68, vel=0.45)
play_arps(PROG, 68, vel=0.2, sub=1)
play_arps(PROG, 76, vel=0.3)
play_melody(THEME_B, 76, vel=0.6)
play_melody(THEME_B, 76, inst='strings', vel=0.45, octave=-12, gain=0.8)
play_strings_chords(PROG, 76, vel=0.45, gain=0.9)
# climax on the embrace (bar 79 ≈ 4:24) — full theme up an octave
play_melody(THEME_A, 79.2, inst='strings', vel=0.55, octave=12, gain=0.55)

# VII. Finale (4:44 – 5:00)
play_pads(['F', 'Bb', 'F'], 85, gain=0.8, bright=0.35, bars_each=2)
for i, n in enumerate([81, 77, 72, 69, 72, 77, 81, 84]):
    add(piano(n, 2 * BEAT, 0.38), bar_t(85) + i * BEAT * 1.5, 0.2)
for n in CH['F'] + [72, 77]:
    add(piano(n, BAR * 2, 0.4), bar_t(88), 0.0)
add(bell(89, 0.25), bar_t(88) + 0.02, 0.3)

music = np.stack([L, R])


# ---------------- ambience ----------------
def shaped_noise(n, slope=1.0, lo=40, hi=8000, seed=0):
    r = np.random.default_rng(seed)
    spec = np.fft.rfft(r.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    shape = np.where(f > 0, 1 / np.maximum(f, 1) ** (slope / 2), 0)
    shape *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    shape *= 1 / (1 + (f / hi) ** 4)
    out = np.fft.irfft(spec * shape, n)
    return out / np.max(np.abs(out))


def env(points):
    tt = np.arange(N) / SR
    xs, ys = zip(*points)
    return np.interp(tt, xs, ys)


tt = np.arange(N) / SR
water = shaped_noise(N, 1.6, 60, 1800, 1) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.23 * tt) * np.sin(2 * np.pi * 0.07 * tt))
water_e = env([(0, 0), (3, 0.045), (68, 0.045), (70, 0.0), (140, 0), (143, 0.04), (172, 0.04), (174, 0), (205, 0), (206, 0.02), (226, 0.025), (284, 0.03), (292, 0.0), (300, 0)])
wind = shaped_noise(N, 1.2, 150, 3000, 2) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 0.05 * tt)))
wind_e = env([(0, 0), (196, 0), (198, 0.05), (224, 0.05), (227, 0), (300, 0)])
amb = water * water_e + wind * wind_e
# birdsong in daytime scenes
birds = np.zeros(N)
for k in range(70):
    t0 = 14 + rng.random() * 106
    if 70 < t0 < 72:
        continue
    f0 = 2600 + rng.random() * 1800
    for c in range(rng.integers(2, 6)):
        d = 0.06 + rng.random() * 0.08
        t = np.arange(int(d * SR)) / SR
        sweep = f0 * (1 + 0.35 * np.sin(np.pi * t / d) * (1 if c % 2 else -0.6))
        ph = 2 * np.pi * np.cumsum(sweep) / SR
        ch = np.sin(ph) * np.sin(np.pi * t / d) ** 2
        i0 = int((t0 + c * (d + 0.03)) * SR)
        birds[i0:i0 + len(ch)] += ch[: max(0, N - i0)] * 0.012
# crickets at night
cr = np.zeros(N)
carrier = np.sin(2 * np.pi * 4700 * tt)
gate = (np.sin(2 * np.pi * 28 * tt) > 0.3) * (np.sin(2 * np.pi * 0.9 * tt) > 0.1)
cr = carrier * gate * env([(0, 0), (172, 0), (174, 0.004), (196, 0.004), (197, 0), (226, 0), (229, 0.005), (284, 0.005), (292, 0), (300, 0)])
amb2 = np.stack([amb + birds * 0.8 + cr * 0.7, amb * 0.95 + birds * 1.1 + np.roll(cr, 1100) * 0.7])


# ---------------- reverb (FFT convolution with a synthetic hall) ----------------
def reverb(x, seconds=3.2, wet=0.32, seed=5):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = []
    for ch in range(2):
        ir = r.standard_normal(n) * np.exp(-t * 6.9 / seconds)
        ir *= np.minimum(1, t / 0.02)
        ir[: int(0.012 * SR)] = 0
        ir /= np.sqrt(np.sum(ir ** 2))
        m = len(x[ch]) + n
        size = 1 << (m - 1).bit_length()
        y = np.fft.irfft(np.fft.rfft(x[ch], size) * np.fft.rfft(ir, size), size)[: len(x[ch])]
        out.append(x[ch] * (1 - wet) + y * wet * 2.2)
    return np.stack(out)


music = reverb(music)
mix = music + amb2
# master: gentle fades, dip before the blue-hour cut, soft limiter
master = env([(0, 0), (1.5, 1), (153.5, 1), (156.0, 0.25), (157.5, 1), (296, 1), (300, 0)])
mix *= master
peak = np.max(np.abs(mix))
mix = mix / peak * 0.95
mix = np.tanh(mix * 1.15) / np.tanh(1.15)
mix *= 0.89

os.makedirs('out', exist_ok=True)
pcm = (np.clip(mix.T, -1, 1) * 32767).astype('<i2')
with wave.open('out/score.wav', 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('wrote out/score.wav', pcm.shape[0] / SR, 's')
