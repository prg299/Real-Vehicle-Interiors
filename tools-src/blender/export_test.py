# Blender (background) calibration: export a known box to check how the game loads
# ME: LENS FBX files (units and axes).
#   blender -b --factory-startup --python export_test.py -- <out.fbx>
# The box spans x 0..1, y 0..2, z 0..3 (Blender units), so each axis is recognisable.
import sys

import bmesh
import bpy

out = sys.argv[sys.argv.index("--") + 1:][0]
bpy.ops.wm.read_factory_settings(use_empty=True)

mesh = bpy.data.meshes.new("testbox")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
for v in bm.verts:
    v.co.x = (v.co.x + 0.5) * 1.0
    v.co.y = (v.co.y + 0.5) * 2.0
    v.co.z = (v.co.z + 0.5) * 3.0
uv = bm.loops.layers.uv.new("UVMap")
for face in bm.faces:
    for loop in face.loops:
        loop[uv].uv = (0.05, 0.05)
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new("testbox", mesh)
bpy.context.scene.collection.objects.link(obj)

bpy.ops.export_scene.fbx(
    filepath=out,
    use_selection=False,
    object_types={"MESH"},
    axis_forward="-Z",
    axis_up="Y",
    apply_unit_scale=False,
    apply_scale_options="FBX_SCALE_NONE",
    global_scale=1.0,
    bake_space_transform=True,
    use_mesh_modifiers=True,
    mesh_smooth_type="FACE",
    add_leaf_bones=False,
)
print("EXPORTED", out)
