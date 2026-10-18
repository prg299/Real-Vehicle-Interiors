"""Developer helper: read vehicle scripts (the game's script format) offline, with their
templates resolved the way the game merges them, and print what ME: LENS needs to set a
vehicle up: model and scales, passengers (seats) with their positions, doors, areas and
the parts' models.
    python dev/pzscripts.py <scripts dir>[;<scripts dir>...] <vehicle> [<vehicle> ...]
    python dev/pzscripts.py <dirs> <vehicle> --json out.json
Offsets are printed as written in the script (the game multiplies passenger, area and
wheel offsets by the vehicle's model scale when it loads them)."""
import json
import os
import re
import sys


def tokens(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    return re.findall(r"[{}]|,|=|[^\s{},=]+", text)


class Block:
    def __init__(self, kind, name):
        self.kind, self.name = kind, name
        self.values = []      # (key, value) in order
        self.children = []    # Blocks in order

    def get(self, key, default=None):
        for k, v in reversed(self.values):
            if k == key:
                return v
        return default

    def child(self, kind, name=None):
        for c in self.children:
            if c.kind == kind and (name is None or c.name == name):
                return c
        return None


def parse(toks):
    """Returns the top-level blocks. A block: words then '{'; a value: key '=' words ','."""
    pos = 0

    def block_body(block):
        nonlocal pos
        words = []
        while pos < len(toks):
            t = toks[pos]
            pos += 1
            if t == "}":
                if words:
                    block.values.append((words[0], ""))
                return
            if t == "{":
                kind = words[0] if words else ""
                name = " ".join(words[1:]) if len(words) > 1 else ""
                child = Block(kind, name)
                block_body(child)
                block.children.append(child)
                words = []
            elif t == "=":
                key = " ".join(words)
                vals = []
                while pos < len(toks) and toks[pos] not in (",", "}"):
                    vals.append(toks[pos])
                    pos += 1
                if pos < len(toks) and toks[pos] == ",":
                    pos += 1
                block.values.append((key, " ".join(vals)))
                words = []
            elif t == ",":
                continue
            else:
                words.append(t)
    root = Block("root", "")
    block_body(root)
    return root.children


def load_dirs(dirs):
    models, vehicles, templates = {}, {}, {}
    for d in dirs:
        for dirpath, _, files in os.walk(d):
            for f in files:
                if not f.endswith(".txt"):
                    continue
                with open(os.path.join(dirpath, f), encoding="utf-8", errors="replace") as h:
                    for module in parse(tokens(h.read())):
                        if module.kind != "module":
                            continue
                        for b in module.children:
                            if b.kind == "model":
                                models[b.name] = b
                            elif b.kind == "vehicle":
                                vehicles[b.name] = b
                            elif b.kind == "template" and b.name.startswith("vehicle "):
                                templates[b.name[len("vehicle "):]] = b
    return models, vehicles, templates


KEYED = ("part", "passenger", "area", "wheel")


def merge_into(target, source, only=None):
    """Appends source's values and keyed children to target (the game merges a part,
    passenger, area or wheel with the same id into the existing one)."""
    for k, v in source.values:
        if only is None and k != "template":
            target.values.append((k, v))
    for c in source.children:
        if only and not (c.kind == only[0] and (only[1] == "*" or c.name == only[1])):
            continue
        if c.kind in KEYED:
            existing = next((e for e in target.children if e.kind == c.kind and e.name == c.name), None)
            if existing:
                merge_into(existing, c)
                continue
            copy = Block(c.kind, c.name)
            merge_into(copy, c)
            target.children.append(copy)
        elif only is None:
            target.children.append(c)


def resolve(vehicle, templates):
    out = Block("vehicle", vehicle.name)

    def apply(block):
        for item in block_items(block):
            if isinstance(item, tuple):
                k, v = item
                if k in ("template", "template!"):
                    name, _, rest = v.partition("/")
                    t = templates.get(name)
                    if not t:
                        continue
                    if rest:
                        kind, _, cid = rest.partition("/")
                        merge_into(out, t, (kind, cid or "*"))
                    else:
                        apply(t)
                else:
                    out.values.append(item)
            else:
                c = item
                if c.kind in KEYED:
                    existing = next((e for e in out.children if e.kind == c.kind and e.name == c.name), None)
                    if existing:
                        merge_into(existing, c)
                        continue
                    copy = Block(c.kind, c.name)
                    merge_into(copy, c)
                    out.children.append(copy)
                else:
                    out.children.append(c)
    apply(vehicle)
    return out


def block_items(block):
    """Values and children in source order (values first within the same position is
    fine for the game's merge semantics used here)."""
    items = []
    vi = ci = 0
    # keep the original interleaving approximately: templates (values) before children
    for k, v in block.values:
        items.append((k, v))
    for c in block.children:
        items.append(c)
    return items


def vec(s):
    return [float(x) for x in s.split()] if s else None


def summary(name, models, vehicles, templates):
    v = vehicles.get(name)
    if not v:
        return {"error": "no vehicle " + name}
    r = resolve(v, templates)
    model = r.child("model")
    info = {"name": name, "model": None, "passengers": [], "parts": [], "areas": {}, "wheels": {},
            "extents": vec(r.get("extents")), "centerOfMassOffset": vec(r.get("centerOfMassOffset")),
            "physicsChassisShape": vec(r.get("physicsChassisShape"))}
    if model:
        mdef = models.get(model.get("file"))
        info["model"] = {"file": model.get("file"), "scale": float(model.get("scale", "1")),
                         "offset": vec(model.get("offset")),
                         "mesh": mdef.get("mesh") if mdef else None,
                         "meshScale": float(mdef.get("scale", "1")) if mdef else None}
    for c in r.children:
        if c.kind == "passenger":
            p = {"id": c.name, "door": c.get("door"), "area": c.get("area")}
            for pos in c.children:
                if pos.kind == "position":
                    p[pos.name] = {"offset": vec(pos.get("offset")), "rotate": vec(pos.get("rotate"))}
            info["passengers"].append(p)
        elif c.kind == "area":
            info["areas"][c.name] = vec(c.get("xywh"))
        elif c.kind == "wheel":
            info["wheels"][c.name] = vec(c.get("offset"))
        elif c.kind == "part":
            part = {"id": c.name, "area": c.get("area"), "category": c.get("category"),
                    "itemType": c.get("itemType"), "parent": c.get("parent"), "models": []}
            if c.child("door"):
                part["door"] = True
            cont = c.child("container")
            if cont:
                part["container"] = {"capacity": cont.get("capacity"), "test": cont.get("test"), "seat": cont.get("seat")}
            for m in c.children:
                if m.kind == "model":
                    mdef = models.get(m.get("file"))
                    part["models"].append({"id": m.name, "file": m.get("file"), "offset": vec(m.get("offset")),
                                           "rotate": vec(m.get("rotate")),
                                           "mesh": mdef.get("mesh") if mdef else None})
            info["parts"].append(part)
    return info


if __name__ == "__main__":
    dirs = sys.argv[1].split(";")
    names = [a for a in sys.argv[2:] if not a.startswith("--")]
    out_json = None
    if "--json" in sys.argv:
        out_json = sys.argv[sys.argv.index("--json") + 1]
        names = [n for n in names if n != out_json]
    models, vehicles, templates = load_dirs(dirs)
    result = {n: summary(n, models, vehicles, templates) for n in names}
    if out_json:
        with open(out_json, "w", encoding="utf-8") as h:
            json.dump(result, h, indent=1)
        print("wrote", out_json)
    for n, s in result.items():
        if "error" in s:
            print(n, s["error"])
            continue
        m = s["model"]
        print("== %s  model %s scale %s offset %s mesh %s (x%s)  extents %s" % (
            n, m["file"], m["scale"], m["offset"], m["mesh"], m["meshScale"], s["extents"]))
        for p in s["passengers"]:
            print("   seat %-12s door=%-14s area=%-16s inside=%s outside=%s" % (
                p["id"], p["door"], p["area"], (p.get("inside") or {}).get("offset"), (p.get("outside") or {}).get("offset")))
        for part in s["parts"]:
            if part["models"] or part.get("door") or part.get("container"):
                print("   part %-24s area=%-16s door=%s cont=%s models=%s" % (
                    part["id"], part["area"], part.get("door", False), (part.get("container") or {}).get("capacity"),
                    ", ".join("%s:%s@%s" % (mm["id"], mm["file"], mm["offset"]) for mm in part["models"])))
