"""Developer helper: do the furniture and the shell clip through each other?

    blender -b --factory-startup --python dev/clip_audit.py -- <mod media folder> [swaps] [detail] [key ...]

For each vehicle (default: all), every spot's default piece is put where the game puts it
(profile spots + the piece models of MELens_RV.fbx) and its real triangles are tested against
the shell's walls and against every other piece. Contact is not clipping: pieces are lifted
0.008 off their wall before testing. What lies inside a wheel well is hidden by the shader,
so it is not counted. For each clip it prints the triangles involved, where they are
(passenger space: x to the left, y above the floor, z to the front) and the depth: how far
the piece would have to move into the room to stand clear. Exit code 1 when anything clips."""
import json
import os
import re
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1:]
MEDIA = os.path.abspath(args[0])
LUA = os.path.join(MEDIA, "lua", "shared")
SWAPS = "swaps" in args[1:]          # also try every piece the game lets you put in each spot
DETAIL = "detail" in args[1:]        # with swaps: where each clash is and how far apart the pieces would have to be
KEYS = [a for a in args[1:] if a not in ("swaps", "detail")] or ["FlyingCloud22", "Bambi16", "Airflyte", "Scamp13", "Scamp16", "B700", "F700box"]
TEXTURE = {"FlyingCloud22": "cloud22", "Bambi16": "bambi16", "Airflyte": "airflyte", "Scamp13": "scamp13",
           "Scamp16": "scamp16", "B700": "b700", "F700box": "f700box"}
WALLS = {"front": ((-1, 0), (0, -1)), "back": ((1, 0), (0, 1)), "left": ((0, 1), (-1, 0)), "right": ((0, -1), (1, 0))}
LIFT = 0.008
SLOPE_TOP = 0.30          # the height of the lowest lining ring, where a floor-following lining slope ends
TOLERATED = 0.012           # up to this depth is contact, not clipping
SWAP_TOLERATED = 0.03       # two pieces the player swapped in: handles may touch a neighbour's corner
MIRRORED = ("busseat", "busseat2")


def parse_block(text, start_token):
    """The text of the `{ ... }` after start_token, and the top-level `{ ... }` entries in it."""
    start = text.index(start_token) + len(start_token)
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


def load_kit():
    text = open(os.path.join(LUA, "MELens_RVKit.lua"), encoding="utf-8").read()
    kit = {}
    for m in re.finditer(r'(\w+) = \{ width = ([\d.]+), depth = ([\d.]+), height = ([\d.]+), capacity = \d+, kind = "(\w+)"', text):
        kit[m.group(1)] = {"width": float(m.group(2)), "depth": float(m.group(3)), "height": float(m.group(4)),
                           "kind": m.group(5)}
    return kit


KIT = load_kit()


def fits(spot, name):
    """MELens.Parts.fits."""
    k = KIT[name]
    if (k["kind"] == "box") != bool(spot["cargo"]):
        return False
    if k["width"] > spot["length"] + 0.005 or k["depth"] > spot["depth"] + 0.005:
        return False
    if k["kind"] in ("bed", "seat"):
        if not spot["seats"]:
            return False
        if name in MIRRORED and spot["wall"] not in ("left", "right"):
            return False
    return True


def field(text, name, pattern):
    m = re.search(r"\b" + name + r" = " + pattern, text)
    return m.group(1) if m else None


def load_profile(key):
    path = os.path.join(LUA, "MELens_Profile_%s.lua" % key)
    if not os.path.exists(path):
        path = os.path.join(LUA, "MELens_Profiles.lua")
    text = open(path, encoding="utf-8").read()
    _, spot_entries = parse_block(text, "spots = {")
    spots = []
    for e in spot_entries:
        spots.append({"x": float(field(e, "x", r"([-\d.]+)")), "z": float(field(e, "z", r"([-\d.]+)")),
                      "wall": field(e, "wall", r'"(\w+)"'), "default": field(e, "default", r'"(\w+)"'),
                      "rise": float(field(e, "rise", r"([\d.]+)") or 0.0),
                      "length": float(field(e, "length", r"([\d.]+)")), "depth": float(field(e, "depth", r"([\d.]+)")),
                      "cargo": field(e, "cargo", r"(true)") == "true", "empty": field(e, "empty", r"(true)") == "true", "seats": re.search(r"\bseats = \{", e) is not None})
    floor = float(re.search(r"floorY = ([-\d.]+)", text).group(1))
    wells = []
    if "wheelWells = {" in text:
        _, well_entries = parse_block(text, "wheelWells = {")
        for e in well_entries:
            m = re.search(r"x = \{ ([-\d.]+), ([-\d.]+) \}.*?y = \{ ([-\d.]+), ([-\d.]+) \}.*?z = \{ ([-\d.]+), ([-\d.]+) \}", e, re.S)
            if m:
                v = [float(g) for g in m.groups()]
                wells.append({"x": v[0:2], "y": v[2:4], "z": v[4:6]})
    return spots, floor, wells


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(MEDIA, "models_X", "vehicles", "MELens_RV.fbx"))
bpy.ops.import_scene.fbx(filepath=os.path.join(MEDIA, "models_X", "vehicles", "MELens_Shells.fbx"))
objects = {o.name: o for o in bpy.data.objects if o.type == "MESH"}


def find(name):
    if name in objects:
        return objects[name]
    for key, obj in objects.items():
        if key.split(".")[0] == name:
            return obj
    raise KeyError(name)


def world_mesh(obj, matrix, shift=Vector((0, 0, 0))):
    """The mesh's vertices in tiles: the importer's own transform (FBX centimetres, y-up),
    then `matrix`, the piece's place in the vehicle."""
    full = matrix @ obj.matrix_world
    verts = [full @ v.co + shift for v in obj.data.vertices]
    polys = [tuple(p.vertices) for p in obj.data.polygons]
    return verts, polys


def in_wells(point, wells, pad=0.03):
    # passenger (x, y, z) -> Blender (-x, z, y)
    for w in wells:
        x0, x1 = sorted(-v for v in w["x"])
        z0, z1 = sorted(w["z"])
        if x0 - pad <= point.x <= x1 + pad and z0 - pad <= point.y <= z1 + pad and point.z <= w["y"][1] + pad:
            return True
    return False


def centre(verts, poly):
    return sum((verts[i] for i in poly), Vector()) / len(poly)


def passenger(point, floor):
    return "x %+.2f  y %.2f  z %+.2f" % (-point.x, point.z - floor, point.y)


class Piece:
    def __init__(self, index, spot, floor):
        self.index, self.spot, self.floor = index, spot, floor
        (ax, az), (ox, oz) = WALLS[spot["wall"]]
        xa, ya = Vector((-ax, az, 0)), Vector((ox, -oz, 0))
        matrix = Matrix(((xa.x, ya.x, 0, 0), (xa.y, ya.y, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
        matrix.translation = Vector((-spot["x"], spot["z"], floor + spot["rise"]))
        self.matrix = matrix
        self.name = spot["default"]
        if self.name in MIRRORED and spot["wall"] == "right":
            self.name += "_r"
        self.obj = find("rv_" + self.name)
        self.into_room = Vector((-ox, oz, 0))
        self.along = Vector((-ax, az, 0))

    def mesh(self, shift=0.0, along=0.0):
        return world_mesh(self.obj, self.matrix, self.into_room * shift + self.along * along)

    def tree(self, shift=0.0, along=0.0):
        verts, polys = self.mesh(shift, along)
        return verts, polys, BVHTree.FromPolygons(verts, polys)


def visible_hits(pairs, verts, polys, wells, floor, side=0):
    kept = []
    for pair in pairs:
        c = centre(verts, polys[pair[side]])
        if not in_wells(c, wells):
            kept.append(c)
    return kept


def wall_clip(p, wall_tree, wells, floor):
    """None when the piece stands clear of the walls; else (triangles, their middle, how far the
    piece would have to move into the room to be clear: None when over 30 cm)."""
    verts, polys, tree = p.tree(LIFT)
    hits = visible_hits(wall_tree.overlap(tree), verts, polys, wells, floor, side=1)
    if not hits:
        return None
    depth = None
    for step in range(1, 60):
        shift = LIFT + step * 0.005
        verts2, polys2, tree2 = p.tree(shift)
        if not visible_hits(wall_tree.overlap(tree2), verts2, polys2, wells, floor, side=1):
            depth = shift - LIFT
            break
    if depth is not None and depth <= TOLERATED:
        return None
    return len(hits), sum(hits, Vector()) / len(hits), depth


def stacked(pa, pb):
    """A box on the one below it is one place, not an overlap."""
    return abs(pa.spot["rise"] - pb.spot["rise"]) > 0.01 and abs(pa.spot["x"] - pb.spot["x"]) < 0.02         and abs(pa.spot["z"] - pb.spot["z"]) < 0.02


def pair_clash(pa, pb, wells, floor, tolerated=TOLERATED):
    """None when the two pieces stand clear; else (triangles, their middle, how far apart along the
    first piece's wall they would have to be: None when a lot)."""
    va, poa, ta = pa.tree()
    vb, pob, tb = pb.tree()
    hits = visible_hits(ta.overlap(tb), va, poa, wells, floor, side=0)
    if not hits:
        return None
    # two pieces whose faces meet and sink into each other by a few millimetres are in contact
    for step in range(1, int(TOLERATED / 0.0005) + 1):
        s = step * 0.0005
        if not pa.tree(shift=s)[2].overlap(tb) or not pa.tree(shift=-s)[2].overlap(tb):
            return None
    gap = None
    for step in range(1, 80):
        s = step * 0.005
        if not pa.tree(along=s)[2].overlap(tb) or not pa.tree(along=-s)[2].overlap(tb):
            gap = s
            break
    if gap is not None and gap <= tolerated:
        return None
    return len(hits), sum(hits, Vector()) / len(hits), gap


def rectangle(spot, name):
    """The footprint rectangle MELens.Parts uses for a piece at a spot: x0, x1, z0, z1, and its
    vertical band."""
    k = KIT[name]
    (ax, az), (ox, oz) = WALLS[spot["wall"]]
    xs, zs = [], []
    for a in (-k["width"] / 2, k["width"] / 2):
        for d in (0, k["depth"]):
            xs.append(spot["x"] + ax * a + ox * d)
            zs.append(spot["z"] + az * a + oz * d)
    return min(xs), max(xs), min(zs), max(zs), spot["rise"], spot["rise"] + k["height"]


CLEARANCE = 0.005            # MELens.Parts.CLEARANCE: what the game's placement rule lets two pieces share


def rectangles_meet(a, b):
    """MELens.Parts.roomFor: whether two pieces' floor rectangles and height bands overlap."""
    return min(a[1], b[1]) - max(a[0], b[0]) > CLEARANCE and min(a[3], b[3]) - max(a[2], b[2]) > CLEARANCE         and min(a[5], b[5]) - max(a[4], b[4]) > CLEARANCE


def swap_audit(spots, floor, wells, wall_tree):
    """Every piece the game lets you put in each spot: against the walls, and against every piece
    the other spots could hold. Reports what clips and whether the footprint rectangles would
    have kept the two apart."""
    options = []
    for i, spot in enumerate(spots):
        options.append([Piece(i + 1, dict(spot, default=name), floor) for name in sorted(KIT) if fits(spot, name)])
    issues, tried, uncaught = [], 0, 0
    for row in options:
        for p in row:
            tried += 1
            clip = wall_clip(p, wall_tree, wells, floor)
            if clip:
                issues.append("spot %d could hold a %s, which clips the %s wall: %d triangles at %s, %s deep" % (
                    p.index, p.name, p.spot["wall"], clip[0], passenger(clip[1], floor),
                    ("%.0f mm" % (clip[2] * 1000)) if clip[2] is not None else "over 30 cm"))
    for a in range(len(options)):
        for b in range(a + 1, len(options)):
            bad, caught = [], 0
            for pa in options[a]:
                for pb in options[b]:
                    tried += 1
                    if stacked(pa, pb):
                        continue
                    clash = pair_clash(pa, pb, wells, floor, SWAP_TOLERATED)
                    if clash:
                        met = rectangles_meet(rectangle(pa.spot, pa.name.replace("_r", "")),
                                              rectangle(pb.spot, pb.name.replace("_r", "")))
                        more = (" [%d triangles at %s, %s]" % (clash[0], passenger(clash[1], floor),
                                ("%.0f mm apart needed" % (clash[2] * 1000)) if clash[2] is not None else "a lot")) if DETAIL else ""
                        bad.append("%s+%s%s%s" % (pa.name, pb.name, "" if met else " (NOT caught by footprints)", more))
                        caught += 1 if met else 0
                        uncaught += 0 if met else 1
            if bad:
                issues.append("spots %d and %d, if they hold: %s" % (a + 1, b + 1, ", ".join(bad[:12])
                                                                   + (" ... %d more" % (len(bad) - 12) if len(bad) > 12 else "")))
    return issues, tried, uncaught


total = 0
for key in KEYS:
    spots, floor, wells = load_profile(key)
    walls = find("shell_%s_walls" % TEXTURE[key])
    wall_verts, wall_polys = world_mesh(walls, Matrix.Identity(4))
    # the wheel-well boxes are meant to be overlapped: the shader hides what is inside them
    wall_polys = [p for p in wall_polys if not in_wells(centre(wall_verts, p), wells, pad=0.02)]
    # Where the hull tucks in under the floor (shell config floorOutline) the floor follows it and the
    # walls slope up from its edge to the lowest ring, 0.3 up: a piece's bottom corners at a rounded end may
    # sink into that slope (they stand inside the hull: dev/piece_overhang.py checks), hidden at the wall's
    # foot. Only what the slope's top and the walls above it touch counts.
    shell_cfg_path = os.path.join(MEDIA, "..", "..", "..", "..", "tools-src", "blender", "cfg", "shell_%s.json" % key)
    slope_top = 0.0
    if os.path.exists(shell_cfg_path):
        with open(shell_cfg_path, encoding="utf-8") as handle:
            slope_top = SLOPE_TOP if json.load(handle).get("floorOutline") else 0.0
    if slope_top:
        wall_polys = [p for p in wall_polys if max(wall_verts[i].z for i in p) > floor + slope_top + 0.004]
    wall_tree = BVHTree.FromPolygons(wall_verts, wall_polys)
    pieces = [Piece(i + 1, s, floor) for i, s in enumerate(spots) if not s["empty"]]      # bare spots hold nothing
    issues = []
    for p in pieces:
        clip = wall_clip(p, wall_tree, wells, floor)
        if clip:
            issues.append("piece %d %-8s on the %-5s wall: %2d triangles at %s, %s deep" % (
                p.index, p.name, p.spot["wall"], clip[0], passenger(clip[1], floor),
                ("%.0f mm" % (clip[2] * 1000)) if clip[2] is not None else "over 30 cm"))
    for a in range(len(pieces)):
        for b in range(a + 1, len(pieces)):
            if stacked(pieces[a], pieces[b]):
                continue
            if rectangles_meet(rectangle(pieces[a].spot, pieces[a].spot["default"]),
                               rectangle(pieces[b].spot, pieces[b].spot["default"])):
                issues.append("piece %d %s and piece %d %s: their footprints overlap" % (
                    pieces[a].index, pieces[a].name, pieces[b].index, pieces[b].name))
            clash = pair_clash(pieces[a], pieces[b], wells, floor)
            if clash:
                issues.append("piece %d %s and piece %d %s: %2d triangles at %s, %s overlap" % (
                    pieces[a].index, pieces[a].name, pieces[b].index, pieces[b].name, clash[0],
                    passenger(clash[1], floor), ("%.0f mm" % (clash[2] * 1000)) if clash[2] is not None else "large"))
    summary = ""
    if SWAPS and not any(s["cargo"] for s in spots):
        more, tried, uncaught = swap_audit(spots, floor, wells, wall_tree)
        issues += more
        summary = " (%d swaps tried, %d clash not caught by footprints)" % (tried, uncaught)
    print("== %-14s %d pieces%s: %s" % (key, len(pieces), summary, "no clipping" if not issues else "%d problems" % len(issues)))
    for line in issues[:60]:
        print("   " + line)
    if len(issues) > 60:
        print("   ... and %d more" % (len(issues) - 60))
    total += len(issues)
print("CLIPAUDIT total problems: %d" % total)
sys.exit(1 if total else 0)
