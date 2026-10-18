"""Developer helper: look at the models of a Viewpoint model pack (Workshop 3810302175,
'6244 3D models for Viewpoint') without using or copying them: renders to a private
contact sheet in build/rv/dbg. Read-only on the pack.

    python dev/voxel_pack_preview.py jobs <pack voxel-studio dir> <jobs.json> <sheet[:count]> ...
    blender -b --factory-startup --python dev/voxel_pack_preview.py -- render <jobs.json> <outdir>
    python dev/voxel_pack_preview.py sheet <jobs.json> <outdir> <sheet.png> [columns]

A pack manifest line `bind.<tile sprite>=<model id>-<part>,<rot>,<x>,<y>,<z>,<scale>` gives a
vanilla tile a model; `model.obj` (Z up, tile units) sits in <id>/<variant>/.
"""
import glob
import json
import os
import sys


def read_binds(pack_dir):
    binds = {}
    for path in sorted(glob.glob(os.path.join(pack_dir, "package*.properties"))):
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.startswith("bind."):
                    continue
                sprite, _, value = line.strip()[5:].partition("=")
                head = value.split(",")[0]
                model, _, part = head.rpartition("-")
                binds[sprite] = (model, int(part) if part.isdigit() else 0, value)
    return binds


def model_file(pack_dir, model):
    base = os.path.join(pack_dir, model)
    variants = sorted(d for d in glob.glob(os.path.join(base, "*")) if os.path.isdir(d))
    variants.sort(key=lambda d: (0 if os.path.basename(d).startswith("r1") else 1, d))
    for variant in variants:
        obj = os.path.join(variant, "model.obj")
        if os.path.exists(obj):
            return obj
    return None


def build_jobs(pack_dir, out, specs):
    binds = read_binds(pack_dir)
    jobs, seen = [], set()
    for spec in specs:
        sheet, _, count = spec.partition(":")
        limit = int(count) if count else 16
        taken = 0
        names = sorted((s for s in binds if s.rsplit("_", 1)[0] == sheet), key=lambda s: int(s.rsplit("_", 1)[1]))
        for sprite in names:
            model, part, _ = binds[sprite]
            if model in seen:
                continue
            obj = model_file(pack_dir, model)
            if not obj:
                continue
            seen.add(model)
            jobs.append({"sprite": sprite, "model": model, "part": part, "obj": obj})
            taken += 1
            if taken >= limit:
                break
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(jobs, handle, indent=1)
    print("jobs:", len(jobs))


def render(jobs_path, outdir):
    import math
    import bpy
    from mathutils import Vector

    with open(jobs_path, encoding="utf-8") as handle:
        jobs = json.load(handle)
    os.makedirs(outdir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.film_transparent = False
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
    # the game's isometric angle: 30 degrees up, looking from the south-east
    cam.rotation_euler = (math.radians(60), 0.0, math.radians(45))
    report = []
    for index, job in enumerate(jobs):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(filepath=job["obj"], forward_axis="Y", up_axis="Z")
        objects = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        if not objects:
            continue
        lo = Vector((1e9, 1e9, 1e9))
        hi = Vector((-1e9, -1e9, -1e9))
        tris = 0
        for obj in objects:
            tris += sum(len(p.vertices) - 2 for p in obj.data.polygons)
            for corner in obj.bound_box:
                world = obj.matrix_world @ Vector(corner)
                lo = Vector(min(a, b) for a, b in zip(lo, world))
                hi = Vector(max(a, b) for a, b in zip(hi, world))
            for mat in obj.data.materials:
                if mat and mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type == "TEX_IMAGE":
                            node.interpolation = "Closest"
        centre = (lo + hi) / 2
        size = hi - lo
        radius = max(size.x, size.y, size.z, 0.2)
        forward = cam.rotation_euler.to_matrix() @ Vector((0, 0, 1))
        cam.location = centre + forward * 10
        cam_data.ortho_scale = radius * 1.7
        scene.render.filepath = os.path.join(outdir, "%03d.png" % index)
        bpy.ops.render.render(write_still=True)
        job["size"] = [round(v, 3) for v in size]
        job["tris"] = tris
        report.append("%03d %-34s %5d tris  %.2f x %.2f x %.2f" % (index, job["sprite"], tris, size.x, size.y, size.z))
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for image in list(bpy.data.images):
            if image.users == 0:
                bpy.data.images.remove(image)
    with open(jobs_path, "w", encoding="utf-8") as handle:
        json.dump(jobs, handle, indent=1)
    print("\n".join(report))


def sheet(jobs_path, outdir, out, columns=8):
    from PIL import Image, ImageDraw

    with open(jobs_path, encoding="utf-8") as handle:
        jobs = json.load(handle)
    cell = 200
    rows = (len(jobs) + columns - 1) // columns
    image = Image.new("RGB", (columns * cell, rows * (cell + 16)), (77, 79, 84))
    draw = ImageDraw.Draw(image)
    for index, job in enumerate(jobs):
        path = os.path.join(outdir, "%03d.png" % index)
        if not os.path.exists(path):
            continue
        tile = Image.open(path).convert("RGB").resize((cell, cell), Image.NEAREST)
        x, y = (index % columns) * cell, (index // columns) * (cell + 16)
        image.paste(tile, (x, y))
        label = job["sprite"].replace("furniture_", "f_").replace("appliances_", "a_").replace("fixtures_", "fx_")
        draw.text((x + 3, y + cell + 2), label[:30], fill=(235, 235, 235))
    image.save(out)
    print("saved", out, image.size)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    mode = args[0]
    if mode == "jobs":
        build_jobs(args[1], args[2], args[3:])
    elif mode == "render":
        render(args[1], args[2])
    elif mode == "sheet":
        sheet(args[1], args[2], args[3], int(args[4]) if len(args) > 4 else 8)
