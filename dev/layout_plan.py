"""Developer helper: a plan view of a vehicle's furniture layout, to tune specs by eye.

    python dev/layout_plan.py <key> [key ...]        (writes build/rv/dbg/plan_<key>.png)

Draws, in passenger space (x to the left, z to the front; the picture has the front at the
top and the vehicle's left on the left): the inside outline at the floor, mid height and top
of the furniture (so a wall that curves in shows), each spot's piece footprint (red where it
overlaps another piece), the wheel wells, the door and its exit marker, and the cells the
character's centre may reach (dots). Reads the generated profile and shell config."""
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LUA = os.path.join(ROOT, "mod", "RealVehicleInteriors", "common", "media", "lua", "shared")
CFG = os.path.join(ROOT, "tools-src", "blender", "cfg")
SPECS = os.path.join(ROOT, "tools-src", "vehicles", "specs")
OUT = os.path.join(ROOT, "build", "rv", "dbg")
SCALE = 220
WALLS = {"front": ((-1, 0), (0, -1)), "back": ((1, 0), (0, 1)), "left": ((0, 1), (-1, 0)), "right": ((0, -1), (1, 0))}
COLOURS = {"bed": (200, 190, 150), "dinette": (90, 150, 160), "kitchen": (200, 160, 110), "fridge": (225, 225, 215),
           "cabinet": (170, 130, 90), "wardrobe": (110, 80, 60), "washroom": (180, 200, 220), "heater": (150, 100, 80),
           "busseat": (60, 110, 70), "busseat2": (60, 110, 70), "box": (190, 150, 100)}


def ordered(p0, p1):
    return [min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])]


def load(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def parse_spots(lua_text):
    """The entries of the profile's `spots = { ... }` (one line or several each)."""
    start = lua_text.index("spots = {") + len("spots = {")
    depth, begin, entries = 1, None, []
    for i in range(start, len(lua_text)):
        c = lua_text[i]
        if c == "{":
            depth += 1
            if depth == 2:
                begin = i
        elif c == "}":
            depth -= 1
            if depth == 1 and begin is not None:
                entries.append(lua_text[begin:i + 1])
                begin = None
            if depth == 0:
                break
    spots = []
    for text in entries:
        def field(name, pattern):
            m = re.search(name + r" = " + pattern, text)
            return m.group(1) if m else None
        spot = {"x": float(field("x", r"([-\d.]+)")), "z": float(field("z", r"([-\d.]+)")), "wall": field("wall", r'"(\w+)"'),
                "length": float(field("length", r"([\d.]+)")), "depth": float(field("depth", r"([\d.]+)")),
                "default": field("default", r'"(\w+)"'), "rise": float(field("rise", r"([\d.]+)") or 0.0)}
        spots.append(spot)
    return spots


def kit_sizes():
    sizes = {}
    with open(os.path.join(LUA, "MELens_RVKit.lua"), encoding="utf-8") as handle:
        for line in handle:
            m = re.match(r"\s*(\w+) = \{ width = ([\d.]+), depth = ([\d.]+), height = ([\d.]+),", line)
            if m:
                sizes[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)))
    sizes.setdefault("box", (0.5, 0.5, 0.4))
    return sizes


def rect(spot, sizes):
    width, depth, _ = sizes.get(spot["default"], (spot["length"], spot["depth"], 0.9))
    along, out = WALLS[spot["wall"]]
    pts = [(spot["x"] + along[0] * a + out[0] * d, spot["z"] + along[1] * a + out[1] * d)
           for a in (-width / 2, width / 2) for d in (0.0, depth)]
    return (min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))


def plan(key):
    spec = load(os.path.join(SPECS, key + ".json"))
    lua = open(os.path.join(LUA, "MELens_Profile_%s.lua" % key), encoding="utf-8").read()
    shell = load(os.path.join(CFG, "shell_%s.json" % key))
    measure = load(shell["measure"])
    floor = shell["floorY"]
    spots = parse_spots(lua)
    sizes = kit_sizes()
    stand = re.search(r"door = \{ x = ([-\d.]+), z = ([-\d.]+) \}", lua)
    marker = re.search(r"exitMarker = \{\s*x = ([-\d.]+),\s*z = ([-\d.]+),\s*halfX = ([\d.]+),\s*halfZ = ([\d.]+)", lua, re.S)

    ring = measure["outlines"][min(measure["outlines"], key=lambda k: abs(float(k) - (floor + 0.25)))]
    xs = [p[0] for p in ring]
    zs = [p[1] for p in ring]
    pad = 0.3
    x0, x1, z0, z1 = min(xs) - pad, max(xs) + pad, min(zs) - pad, max(zs) + pad
    w, h = int((x1 - x0) * SCALE), int((z1 - z0) * SCALE)
    image = Image.new("RGB", (w, h), (40, 42, 46))
    draw = ImageDraw.Draw(image, "RGBA")

    def px(x, z):        # the vehicle's left on the picture's left, the front at the top
        return ((x1 - x) * SCALE, (z1 - z) * SCALE)

    # the walk grid, faintly
    grid_file = os.path.join(LUA, "MELens_WalkGrid_%s_Shell.lua" % key)
    if os.path.exists(grid_file):
        text = open(grid_file, encoding="utf-8").read()
        g = re.search(r"x0 = ([-\d.]+), z0 = ([-\d.]+), cell = ([\d.]+), cols = (\d+)", text)
        gx0, gz0, cell, cols = float(g.group(1)), float(g.group(2)), float(g.group(3)), int(g.group(4))
        for r, row in enumerate(re.findall(r'"([01]+)",', text)):
            for c, ch in enumerate(row):
                if ch == "1" and (r % 2 == 0) and (c % 2 == 0):
                    x = gx0 + (c + 0.5) * cell
                    z = gz0 + (r + 0.5) * cell
                    p = px(x, z)
                    draw.point(p, fill=(90, 110, 90))

    # outlines at the floor, mid and top of furniture
    for height, colour in ((0.06, (120, 200, 255)), (0.5, (255, 220, 120)), (0.95, (255, 120, 120))):
        key_h = min(measure["outlines"], key=lambda k: abs(float(k) - (floor + height)))
        pts = [px(*p) for p in measure["outlines"][key_h]]
        draw.line(pts + [pts[0]], fill=colour + (255,), width=1)

    for well in shell.get("wheelWells", []):
        a, b = sorted(well["x"])
        p0, p1 = px(a, well["z"][1]), px(b, well["z"][0])
        draw.rectangle(ordered(p0, p1), outline=(200, 200, 200, 255), fill=(120, 120, 130, 90))

    prints = [rect(s, sizes) for s in spots]
    font = ImageFont.load_default()
    for i, (spot, box) in enumerate(zip(spots, prints)):
        bad = any(j != i and not (spots[j]["rise"] != spots[i]["rise"]) and
                  box[0] < prints[j][1] - 0.011 and prints[j][0] < box[1] - 0.011 and
                  box[2] < prints[j][3] - 0.011 and prints[j][2] < box[3] - 0.011 for j in range(len(spots)))
        colour = (220, 40, 40) if bad else COLOURS.get(spot["default"], (180, 180, 180))
        p0, p1 = px(box[0], box[3]), px(box[1], box[2])
        draw.rectangle(ordered(p0, p1), fill=colour + (150,), outline=colour + (255,))
        if spot["rise"] == 0:
            draw.text((min(p0[0], p1[0]) + 3, min(p0[1], p1[1]) + 2), "%d %s" % (i + 1, spot["default"]), fill=(255, 255, 255), font=font)

    if stand:
        sx, sz = float(stand.group(1)), float(stand.group(2))
        cx, cy = px(sx, sz)
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], outline=(80, 255, 80, 255), width=2)
    if marker:
        mx, mz, hx, hz = [float(marker.group(i)) for i in range(1, 5)]
        p0, p1 = px(mx + hx, mz + hz), px(mx - hx, mz - hz)
        draw.rectangle(ordered(p0, p1), outline=(80, 255, 80, 255))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "plan_%s.png" % key)
    image.save(path)
    print("saved", path, image.size)


for name in sys.argv[1:]:
    plan(name)
