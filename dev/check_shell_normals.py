"""Developer helper: do the shell wall faces look into the room? For each wall object of
MELens_Shells.fbx, faces at each height band: how many face the shell's middle (inward)
and how many away. A wall wound the wrong way is culled when seen from inside.
    blender -b --factory-startup --python dev/check_shell_normals.py -- <MELens_Shells.fbx> [name-filter]
"""
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=args[0])
wanted = args[1] if len(args) > 1 else "_walls"
for obj in sorted(bpy.data.objects, key=lambda o: o.name):
    if obj.type != "MESH" or wanted not in obj.name:
        continue
    mesh = obj.data
    mesh.calc_normals_split() if hasattr(mesh, "calc_normals_split") else None
    verts = [obj.matrix_world @ v.co for v in mesh.vertices]
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    centre = (lo + hi) / 2
    bands = {}
    for poly in mesh.polygons:
        pc = obj.matrix_world @ poly.center
        n = obj.matrix_world.to_3x3() @ poly.normal
        if abs(n.z) > 0.7:
            kind = "horizontal"
        else:
            inward = Vector((centre.x - pc.x, centre.y - pc.y, 0.0))
            kind = "inward" if inward.dot(Vector((n.x, n.y, 0.0))) > 0 else "OUTWARD"
        band = round(pc.z, 1)
        bands.setdefault(band, {}).setdefault(kind, 0)
        bands[band][kind] += 1
    print("== %s: %d faces, bounds x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (
        obj.name, len(mesh.polygons), lo.x, hi.x, lo.y, hi.y, lo.z, hi.z))
    total = {}
    for band in sorted(bands):
        for kind, count in bands[band].items():
            total[kind] = total.get(kind, 0) + count
    print("   totals", total)
    for band in sorted(bands):
        print("   z %6.1f %s" % (band, bands[band]))
