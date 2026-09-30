"""Render the same portrait shot with every texture pack -> build/packs/."""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import engine as E
import world as W

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build", "packs")
os.makedirs(OUT, exist_ok=True)
g = W.build_base()
W.tree(g, 87, 12, 91, 5)
W.tree(g, 100, 12, 93, 5)
ceo, tax = W.skin_set("ceo"), W.skin_set("taxman")
font = ImageFont.truetype(os.path.join(os.path.dirname(__file__), "assets", "Montserrat.ttf"), 64)
font.set_variation_by_name("ExtraBold")
tiles = []
for i, name in enumerate(sys.argv[1:] or list(E.PACKS)):
    E.configure(360, 780, name)
    cam = E.Camera((96.5, 19.5, 82.5), (93.0, 14.0, 99), 80)
    boxes = W.player(ceo, (91.3, 12, 92.0), 2.9) + W.player(tax, (93.6, 12, 91.2), -2.6, hat=True, arm_r=-1.3)
    img, _ = E.render(g, cam, 3.0, boxes, blobs=[(91.3, 92.0, 0.55), (93.6, 91.2, 0.55)])
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((1080, 2340), Image.NEAREST)
    d = ImageDraw.Draw(im)
    label = f"{i + 1}. {E.PACKS[name]['title']}"
    d.text((540, 120), label, font=font, fill="white", anchor="mm", stroke_width=8, stroke_fill="black")
    im.save(os.path.join(OUT, f"{i + 1}_{name}.png"))
    tiles.append(im.resize((540, 1170), Image.LANCZOS))
    print("done", name, flush=True)
sheet = Image.new("RGB", (540 * len(tiles) + 20 * (len(tiles) - 1), 1170), (20, 20, 20))
for i, t in enumerate(tiles):
    sheet.paste(t, (i * 560, 0))
sheet.save(os.path.join(OUT, "contact_sheet.jpg"), quality=90)
