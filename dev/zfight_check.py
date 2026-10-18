"""Developer helper: find faces of a furniture piece that lie in the same plane, face the same way and overlap, though they
belong to different boxes of the piece (rv_kit.py's Builder): in the game they fight for the depth buffer, and the one that
is occluded in the ambient-occlusion bake (a face inside the other box) shows through as a black patch.

    blender -b --factory-startup --python dev/zfight_check.py -- [<piece> ...]

Prints the pairs per piece with their positions (the piece's own space, metres) and a total."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, "..", "tools-src", "blender", "rv_kit.py")
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
sys.argv = [sys.argv[0], "--", os.path.join(os.environ.get("TEMP", "."), "zfight_scratch")]
source = open(KIT, encoding="utf-8").read().rstrip()
assert source.endswith("main()")
kit = {"__name__": "rv_kit", "__file__": os.path.abspath(KIT)}
exec(compile(source[:-len("main()")], KIT, "exec"), kit)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.geometry import intersect_point_tri_2d  # noqa: E402

EPS_PLANE = 0.0012        # 1.2 mm: nearer than that the depth buffer cannot tell the planes apart at the game's zoom
MIN_OVERLAP = 0.00002     # m2 (0.2 cm2)


def basis(normal):
    helper = Vector((1, 0, 0)) if abs(normal.x) < 0.9 else Vector((0, 1, 0))
    u = normal.cross(helper).normalized()
    return u, normal.cross(u).normalized()


def overlap_area(fa, fb, normal):
    """Rough area of the overlap of two coplanar faces: sample points of a on a grid, count those inside b."""
    u, v = basis(normal)
    pa = [((p.dot(u)), (p.dot(v))) for p in fa["pts"]]
    pb = [((p.dot(u)), (p.dot(v))) for p in fb["pts"]]
    x0, x1 = min(p[0] for p in pa), max(p[0] for p in pa)
    y0, y1 = min(p[1] for p in pa), max(p[1] for p in pa)
    n = 24
    hits = 0
    tris_a = [(pa[0], pa[i], pa[i + 1]) for i in range(1, len(pa) - 1)]
    tris_b = [(pb[0], pb[i], pb[i + 1]) for i in range(1, len(pb) - 1)]

    def inside(point, tris):
        q = Vector(point)
        return any(intersect_point_tri_2d(q, Vector(t[0]), Vector(t[1]), Vector(t[2])) for t in tris)
    for i in range(n):
        for j in range(n):
            point = (x0 + (x1 - x0) * (i + 0.5) / n, y0 + (y1 - y0) * (j + 0.5) / n)
            if inside(point, tris_a) and inside(point, tris_b):
                hits += 1
    return (x1 - x0) * (y1 - y0) * hits / (n * n)


def check(name):
    spec = kit["PIECES"][name]
    b = kit["Builder"]("rv_" + name)
    spec["build"](b)
    obj = b.finish()
    faces = []
    for p in obj.data.polygons:
        pts = [obj.data.vertices[i].co.copy() for i in p.vertices]
        normal = p.normal.copy()
        if normal.length < 1e-6 or p.area < MIN_OVERLAP:
            continue
        faces.append({"pts": pts, "n": normal, "d": normal.dot(pts[0]), "c": p.center.copy(), "i": p.index})
    pairs = []
    for ia in range(len(faces)):
        for ib in range(ia + 1, len(faces)):
            a, b_ = faces[ia], faces[ib]
            if a["n"].dot(b_["n"]) < 0.9999 or abs(a["d"] - b_["d"]) > EPS_PLANE:
                continue
            area = overlap_area(a, b_, a["n"])
            if area > MIN_OVERLAP:
                pairs.append((a, b_, area))
    # faces of ONE box never overlap in a plane (bevels aside), so every pair here is two different boxes
    print("== %s: %d overlapping same-plane pair(s)" % (name, len(pairs)))
    for a, b_, area in sorted(pairs, key=lambda t: -t[2])[:12]:
        print("   normal (%+.0f %+.0f %+.0f) at (%.3f %.3f %.3f) and (%.3f %.3f %.3f), overlap %.1f cm2" % (
            round(a["n"].x), round(a["n"].y), round(a["n"].z), a["c"].x, a["c"].y, a["c"].z, b_["c"].x, b_["c"].y, b_["c"].z,
            area * 1e4))
    return len(pairs)


total = 0
names = args or [n for n, s in kit["PIECES"].items() if s["kind"] != "model"]
bpy.ops.wm.read_factory_settings(use_empty=True)
for name in names:
    total += check(name)
print("ZFIGHT total pairs:", total)
