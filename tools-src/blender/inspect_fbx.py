# Blender (background) helper: list the objects of an FBX with their world bounds.
#   blender -b --factory-startup --python inspect_fbx.py -- <file.fbx> [name-filter]
import sys
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
path = args[0]
name_filter = args[1] if len(args) > 1 else ""

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=path)
for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
    if obj.type != "MESH" or name_filter not in obj.name:
        continue
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = [min(c[i] for c in corners) for i in range(3)]
    hi = [max(c[i] for c in corners) for i in range(3)]
    print("OBJ %-40s verts=%6d  min=(%.6f, %.6f, %.6f)  max=(%.6f, %.6f, %.6f)" % (
        obj.name, len(obj.data.vertices), lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]))
