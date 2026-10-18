"""Developer helper: render furniture pieces from all four corners at the game's camera angle, without the game, with
rv_kit.py's real materials baked into a scratch folder (what the game shows, minus its light). For checking a piece's
back and sides, which show whenever the wall facing the camera is cut low.

    blender -b --factory-startup --python dev/piece_views.py -- <out dir> <piece> [<piece> ...]

Writes <out dir>/<piece>_<corner>.png (400 px) for the corners 45, 135, 225 and 315 degrees: the piece faces -y (its
front), so 45 sees its front and right side, 135 its back and right side, 225 its back and left, 315 front and left.
dev/piece_views.py's output is joined by dev/piece_views_sheet.py."""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.environ.get("MELENS_KIT") or os.path.join(HERE, "..", "tools-src", "blender", "rv_kit.py")     # MELENS_KIT: another copy of the kit, to compare
args = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(args[0])
names = args[1:]
os.makedirs(out, exist_ok=True)
sys.argv = [sys.argv[0], "--", os.path.join(out, "baked")]
source = open(KIT, encoding="utf-8").read().rstrip()
assert source.endswith("main()")
kit = {"__name__": "rv_kit", "__file__": os.path.abspath(KIT)}
exec(compile(source[:-len("main()")], KIT, "exec"), kit)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
PX = int(os.environ.get("MELENS_VIEW_PX", "400"))      # render size; dev/piece_views_sheet.py joins 400 px renders
scene.render.resolution_x = scene.render.resolution_y = PX
shading = scene.display.shading
shading.light = "FLAT"
shading.color_type = "TEXTURE"
shading.show_shadows = False
shading.show_object_outline = False
shading.show_cavity = False
scene.view_settings.view_transform = "Standard"
scene.world = bpy.data.worlds.new("w")
scene.world.color = (0.20, 0.20, 0.22)
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

for name in names:
    spec = kit["PIECES"][name]
    b = kit["Builder"]("rv_" + name)
    spec["build"](b)
    obj = b.finish()
    kit["check_extent"](name, obj, spec)
    for v in obj.data.vertices:
        v.co.y -= spec["depth"] / 2
    texture = os.path.join(out, "baked", "MELensRV_%s.png" % name)
    os.makedirs(os.path.dirname(texture), exist_ok=True)
    kit["bake_piece"](obj, texture, 512)
    mat = bpy.data.materials.new("show_" + name)
    mat.use_nodes = True
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(texture)
    node.interpolation = "Closest"
    mat.node_tree.links.new(node.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    mat.node_tree.nodes.active = node
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.material_index = 0
    for o in scene.objects:
        o.hide_render = o.type == "MESH" and o is not obj
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    centre = sum(corners, Vector()) / 8
    size = max(max(c[i] for c in corners) - min(c[i] for c in corners) for i in range(3))
    for yaw in (45, 135, 225, 315):
        cam.rotation_euler = (math.radians(60), 0.0, math.radians(yaw))
        cam.location = centre + cam.rotation_euler.to_matrix() @ Vector((0, 0, 1)) * 6
        cam.data.ortho_scale = max(1.2, size * 1.35)
        scene.render.filepath = os.path.join(out, "%s_%d.png" % (name, yaw))
        bpy.ops.render.render(write_still=True)
    obj.hide_render = True
    print("VIEWS", name, flush=True)
