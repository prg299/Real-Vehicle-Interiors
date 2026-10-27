"""Build tool: ME: LENS vehicle profiles and shell configs from short layout specs.

    python tools-src/vehicles/make_vehicles.py [spec ...]      (default: every spec)

A spec (tools-src/vehicles/specs/<key>.json) holds the design decisions for one vehicle
body: which KI5 vehicles use it, the way in, and the furniture spots (wall, where along
it, size, the default piece and the KI5 seats it lets you use). Everything else is
worked out from the measurements (tools-src/blender/measure_vehicle.py) and KI5's
script (dev/pzscripts.py), with the rules the Flying Cloud 22 was set up by:

  * a spot's back edge sits on the shell's wall (the measured inside outline, 0.03 in);
  * openings in the shell walls from the door objects (windows stay closed walls);
  * wheel-well boxes over the wheels that stand inside the floor;
  * the wall cut heights, lamps and utility panel relative to the floor;
  * where you stand inside the door, the exit marker, and where you step out;
  * how you lie on a bed and sit on a bench (the bone measurements of damnlib's
    "lying" and "facingLeft" poses, see MELens_Profiles.lua).

Writes:
  mod/RealVehicleInteriors/common/media/lua/shared/MELens_Profile_<key>.lua     the profile(s)
  tools-src/blender/cfg/shell_<key>.json                            rv_kit.py's shell config
  and lists the shell models for mod/RealVehicleInteriors/common/media/scripts/MELens_models.txt.
Coordinates: passenger space in tiles, x to the vehicle's left, y up, z to the front."""
import json
import math
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SPECS = os.path.join(ROOT, "tools-src", "vehicles", "specs")
FLOORPLANS = os.path.join(ROOT, "build", "rv", "floorplans")
MEDIA = os.path.join(ROOT, "mod", "RealVehicleInteriors", "common", "media")
LUA = os.path.join(MEDIA, "lua", "shared")
CFG = os.path.join(ROOT, "tools-src", "blender", "cfg")

INSET = 0.03            # the shell's walls stand this far inside KI5's body
MESH_SCALE = 0.09       # KI5 bodies: model scale 0.1 x vehicle scale 0.9
LIFT = 0.666            # KI5's object translation the game leaves out (raw units)
CUT_HEIGHTS = (0.605, 0.83, 1.055)   # Low / Medium / High walls, above the floor
NEAR_CUT = 0.38         # walls facing the camera, above the floor
LAMP_HEIGHT = 0.64
PANEL = (0.24, 0.35)    # the utility panel's bottom and top above the floor
WELL_TOP = 0.24         # wheel-well boxes: top above the floor, inner side from the wheel
WELL_HALF = 0.34
STAND_IN = 0.19         # where you stand, inside the door
WALK_RADIUS = 0.15      # how close the middle of the character may come to a wall (the body is ~0.2 wide)

# Furniture geometry (tools-src/blender/rv_kit.py), used for the seat placements.
BED_MATTRESS_TOP = 0.30     # above the floor
BED_MID_DEPTH = 0.272       # the mattress's middle, from the wall
DINETTE_BACKREST = 0.46     # a bench's backrest face, along the piece from its middle
BENCH_SEAT_DEPTH = 0.27     # the middle of a bench's seat, from the wall

# Poses (MELens_Profiles.lua): lying, the root 0.064 from the body's middle towards
# the head, 0.02 into the mattress; sitting upright ("facingLeft"), the root 0.12 in
# front of the backrest and 0.395 above the floor for a 0.31 high seat.
LIE_SHIFT = 0.064
LIE_SINK = 0.02
SIT_FORWARD = 0.12
SIT_ABOVE_SEAT = 0.085

STYLES = {
    # the shell's look per kind of vehicle (rv_kit.py wall_texture / floor_texture): the painted textures
    # (tools-src/art/generate.ps1) graded to muted colours like the game's own rooms, panel joints on the
    # walls, a floor clearly darker than the walls, and in a box truck grey steel walls against a dark floor
    # and the brown cardboard (the colours are sRGB, before the game's light)
    "camper": {"flat": False, "floorArt": "floor_planks", "floorTile": 0.9, "floorTint": [0.38, 0.27, 0.19],
               "wallArt": "wall_paint", "wallTile": 0.8, "wallTint": [0.80, 0.76, 0.66], "panelWidth": 0.6,
               "baseboard": 0.07, "baseboardArt": "wood_dark", "baseboardColour": [0.30, 0.20, 0.13],
               "wallSize": [2048, 256], "floorSize": [512, 1024]},
    "bus": {"flat": False, "floorArt": "rubberfloor", "floorTile": 1.0, "floorTint": [0.20, 0.20, 0.21],
            "wallArt": "wall_paint", "wallTile": 0.8, "wallTint": [0.78, 0.76, 0.70], "panelWidth": 0.75,
            "baseboard": 0.05, "baseboardArt": "darkmetal", "baseboardColour": [0.22, 0.22, 0.23],
            "wallSize": [2048, 256], "floorSize": [512, 2048]},
    "cargo": {"flat": False, "floorArt": "diamondplate", "floorTile": 0.55, "floorTint": [0.34, 0.36, 0.38],
              "wallArt": "steel", "wallTile": 1.0, "wallTint": [0.55, 0.57, 0.59], "panelWidth": 0.5,
              "baseboard": 0.0, "wallSize": [2048, 256], "floorSize": [512, 2048]},
}

WALLS = {
    # along: the direction of a piece's length; out: from the wall into the room
    "front": {"along": (-1, 0), "out": (0, -1)},
    "back": {"along": (1, 0), "out": (0, 1)},
    "left": {"along": (0, 1), "out": (-1, 0)},
    "right": {"along": (0, -1), "out": (1, 0)},
}
HEAD = {"front": (0, 1), "back": (0, -1), "left": (1, 0), "right": (-1, 0)}


def load(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def crossings(ring, axis, value):
    """Where the closed outline crosses the line x = value (axis 0) or z = value (axis 1):
    the other coordinate of each crossing."""
    out = []
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        if (a[axis] - value) * (b[axis] - value) <= 0 and a[axis] != b[axis]:
            t = (value - a[axis]) / (b[axis] - a[axis])
            out.append(a[1 - axis] + (b[1 - axis] - a[1 - axis]) * t)
    return out


def outline_at(measure, height):
    key = min(measure["outlines"], key=lambda k: abs(float(k) - height))
    return measure["outlines"][key]


def wall_line(ring, wall, lo, hi):
    """The wall's inside line over [lo, hi] along it: the tightest crossing, INSET in."""
    samples = [lo + (hi - lo) * i / 12 for i in range(13)]
    if wall in ("left", "right"):
        values = []
        for z in samples:
            xs = crossings(ring, 1, z)
            if xs:
                values.append(max(xs) if wall == "left" else min(xs))
        if not values:
            raise ValueError("no %s wall between z %.2f and %.2f" % (wall, lo, hi))
        return (min(values) - INSET) if wall == "left" else (max(values) + INSET)
    values = []
    for x in samples:
        zs = crossings(ring, 0, x)
        if zs:
            values.append(max(zs) if wall == "front" else min(zs))
    if not values:
        raise ValueError("no %s wall between x %.2f and %.2f" % (wall, lo, hi))
    return (min(values) - INSET) if wall == "front" else (max(values) + INSET)


def r(v, n=3):
    return round(v + 0.0, n)


def lua(value, indent=0):
    """A Lua literal for a JSON-like value (lists of numbers stay on one line)."""
    pad = "    " * indent
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and abs(value - round(value, 4)) < 1e-9:
            return ("%.4f" % value).rstrip("0").rstrip(".") if value != int(value) else str(int(value))
        return str(value)
    if isinstance(value, str):
        if value.startswith("@"):
            return value[1:]         # a Lua expression, e.g. @math.pi / 2
        return '"%s"' % value
    if isinstance(value, list):
        if all(isinstance(v, (int, float, str)) for v in value):
            return "{ " + ", ".join(lua(v) for v in value) + " }"
        return "{\n" + "".join(pad + "    " + lua(v, indent + 1) + ",\n" for v in value) + pad + "}"
    if isinstance(value, dict):
        simple = all(isinstance(v, (int, float, str, bool)) for v in value.values()) and len(value) <= 8
        items = []
        for k, v in value.items():
            key = k if k.isidentifier() else '["%s"]' % k
            items.append("%s = %s" % (key, lua(v, indent + 1)))
        if simple:
            return "{ " + ", ".join(items) + " }"
        return "{\n" + "".join(pad + "    " + item + ",\n" for item in items) + pad + "}"
    raise TypeError(value)


def turn_literal(angle):
    for num, text in ((0, "0"), (math.pi, "@math.pi"), (-math.pi, "@-math.pi"), (math.pi / 2, "@math.pi / 2"), (-math.pi / 2, "@-math.pi / 2")):
        if abs(angle - num) < 1e-6:
            return text if text != "0" else 0
    return r(angle, 4)


def box_measure(measure, box, floor, ceiling, path):
    """A measurement with a rectangular inside outline (x within +-box["x"], z within
    box["z"]) at every height, for a body whose sliced outline runs into another room
    (a box truck's cab). Parts are kept."""
    hx, (z0, z1) = box["x"], box["z"]
    ring = []
    for i in range(20):
        ring.append([r(-hx + 2 * hx * i / 20), z0])
    for i in range(40):
        ring.append([hx, r(z0 + (z1 - z0) * i / 40)])
    for i in range(20):
        ring.append([r(hx - 2 * hx * i / 20), z1])
    for i in range(40):
        ring.append([-hx, r(z1 - (z1 - z0) * i / 40)])
    out = dict(measure)
    out["outlines"] = {}
    h = floor - 0.1
    while h <= ceiling + 0.05:
        out["outlines"]["%.2f" % h] = ring
        h = round(h + 0.1, 4)
    out["floor"], out["ceiling"] = floor, ceiling
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=1)
    return out


def footprint(spot):
    """A spot's rectangle on the floor: (x0, x1, z0, z1)."""
    w = WALLS[spot["wall"]]
    pts = []
    for a in (-spot["length"] / 2, spot["length"] / 2):
        for d in (0.0, spot["depth"]):
            pts.append((spot["x"] + w["along"][0] * a + w["out"][0] * d, spot["z"] + w["along"][1] * a + w["out"][1] * d))
    return (min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))


def overlap(a, b, tolerance=0.01):
    return a[0] < b[1] - tolerance and b[0] < a[1] - tolerance and a[2] < b[3] - tolerance and b[2] < a[3] - tolerance


# --- the furniture kit's sizes (rv_kit.py writes MELens_RVKit.lua) -------------------------
KIT_FALLBACK = {"box": {"width": 0.5, "depth": 0.5, "height": 0.4}}


def load_kit():
    kit = dict(KIT_FALLBACK)
    path = os.path.join(LUA, "MELens_RVKit.lua")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                m = re.match(r"\s*(\w+) = \{ width = ([\d.]+), depth = ([\d.]+), height = ([\d.]+),", line)
                if m:
                    kit[m.group(1)] = {"width": float(m.group(2)), "depth": float(m.group(3)), "height": float(m.group(4))}
    return kit


# --- fitting a spot inside the walls --------------------------------------------------------
def in_polygon(pt, poly):
    x, z = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, z0 = poly[i]
        x1, z1 = poly[(i + 1) % n]
        if (z0 > z) != (z1 > z) and x < x0 + (x1 - x0) * (z - z0) / (z1 - z0):
            inside = not inside
    return inside


def distance_to_polygon(pt, poly):
    best = 1e9
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]
        bx, bz = poly[(i + 1) % n]
        dx, dz = bx - ax, bz - az
        length2 = dx * dx + dz * dz
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - az) * dz) / length2))
        best = min(best, math.hypot(pt[0] - (ax + dx * t), pt[1] - (az + dz * t)))
    return best


def clear_of_walls(pt, constraints):
    """Whether a point is inside every outline (the inside of the body or the lining at a height) by at
    least that outline's margin: `constraints` are (outline, margin) pairs; a negative margin lets the
    point stand that far outside."""
    for poly, margin in constraints:
        distance = distance_to_polygon(pt, poly)
        if (distance if in_polygon(pt, poly) else -distance) < margin:
            return False
    return True


def spot_points(spot, length, samples=0.08):
    """Points round a spot's rectangle: `length` along the wall, `depth` out from it."""
    w = WALLS[spot["wall"]]
    pts = []
    count = max(2, int(length / samples) + 1)
    for i in range(count + 1):
        a = -length / 2 + length * i / count
        for d in (0.0, spot["depth"] / 2, spot["depth"]):
            pts.append((spot["x"] + w["along"][0] * a + w["out"][0] * d, spot["z"] + w["along"][1] * a + w["out"][1] * d))
    for d in (spot["depth"] * k / 4 for k in range(5)):
        for a in (-length / 2, length / 2):
            pts.append((spot["x"] + w["along"][0] * a + w["out"][0] * d, spot["z"] + w["along"][1] * a + w["out"][1] * d))
    return pts


PROBLEMS = []          # layouts that would clip the walls: the build fails on any
FURNITURE_TOP = 1.0    # above the tallest piece of the kit (the kitchen, 0.99)


def fit_spot(spot, measure, floor, height, min_length=0.3):
    """Moves a spot inward, and narrows it if it must (never below `min_length`, the width
    of the piece it is for), until its whole room stands clear of the walls at every height
    up to `height` above the floor. Campers curve in towards the top and round their noses,
    so a piece placed against the wall at floor height reaches through it higher up.
    Returns a note about what changed, or None."""
    heights = [floor + 0.06] + [floor + 0.1 * k for k in range(1, int(height / 0.1) + 1)] + [floor + height]
    constraints = [(outline_at(measure, h), INSET - 0.006) for h in heights]
    w = WALLS[spot["wall"]]
    original = (spot["x"], spot["z"], spot["length"])
    length = spot["length"]
    for shrink in range(0, 40):
        trial = dict(spot)
        moved = 0.0
        while moved <= 0.45:
            trial["x"] = spot["x"] + w["out"][0] * moved
            trial["z"] = spot["z"] + w["out"][1] * moved
            if all(clear_of_walls(p, constraints) for p in spot_points(trial, length)):
                spot["x"], spot["z"], spot["length"] = r(trial["x"]), r(trial["z"]), r(length)
                changed = []
                if moved > 0.004:
                    changed.append("moved in %.2f" % moved)
                if length < original[2] - 0.004:
                    changed.append("length %.2f -> %.2f" % (original[2], length))
                return ", ".join(changed) or None
            moved += 0.01
        length -= 0.04
        if length < min_length - 0.001:
            break
    return "DOES NOT FIT (room %.2f long, needs %.2f)" % (original[2], min_length)


def expand_spots(entries, kit):
    """Spec spots to flat spots: `repeat` (count columns `step` apart along the wall) and
    `levels` (boxes stacked on each other, each its own spot, `rise` above the floor). `heights` (one
    number per column, repeated if there are fewer) is how many boxes stand in each column to begin
    with: the stack's other places start bare, so stacks differ in height and any of them can still be
    built up to `levels` by hand. `appendLevelsAbove` (a level number): the places of the levels above it
    are listed after all the others, so the spot numbers of an older layout with fewer levels stay what they
    were (a saved vehicle keeps its boxes where they stand: its parts are numbered by their place here).
    `appendAtEnd` (true): the entry's places come after everything else, appended levels included, for the same
    reason (spots added to a released layout)."""
    out = []
    appended = []
    at_end = []
    for s in entries:
        rep = s.get("repeat") or {"count": 1, "step": 0.0}
        heights = s.get("heights")
        for i in range(rep["count"]):
            for level in range(1, s.get("levels", 1) + 1):
                e = {k: v for k, v in s.items() if k not in ("repeat", "levels", "heights", "appendLevelsAbove", "appendAtEnd")}
                e["at"] = round(s["at"] + i * rep["step"], 4)
                if s.get("levels", 1) > 1 or s.get("cargo"):
                    height = kit.get(s.get("default"), {"height": 0.4})["height"]
                    e["level"] = level
                    e["rise"] = round((level - 1) * height, 4)
                if heights and level > heights[i % len(heights)]:
                    e["empty"] = True
                if s.get("appendAtEnd"):
                    at_end.append(e)
                else:
                    (appended if level > s.get("appendLevelsAbove", 1 << 30) else out).append(e)
    return out + appended + at_end


def remove_generated(spec):
    """A disabled vehicle: none of its generated files stay behind."""
    key = spec["key"]
    tex = spec.get("texture")
    paths = [os.path.join(LUA, "MELens_Profile_%s.lua" % key),
             os.path.join(CFG, "shell_%s.json" % key),
             os.path.join(LUA, "MELens_WalkGrid_%s_Shell.lua" % key),
             os.path.join(FLOORPLANS, "measure_%s_box.json" % key)]
    if tex:
        paths += [os.path.join(MEDIA, "textures", "Vehicles", "MELensShell_%s_%s.png" % (tex, part)) for part in ("floor", "walls")]
    for path in paths:
        if os.path.exists(path):
            os.remove(path)
            print("  removed", os.path.relpath(path, ROOT))


def measured_corner_returns(measure, regions, shell_cfg):
    """Native corner spines omitted by nearest-angle outline sampling.

    Regions identify actual body corners, not dimensions of a replacement slab.
    Each section must contain both incident skins at its extremal corner. Keep
    the existing lining untouched; rv_kit joins that lining to these spines.
    """
    sections = measure.get("sections")
    assert sections, "corner returns need exact native body sections"
    result = []
    for region in regions:
        side, end = region["side"], region["end"]
        assert side in (-1, 1) and end in (-1, 1)
        rows = []
        for height, segments in sorted(sections.items(), key=lambda pair: float(pair[0])):
            height = float(height)
            if not shell_cfg["lowestOutline"] <= height <= shell_cfg["top"]:
                continue
            if rows and height - rows[-1][0] < 1e-6:
                continue
            points = [p for segment in segments for p in segment
                      if region["x"][0] <= p[0] <= region["x"][1]
                      and region["z"][0] <= p[1] <= region["z"][1]]
            if not points:
                continue
            candidates = []
            for point in points:
                incident = []
                for a, b in segments:
                    if math.dist(a, point) < 1e-5 and math.dist(a, b) > 1e-5:
                        incident.append((b[0] - a[0], b[1] - a[1]))
                    elif math.dist(b, point) < 1e-5 and math.dist(a, b) > 1e-5:
                        incident.append((a[0] - b[0], a[1] - b[1]))
                # Reject a lone trim spike or a disconnected extremum. Both
                # actual native skins must meet, and head into this corner.
                if (any(side * dx < -1e-5 and abs(dz) < 1e-5 for dx, dz in incident)
                        and any(end * dz < -1e-5 and abs(dx) < 1e-5 for dx, dz in incident)):
                    candidates.append(point)
            assert candidates, (height, region, "no connected corner skins")
            corner = max(candidates, key=lambda p: (end * p[1], side * p[0]))
            row = [height, corner[0], corner[1]]
            if rows and height - rows[-1][0] < 1e-6:
                assert math.dist(row[1:], rows[-1][1:]) < 1e-5
                continue
            # Preserve native bends while dropping collinear triangulation
            # and window-detail heights; the lining supplies its own rows.
            while len(rows) > 1:
                a, b = rows[-2:]
                t = (b[0] - a[0]) / (height - a[0])
                if math.dist(b[1:], [a[i] + (row[i] - a[i]) * t for i in (1, 2)]) >= 1e-5:
                    break
                rows.pop()
            rows.append(row)
        assert len(rows) >= 2, (region, "no connected native corner")
        assert rows[0][0] < shell_cfg["floorY"] + NEAR_CUT
        assert rows[-1][0] > shell_cfg["floorY"] + max(CUT_HEIGHTS)
        result.append({"side": side, "end": end, "skin": .003,
                       "section": [[r(v, 9) for v in row] for row in rows]})
    return result


def measured_cowl_return(measure, request, lining, skin=.002):
    """Trace the one connected native cowl skin ahead of the existing room."""
    height, rear = request["height"], request["rear"]
    sections = measure.get("sections", {})
    key = min(sections, key=lambda k: abs(float(k) - height))
    assert abs(float(key) - height) < 1e-9, "cowl needs its exact native section plane"
    lo, hi = request["x"]
    nodes, graph = {}, {}
    for a, b in sections[key]:
        if not all(lo <= p[0] <= hi and p[1] >= rear for p in (a, b)):
            continue
        ka, kb = tuple(round(v, 6) for v in a), tuple(round(v, 6) for v in b)
        if ka == kb:
            continue
        nodes.setdefault(ka, a); nodes.setdefault(kb, b)
        graph.setdefault(ka, set()).add(kb); graph.setdefault(kb, set()).add(ka)
    components, unseen = [], set(graph)
    while unseen:
        component, todo = set(), [next(iter(unseen))]
        while todo:
            point = todo.pop()
            if point in component:
                continue
            component.add(point); unseen.discard(point)
            todo.extend(graph[point] - component)
        if min(p[0] for p in component) < 0 < max(p[0] for p in component):
            components.append(component)
    assert len(components) == 1, "cowl region must contain one connected skin across the cab"
    component = components[0]
    ends = [p for p in component if len(graph[p]) == 1]
    assert len(ends) == 2 and all(len(graph[p]) <= 2 for p in component), "cowl skin must be an unbranched contour"
    current, finish = sorted(ends)
    chain, previous = [], None
    while True:
        point = nodes[current]
        while len(chain) > 1:
            a, b = chain[-2:]
            area = abs((b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]))
            if area / max(math.dist(a, point), 1e-8) >= 1e-5:
                break
            chain.pop()
        chain.append(point)
        if current == finish:
            break
        following = next(p for p in graph[current] if p != previous)
        previous, current = current, following
    front = [p for p in lining if abs(p[1] - rear) < 1e-6]
    assert len(front) >= 2, "cowl must join the unchanged room front"
    left, right = min(p[0] for p in front), max(p[0] for p in front)
    assert chain[0][0] < left + .01 and chain[-1][0] > right - .01
    # A 3mm underlap behind the lining closes the shared edge without a
    # coincident face. Every other boundary comes from the native section.
    polygon = [[left, rear - .003]] + chain + [[right, rear - .003]]
    # Move the thin perimeter skin off the native vertical faces. The rear
    # edge retains a 1mm underlap; neither surface is coplanar with the hull.
    import shell_rings
    polygon = shell_rings.inset_ring(polygon, skin)
    return {"height": height, "thickness": request.get("thickness", .006),
            "polygon": [[r(v, 9) for v in point] for point in polygon]}


def apply_native_floor(spec):
    """Complete measured planar or bilateral curves enter the reciprocal mask."""
    perimeter = load(os.path.join(ROOT, "tools-src", "vehicles", "native-floor-perimeters.json"))["families"].get(spec["key"])
    if perimeter:
        spec["nativeFloorPerimeter"] = {key: perimeter[key] for key in ("margins", "polygons") if perimeter.get(key)}
    returns = load(os.path.join(ROOT, "tools-src", "vehicles", "native-floor-returns.json"))["families"].get(spec["key"])
    if returns:
        spec["nativeFloorReturns"] = returns
    measured = load(os.path.join(ROOT, "tools-src", "vehicles", "native-wheel-floors.json"))["families"].get(spec["key"])
    if measured:
        assert spec.get("nativeBodyWalls") and spec.get("separateShellSupports")
        if measured.get("stockTrim"):
            assert spec.get("nativePlainFinish"),"stock wheel-well replacement is vanilla-only"
            spec["nativeWheelWellTrim"] = measured["stockTrim"]
        if measured.get("sides"):
            assert len(measured["sides"]) == 2
            spec["flatWheelFloor"] = True
            seals = dict(spec.get("nativeSupportSeals", {}))
            seals["archSides"] = measured["sides"]
            seals["archWall"] = measured.get("archWall",True)
            if measured.get("fullMeasuredFloorChain"):
                seals["fullMeasuredFloorChain"] = True
            if measured.get("reuseSupportAsCovers"):seals["reuseSupportAsCovers"] = True
            seals.setdefault("overlap", .002)
            seals.setdefault("archOnly", True)
            spec["nativeSupportSeals"] = seals
            return
        contour = measured["archContour"]
        assert 2 <= len(contour) <= 16 and all(a[0] < b[0] for a,b in zip(contour,contour[1:]))
        spec["flatWheelFloor"] = True
        # The shared survey owns the qualified arch. A family can add measured
        # perimeter/threshold seals without silently losing them on generation.
        seals = dict(spec.get("nativeSupportSeals", {}))
        for key, value in (("archSideX", measured["archSideX"]), ("archContour", contour)):
            assert key not in seals or seals[key] == value, (spec["key"], "conflicting measured arch", key)
            seals[key] = value
        if measured.get("floorMargins"):seals["floorMargins"] = measured["floorMargins"]
        seals.setdefault("overlap", .003)
        seals.setdefault("archOnly", "rearPlane" not in seals)
        spec["nativeSupportSeals"] = seals


def native_window_returns(key):
    path = os.path.join(ROOT, "tools-src", "vehicles", "native-window-returns.json")
    return load(path)["families"].get(key, {}).get("panes", []) if os.path.exists(path) else []


def native_living_leaves(key):
    path=os.path.join(ROOT,"tools-src","vehicles","native-living-leaves.json")
    return load(path)["families"].get(key,{}).get("models",[]) if os.path.exists(path) else []


def native_stock_metal(spec):
    """Existing stock pixels for five vanilla bodies; no generated art or geometry."""
    assert spec.get("nativeBodyWalls") and spec.get("nativePlainFinish") and spec.get("nativeWallMaterial"), "stock metal needs the measured plain-material classifier"
    contract = load(os.path.join(ROOT, "tools-src", "vehicles", "native-stock-metal.json"))
    assert contract["schemaVersion"] == 1
    assert set(contract["families"]) == {"VanillaVan", "VanillaPassengerVan", "VanillaAmbulance", "VanillaRadioVan", "VanillaStepVan"}, "stock metal scope changed"
    entry = contract["families"][spec["key"]]
    texture, paint, panel = contract["texture"], entry["paintUV"], contract["panelUV"]
    assert re.fullmatch(r"vehicle_[a-z0-9_]+", texture), "stock panel must reference an existing game texture basename"
    assert len(paint) == 2 and len(panel) == 4
    assert all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in paint + panel)
    assert panel[0] < panel[2] and panel[1] < panel[3]
    width, height = contract["panelWidth"], contract["panelHeight"]
    assert all(isinstance(v, (int, float)) and math.isfinite(v) and .05 <= v <= 10 for v in (width, height))
    return dict(texture=texture, paintUV=paint, panelUV=panel, panelWidth=width, panelHeight=height)


def native_wall_finish(spec, measure, shell_cfg, hull_measure):
    """One physical material scale for the native hull and its authored fittings."""
    if not spec.get("nativeWallMaterial"):
        return None
    import shell_rings
    floor_measure = load(shell_cfg["floorOutline"]["measure"]) if shell_cfg.get("floorOutline", {}).get("measure") else None
    lining = shell_rings.build(measure, shell_cfg, floor_measure)
    ring = lining["rings"][0][1]
    perimeter = sum(math.hypot(a[0]-b[0], a[1]-b[1]) for a,b in zip(ring, ring[1:]+ring[:1]))
    height = shell_cfg["top"]-shell_cfg["floorY"]
    if spec.get("nativePlainFinish") and shell_cfg.get("cabBulkhead"):
        cap = shell_cfg["cabBulkhead"]
        height = max([cap["top"]]+[y for segment in cap.get("section", []) for x,y in segment])-shell_cfg["floorY"]
    room = lining["room_ring"]
    return dict(texture="MELensShell_%s_walls" % spec["nativeWallMaterial"],
                height=round(height,6), perimeter=round(perimeter,6),
                origin=[min(x for x,z in room),min(z for x,z in room)],
                bodyBounds=hull_measure["body"], continuous=bool(spec.get("nativePlainFinish")))


def separate_door_returns(spec):
    """Register a separate return only when its builder has actual faces.

    Plain curved camper openings and arch-only additions create no reveals.
    Their empty FBX objects are not loadable game meshes. Threshold jambs and
    measured rear closures are the two producers in rv_kit.build_shell.
    """
    requested = spec.get("separateDoorReturns") or spec.get("nativeSupportSeals")
    return bool(requested and (spec.get("rearClosure") or spec.get("entryOpening")
                or any(lining.get("threshold") for lining in spec.get("doorLinings", []))))


def build(spec_path):
    spec = load(spec_path)
    apply_native_floor(spec)
    key = spec["key"]
    # One owner for source-qualified decorative/fixture cuts. This also keeps
    # direct profile regeneration consistent with the expansion generator.
    cuts=load(os.path.join(ROOT,"tools-src","vehicles","native-interior-cuts.json"))["families"].get(key)
    if cuts:spec["nativeSurfaceCuts"]=cuts["cuts"]
    near_faces=load(os.path.join(ROOT,"tools-src","vehicles","native-near-faces.json"))["families"].get(key)
    if near_faces and near_faces.get("faces"):spec["nativeNearFaces"]=near_faces["faces"]
    if spec.get("disabled"):
        remove_generated(spec)
        print("SKIPPED %-12s %s" % (key, spec["disabled"]))
        return None
    kit = load_kit()
    measure = load(os.path.join(FLOORPLANS, spec["measure"]))
    hull_measure = measure
    scripts = load(os.path.join(FLOORPLANS, spec["scripts"][0]))
    info = scripts[spec["scripts"][1]]
    scale = info["model"]["scale"]
    mesh = spec.get("mesh", {"scale": MESH_SCALE, "lift": LIFT})
    floor = spec.get("floorY", measure["floor"])
    ceiling = spec.get("ceiling", measure["ceiling"])
    measure_file = spec["measure"]
    if spec.get("box"):
        measure_file = "measure_%s_box.json" % key
        measure = box_measure(measure, spec["box"], floor, ceiling, os.path.join(FLOORPLANS, measure_file))
    ring = outline_at(measure, floor + 0.25)
    parts = measure["parts"]
    seats = {p["id"]: p for p in info["passengers"]}

    def part(name):
        return parts[name]

    # --- furniture spots: the back edge on the wall, the whole room clear of it ----------
    spots = []
    for s in expand_spots(spec["spots"], kit):
        wall = s["wall"]
        half = s["length"] / 2
        if wall in ("left", "right"):
            lo, hi = s["at"] - half, s["at"] + half
            x = wall_line(ring, wall, lo, hi)
            spot = {"x": r(x), "z": r(s["at"])}
        else:
            lo, hi = s["at"] - half, s["at"] + half
            z = wall_line(ring, wall, lo, hi)
            spot = {"x": r(s["at"]), "z": r(z)}
        spot.update({"wall": wall, "length": s["length"], "depth": s["depth"]})
        if s.get("default"):
            spot["default"] = s["default"]   # (a spot without one starts bare and takes any piece that fits)
        if s.get("seats"):
            spot["seats"] = s["seats"]
        if s.get("head"):
            spot["head"] = s["head"]         # which way a bed's head lies (front / back / left / right)
        if s.get("empty"):
            spot["empty"] = True             # sized for its default piece, but starts bare
        if s.get("cargo"):
            spot["cargo"] = True             # boxes only, and boxes only here
        if s.get("rise") is not None:
            spot["rise"] = s["rise"]
        if s.get("level"):
            spot["level"], spot["rise"] = s["level"], s["rise"]
        # tall furniture (any piece can be swapped in: up to FURNITURE_TOP) must not reach through the
        # curving walls: fit the room
        # to the walls over the height of what can stand here
        piece_height = kit.get(s.get("default"), {"height": 0.9})["height"]
        top = (s.get("rise", 0.0) + piece_height) if s.get("cargo") else max(FURNITURE_TOP, piece_height)
        note = fit_spot(spot, measure, floor, top, kit.get(s.get("default"), {"width": 0.3})["width"])
        if s.get("push"):
            # a piece's bottom corners at a rounded end can reach past the hull's skin where it tucks in under
            # the floor (dev/piece_overhang.py says so): this much further in, after the fit
            w = WALLS[wall]
            spot["x"] = r(spot["x"] + w["out"][0] * s["push"])
            spot["z"] = r(spot["z"] + w["out"][1] * s["push"])
        if note and note.startswith("DOES NOT FIT"):
            if s.get("cargo"):
                # a box that cannot stand there (the rounded corners of a body): no box there
                print("  dropped %-6s box at %6.2f (level %d): %s" % (wall, s["at"], s.get("level", 1), note))
                continue
            PROBLEMS.append("%s: the %s spot at %.2f (%s): %s" % (key, wall, s["at"], s.get("default"), note))
        if note:
            print("  fit %-6s at %6.2f: %s" % (wall, s["at"], note))
        spots.append((spot, s))

    def point(spot, a, d):
        w = WALLS[spot["wall"]]
        return (spot["x"] + w["along"][0] * a + w["out"][0] * d, spot["z"] + w["along"][1] * a + w["out"][1] * d)

    # --- where you lie and sit ----------------------------------------------------------
    placement = {}
    for spot, s in spots:
        piece = s.get("default")
        ids = s.get("seats") or []
        if not ids:
            continue
        kind = s.get("use", piece)
        if kind == "bed":
            head = HEAD[s.get("head", "front")]
            cx, cz = point(spot, 0.0, BED_MID_DEPTH)
            turn = math.atan2(-head[0], head[1])
            placement[ids[0]] = {"pose": "lying", "x": r(cx + LIE_SHIFT * head[0]), "y": r(floor + BED_MATTRESS_TOP - LIE_SINK),
                                 "z": r(cz + LIE_SHIFT * head[1]), "turn": turn_literal(turn)}
        elif kind == "dinette":
            w = WALLS[spot["wall"]]
            for sign, sid in zip((1, -1), ids):
                a = sign * (DINETTE_BACKREST - SIT_FORWARD)
                x, z = point(spot, a, BENCH_SEAT_DEPTH)
                face = (-sign * w["along"][0], -sign * w["along"][1])
                placement[sid] = {"pose": "facingLeft", "x": r(x), "y": r(floor + 0.31 + SIT_ABOVE_SEAT), "z": r(z),
                                  "turn": turn_literal(math.atan2(face[1], face[0]))}
        elif kind in ("busseat", "busseat2"):
            # benches facing the front (+z), one per 0.75 along the spot, each with its
            # 0.10 thick backrest at its rear end and a seat 0.33 high
            benches = 1 if kind == "busseat" else 2
            for i, sid in enumerate(ids[:benches]):
                middle = (i - (benches - 1) / 2) * 0.75
                x, z = point(spot, middle, s.get("seatDepth", 0.40))
                back = z - 0.75 / 2 + 0.10
                placement[sid] = {"pose": "facingLeft", "x": r(x), "y": r(floor + 0.33 + SIT_ABOVE_SEAT),
                                  "z": r(back + SIT_FORWARD), "turn": "@math.pi / 2"}

    # --- the way in ---------------------------------------------------------------------
    entry = spec["entry"]
    if entry.get("object"):
        door_part = part(entry["object"])
        lo, hi = door_part["min"], door_part["max"]
    else:
        # a door KI5 models elsewhere: its span along the wall
        s0, s1 = entry["span"]
        lo, hi = [s0, floor, s0], [s1, floor + 1.3, s1]
    if entry["wall"] in ("left", "right"):
        dz = (lo[2] + hi[2]) / 2
        wx = wall_line(ring, entry["wall"], lo[2], hi[2])
        inward = -1 if entry["wall"] == "left" else 1
        stand = (wx + inward * STAND_IN, dz)
        marker = {"x": r(wx + inward * 0.235), "z": r(dz), "halfX": 0.30, "halfZ": r((hi[2] - lo[2]) / 2 + 0.05),
                  "outward": [-inward, 0]}
        panel_z = (lo[2] - 0.12, lo[2] - 0.05) if entry.get("panel", "behind") == "behind" else (hi[2] + 0.05, hi[2] + 0.12)
        # on the wall where the panel is (not where the door is: the walls curve)
        panel = {"x": r(wall_line(ring, entry["wall"], panel_z[0], panel_z[1])),
                 "y": [r(floor + PANEL[0]), r(floor + PANEL[1])], "z": [r(panel_z[0]), r(panel_z[1])]}
        panel_wall = entry["wall"]
    else:
        dx = (lo[0] + hi[0]) / 2
        wz = wall_line(ring, entry["wall"], lo[0], hi[0])
        inward = -1 if entry["wall"] == "front" else 1
        stand = (dx, wz + inward * STAND_IN)
        marker = {"x": r(dx), "z": r(wz + inward * 0.2), "halfX": r(min(0.45, (hi[0] - lo[0]) / 2)), "halfZ": 0.22,
                  "outward": [0, -inward]}
        # the panel on the side wall next to the door
        side = entry.get("panelWall", "right")
        pz = wz + inward * 0.18
        px = wall_line(ring, side, pz - 0.1, pz + 0.1)
        panel = {"x": r(px), "y": [r(floor + PANEL[0]), r(floor + PANEL[1])], "z": [r(pz - 0.07), r(pz + 0.07)]}
        panel_wall = side
    outside = entry.get("outside")
    if not outside:
        ki5 = seats.get(entry.get("outsideFrom", ""))
        if ki5 and ki5.get("outside"):
            outside = [v * scale for v in ki5["outside"]["offset"]]
        else:
            ground = -(info["model"]["offset"][1] * scale + 0.26)
            if entry["wall"] in ("front", "back"):
                outside = [stand[0], ground, stand[1] - inward * 0.9]
            else:
                outside = [stand[0] - inward * 0.75, ground, stand[1]]

    # --- the shell ----------------------------------------------------------------------
    openings = []
    window_boxes = []
    jamb_boxes = []
    for name in spec.get("openings", []):
        b = part(name)
        blo, bhi = b["min"], b["max"]
        if abs(blo[0] + bhi[0]) / 2 > 0.5:              # a side opening
            side = 1 if blo[0] > 0 else -1
            # (`openingPad`: the door leaf stands a few cm outside the lining, so at the opening's edge the camera
            # sees past the wall's end into the ground behind it; the wall overlaps the leaf by this much)
            pad = spec.get("openingPads", {}).get(name, spec.get("openingPad", 0.04))
            box = {"x": sorted([side * 0.55, side * 1.2]), "y": [r(blo[1] - 0.03), r(bhi[1] + 0.03)],
                   "z": [r(blo[2] + pad), r(bhi[2] - pad)]}
        else:                                           # front or rear
            front = blo[2] > 0
            box = {"x": [r(blo[0] - 0.03), r(bhi[0] + 0.03)], "y": [r(blo[1] - 0.03), r(bhi[1] + 0.03)],
                   "z": [r(blo[2] - 0.5), r(bhi[2] + 0.3)] if front else [r(blo[2] - 0.3), r(bhi[2] + 0.5)]}
        # The walls have an opening for a door only. A window's opening would show KI5's hull behind
        # it (frame rails and posts standing on the wall top) and leave notches in the cut wall top;
        # the glass is not drawn inside anyway (see hideOpenings). What KI5's hull keeps of a window
        # (the seal round its opening, a pillar between two panes) is not drawn inside either: the
        # window's box goes in the profile (windowBoxes, see the vehicle cutaway shader).
        if "window" in name.lower() or "windshield" in name.lower():
            window_boxes.append(box)
        else:
            openings.append(box)
            # the door frame's jambs (the hull's opening, black rubber) between the lining's ends and the leaf are
            # painted like the room: a box a hand wider than the leaf along the camper, from the lining out past the skin
            if abs(blo[0] + bhi[0]) / 2 > 0.5:
                side = 1 if blo[0] > 0 else -1
                jamb_boxes.append({"x": sorted([side * 0.6, side * 1.4]), "y": [r(blo[1] - 0.05), r(bhi[1] + 0.1)],
                                   "z": [r(blo[2] - 0.14), r(bhi[2] + 0.14)]})
    openings.extend(spec.get("extraOpenings", []))
    window_boxes.extend(spec.get("windowBoxes", []))
    wells = []
    if spec.get("entryOpening"):
        openings.append(spec["entryOpening"])
        window_boxes.append(spec["entryOpening"])
    for w in spec.get("wheelWells", []):
        wz = w["z"]
        half_length = w.get("halfLength", WELL_HALF)
        for side in (1, -1):
            outer = wall_line(ring, "left" if side > 0 else "right", wz - half_length, wz + half_length) + side * INSET
            inner = side * w["inner"]
            wells.append({"x": [r(inner), r(outer + side * 0.02)], "z": [r(wz - half_length), r(wz + half_length)],
                          "top": r(w.get("top", floor + WELL_TOP)), "bottom": r(floor - 0.16)})
    xs = [p[0] for p in ring]
    zs = [p[1] for p in ring]
    shell_cfg = {
        "measure": os.path.relpath(os.path.join(FLOORPLANS, measure_file), ROOT).replace("\\", "/"),
        "object": "shell_" + spec["texture"],
        "floorY": floor,
        "top": r(min(ceiling, floor + 1.64)),
        "refHeight": r(floor + 0.44, 2),
        "lowestOutline": r(floor + 0.24, 2),
        "segments": spec.get("segments", 72),
        "inset": INSET,
        "wall": "wall_panel",
        "floor": "floor_planks",
        "openings": openings,
        "grid": {"name": "MELens." + key + ".shell", "file": key + "_Shell", "cell": 0.025,
                 "xRange": [r(min(xs) - 0.05, 2), r(max(xs) + 0.05, 2)], "zRange": [r(min(zs) - 0.05, 2), r(max(zs) + 0.05, 2)],
                 "radius": WALK_RADIUS, "headroom": r(min(1.05, ceiling - floor - 0.1), 2), "floorTolerance": 0.04},
        "texture": spec["texture"],
        "seed": spec.get("seed", 11),
        "style": spec.get("style", STYLES[spec.get("kind", "camper")]),
        "wheelWells": [{"x": w["x"], "z": w["z"], "top": w["top"], "bottom": w["bottom"]} for w in wells],
        "panel": {"x": panel["x"], "depth": 0.02, "y": panel["y"], "z": panel["z"]},
    }
    if spec.get("reuseTexture"):
        shell_cfg["reuseTexture"] = spec["reuseTexture"]
    if spec.get("entryOpening"):
        shell_cfg["entryOpening"] = spec["entryOpening"]
        # A conservative rectangular room is narrower than a rounded rear body.
        # Close the entire measured rear cross-section, including the skirt below
        # the floor and the band between the room's corners and the exterior posts.
        plane=spec['box']['z'][0]+INSET-.004
        samples=[]
        for height,segments in hull_measure['sections'].items():
            crossing=[]
            for a,b in segments:
                if (a[1]-plane)*(b[1]-plane)<=0 and abs(a[1]-b[1])>1e-8:
                    crossing.append(a[0]+(b[0]-a[0])*(plane-a[1])/(b[1]-a[1]))
            if crossing and min(crossing)<-.2 and max(crossing)>.2:
                samples.append((float(height),min(crossing)+.008,max(crossing)-.008))
        samples.sort()
        assert samples,(key,'rear cross-section missing')
        bottom=max(hull_measure['body']['min'][1]+.008,floor-.32)
        high=shell_cfg['top']
        def section_at(y):
            lo=max((s for s in samples if s[0]<=y),default=samples[0])
            hi=min((s for s in samples if s[0]>=y),default=samples[-1])
            t=(y-lo[0])/(hi[0]-lo[0]) if hi[0]>lo[0] else 0
            return [r(y),r(lo[1]+(hi[1]-lo[1])*t),r(lo[2]+(hi[2]-lo[2])*t)]
        section=[section_at(bottom)]+[list(s) for s in samples if bottom<s[0]<high]+[section_at(high)]
        shell_cfg['rearClosure']={'z':r(plane,4),'section':section}
        # Follow the connected rear body contour, rather than extruding the
        # flat lining to body.min.z (the roof and lower skirt taper forward).
        # Only components reached from the two outer plane crossings count;
        # detached bumper/hitch details cannot set the closure's rear depth.
        def aft_component(segments,seed_x):
            clipped=[];neighbours={}
            def point_key(point):return (round(point[0],4),round(point[1],4))
            for a,b in segments:
                a,b=list(a),list(b)
                if min(a[1],b[1])>plane:continue
                if max(a[1],b[1])>plane:
                    t=(plane-a[1])/(b[1]-a[1])
                    cross=[a[0]+(b[0]-a[0])*t,plane]
                    if a[1]>plane:a=cross
                    else:b=cross
                ka,kb=point_key(a),point_key(b)
                if ka==kb:continue
                index=len(clipped);clipped.append((a,b))
                neighbours.setdefault(ka,[]).append((kb,index))
                neighbours.setdefault(kb,[]).append((ka,index))
            if not neighbours:return []
            seed=min(neighbours,key=lambda point:(point[0]-seed_x)**2+(point[1]-plane)**2)
            pending=[seed];seen=set();edges=set()
            while pending:
                node=pending.pop()
                if node in seen:continue
                seen.add(node)
                for other,index in neighbours[node]:
                    edges.add(index)
                    if other not in seen:pending.append(other)
            return [clipped[index] for index in sorted(edges)]

        def outer_crossing(side,z,is_left):
            crossing=[]
            for a,b in side:
                if min(a[1],b[1])-1e-8<=z<=max(a[1],b[1])+1e-8:
                    if abs(a[1]-b[1])<1e-8:crossing.extend((a[0],b[0]))
                    else:crossing.append(a[0]+(b[0]-a[0])*(z-a[1])/(b[1]-a[1]))
            if not crossing:return None
            return min(crossing) if is_left else max(crossing)

        def pillar_end(side,is_left):
            # A connected rear skin can continue across the transom into a
            # central apex: that is not the end of the side pillar. Follow its
            # outer envelope to the side-to-transom tangent turn instead. A
            # transverse run is within 30 degrees of the rear-facing plane.
            # Square-ended bodies simply end at their measured aft side corner.
            curve=[]
            for z in sorted({plane}|{p[1] for edge in side for p in edge},reverse=True):
                x=outer_crossing(side,z,is_left)
                if x is None:continue
                if curve and math.hypot(x-curve[-1][0],z-curve[-1][1])<.0001:continue
                # Triangle slicing introduces vertices on straight native
                # facets. Remove only sub-0.1mm deviations before sharing the
                # stations across heights; keep the actual silhouette bends.
                while len(curve)>1:
                    a,b=curve[-2],curve[-1]
                    length=math.hypot(x-a[0],z-a[1])
                    area=abs((b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(x-a[0]))
                    if length<1e-8 or area/length>=.0001:break
                    curve.pop()
                curve.append((x,z))
            previous=None
            for i,(a,b) in enumerate(zip(curve,curve[1:])):
                angle=math.atan2(abs(b[0]-a[0]),abs(b[1]-a[1]))
                if angle>=math.pi/3 and (previous is None or previous<math.pi/3 or angle-previous>=math.pi/12):
                    return a[1],curve
                previous=angle
            return (curve[-1][1] if curve else plane),curve

        depth_sources={};fractions={0.0,1.0};skin=.003
        for height,left,right in samples:
            if not bottom<=height<=high:continue
            segments=hull_measure['sections']['%.2f'%height]
            sides=[aft_component(segments,left-.008),aft_component(segments,right+.008)]
            if not all(sides):continue
            ends=[pillar_end(side,index==0) for index,side in enumerate(sides)]
            aft=max(end for end,curve in ends)+skin
            if aft>=plane-1e-6:continue
            depth_sources[height]=(aft,sides)
            # All contour bends become common stations, so interpolation in
            # height does not replace a rounded pillar with an arbitrary slab.
            for end,curve in ends:
                for x,z in curve:
                    if aft<z<plane:
                        fraction=round((z-plane)/(aft-plane),6)
                        if 0<fraction<1:fractions.add(fraction)
        fractions=sorted(fractions)
        depth_sections=[]
        # Depth must end at actual measured rows. Extending it down to the
        # unmeasured skirt endpoint produces an exposed triangular wedge;
        # dropping measured below-floor rows instead leaves the lower hinge
        # interval open. The mesh caps these measured endpoints, while the
        # original flat closure/leaf continues through the skirt and roof.
        depth_rows=[list(s) for s in samples if bottom<=s[0]<=high]
        for height,left,right in depth_rows:
            source=depth_sources.get(height)
            stations=[]
            for t in fractions:
                if source is None or t==0:
                    stations.append([r(plane,6),left,right]);continue
                aft,sides=source;z=plane+(aft-plane)*t
                bounds=[]
                for side_index,side in enumerate(sides):
                    x=outer_crossing(side,z,side_index==0)
                    assert x is not None,(key,height,z,'rear contour disconnected')
                    bounds.append(x+skin if side_index==0 else x-skin)
                assert bounds[1]-bounds[0]>.07,(key,height,z,'rear contour too narrow')
                stations.append([r(z,6),r(bounds[0],6),r(bounds[1],6)])
            depth_sections.append([height,stations])
        # No depth is extrapolated into the unmeasured skirt or roof bands.
        shell_cfg['rearClosure']['depthSections']=depth_sections
    # A cut-away cargo shell needs an opaque, full-height partition behind the
    # cab. The native cab mesh is often single-sided at this artificial cut.
    if spec.get("kind") == "cargo" and spec.get("cutFront") is not None:
        shell_cfg["cabBulkhead"] = {"top": max(ceiling, spec.get("cutFrontTop", ceiling))}
        if measure.get("cabSection"):
            shell_cfg["cabBulkhead"] = {"top": ceiling, "section": measure["cabSection"]}
        # The section was measured at the native cut plane. Placing it at the
        # inset room outline instead leaves a 33mm slit behind the intact roof.
        shell_cfg["cabBulkhead"]["z"] = spec["cutFront"]
        shell_cfg["cabBulkhead"].update(spec.get("cabBulkhead", {}))
    if spec.get("box"):
        # a rectangular room (a box truck's cargo space, a bus): the shell keeps its corners
        shell_cfg["sharpCorners"] = True
    if spec.get("floorOutline"):
        # the floor follows the hull's inside at floor height (see rv_kit.build_shell): for bodies that
        # tuck in under the floor, which the lining outlines from 0.24 up do not show. "measure": a
        # second measurement that has the floor's height among its outlines (the body's first one, the
        # furniture was fitted to, may not)
        shell_cfg["floorOutline"] = dict(spec["floorOutline"])
        if shell_cfg["floorOutline"].get("measure"):
            shell_cfg["floorOutline"]["measure"] = os.path.join(FLOORPLANS, shell_cfg["floorOutline"]["measure"]).replace("\\", "/")
        # the wall slopes up from the floor's edge: the walk grid counts the first part of the slope as floor
        shell_cfg["grid"]["floorTolerance"] = 0.2
    if spec.get("cornerReturns"):
        shell_cfg["cornerReturns"] = measured_corner_returns(hull_measure, spec["cornerReturns"], shell_cfg)
    if spec.get("cowlReturn"):
        import shell_rings
        lining = shell_rings.build(measure, shell_cfg)
        shell_cfg["cowlReturn"] = measured_cowl_return(hull_measure, spec["cowlReturn"], lining["room_ring"])
    if spec.get("doorLinings"):
        shell_cfg["doorLinings"] = spec["doorLinings"]
    if spec.get("separateShellSupports"):
        shell_cfg["separateShellSupports"] = True
    if spec.get("separateDoorReturns"):
        assert shell_cfg.get("separateShellSupports"), "separate doorway returns need separate supports"
        shell_cfg["separateDoorReturns"] = True
    if spec.get("nativeSupportSeals"):
        shell_cfg["nativeSupportSeals"] = spec["nativeSupportSeals"]
    if spec.get("nativeFloorPerimeter"):
        assert spec.get("nativeBodyWalls"), "measured perimeter margins require native body walls"
        shell_cfg["nativeFloorPerimeter"] = spec["nativeFloorPerimeter"]
    if spec.get("flatWheelFloor"):
        assert shell_cfg.get("separateShellSupports") and shell_cfg.get("nativeSupportSeals"), "flat wheel floor needs measured separate supports"
        shell_cfg["flatWheelFloor"] = True
    if spec.get("nativeWellCapSideX"):
        shell_cfg["nativeWellCapSideX"] = spec["nativeWellCapSideX"]
    if spec.get("nativeFloorReturns"):
        shell_cfg["nativeFloorReturns"] = spec["nativeFloorReturns"]
    native_panel = load(os.path.join(ROOT, "tools-src", "vehicles", "native-panel-placements.json"))["families"].get(key)
    if native_panel:
        assert spec.get("nativeBodyWalls") and spec.get("separateShellSupports")
        assert native_panel["y"] == panel["y"] and native_panel["z"] == panel["z"], "Measured panel footprint changed"
        shell_cfg["nativePanel"] = native_panel
    if spec.get("navigationFront") is not None:
        # A visual cab closure can extend beyond the original room floor.
        # Keep its walk-grid erosion on that same original floor boundary.
        shell_cfg["grid"]["frontLimit"] = spec["navigationFront"]
    window_returns = native_window_returns(key)
    if window_returns:
        assert spec.get("nativeBodyWalls")
        shell_cfg["nativeWindowReturns"] = window_returns
    finish = native_wall_finish(spec, measure, shell_cfg, hull_measure)
    if finish:
        shell_cfg["nativeWallFinish"] = finish
    with open(os.path.join(CFG, "shell_%s.json" % key), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(shell_cfg, handle, indent=4)

    # --- the profile --------------------------------------------------------------------
    shell_models = ["MELensShell_%s_floor" % spec["texture"], "MELensShell_%s_walls" % spec["texture"]]
    if shell_cfg.get("cabBulkhead"):
        shell_models.append("MELensShell_%s_bulkhead" % spec["texture"])
    if shell_cfg.get("entryOpening"):
        shell_models.append("MELensShell_%s_entry" % spec["texture"])
    entry_model = len(shell_models)
    for lining in shell_cfg.get("doorLinings", []):
        shell_models.append("MELensShell_%s_%s" % (spec["texture"], lining["suffix"]))
    if shell_cfg.get("separateShellSupports"):
        # Append only: saved entry/side-door model indices keep their meaning.
        shell_models.append("MELensShell_%s_support" % spec["texture"])
    arch_only = shell_cfg.get("nativeSupportSeals", {}).get("archOnly", False)
    has_door_returns = separate_door_returns(shell_cfg)
    if shell_cfg.get("nativeSupportSeals") and not arch_only:
        shell_models.append("MELensShell_%s_support_seals" % spec["texture"])
    if arch_only and has_door_returns:
        # Preserve every existing optional native model index as well as the
        # published prefix; the new arch models are appended after returns.
        shell_models.append("MELensShell_%s_door_returns" % spec["texture"])
    wheel_covers_model = wheel_floor_model = wheel_wall_model = None
    curved_wheels = shell_cfg.get("nativeSupportSeals", {}).get("archSides")
    if shell_cfg.get("flatWheelFloor") and not curved_wheels:
        shell_models.append("MELensShell_%s_wheel_covers" % spec["texture"])
        wheel_covers_model = len(shell_models)
        shell_models.append("MELensShell_%s_wheel_floor" % spec["texture"])
        wheel_floor_model = len(shell_models)
        if shell_cfg["nativeSupportSeals"].get("archWall",True):
            shell_models.append("MELensShell_%s_wheel_wall" % spec["texture"])
            wheel_wall_model = len(shell_models)
    if not arch_only and has_door_returns:
        shell_models.append("MELensShell_%s_door_returns" % spec["texture"])
    if native_panel and not spec.get("factoryLayout"):
        shell_models.append("MELensShell_%s_panel_legacy" % spec["texture"])
        legacy_panel_model = len(shell_models)
        shell_models.append("MELensShell_%s_panel_native" % spec["texture"])
        native_panel_model = len(shell_models)
    if shell_cfg.get("nativeFloorPerimeter"):
        shell_models.append("MELensShell_%s_floor_perimeter" % spec["texture"])
        native_floor_model = len(shell_models)
    if curved_wheels:
        # New curved opt-ins append after every existing optional model too.
        if shell_cfg["nativeSupportSeals"].get("reuseSupportAsCovers"):
            wheel_covers_model = shell_models.index("MELensShell_%s_support" % spec["texture"])+1
        else:
            shell_models.append("MELensShell_%s_wheel_covers" % spec["texture"])
            wheel_covers_model = len(shell_models)
        shell_models.append("MELensShell_%s_wheel_floor" % spec["texture"])
        wheel_floor_model = len(shell_models)
        if shell_cfg["nativeSupportSeals"].get("archWall",True):
            shell_models.append("MELensShell_%s_wheel_wall" % spec["texture"])
            wheel_wall_model = len(shell_models)
    if native_panel and spec.get("factoryLayout"):
        # New factory opt-ins append after every already-published native model.
        shell_models.append("MELensShell_%s_panel_legacy" % spec["texture"])
        legacy_panel_model = len(shell_models)
        shell_models.append("MELensShell_%s_panel_native" % spec["texture"])
        native_panel_model = len(shell_models)
    if window_returns:
        window_return_models = []
        for index, pane in enumerate(window_returns, 1):
            shell_models.append("MELensShell_%s_window_return_%d" % (spec["texture"], index))
            trim_entry = dict(model=len(shell_models), part=pane["part"])
            if pane.get("parent"):trim_entry["parent"] = pane["parent"]
            if pane.get("scripts"):trim_entry["scripts"] = pane["scripts"]
            window_return_models.append(trim_entry)
    hide = {}
    for model, keep in spec.get("hide", {}).items():
        if keep is True or isinstance(keep, dict):
            hide[model] = keep                     # all of it, or {plane = {a, b, c, d}}
        else:
            hide[model] = r(ceiling - 0.14 if keep == "ceiling" else keep, 2)
    # A camper's window glass is not drawn while you are inside: cut down with the walls, the glass
    # shows as black slabs standing on the wall tops. The shell's openings then show the outside,
    # like open windows. (A door leaf stays, closed like the hull around it; its inside is painted
    # like the room, see doorPaint. A bus or truck lists what to hide in its spec: its cab's glass
    # stays.)
    if spec.get("hideOpenings", spec.get("kind", "camper") == "camper"):
        for part_name in parts:
            low = part_name.lower()
            if "window" in low or "windshield" in low:
                hide.setdefault("mesh:" + part_name, True)
    length_z = (min(zs), max(zs))
    lamps = spec.get("lamps")
    if lamps is None:
        count = max(1, int(round((length_z[1] - length_z[0]) / 2.2)))
        step = (length_z[1] - length_z[0]) / count
        lamps = [[0.0, r(length_z[0] + step * (i + 0.5), 2)] for i in range(count)]
    profile = {
        "name": spec["title"],
        "kind": spec.get("kind", "camper"),
        "seatId": "MELensCabin",
        "floorY": floor,
        "mesh": mesh,
        "shell": {"models": shell_models},
        "hideKI5": hide,
        "light": {
            "interiorModels": shell_models,
            "daylight": 1.0, "minimum": 0.18, "topDown": 0.5,
            "lamps": [{"x": l[0], "y": r(floor + LAMP_HEIGHT, 2), "z": l[1]} for l in lamps],
            "lampReach": spec.get("lampReach", 1.9),
            "lampColour": [1.0, 0.94, 0.82],
            "worldColour": [0.8, 0.75, 0.65],
            "worldRadius": spec.get("worldRadius", 3),
        },
        # fragments with -z - d > 0 are cut: d from the cut's height above the floor
        "cutPlanes": [[0.0, 0.0, -1.0, r(-((h + floor - 0.06) / MESH_SCALE), 2)] for h in CUT_HEIGHTS],
        "nearCutY": r(floor + NEAR_CUT, 2),
        "walkSpeed": 1.35,
        "aisleX": spec.get("aisleX", 0.0),
        "standing": {"door": entry["part"], "area": entry["area"], "inside": [r(stand[0]), floor, r(stand[1])],
                     "outside": [r(v) for v in outside]},
        "door": {"x": r(stand[0]), "z": r(stand[1])},
        "exitMarker": marker,
        "walkGrid": shell_cfg["grid"]["name"],
        "walkable": [{"x1": r(stand[0] - 0.1), "x2": r(stand[0] + 0.1), "z1": r(stand[1] - 0.1), "z2": r(stand[1] + 0.1)}],
        "spots": [spot for spot, _ in spots],
        "wheelWells": [{"x": sorted(w["x"]), "y": [w["bottom"] - 0.15, w["top"]], "z": w["z"]} for w in wells],
        # the panel's face, 0.01 into the room from its wall
        "panel": {"x": r(panel["x"] + (-0.01 if panel_wall == "left" else 0.01)), "y": r((panel["y"][0] + panel["y"][1]) / 2),
                  "z": r((panel["z"][0] + panel["z"][1]) / 2), "halfX": 0.05, "halfY": 0.075, "halfZ": 0.09},
        "waterTank": spec.get("waterTank", 60),
        "fuelTank": spec.get("fuelTank", 20),
    }
    if shell_cfg.get("entryOpening"):
        profile["shell"]["entryModel"] = entry_model
        profile["shell"]["entryDoor"] = entry["part"]
    if shell_cfg.get("nativeFloorPerimeter"):
        profile["shell"]["nativeFloorModel"] = native_floor_model
    if native_panel:
        profile["shell"]["legacyPanelModel"] = legacy_panel_model
        profile["shell"]["nativePanelModel"] = native_panel_model
        side = 1 if panel["x"] > 0 else -1
        centre_x = sum(x for row in native_panel["skinX"] for x in row) / 4 - side * (native_panel["inset"] + shell_cfg["panel"]["depth"] / 2)
        profile["nativePanel"] = dict(profile["panel"], x=r(centre_x, 6))
    if shell_cfg.get("doorLinings"):
        profile["shell"]["extraDoors"] = [{"model": entry_model+i+1, "part": d["part"]}
                                           for i,d in enumerate(shell_cfg["doorLinings"])]
    if window_returns:
        profile["shell"]["windowReturns"] = window_return_models
    if shell_cfg.get("flatWheelFloor"):
        profile["shell"]["wheelCoversModel"] = wheel_covers_model
        profile["shell"]["wheelFloorModel"] = wheel_floor_model
        if wheel_wall_model is not None:profile["shell"]["wheelWallModel"] = wheel_wall_model
        seals = shell_cfg["nativeSupportSeals"]
        profile["nativeWheelArch"] = ({"sides": [{"side": s["side"], "contour": s["contour"]} for s in seals["archSides"]]}
            if seals.get("archSides") else {"sideX": seals["archSideX"], "contour": seals["archContour"]})
        if spec.get("nativeWheelWellTrim"):profile["nativeWheelWellTrim"] = spec["nativeWheelWellTrim"]
    if "mesh" in spec:
        # A short cargo body can have its ceiling below the nominal High cut.
        # Keep the cut under that measured ceiling: otherwise its roof flange
        # survives above the lining as an unsupported strip (E150).
        cut_tops = [min(h + floor, ceiling - .02) if spec.get("kind") == "cargo" else h + floor
                    for h in CUT_HEIGHTS]
        profile["cutPlanes"] = [[0, 0, -1, r(mesh["lift"] - h / mesh["scale"], 2)] for h in cut_tops]
    if spec.get("nativeHighCut") is not None:
        high = spec["nativeHighCut"]
        assert spec.get("nativeBodyWalls") and floor < high < spec.get("nativeCeiling", ceiling)
        profile["nativeCutPlanes"] = [list(plane) for plane in profile["cutPlanes"]]
        profile["nativeCutPlanes"][2] = [0, 0, -1, r(mesh["lift"] - high / mesh["scale"], 6)]
    if abs(scale - 0.9) > 0.00001:
        profile["vehicleScale"] = scale
    for extra in ("vanillaSeats", "ki5Storage", "loot", "driver", "cutFront", "cutFrontTop", "nativeCabCutFront", "nativeCabCutFrontTop", "modelShift", "bodyKeepPlanes"):
        if extra in spec:
            profile[extra] = spec[extra]
    # KI5's body carries details inside its hull (a trailer tongue's arm tips at the front corners)
    # that stand inside the shell's lining and show as black objects: the cutaway does not draw
    # KI5's own models inside the lining's outline (written with the walk grid by the bake), low
    # above the floor. (Not in a bus or truck, whose driver's seat and cab are KI5's.)
    if spec.get("extraSeats"):
        profile["extraSeats"] = spec["extraSeats"]
    if spec.get("clipBody", spec.get("kind", "camper") == "camper"):
        profile["clipBody"] = True
    if spec.get("nativeBodyLining"):
        profile["nativeBodyLining"] = spec["nativeBodyLining"]
    if spec.get("nativeBodyWalls"):
        assert shell_cfg.get("separateShellSupports"), "native walls need independent floor supports"
        profile["nativeBodyWalls"] = True
        if spec.get("nativeBodyTrim"):
            profile["nativeBodyTrim"] = spec["nativeBodyTrim"]
        # The fallback keeps the dependency ceiling above its low wall slice.
        # Native High retains whole panes and would expose its detached rails.
        ceiling_models = [model for model, keep in spec.get("hide", {}).items() if keep == "ceiling"]
        if ceiling_models:
            profile["nativeBodyKeepPlanes"] = {model: [0, 0, 0, 1] for model in ceiling_models}
        if spec.get("nativeBodyKeepPlanes"):
            profile.setdefault("nativeBodyKeepPlanes", {}).update(spec["nativeBodyKeepPlanes"])
        if spec.get("nativeCabPartition"):
            assert shell_cfg.get("cabBulkhead"), "native partition needs a measured cab section"
            profile["nativeCabPartition"] = True
        if spec.get("nativePlainFinish"):
            profile["nativePlainFinish"] = True
        if spec.get("nativeWallMaterial"):
            profile["nativeWallMaterial"] = {k:finish[k] for k in ("texture","height","perimeter")}
            if spec.get("nativeWallBoundaryFinish"):
                profile["nativeWallBoundaryFinish"] = True
        if spec.get("nativeStockMetal"):
            profile["nativeStockMetal"] = native_stock_metal(spec)
        if spec.get("nativeBodyModels"):
            profile["nativeBodyModels"] = spec["nativeBodyModels"]
        leaves=native_living_leaves(key)
        if leaves:
            profile["nativeLivingLeafModels"]=leaves
            profile["nativeBodyModels"]=list(dict.fromkeys(profile.get("nativeBodyModels",[])+leaves))
        for extra in ("nativeCabModels", "nativeArchTrimModels", "nativeCabKeepPlanes", "nativeCabFallbackBodyModels", "nativeRoofCuts", "nativeSurfaceCuts", "nativeNearFaces"):
            if spec.get(extra):
                profile[extra] = spec[extra]
        if spec.get("nativePlainFinish") and spec.get("entryOpening"):
            profile["nativeEntryOpening"] = spec["entryOpening"]
            if spec.get("nativeEntryNearBounds"):
                profile["nativeEntryNearBounds"] = spec["nativeEntryNearBounds"]
        if spec.get("nativeDoorOpenings"):
            profile["nativeDoorOpenings"] = spec["nativeDoorOpenings"]
        profile.setdefault("nativeBodyLining", [.64, .66, .67] if profile["kind"] == "cargo"
                           else [.78, .76, .70] if profile["kind"] == "bus" else [.80, .76, .66])
    if window_boxes:
        profile["windowBoxes"] = window_boxes
    if jamb_boxes:
        profile["jambBoxes"] = jamb_boxes
    # the inside of a door leaf is bare black: painted like the room's walls (not in a truck)
    if spec.get("kind", "camper") in ("camper", "bus"):
        profile["doorPaint"] = [0.80, 0.78, 0.72]
    if spec.get("blocked"):
        profile["blocked"] = [{"x1": b["x"][0], "x2": b["x"][1], "z1": b["z"][0], "z2": b["z"][1]} for b in spec["blocked"]]

    # --- checks: what stands at each spot must not overlap another piece, a wheel well, the
    # door or a blocked area (boxes stacked in one column are one place, not an overlap)
    def piece_print(spot):
        dims = kit.get(spot.get("default"))
        return footprint(dict(spot, length=dims["width"] if dims else spot["length"], depth=dims["depth"] if dims else spot["depth"]))

    prints = [(i + 1, piece_print(spot)) for i, (spot, _) in enumerate(spots) if not spot.get("empty")]
    well_prints = [(min(w["x"]), max(w["x"]), w["z"][0], w["z"][1]) for w in wells]
    # the utility panel (lights, dashboard) on the side wall: no room may cover it, or
    # whatever is put there hides it
    panel_face = profile["panel"]
    panel_room = (panel_face["x"] - 0.07, panel_face["x"] + 0.07,
                  panel_face["z"] - panel_face["halfZ"], panel_face["z"] + panel_face["halfZ"])
    for i, (spot, _) in enumerate(spots):
        if overlap(footprint(spot), panel_room):
            PROBLEMS.append("%s: spot %d (%s, %s) covers the utility panel (x %.2f, z %.2f..%.2f)" % (
                key, i + 1, spot["wall"], spot.get("default"), panel_face["x"], panel_room[2], panel_room[3]))
    quiet = len(spots) > 24            # a truck's boxes: list problems, not every box
    for i, a in prints:
        for j, b in prints:
            same_column = spots[i - 1][0].get("level") and spots[j - 1][0].get("level") and \
                abs(a[0] - b[0]) < 0.011 and abs(a[2] - b[2]) < 0.011
            if i < j and not same_column and overlap(a, b, 0.005):
                PROBLEMS.append("%s: spots %d and %d overlap (%s / %s)" % (key, i, j, [r(v, 3) for v in a], [r(v, 3) for v in b]))
        for well in well_prints:
            if overlap(a, well):
                print("  note %s: spot %d stands over a wheel well (the part of it inside the well is not drawn)" % (key, i))
        if overlap(a, (stand[0] - 0.12, stand[0] + 0.12, stand[1] - 0.12, stand[1] + 0.12)):
            print("  WARNING %s: spot %d covers where you stand inside the door" % (key, i))
        for blk in spec.get("blocked", []):
            if overlap(a, (blk["x"][0], blk["x"][1], blk["z"][0], blk["z"][1])):
                print("  WARNING %s: spot %d overlaps a blocked area" % (key, i))
        if not quiet:
            print("  spot %d %-6s %-8s x %6.2f..%-6.2f z %6.2f..%-6.2f" % (i, spots[i - 1][0]["wall"], spots[i - 1][0].get("default"), *a))
    lines = ["-- Generated by tools-src/vehicles/make_vehicles.py from specs/%s.json; edit the spec." % key,
             "MELens = MELens or {}",
             "MELens.Profiles = MELens.Profiles or {}",
             "",
             "local profile = " + lua(profile),
             ""]
    for full in spec["vehicles"]:
        lines.append('MELens.Profiles["%s"] = profile' % full)
    if spec.get("factoryLayout"):
        import factory_layouts
        factory_layouts.append_profiles(spec, profile, lines)
    out = os.path.join(LUA, "MELens_Profile_%s.lua" % key)
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print("VEHICLE %-12s floor %.2f spots %d seats %d wells %d openings %d -> %s" % (
        key, floor, len(spots), len(placement), len(wells), len(openings), os.path.basename(out)))
    return spec["texture"]


def write_factory_models():
    """Refresh declarations from qualified specs without recreating their geometry decisions."""
    declarations=["/* Generated from the measured factory specs. Existing authored atlases. */","module Base","{"]
    for filename in sorted(os.listdir(SPECS)):
        if not filename.endswith('.json'):continue
        spec=load(os.path.join(SPECS,filename))
        if spec.get("disabled") or not spec.get("factoryLayout"):continue
        apply_native_floor(spec)
        texture=spec["texture"]
        suffixes=["floor","walls","bulkhead","entry"]+[d["suffix"] for d in spec.get("doorLinings",[])]
        if spec.get("separateShellSupports"):suffixes.append("support")
        if spec.get("nativeSupportSeals") and not spec["nativeSupportSeals"].get("archOnly"):suffixes.append("support_seals")
        if spec.get("flatWheelFloor"):
            suffixes += ["wheel_covers","wheel_floor"]
            if spec["nativeSupportSeals"].get("archWall",True):suffixes.append("wheel_wall")
        if separate_door_returns(spec):suffixes.append("door_returns")
        for suffix in suffixes:
            material="floor" if suffix in ("floor","wheel_floor") else "walls"
            atlas=spec.get("nativeWallMaterial",spec.get("reuseTexture",texture)) if suffix in ("bulkhead","wheel_wall") else spec.get("reuseTexture",texture)
            declarations.append("    model MELensShell_%s_%s { mesh = vehicles/MELens_Fleet|shell_%s_%s, texture = Vehicles/MELensShell_%s_%s, shader = vehiclewheel, scale = 0.0111111, }" % (texture,suffix,texture,suffix,atlas,material))
    declarations.append("}")
    with open(os.path.join(MEDIA,"scripts","MELens_fleet_models.txt"),"w",encoding="utf-8",newline="\n") as handle:
        handle.write("\n".join(declarations)+"\n")


def write_native_models():
    """Optional appended models share one declaration owner across both generators."""
    declarations = ["/* Generated measured native floor additions; existing material assets. */", "module Base", "{"]
    for filename in sorted(os.listdir(SPECS)):
        if not filename.endswith('.json'): continue
        spec = load(os.path.join(SPECS, filename))
        if spec.get("disabled"): continue
        apply_native_floor(spec)
        texture = spec["texture"]
        suffixes = []
        if not spec.get("factoryLayout"):
            suffixes = ["door_returns"] if separate_door_returns(spec) else []
            if spec.get("flatWheelFloor"):
                if not spec.get("nativeSupportSeals", {}).get("reuseSupportAsCovers"):suffixes.append("wheel_covers")
                suffixes.append("wheel_floor")
                if spec.get("nativeSupportSeals", {}).get("archWall",True):suffixes.append("wheel_wall")
        native_panels = load(os.path.join(ROOT, "tools-src", "vehicles", "native-panel-placements.json"))["families"]
        if spec["key"] in native_panels: suffixes += ["panel_legacy", "panel_native"]
        if spec.get("nativeFloorPerimeter"): suffixes.append("floor_perimeter")
        suffixes.extend("window_return_%d" % i for i in range(1, len(native_window_returns(spec["key"]))+1))
        fbx = "MELens_Fleet" if spec.get("factoryLayout") else "MELens_Shells"
        atlas = spec.get("reuseTexture", texture)
        for suffix in suffixes:
            material = "floor" if suffix in ("wheel_floor", "floor_perimeter") else "walls"
            selected_atlas = spec.get("nativeWallMaterial",atlas) if suffix == "wheel_wall" or suffix.startswith("window_return_") else atlas
            declarations.append("    model MELensShell_%s_%s { mesh = vehicles/%s|shell_%s_%s, texture = Vehicles/MELensShell_%s_%s, shader = vehiclewheel, scale = 0.0111111, }" % (texture,suffix,fbx,texture,suffix,selected_atlas,material))
    cloud = load(os.path.join(ROOT, "tools-src", "vehicles", "native-floor-perimeters.json"))["families"].get("FlyingCloud22")
    if cloud:
        cfg_path = os.path.join(ROOT, "tools-src", "blender", "cfg", "shell_FlyingCloud22.json")
        cfg = load(cfg_path)
        cloud_returns = native_window_returns("FlyingCloud22")
        cfg["nativeWindowReturns"] = cloud_returns
        measure=load(os.path.join(ROOT,cfg["measure"]))
        cloud_finish=native_wall_finish(dict(nativeWallMaterial="cloud22"),measure,cfg,measure)
        cfg["nativeWallFinish"]=cloud_finish
        cfg["nativeFloorPerimeter"] = {key: cloud[key] for key in ("margins", "polygons") if cloud.get(key)}
        cloud_arch = load(os.path.join(ROOT, "tools-src", "vehicles", "native-wheel-floors.json"))["families"].get("FlyingCloud22")
        if cloud_arch:
            cfg["flatWheelFloor"] = True
            cfg["nativeSupportSeals"] = dict(archSides=cloud_arch["sides"],archOnly=True,overlap=.002)
            arch_profile = {"sides": [{"side": s["side"], "contour": s["contour"]} for s in cloud_arch["sides"]]}
            manual_path = os.path.join(LUA, "MELens_Profiles.lua")
            with open(manual_path,encoding="utf-8") as handle:text=handle.read()
            start,end="-- BEGIN GENERATED CLOUD NATIVE ARCH","-- END GENERATED CLOUD NATIVE ARCH"
            assert text.count(start)==text.count(end)==1,"manual Cloud data markers missing"
            prefix,rest=text.split(start);_,suffix=rest.split(end)
            text=prefix+start+"\nlocal cloudNativeWheelArch = "+lua(arch_profile)+"\n"+end+suffix
            with open(manual_path,"w",encoding="utf-8",newline="\n") as handle:handle.write(text)
            for wheel_suffix in ("wheel_covers","wheel_floor","wheel_wall"):
                material="floor" if wheel_suffix=="wheel_floor" else "walls"
                declarations.append("    model MELensShell_cloud22_%s { mesh = vehicles/MELens_Shells|shell_cloud22_%s, texture = Vehicles/MELensShell_cloud22_%s, shader = vehiclewheel, scale = 0.0111111, }" % (wheel_suffix,wheel_suffix,material))
        with open(cfg_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(cfg, handle, indent=4); handle.write("\n")
        manual_path=os.path.join(LUA,"MELens_Profiles.lua")
        with open(manual_path,encoding="utf-8") as handle:text=handle.read()
        start,end="-- BEGIN GENERATED CLOUD WINDOW RETURNS","-- END GENERATED CLOUD WINDOW RETURNS"
        if start not in text:
            marker="function MELens.profileFor(vehicle)"
            assert marker in text,"Cloud profile boundary missing"
            text=text.replace(marker,start+"\n"+end+"\n\n"+marker)
        prefix,rest=text.split(start);_,suffix=rest.split(end)
        models=[];trims=[]
        for index,pane in enumerate(cloud_returns,1):
            model="MELensShell_cloud22_window_return_%d" % index
            models.append(model)
            trim=dict(model=7+index,part=pane["part"])
            if pane.get("parent"):trim["parent"]=pane["parent"]
            if pane.get("scripts"):trim["scripts"]=pane["scripts"]
            trims.append(trim)
            declarations.append("    model %s { mesh = vehicles/MELens_Shells|shell_cloud22_window_return_%d, texture = Vehicles/MELensShell_cloud22_walls, shader = vehiclewheel, scale = 0.0111111, }" % (model,index))
        block=('\nlocal cloudProfile = MELens.Profiles["Base.Trailer54FlyingCloud22"]\n'
               'for _, model in ipairs('+lua(models)+') do\n'
               '    table.insert(cloudProfile.shell.models, model)\n'
               '    table.insert(cloudProfile.light.interiorModels, model)\nend\n'
               'cloudProfile.shell.windowReturns = '+lua(trims)+'\n')
        cloud_leaves=native_living_leaves("FlyingCloud22")
        if cloud_leaves:
            block+='cloudProfile.nativeBodyModels = '+lua(cloud_leaves)+'\ncloudProfile.nativeLivingLeafModels = '+lua(cloud_leaves)+'\n'
        text=prefix+start+block+end+suffix
        with open(manual_path,"w",encoding="utf-8",newline="\n") as handle:handle.write(text)
        declarations.append("    model MELensShell_cloud22_floor_perimeter { mesh = vehicles/MELens_Shells|shell_cloud22_floor_perimeter, texture = Vehicles/MELensShell_cloud22_floor, shader = vehiclewheel, scale = 0.0111111, }")
    declarations.append("}")
    with open(os.path.join(ROOT,"mod/RealVehicleInteriors/common/media/scripts/MELens_native_floor_models.txt"),"w",encoding="utf-8",newline="\n") as handle:
        handle.write("\n".join(declarations)+"\n")


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(f[:-5] for f in os.listdir(SPECS) if f.endswith(".json"))
    textures = [t for t in (build(os.path.join(SPECS, n + ".json")) for n in names) if t]
    write_native_models()
    write_factory_models()
    if PROBLEMS:
        print("\nLAYOUT PROBLEMS (fix the spec, then build again):")
        for line in PROBLEMS:
            print("  " + line)
        sys.exit(1)
    for t in textures:
        print('    model MELensShell_%s_floor { mesh = vehicles/MELens_Shells|shell_%s_floor, texture = Vehicles/MELensShell_%s_floor, shader = vehiclewheel, scale = 0.0111111, }' % (t, t, t))
        print('    model MELensShell_%s_walls { mesh = vehicles/MELens_Shells|shell_%s_walls, texture = Vehicles/MELensShell_%s_walls, shader = vehiclewheel, scale = 0.0111111, }' % (t, t, t))
