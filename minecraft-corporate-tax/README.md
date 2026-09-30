# Taxing corporations on unrealized gains (vertical, Minecraft-style)

`corporate_unrealized_gains_minecraft.mp4` is a ~50 second vertical video (1080×2340, the iPhone 15 Pro's 19.5:9 aspect).

**Story:** Blockworks Inc. owns a factory, an iron stockpile and 50 diamond blocks. Diamond prices double, which creates a +1,000 emerald gain on paper, but the company has 0 new emeralds. It gets a 200-emerald tax bill and has to sell diamonds, iron and part of its factory to a buyer. The next year prices rise again, a new bill arrives, and it sells more. The loop shrinks production, jobs and investment. Outro: tax gains when the asset is actually sold.

## Look
- **Texture pack "Bare Bones"** (clean, flat colors). Four other packs are available through `PACK=faithful|shaders|toon|pastel` (see `engine.PACKS`). `python3 pack_preview.py` renders the comparison sheet in `build/packs/`.
- The engine supports sun shadows, Minecraft-style smooth ambient occlusion, color grading and toon outlines, depending on the pack.
- **Captions** are word-by-word in Montserrat ExtraBold, synced to the voice's word timings.
- **UI:** in-world labels use a pixel font. There is no chat, and the only HUD is the three inventory slots the story needs (diamonds, iron, emeralds).

## Re-render
```bash
pip install -r requirements.txt
python3 render.py --preview       # stills in build/preview/
python3 render.py                 # full video (JOBS=N workers, PACK=... texture pack)
```

Fonts: Pixelify Sans and Montserrat (SIL Open Font License, see `assets/`). All textures, models, music and sound effects are procedural.
