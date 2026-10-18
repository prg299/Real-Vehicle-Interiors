"""Developer helper: do the surfaces MELens_Loose.lua declares for each piece lie on the piece?

    blender -b --factory-startup --python dev/surface_audit.py -- <mod media folder> [piece ...]

For every surface of L.SURFACES (a0..a1 along the piece from its middle, d0..d1 out from its wall, h above its
base) a grid of points inside it is tested against the real triangles of the piece in MELens_RV.fbx: a ray going
down from 5 cm above the height must hit within TOLERANCE of it (there is something to stand on, all over the
rectangle), and, where the surface declares `head`, a ray going up from just above the height must find nothing
nearer than that (the room for the things that stand there). Also: the rectangle lies inside the piece's footprint.
Prints a line per surface; the exit code is 1 when anything fails."""
import os
import re
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1:]
MEDIA = os.path.abspath(args[0])
ONLY = args[1:]
LUA = os.path.join(MEDIA, "lua", "shared")
TOLERANCE = 0.015     # a burner's grate stands 1 cm above the plate a pot is said to rest on
GRID = 5


def load_surfaces():
    text = open(os.path.join(LUA, "MELens_Loose.lua"), encoding="utf-8").read()
    start = text.index("L.SURFACES = {")
    depth, end = 0, start
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    block = text[start:end]
    surfaces, piece = {}, None
    entry = re.compile(r'\{ a0 = ([-\d.]+), a1 = ([-\d.]+), d0 = ([-\d.]+), d1 = ([-\d.]+), h = ([-\d.]+)'
                       r'(?:, head = ([-\d.]+))?, name = "(\w+)" \}')
    for line in block.splitlines()[1:]:
        m = re.match(r"\s{4}(\w+) = \{", line)
        if m:
            piece = m.group(1)
            surfaces.setdefault(piece, [])
        for e in entry.finditer(line):
            a0, a1, d0, d1, h = (float(e.group(i)) for i in range(1, 6))
            head = float(e.group(6)) if e.group(6) else None
            surfaces[piece].append({"a0": a0, "a1": a1, "d0": d0, "d1": d1, "h": h, "head": head, "name": e.group(7)})
    return surfaces


def load_kit():
    text = open(os.path.join(LUA, "MELens_RVKit.lua"), encoding="utf-8").read()
    kit = {}
    for m in re.finditer(r'(\w+) = \{ width = ([\d.]+), depth = ([\d.]+), height = ([\d.]+)', text):
        kit[m.group(1)] = {"width": float(m.group(2)), "depth": float(m.group(3)), "height": float(m.group(4))}
    return kit


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(MEDIA, "models_X", "vehicles", "MELens_RV.fbx"))
objects = {o.name.split(".")[0]: o for o in bpy.data.objects if o.type == "MESH"}
surfaces, kit = load_surfaces(), load_kit()
failures = 0
down, up = Vector((0, 0, -1)), Vector((0, 0, 1))

for piece, defs in surfaces.items():
    if ONLY and piece not in ONLY:
        continue
    obj = objects.get("rv_" + piece)
    if obj is None:
        print("FAIL  %-9s no model rv_%s" % (piece, piece))
        failures += 1
        continue
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    polys = [tuple(p.vertices) for p in obj.data.polygons]
    tree = BVHTree.FromPolygons(verts, polys)
    base = min(v.z for v in verts)
    size = kit[piece]
    for d in defs:
        problems = []
        if d["a0"] < -size["width"] / 2 - 1e-6 or d["a1"] > size["width"] / 2 + 1e-6 or d["d0"] < -1e-6 or d["d1"] > size["depth"] + 1e-6:
            problems.append("outside the footprint (%.2f x %.2f)" % (size["width"], size["depth"]))
        worst, ceiling = 0.0, None
        missing = 0
        for i in range(GRID):
            for j in range(GRID):
                a = d["a0"] + (d["a1"] - d["a0"]) * (i + 0.5) / GRID
                dd = d["d0"] + (d["d1"] - d["d0"]) * (j + 0.5) / GRID
                # the piece's own frame: x along it, its back edge at y = 0, the front at y = -depth
                x, y = a, -dd
                z = base + d["h"]
                hit = tree.ray_cast(Vector((x, y, z + 0.05)), down)
                if hit[0] is None:
                    missing += 1
                    continue
                off = hit[0].z - z
                worst = max(worst, abs(off))
                if abs(off) > TOLERANCE:
                    missing += 1
                    continue
                roof = tree.ray_cast(Vector((x, y, z + 0.002)), up)
                if roof[0] is not None:
                    room = roof[0].z - z
                    ceiling = room if ceiling is None else min(ceiling, room)
        if missing:
            problems.append("%d of %d points have nothing at h=%.3f (worst off by %.3f)" % (missing, GRID * GRID, d["h"], worst))
        if d["head"] is not None:
            if ceiling is not None and ceiling < d["head"] - 0.005:
                problems.append("the room above is %.3f, declared %.3f" % (ceiling, d["head"]))
            if ceiling is None:
                problems.append("declares head %.3f but nothing is above" % d["head"])
        status = "FAIL" if problems else "ok  "
        if problems:
            failures += 1
        print("%s  %-9s %-9s h=%.3f%s  %s" % (status, piece, d["name"], d["h"],
                                              ("  room %.3f" % ceiling) if ceiling is not None else "", "; ".join(problems)))

print("%s" % ("surface audit: all good" if not failures else "surface audit: %d failure(s)" % failures))
sys.exit(1 if failures else 0)
