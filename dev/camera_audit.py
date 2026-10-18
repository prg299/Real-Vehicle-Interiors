"""Developer helper: what of ME: LENS' can the game's camera see in front of KI5's hull, from each side?

    blender -b --factory-startup --python dev/camera_audit.py -- <mod media folder> [key ...] [--out <folder>]
    (key: FlyingCloud22 Bambi16 Airflyte Scamp13 Scamp16 B700 F700box; default: all)

A small z-buffer renderer of the cutaway as the game draws it, without the game: KI5's hull (single sided:
its faces that look at the camera), cut down like the game's walls (the walls facing the camera to 0.38
above the floor, the others to 0.83), and ME: LENS' shell (floor, walls, the wheel wells' boxes) and the
default furniture. From each of the four camera directions (the camera never turns, the vehicle does)
the camera looks down at 30 degrees. What the hull's skin covers from the camera is not seen: anything of
ours drawn IN FRONT of the skin where the skin is drawn sticks out past it (a floor's edge past the hull's
bottom, a wheel well's plate across the tyre). Those pixels are reported per object with where they are
(passenger space), and with --out written as pictures: the hull in grey, ours where it is fine in
colour, what sticks out in magenta.

The cutaway shaders' rules are restated here in simple form (see melens_cutaway_*.frag): a fragment of a
wall that faces the camera by more than 0.35 is cut at the near height, the furniture and the floor are
not cut, a wheel well's box on the camera's side is cut to the floor. It is a check for the things
that stick out, not a picture of the game. Exit code 1 when anything sticks out."""
import json
import math
import os
import re
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
MEASURE = {"FlyingCloud22": "measure_FlyingCloud22.json", "Bambi16": "measure_Bambi16.json", "Airflyte": "measure_Airflyte.json",
           "Scamp13": "measure_Scamp13.json", "Scamp16": "measure_Scamp16.json", "B700": "measure_B700school.json",
           "F700box": "measure_F700box.json"}
NEAR_CUT = 0.38          # walls facing the camera: cut to this above the floor
WALL_CUT = 0.83          # the other walls (the Medium wall height)
WELL_CUT = 0.03          # a wheel well's box on the camera's side
ELEVATION = math.radians(30)
SCALE = 240              # pixels per tile
TOLERANCE = 0.006        # how much closer to the camera than the skin counts as in front of it (tiles)
MIN_PIXELS = 6           # fewer than this many pixels in a place is noise

args = sys.argv[sys.argv.index("--") + 1:]
out_dir = None
if "--out" in args:
    i = args.index("--out")
    out_dir = os.path.abspath(args[i + 1])
    del args[i:i + 2]
    os.makedirs(out_dir, exist_ok=True)
sys.argv = sys.argv[:sys.argv.index("--") + 1] + args

source = open(os.path.join(HERE, "clip_audit.py"), encoding="utf-8").read()
head = source[:source.index("total = 0\nfor key in KEYS:")]
ns = {"__name__": "clip_audit_head"}
exec(compile(head, "clip_audit_head", "exec"), ns)
KEYS, MEDIA = ns["KEYS"], ns["MEDIA"]
Piece, load_profile, world_mesh, find, TEXTURE = ns["Piece"], ns["load_profile"], ns["world_mesh"], ns["find"], ns["TEXTURE"]


def load_room_ring(media, key):
    """MELens.RoomRings[...] of a vehicle in its walk grid file, as (x, y) in the shells' Blender plane, or None."""
    names = ["MELens.%s.shell" % key] + (["Base.Trailer54FlyingCloud22.shell"] if key == "FlyingCloud22" else [])
    folder = os.path.join(media, "lua", "shared")
    for name in sorted(os.listdir(folder)):
        if not (name.startswith("MELens_WalkGrid_") and name.endswith("_Shell.lua")):
            continue
        text = open(os.path.join(folder, name), encoding="utf-8").read()
        for ring_name in names:
            token = 'MELens.RoomRings["%s"] = {' % ring_name
            if token in text:
                start = text.index(token) + len(token)
                block = text[start:text.index("\n}", start)]
                return [(-float(a), float(b)) for a, b in re.findall(r"\{\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\}", block)]
    return None


def triangles_of(vertices, polygons):
    """Triangles (index triples) of polygons, fan-triangulated."""
    tris = []
    for poly in polygons:
        for k in range(1, len(poly) - 1):
            tris.append((poly[0], poly[k], poly[k + 1]))
    return tris


def camera_basis(azimuth):
    """Camera looking down at ELEVATION from the horizontal direction `azimuth` (radians, in the shells'
    Blender plane): returns (c, right, up) with c the unit vector from the scene to the camera."""
    c = Vector((math.cos(ELEVATION) * math.cos(azimuth), math.cos(ELEVATION) * math.sin(azimuth), math.sin(ELEVATION)))
    right = Vector((0, 0, 1)).cross(-c).normalized()       # screen right
    up = (-c).cross(right).normalized()                   # screen up
    return c, right, up


def rasterize(size, origin, project, tris, verts, ids, buffers_depth, buffers_id):
    """Draw triangles (index triples into `verts`, a list of 3D points) into the depth/id buffers."""
    height, width = buffers_depth.shape
    for tri, ident in zip(tris, ids):
        p = [project(verts[i]) for i in tri]
        xs = [q[0] for q in p]
        ys = [q[1] for q in p]
        x0, x1 = max(0, int(math.floor(min(xs)))), min(width - 1, int(math.ceil(max(xs))))
        y0, y1 = max(0, int(math.floor(min(ys)))), min(height - 1, int(math.ceil(max(ys))))
        if x0 > x1 or y0 > y1:
            continue
        (ax, ay, az), (bx, by, bz), (cx_, cy_, cz) = p
        denom = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
        if abs(denom) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((by - cy_) * (gx - cx_) + (cx_ - bx) * (gy - cy_)) / denom
        w1 = ((cy_ - ay) * (gx - cx_) + (ax - cx_) * (gy - cy_)) / denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        depth = w0 * az + w1 * bz + w2 * cz
        region_d = buffers_depth[y0:y1 + 1, x0:x1 + 1]
        region_i = buffers_id[y0:y1 + 1, x0:x1 + 1]
        take = inside & (depth > region_d)
        region_d[take] = depth[take]
        region_i[take] = ident


def facing_of(centre_xy, bounds, toward_camera_xy):
    """The shader's test: how much the point on the body's hull looks at the camera (the direction from the
    body's rounded-rectangle axis to the point, against the direction to the camera), and its distance."""
    (lx, ly), (hx, hy) = bounds
    cx, cy = (lx + hx) / 2, (ly + hy) / 2
    halfx, halfy = (hx - lx) / 2, (hy - ly) / 2
    radius = min(halfx, halfy)
    ax, ay = halfx - radius, halfy - radius
    ox, oy = centre_xy[0] - cx, centre_xy[1] - cy
    fx = ox - max(-ax, min(ax, ox))
    fy = oy - max(-ay, min(ay, oy))
    dist = math.hypot(fx, fy)
    if dist < 1e-4:
        return 0.0, 0.0, 0.0, 0.0
    return (fx * toward_camera_xy[0] + fy * toward_camera_xy[1]) / dist, dist, fx / dist, fy / dist


found = 0
for key in KEYS:
    cfg = json.load(open(os.path.join(ROOT, "tools-src", "blender", "cfg", MEASURE[key]), encoding="utf-8-sig"))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=cfg["fbx"])
    body = bpy.data.objects[cfg["body"]]
    mesh = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    hull_verts = [body.matrix_world @ v.co * 90.0 for v in mesh.vertices]
    hull_tris = triangles_of(hull_verts, [tuple(p.vertices) for p in mesh.polygons])
    spots, floor, wells = load_profile(key)
    # the cutaway's clip of KI5's body details inside the room (campers): faces that do not look down, inside
    # the lining's floor outline, 0.012-0.30 above the floor, are not drawn (MELens.RoomRings, from the walk grid)
    room_ring = load_room_ring(MEDIA, key)
    xs = [v.x for v in hull_verts]
    ys = [v.y for v in hull_verts]
    bounds = ((min(xs), min(ys)), (max(xs), max(ys)))

    # ours: (label, vertices, triangles, cut class) in the shells' Blender coordinates
    ours = []
    for label, obj in (("floor", find("shell_%s_floor" % TEXTURE[key])), ("walls", find("shell_%s_walls" % TEXTURE[key]))):
        vs, polys = world_mesh(obj, Matrix.Identity(4))
        ours.append((label, vs, triangles_of(vs, polys), label))
    for i, spot in enumerate(spots):
        if spot["empty"]:
            continue
        piece = Piece(i + 1, spot, floor)
        vs, polys = world_mesh(piece.obj, piece.matrix)
        ours.append(("piece %d %s" % (i + 1, piece.name), vs, triangles_of(vs, polys), "piece"))

    def inside_ring(x, y):
        inside = False
        j = len(room_ring) - 1
        for i in range(len(room_ring)):
            (xi, yi), (xj, yj) = room_ring[i], room_ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        return inside

    def in_well_box(p):
        # passenger (x, y, z) -> Blender (-x, z, y); well boxes from the profile
        for w in wells:
            x0, x1 = sorted(-v for v in w["x"])
            z0, z1 = sorted(w["z"])
            if x0 - 0.02 <= p.x <= x1 + 0.02 and z0 - 0.02 <= p.y <= z1 + 0.02 and p.z <= w["y"][1] + 0.02:
                return True
        return False

    print("CAMERA == %s (floor %.2f)" % (key, floor))
    total_bad = 0
    for az_deg in (45, 135, 225, 315):
        azimuth = math.radians(az_deg)
        c, right, up = camera_basis(azimuth)
        toward = (math.cos(azimuth), math.sin(azimuth))

        def visible_tris(vs, tris, kind):
            """Triangles that face the camera and are not cut away; yields (triangle, normal)."""
            result = []
            for tri in tris:
                a, b, d = vs[tri[0]], vs[tri[1]], vs[tri[2]]
                n = (b - a).cross(d - a)
                if n.length < 1e-12:
                    continue
                n.normalize()
                centre = (a + b + d) / 3
                facing, dist, ux, uy = facing_of((centre.x, centre.y), bounds, toward)
                nearwall = dist > 0.35 * min((bounds[1][0] - bounds[0][0]) / 2, (bounds[1][1] - bounds[0][1]) / 2)
                near = facing > 0.35 and nearwall
                if kind == "hull":
                    # only the skin's outside on the camera's side hides things from the camera (the body has
                    # inside faces too, which ME: LENS' lining is drawn in front of), and only below the near cut
                    if not near or n.x * ux + n.y * uy <= 0.1 or min(v.z for v in (a, b, d)) - floor > NEAR_CUT - 0.02:
                        continue
                    if room_ring and 0.012 <= centre.z - floor <= 0.30 and n.z >= -0.1 and inside_ring(centre.x, centre.y):
                        continue
                elif kind == "walls":
                    cut = NEAR_CUT if near else WALL_CUT
                    if min(v.z for v in (a, b, d)) - floor > cut - 0.02:
                        continue
                    if near and in_well_box(centre) and centre.z - floor > WELL_CUT:
                        continue
                if kind == "piece" and in_well_box(centre):
                    continue        # the shader does not draw furniture inside a wheel well's box
                if n.dot(c) <= 0.0:
                    continue
                result.append((tri, n))
            return result

        def project(v):
            return (v.dot(right) * SCALE + ox, -v.dot(up) * SCALE + oy, v.dot(c))

        allv = hull_verts + [v for _, vs, _, _ in ours for v in vs]
        ox = -min(v.dot(right) for v in allv) * SCALE + 12
        oy = max(v.dot(up) for v in allv) * SCALE + 12
        width = int((max(v.dot(right) for v in allv) - min(v.dot(right) for v in allv)) * SCALE + 24)
        height = int((max(v.dot(up) for v in allv) - min(v.dot(up) for v in allv)) * SCALE + 24)
        hull_depth = np.full((height, width), -1e9)
        hull_id = np.zeros((height, width), dtype=np.int32)
        hull_visible = visible_tris(hull_verts, hull_tris, "hull")
        rasterize(SCALE, (ox, oy), project, [t for t, _ in hull_visible], hull_verts, [1] * len(hull_visible), hull_depth, hull_id)
        own_depth = np.full((height, width), -1e9)
        own_id = np.zeros((height, width), dtype=np.int32)
        centroids = {}
        for index, (label, vs, tris, kind) in enumerate(ours):
            shown = visible_tris(vs, tris, "walls" if kind == "walls" else kind)
            centroids[index] = [(vs[t[0]] + vs[t[1]] + vs[t[2]]) / 3 for t, _ in shown]
            rasterize(SCALE, (ox, oy), project, [t for t, _ in shown], vs,
                      [(index + 1) * 1000000 + k for k in range(len(shown))], own_depth, own_id)
        own_obj = own_id // 1000000
        # ours in front of the skin: the hull is drawn there and ours is closer to the camera
        front = (own_id > 0) & (hull_id > 0) & (own_depth > hull_depth + TOLERANCE)
        report = []
        for index, (label, vs, tris, kind) in enumerate(ours):
            mask = front & (own_obj == index + 1)
            count = int(mask.sum())
            if count >= MIN_PIXELS:
                yy, xx = np.nonzero(mask)
                # the flagged pixels' places: an orthographic camera, so a pixel and its depth give the point
                px = (xx + 0.5 - ox) / SCALE
                py = -(yy + 0.5 - oy) / SCALE
                depth = own_depth[yy, xx]
                pts = [right * a + up * b + c * d for a, b, d in zip(px.tolist(), py.tolist(), depth.tolist())]
                places = "x %+.2f..%+.2f z %+.2f..%+.2f y %.2f..%.2f above the floor" % (
                    -max(w.x for w in pts), -min(w.x for w in pts), min(w.y for w in pts), max(w.y for w in pts),
                    min(w.z for w in pts) - floor, max(w.z for w in pts) - floor)
                report.append((count, label, int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max()), places))
        for count, label, x0, y0, x1, y1, places in sorted(report, reverse=True):
            print("CAMERA   from %3d deg: %-16s %5d px in front of the skin (%s)" % (az_deg, label, count, places))
            total_bad += 1
        if out_dir:
            image = np.zeros((height, width, 3), dtype=np.float32)
            image[:] = (0.16, 0.27, 0.16)                      # grass
            image[hull_id > 0] = (0.27, 0.27, 0.31)            # KI5's hull
            colours = {"floor": (0.78, 0.63, 0.39), "walls": (0.90, 0.90, 0.88)}
            for index, (label, vs, tris, kind) in enumerate(ours):
                image[own_obj == index + 1] = colours.get(label, (0.75, 0.47, 0.24))
            image[(own_id > 0) & (hull_id > 0) & ~front] = (0.24, 0.24, 0.27)   # ours behind the skin: hidden by it
            image[front] = (1.0, 0.0, 1.0)                     # ours in front of the skin: sticks out
            rgba = np.ones((height, width, 4), dtype=np.float32)
            rgba[:, :, :3] = image
            picture = bpy.data.images.new("%s_%d" % (key, az_deg), width, height)
            picture.pixels = np.flipud(rgba).ravel().tolist()
            picture.filepath_raw = os.path.join(out_dir, "%s_%d.png" % (key, az_deg))
            picture.file_format = "PNG"
            picture.save()
            bpy.data.images.remove(picture)
    print("CAMERA   %s: %d places where ours sticks out in front of the skin" % (key, total_bad))
    found += total_bad
    for obj in set(bpy.data.objects) - before:
        bpy.data.objects.remove(obj, do_unlink=True)
print("CAMERAAUDIT places sticking out: %d" % found)
sys.exit(1 if found else 0)
