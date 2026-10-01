# THE LAST LANTERN

*A 5-minute love story in blocks.*

A lantern maker named Juno waits at the end of a pier for someone worth lighting the last lantern for. Rowan is a wandering cartographer who arrives in the morning mist.

- **Screenplay:** [`SCREENPLAY.md`](SCREENPLAY.md)
- **Film:** `THE_LAST_LANTERN_1080p.mp4` (1920×1080 with 2.39:1 letterbox, 24 fps, 5:00, voiced, with stereo score)
- **Version française:** `LA_DERNIERE_LANTERNE_1080p.mp4`, the same picture with English subtitles and a French voice track (Juno: Kokoro `ff_siwis`; Rowan: Piper `fr_FR-tom`; narrator: Piper `fr_FR-upmc` Pierre)

## How it was made

The film is shot in a Minecraft-style voxel world rendered in real time with a custom Three.js "studio". Headless Chromium renders it offline, frame by frame. Every asset is original and generated from code:

| Department | What's in `film/` |
|---|---|
| **Texture pack** | `src/textures.js`: "Willow", a cozy 16×16 pack painted procedurally (grass, cherry blossom, timber-frame plaster, terracotta and teal roofs, lanterns, flowers…), sampled from a mip-mapped texture array |
| **Set** | `src/world.js`: the Willow Lake valley with a mountain ring, lake, beach, cherry grove, hill plateau, five cottages, Juno's workshop pavilion, and the pier with its lantern posts. The mesher adds per-vertex ambient occlusion |
| **Cast** | `src/characters.js`: Juno and Rowan, blocky rigs with hand-painted pixel skins, blinking, talking head-bob, walk, sit, crouch and hug poses |
| **Lighting** | `src/sky.js`: a graded time-of-day colour script (dawn → noon → golden hour → sunset → blue hour → night), a square sun and moon, stars, blocky clouds, and a sun or moon with PCF soft shadows. Lanterns drive a pool of real point lights. Windows glow at night |
| **Water & FX** | `src/materials.js`, `src/props.js`: planar mirror reflections with ripple normals and fresnel, lake mist layers, waving foliage, snow cover, cherry petals, snowfall, fireflies, chimney smoke, pixel hearts and rising sky lanterns |
| **Camera & post** | `src/film.js`, `src/main.js`: 27 shots with cranes, dollies, orbits, push-ins, depth of field with focus pulls, handheld micro-shake and cross-dissolves. Post adds HDR bloom, ACES tonemapping, a film grade (split-tone, vignette, grain, chromatic aberration), anamorphic letterbox, titles and subtitles |
| **Voices** | `voices.py`: Juno, Rowan and a storybook narrator, voiced with the open-source Kokoro neural TTS (`af_heart`, `am_michael`, `bm_george`). Each line is timed to the picture, the score is ducked under speech, and a touch of room reverb is added |
| **Score** | `music.py`: an original piano, strings, pad and bell score synthesized with numpy and cued to the picture, with lake, birdsong, winter wind and cricket ambience |

## Rendering

```bash
cd film
npm install
./render_all.sh          # ~4h on 4 CPU cores (software WebGL); resumable
python3 voices.py [fr]   # needs film/tts/kokoro-v1.0.onnx + voices-v1.0.bin; writes out/final_mix.wav
```

Stills of individual frames: `node render.mjs --stills 700,3000,6600 --dir stills`.
