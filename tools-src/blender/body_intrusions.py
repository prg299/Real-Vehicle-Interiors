# Blender (background) tool: which parts of KI5's body mesh stand inside the room?
#
#   blender -b --factory-startup --python body_intrusions.py -- <measure config.json> [min height above floor]
#
# The cutaway draws KI5's body below the cut, and ME: LENS' shell lines it on the inside.
# Anything the body carries inside that lining (hinge boxes, latches, a wheel arch's inner
# box, hooks) is drawn in front of the shell's white walls as a black object. This finds such
# parts: the body mesh is split into its connected pieces, and each piece whose middle lies
# inside the room's outline (from the measurement, at the piece's height, and further from the
# wall than a margin) is listed with its size and place in passenger space (tiles; x to the
# vehicle's left, y up, z to the front). KI5's mesh is only measured, never copied.
import json
import math
import sys

import bmesh
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
with open(args[0], "r", encoding="utf-8-sig") as handle:
    cfg = json.load(handle)
MIN_ABOVE_FLOOR = float(args[1]) if len(args) > 1 else 0.0
with open(cfg["out"], "r", encoding="utf-8") as handle:
    measure = json.load(handle)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=cfg["fbx"])
m = cfg.get("map", {"sx": -90, "sy": 90, "sz": 90})


def to_passenger(v):
    return (v.x * m["sx"], v.z * m["sy"], v.y * m["sz"])


floor = measure["floor"]
outlines = measure["outlines"]


def outline_polygon(height):
    """The measured inside outline nearest to `height`: a list of (x, z)."""
    keys = sorted(outlines, key=lambda k: abs(float(k) - height))
    return [tuple(p) for p in outlines[keys[0]]]


def inside(point, polygon):
    x, z = point
    hit = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, zi = polygon[i]
        xj, zj = polygon[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi:
            hit = not hit
        j = i
    return hit


def wall_distance(point, polygon):
    x, z = point
    best = 1e9
    j = len(polygon) - 1
    for i in range(len(polygon)):
        ax, az = polygon[j]
        bx, bz = polygon[i]
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz + 1e-12)))
        best = min(best, math.hypot(x - (ax + t * dx), z - (az + t * dz)))
        j = i
    return best


obj = bpy.data.objects[cfg["body"]]
depsgraph = bpy.context.evaluated_depsgraph_get()
mesh = obj.evaluated_get(depsgraph).to_mesh()
bm = bmesh.new()
bm.from_mesh(mesh)
bm.verts.ensure_lookup_table()
seen = set()
pieces = []
for v in bm.verts:
    if v.index in seen:
        continue
    stack, group = [v], []
    seen.add(v.index)
    while stack:
        cur = stack.pop()
        group.append(cur)
        for e in cur.link_edges:
            other = e.other_vert(cur)
            if other.index not in seen:
                seen.add(other.index)
                stack.append(other)
    pieces.append(group)
print("BODYPIECES %d pieces in %s" % (len(pieces), cfg["body"]))
rows = []
for group in pieces:
    ps = [to_passenger(obj.matrix_world @ v.co) for v in group]
    lo = [min(p[i] for p in ps) for i in range(3)]
    hi = [max(p[i] for p in ps) for i in range(3)]
    mid = [(lo[i] + hi[i]) / 2 for i in range(3)]
    height = mid[1]
    polygon = outline_polygon(height)
    if not inside((mid[0], mid[2]), polygon):
        continue
    if lo[1] < floor + MIN_ABOVE_FLOOR or hi[1] > floor + 1.6:
        continue
    d = wall_distance((mid[0], mid[2]), polygon)
    rows.append((d, len(group), lo, hi))
rows.sort(key=lambda r: -r[0])
print("INSIDE the room's outline, furthest from the wall first (floor %.2f):" % floor)
for d, n, lo, hi in rows[:40]:
    print("BODYPIECE wall %.2f verts %4d  x %+.2f..%+.2f  above floor %.2f..%.2f  z %+.2f..%+.2f" % (
        d, n, lo[0], hi[0], lo[1] - floor, hi[1] - floor, lo[2], hi[2]))


# Vertices of the body that lie clearly inside the room: the hull's own inner surface lies on
# the outline, so a vertex further in than MARGIN is something the body carries into the room.
MARGIN = float(args[2]) if len(args) > 2 else 0.035
stray = []
for v in bm.verts:
    px, py, pz = to_passenger(obj.matrix_world @ v.co)
    if py < floor - 0.05 or py > floor + 1.5:
        continue
    polygon = outline_polygon(py)
    if inside((px, pz), polygon) and wall_distance((px, pz), polygon) > MARGIN:
        stray.append((px, py, pz))
print("BODYSTRAY %d vertices further in than %.3f" % (len(stray), MARGIN))
clusters = []
for p in stray:
    for c in clusters:
        if abs(c["x"] - p[0]) < 0.15 and abs(c["y"] - p[1]) < 0.15 and abs(c["z"] - p[2]) < 0.15:
            c["pts"].append(p)
            c["x"], c["y"], c["z"] = [sum(q[i] for q in c["pts"]) / len(c["pts"]) for i in range(3)]
            break
    else:
        clusters.append({"x": p[0], "y": p[1], "z": p[2], "pts": [p]})
for c in sorted(clusters, key=lambda c: -len(c["pts"]))[:30]:
    xs = [q[0] for q in c["pts"]]
    ys = [q[1] - floor for q in c["pts"]]
    zs = [q[2] for q in c["pts"]]
    print("BODYSTRAYCLUSTER n=%3d  x %+.2f..%+.2f  above floor %.2f..%.2f  z %+.2f..%+.2f" % (
        len(c["pts"]), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
