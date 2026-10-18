# Blender (background) tool: which parts of KI5's body mesh stand inside ME: LENS' room?
#
#   blender -b --factory-startup --python body_in_room.py -- <measure config.json> <media folder> <shell texture key> [max height above floor]
#
# The cutaway draws KI5's body up to the cut and the shell lines the inside of it. The body's
# own inner details (the A-frame tongue's arm tips at the front corners of a trailer, hinge
# blocks) that stand inside the lining show in front of the shell's white walls as black
# objects. This reports the body vertices that lie inside the baked shell floor's outline
# (seen from above) and above the floor, clustered, in passenger space (tiles; x to the
# vehicle's left, y up, z to the front). KI5's mesh is only measured here, never copied.
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
with open(args[0], "r", encoding="utf-8-sig") as handle:
    cfg = json.load(handle)
media, key = os.path.abspath(args[1]), args[2]
max_above = float(args[3]) if len(args) > 3 else 0.9
with open(cfg["out"], "r", encoding="utf-8") as handle:
    measure = json.load(handle)
floor = measure["floor"]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(media, "models_X", "vehicles", "MELens_Shells.fbx"))
shell_floor = [o for o in bpy.data.objects if o.name.split(".")[0] == "shell_%s_floor" % key][0]
# the shell floor's outline (seen from above): its boundary edges, in passenger space
bm = bmesh.new()
bm.from_mesh(shell_floor.data)
edges = [e for e in bm.edges if len(e.link_faces) == 1]
world = shell_floor.matrix_world


def passenger_of_shell(v):
    w = world @ v.co
    return (-w.x, w.z, w.y)          # shell world (-x, z, y) -> passenger (x, y, z)


segments = []
for e in edges:
    a, b = [passenger_of_shell(v) for v in e.verts]
    segments.append(((a[0], a[2]), (b[0], b[2])))
print("SHELLFLOOR boundary edges: %d" % len(segments))


def inside(x, z):
    """Even-odd test against the floor's boundary segments."""
    hit = False
    for (ax, az), (bx, bz) in segments:
        if (az > z) != (bz > z) and x < (bx - ax) * (z - az) / (bz - az) + ax:
            hit = not hit
    return hit


def boundary_distance(x, z):
    best = 1e9
    for (ax, az), (bx, bz) in segments:
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz + 1e-12)))
        best = min(best, math.hypot(x - (ax + t * dx), z - (az + t * dz)))
    return best


bpy.ops.import_scene.fbx(filepath=cfg["fbx"])
m = cfg.get("map", {"sx": -90, "sy": 90, "sz": 90})
obj = bpy.data.objects[cfg["body"]]
depsgraph = bpy.context.evaluated_depsgraph_get()
mesh = obj.evaluated_get(depsgraph).to_mesh()
points = []
for v in mesh.vertices:
    w = obj.matrix_world @ v.co
    px, py, pz = w.x * m["sx"], w.z * m["sy"], w.y * m["sz"]
    if py < floor + 0.015 or py > floor + max_above:
        continue
    if inside(px, pz) and boundary_distance(px, pz) > 0.004:
        points.append((px, py, pz, boundary_distance(px, pz)))
print("BODYINROOM %d vertices inside the room, above the floor (floor %.2f)" % (len(points), floor))
clusters = []
for p in points:
    for c in clusters:
        if abs(c["x"] - p[0]) < 0.12 and abs(c["y"] - p[1]) < 0.12 and abs(c["z"] - p[2]) < 0.12:
            c["pts"].append(p)
            c["x"], c["y"], c["z"] = [sum(q[i] for q in c["pts"]) / len(c["pts"]) for i in range(3)]
            break
    else:
        clusters.append({"x": p[0], "y": p[1], "z": p[2], "pts": [p]})
for c in sorted(clusters, key=lambda c: c["z"]):
    xs = [q[0] for q in c["pts"]]
    ys = [q[1] - floor for q in c["pts"]]
    zs = [q[2] for q in c["pts"]]
    ds = [q[3] for q in c["pts"]]
    print("BODYINROOMCLUSTER n=%3d  x %+.2f..%+.2f  above floor %.2f..%.2f  z %+.2f..%+.2f  inside the edge by %.3f..%.3f" % (
        len(c["pts"]), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), min(ds), max(ds)))

# how far the hull skin tucks in towards the floor: the widest vertex of the body at each height
# in the middle of the length (the skin itself, not the details inside)
print("BODYSECTION height above floor -> widest |x| over z -1.0..1.0 (vertices of the body)")
for step in range(0, 11):
    lo, hi = floor + 0.04 * step - 0.02, floor + 0.04 * step + 0.02
    xs = []
    for v in mesh.vertices:
        w = obj.matrix_world @ v.co
        px, py, pz = w.x * m["sx"], w.z * m["sy"], w.y * m["sz"]
        if lo <= py < hi and -1.0 <= pz <= 1.0:
            xs.append(abs(px))
    print("BODYSECTION  +%.2f  n=%3d  widest %s" % (0.04 * step, len(xs), "%.3f" % max(xs) if xs else "-"))
