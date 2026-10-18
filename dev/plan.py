"""Developer helper: draw a vehicle's measured floor plan (passenger space, seen from
above, the front at the top, the vehicle's left on the left) to design its ME: LENS
layout: the inside outline at a few heights, the measured parts (grey: furniture and
cushions, blue: windows, green: doors), the KI5 seats (red dots, with ids) and wheels.
    python dev/plan.py <measure.json> <scripts.json> <vehicle> <out.png> [scale px/tile]"""
import json
import sys

from PIL import Image, ImageDraw

measure = json.load(open(sys.argv[1], encoding="utf-8"))
scripts = json.load(open(sys.argv[2], encoding="utf-8"))
info = scripts[sys.argv[3]]
out = sys.argv[4]
S = float(sys.argv[5]) if len(sys.argv) > 5 else 120.0

b = measure["body"]
xmin, xmax = b["min"][0] - 0.3, b["max"][0] + 0.3
zmin, zmax = b["min"][2] - 0.3, b["max"][2] + 0.3
W, H = int((xmax - xmin) * S) + 240, int((zmax - zmin) * S) + 20


def P(x, z):
    # the vehicle's left (+x) on the left of the picture, the front (+z) at the top
    return (xmax - x) * S + 10, (zmax - z) * S + 10


im = Image.new("RGB", (W, H), (250, 250, 248))
d = ImageDraw.Draw(im)
for t in range(int(zmin) - 1, int(zmax) + 2):          # grid, 1 tile
    d.line([P(xmin, t), P(xmax, t)], fill=(225, 225, 225))
for t in range(int(xmin) - 1, int(xmax) + 2):
    d.line([P(t, zmin), P(t, zmax)], fill=(225, 225, 225))
floor = measure["floor"]
colours = [(200, 60, 60), (40, 40, 40), (120, 120, 200)]
heights = sorted(measure["outlines"], key=float)
for i, dh in enumerate((0.05, 0.4, 1.0)):
    key = min(heights, key=lambda k: abs(float(k) - (floor + dh)))
    ring = measure["outlines"].get(key) or []
    if len(ring) > 2:
        d.line([P(x, z) for x, z in ring] + [P(*ring[0])], fill=colours[i], width=2 if i == 1 else 1)
for name, bb in measure["parts"].items():
    lo, hi = bb["min"], bb["max"]
    if "body" in name or "interior" in name:
        continue
    colour = (150, 150, 150)
    if "window" in name or "windshield" in name:
        colour = (70, 110, 220)
    elif "door" in name:
        colour = (40, 160, 70)
    d.rectangle([P(hi[0], hi[2]), P(lo[0], lo[2])], outline=colour, width=2)
    if colour == (150, 150, 150) and (hi[0] - lo[0]) > 0.15:
        d.text(P(hi[0], hi[2]), "%s %.2f" % (name.split("_", 1)[-1], hi[1]), fill=(90, 90, 90))
scale = info["model"]["scale"]
for p in info["passengers"]:
    off = (p.get("inside") or {}).get("offset")
    if not off or p["id"] in ("*", "DAMNFakeSeat"):
        continue
    x, y, z = (v * scale for v in off)
    cx, cy = P(x, z)
    d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(220, 30, 30))
    d.text((cx + 6, cy - 6), "%s y%.2f" % (p["id"], y), fill=(160, 20, 20))
for name, off in info["wheels"].items():
    if off:
        x, y, z = (v * scale for v in off)
        cx, cy = P(x, z)
        d.rectangle([cx - 6, cy - 12, cx + 6, cy + 12], outline=(0, 0, 0), width=2)
d.text((10, H - 16), "%s  floor %.2f  ceiling %.2f  (1 grid square = 1 tile; top = front, left = vehicle's left)" % (
    measure["name"], floor, measure["ceiling"]), fill=(0, 0, 0))
im.save(out)
print("plan", out, im.size)
