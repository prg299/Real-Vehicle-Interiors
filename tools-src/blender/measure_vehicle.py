# Blender (background) tool: measure a KI5 vehicle for ME: LENS' inside shell and profile.
#
#   blender -b --factory-startup --python measure_vehicle.py -- <config.json>
#
# config: { "name", "fbx", "body": object, "interior": [objects], "prefix": [name
#           prefixes of the vehicle's own objects], "out": json path,
#           "map": {"sx": -90, "sy": 90, "sz": 90} (optional; KI5's scale 0.1 x 0.9),
#           "floor": height (optional; the floor's height when the rays find another) }
#
# Writes, in passenger space (tiles; x to the vehicle's left, y up, z to the front):
#   floor: the height most rays straight down along the middle meet first;
#   ceiling: the height the rays straight up meet first;
#   outlines: the body's inside outline at heights from the floor to the ceiling;
#   parts: the bounds of every object whose name starts with one of the prefixes.
# KI5's meshes are only measured here; ME: LENS models its own geometry from these numbers.
import json
import math
from pathlib import Path
import sys
from collections import Counter

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1:]
with open(args[0], "r", encoding="utf-8-sig") as handle:
    cfg = json.load(handle)

bpy.ops.wm.read_factory_settings(use_empty=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_vehicle_fbx import load as load_vehicle_fbx
load_vehicle_fbx(cfg["fbx"])
m = cfg.get("map", {"sx": -90, "sy": 90, "sz": 90})
if "modelScale" in cfg:
    body_obj = bpy.data.objects.get(cfg["body"])
    if body_obj is None:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        assert len(meshes) == 1, (cfg["name"], cfg["body"], [o.name for o in meshes])
        body_obj = meshes[0]
        cfg["body"] = body_obj.name
    size = body_obj.matrix_world.to_scale()
    assert max(size) - min(size) < 1e-5, "Non-uniform body import scale needs a dedicated mapping"
    factor = cfg["modelScale"] / size.z
    m = {"sx": -factor, "sy": factor, "sz": factor}
    cfg["mesh"] = {"scale": cfg["modelScale"], "lift": body_obj.matrix_world.to_translation().z / size.z}
depsgraph = bpy.context.evaluated_depsgraph_get()


def to_passenger(v):
    return (v.x * m["sx"], v.z * m["sy"], v.y * m["sz"])


def to_blender(px, py, pz):
    return Vector((px / m["sx"], pz / m["sz"], py / m["sy"]))


def world_mesh(name):
    obj = bpy.data.objects[name]
    mesh = obj.evaluated_get(depsgraph).to_mesh()
    verts = [obj.matrix_world @ v.co for v in mesh.vertices]
    return verts, [tuple(e.vertices) for e in mesh.edges], [tuple(p.vertices) for p in mesh.polygons]


def tree(names):
    verts, polys = [], []
    for name in names:
        if name not in bpy.data.objects:
            continue
        v, _, p = world_mesh(name)
        base = len(verts)
        verts.extend(v)
        polys.extend(tuple(i + base for i in poly) for poly in p)
    return BVHTree.FromPolygons(verts, polys) if polys else None


def bounds(name):
    verts, _, _ = world_mesh(name)
    ps = [to_passenger(v) for v in verts]
    lo = [min(p[i] for p in ps) for i in range(3)]
    hi = [max(p[i] for p in ps) for i in range(3)]
    return {"min": [round(v, 4) for v in lo], "max": [round(v, 4) for v in hi]}


def slice_segments(name, py):
    """Keep exact cross-section segments so embedded seats cannot shrink the body envelope."""
    verts, _, polys = world_mesh(name)
    pv = [to_passenger(v) for v in verts]
    segments = []
    for poly in polys:
        cuts = []
        for i in range(len(poly)):
            pa, pb = pv[poly[i]], pv[poly[(i + 1) % len(poly)]]
            if (pa[1] - py) * (pb[1] - py) > 0 or pa[1] == pb[1]:
                continue
            t = (py - pa[1]) / (pb[1] - pa[1])
            cuts.append((pa[0] + (pb[0] - pa[0]) * t, pa[2] + (pb[2] - pa[2]) * t))
        segments.extend([cuts[i], cuts[i + 1]] for i in range(0, len(cuts) - 1, 2))
    return segments


def slice_outline(name, py, samples=144, step=0.02):
    """Outline of the mesh at height py: for each direction from the centre, the
    closest point of the mesh's cross-section (the inside surface of the shell). Each
    face crossing the height is cut into a segment, sampled every `step` tiles, so a
    low-poly body still gives a point in every direction."""
    pts = []
    for (x0, z0), (x1, z1) in slice_segments(name, py):
        count = max(1, int(math.hypot(x1 - x0, z1 - z0) / step))
        for k in range(count + 1):
            t = k / count
            pts.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t))
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


body = cfg["body"]
body_bounds = bounds(body)
inside = tree(cfg.get("interior", []) + [body])

# floor and ceiling along the middle (x = 0), from mid-height
lo, hi = body_bounds["min"], body_bounds["max"]
mid = (lo[1] + hi[1]) / 2
floors, ceilings = [], []
sample_lo = max(lo[2], cfg["sampleZ"][0]) if "sampleZ" in cfg else lo[2]
sample_hi = min(hi[2], cfg["sampleZ"][1]) if "sampleZ" in cfg else hi[2]
for i in range(81):
    z = sample_lo + (sample_hi - sample_lo) * (0.05 + 0.9 * i / 80)
    for x in (-0.15, 0.0, 0.15):
        origin = to_blender(x, mid, z)
        down = inside.ray_cast(origin, Vector((0, 0, -1))) if inside else (None,)
        up = inside.ray_cast(origin, Vector((0, 0, 1))) if inside else (None,)
        if down[0] is not None:
            floors.append(round(to_passenger(down[0])[1], 2))
        if up[0] is not None:
            ceilings.append(round(to_passenger(up[0])[1], 2))
floor = Counter(floors).most_common(1)[0][0] if floors else lo[1]
ceiling = Counter(ceilings).most_common(1)[0][0] if ceilings else hi[1]
# a body whose rays meet something above its real floor (a bed, a counter) says where the floor is
if "floor" in cfg:
    floor = cfg["floor"]

result = {"name": cfg["name"], "floor": floor, "ceiling": ceiling, "body": body_bounds,
          "floorCounts": Counter(floors).most_common(6), "ceilingCounts": Counter(ceilings).most_common(6),
          "outlines": {}, "parts": {}}
if "mesh" in cfg:
    result["mesh"] = cfg["mesh"]
if cfg.get("fitEnvelope"):
    result["sections"] = {}
h = floor - 0.1
while h <= ceiling + 0.05:
    result["outlines"]["%.2f" % h] = slice_outline(body, h)
    if cfg.get("fitEnvelope"):
        result["sections"]["%.2f" % h] = slice_segments(body, h)
    h = round(h + 0.1, 4)
prefixes = cfg.get("prefix", [])
for obj in bpy.data.objects:
    if obj.type == "MESH" and any(obj.name.startswith(p) for p in prefixes):
        result["parts"][obj.name] = bounds(obj.name)
with open(cfg["out"], "w", encoding="utf-8") as handle:
    json.dump(result, handle, indent=1)
print("MEASURED %s floor %.2f ceiling %.2f (floor hits %s)" % (cfg["name"], floor, ceiling, result["floorCounts"][:3]))
for name, b in sorted(result["parts"].items()):
    print("PART %-34s x %6.2f..%-6.2f y %6.2f..%-6.2f z %6.2f..%-6.2f" % (name, b["min"][0], b["max"][0], b["min"][1], b["max"][1], b["min"][2], b["max"][2]))
