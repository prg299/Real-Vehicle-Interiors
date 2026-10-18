"""Developer helper: does the shell's floor stick out of KI5's hull?

    blender -b --factory-startup --python dev/floor_overhang.py -- <mod media folder> <measure cfg> <shell key> [<measure cfg> <shell key> ...]
    (shell key: the shell texture key, e.g. scamp16; measure cfg: tools-src/blender/cfg/measure_Scamp16.json)

The floor is a flat polygon at floor height. Where KI5's hull tucks in under the floor (a trailer's
end bevels, the lower skin of the long sides), a polygon that follows the hull's inner outline from
a little above the floor reaches past the hull's outer skin at floor height, and its planks show
under the black hull as a tan strip. For each floor corner this casts a ray from outside, at a few
heights just above the floor, onto KI5's body and prints how far the corner is beyond the first
surface it meets (positive: sticking out). KI5's mesh is only measured, never copied."""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1:]
media = os.path.abspath(args[0])
pairs = [(args[i], args[i + 1]) for i in range(1, len(args) - 1, 2)]
HEIGHTS = (0.004, 0.03, 0.06, 0.10)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(media, "models_X", "vehicles", "MELens_Shells.fbx"))
shell_objects = {o.name.split(".")[0]: o for o in bpy.data.objects if o.type == "MESH"}

for cfg_path, key in pairs:
    cfg = json.load(open(cfg_path, encoding="utf-8-sig"))
    floor_obj = shell_objects["shell_%s_floor" % key]
    bm = bmesh.new()
    bm.from_mesh(floor_obj.data)
    # the shell's own floor height (a spec may override the measured one)
    bm.verts.ensure_lookup_table()
    floor_y = (floor_obj.matrix_world @ bm.verts[0].co).z
    boundary = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            for v in e.verts:
                w = floor_obj.matrix_world @ v.co
                p = (-w.x, w.y)                       # passenger (x, z)
                if all(math.hypot(p[0] - q[0], p[1] - q[1]) > 1e-4 for q in boundary):
                    boundary.append(p)
    cx = sum(p[0] for p in boundary) / len(boundary)
    cz = sum(p[1] for p in boundary) / len(boundary)

    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=cfg["fbx"])
    m = cfg.get("map", {"sx": -90, "sy": 90, "sz": 90})
    body = bpy.data.objects[cfg["body"]]
    mesh = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    verts, polys = [], [tuple(p.vertices) for p in mesh.polygons]
    for v in mesh.vertices:
        w = body.matrix_world @ v.co
        # passenger (px, py, pz) -> tree space (px, pz, py): x, z along the floor, y up
        verts.append(Vector((w.x * m["sx"], w.y * m["sz"], w.z * m["sy"])))
    tree = BVHTree.FromPolygons(verts, polys)
    lowest = min(v.z for v in verts)

    rows = []
    for (bx, bz) in boundary:
        dx, dz = bx - cx, bz - cz
        r_poly = math.hypot(dx, dz)
        ux, uz = dx / r_poly, dz / r_poly
        entry = {"x": bx, "z": bz, "r": r_poly, "over": []}
        for h in HEIGHTS:
            y = floor_y + h
            origin = Vector((cx + ux * (r_poly + 1.2), cz + uz * (r_poly + 1.2), y))
            hit = tree.ray_cast(origin, Vector((-ux, -uz, 0.0)), 2.4)
            if hit[0] is None:
                entry["over"].append(None)
            else:
                r_outer = math.hypot(hit[0].x - cx, hit[0].y - cz)
                entry["over"].append(r_poly - r_outer)
        rows.append(entry)
    print("FLOOROVER %s: floor %.2f, body's lowest point %.3f below it (%d floor corners)" % (
        key, floor_y, floor_y - lowest, len(rows)))
    for i, h in enumerate(HEIGHTS):
        vals = [(r["over"][i], r) for r in rows if r["over"][i] is not None]
        if not vals:
            print("FLOOROVER   at +%.3f: the hull is not met" % h)
            continue
        worst = max(vals, key=lambda t: t[0])
        many = sum(1 for v, _ in vals if v > 0.01)
        print("FLOOROVER   at +%.3f above the floor: floor corner beyond the skin by up to %+.3f (at x %+.2f z %+.2f); %d of %d corners over 1 cm" % (
            h, worst[0], worst[1]["x"], worst[1]["z"], many, len(vals)))
    for obj in set(bpy.data.objects) - before:
        bpy.data.objects.remove(obj, do_unlink=True)
