"""Developer helper: the facts a vehicle's ME: LENS layout is designed from, in passenger
space (tiles): floor and ceiling, KI5's seats (runtime offsets = script x model scale),
the measured cushions, doors and windows, and KI5's part models (interior, seats, beds).
    python dev/layout_facts.py <measure.json> <scripts.json> <vehicle>"""
import json
import sys

measure = json.load(open(sys.argv[1], encoding="utf-8"))
info = json.load(open(sys.argv[2], encoding="utf-8"))[sys.argv[3]]
scale = info["model"]["scale"]
print("%s: floor %.2f ceiling %.2f  body x %.2f..%.2f z %.2f..%.2f  model offset %s" % (
    sys.argv[3], measure["floor"], measure["ceiling"], measure["body"]["min"][0], measure["body"]["max"][0],
    measure["body"]["min"][2], measure["body"]["max"][2], [round(v * scale, 3) for v in info["model"]["offset"]]))
for p in info["passengers"]:
    ins = (p.get("inside") or {}).get("offset")
    out = (p.get("outside") or {}).get("offset")
    if ins and p["id"] not in ("*", "DAMNFakeSeat"):
        print("  seat %-10s inside (%.3f, %.3f, %.3f)  outside (%s)  door %s area %s" % (
            p["id"], *(v * scale for v in ins), ", ".join("%.2f" % (v * scale) for v in out) if out else "-", p["door"], p["area"]))
for name, b in sorted(measure["parts"].items()):
    lo, hi = b["min"], b["max"]
    if any(k in name for k in ("bed", "seat", "door", "window", "windshield", "lid", "top", "vent")):
        print("  part %-30s x %6.3f..%-6.3f y %6.3f..%-6.3f z %6.3f..%-6.3f" % (name, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
for part in info["parts"]:
    files = [m["file"] for m in part["models"] if m.get("file")]
    if files and any(k in (part["id"] + " ".join(files)).lower() for k in ("interior", "seat", "bed", "glovebox")):
        print("  model part %-18s area %-16s models %s" % (part["id"], part["area"], ", ".join(files)))
    if part.get("container"):
        print("  container %-18s area %-16s capacity %s" % (part["id"], part["area"], part["container"]["capacity"]))
for name, off in info["wheels"].items():
    if off:
        print("  wheel %-14s (%.3f, %.3f, %.3f)" % (name, *(v * scale for v in off)))
