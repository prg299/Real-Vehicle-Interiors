"""Developer helper: tight, enlarged crops of dev/review_interiors.ps1's captures, to look at.

    python dev/review_zoom.py <captures dir> <key> [<key> ...]

Writes <key>_<heading>_zoom.png next to the captures (the vehicle enlarged about 2x)."""
import os
import sys

from PIL import Image

CLIENT = (8, 31, 1288, 751)
folder = sys.argv[1]
for key in sys.argv[2:]:
    for heading in "NESW":
        path = os.path.join(folder, "%s_%s.png" % (key, heading))
        if not os.path.exists(path):
            continue
        image = Image.open(path).convert("RGB").crop(CLIENT)
        w, h = image.size
        if key in ("B700bus", "F700box"):
            box = (int(w * 0.04), int(h * 0.02), int(w * 0.98), int(h * 0.98))
            scale = 1.6
        else:
            box = (int(w * 0.17), int(h * 0.12), int(w * 0.93), int(h * 0.80))
            scale = 1.9
        crop = image.crop(box)
        crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
        crop.save(os.path.join(folder, "%s_%s_zoom.png" % (key, heading)))
print("ok")
