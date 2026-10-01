"""Voice track for THE LAST LANTERN: Juno, Rowan and a narrator (Kokoro TTS).

Lines are timed to the picture. The score is ducked under speech, a little
room reverb is added, and out/final_mix.wav is written.
"""
import numpy as np
import wave
import re
import sys
from kokoro_onnx import Kokoro

FRENCH = len(sys.argv) > 1 and sys.argv[1] == 'fr'

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


LINES_FR = [
    (3.6, 12.6, 'narrator', "Chaque village a une histoire qu'il se raconte. Au Lac des Saules, c'était l'histoire d'une lanterne."),
    (14.8, 24.0, 'narrator', "Juno fabriquait des lanternes. Toutes brillaient le long du vieux ponton. Toutes, sauf la dernière."),
    (26.5, 30.0, 'juno', "Grand-mère disait toujours que le dernier poteau attend..."),
    (30.1, 35.5, 'juno', "...quelqu'un pour qui ça vaut la peine de l'allumer."),
    (37.0, 46.0, 'narrator', "Et un matin de printemps, sortant de la brume, arriva quelqu'un qui n'était jamais resté nulle part assez longtemps pour s'y sentir chez soi."),
    (49.6, 54.2, 'rowan', "Bonjour ! C'est bien... le Lac des Saules ? Il n'est sur aucune carte."),
    (54.4, 58.0, 'juno', "Alors ta carte est fausse."),
    (59.0, 62.4, 'rowan', "Moi, c'est Rowan. Je dessine des cartes."),
    (62.6, 65.7, 'juno', "Juno. Je fabrique des lanternes."),
    (65.9, 69.9, 'rowan', "Alors tu pourras peut-être m'aider à trouver mon chemin."),
    (71.0, 73.9, 'narrator', "Et c'est ce qu'elle fit."),
    (74.0, 79.2, 'juno', "Voici le bosquet. Chaque arbre ici a un nom."),
    (79.6, 85.8, 'narrator', "Les jours qui suivirent furent petits, lumineux, et pleins."),
    (86.0, 90.8, 'rowan', "Rivières, crêtes, chemins... je peux tout cartographier."),
    (91.0, 94.5, 'juno', "Pas tout."),
    (99.6, 103.2, 'rowan', "La mienne ressemble à une patate."),
    (103.4, 107.6, 'juno', "Une patate lumineuse. Elle est parfaite."),
    (109.5, 119.0, 'narrator', "Ils plantèrent un arbre sur la colline. Aucun des deux ne dit à voix haute à quoi il servait."),
    (124.0, 128.2, 'rowan', "La carte est presque finie."),
    (128.6, 132.6, 'juno', "...Et ensuite tu pars."),
    (133.0, 138.0, 'rowan', "Les cartographes partent toujours. C'est le métier."),
    (142.0, 153.5, 'narrator', "Ce soir-là, les lanternes s'allumèrent une à une, tout le long du ponton. Le dernier poteau resta dans le noir."),
    (158.4, 162.6, 'rowan', "Je reviendrai."),
    (163.0, 166.8, 'juno', "Tout le monde dit ça."),
    (173.0, 183.5, 'narrator', "Alors Juno fit la seule chose qu'elle savait faire. Elle fabriqua une lanterne. La plus belle qu'elle ait jamais faite."),
    (190.6, 195.0, 'juno', "Pour que tu retrouves ton chemin."),
    (198.0, 212.5, 'narrator', "L'hiver arriva. Le lac s'immobilisa, et la neige recouvrit tout. Et chaque nuit, la dernière lanterne brûlait quand même."),
    (215.5, 225.5, 'narrator', "Elle attendit. Pas parce qu'elle en était sûre... mais parce que quelqu'un devait garder la lumière allumée."),
    (228.0, 239.5, 'narrator', "Puis vint le printemps. Et loin sur l'eau sombre, une petite lumière répondit."),
    (247.6, 251.0, 'rowan', "J'ai fini la carte."),
    (251.2, 256.0, 'rowan', "Il se trouve que tous ses chemins mènent ici."),
    (257.0, 260.6, 'juno', "Tu as suivi la lanterne."),
    (261.4, 264.4, 'rowan', "C'est toi que j'ai suivie."),
    (271.0, 284.0, 'narrator', "Certaines cartes sont faites pour partir. Les plus belles... montrent le chemin de la maison."),
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
if FRENCH:
    from piper import PiperVoice, SynthesisConfig
    PIPER = {'rowan': (PiperVoice.load('tts/fr_FR-tom-medium.onnx'), None), 'narrator': (PiperVoice.load('tts/fr_FR-upmc-medium.onnx'), 1)}
    LINES = LINES_FR
    SPEED = {'juno': 0.95, 'rowan': 1.0, 'narrator': 0.92}


def synth(text, who, speed):
    if FRENCH and who in PIPER:
        v, spk = PIPER[who]
        chunks = list(v.synthesize(text, SynthesisConfig(speaker_id=spk, length_scale=1 / speed)))
        return np.concatenate([c.audio_float_array for c in chunks]), chunks[0].sample_rate
    if FRENCH:
        return k.create(text, voice='ff_siwis', speed=speed, lang='fr-fr')
    return k.create(text, voice=VOICE[who], speed=speed, lang='en-gb' if who == 'narrator' else 'en-us')
music = read_wav('out/score.wav')
N = music.shape[1]
voice = np.zeros((2, N))
speech_mask = np.zeros(N)

for start, end, who, text in LINES:
    speed = SPEED[who]
    for attempt in range(6):
        samples, sr = synth(text, who, speed)
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
OUT = 'out/final_mix_fr.wav' if FRENCH else 'out/final_mix.wav'
with wave.open(OUT, 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('wrote', OUT)
