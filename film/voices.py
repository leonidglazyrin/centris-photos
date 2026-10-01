"""Voice track for THE LAST LANTERN: Juno, Rowan and a narrator (Kokoro TTS).

Lines are timed to the picture. The score is ducked under speech, a little
room reverb is added, and out/final_mix.wav is written.
"""
import numpy as np
import wave
import re
from kokoro_onnx import Kokoro

SR = 44100
VOICE = {'juno': 'af_heart', 'rowan': 'am_michael', 'narrator': 'bm_george'}
SPEED = {'juno': 0.95, 'rowan': 0.98, 'narrator': 0.9}
GAIN = {'juno': 1.0, 'rowan': 1.0, 'narrator': 0.95}

# (start seconds, latest end, who, text)
LINES = [
    (3.6, 12.6, 'narrator', 'Every village has a story it tells about itself. In Willow Lake, the story was about a lantern.'),
    (14.8, 24.0, 'narrator', 'Juno made lanterns. Every one of them burned along the old pier. Every one, except the last.'),
    (26.5, 30.0, 'juno', 'Grandma always said the last post waits...'),
    (30.1, 35.5, 'juno', '...for someone worth lighting it for.'),
    (37.0, 46.0, 'narrator', 'And one spring morning, out of the mist, came someone who had never stayed anywhere long enough to call it home.'),
    (49.6, 54.2, 'rowan', "Hi! Is this... Willow Lake? It isn't on any map."),
    (54.4, 58.0, 'juno', 'Then your map is wrong.'),
    (59.0, 62.4, 'rowan', "I'm Rowan. I draw maps."),
    (62.6, 65.7, 'juno', 'Juno. I make lanterns.'),
    (65.9, 69.9, 'rowan', 'Then maybe you can help me find my way.'),
    (71.0, 73.9, 'narrator', 'So she did.'),
    (74.0, 79.2, 'juno', 'This is the grove. Every tree here has a name.'),
    (79.6, 85.8, 'narrator', 'The days that followed were small, and bright, and full.'),
    (86.0, 90.8, 'rowan', 'Rivers, ridges, roads... I can map all of it.'),
    (91.0, 94.5, 'juno', 'Not all of it.'),
    (99.6, 103.2, 'rowan', 'Mine looks like a potato.'),
    (103.4, 107.6, 'juno', "A glowing potato. It's perfect."),
    (109.5, 119.0, 'narrator', 'They planted a tree on the hill. Neither of them said out loud what it was for.'),
    (124.0, 128.2, 'rowan', "The map's almost finished."),
    (128.6, 132.6, 'juno', '...And then you leave.'),
    (133.0, 138.0, 'rowan', "Cartographers always leave. It's the job."),
    (142.0, 153.5, 'narrator', 'That night the lanterns came on, one by one, all along the pier. The last post stayed dark.'),
    (158.4, 162.6, 'rowan', "I'll come back."),
    (163.0, 166.8, 'juno', 'Everyone says that.'),
    (173.0, 183.5, 'narrator', 'So Juno did the only thing she knew how to do. She made a lantern. The finest one she had ever made.'),
    (190.6, 195.0, 'juno', 'So you can find your way back.'),
    (198.0, 212.5, 'narrator', 'Winter came. The lake went still, and the snow fell on everything. And every night, the last lantern burned anyway.'),
    (215.5, 225.5, 'narrator', 'She waited. Not because she was sure... but because someone had to keep the light on.'),
    (228.0, 239.5, 'narrator', 'Then came spring. And far out on the dark water, a small light answered.'),
    (247.6, 251.0, 'rowan', 'I finished the map.'),
    (251.2, 256.0, 'rowan', 'Turns out every road on it leads here.'),
    (257.0, 260.6, 'juno', 'You followed the lantern.'),
    (261.4, 264.4, 'rowan', 'I followed you.'),
    (271.0, 284.0, 'narrator', 'Some maps are drawn to help you leave. The best ones... show you the way home.'),
]


def resample(x, sr_in, sr_out=SR):
    n = int(len(x) * sr_out / sr_in)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def trim(x, thr=0.004):
    idx = np.where(np.abs(x) > thr)[0]
    return x[max(0, idx[0] - 200): idx[-1] + 2000] if len(idx) else x


def room(x, seconds=0.45, wet=0.12):
    rng = np.random.default_rng(3)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t * 14)
    ir /= np.sqrt(np.sum(ir ** 2))
    y = np.convolve(x, ir)
    out = np.zeros(len(y))
    out[: len(x)] += x * (1 - wet)
    return out + y * wet


def read_wav(p):
    w = wave.open(p)
    a = np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, 2).astype(np.float64) / 32768
    return a.T.copy()


k = Kokoro('tts/kokoro-v1.0.onnx', 'tts/voices-v1.0.bin')
music = read_wav('out/score.wav')
N = music.shape[1]
voice = np.zeros((2, N))
speech_mask = np.zeros(N)

for start, end, who, text in LINES:
    speed = SPEED[who]
    for attempt in range(6):
        samples, sr = k.create(text, voice=VOICE[who], speed=speed, lang='en-gb' if who == 'narrator' else 'en-us')
        clip = trim(resample(np.asarray(samples, dtype=np.float64), sr))
        dur = len(clip) / SR
        if start + dur <= end + 0.15 or attempt == 5:
            break
        speed *= min(1.12, (dur / (end - start)) ** 0.8 + 0.01)
    status = 'ok ' if start + dur <= end + 0.15 else 'LONG'
    short = re.sub(r'\s+', ' ', text)[:60]
    print(f"{status} {start:6.1f}s {who:8s} {dur:4.1f}s/{end - start:4.1f}s  speed {speed:.2f}  {short}")
    clip = clip / (np.max(np.abs(clip)) + 1e-9) * 0.7 * GAIN[who]
    clip = room(clip, wet=0.08 if who == 'narrator' else 0.14)
    i0 = int(start * SR)
    seg = clip[: N - i0]
    pan = {'juno': -0.08, 'rowan': 0.08, 'narrator': 0.0}[who]
    voice[0, i0:i0 + len(seg)] += seg * np.cos((pan + 1) * np.pi / 4) * 1.414
    voice[1, i0:i0 + len(seg)] += seg * np.sin((pan + 1) * np.pi / 4) * 1.414
    speech_mask[i0:i0 + len(seg)] = 1

# duck the score under speech with smooth attack/release
win = int(0.35 * SR)
kernel = np.hanning(win * 2)
kernel /= kernel.sum()
duck = np.convolve(speech_mask, kernel, mode='same')
duck = np.clip(duck * 1.6, 0, 1)
music_gain = 1 - 0.55 * duck

mix = music * music_gain + voice * 0.95
peak = np.max(np.abs(mix))
mix = np.tanh(mix / peak * 1.1) / np.tanh(1.1) * 0.92
pcm = (np.clip(mix.T, -1, 1) * 32767).astype('<i2')
with wave.open('out/final_mix.wav', 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('wrote out/final_mix.wav')
