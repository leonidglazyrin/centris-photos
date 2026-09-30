# Taxing corporations on unrealized gains (vertical, Minecraft-style)

`corporate_unrealized_gains_minecraft.mp4` is a ~82 second vertical video (1080×2340, the iPhone 15 Pro's 19.5:9 aspect).

**Story** (a real, profitable business that still can't pay):
1. Blockworks makes diamond tools and sells them at the market. Year 1: 300 emeralds of sales, minus 200 for wages and materials, is 100 of profit. It pays normal profit tax (-20) and keeps 80 in cash.
2. Its vault of 50 diamond blocks (next year's raw material) doubles in price, from 1,000 to 2,000. That's a +1,000 gain on paper, with nothing sold.
3. An unrealized-gains tax bills 20% of that: 200 emeralds. It has 80 in cash, which was meant for wages and equipment, so 120 is missing.
4. It sells a diamond block, iron and part of its factory to cover the 120.
5. Year 2: with fewer materials and less factory, sales drop to 240. If prices rise again, the new bill is again bigger than its cash, so it sells more. The loop: prices rise, tax bill exceeds cash, sell assets, less revenue.
6. Production, jobs and investment shrink. Outro: today, gains are taxed when the asset is sold, because that's when the money is real.

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
