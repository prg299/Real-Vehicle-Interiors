"""Developer helper: list the faces of each furniture piece whose baked texture is (nearly) black: a face that is
buried inside another box gets black ambient occlusion, which is right for a hidden face and a black spot for one that
shows. The pieces are built and baked into a scratch folder with rv_kit.py's real materials.

    blender -b --factory-startup --python dev/black_faces.py -- [<piece> ...]

Prints, per piece, the black faces with their centre (piece space, metres), normal, area and material, and whether
the face is hidden (another face of the piece lies within 3 mm in front of it) or shows."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, "..", "tools-src", "blender", "rv_kit.py")
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
scratch = os.path.join(os.environ.get("TEMP", "."), "black_faces_scratch")
os.makedirs(scratch, exist_ok=True)
sys.argv = [sys.argv[0], "--", scratch]
source = open(KIT, encoding="utf-8").read().rstrip()
assert source.endswith("main()")
kit = {"__name__": "rv_kit", "__file__": os.path.abspath(KIT)}
exec(compile(source[:-len("main()")], KIT, "exec"), kit)

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
names = args or [n for n, s in kit["PIECES"].items() if s["kind"] != "model"]
total_show = 0
for name in names:
    spec = kit["PIECES"][name]
    b = kit["Builder"]("rv_" + name)
    spec["build"](b)
    obj = b.finish()
    for v in obj.data.vertices:
        v.co.y -= spec["depth"] / 2
    texture = os.path.join(scratch, "MELensRV_%s.png" % name)
    image = kit["bake_piece"](obj, texture, 512)
    size = image.size[0]
    pixels = image.pixels[:]
    mesh = obj.data
    uv = mesh.uv_layers.active.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)

    def sample(u, v):
        x = min(size - 1, max(0, int(u * size)))
        y = min(size - 1, max(0, int(v * size)))
        i = (y * size + x) * 4
        return (pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3.0

    black = []
    for p in mesh.polygons:
        if p.area < 0.0002:
            continue
        loops = [uv[i].uv for i in p.loop_indices]
        cu = sum(l[0] for l in loops) / len(loops)
        cv = sum(l[1] for l in loops) / len(loops)
        values = [sample(cu, cv)] + [sample(cu + (l[0] - cu) * 0.6, cv + (l[1] - cv) * 0.6) for l in loops]
        mean = sum(values) / len(values)
        if mean < 0.04:
            # hidden: a ray from the face centre along its normal, started 0.2 mm out, hits the piece within 3 mm
            origin = p.center + p.normal * 0.0002
            hit = tree.ray_cast(origin, p.normal, 0.003)
            hidden = hit[0] is not None
            black.append((p, mean, hidden))
    shown = [t for t in black if not t[2]]
    total_show += len(shown)
    print("== %s: %d black face(s), %d of them showing" % (name, len(black), len(shown)))
    for p, mean, hidden in sorted(black, key=lambda t: (t[2], -t[0].area))[:10]:
        print("   %-7s centre (%.3f %.3f %.3f) normal (%+.0f %+.0f %+.0f) area %.1f cm2 material %s" % (
            "hidden" if hidden else "SHOWS", p.center.x, p.center.y, p.center.z,
            round(p.normal.x), round(p.normal.y), round(p.normal.z), p.area * 1e4,
            kit["MATERIAL_NAMES"][p.material_index]))
    bm.free()
print("BLACKFACES showing in total:", total_show)
