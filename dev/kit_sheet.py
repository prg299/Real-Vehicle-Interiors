"""Developer helper: a contact sheet of ME: LENS' furniture models, seen the way the pack previews of the
Viewpoint models are (dev/voxel_pack_preview.py): the game's isometric angle, flat lighting, one tile per
piece, for comparing the look.

    blender -b --factory-startup --python dev/kit_sheet.py -- <mod media folder> <out dir>

Renders <out dir>/<piece>.png (256 px each) from models_X/vehicles/MELens_RV.fbx with each piece's own
texture from textures/Vehicles, then dev/kit_sheet.py's second mode joins them:

    python dev/kit_sheet.py sheet <out dir> <sheet.png> [columns]
"""
import math
import os
import sys


def render(media, out):
    import bpy
    from mathutils import Vector

    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = 256
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "TEXTURE"
    shading.show_shadows = False
    shading.show_object_outline = False
    shading.show_cavity = False
    scene.world = bpy.data.worlds.new("w")
    scene.world.color = (0.30, 0.31, 0.33)
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.rotation_euler = (math.radians(60), 0.0, math.radians(45))      # from the south-east: a piece faces -y, so the camera sees its front and its right side

    bpy.ops.import_scene.fbx(filepath=os.path.join(media, "models_X", "vehicles", "MELens_RV.fbx"))
    objects = [o for o in bpy.data.objects if o.type == "MESH"]
    for obj in objects:
        obj.hide_render = True
    for obj in sorted(objects, key=lambda o: o.name):
        piece = obj.name.split(".")[0]
        if piece.startswith("rv_"):
            piece = piece[3:]
        path = os.path.join(media, "textures", "Vehicles", "MELensRV_%s.png" % piece)
        if not os.path.exists(path):
            continue
        image = bpy.data.images.load(path)
        mat = bpy.data.materials.new("m_" + piece)
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Closest"
        mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.hide_render = False
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        lo = Vector((min(c[i] for c in corners) for i in range(3)))
        hi = Vector((max(c[i] for c in corners) for i in range(3)))
        centre = (lo + hi) / 2
        radius = max((hi - lo).x, (hi - lo).y, (hi - lo).z, 0.3)
        forward = cam.rotation_euler.to_matrix() @ Vector((0, 0, 1))
        cam.location = centre + forward * 10
        cam_data.ortho_scale = radius * 1.7
        scene.render.filepath = os.path.join(out, "%s.png" % piece)
        bpy.ops.render.render(write_still=True)
        obj.hide_render = True


def sheet(out, path, columns=6):
    from PIL import Image, ImageDraw
    names = sorted(f[:-4] for f in os.listdir(out) if f.endswith(".png") and not f.startswith("sheet"))
    cell = 256
    rows = (len(names) + columns - 1) // columns
    image = Image.new("RGB", (columns * cell, rows * (cell + 16)), (77, 79, 84))
    draw = ImageDraw.Draw(image)
    for index, name in enumerate(names):
        tile = Image.open(os.path.join(out, name + ".png")).convert("RGB").resize((cell, cell), Image.NEAREST)
        x, y = (index % columns) * cell, (index // columns) * (cell + 16)
        image.paste(tile, (x, y))
        draw.text((x + 3, y + cell + 2), name, fill=(235, 235, 235))
    image.save(path)
    print("saved", path, image.size)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if args[0] == "sheet":
        sheet(args[1], args[2], int(args[3]) if len(args) > 3 else 6)
    else:
        render(os.path.abspath(args[0]), os.path.abspath(args[1]))
