# Money laundering, explained (vertical, Minecraft-style)

`money_laundering_minecraft.mp4` is a ~47 second vertical video (1080×2340, the iPhone 15 Pro's 19.5:9 aspect) using the **Faithful HD** texture pack (32px textures, sun shadows, smooth ambient occlusion).

**Story:**
1. A griefer's stolen emeralds are "dirty": everyone knows where they came from.
2. **Placement:** small deposits go into several banks and shops.
3. **Layering:** the emeralds bounce between shell companies and an offshore account, leaving a tangled red trail.
4. **Integration:** the money comes back as "profits" from a Totally Legit Bakery and is spent on a mansion.
5. **Red flags:** many small deposits, a business earning more than it plausibly could, and money moving in circles.
6. Investigators (an iron golem) follow the trail, the mansion is seized and the scheme collapses. Title: "Follow the money."

The HUD is two slots only (DIRTY and CLEAN emeralds). There is no chat, and captions are word-by-word in Montserrat.

## Re-render
```bash
pip install -r requirements.txt
python3 render.py --preview       # stills in build/preview/
python3 render.py                 # full video (JOBS=N workers, PACK=faithful|barebones|shaders|toon|pastel)
```

Fonts: Pixelify Sans and Montserrat (SIL Open Font License, see `assets/`). All textures, models, music and sound effects are procedural.
