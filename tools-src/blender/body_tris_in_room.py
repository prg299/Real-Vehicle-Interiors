# Blender (background) tool: the triangles of KI5's body mesh that lie inside ME: LENS' room
# outline (seen from above) within a height window above the floor: what the cutaway's body
# clip would remove. Prints each triangle's centre, normal, area and piece in passenger space
# (tiles; x to the vehicle's left, y up, z to the front), so the hull's own tucked-in skin
# (normals pointing outwards/down) can be told from details standing in the room.
#
#   blender -b --factory-startup --python body_tris_in_room.py -- <measure config.json> <media folder> <shell key> [min above floor] [max above floor]
import json
import math
import os
import sys

import bmesh
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
with open(args[0], "r", encoding="utf-8-sig") as handle:
    cfg = json.load(handle)
media, key = os.path.abspath(args[1]), args[2]
lo_h = float(args[3]) if len(args) > 3 else 0.012
hi_h = float(args[4]) if len(args) > 4 else 0.30
with open(cfg["out"], "r", encoding="utf-8") as handle:
    measure = json.load(handle)
floor = measure["floor"]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(media, "models_X", "vehicles", "MELens_Shells.fbx"))
shell_floor = [o for o in bpy.data.objects if o.name.split(".")[0] == "shell_%s_floor" % key][0]
bm = bmesh.new()
bm.from_mesh(shell_floor.data)
segments = []
for e in bm.edges:
    if len(e.link_faces) == 1:
        a, b = [shell_floor.matrix_world @ v.co for v in e.verts]
        segments.append(((-a.x, a.y), (-b.x, b.y)))        # passenger (x, z)


def inside(x, z):
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
mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
bmb = bmesh.new()
bmb.from_mesh(mesh)
bmb.verts.ensure_lookup_table()
bmb.faces.ensure_lookup_table()

# connected pieces
piece = {}
n_pieces = 0
for v in bmb.verts:
    if v.index in piece:
        continue
    stack = [v]
    piece[v.index] = n_pieces
    while stack:
        cur = stack.pop()
        for e in cur.link_edges:
            o = e.other_vert(cur)
            if o.index not in piece:
                piece[o.index] = n_pieces
                stack.append(o)
    n_pieces += 1


def to_p(v):
    w = obj.matrix_world @ v.co
    return (w.x * m["sx"], w.z * m["sy"], w.y * m["sz"])


rows = []
for f in bmb.faces:
    pts = [to_p(v) for v in f.verts]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    cz = sum(p[2] for p in pts) / len(pts)
    if cy < floor + lo_h or cy > floor + hi_h:
        continue
    if not inside(cx, cz):
        continue
    # normal in passenger space
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = pts[0], pts[1], pts[2]
    ux, uy, uz = x1 - x0, y1 - y0, z1 - z0
    vx, vy, vz = x2 - x0, y2 - y0, z2 - z0
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    nx, ny, nz = nx / ln, ny / ln, nz / ln
    # the mapping flips handedness (sx = -90): the normal's sign is arbitrary; report |.|
    rows.append((piece[f.verts[0].index], cx, cy - floor, cz, nx, ny, nz, f.calc_area() * 8100.0, boundary_distance(cx, cz)))

# per piece: the hull skin is the piece whose extent is the largest; any other piece with
# faces in the band is a detail standing in the room
def piece_box(faces):
    pts = [to_p(v) for f in faces for v in f.verts]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


by_piece = {}
for f in bmb.faces:
    by_piece.setdefault(piece[f.verts[0].index], []).append(f)
extents = {}
for pid, faces in by_piece.items():
    lo, hi = piece_box(faces)
    extents[pid] = (hi[0] - lo[0]) * (hi[2] - lo[2]) * max(hi[1] - lo[1], 0.05)
skin = max(extents, key=lambda k: extents[k])
print("BODYTRIS pieces %d, skin piece %d" % (len(by_piece), skin))
for pid in sorted(by_piece):
    if pid == skin:
        continue
    inband = [f for f in by_piece[pid]
              if floor + lo_h <= sum(to_p(v)[1] for v in f.verts) / len(f.verts) <= floor + hi_h
              and inside(sum(to_p(v)[0] for v in f.verts) / len(f.verts), sum(to_p(v)[2] for v in f.verts) / len(f.verts))]
    if not inband:
        continue
    lo, hi = piece_box(inband)
    flo, fhi = piece_box(by_piece[pid])
    print("BODYTRIPIECE %2d faces %3d in band of %3d  x %+.2f..%+.2f  above floor %.2f..%.2f  z %+.2f..%+.2f   (whole piece x %+.2f..%+.2f y %.2f..%.2f z %+.2f..%+.2f)" % (
        pid, len(inband), len(by_piece[pid]), lo[0], hi[0], lo[1] - floor, hi[1] - floor, lo[2], hi[2],
        flo[0], fhi[0], flo[1] - floor, fhi[1] - floor, flo[2], fhi[2]))
