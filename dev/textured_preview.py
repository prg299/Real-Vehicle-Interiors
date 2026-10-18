"""Developer helper: what the inside looks like, in colour, without the game.

    blender -b --factory-startup --python dev/textured_preview.py -- <mod media folder> <out dir> [key ...] [--az 45,135,225,315]
    (key: FlyingCloud22 Bambi16 Airflyte Scamp13 Scamp16 B700 F700box; default: all)

A small software renderer of ME: LENS' own models only (the shell's floor and walls with their textures,
the default furniture with its palette), from the game's camera (an orthographic view looking down at 30
degrees from each of the given azimuths), with the walls cut the way the cutaway does: the walls facing
the camera down to 0.38 above the floor, the others to 0.83. Triangles are clipped at the cut, textures
sampled without filtering, and the form shading is a rough copy of the shader's (top faces light, side
faces a little darker). It is for judging colours and contrast (floor against walls against furniture) and
the silhouette of the rooms, not a picture of the game: no KI5 hull, no lamps, no daylight."""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
NEAR_CUT = 0.38
WALL_CUT = 0.83
ELEVATION = math.radians(30)
SCALE = 220

args = sys.argv[sys.argv.index("--") + 1:]
azimuths = [45, 135, 225, 315]
if "--az" in args:
    i = args.index("--az")
    azimuths = [int(a) for a in args[i + 1].split(",")]
    del args[i:i + 2]
out_dir = os.path.abspath(args[1])
os.makedirs(out_dir, exist_ok=True)
sys.argv = sys.argv[:sys.argv.index("--") + 1] + [args[0]] + args[2:]

source = open(os.path.join(HERE, "clip_audit.py"), encoding="utf-8").read()
head = source[:source.index("total = 0\nfor key in KEYS:")]
ns = {"__name__": "clip_audit_head"}
exec(compile(head, "clip_audit_head", "exec"), ns)
KEYS, MEDIA = ns["KEYS"], ns["MEDIA"]
Piece, load_profile, find, TEXTURE = ns["Piece"], ns["load_profile"], ns["find"], ns["TEXTURE"]

_images = {}


def texture(path):
    """The image's pixels as a (h, w, 3) float array, row 0 at the top."""
    if path not in _images:
        image = bpy.data.images.load(path)
        image.colorspace_settings.name = "Non-Color"       # the stored values as they are
        w, h = image.size
        px = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3]
        _images[path] = np.flipud(px)       # Blender stores the bottom row first
    return _images[path]


def triangles(obj, matrix, tex):
    """[(world verts (3), uvs (3), tex array)] of an object, fan-triangulated."""
    full = matrix @ obj.matrix_world
    mesh = obj.data
    uv = mesh.uv_layers.active.data if mesh.uv_layers.active else None
    out = []
    for poly in mesh.polygons:
        loops = list(poly.loop_indices)
        for k in range(1, len(loops) - 1):
            idx = (loops[0], loops[k], loops[k + 1])
            verts = [full @ mesh.vertices[mesh.loops[i].vertex_index].co for i in idx]
            uvs = [tuple(uv[i].uv) if uv else (0.5, 0.5) for i in idx]
            out.append((verts, uvs, tex))
    return out


def clip_below(tri, limit):
    """The part of a triangle (verts, uvs, tex) at or below z = limit, as 0-2 triangles."""
    verts, uvs, tex = tri
    poly = list(zip(verts, uvs))
    result = []
    for i in range(3):
        (a, ua), (b, ub) = poly[i], poly[(i + 1) % 3]
        a_in, b_in = a.z <= limit, b.z <= limit
        if a_in:
            result.append((a, ua))
        if a_in != b_in:
            t = (limit - a.z) / (b.z - a.z)
            result.append((a + (b - a) * t, (ua[0] + (ub[0] - ua[0]) * t, ua[1] + (ub[1] - ua[1]) * t)))
    if len(result) < 3:
        return []
    return [([result[0][0], result[k][0], result[k + 1][0]], [result[0][1], result[k][1], result[k + 1][1]], tex)
            for k in range(1, len(result) - 1)]


def facing(centre, bounds, toward):
    """melens_cutaway: how much a wall point looks at the camera (the direction from the body's axis to it)."""
    (lx, ly), (hx, hy) = bounds
    cx, cy = (lx + hx) / 2, (ly + hy) / 2
    halfx, halfy = (hx - lx) / 2, (hy - ly) / 2
    radius = min(halfx, halfy)
    ax, ay = halfx - radius, halfy - radius
    ox, oy = centre.x - cx, centre.y - cy
    fx, fy = ox - max(-ax, min(ax, ox)), oy - max(-ay, min(ay, oy))
    dist = math.hypot(fx, fy)
    if dist < 1e-4:
        return 0.0, 0.0
    return (fx * toward[0] + fy * toward[1]) / dist, dist


def render(tris, azimuth, floor, bounds, size_pad=12):
    c = Vector((math.cos(ELEVATION) * math.cos(azimuth), math.cos(ELEVATION) * math.sin(azimuth), math.sin(ELEVATION)))
    right = Vector((0, 0, 1)).cross(-c).normalized()
    up = (-c).cross(right).normalized()
    toward = (math.cos(azimuth), math.sin(azimuth))
    half = min((bounds[1][0] - bounds[0][0]) / 2, (bounds[1][1] - bounds[0][1]) / 2)
    drawn = []
    for kind, tri in tris:
        if kind == "wall":
            centre = sum(tri[0], Vector()) / 3
            f, dist = facing(centre, bounds, toward)
            near = f > 0.35 and dist > 0.35 * half
            drawn.extend(clip_below(tri, floor + (NEAR_CUT if near else WALL_CUT)))
        else:
            drawn.append(tri)
    allv = [v for t in drawn for v in t[0]]
    rs = [v.dot(right) for v in allv]
    us = [v.dot(up) for v in allv]
    ox, oy = -min(rs) * SCALE + size_pad, max(us) * SCALE + size_pad
    width = int((max(rs) - min(rs)) * SCALE + 2 * size_pad)
    height = int((max(us) - min(us)) * SCALE + 2 * size_pad)
    depth = np.full((height, width), -1e9)
    image = np.zeros((height, width, 3), dtype=np.float32)
    image[:] = (0.20, 0.30, 0.18)
    light = Vector((-0.35, -0.55, 0.76)).normalized()
    for verts, uvs, tex in drawn:
        n = (verts[1] - verts[0]).cross(verts[2] - verts[0])
        if n.length < 1e-12:
            continue
        n.normalize()
        if n.dot(c) <= 0:
            continue
        p = [(v.dot(right) * SCALE + ox, -v.dot(up) * SCALE + oy, v.dot(c)) for v in verts]
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
        z = w0 * az + w1 * bz + w2 * cz
        region_d = depth[y0:y1 + 1, x0:x1 + 1]
        take = inside & (z > region_d)
        if not take.any():
            continue
        region_d[take] = z[take]
        u = w0 * uvs[0][0] + w1 * uvs[1][0] + w2 * uvs[2][0]
        v = w0 * uvs[0][1] + w1 * uvs[1][1] + w2 * uvs[2][1]
        th, tw = tex.shape[:2]
        # (wrapped: the shells' tiles repeat; v runs bottom-up, the array's rows top-down)
        ix = np.floor((u % 1.0) * tw).astype(int).clip(0, tw - 1)
        iy = np.floor((1.0 - (v % 1.0)) * th).astype(int).clip(0, th - 1)
        colour = tex[iy, ix]
        shade = 0.78 + 0.22 * max(0.0, n.z) + 0.07 * (n.x * light.x + n.y * light.y) / 0.65
        region_i = image[y0:y1 + 1, x0:x1 + 1]
        region_i[take] = (colour * min(1.0, shade))[take]
    return image


for key in KEYS:
    spots, floor, wells = load_profile(key)
    tex = TEXTURE[key]
    floor_obj, walls_obj = find("shell_%s_floor" % tex), find("shell_%s_walls" % tex)
    textures = os.path.join(MEDIA, "textures", "Vehicles")
    tris = []
    for kind, obj, name in (("floor", floor_obj, "MELensShell_%s_floor.png" % tex), ("wall", walls_obj, "MELensShell_%s_walls.png" % tex)):
        for t in triangles(obj, Matrix.Identity(4), texture(os.path.join(textures, name))):
            tris.append((kind, t))
    for i, spot in enumerate(spots):
        if spot["empty"]:
            continue
        piece = Piece(i + 1, spot, floor)
        path = os.path.join(textures, "MELensRV_%s.png" % piece.name.replace("_r", ""))
        if not os.path.exists(path):
            path = os.path.join(textures, "MELens_RV.png")
        for t in triangles(piece.obj, piece.matrix, texture(path)):
            tris.append(("piece", t))
    fl = [v for kind, t in tris if kind == "floor" for v in t[0]]
    bounds = ((min(v.x for v in fl), min(v.y for v in fl)), (max(v.x for v in fl), max(v.y for v in fl)))
    for az in azimuths:
        image = render(tris, math.radians(az), floor, bounds)
        h, w = image.shape[:2]
        rgba = np.ones((h, w, 4), dtype=np.float32)
        rgba[:, :, :3] = np.clip(image, 0, 1)
        picture = bpy.data.images.new("%s_%d" % (key, az), w, h)
        picture.colorspace_settings.name = "Non-Color"
        picture.pixels = np.flipud(rgba).ravel().tolist()
        picture.filepath_raw = os.path.join(out_dir, "%s_%d.png" % (key, az))
        picture.file_format = "PNG"
        picture.save()
        bpy.data.images.remove(picture)
        print("TEXPREVIEW %s %d -> %s_%d.png (%dx%d)" % (key, az, key, az, w, h))
