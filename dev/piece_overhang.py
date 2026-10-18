"""Developer helper: does furniture (or the shell's walls) stand outside KI5's hull, low down where it tucks in?

    blender -b --factory-startup --python dev/piece_overhang.py -- <mod media folder> [key ...]
    (key: FlyingCloud22 Bambi16 Airflyte Scamp13 Scamp16 B700 F700box; default: all)

The furniture was fitted to the hull's inside outlines from 0.1 above the floor up (campers curve in
towards the top and round their noses). Below that the hull tucks in under the floor, so a piece's
bottom corners at a rounded end can reach past the skin and show from outside. For every vertex of each
default piece (and of the shell's walls) up to 0.45 above the floor, this measures how far it lies
outside the hull's inside outline at its height (interpolated between the measured outlines, 0.1
apart), less the skin's thickness, and prints the worst vertices per piece: positive means beyond the
skin's outer face. KI5's mesh is not used: only the measured outlines (build/rv/floorplans)."""
import json
import math
import os
import sys

from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
FLOORPLANS = os.path.join(ROOT, "build", "rv", "floorplans")
MEASURES = {"FlyingCloud22": ["measure_FlyingCloud22.json"], "Bambi16": ["measure_Bambi16.json"],
            "Airflyte": ["measure_Airflyte.json"], "Scamp13": ["measure_Scamp13_floor.json"],
            "Scamp16": ["measure_Scamp16.json"], "B700": ["measure_B700_box.json"], "F700box": ["measure_F700box_box.json"]}
SKIN = 0.011        # the skin's thickness: the outline is its inside face
BEYOND = 0.006      # what counts as beyond the skin: the outlines are 0.1 apart in height, so this much is measurement noise
LIMIT = 0.45

source = open(os.path.join(HERE, "clip_audit.py"), encoding="utf-8").read()
head = source[:source.index("total = 0\nfor key in KEYS:")]
ns = {"__name__": "clip_audit_head"}
exec(compile(head, "clip_audit_head", "exec"), ns)
KEYS = ns["KEYS"]
Piece, load_profile, world_mesh, find, TEXTURE = ns["Piece"], ns["load_profile"], ns["world_mesh"], ns["find"], ns["TEXTURE"]


def signed_distance(poly, x, z):
    """Distance from (x, z) to the closed polygon's edge: positive outside, negative inside."""
    inside = False
    best = 1e9
    j = len(poly) - 1
    for i in range(len(poly)):
        ax, az = poly[j]
        bx, bz = poly[i]
        if (az > z) != (bz > z) and x < (bx - ax) * (z - az) / (bz - az) + ax:
            inside = not inside
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz + 1e-12)))
        best = min(best, math.hypot(x - (ax + t * dx), z - (az + t * dz)))
        j = i
    return -best if inside else best


found_any = 0
for key in KEYS:
    measure = json.load(open(os.path.join(FLOORPLANS, MEASURES[key][0]), encoding="utf-8"))
    levels = sorted((float(h), pts) for h, pts in measure["outlines"].items() if pts)
    spots, floor, wells = load_profile(key)

    def hull_distance(px, pz, y):
        """How far (px, pz) at height y lies outside the hull's inside outline there (negative: inside)."""
        lower = [lv for lv in levels if lv[0] <= y]
        upper = [lv for lv in levels if lv[0] >= y]
        if not lower or not upper:
            return None
        (ha, pa), (hb, pb) = lower[-1], upper[0]
        da = signed_distance(pa, px, pz)
        if hb <= ha + 1e-9:
            return da
        db = signed_distance(pb, px, pz)
        return da + (db - da) * (y - ha) / (hb - ha)

    def in_well(px, pz, h):
        for w in wells:
            x0, x1 = sorted(w["x"])
            z0, z1 = sorted(w["z"])
            if x0 - 0.03 <= px <= x1 + 0.03 and z0 - 0.03 <= pz <= z1 + 0.03 and h <= w["y"][1] - floor + 0.03:
                return True
        return False

    print("OVERHANG == %s (floor %.2f; outlines from %s)" % (key, floor, MEASURES[key][0]))
    groups = []
    for i, spot in enumerate(spots):
        if spot["empty"]:
            continue
        piece = Piece(i + 1, spot, floor)
        groups.append(("piece %d %s" % (i + 1, piece.name), piece.obj, piece.matrix))
    groups.append(("walls", find("shell_%s_walls" % TEXTURE[key]), Matrix.Identity(4)))
    groups.append(("floor", find("shell_%s_floor" % TEXTURE[key]), Matrix.Identity(4)))
    for label, obj, matrix in groups:
        vs, _ = world_mesh(obj, matrix)
        worst = []
        for v in vs:
            h = v.z - floor
            if h < -0.002 or h > LIMIT:
                continue
            px, pz = -v.x, v.y
            if label != "walls" and in_well(px, pz, h):
                continue        # (furniture over a wheel well is not drawn inside it: the shell's walls, the wells' plates included, are measured)
            d = hull_distance(px, pz, floor + max(h, 0.0))
            if d is None:
                continue
            worst.append((d - SKIN, px, pz, h))
        if not worst:
            continue
        worst.sort(reverse=True)
        top = worst[0]
        beyond = [w for w in worst if w[0] > BEYOND]
        flag = "BEYOND THE SKIN" if top[0] > BEYOND else "inside"
        print("OVERHANG   %-18s worst %+.3f (x %+.2f z %+.2f, %.2f above the floor): %s; %d vertices beyond" % (
            label, top[0], top[1], top[2], top[3], flag, len(beyond)))
        if top[0] > BEYOND and label.startswith("piece"):
            found_any += 1
            for d, px, pz, h in worst[:3]:
                print("OVERHANG       %+.3f at x %+.2f z %+.2f, %.2f above the floor" % (d, px, pz, h))
        if top[0] > BEYOND and label in ("walls", "floor"):
            found_any += 1
print("OVERHANGAUDIT pieces (and shell) beyond the skin: %d" % found_any)
sys.exit(1 if found_any else 0)
