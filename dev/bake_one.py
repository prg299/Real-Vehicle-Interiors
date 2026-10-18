"""Developer helper: bake one furniture piece with rv_kit.py's materials into a scratch folder (to try the look
quickly, or to find out why a bake fails), without touching the mod.

    blender -b --factory-startup --python dev/bake_one.py -- <out dir> <piece> [<piece> ...]

Writes <out dir>/MELensRV_<piece>.png for each piece."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, "..", "tools-src", "blender", "rv_kit.py")
args = sys.argv[sys.argv.index("--") + 1:]
out = os.path.abspath(args[0])
names = args[1:]
os.makedirs(out, exist_ok=True)
# rv_kit.py reads its own arguments at import: give it the scratch folder as the media folder
sys.argv = [sys.argv[0], "--", out]
source = open(KIT, encoding="utf-8").read()
assert source.rstrip().endswith("main()")
source = source.rstrip()[:-len("main()")]
kit = {"__name__": "rv_kit", "__file__": os.path.abspath(KIT)}
exec(compile(source, KIT, "exec"), kit)

import bpy  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
for name in names:
    spec = kit["PIECES"][name]
    b = kit["Builder"]("rv_" + name)
    spec["build"](b)
    obj = b.finish()
    for v in obj.data.vertices:
        v.co.y -= spec["depth"] / 2
    path = os.path.join(out, "MELensRV_%s.png" % name)
    size = 1024 if spec["width"] > 1.2 else 512
    print("BAKEONE baking", name, size, flush=True)
    kit["bake_piece"](obj, path, size)
    print("BAKEONE wrote", path, flush=True)
