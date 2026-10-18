"""Developer helper: draw projected points onto a capture of the test game window.
    python dev/overlay.py <capture.png> <out.png> <spec>
spec: groups separated by '|', each 'kind:colour:sx,sy;sx,sy;...' with kind 'poly' (closed
outline) or 'dots'; points are game screen coordinates (dev/lua/project_points.lua).
The capture is the whole window, so the client area starts at the frame offset."""
import sys
from PIL import Image, ImageDraw

FRAME_X, FRAME_Y = 8, 31

capture, out, spec = sys.argv[1], sys.argv[2], sys.argv[3]
im = Image.open(capture).convert("RGB")
draw = ImageDraw.Draw(im)
for group in spec.split("|"):
    kind, colour, pts = group.split(":", 2)
    xy = [(float(a) + FRAME_X, float(b) + FRAME_Y) for a, b in (p.split(",") for p in pts.split(";"))]
    if kind == "poly":
        draw.line(xy + [xy[0]], fill=colour, width=2)
    else:
        for x, y in xy:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), outline=colour, width=2)
im.save(out)
print("saved", out)
