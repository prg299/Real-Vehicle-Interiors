"""Developer helper: how many pure magenta pixels (what MELensRV.setRoomDebug paints) a capture
has inside a box of client-area pixels.

    python dev/magenta_count.py <capture.png> <x0> <y0> <x1> <y1>

Prints `count x0 y0 x1 y1` of the magenta pixels inside the box (0 0 0 0 0 when none)."""
import sys

import numpy as np
from PIL import Image

CLIENT = (8, 31, 1288, 751)
image = np.asarray(Image.open(sys.argv[1]).convert("RGB").crop(CLIENT)).astype(np.int16)
x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
box = image[y0:y1, x0:x1]
mask = (box[:, :, 0] > 230) & (box[:, :, 1] < 40) & (box[:, :, 2] > 230)
ys, xs = np.nonzero(mask)
if len(xs) == 0:
    print("0 0 0 0 0")
else:
    print("%d %d %d %d %d" % (len(xs), xs.min() + x0, ys.min() + y0, xs.max() + x0, ys.max() + y0))
