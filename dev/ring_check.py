"""Developer helper: how far does each vehicle's room outline (the cutaway's clip polygon for KI5
body details, written with the walk grid) stand outside the shell's floor edge?

    blender -b --factory-startup --python dev/ring_check.py -- <mod media folder> <key> [<key> ...]
    (key: the shell texture key, e.g. scamp16)

Prints the corners whose distance to the floor's boundary exceeds 4 cm: where the outline bulges
(a door opening's frame) and so would clip the hull's own surface."""
import math
import os
import re
import sys

import bmesh
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
media = os.path.abspath(args[0])
keys = args[1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=os.path.join(media, "models_X", "vehicles", "MELens_Shells.fbx"))
WALKGRIDS = {"scamp16": "Scamp16", "scamp13": "Scamp13", "bambi16": "Bambi16", "airflyte": "Airflyte",
             "cloud22": "FlyingCloud22", "b700": "B700", "f700box": "F700box"}
for key in keys:
    floor_obj = [o for o in bpy.data.objects if o.name.split(".")[0] == "shell_%s_floor" % key][0]
    bm = bmesh.new()
    bm.from_mesh(floor_obj.data)
    segments = []
    for e in bm.edges:
        if len(e.link_faces) == 1:
            a, b = [floor_obj.matrix_world @ v.co for v in e.verts]
            segments.append(((-a.x, a.y), (-b.x, b.y)))

    def boundary_distance(x, z):
        best = 1e9
        for (ax, az), (bx, bz) in segments:
            dx, dz = bx - ax, bz - az
            t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz + 1e-12)))
            best = min(best, math.hypot(x - (ax + t * dx), z - (az + t * dz)))
        return best

    path = os.path.join(media, "lua", "shared", "MELens_WalkGrid_%s_Shell.lua" % WALKGRIDS[key])
    text = open(path, encoding="utf-8").read()
    ring = [(float(a), float(b)) for a, b in re.findall(r"\{ (-?[\d.]+), (-?[\d.]+) \}", text[text.index("RoomRings"):])]
    far = [(boundary_distance(x, z), x, z) for x, z in ring]
    far.sort(reverse=True)
    print("RING %s: %d corners, farthest from the floor edge: %s" % (
        key, len(ring), ", ".join("%.3f at (%.2f, %.2f)" % f for f in far[:6])))
