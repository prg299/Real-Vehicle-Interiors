# Blender (background) tool: measure a KI5 camper shell for ME: LENS' own inside shell.
#
#   blender -b --factory-startup --python measure_shell.py -- <config.json>
#
# Slices the body mesh at several heights and writes the outline (passenger space,
# tiles) to JSON, together with the bounds of the door, window and wheel objects. KI5's
# mesh is only measured here; ME: LENS models its own geometry from these numbers.
import json
import math
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
with open(args[0], "r", encoding="utf-8-sig") as handle:
    cfg = json.load(handle)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=cfg["fbx"])
m = cfg["map"]

def to_passenger(v):
    return (v.x * m["sx"], v.z * m["sy"], v.y * m["sz"])

depsgraph = bpy.context.evaluated_depsgraph_get()

def world_mesh(name):
    obj = bpy.data.objects[name]
    mesh = obj.evaluated_get(depsgraph).to_mesh()
    return obj, [obj.matrix_world @ v.co for v in mesh.vertices], [tuple(e.vertices) for e in mesh.edges]

def slice_outline(name, py, samples=72):
    """Outline of the mesh at height py: for each direction from the centre, the
    closest crossing point (the inside surface of the shell)."""
    _, verts, edges = world_mesh(name)
    pts = []
    for a, b in edges:
        pa, pb = to_passenger(verts[a]), to_passenger(verts[b])
        if (pa[1] - py) * (pb[1] - py) > 0 or pa[1] == pb[1]:
            continue
        t = (py - pa[1]) / (pb[1] - pa[1])
        pts.append((pa[0] + (pb[0] - pa[0]) * t, pa[2] + (pb[2] - pa[2]) * t))
    if not pts:
        return []
    cx = sum(p[0] for p in pts) / len(pts)
    cz = sum(p[1] for p in pts) / len(pts)
    best = {}
    for x, z in pts:
        angle = math.atan2(z - cz, x - cx)
        k = int((angle + math.pi) / (2 * math.pi) * samples) % samples
        d = (x - cx) ** 2 + (z - cz) ** 2
        if k not in best or d < best[k][0]:
            best[k] = (d, x, z)
    return [[round(best[k][1], 4), round(best[k][2], 4)] for k in sorted(best)]

def bounds(name):
    _, verts, _ = world_mesh(name)
    ps = [to_passenger(v) for v in verts]
    lo = [min(p[i] for p in ps) for i in range(3)]
    hi = [max(p[i] for p in ps) for i in range(3)]
    return {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi]}

result = {"name": cfg["name"], "outlines": {}, "parts": {}}
for py in cfg["heights"]:
    result["outlines"]["%.2f" % py] = slice_outline(cfg["body"], py)
for name in cfg.get("parts", []):
    if name in bpy.data.objects:
        result["parts"][name] = bounds(name)
with open(cfg["out"], "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=1)
print("MEASURED", cfg["name"], "->", cfg["out"])
for name, b in result["parts"].items():
    print("PART %-28s x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f" % (name, b["min"][0], b["max"][0], b["min"][1], b["max"][1], b["min"][2], b["max"][2]))
for py, outline in result["outlines"].items():
    xs = [p[0] for p in outline]
    zs = [p[1] for p in outline]
    if outline:
        print("OUTLINE y=%s: %d points, x %.2f..%.2f, z %.2f..%.2f" % (py, len(outline), min(xs), max(xs), min(zs), max(zs)))
