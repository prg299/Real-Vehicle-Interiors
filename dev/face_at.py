"""Developer helper: which faces of a piece are drawn in a region of a dev/piece_views.py render? Builds and bakes the
piece, sets the same camera, projects every camera-facing face's centre to the image and lists the faces whose centre
falls inside the pixel box, with their normal, material and the baked texture colour under their centre.

    blender -b --factory-startup --python dev/face_at.py -- <piece> <yaw> <px> <x0> <y0> <x1> <y1>

(<px> is the render size used, <x0..y1> the pixel box with the origin at the top left, as in an image viewer.)"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, "..", "tools-src", "blender", "rv_kit.py")
piece, yaw, px = sys.argv[sys.argv.index("--") + 1], float(sys.argv[sys.argv.index("--") + 2]), int(sys.argv[sys.argv.index("--") + 3])
box = [float(v) for v in sys.argv[sys.argv.index("--") + 4:sys.argv.index("--") + 8]]
scratch = os.path.join(os.environ.get("TEMP", "."), "face_at_scratch")
os.makedirs(scratch, exist_ok=True)
sys.argv = [sys.argv[0], "--", scratch]
source = open(KIT, encoding="utf-8").read().rstrip()
kit = {"__name__": "rv_kit", "__file__": os.path.abspath(KIT)}
exec(compile(source[:-len("main()")], KIT, "exec"), kit)

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
spec = kit["PIECES"][piece]
b = kit["Builder"]("rv_" + piece)
spec["build"](b)
obj = b.finish()
for v in obj.data.vertices:
    v.co.y -= spec["depth"] / 2
image = kit["bake_piece"](obj, os.path.join(scratch, "MELensRV_%s.png" % piece), 512)
size = image.size[0]
pixels = image.pixels[:]
scene.render.resolution_x = scene.render.resolution_y = px
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
centre = sum(corners, Vector()) / 8
extent = max(max(c[i] for c in corners) - min(c[i] for c in corners) for i in range(3))
cam.rotation_euler = (math.radians(60), 0.0, math.radians(yaw))
cam.location = centre + cam.rotation_euler.to_matrix() @ Vector((0, 0, 1)) * 6
cam.data.ortho_scale = max(1.2, extent * 1.35)
bpy.context.view_layer.update()
toward = cam.rotation_euler.to_matrix() @ Vector((0, 0, 1))
uv = obj.data.uv_layers.active.data
found = []
for p in obj.data.polygons:
    if p.normal.dot(toward) <= 0.01:
        continue
    c = world_to_camera_view(scene, cam, obj.matrix_world @ p.center)
    sx, sy = c.x * px, (1.0 - c.y) * px
    if box[0] <= sx <= box[2] and box[1] <= sy <= box[3]:
        us = [uv[i].uv for i in p.loop_indices]
        cu, cv = sum(u[0] for u in us) / len(us), sum(u[1] for u in us) / len(us)
        x, y = min(size - 1, int(cu * size)), min(size - 1, int(cv * size))
        i = (y * size + x) * 4
        found.append((p, (pixels[i], pixels[i + 1], pixels[i + 2]), (cu, cv), (sx, sy)))
print("FACES in the box:", len(found))
for p, colour, uvc, s in sorted(found, key=lambda t: -t[0].area):
    print("  face %4d centre (%.3f %.3f %.3f) normal (%+.2f %+.2f %+.2f) area %6.1f cm2 %-10s texel (%.2f %.2f %.2f) uv (%.3f %.3f) screen (%.0f %.0f)" % (
        p.index, p.center.x, p.center.y, p.center.z, p.normal.x, p.normal.y, p.normal.z, p.area * 1e4,
        kit["MATERIAL_NAMES"][p.material_index], colour[0], colour[1], colour[2], uvc[0], uvc[1], s[0], s[1]))
