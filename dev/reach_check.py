"""Developer helper: can you walk to everything inside each vehicle?

    python dev/reach_check.py [key ...]

Rebuilds the walk grid the way MELens_Cabin.lua does (the empty shell's grid with the default
furniture blocked out, character radius 0.15), floods it from the door, and checks that each
piece can be walked up to (the stand point in front of it, snapped to the nearest open cell as
M.walkTo does, must be reachable and within reach of the piece), that the utility panel can,
and how much of the floor is left to walk on. Exit code 1 on any unreachable target."""
import os
import re
import sys
from collections import deque

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LUA = os.path.join(ROOT, "mod", "RealVehicleInteriors", "common", "media", "lua", "shared")
SHOW_MAP = "map" in sys.argv[1:]
KEYS = [a for a in sys.argv[1:] if a != "map"] or ["FlyingCloud22", "Bambi16", "Airflyte", "Scamp13", "Scamp16", "B700", "F700box"]
WALLS = {"front": ((-1, 0), (0, -1)), "back": ((1, 0), (0, 1)), "left": ((0, 1), (-1, 0)), "right": ((0, -1), (1, 0))}
RADIUS = 0.15        # CHARACTER_RADIUS in MELens_Cabin.lua
REACH = 0.45         # MELens.Parts.REACH
STAND_OFF = 0.17     # MELens_Interact.lua
PANEL_OFF = 0.25     # panelMenu: you stand this far into the room from the panel
PANEL_REACH = 0.60   # and it must be possible to stand within this of it


def blocks(text, token):
    """The text after `token` up to its closing brace, and the top-level `{ ... }` entries in it."""
    start = text.index(token) + len(token)
    depth, begin, entries, end = 1, None, [], start
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
            if depth == 2:
                begin = i
        elif c == "}":
            depth -= 1
            if depth == 1 and begin is not None:
                entries.append(text[begin:i + 1])
                begin = None
            if depth == 0:
                end = i
                break
    return text[start:end], entries


def num(text, name):
    m = re.search(r"\b" + name + r" = (-?[\d.]+)", text)
    return float(m.group(1)) if m else None


def load_kit():
    text = open(os.path.join(LUA, "MELens_RVKit.lua"), encoding="utf-8").read()
    kit = {}
    for m in re.finditer(r'(\w+) = \{ width = ([\d.]+), depth = ([\d.]+), height = ([\d.]+)', text):
        kit[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)))
    return kit


def load_profile(key):
    path = os.path.join(LUA, "MELens_Profile_%s.lua" % key)
    if not os.path.exists(path):
        path = os.path.join(LUA, "MELens_Profiles.lua")
    text = open(path, encoding="utf-8").read()
    _, entries = blocks(text, "spots = {")
    spots = []
    for e in entries:
        wall = re.search(r'wall = "(\w+)"', e).group(1)
        default = re.search(r'default = "(\w+)"', e).group(1)
        spots.append({"x": num(e, "x"), "z": num(e, "z"), "wall": wall, "default": default,
                      "length": num(e, "length"), "depth": num(e, "depth"), "rise": num(e, "rise") or 0.0,
                      "empty": re.search(r"\bempty = true", e) is not None})
    grid_key = re.search(r'walkGrid = "([^"]+)"', text).group(1)
    panel_text = re.search(r"panel = \{[^}]*\}", text).group(0)
    door_text = re.search(r"\n\s+door = \{[^}]*\}", text).group(0)
    profile = {"spots": spots, "grid_key": grid_key, "panel": (num(panel_text, "x"), num(panel_text, "z")),
               "door": (num(door_text, "x"), num(door_text, "z")), "blocked": []}
    if "blocked = {" in text:
        _, bl = blocks(text, "blocked = {")
        profile["blocked"] = [(num(b, "x1"), num(b, "x2"), num(b, "z1"), num(b, "z2")) for b in bl]
    profile["spots"] = [s for s in spots if not s["empty"]]      # bare spots hold nothing
    return profile


def load_grid(grid_key):
    for name in os.listdir(LUA):
        if name.startswith("MELens_WalkGrid_"):
            text = open(os.path.join(LUA, name), encoding="utf-8").read()
            if 'WalkGrids["%s"]' % grid_key in text:
                m = re.search(r"x0 = (-?[\d.]+), z0 = (-?[\d.]+), cell = ([\d.]+), cols = (\d+), rows = \{(.*?)\n    \}", text, re.S)
                rows = re.findall(r'"([01]+)"', m.group(5))
                return {"x0": float(m.group(1)), "z0": float(m.group(2)), "cell": float(m.group(3)),
                        "cols": int(m.group(4)), "rows": rows}
    raise SystemExit("no walk grid for " + grid_key)


def to_spot(spot, x, z):
    (ax, az), (ox, oz) = WALLS[spot["wall"]]
    dx, dz = x - spot["x"], z - spot["z"]
    return dx * ax + dz * az, dx * ox + dz * oz


def spot_point(spot, a, d):
    (ax, az), (ox, oz) = WALLS[spot["wall"]]
    return spot["x"] + ax * a + ox * d, spot["z"] + az * a + oz * d


def furnish(grid, spots, kit, blocked):
    """MELens_Cabin.lua furnishGrid: the open cells left with the pieces (and their radius) blocked."""
    open_cells = []
    for r, row in enumerate(grid["rows"]):
        z = grid["z0"] + (r + 0.5) * grid["cell"]
        line = []
        for c in range(grid["cols"]):
            is_open = row[c] == "1"
            if is_open:
                x = grid["x0"] + (c + 0.5) * grid["cell"]
                for spot in spots:
                    width, depth, _ = kit[spot["default"]]
                    a, d = to_spot(spot, x, z)
                    if abs(a) <= width / 2 + RADIUS and d <= depth + RADIUS:
                        is_open = False
                        break
                for x1, x2, z1, z2 in blocked:
                    if is_open and x1 - RADIUS <= x <= x2 + RADIUS and z1 - RADIUS <= z <= z2 + RADIUS:
                        is_open = False
            line.append(is_open)
        open_cells.append(line)
    return open_cells


def cell_of(grid, x, z):
    return int((x - grid["x0"]) // grid["cell"]), int((z - grid["z0"]) // grid["cell"])


def is_open(cells, grid, c, r):
    return 0 <= r < len(cells) and 0 <= c < grid["cols"] and cells[r][c]


def nearest_open(cells, grid, x, z):
    """MELens_Cabin.lua nearestWalkable: (c, r) and the distance moved."""
    c0, r0 = cell_of(grid, x, z)
    if is_open(cells, grid, c0, r0):
        return (c0, r0), 0.0
    for ring in range(1, 41):
        best = None
        for dr in range(-ring, ring + 1):
            for dc in range(-ring, ring + 1):
                if max(abs(dr), abs(dc)) == ring:
                    cx, cz = x + dc * grid["cell"], z + dr * grid["cell"]
                    c, r = cell_of(grid, cx, cz)
                    d = dr * dr + dc * dc
                    if (best is None or d < best[0]) and is_open(cells, grid, c, r):
                        best = (d, c, r)
        if best:
            return (best[1], best[2]), (best[0] ** 0.5) * grid["cell"]
    return None, None


def flood(cells, grid, start):
    seen = {start}
    queue = deque([start])
    while queue:
        c, r = queue.popleft()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nc, nr = c + dc, r + dr
            if (nc, nr) in seen or not is_open(cells, grid, nc, nr):
                continue
            if dc and dr and not (is_open(cells, grid, c + dc, r) and is_open(cells, grid, c, r + dr)):
                continue
            seen.add((nc, nr))
            queue.append((nc, nr))
    return seen


def distance_to(spot, kit_dims, x, z):
    width, depth, _ = kit_dims
    a, d = to_spot(spot, x, z)
    da = max(0.0, abs(a) - width / 2)
    dd = max(0.0, -d, d - depth)
    return (da * da + dd * dd) ** 0.5


kit = load_kit()
total = 0
for key in KEYS:
    profile = load_profile(key)
    grid = load_grid(profile["grid_key"])
    cells = furnish(grid, profile["spots"], kit, profile["blocked"])
    start, moved = nearest_open(cells, grid, *profile["door"])
    problems = []
    if start is None:
        problems.append("nothing open near the door")
        reach = set()
    else:
        reach = flood(cells, grid, start)
    open_count = sum(row.count(True) for row in cells)
    base_open = sum(row.count("1") for row in grid["rows"])

    def target(name, x, z, within=None, panel=None):
        """The stand point snapped to the nearest open floor (as M.walkTo does) must be reachable
        from the door and close enough to do what it is for."""
        cell, snap = nearest_open(cells, grid, x, z)
        cx = grid["x0"] + (cell[0] + 0.5) * grid["cell"] if cell else None
        cz = grid["z0"] + (cell[1] + 0.5) * grid["cell"] if cell else None
        if cell is None or cell not in reach:
            problems.append("%s: cannot be walked to (stand point x %+.2f z %+.2f)" % (name, x, z))
        elif within and distance_to(within[0], within[1], cx, cz) > REACH:
            problems.append("%s: the nearest place to stand (x %+.2f z %+.2f, %.2f from the stand point) is %.2f from it (reach is %.2f)" % (
                name, cx, cz, snap, distance_to(within[0], within[1], cx, cz), REACH))
        elif panel and ((cx - panel[0]) ** 2 + (cz - panel[1]) ** 2) ** 0.5 > PANEL_REACH:
            problems.append("%s: the nearest place to stand is %.2f from it (max %.2f)" % (
                name, ((cx - panel[0]) ** 2 + (cz - panel[1]) ** 2) ** 0.5, PANEL_REACH))

    for index, spot in enumerate(profile["spots"]):
        dims = kit[spot["default"]]
        # the middle of the front, like standPoint(spot, piece, 0), and the two ends of a long piece
        for a in {0.0, -dims[0] / 2 + 0.1, dims[0] / 2 - 0.1}:
            x, z = spot_point(spot, a, dims[1] + STAND_OFF)
            target("spot %d %s (%s) at %+.2f" % (index + 1, spot["default"], spot["wall"], a), x, z, (spot, dims))
    px, pz = profile["panel"]
    target("utility panel", px + PANEL_OFF, pz, panel=(px, pz))
    if SHOW_MAP:
        # front (high z) at the top, the vehicle's left (+x) on the left: # wall or piece, . open and
        # reachable, o open but cut off, S the door
        step = 2
        for r in range(len(cells) - 1, -1, -step):
            line = ""
            for c in range(grid["cols"] - 1, -1, -step):
                if start == (c, r):
                    line += "S"
                elif not is_open(cells, grid, c, r):
                    line += "#" if grid["rows"][r][c] == "1" else " "
                elif (c, r) in reach:
                    line += "."
                else:
                    line += "o"
            print("%6.2f %s" % (grid["z0"] + (r + 0.5) * grid["cell"], line))
        print("       x from %.2f (left) to %.2f (right)" % (grid["x0"] + grid["cols"] * grid["cell"], grid["x0"]))
    # margin: erode the open floor by 2 cells (0.05) and see whether the door still connects the rest
    def eroded(n):
        out = []
        for r in range(len(cells)):
            line = []
            for c in range(grid["cols"]):
                line.append(all(is_open(cells, grid, c + dc, r + dr) for dr in range(-n, n + 1) for dc in range(-n, n + 1)))
            out.append(line)
        return out
    margin_note = ""
    tight = eroded(2)
    tight_open = sum(row.count(True) for row in tight)
    s2, moved2 = nearest_open(tight, grid, *profile["door"])
    if s2 is None:
        margin_note = "  TIGHT: with a body 0.05 wider nothing near the door is open"
    else:
        tight_reach = flood(tight, grid, s2)
        lost = 1.0 - len(tight_reach) / max(1, tight_open)
        if lost > 0.05:
            margin_note = "  TIGHT: with a body 0.05 wider %d%% of the open floor is cut off from the door" % round(lost * 100)
    print("== %-14s open floor %5d cells (empty shell %5d), reachable %5d: %s" % (
        key, open_count, base_open, len(reach), "everything reachable" if not problems else "%d problems" % len(problems)) + margin_note)
    for p in problems:
        print("   " + p)
    total += len(problems)
print("REACHCHECK total problems: %d" % total)
sys.exit(1 if total else 0)
