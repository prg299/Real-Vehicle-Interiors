"""Build tool: what the wall fitter (make_vehicles.fit_spot) would change in a hand-written
profile's spots, for the Flying Cloud 22 (MELens_Profiles.lua), whose layout is not
generated. Prints each spot before and after; apply the numbers by hand.

    python tools-src/vehicles/fit_existing.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_vehicles as mv   # noqa: E402

shell = mv.load(os.path.join(mv.CFG, "shell_FlyingCloud22.json"))
measure = mv.load(shell["measure"])
floor = shell["floorY"]
kit = mv.load_kit()
text = open(os.path.join(mv.LUA, "MELens_Profiles.lua"), encoding="utf-8").read()
block = text[text.index("spots = {"):]
block = block[:block.index("},\n\n")]
pattern = r'\{ x = ([-\d.]+), z = ([-\d.]+), wall = "(\w+)", length = ([\d.]+), depth = ([\d.]+), default = "(\w+)"'
for m in re.finditer(pattern, block):
    spot = {"x": float(m.group(1)), "z": float(m.group(2)), "wall": m.group(3), "length": float(m.group(4)),
            "depth": float(m.group(5)), "default": m.group(6)}
    before = dict(spot)
    dims = kit[spot["default"]]
    note = mv.fit_spot(spot, measure, floor, max(mv.FURNITURE_TOP, dims["height"]), dims["width"])
    print("%-8s %-6s x %6.3f z %6.3f len %.2f  ->  x %6.3f z %6.3f len %.2f   %s" % (
        spot["default"], spot["wall"], before["x"], before["z"], before["length"],
        spot["x"], spot["z"], spot["length"], note or "fits"))
