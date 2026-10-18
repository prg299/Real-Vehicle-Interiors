# Turns the generated RV furniture icons (tools-src/art/icons/icon_<piece>.png, see
# generate.ps1) into the mod's inventory icons: the background removed when the image
# has none, cropped to the object, padded square and scaled to 64 x 64.
#
#   python tools-src/art/icons.py <mod media folder>
import os
import sys
from collections import deque

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PIECES = ["bed", "dinette", "kitchen", "fridge", "cabinet", "wardrobe", "washroom", "heater", "shelf",
          "box", "busseat", "busseat2"]
SIZE = 64


def remove_background(im):
    """Clears the background by flooding in from the border over pixels close to the
    border's colours (a plain backdrop, or the checkerboard some images fake)."""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    border = [px[x, 0] for x in range(0, w, 7)] + [px[x, h - 1] for x in range(0, w, 7)]
    border += [px[0, y] for y in range(0, h, 7)] + [px[w - 1, y] for y in range(0, h, 7)]
    if sum(1 for c in border if c[3] < 20) > len(border) * 0.9:
        return im   # already transparent
    backdrop = []
    for c in border:
        if not any(abs(c[0] - b[0]) + abs(c[1] - b[1]) + abs(c[2] - b[2]) < 24 for b in backdrop):
            backdrop.append(c)
    backdrop = backdrop[:6]

    def is_backdrop(c):
        return any(abs(c[0] - b[0]) + abs(c[1] - b[1]) + abs(c[2] - b[2]) < 60 for b in backdrop)

    seen = bytearray(w * h)
    queue = deque()
    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))
    while queue:
        x, y = queue.popleft()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        c = px[x, y]
        if not is_backdrop(c):
            continue
        px[x, y] = (c[0], c[1], c[2], 0)
        if x > 0: queue.append((x - 1, y))
        if x < w - 1: queue.append((x + 1, y))
        if y > 0: queue.append((x, y - 1))
        if y < h - 1: queue.append((x, y + 1))
    return im


def make_icon(src, dst):
    im = remove_background(Image.open(src))
    box = im.getchannel("A").point(lambda a: 255 if a > 24 else 0).getbbox()
    if box:
        im = im.crop(box)
    side = int(max(im.size) * 1.06)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(im, ((side - im.width) // 2, (side - im.height) // 2))
    square = square.resize((SIZE, SIZE), Image.LANCZOS)
    square.save(dst)


def main():
    media = sys.argv[1]
    out_dir = os.path.join(media, "textures")
    made = 0
    for piece in PIECES:
        src = os.path.join(HERE, "icons", "icon_%s.png" % piece)
        if os.path.exists(src):
            make_icon(src, os.path.join(out_dir, "Item_MELensRV_%s.png" % piece))
            made += 1
        else:
            print("no generated icon for", piece)
    print("ICONS", made)


main()
