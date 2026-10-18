"""Developer helper: tan or brown things on the outside edge of a vehicle in a capture.

    python dev/edge_tan.py <capture.png> [<reference.png>] [<out.png>]

The inside of a vehicle is cut open, so what sticks out past the hull shows against the grass: this
finds the warm-coloured (floor planks, wood, cardboard) pixels that touch grass (within 3 px) and
lists their connected blobs, bounding box first (client-area pixels of the capture). With a
reference capture of the same scene without ME: LENS' inside (the vehicle drawn uncut by
MELensRV.clearCutaway()), blobs that are also in the reference are KI5's own and are marked so.
<out.png> (default <capture>_tan.png) is the capture enlarged 2x with boxes round the blobs."""
import sys

import numpy as np
from PIL import Image, ImageDraw

CLIENT = (8, 31, 1288, 751)


def load(path):
    return np.asarray(Image.open(path).convert("RGB").crop(CLIENT)).astype(np.int16)


def masks(image):
    r, g, b = image[:, :, 0], image[:, :, 1], image[:, :, 2]
    grass = (g > r + 6) & (g > b + 30)
    tan = (r > 120) & (r >= g) & (g >= b) & (r - b > 45) & ~grass
    return grass, tan


def grow(mask, n):
    out = mask.copy()
    for dy in range(-n, n + 1):
        for dx in range(-n, n + 1):
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def blobs(mask):
    seen = np.zeros_like(mask, dtype=bool)
    found = []
    h, w = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, cells = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            cells.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        ys = [c[0] for c in cells]
        xs = [c[1] for c in cells]
        found.append((len(cells), min(xs), min(ys), max(xs), max(ys)))
    return found


def main():
    path = sys.argv[1]
    reference = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].endswith(".png") and not sys.argv[2].endswith("_tan.png") else None
    out = sys.argv[3] if len(sys.argv) > 3 else path[:-4] + "_tan.png"
    image = load(path)
    grass, tan = masks(image)
    edge = tan & grow(grass, 3)
    edge = grow(edge, 2) & tan            # tan pixels beside an edge pixel belong to the same thing
    ref_edge = None
    if reference:
        rg, rt = masks(load(reference))
        ref_edge = grow(rt & grow(rg, 3), 5)
    shown = Image.fromarray(image.astype(np.uint8)).resize((image.shape[1] * 2, image.shape[0] * 2), Image.NEAREST)
    draw = ImageDraw.Draw(shown)
    rows = []
    for n, x0, y0, x1, y1 in blobs(edge):
        if n < 3:
            continue
        ours = ""
        if ref_edge is not None:
            inside = ref_edge[y0:y1 + 1, x0:x1 + 1]
            ours = "KI5's own" if inside.mean() > 0.3 else "NOT in the reference"
        rows.append((n, x0, y0, x1, y1, ours))
        colour = (255, 0, 255) if ours != "KI5's own" else (0, 255, 255)
        draw.rectangle((x0 * 2 - 6, y0 * 2 - 6, x1 * 2 + 6, y1 * 2 + 6), outline=colour, width=2)
    rows.sort(key=lambda r: -r[0])
    for n, x0, y0, x1, y1, ours in rows[:40]:
        print("TAN %4d px  box %4d,%4d - %4d,%4d  %s" % (n, x0, y0, x1, y1, ours))
    print("TAN blobs: %d (%d not in the reference)" % (len(rows), sum(1 for r in rows if r[5] == "NOT in the reference")))
    shown.save(out)


main()
