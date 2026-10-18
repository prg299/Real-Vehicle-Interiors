"""Developer helper: turn dev/review_interiors.ps1's raw captures into things to look at.

    python dev/review_sheet.py <captures dir> <key> [zoom]

Crops the game's client area round the vehicle and writes, next to the captures,
<key>_sheet.png (the four headings side by side in a 2 x 2 grid) and, for each heading,
<key>_<heading>_big.png (the vehicle enlarged 2x, for judging edges and what pokes out)."""
import os
import sys

from PIL import Image, ImageDraw

CLIENT = (8, 31, 1288, 751)
HEADINGS = ("N", "E", "S", "W")


def vehicle_box(image):
    """The area round the vehicle: the test spot is where the camera is centred."""
    w, h = image.size
    return (int(w * 0.10), int(h * 0.08), int(w * 0.92), int(h * 0.98))


def main():
    folder, key = sys.argv[1], sys.argv[2]
    tiles = []
    for heading in HEADINGS:
        path = os.path.join(folder, "%s_%s.png" % (key, heading))
        if not os.path.exists(path):
            continue
        image = Image.open(path).convert("RGB").crop(CLIENT)
        image = image.crop(vehicle_box(image))
        big = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)
        big.save(os.path.join(folder, "%s_%s_big.png" % (key, heading)))
        label = image.copy()
        ImageDraw.Draw(label).text((10, 8), "%s facing %s" % (key, heading), fill=(255, 255, 255))
        tiles.append(label)
    if not tiles:
        raise SystemExit("no captures for " + key)
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * 2, h * 2), (20, 20, 20))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 2) * w, (i // 2) * h))
    sheet.save(os.path.join(folder, "%s_sheet.png" % key))
    print("sheet", sheet.size, "tiles", len(tiles))


main()
