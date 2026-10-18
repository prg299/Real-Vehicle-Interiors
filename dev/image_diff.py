"""Developer helper: what changed between two captures of the test game.

    python dev/image_diff.py <base.png> <other.png> [<noise.png>] [--roi x0 y0 x1 y1]

Prints `count x0 y0 x1 y1` for the pixels that differ (client area only; with --roi only those
inside the box, client-area pixels). A third capture of the same scene as <base.png> marks the
pixels that change by themselves (an idle animation) so they are not counted."""
import sys

import numpy as np
from PIL import Image

CLIENT = (8, 31, 1288, 751)


def load(path):
    return np.asarray(Image.open(path).convert("RGB").crop(CLIENT)).astype(np.int16)


def main():
    argv = sys.argv[:]
    roi = None
    if "--roi" in argv:
        i = argv.index("--roi")
        roi = [int(v) for v in argv[i + 1:i + 5]]
        del argv[i:i + 5]
    base, other = load(argv[1]), load(argv[2])
    changed = np.abs(base - other).sum(axis=2) > 36
    if len(argv) > 3:
        noise = np.abs(base - load(argv[3])).sum(axis=2) > 12
        # grow the noise a little: an animated limb moves by a few pixels
        grown = noise.copy()
        for dy in (-3, 0, 3):
            for dx in (-3, 0, 3):
                grown |= np.roll(np.roll(noise, dy, axis=0), dx, axis=1)
        changed &= ~grown
    if roi:
        mask = np.zeros_like(changed)
        mask[roi[1]:roi[3], roi[0]:roi[2]] = True
        changed &= mask
    ys, xs = np.nonzero(changed)
    if len(xs) == 0:
        print("0 0 0 0 0")
    else:
        print("%d %d %d %d %d" % (len(xs), xs.min(), ys.min(), xs.max(), ys.max()))


main()
