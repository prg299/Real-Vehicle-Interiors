"""Developer helper: the same region of several captures side by side, enlarged.

    python dev/roi_sheet.py <out.png> <x0> <y0> <x1> <y1> <scale> <capture.png> [<capture.png> ...]

The box is in client-area pixels of the test game's window captures."""
import sys

from PIL import Image, ImageDraw

CLIENT = (8, 31, 1288, 751)
out = sys.argv[1]
x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
scale = float(sys.argv[6])
paths = sys.argv[7:]
tiles = []
for path in paths:
    crop = Image.open(path).convert("RGB").crop(CLIENT).crop((x0, y0, x1, y1))
    crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
    ImageDraw.Draw(crop).text((4, 4), path.replace("\\", "/").split("/")[-1], fill=(255, 255, 0))
    tiles.append(crop)
cols = 2 if len(tiles) > 1 else 1
rows = (len(tiles) + cols - 1) // cols
w, h = tiles[0].size
sheet = Image.new("RGB", (w * cols, h * rows), (20, 20, 20))
for i, tile in enumerate(tiles):
    sheet.paste(tile, ((i % cols) * w, (i // cols) * h))
sheet.save(out)
print(sheet.size)
