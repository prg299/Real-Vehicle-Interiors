# Developer helper: puts the middle of each screenshot (where the camera's player stands) side by side, enlarged.
#   python dev/sheet.py out.png shot1.png shot2.png ...
import sys
from PIL import Image

out, shots = sys.argv[1], sys.argv[2:]
crops = []
for path in shots:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    cw, ch = w * 3 // 10, h * 4 // 10
    box = (w // 2 - cw // 2, h // 2 - ch // 2, w // 2 + cw // 2, h // 2 + ch // 2)
    crops.append(im.crop(box).resize((cw * 2, ch * 2), Image.LANCZOS))
cols = 2
rows = (len(crops) + cols - 1) // cols
cw, ch = crops[0].size
sheet = Image.new("RGB", (cw * cols, ch * rows), "white")
for i, c in enumerate(crops):
    sheet.paste(c, ((i % cols) * cw, (i // cols) * ch))
sheet.save(out)
print(out)
