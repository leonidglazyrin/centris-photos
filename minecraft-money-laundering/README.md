# Money laundering, explained (vertical, Minecraft-style)

`money_laundering_minecraft.mp4` is a ~63 second vertical video (1080×2340, the iPhone 15 Pro's 19.5:9 aspect) using the **Faithful HD** texture pack (32px textures, sun shadows, smooth ambient occlusion).

**Story** (the script explains why each step exists):
1. Criminals can't just spend stolen money, because big purchases raise the question "where did this come from?" Laundering gives dirty money a fake, clean-looking story.
2. A griefer steals 64 emeralds. Buying a mansion with them outright would get him caught.
3. **Placement** (get the cash into the system): small deposits spread across banks and shops, so no single amount looks suspicious.
4. **Layering** (hide where it came from): the money moves through shell companies and an offshore account until nobody can follow the trail.
5. **Integration** (bring it back looking honest): a fake bakery reports the emeralds as sales, so they become "profit" and he buys the mansion openly.
6. **Red flags:** many small deposits, a tiny business with a huge income, and money moving in circles.
7. Investigators follow the trail, the story falls apart and the emeralds are seized. Title: "Follow the money."

The camera cuts to whatever the narration mentions, using word-level timing from the voice.

The HUD is two slots only (DIRTY and CLEAN emeralds). There is no chat, and captions are word-by-word in Montserrat.

## Re-render
```bash
pip install -r requirements.txt
python3 render.py --preview       # stills in build/preview/
python3 render.py                 # full video (JOBS=N workers, PACK=faithful|barebones|shaders|toon|pastel)
```

Fonts: Pixelify Sans and Montserrat (SIL Open Font License, see `assets/`). All textures, models, music and sound effects are procedural.
