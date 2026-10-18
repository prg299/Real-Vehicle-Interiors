# Blender (background) helper: the object transforms of an FBX (location, rotation,
# scale, and the mesh's own vertex bounds before the transform), to see how the game's
# raw mesh space relates to Blender's world space for a vehicle model.
#   blender -b --factory-startup --python fbx_transforms.py -- <file.fbx> [name-filter]
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
    loc = obj.matrix_world.to_translation()
    rot = obj.matrix_world.to_euler()
    scl = obj.matrix_world.to_scale()
    vs = [v.co for v in obj.data.vertices]
    lo = [min(v[i] for v in vs) for i in range(3)]
    hi = [max(v[i] for v in vs) for i in range(3)]
    parent = obj.parent.name if obj.parent else "-"
    print("XF %-32s parent=%-10s loc=(%.6f, %.6f, %.6f) rot=(%.1f, %.1f, %.1f) scale=(%.6f, %.6f, %.6f) local min=(%.3f, %.3f, %.3f) max=(%.3f, %.3f, %.3f)" % (
        obj.name, parent, loc.x, loc.y, loc.z, *(r * 57.29578 for r in rot), scl.x, scl.y, scl.z, *lo, *hi))
