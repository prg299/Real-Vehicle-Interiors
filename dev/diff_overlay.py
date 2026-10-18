"""Developer helper: show where two captures of the test game differ.

    python dev/diff_overlay.py <base.png> <other.png> <out.png> [<noise.png>] [x0 y0 x1 y1]

Writes <out.png>: the base capture (client area) with the changed pixels painted magenta and
the region round them enlarged 2x (or the given client-area box). A third capture of the same
scene as <base.png> marks the pixels that change by themselves so they are left out."""
import sys

import numpy as np
from PIL import Image

CLIENT = (8, 31, 1288, 751)


def load(path):
    return Image.open(path).convert("RGB").crop(CLIENT)


def main():
    base_img, other_img = load(sys.argv[1]), load(sys.argv[2])
    out = sys.argv[3]
    rest = sys.argv[4:]
    noise_path = rest.pop(0) if rest and not rest[0].lstrip("-").isdigit() else None
    base = np.asarray(base_img).astype(np.int16)
    other = np.asarray(other_img).astype(np.int16)
    changed = np.abs(base - other).sum(axis=2) > 36
    if noise_path:
        noise = np.abs(base - np.asarray(load(noise_path)).astype(np.int16)).sum(axis=2) > 12
        grown = noise.copy()
        for dy in (-3, 0, 3):
            for dx in (-3, 0, 3):
                grown |= np.roll(np.roll(noise, dy, axis=0), dx, axis=1)
        changed &= ~grown
    ys, xs = np.nonzero(changed)
    print("changed", len(xs))
    shown = base.copy().astype(np.uint8)
    # paint the changed pixels, slightly grown so single pixels can be seen
    grown = changed.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            grown |= np.roll(np.roll(changed, dy, axis=0), dx, axis=1)
    shown[grown] = (255, 0, 255)
    image = Image.fromarray(shown)
    if len(rest) == 4:
        box = tuple(int(v) for v in rest)
    elif len(xs):
        box = (max(0, xs.min() - 40), max(0, ys.min() - 40), min(image.width, xs.max() + 40), min(image.height, ys.max() + 40))
    else:
        box = (0, 0, image.width, image.height)
    crop = image.crop(box)
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
    crop.save(out)
    print("box", box, "->", crop.size)


main()
