# Why taxing unrealized gains doesn't work (Minecraft-style explainer)

`unrealized_gains_minecraft.mp4` is a ~62 second, 1080p/30fps explainer rendered entirely from code:

- `engine.py`: a small numpy voxel ray-caster with procedural 16x16 block textures, sky, clouds and fog, plus textured oriented boxes for the characters
- `world.py`: terrain, trees, Steve's house, the tax office, the nether portal, village houses and blocky characters
- `render.py`: narration (edge-tts), scene timeline, cameras, HUD/chat/GUI overlays, procedural music and sound effects, and parallel encoding with ffmpeg

## Story beats
1. **Intro**: taxing unrealized gains means taxing value you never sold.
2. **Paper gains**: Steve's 10-emerald plot is "worth" 100, but his chest is empty.
3. **Liquidity**: the 18-emerald tax bill forces him to sell roof blocks.
4. **Valuation**: three appraisers, three prices.
5. **Volatility**: the market crashes (TNT), and refunds would make revenue swing.
6. **Capital flight**: rich players leave through the portal. The OECD counted 12 countries with a wealth tax in 1990 and 4 in 2017.
7. **Outro**: tax gains when they're real, when you sell.

## Re-render
```bash
pip install -r requirements.txt
python3 render.py --preview        # sample stills in build/preview/
python3 render.py                  # full video (JOBS=N to set worker count)
```

The font is Pixelify Sans (SIL Open Font License, see `assets/OFL.txt`). All textures, characters, music and sound effects are generated procedurally. No Minecraft assets are used.
