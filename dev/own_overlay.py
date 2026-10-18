"""Developer helper: paint what each group of ME: LENS' models draws over a capture (dev/own_overlay.ps1).

    python dev/own_overlay.py <captures dir> <key>

Reads <key>_base.png, <key>_noise.png and <key>_no_floor / _no_walls / _no_furniture.png and writes
<key>.png: the base capture, enlarged 2x round the vehicle, with the pixels the floor draws in magenta,
the walls' in cyan and the furniture's in yellow (a pixel two groups draw is the last one's colour: the
furniture's, then the walls', then the floor's). The pixels of a group that stick out past the hull
show on the black skin or the grass."""
import os
import sys

import numpy as np
from PIL import Image

CLIENT = (8, 31, 1288, 751)
folder, key = sys.argv[1], sys.argv[2]


def load(name):
    return np.asarray(Image.open(os.path.join(folder, "%s_%s.png" % (key, name))).convert("RGB").crop(CLIENT)).astype(np.int16)


base, noise = load("base"), load("noise")
moving = np.abs(base - noise).sum(axis=2) > 12
grown = moving.copy()
for dy in (-3, 0, 3):
    for dx in (-3, 0, 3):
        grown |= np.roll(np.roll(moving, dy, axis=0), dx, axis=1)
shown = base.copy().astype(np.uint8)
stats = []
for label, colour in (("furniture", (255, 255, 0)), ("walls", (0, 255, 255)), ("floor", (255, 0, 255))):
    path = os.path.join(folder, "%s_no_%s.png" % (key, label))
    if not os.path.exists(path):
        continue
    other = load("no_" + label)
    changed = (np.abs(base - other).sum(axis=2) > 36) & ~grown
    shown[changed] = colour
    stats.append("%s %d px" % (label, changed.sum()))
ys, xs = np.nonzero((shown != base.astype(np.uint8)).any(axis=2))
if len(xs):
    box = (max(0, xs.min() - 30), max(0, ys.min() - 30), min(shown.shape[1], xs.max() + 30), min(shown.shape[0], ys.max() + 30))
else:
    box = (0, 0, shown.shape[1], shown.shape[0])
image = Image.fromarray(shown).crop(box)
image = image.resize((image.width * 2, image.height * 2), Image.NEAREST)
image.save(os.path.join(folder, key + ".png"))
print("OWN %s: %s; box %s -> %s" % (key, ", ".join(stats), box, image.size))
