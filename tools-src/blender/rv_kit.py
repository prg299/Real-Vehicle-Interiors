# Blender (background) tool: build the ME: LENS RV kit.
#
#   blender -b --factory-startup --python rv_kit.py -- <mod media folder> [--shells-only] <shell spec json>...
#
# Writes, under <mod media folder>:
#   textures/Vehicles/MELens_RV.png         palette texture shared by every model
#   models_X/vehicles/MELens_RV.fbx         RV furniture, one object per piece
#   models_X/vehicles/MELens_Shells.fbx     inside shells, one object per camper
#   textures/Item_MELensRV_<piece>.png      inventory icons
#   lua/shared/MELens_RVKit.lua             footprints, heights and capacities for Lua
#
# Conventions (checked in game with the calibration box): one Blender unit is one tile
# with the model script scale 0.0111111; +Y is the camper's front, +Z is up and +X is
# the camper's right. Furniture is modelled with its back to +Y, its front to -Y, the
# origin at the middle of its footprint on the floor. Pieces stay at most 0.9 tall
# (compact RV furniture; the game never cuts furniture, only walls).
import hashlib
import inspect
import json
import math
import os
import shutil
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vehicles"))
import shell_rings  # noqa: E402  (the lining's rings, shared with make_vehicles.py)

args = sys.argv[sys.argv.index("--") + 1:]
# --shells-only: rebuild the shells and their walk grids only (the furniture takes most of the time
# and is left as it is); every shell config must still be given, the FBX holds exactly those.
SHELLS_ONLY = "--shells-only" in args
# --no-cache: bake every piece again, also those whose cached texture still matches (bake_piece)
NO_CACHE = "--no-cache" in args
SHELL_FILE = next((a.split("=", 1)[1] for a in args if a.startswith("--shell-file=")), "MELens_Shells")
assert SHELL_FILE.replace("_", "").isalnum(), "Shell output must be a filename without a path"
args = [a for a in args if a not in ("--shells-only", "--no-cache") and not a.startswith("--shell-file=")]
# Absolute: Blender saves images relative to the .blend file, not the working folder, so
# a relative media path left the baked textures unwritten (the FBX export was fine).
MEDIA = os.path.abspath(args[0])
MEASURES = [os.path.abspath(a) for a in args[1:]]

# The look: like the game's own furniture sprites, measured on them in the game (dev/lua/vanilla_furniture.lua
# puts a row of them next to the test camper): painted materials in muted, dirty colours (dark wood, beige
# tops, off-white enamel), tops lit and sides darker, the lower part darker with grime, rounded edges that
# catch the light and dark seams where parts meet. The painted textures (tools-src/art/textures) are graded to
# each material's palette colour and baked with ambient occlusion in the gaps. FLAT = True gives the earlier
# flat-colour look instead (every face one palette colour, hard edges, no bake), which did not look like the
# game's furniture.
FLAT = False
OUTLINES = False           # a dark outline round every piece (add_outline): tried, it read as black dots and a comic edge

# ------------------------------------------------------------------------------------
# Palette: an 8 x 8 grid of 64 px cells, each a flat colour.
# ------------------------------------------------------------------------------------

CELL = 64
GRID = 8
SIZE = CELL * GRID

PALETTE = {
    # name: (row, col, colour, pattern). The colour is what a material's painted texture is graded to (sRGB,
    # before the game's light), chosen against the game's own furniture in the same light: dark warm woods,
    # beige tops, off-white enamel with grey in it, muted fabrics. (The pattern is only used by the flat look.)
    "wood_light": (0, 0, (0.36, 0.22, 0.12), "grain"),            # cabinet bodies, bed and bench frames
    "wood_dark": (0, 1, (0.36, 0.27, 0.19), "grain"),             # walnut: the wardrobe
    "wood_birch": (0, 2, (0.40, 0.26, 0.15), "grain"),            # door and drawer fronts, a little lighter
    "paint_cream": (0, 3, (0.84, 0.80, 0.71), "flat"),
    "paint_mint": (0, 4, (0.60, 0.72, 0.66), "flat"),
    "paint_turquoise": (0, 5, (0.30, 0.50, 0.52), "flat"),
    "paint_white": (0, 6, (0.84, 0.83, 0.79), "flat"),
    "laminate": (0, 7, (0.85, 0.78, 0.61), "speckle"),            # counter and table tops: the game's beige tops
    "fabric_red": (1, 0, (0.59, 0.24, 0.20), "weave"),
    "fabric_blue": (1, 1, (0.30, 0.41, 0.45), "weave"),           # dinette vinyl: a muted teal
    "fabric_beige": (1, 2, (0.70, 0.63, 0.50), "weave"),
    "fabric_grey": (1, 3, (0.48, 0.49, 0.50), "weave"),
    "fabric_green": (1, 4, (0.30, 0.42, 0.30), "weave"),
    "fabric_mustard": (1, 5, (0.70, 0.55, 0.24), "weave"),
    "leather_brown": (1, 6, (0.36, 0.24, 0.15), "speckle"),
    "mattress": (1, 7, (0.44, 0.54, 0.63), "weave"),              # the blanket on a bed: the game's blue linen
    "steel": (2, 0, (0.64, 0.65, 0.66), "brushed"),
    "enamel": (2, 1, (0.86, 0.85, 0.80), "flat"),                 # white goods: off-white
    "black": (2, 2, (0.16, 0.16, 0.16), "flat"),
    "chrome": (2, 3, (0.72, 0.73, 0.74), "brushed"),
    "burner": (2, 4, (0.07, 0.07, 0.07), "flat"),
    "glass": (2, 5, (0.45, 0.55, 0.60), "flat"),
    "rubber": (2, 6, (0.08, 0.08, 0.08), "flat"),
    "copper": (2, 7, (0.58, 0.39, 0.25), "brushed"),
    "floor_lino": (3, 0, (0.76, 0.73, 0.64), "speckle"),
    "floor_planks": (3, 1, (0.36, 0.25, 0.17), "grain"),
    "wall_panel": (3, 2, (0.82, 0.78, 0.68), "flat"),
    "wall_alu": (3, 3, (0.66, 0.67, 0.68), "brushed"),
    "trim": (3, 4, (0.25, 0.25, 0.25), "flat"),
    "pillow": (3, 5, (0.88, 0.87, 0.83), "weave"),                # sheets and pillows
    "water": (3, 6, (0.35, 0.50, 0.62), "flat"),
    "bulb": (3, 7, (1.00, 0.85, 0.55), "flat"),
    "shadow": (4, 0, (0.05, 0.05, 0.05), "flat"),
    "vent": (4, 1, (0.20, 0.20, 0.21), "slats"),
    "wood_kick": (4, 2, (0.22, 0.13, 0.07), "grain"),              # the toe kick: the cabinet's wood in shade
    "basin": (4, 3, (0.48, 0.49, 0.50), "brushed"),
    "heater_body": (4, 4, (0.42, 0.29, 0.20), "flat"),
    "cardboard": (4, 5, (0.67, 0.51, 0.34), "flat"),
    "tape": (4, 6, (0.80, 0.72, 0.55), "flat"),
    "busvinyl": (4, 7, (0.21, 0.36, 0.24), "weave"),
    "cardboard_dark": (5, 0, (0.55, 0.40, 0.25), "flat"),
    "cardboard_light": (5, 1, (0.76, 0.62, 0.44), "flat"),
    "label_paper": (5, 2, (0.90, 0.89, 0.84), "flat"),
    "stencil": (5, 3, (0.14, 0.11, 0.09), "flat"),
    "stamp_red": (5, 4, (0.62, 0.20, 0.16), "flat"),
    "tape_brown": (5, 5, (0.45, 0.30, 0.16), "flat"),
    "fridge_mint": (5, 6, (0.60, 0.72, 0.66), "flat"),
    "sheet": (5, 7, (0.88, 0.87, 0.83), "flat"),
}

# How much darker a material's sides are than its top, painted in like the game's sprites (their wood is
# much darker on the sides than on top; white goods hardly). The cutaway shader's form shading comes on top.
SIDE_SHADE = {"wood_light": 0.80, "wood_dark": 0.80, "wood_birch": 0.82, "wood_kick": 0.80, "laminate": 0.88,
              "cardboard": 0.86, "tape": 0.90, "busvinyl": 0.86, "fabric_blue": 0.86, "mattress": 0.88,
              "heater_body": 0.84, "copper": 0.86}


def pattern_cell(rgb, kind, rng):
    if FLAT:
        return np.ones((CELL, CELL, 3)) * np.array(rgb)
    y, x = np.mgrid[0:CELL, 0:CELL]
    base = np.ones((CELL, CELL, 3)) * np.array(rgb)
    shade = np.ones((CELL, CELL))
    if kind == "grain":
        shade = 1.0 + 0.06 * np.sin(y * 0.9 + np.sin(x * 0.35) * 2.0) + 0.03 * rng.standard_normal((CELL, CELL))
    elif kind == "speckle":
        shade = 1.0 + 0.05 * rng.standard_normal((CELL, CELL))
    elif kind == "plaid":
        stripes = ((x // 4) % 4 == 0) | ((y // 4) % 4 == 0)
        shade = np.where(stripes, 0.72, 1.0) + 0.03 * rng.standard_normal((CELL, CELL))
    elif kind == "weave":
        shade = 1.0 + 0.05 * ((x + y) % 2 - 0.5) + 0.03 * rng.standard_normal((CELL, CELL))
    elif kind == "quilt":
        seams = ((x % 8) == 0) | ((y % 8) == 0)
        shade = np.where(seams, 0.86, 1.0)
    elif kind == "brushed":
        shade = 1.0 + 0.04 * np.sin(y * 2.3) + 0.02 * rng.standard_normal((CELL, CELL))
    elif kind == "rings":
        r = np.hypot(x - CELL / 2 + 0.5, y - CELL / 2 + 0.5)
        shade = np.where((r > 9) & (r < 11), 1.8, np.where((r > 4) & (r < 6), 1.6, 1.0))
    elif kind == "checker":
        dark = ((x // 8) + (y // 8)) % 2 == 1
        base = np.where(dark[..., None], np.array([0.52, 0.24, 0.22]), base)
    elif kind == "planks":
        seams = (y % 8) == 0
        shade = np.where(seams, 0.7, 1.0 + 0.05 * np.sin(x * 0.6 + (y // 8) * 1.7))
    elif kind == "panels":
        seams = (x % 16) == 0
        shade = np.where(seams, 0.82, 1.0) + 0.015 * rng.standard_normal((CELL, CELL))
    elif kind == "slats":
        shade = np.where((y % 4) < 2, 0.6, 1.1)
    return np.clip(base * shade[..., None], 0.0, 1.0)


def build_palette(path):
    rng = np.random.default_rng(7)
    pixels = np.zeros((SIZE, SIZE, 4))
    pixels[..., 3] = 1.0
    for name, (row, col, rgb, kind) in PALETTE.items():
        cell = pattern_cell(rgb, kind, rng)
        # Blender images start at the bottom row; keep row 0 at the top of the file.
        y0 = SIZE - (row + 1) * CELL
        pixels[y0:y0 + CELL, col * CELL:(col + 1) * CELL, :3] = cell
    img = bpy.data.images.new("MELens_RV", width=SIZE, height=SIZE, alpha=True)
    img.pixels = pixels.flatten().tolist()
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img


def cell_uv(name):
    """The inner rectangle (u0, v0, u1, v1) of a palette cell, with a 2 px margin."""
    row, col, _, _ = PALETTE[name]
    m = 4.0 / SIZE
    u0 = col * CELL / SIZE + m
    u1 = (col + 1) * CELL / SIZE - m
    v1 = 1.0 - row * CELL / SIZE - m
    v0 = 1.0 - (row + 1) * CELL / SIZE + m
    return u0, v0, u1, v1


# ------------------------------------------------------------------------------------
# Mesh building
# ------------------------------------------------------------------------------------

def map_faces(faces, uv, material):
    """Map each face onto its palette cell (planar, along the face's main axis)."""
    u0, v0, u1, v1 = cell_uv(material)
    for face in faces:
        n = face.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        a, b = [i for i in range(3) if i != ax]
        coords = [(l.vert.co[a], l.vert.co[b]) for l in face.loops]
        amin = min(c[0] for c in coords)
        amax = max(c[0] for c in coords)
        bmin = min(c[1] for c in coords)
        bmax = max(c[1] for c in coords)
        for loop, (ca, cb) in zip(face.loops, coords):
            s = (ca - amin) / (amax - amin) if amax > amin else 0.5
            t = (cb - bmin) / (bmax - bmin) if bmax > bmin else 0.5
            loop[uv].uv = (u0 + (u1 - u0) * s, v0 + (v1 - v0) * t)


# Material slot per palette name (for baking the furniture's own textures).
MATERIAL_NAMES = list(PALETTE)
MATERIAL_INDEX = {name: i for i, name in enumerate(MATERIAL_NAMES)}


class Builder:
    """Collects boxes, cylinders and quads into one mesh, each face mapped to a palette
    cell. Every primitive is built in its own bmesh and then merged, so a bevel or a
    normal fix never touches its neighbours."""

    # Two boxes whose faces lie in one plane, facing the same way, fight for the depth buffer in the game, and the
    # ambient-occlusion bake sees the other face at zero distance and bakes the shared area black: the black patches
    # on the dinette's end panel, the bus seat's posts and so on. Boxes are therefore collected and, in finish(),
    # such faces are kept SEPARATION apart (the earlier box's face steps inward, the later one stays where it was
    # asked for), so one face always lies clearly in front of the other.
    SEPARATION = 0.0016

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.boxes = []

    def _merge(self, tb, material):
        uv = tb.loops.layers.uv.new("UVMap")
        map_faces(tb.faces, uv, material)
        for face in tb.faces:
            face.material_index = MATERIAL_INDEX[material]
        tmp = bpy.data.meshes.new("tmp")
        tb.to_mesh(tmp)
        tb.free()
        self.bm.from_mesh(tmp)   # appends
        bpy.data.meshes.remove(tmp)

    def box(self, x0, y0, z0, x1, y1, z1, material, bevel=0.0, segments=1):
        """A box; `bevel` rounds its edges (more `segments`: rounder, for cushions). Built in finish()."""
        self.boxes.append({"lo": [min(x0, x1), min(y0, y1), min(z0, z1)], "hi": [max(x0, x1), max(y0, y1), max(z0, z1)],
                           "material": material, "bevel": bevel, "segments": segments})

    def _separate_boxes(self):
        """Keeps the same-direction faces of overlapping boxes SEPARATION apart (see the class comment)."""
        boxes = self.boxes
        eps = 1e-5
        for _ in range(8):
            changed = False
            for j in range(len(boxes)):
                for i in range(j):
                    a, b = boxes[i], boxes[j]      # b was asked for later
                    for axis in range(3):
                        others = [k for k in range(3) if k != axis]
                        if any(min(a["hi"][k], b["hi"][k]) - max(a["lo"][k], b["lo"][k]) <= 1e-6 for k in others):
                            continue                # not overlapping on this face
                        for side, sign in (("hi", 1.0), ("lo", -1.0)):
                            d = (a[side][axis] - b[side][axis]) * sign         # > 0: a's face is further out
                            if abs(d) >= self.SEPARATION - eps:
                                continue
                            # the face that is not further out steps inward; equal planes: the earlier box steps
                            inner, outer = (b, a) if d > eps else (a, b)
                            target = outer[side][axis] - sign * self.SEPARATION
                            lo, hi = list(inner["lo"]), list(inner["hi"])
                            (hi if side == "hi" else lo)[axis] = target
                            if hi[axis] - lo[axis] < 0.003:
                                continue            # never squash a thin box
                            inner[side][axis] = target
                            changed = True
            if not changed:
                return

    def _build_box(self, spec):
        (x0, y0, z0), (x1, y1, z1) = spec["lo"], spec["hi"]
        material, bevel, segments = spec["material"], spec["bevel"], spec["segments"]
        tb = bmesh.new()
        bmesh.ops.create_cube(tb, size=1.0)
        for v in tb.verts:
            v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
            v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
            v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
        if FLAT:
            bevel = 0.0                  # hard edges
        bevel = min(bevel, 0.45 * min(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)))
        if bevel > 0.0005:
            bmesh.ops.bevel(tb, geom=list(tb.edges), offset=bevel, segments=segments, affect="EDGES", profile=0.5)
        bmesh.ops.recalc_face_normals(tb, faces=list(tb.faces))
        self._merge(tb, material)

    def cylinder(self, cx, cy, z0, z1, radius, material, segments=12):
        tb = bmesh.new()
        bmesh.ops.create_cone(tb, cap_ends=True, cap_tris=False, segments=segments,
                              radius1=radius, radius2=radius, depth=abs(z1 - z0))
        for v in tb.verts:
            v.co = Vector((cx + v.co.x, cy + v.co.y, (z0 + z1) / 2 + v.co.z))
        bmesh.ops.recalc_face_normals(tb, faces=list(tb.faces))
        self._merge(tb, material)

    def front_cylinder(self, cx, y0, y1, cz, radius, material, segments=16):
        """Round front-facing furniture hardware, in the same material/UV pipeline."""
        tb = bmesh.new()
        bmesh.ops.create_cone(tb, cap_ends=True, cap_tris=False, segments=segments,
                              radius1=radius, radius2=radius, depth=abs(y1-y0))
        for v in tb.verts:
            v.co = Vector((cx+v.co.x, (y0+y1)/2+v.co.z, cz+v.co.y))
        bmesh.ops.recalc_face_normals(tb, faces=list(tb.faces))
        self._merge(tb, material)

    def brace(self, a, c, width, depth, material):
        """A diagonal front batten between two points; useful for shipping crates."""
        start,end=Vector(a),Vector(c)
        axis=end-start;rotation=axis.to_track_quat('Z','Y')
        tb=bmesh.new();bmesh.ops.create_cube(tb,size=1)
        for v in tb.verts:
            v.co=(start+end)/2+rotation@Vector((v.co.x*width,v.co.y*depth,v.co.z*axis.length))
        bmesh.ops.recalc_face_normals(tb,faces=list(tb.faces))
        self._merge(tb,material)

    def quad(self, corners, material, facing):
        """One polygon (3 or 4 corners) whose normal points along `facing`."""
        verts = [self.bm.verts.new(c) for c in corners]
        face = self.bm.faces.new(verts)
        face.normal_update()
        if face.normal.dot(facing) < 0:
            face.normal_flip()
        map_faces([face], self.uv, material)
        face.material_index = MATERIAL_INDEX[material]
        return face

    def finish(self):
        # (UVBuilder, the shells' builder, borrows this method and collects no boxes)
        if getattr(self, "boxes", None):
            self._separate_boxes()
            for spec in self.boxes:
                self._build_box(spec)
            self.boxes = []
        mesh = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj


# ------------------------------------------------------------------------------------
# RV furniture. Back to +Y, front to -Y, origin on the floor in the middle.
# Each entry: footprint (width x, depth y), height, container capacity, kind.
# ------------------------------------------------------------------------------------

PIECES = {}


def piece(name, width, depth, height, capacity, kind, label):
    def register(fn):
        PIECES[name] = {"build": fn, "width": width, "depth": depth, "height": height,
                        "capacity": capacity, "kind": kind, "label": label}
        return fn
    return register


def handle(b, x, y, z, material="chrome", vertical=True):
    """A bar handle standing out in front of a door or drawer whose face is at y."""
    if vertical:
        b.box(x - 0.008, y - 0.022, z - 0.045, x + 0.008, y - 0.004, z + 0.045, material, bevel=0.003)
    else:
        b.box(x - 0.045, y - 0.022, z - 0.008, x + 0.045, y - 0.004, z + 0.008, material, bevel=0.003)


def front(b, x0, x1, z0, z1, y, material):
    """A door or drawer front on the face at y, with a dark gap all round (a plate behind it, a little larger:
    the game's furniture sprites draw every door and drawer with a dark line round it)."""
    b.box(x0 - 0.004, y - 0.004, z0 - 0.004, x1 + 0.004, y + 0.002, z1 + 0.004, "wood_dark")
    b.box(x0, y - 0.014, z0, x1, y + 0.002, z1, material, bevel=0.006, segments=2)


def plinth(b, x0, x1, y0, y1, height=0.05, material="wood_kick"):
    """The recessed toe kick under a cabinet (the cabinet's wood, a little darker)."""
    b.box(x0, y0, 0.0, x1, y1, height, material)


# Seat and bed surfaces sit at 0.31 above the floor, where KI5's seat positions put a
# sitting or lying character (their cushions were 0.30 to 0.32 high).
@piece("bed", 1.50, 0.55, 0.30, 20, "bed", "RV Bed")
def build_bed(b):
    # A simple bed like the game's own: a wooden base with a bare mattress (no blanket, no pillow).
    b.box(-0.75, -0.26, 0.04, 0.75, 0.275, 0.19, "wood_light", bevel=0.01, segments=2)
    plinth(b, -0.73, 0.73, -0.245, 0.26, 0.04)
    b.box(-0.735, -0.262, 0.19, 0.735, 0.268, 0.28, "sheet", bevel=0.04, segments=3)

@piece("stretcher", 1.50, 0.55, 0.55, 0, "bed", "Medical Stretcher")
def build_stretcher(b):
    # The same painted steel, dark vinyl and bevels as the existing bus seats.
    for x in (-.62, .62):
        for y in (-.19, .19):
            b.box(x-.035, y-.025, 0, x+.035, y+.025, .085, "rubber", bevel=.02, segments=3)
            b.box(x-.018, y-.018, .07, x+.018, y+.018, .40, "steel", bevel=.005)
    b.box(-.69, -.22, .13, .69, .22, .16, "steel", bevel=.008)
    b.box(-.75, -.26, .39, .75, .26, .435, "steel", bevel=.012, segments=2)
    b.box(-.72, -.245, .435, .72, .245, .53, "mattress", bevel=.025, segments=3)
    for y in (-.264, .264):
        b.box(-.52, y-.008, .53, .52, y+.008, .55, "chrome", bevel=.006)
    for x in (-.30, .30):
        b.box(x-.025, -.248, .531, x+.025, .248, .536, "black", bevel=.003)


@piece("metalcase", .52, .52, .80, 25, "storage", "Steel Equipment Cabinet")
def build_metalcase(b):
    b.box(-.26, -.235, .04, .26, .26, .77, "steel", bevel=.008, segments=2)
    plinth(b, -.245, .245, -.22, .245, .04, "black")
    b.box(-.26, -.26, .77, .26, .26, .80, "steel", bevel=.009, segments=2)
    for z0, z1 in ((.06,.28),(.295,.515),(.53,.75)):
        b.box(-.247, -.248, z0-.003, .247, -.234, z1+.003, "black")
        b.box(-.24, -.258, z0, .24, -.247, z1, "steel", bevel=.005, segments=2)
        handle(b, 0, -.255, (z0+z1)/2, vertical=False)


@piece("safe", .60, .52, .90, 45, "storage", "Armored Cash Safe")
def build_safe(b):
    b.box(-.30,-.235,.035,.30,.26,.90,"trim",bevel=.012,segments=2)
    plinth(b,-.285,.285,-.22,.245,.055,"black")
    b.box(-.275,-.25,.085,.275,-.234,.86,"black",bevel=.006)
    b.box(-.26,-.259,.10,.26,-.249,.845,"heater_body",bevel=.01,segments=2)
    for z in (.23,.70): b.box(.246,-.26,z-.055,.283,-.23,z+.055,"chrome",bevel=.01,segments=2)
    b.front_cylinder(-.045,-.259,-.245,.51,.052,"chrome")
    b.front_cylinder(-.045,-.26,-.259,.51,.030,"black")
    b.box(-.10,-.26,.31,.10,-.245,.335,"chrome",bevel=.01,segments=3)


@piece("parcels", .60, .50, .85, 45, "storage", "Stacked Delivery Parcels")
def build_parcels(b):
    for x0,x1,z0,z1,mat in ((-.298,-.008,0,.43,"cardboard"),(.008,.298,0,.43,"cardboard_dark"),(-.285,.285,.435,.845,"cardboard_light")):
        b.box(x0,-.244,z0,x1,.244,z1,mat,bevel=.009,segments=2)
        mid=(x0+x1)/2
        b.box(mid-.018,-.247,z1-.11,mid+.018,-.241,z1+.002,"tape")
        b.box(mid-.018,-.246,z1-.002,mid+.018,.246,z1+.003,"tape")


@piece("hamradio", .36, .24, .40, 0, "model", "HAM Radio Visual Adapter")
def build_hamradio(b):
    # Model-only appearance for the real Base.HamRadio1 item; never factory furniture.
    # ImageGen concept exec-52c3bdb2-f11c-4bfc-af80-d2e4239d36b3: worn grey
    # transceiver, black grille and knobs, dull screen, carry handle and rear aerial.
    for x in (-.145, .145):
        for y in (-.055, .088):
            b.cylinder(x, y, 0, .031, .017, "rubber")
    b.box(-.18, -.086, .025, .18, .12, .245, "steel", bevel=.009, segments=2)
    b.box(-.172, -.098, .037, .172, -.084, .233, "black", bevel=.005, segments=2)
    # The grille is recessed behind dark horizontal ribs, with a readable border.
    b.box(-.160, -.102, .070, -.052, -.097, .216, "rubber", bevel=.003)
    for z in (.078, .096, .114, .132, .150, .168, .186, .204):
        b.box(-.155, -.105, z, -.057, -.101, z+.006, "trim", bevel=.001)
    b.box(-.031, -.104, .156, .083, -.097, .218, "trim", bevel=.003)
    b.box(-.024, -.106, .163, .076, -.103, .211, "busvinyl", bevel=.002)
    for x in (-.020, .032, .084):
        b.front_cylinder(x, -.103, -.097, .104, .016, "steel")
        b.front_cylinder(x, -.117, -.102, .104, .013, "black")
        b.box(x-.0015, -.120, .109, x+.0015, -.116, .115, "chrome")
    b.front_cylinder(.133, -.103, -.097, .128, .034, "steel", segments=20)
    b.front_cylinder(.133, -.117, -.102, .128, .030, "black", segments=20)
    b.box(.131, -.120, .145, .135, -.116, .153, "chrome")
    for x in (-.163, .163):
        for z in (.048, .222):
            b.front_cylinder(x, -.103, -.098, z, .004, "chrome", segments=8)
    for x in (-.098, .098):
        b.box(x-.013, -.027, .242, x+.013, .012, .279, "steel", bevel=.004)
    b.box(-.098, -.020, .263, .098, .005, .284, "black", bevel=.006, segments=2)
    b.cylinder(.150, .088, .244, .266, .012, "steel")
    b.cylinder(.150, .088, .260, .394, .0055, "black")
    b.cylinder(.150, .088, .391, .400, .0065, "rubber")
    # Loose items use the game's ground-model frame, not furniture's wall frame.
    # The native C workbench view exposed the rear at its chosen packing yaw;
    # face the controls into the aisle without changing other world-item poses.
    # Turn around the footprint centre before main() shifts the furniture origin.
    for spec in b.boxes:
        for axis in (0, 1):
            spec["lo"][axis], spec["hi"][axis] = -spec["hi"][axis], -spec["lo"][axis]
    for v in b.bm.verts:
        v.co.x = -v.co.x
        v.co.y = -v.co.y


@piece("workbench", .90, .40, .78, 30, "storage", "Service Workbench")
def build_workbench(b):
    # Compact mobile workshop furniture; the actual stored tools/radios are
    # drawn on the empty top by the shared container-content renderer.
    for x in (-.44,.412):
        for y in (-.19,.162):
            b.box(x,y,0,x+.028,y+.028,.74,"steel",bevel=.004)
            b.box(x-.003,y-.003,0,x+.031,y+.031,.018,"black",bevel=.004)
    b.box(-.425,-.177,.075,.425,.177,.098,"steel",bevel=.004)
    b.box(-.438,-.18,.565,.438,.185,.735,"steel",bevel=.005)
    for x0,x1 in ((-.422,-.008),(.008,.422)):
        b.box(x0,-.194,.579,x1,-.179,.718,"black",bevel=.004)
        b.box(x0+.006,-.199,.585,x1-.006,-.191,.712,"steel",bevel=.005)
        handle(b,(x0+x1)/2,-.192,.65,vertical=False)
    b.box(-.45,-.20,.735,.45,.20,.765,"wood_birch",bevel=.006,segments=2)
    b.box(-.447,.184,.765,.447,.20,.78,"steel",bevel=.003)


@piece("medlocker", .50, .32, .98, 35, "storage", "Medical Supply Cabinet")
def build_medlocker(b):
    b.box(-.25,.125,.025,.25,.16,.98,"paint_white",bevel=.006)
    for x in (-.25,.228):b.box(x,-.145,.025,x+.022,.15,.98,"paint_white",bevel=.004)
    for z in (.025,.36,.65,.957):b.box(-.25,-.145,z,.25,.15,z+.023,"paint_white",bevel=.004)
    front(b,-.228,.228,.05,.33,-.139,"paint_white");handle(b,.17,-.139,.21)
    # Empty boards: the client renders the container's actual items on them.
    for z in (.39,.68):
        b.box(-.23,-.154,z+.04,.23,-.14,z+.058,"chrome",bevel=.004)


@piece("medbench", 1.10, .40, .80, 25, "seat", "Utility Bench Seat")
def build_medbench(b):
    b.box(-.55,-.21,.025,.55,.225,.215,"paint_white",bevel=.009,segments=2)
    for x in (-.535,.008):
        front(b,x,x+.527,.045,.19,-.21,"steel")
        handle(b,x+.263,-.21,.12,vertical=False)
        b.box(x,-.217,.215,x+.527,.20,.31,"mattress",bevel=.026,segments=3)
        b.box(x,.147,.315,x+.527,.223,.79,"mattress",bevel=.022,segments=3)
        b.box(x+.23,-.218,.311,x+.26,.16,.317,"black")
        b.box(x+.222,-.11,.317,x+.27,-.075,.325,"chrome",bevel=.004)
    b.box(-.55,.213,.30,.55,.225,.80,"steel",bevel=.006)
    # A compact side-facing seat leaves a 0.35m aisle in the narrow ambulances.
    for box in b.boxes:
        box['lo'][1] *= .40/.45
        box['hi'][1] *= .40/.45


@piece("equipmentrack", .60, .32, .98, 40, "storage", "Equipment Rack")
def build_equipmentrack(b):
    for x in (-.30,.275):
        for y in (-.15,.135):b.box(x,y,0,x+.025,y+.025,.98,"steel",bevel=.003)
    for z in (.03,.34,.65,.955):b.box(-.30,-.15,z,.30,.16,z+.022,"steel",bevel=.004)
    for z in (.055,.365,.675):
        b.box(-.285,-.156,z+.09,.285,-.14,z+.11,"chrome",bevel=.004)


@piece("dinette", 1.12, 0.55, 0.72, 15, "seat", "RV Dinette")
def build_dinette(b):
    # Two booth benches facing each other along the wall (seats 0.79 apart, like KI5's):
    # thick vinyl seat cushions, backrests in three tufted channels, wooden end panels
    # on the aisle side; a laminate table with a chrome edge on a pedestal between.
    board = 0.03          # the backboard behind the backrest cushions: they sit against it, nothing stands free
    for s in (-1, 1):
        x0, x1 = (0.23, 0.56) if s > 0 else (-0.56, -0.23)
        back0, back1 = (x1 - 0.13, x1 - board) if s > 0 else (x0 + board, x0 + 0.13)
        b.box(x0, -0.24, 0.05, x1, 0.275, 0.20, "wood_light", bevel=0.008)
        plinth(b, x0 + 0.01, x1 - 0.01, -0.225, 0.26)
        sx0, sx1 = (x0 + 0.005, x1 - board) if s > 0 else (x0 + board, x1 - 0.005)
        b.box(sx0, -0.255, 0.20, sx1, 0.27, 0.31, "fabric_blue", bevel=0.035, segments=3)
        for y0, y1 in ((-0.255, -0.08), (-0.08, 0.095), (0.095, 0.27)):
            b.box(back0, y0, 0.30, back1, y1, 0.665, "fabric_blue", bevel=0.035, segments=3)
        wx0, wx1 = (x1 - board, x1) if s > 0 else (x0, x0 + board)
        b.box(wx0, -0.256, 0.20, wx1, 0.275, 0.72, "wood_light", bevel=0.01, segments=2)        # the backboard
        rx0, rx1 = (back0, x1 - 0.003) if s > 0 else (x0 + 0.003, back1)       # 3 mm short of the board's end
        b.box(rx0, -0.2535, 0.665, rx1, 0.2725, 0.715, "wood_light", bevel=0.012, segments=2)   # top rail over the cushions
        b.box(x0, -0.278, 0.0, x1, -0.256, 0.33, "wood_light", bevel=0.01, segments=2)          # end panel, seat
        b.box(rx0, -0.278, 0.0, rx1, -0.256, 0.70, "wood_light", bevel=0.02, segments=3)        # end panel, back
    b.box(-0.21, -0.225, 0.56, 0.21, 0.275, 0.595, "laminate", bevel=0.012, segments=2)
    b.box(-0.214, -0.229, 0.552, 0.214, 0.275, 0.566, "chrome", bevel=0.004)
    b.cylinder(0.0, 0.02, 0.02, 0.552, 0.028, "chrome", segments=12)
    b.cylinder(0.0, 0.02, 0.0, 0.02, 0.11, "chrome", segments=16)

@piece("kitchen", 1.00, 0.52, 0.92, 30, "kitchen", "RV Kitchenette")
def build_kitchen(b):
    # Cabinets with doors and drawers, a laminate counter with a chrome edge and a
    # backsplash, a two-burner stove on the left and a steel sink on the right.
    b.box(-0.50, -0.235, 0.05, 0.50, 0.26, 0.80, "wood_light", bevel=0.014, segments=2)
    plinth(b, -0.49, 0.49, -0.22, 0.25)
    for x0, x1 in ((-0.485, -0.008), (0.008, 0.485)):
        front(b, x0, x1, 0.07, 0.635, -0.235, "wood_birch")
        front(b, x0, x1, 0.655, 0.775, -0.235, "wood_birch")
        handle(b, x1 - 0.05 if x0 < 0 else x0 + 0.05, -0.249, 0.55)
        handle(b, (x0 + x1) / 2, -0.249, 0.715, vertical=False)
    b.box(-0.50, -0.265, 0.80, 0.50, 0.265, 0.845, "laminate", bevel=0.014, segments=3)
    b.box(-0.50, -0.27, 0.80, 0.50, -0.255, 0.845, "chrome", bevel=0.004)
    b.box(-0.50, 0.235, 0.845, 0.50, 0.265, 0.905, "laminate", bevel=0.006, segments=2)
    b.box(-0.47, -0.22, 0.845, -0.05, 0.215, 0.856, "steel", bevel=0.004)
    for cx in (-0.36, -0.16):
        b.cylinder(cx, -0.01, 0.856, 0.862, 0.075, "burner", segments=18)
        b.cylinder(cx, -0.01, 0.862, 0.870, 0.028, "black", segments=12)
        b.box(cx - 0.085, -0.018, 0.866, cx + 0.085, -0.002, 0.878, "black")     # grate
        b.box(cx - 0.008, -0.095, 0.866, cx + 0.008, 0.075, 0.878, "black")
    for x in (-0.40, -0.31, -0.22, -0.13):
        b.cylinder(x, -0.185, 0.856, 0.876, 0.014, "chrome", segments=10)
    b.box(0.04, -0.20, 0.845, 0.46, 0.20, 0.849, "steel", bevel=0.004)
    b.box(0.08, -0.16, 0.838, 0.42, 0.16, 0.850, "basin")
    b.cylinder(0.25, 0.205, 0.849, 0.915, 0.015, "chrome", segments=10)
    b.box(0.237, 0.10, 0.900, 0.263, 0.215, 0.917, "chrome", bevel=0.004)
    b.cylinder(0.32, 0.205, 0.849, 0.89, 0.012, "chrome", segments=8)


@piece("fridge", 0.52, 0.52, 0.88, 30, "fridge", "RV Fridge")
def build_fridge(b):
    # A rounded 1950s enamel fridge: a freezer door over the main door, chrome lever
    # handles on the left, hinges on the right, a chrome base.
    b.box(-0.26, -0.235, 0.05, 0.26, 0.26, 0.88, "enamel", bevel=0.04, segments=3)
    b.box(-0.245, -0.22, 0.0, 0.245, 0.245, 0.05, "chrome", bevel=0.008)
    front(b, -0.248, 0.248, 0.075, 0.62, -0.235, "enamel")
    front(b, -0.248, 0.248, 0.635, 0.86, -0.235, "enamel")
    b.box(-0.248, -0.2365, 0.620, 0.248, -0.2340, 0.635, "shadow")      # the seam between the two doors
    handle(b, -0.14, -0.249, 0.54, vertical=False)
    handle(b, -0.14, -0.249, 0.78, vertical=False)
    for z in (0.14, 0.52, 0.70):
        b.box(0.238, -0.256, z, 0.256, -0.24, z + 0.07, "chrome", bevel=0.004)
    # its back, seen over a cut-away wall: the black condenser grille with its tubes, the compressor below
    b.box(-0.20, 0.255, 0.20, 0.20, 0.266, 0.80, "black")
    for i in range(10):
        z = 0.235 + i * 0.058
        b.box(-0.19, 0.266, z, 0.19, 0.271, z + 0.012, "steel")
    b.box(-0.13, 0.20, 0.0, 0.13, 0.27, 0.15, "black", bevel=0.01)

@piece("wardrobe", 0.52, 0.52, 0.90, 40, "storage", "RV Wardrobe")
def build_wardrobe(b):
    # Two tall doors with raised panels, a crown on top and a recessed plinth.
    b.box(-0.26, -0.235, 0.05, 0.26, 0.26, 0.87, "wood_dark", bevel=0.01)
    plinth(b, -0.25, 0.25, -0.22, 0.25, material="wood_dark")
    b.box(-0.26, -0.255, 0.87, 0.26, 0.27, 0.90, "wood_dark", bevel=0.008, segments=2)
    for x0, x1 in ((-0.248, -0.004), (0.004, 0.248)):
        front(b, x0, x1, 0.065, 0.855, -0.235, "wood_dark")
        b.box(x0 + 0.03, -0.256, 0.10, x1 - 0.03, -0.246, 0.45, "wood_dark", bevel=0.008, segments=2)
        b.box(x0 + 0.03, -0.256, 0.48, x1 - 0.03, -0.246, 0.82, "wood_dark", bevel=0.008, segments=2)
    handle(b, -0.035, -0.249, 0.47)
    handle(b, 0.035, -0.249, 0.47)


@piece("cabinet", 0.52, 0.52, 0.80, 25, "storage", "RV Cabinet")
def build_cabinet(b):
    # Three wooden drawers with chrome pulls under a thick laminate top, on a plinth.
    b.box(-0.26, -0.235, 0.05, 0.26, 0.26, 0.75, "wood_light", bevel=0.008)
    plinth(b, -0.25, 0.25, -0.22, 0.25)
    b.box(-0.26, -0.27, 0.75, 0.26, 0.268, 0.80, "laminate", bevel=0.014, segments=3)
    for z0, z1 in ((0.065, 0.28), (0.295, 0.51), (0.525, 0.74)):
        front(b, -0.248, 0.248, z0, z1, -0.235, "wood_light")
        handle(b, 0.0, -0.249, (z0 + z1) / 2, vertical=False)

@piece("washroom", 1.00, 0.52, 0.90, 10, "washroom", "RV Washroom")
def build_washroom(b):
    # Low cubicle walls (open at the top so you can see in from above), a door, a
    # toilet and a small basin.
    b.box(-0.50, 0.22, 0.00, 0.50, 0.26, 0.90, "paint_white", bevel=0.006)
    b.box(-0.50, -0.25, 0.00, -0.46, 0.26, 0.90, "paint_white", bevel=0.006)
    b.box(0.46, -0.25, 0.00, 0.50, 0.26, 0.90, "paint_white", bevel=0.006)
    b.box(-0.46, -0.25, 0.00, 0.0, -0.21, 0.90, "paint_white", bevel=0.006)
    b.box(-0.50, -0.255, 0.88, 0.50, 0.265, 0.90, "wood_light", bevel=0.005)          # top rail
    front(b, 0.005, 0.455, 0.02, 0.87, -0.225, "wood_birch")
    handle(b, 0.06, -0.239, 0.45)
    b.box(-0.46, -0.21, 0.0, 0.46, 0.22, 0.012, "floor_lino")
    b.box(-0.36, 0.09, 0.012, -0.10, 0.22, 0.42, "enamel", bevel=0.025, segments=2)       # cistern
    b.cylinder(-0.23, -0.01, 0.012, 0.30, 0.11, "enamel", segments=18)
    b.cylinder(-0.23, -0.01, 0.30, 0.32, 0.12, "paint_white", segments=18)
    b.box(0.12, 0.06, 0.55, 0.42, 0.22, 0.60, "enamel", bevel=0.015, segments=2)          # basin
    b.cylinder(0.27, 0.19, 0.60, 0.68, 0.012, "chrome", segments=8)


@piece("heater", 0.52, 0.32, 0.62, 0, "heater", "RV Propane Heater")
def build_heater(b):
    # A brown enamel heater on four feet: a chrome bar grille over a glowing window,
    # side vents, a copper top with a knob.
    b.box(-0.25, -0.14, 0.05, 0.25, 0.16, 0.55, "heater_body", bevel=0.02, segments=2)
    for x in (-0.22, 0.22):
        for y in (-0.11, 0.13):
            b.box(x - 0.025, y - 0.025, 0.0, x + 0.025, y + 0.025, 0.05, "black", bevel=0.008)
    b.box(-0.26, -0.152, 0.55, 0.26, 0.172, 0.59, "copper", bevel=0.012, segments=2)
    b.box(-0.19, -0.146, 0.12, 0.19, -0.138, 0.44, "shadow")
    b.box(-0.13, -0.142, 0.18, 0.13, -0.136, 0.36, "bulb")
    for i in range(8):
        z = 0.14 + i * 0.041
        b.box(-0.19, -0.156, z - 0.008, 0.19, -0.144, z + 0.008, "chrome", bevel=0.003)
    for side in (-1, 1):
        for i in range(4):
            y = -0.08 + i * 0.045
            b.box(side * 0.25 - 0.004, y - 0.008, 0.40, side * 0.25 + 0.004, y + 0.008, 0.49, "shadow")
    b.cylinder(0.14, 0.05, 0.59, 0.62, 0.028, "black", segments=12)


@piece("shelf", 0.52, 0.32, 0.90, 0, "shelf", "RV Shelf Unit")
def build_shelf(b):
    # An open shelving unit for the things you collect: two wooden side panels, a thin dark back board, three
    # boards (the lowest just above the recessed plinth, the highest the top) and a low rail along the front of
    # the lower two, so things stay put when the camper moves. Two roomy compartments (a plush fits): the boards'
    # tops are at 0.09, 0.47 and 0.90 (MELens_Loose.lua's surfaces read them off).
    for x0, x1 in ((-0.26, -0.24), (0.24, 0.26)):
        b.box(x0, -0.16, 0.0, x1, 0.16, 0.875, "wood_light", bevel=0.006, segments=2)
    plinth(b, -0.24, 0.24, -0.14, 0.15, 0.05)
    b.box(-0.24, 0.146, 0.05, 0.24, 0.16, 0.875, "wood_dark")           # the back board
    for top in (0.090, 0.470):
        b.box(-0.24, -0.155, top - 0.025, 0.24, 0.150, top, "wood_light", bevel=0.005, segments=2)
        b.box(-0.24, -0.155, top, 0.24, -0.141, top + 0.022, "wood_dark", bevel=0.004)      # the rail
    b.box(-0.26, -0.16, 0.875, 0.26, 0.165, 0.90, "wood_light", bevel=0.008, segments=2)    # the top board


def carton(b):
    """A closed plain cardboard box in its 0.5 x 0.5 x 0.4 place, a little smaller (0.488 x 0.488 x
    0.392: a centimetre of air between boxes shows as a dark line where they stand side by side and where
    they are stacked), with flap tape over the top and down the front and back. Every box is this one
    model, with no labels or markings: a stack of them reads as boxes by their edges. The front (-y)
    faces the aisle."""
    w, h = 0.244, 0.392
    b.box(-w, -w, 0.0, w, w, h, "cardboard", bevel=0.010, segments=2)
    # flap tape: over the top from the front to the back, down both of those faces
    b.box(-0.022, -w - 0.003, h - 0.004, 0.022, w + 0.003, h + 0.003, "tape")
    b.box(-0.022, -w - 0.003, h - 0.12, 0.022, -w + 0.001, h - 0.002, "tape")
    b.box(-0.022, w - 0.001, h - 0.12, 0.022, w + 0.003, h - 0.002, "tape")


@piece("box", 0.50, 0.50, 0.40, 20, "box", "Cargo Box")
def build_box(b):
    # Cargo: a plain cardboard box. Every box is this size and this model, so they stack up to three
    # high in a box truck (each its own storage, with loot inside).
    carton(b)


def bench(b, cx, mirror):
    """A school bus bench seat, 0.75 along the wall, across 0.8 from it, facing +x (the
    piece's length; the bus's front on the left wall) or -x when mirrored (right wall):
    the seat 0.33 high, the backrest at its rear end, a steel frame and one leg."""
    s = -1.0 if mirror else 1.0

    def bx(xa, xb, y0, z0, y1, z1, material, **kw):
        b.box(min(cx + s * xa, cx + s * xb), y0, z0, max(cx + s * xa, cx + s * xb), y1, z1, material, **kw)
    bx(-0.24, 0.125, -0.385, 0.25, 0.385, 0.33, "busvinyl", bevel=0.03, segments=3)        # seat
    bx(-0.34, -0.24, -0.385, 0.30, 0.385, 0.83, "busvinyl", bevel=0.035, segments=3)       # backrest cushion
    bx(-0.375, -0.34, -0.39, 0.22, 0.39, 0.84, "trim", bevel=0.01, segments=2)             # back frame behind it
    bx(-0.375, -0.335, -0.36, 0.82, 0.36, 0.853, "chrome", bevel=0.008, segments=2)        # grab rail along the top
    bx(-0.375, -0.34, -0.385, 0.0, -0.33, 0.30, "chrome", bevel=0.006)                     # rear post, aisle end
    bx(-0.375, -0.34, 0.33, 0.0, 0.385, 0.30, "chrome", bevel=0.006)                       # rear post, wall end
    bx(-0.24, 0.10, -0.36, 0.19, 0.36, 0.25, "steel", bevel=0.006)                         # seat frame
    bx(-0.06, 0.0, -0.37, 0.0, -0.31, 0.19, "chrome", bevel=0.006)                         # leg, aisle end
    bx(-0.16, 0.10, -0.37, 0.0, -0.31, 0.03, "chrome", bevel=0.006)                        # foot
    bx(-0.10, 0.10, 0.37, 0.12, 0.40, 0.24, "chrome", bevel=0.004)                         # wall bracket


@piece("busseat", 0.75, 0.80, 0.85, 0, "seat", "Bus Seat")
def build_busseat(b):
    bench(b, 0.0, False)


@piece("busseat2", 1.50, 0.80, 0.85, 0, "seat", "Bus Seats")
def build_busseat2(b):
    bench(b, -0.375, False)
    bench(b, 0.375, False)


# Mirrored bus seats for right-hand walls (a spot's length runs to the back there), so
# every bench faces the front. Models only: the items are busseat and busseat2.
@piece("busseat_r", 0.75, 0.80, 0.85, 0, "model", "Bus Seat")
def build_busseat_r(b):
    bench(b, 0.0, True)


@piece("busseat2_r", 1.50, 0.80, 0.85, 0, "model", "Bus Seats")
def build_busseat2_r(b):
    bench(b, -0.375, True)
    bench(b, 0.375, True)

# ------------------------------------------------------------------------------------
# Inside shells, fitted to the measured outline of each camper (measure_shell.py).
# ------------------------------------------------------------------------------------

class UVBuilder:
    """A mesh with explicit UVs, for models with their own unwrapped texture."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")

    def poly(self, corners, uvs, facing):
        verts = [self.bm.verts.new(c) for c in corners]
        face = self.bm.faces.new(verts)
        face.normal_update()
        if face.normal.dot(facing) < 0:
            face.normal_flip()
        by_vert = dict(zip(verts, uvs))
        for loop in face.loops:
            loop[self.uv].uv = by_vert[loop.vert]
        return face

    def finish(self):
        return Builder.finish(self)


def smooth_noise(rng, h, w, cell):
    """Low-frequency noise in [0, 1]: a coarse random grid, bilinearly enlarged."""
    gh, gw = int(h / cell) + 3, int(w / cell) + 3
    g = rng.random((gh, gw))
    ys = np.linspace(0, gh - 2.001, h)
    xs = np.linspace(0, gw - 2.001, w)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    a, b = g[y0][:, x0], g[y0][:, x0 + 1]
    c, d = g[y0 + 1][:, x0], g[y0 + 1][:, x0 + 1]
    return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy


def save_image(name, pixels_rgb, path):
    """pixels_rgb: (rows, cols, 3), row 0 at the bottom (Blender's order)."""
    h, w, _ = pixels_rgb.shape
    rgba = np.ones((h, w, 4))
    rgba[..., :3] = np.clip(pixels_rgb, 0.0, 1.0)
    img = bpy.data.images.new(name, width=w, height=h, alpha=True)
    img.pixels = rgba.flatten().tolist()
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img


def pixelate(rgb, mask, block, rng):
    """The baked texture as fine pixels like the game's sprites (about two screen pixels each, measured against a
    vanilla bed: much finer than first tried, coarse blocks looked like a different game): block x block
    averages, a dark outline one pixel wide along the edge of every face (the border of a UV island) and
    grain per pixel."""
    h, w, _ = rgb.shape
    ph, pw = -h % block, -w % block
    img = np.pad(rgb, ((0, ph), (0, pw), (0, 0)), mode="edge")
    m = np.pad(mask, ((0, ph), (0, pw)), mode="edge")
    bh, bw = img.shape[0] // block, img.shape[1] // block
    small = img.reshape(bh, block, bw, block, 3).mean(axis=(1, 3))
    cover = m.reshape(bh, block, bw, block).mean(axis=(1, 3)) > 0.5
    inner = cover.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        inner &= np.roll(cover, (dy, dx), axis=(0, 1))
    small = np.where((cover & ~inner)[..., None], small * 0.62, small)
    small = small * (1.0 + (rng.random((bh, bw, 1)) - 0.5) * 0.02)   # (more grain was "annoying to look at")
    big = np.repeat(np.repeat(small, block, axis=0), block, axis=1)[:h, :w]
    return big


def edge_distance(points, polygon):
    """Distance (tiles) from each point to the nearest edge of a closed polygon."""
    px, py = points[..., 0], points[..., 1]
    best = np.full(px.shape, 1e9)
    n = len(polygon)
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy or 1e-9
        t = np.clip(((px - ax) * dx + (py - ay) * dy) / L, 0.0, 1.0)
        d = np.hypot(px - (ax + t * dx), py - (ay + t * dy))
        best = np.minimum(best, d)
    return best


def floor_texture(path, bounds, outline, rng, style):
    """Staggered planks along the camper's length, with grain, seams, wear and darker edges.
    bounds: (xmin, xmax, zmin, zmax) in passenger space; texture x = width, y = length."""
    xmin, xmax, zmin, zmax = bounds
    W, H = style.get("floorSize", (512, 1024))
    if style.get("flat", FLAT):
        # The floor as flat pixel art: a generated tile of boards (tools-src/art/generate.ps1, px_*), laid
        # along the vehicle's length and repeated with hard pixels; no soft shadow at the walls.
        gx = xmin + (np.arange(W) + 0.5) * (xmax - xmin) / W
        gz = zmin + (np.arange(H) + 0.5) * (zmax - zmin) / H
        art = load_art(style.get("floorArt", "px_floor_planks"))
        tile = style.get("floorTile", 1.4)
        img = tile_art(art, gx / tile, gz / tile) * style.get("floorBrightness", 1.0)
        return save_image(os.path.basename(path)[:-4], img, path)
    ppx = W / (xmax - xmin)          # pixels per tile across
    ppz = H / (zmax - zmin)          # pixels per tile along
    img = np.zeros((H, W, 3))
    base = np.array(style.get("wood", (0.50, 0.36, 0.23)))
    plank_w = style.get("plankWidth", 0.12)
    cols = int(math.ceil((xmax - xmin) / plank_w))
    grain_noise = smooth_noise(rng, H, W, 18)
    ys = np.arange(H)[:, None]
    xs = np.arange(W)[None, :]
    for c in range(cols):
        x0 = int(round(c * plank_w * ppx))
        x1 = min(W, int(round((c + 1) * plank_w * ppx)))
        pos = -rng.uniform(0.0, 1.3)
        while pos < (zmax - zmin):
            length = rng.uniform(0.9, 1.7)
            y0 = max(0, int(round(pos * ppz)))
            y1 = min(H, int(round((pos + length) * ppz)))
            if y1 > y0 and x1 > x0:
                tone = base * rng.uniform(0.86, 1.10) * np.array([1.0, rng.uniform(0.96, 1.04), rng.uniform(0.93, 1.05)])
                gx = xs[:, x0:x1] - x0
                gy = ys[y0:y1]
                grain = 0.5 + 0.5 * np.sin(gx * rng.uniform(0.8, 1.3) + 5.0 * grain_noise[y0:y1, x0:x1] + gy * 0.01)
                shade = 0.93 + 0.07 * grain
                img[y0:y1, x0:x1] = tone[None, None, :] * shade[..., None]
                img[y0:min(y0 + 2, H), x0:x1] *= 0.62          # plank end seam
            pos += length
        img[:, x0:min(x0 + 2, W)] *= 0.58                     # long seam
    wear = smooth_noise(rng, H, W, 90)
    img *= (0.94 + 0.10 * wear)[..., None]
    gx = xmin + (np.arange(W) + 0.5) / ppx
    gz = zmin + (np.arange(H) + 0.5) / ppz
    # The painted plank floor (art), laid along the camper's length, when there is one.
    art = load_art(style.get("floorArt", "floor_planks"))
    if art is not None:
        tile = style.get("floorTile", 0.9)
        img = grade(tile_art(art, gx / tile, gz / tile), style.get("floorTint")) * style.get("floorBrightness", 1.0)
    # a little darker next to the walls (soft contact shadow)
    pts = np.stack(np.meshgrid(gx, gz), axis=-1)
    d = edge_distance(pts, outline)
    img *= (1.0 - 0.18 * np.exp(-d / 0.08))[..., None]
    return save_image(os.path.basename(path)[:-4], img, path)


# The wall texture's rows above the highest wall cut are never seen on the walls (the
# walls are only drawn in the camper you are in, cut at most 1.05 above the floor), so
# they hold swatches for the wheel-well boxes and the utility panel: (u0, v0, u1, v1).
SWATCH = {
    "metal": (0.10, 0.66, 0.45, 0.90),       # brushed metal: the wheel-well boxes, one face each
    "liner": (0.10, 0.93, 0.90, 0.97),       # dark: inside the wheel wells, seen through the arches
    "plate": (0.030, 0.74, 0.040, 0.78),     # the utility panel's edges
    "panel": (0.0005, 0.70, 0.0225, 0.82),   # the utility panel's face (45 x 31 px)
}


def swatch_uv(name, s, t):
    u0, v0, u1, v1 = SWATCH[name]
    return (u0 + (u1 - u0) * s, v0 + (v1 - v0) * t)


def wall_uv(u, v):
    # The atlas also contains wheel-house, liner and control-panel swatches.
    # Plain walls must never sample those patches, even above a high wall cut
    # or below the floor on a rear-door skirt.
    return (.50 + .48 * min(1, max(0, u)), .02 + .88 * min(1, max(0, v)))


def wall_texture(path, perimeter, height, rng, style):
    """Plain painted walls with a wooden baseboard; x = along the wall, y = up. Plus the
    swatches above (row 0 is the floor)."""
    W, H = style.get("wallSize", (2048, 256))
    ppv = H / height
    ppu = W / perimeter
    u = (np.arange(W) + 0.5) / ppu
    v = (np.arange(H) + 0.5) / ppv
    flat = style.get("flat", FLAT)
    paint = np.array(style.get("paint", (0.86, 0.84, 0.79)))
    painted = load_art(style.get("wallArt", "px_wall_cream" if flat else "wall_paint"))
    if painted is not None:
        tile = style.get("wallTile", 0.8)
        img = grade(tile_art(painted, u / tile, v / tile), style.get("wallTint")) * style.get("wallBrightness", 1.0)
        panel = style.get("panelWidth")
        if panel and not flat:
            # the joints between wall panels: a soft dark groove with a lit edge beside it
            d = np.mod(u, panel) * ppu                                      # pixels past the last joint
            groove = np.exp(-(d / 1.2) ** 2) + np.exp(-((panel * ppu - d) / 1.2) ** 2)
            lit = np.exp(-((d - 2.5) / 1.0) ** 2)
            img *= (1.0 - 0.30 * groove + 0.06 * lit)[None, :, None]
    else:
        img = np.ones((H, W, 3)) * paint
        img *= (0.975 + 0.035 * smooth_noise(rng, H, W, 140))[..., None]   # barely-there unevenness
    base_h = style.get("baseboard", 0.07)
    wood = np.array(style.get("baseboardColour", (0.46, 0.33, 0.21)))
    board = v < base_h
    rows = int(board.sum())
    if rows:
        dark = None if flat else load_art(style.get("baseboardArt", "wood_dark"))
        if dark is not None:
            img[board] = grade(tile_art(dark, u / 0.5, v[board] / 0.5), style.get("baseboardColour"))
        elif flat:
            img[board] = wood[None, None, :]                        # one flat colour, a lighter line on top
            img[(v >= base_h - 1.5 / ppv) & board] = np.clip(wood * 1.35, 0.0, 1.0)
        else:
            img[board] = wood[None, None, :] * (0.95 + 0.08 * smooth_noise(rng, rows, W, 24))[..., None]
        if not flat:
            img[np.abs(v - base_h) * ppv < 1.0] *= 0.78            # shadow line on top of the board
    if not flat:
        img *= (1.0 - 0.20 * np.exp(-v / 0.09))[:, None, None]    # soft contact shadow at the floor

    def region(name):
        u0, v0, u1, v1 = SWATCH[name]
        return slice(int(v0 * H), int(math.ceil(v1 * H))), slice(int(u0 * W), int(math.ceil(u1 * W)))

    # A wheel-well face: aluminium diamond plate, a thin dark seam round the edge and a
    # light fold just inside it, like a sheet-metal box. The swatch stands for a face of
    # about 0.68 x 0.26 tiles (s along it, t across or up it).
    r, c = region("metal")
    rows, cols = r.stop - r.start, c.stop - c.start
    s = (np.arange(cols) + 0.5) / cols
    t = (np.arange(rows) + 0.5) / rows
    if flat:
        # flat sheet metal: one grey, a dark seam round the edge and a light fold just inside it
        metal = np.ones((rows, cols, 3)) * np.array(style.get("metal", (0.66, 0.69, 0.72)))
    else:
        plate = load_art("diamondplate")
        if plate is None:
            plate = load_art("steel")
        if plate is not None:
            metal = tile_art(plate, s * 0.68 / 0.30, t * 0.26 / 0.30)
        else:
            metal = np.ones((rows, cols, 3)) * np.array((0.64, 0.65, 0.66))
    edge = np.minimum.outer(np.minimum(t, 1.0 - t) * 0.26, np.minimum(s, 1.0 - s) * 0.68)   # tiles to the nearest edge
    metal *= np.where(edge < 0.006, 0.72, np.where(edge < 0.02, 1.12, 1.0))[..., None]
    img[r, c] = metal
    r, c = region("liner")
    # (near black: lit by the room's light it must still read as the dark inside of the wheel house, KI5's own
    # being black, where a plate's end shows beside the tyre through the arch)
    img[r, c] = (0.022, 0.022, 0.025)
    r, c = region("plate")
    img[r, c] = (0.80, 0.78, 0.72)
    # The panel face: a cream plate, a rocker switch, two lamps and a small gauge.
    r, c = region("panel")
    ph, pw = r.stop - r.start, c.stop - c.start
    # drawn at 31 x 45 and scaled to the region (its size follows the texture's)
    face = np.ones((31, 45, 3)) * np.array((0.90, 0.88, 0.81))
    face[:2, :] = face[-2:, :] = (0.45, 0.44, 0.42)
    face[:, :2] = face[:, -2:] = (0.45, 0.44, 0.42)
    face[7:24, 6:15] = (0.12, 0.12, 0.13)                     # switch
    face[16:23, 7:14] = (0.28, 0.28, 0.30)                     # its upper (lit) half
    face[19:23, 20:25] = (0.20, 0.75, 0.30)                    # power lamp
    face[19:23, 28:33] = (0.95, 0.62, 0.15)                    # water lamp
    face[8:14, 20:40] = (0.20, 0.24, 0.22)                     # gauge
    face[9:13, 21:33] = (0.35, 0.80, 0.55)
    img[r, c] = face[(np.arange(ph) * 31 // ph)][:, (np.arange(pw) * 45 // pw)]
    return save_image(os.path.basename(path)[:-4], img, path)


ROOM_RINGS = {}     # shell grid name -> the floor's outline (passenger x, z), written with the walk grid


def split_rings_at_openings(rings, boxes):
    """`rings` ((height, [(x, z), ...]) from the floor up, all with the same number of points) with a point
    inserted into every ring where the floor ring crosses a side opening's z limits, at the same place along
    the segment in every ring, so rings[k][1][i] still pairs with rings[k+1][1][i]."""
    floor_ring = rings[0][1]
    count = len(floor_ring)
    inserts = {}
    for box in boxes:
        for axis,other in ((0,1),(1,0)):
            for limit in box[("x","z")[axis]]:
                for i in range(count):
                    a,b = floor_ring[i], floor_ring[(i + 1) % count]
                    if (a[axis]-limit)*(b[axis]-limit)>=0:continue
                    t=(limit-a[axis])/(b[axis]-a[axis])
                    cross=a[other]+(b[other]-a[other])*t
                    if box[("x","z")[other]][0]<=cross<=box[("x","z")[other]][1]:
                        inserts.setdefault(i,set()).add(t)
    if not inserts:
        return rings
    out = []
    for height, ring in rings:
        points = []
        for i in range(count):
            a, b = ring[i], ring[(i + 1) % count]
            points.append(a)
            for t in sorted(inserts.get(i, [])):
                points.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        out.append((height, points))
    return out


def build_shell(measure, spec, tex_dir):
    """Floor and inside walls in passenger space, written as Blender (x = -px, y = pz, z = py),
    as two objects with their own unwrapped textures: <object>_floor and <object>_walls.
    Wall quads face the camper's long axis; the floor faces up. Openings (door, windows)
    leave out the wall quads whose centre falls inside them."""
    floor_y = spec["floorY"]
    top = spec.get("top", 1.5)
    n = spec.get("segments", 72)
    # The lining's rings (tools-src/vehicles/shell_rings.py, which make_vehicles.py fits the furniture to
    # too): from `lowestOutline` up the measured outlines of the hull's inside, moved in by the inset (below
    # it the outline runs into the hitch); where the hull tucks in under the floor the floor follows it and
    # the wall slopes up from it (spec floorOutline). A spec can name a second measurement for the hull's
    # inside at floor height (floorOutline.measure) when the first has no outline there.
    floor_measure = None
    if spec.get("floorOutline") and spec["floorOutline"].get("measure"):
        with open(spec["floorOutline"]["measure"], "r", encoding="utf-8-sig") as handle:
            floor_measure = json.load(handle)
    try:
        lining = shell_rings.build(measure, spec, floor_measure)
    except ValueError as problem:
        raise SystemExit("RVKIT ERROR: %s: %s" % (spec["object"], problem))
    rings, (cx, cz), hull_at_floor = lining["rings"], lining["centre"], lining["hull_at_floor"]
    # the lining's outline (the walls stand on it), for the cutaway's clip of KI5's body details
    ROOM_RINGS[spec["grid"]["name"]] = [(x, z) for x, z in lining["room_ring"]]
    cab_plane = spec.get("cabBulkhead", {}).get("z")
    if cab_plane is not None:
        # The conservative room stops 30mm behind the native cab cut. Extend
        # its rendered floor/side edges to the measured partition, then omit
        # the duplicate front wall below. Keep navigation's room ring intact.
        extended = []
        for height, ring in rings:
            front = max(z for x,z in ring)
            extended.append((height, [(x, cab_plane if abs(z-front)<1e-6 else z) for x,z in ring]))
        rings = extended
    # The wall leaves out the segments whose middle is inside an opening, so a segment's length (a quarter of a
    # metre on a bus) is how coarse the door's edges would be, and a door leaf standing a few centimetres outside
    # the lining then shows the ground behind it in a slit. The rings get a point at each side opening's edges
    # first, so the cut-out is exactly the opening.
    rings = split_rings_at_openings(rings, spec.get("openings", []))
    n = len(rings[0][1])

    def P(px, py, pz):
        return Vector((-px, pz, py))

    def in_box(px, py, pz, box):
        return box["x"][0] <= px <= box["x"][1] and box["y"][0] <= py <= box["y"][1] and box["z"][0] <= pz <= box["z"][1]

    rng = np.random.default_rng(spec.get("seed", 11))
    style = spec.get("style", {})
    name = spec["object"]

    # walls: u runs along the floor ring's perimeter, v up from the floor
    floor_ring = rings[0][1]
    arc = [0.0]
    for i in range(n):
        a, b2 = floor_ring[i], floor_ring[(i + 1) % n]
        arc.append(arc[-1] + math.hypot(b2[0] - a[0], b2[1] - a[1]))
    perimeter = arc[-1]
    walls = UVBuilder(name + "_walls")
    entry = UVBuilder(name + "_entry") if spec.get("entryOpening") else None
    zs = [z for _, z in rings[-1][1]]
    axis_lo, axis_hi = min(zs) + 0.9, max(zs) - 0.9
    holes = spec.get("openings", [])
    for (h0, r0), (h1, r1) in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            if cab_plane is not None and all(abs(point[1]-cab_plane)<1e-6
                    for point in (r0[i],r0[j],r1[i],r1[j])):
                continue
            mx = (r0[i][0] + r0[j][0] + r1[i][0] + r1[j][0]) / 4
            mz = (r0[i][1] + r0[j][1] + r1[i][1] + r1[j][1]) / 4
            my = (h0 + h1) / 2
            target=walls
            if any(in_box(mx, my, mz, box) for box in holes):
                if entry and not spec.get('rearClosure') and in_box(mx,my,mz,spec["entryOpening"]):target=entry
                else:continue
            inward = P(cx, my, min(max(mz, axis_lo), axis_hi)) - P(mx, my, mz)
            inward.z = 0.0
            u0, u1 = arc[i] / perimeter, arc[i + 1] / perimeter
            v0, v1 = (h0 - floor_y) / (top - floor_y), (h1 - floor_y) / (top - floor_y)
            target.poly([P(r0[i][0], h0, r0[i][1]), P(r1[i][0], h1, r1[i][1]),
                        P(r1[j][0], h1, r1[j][1]), P(r0[j][0], h0, r0[j][1])],
                       [wall_uv(u0, v0), wall_uv(u0, v1), wall_uv(u1, v1), wall_uv(u1, v0)], inward)
            if target is entry or spec.get("cabBulkhead"):
                # The camera can see either side of a lowered rear door. Native
                # cargo cuts also expose the back of the side lining; retain an
                # opaque inside skin instead of showing the native dark cavity.
                target.poly([P(r0[i][0], h0, r0[i][1]), P(r1[i][0], h1, r1[i][1]),
                            P(r1[j][0], h1, r1[j][1]), P(r0[j][0], h0, r0[j][1])],
                           [wall_uv(u0,v0),wall_uv(u0,v1),wall_uv(u1,v1),wall_uv(u1,v0)], -inward)
    for corner_return in spec.get("cornerReturns", []):
        # Angular body outlines omit some real corner turns. Add a narrow
        # opaque skin between the unchanged lining arc and the exact native
        # corner spine. No floor, room ring or navigation point is moved.
        section = corner_return["section"]
        side, end = corner_return["side"], corner_return["end"]
        skin = corner_return.get("skin", .003)

        def corner_at(height):
            for a, b in zip(section, section[1:]):
                if a[0] - 1e-8 <= height <= b[0] + 1e-8:
                    t = (height - a[0]) / (b[0] - a[0])
                    return (a[1] + (b[1] - a[1]) * t - side * skin,
                            a[2] + (b[2] - a[2]) * t - end * skin)
            raise AssertionError("corner return outside measured height range")

        heights = sorted({row[0] for row in section} |
                         {h for h, _ in rings if section[0][0] < h < section[-1][0]})
        sampled = [(h, shell_rings.ring_at(rings, h), corner_at(h)) for h in heights]
        assert all(ring is not None for _, ring, _ in sampled)
        brackets = []
        for height, ring, corner in sampled:
            angle = math.atan2(corner[1] - cz, corner[0] - cx)
            delta = [((math.atan2(z - cz, x - cx) - angle + math.pi) % (2 * math.pi) - math.pi)
                     for x, z in ring]
            brackets.append((max((i for i in range(n) if delta[i] <= 0), key=lambda i: delta[i]),
                             min((i for i in range(n) if delta[i] > 0), key=lambda i: delta[i])))
        first = brackets[0][0]
        offsets = [((index - first + n // 2) % n - n // 2) for pair in brackets for index in pair]
        indices = [(first + offset) % n for offset in range(min(offsets), max(offsets) + 1)]
        assert 2 <= len(indices) <= 8, "measured corner must span a local lining arc"

        def corner_face(points, uv, normal):
            verts = [P(*point) for point in points]
            if (verts[1] - verts[0]).cross(verts[2] - verts[0]).length < 1e-10:
                return
            # The cutaway can expose either side of this narrow return.
            walls.poly(verts, uv, normal)
            walls.poly(verts, uv, -normal)

        for (h0, r0, c0), (h1, r1, c1) in zip(sampled, sampled[1:]):
            for index in (indices[0], indices[-1]):
                a0, a1 = r0[index], r1[index]
                u = arc[index] / perimeter
                v0, v1 = (h0 - floor_y) / (top - floor_y), (h1 - floor_y) / (top - floor_y)
                d0, d1 = math.dist(a0, c0) / perimeter, math.dist(a1, c1) / perimeter
                corner_face([(a0[0], h0, a0[1]), (a1[0], h1, a1[1]),
                             (c1[0], h1, c1[1]), (c0[0], h0, c0[1])],
                            [wall_uv(u, v0), wall_uv(u, v1), wall_uv(u + d1, v1), wall_uv(u + d0, v0)],
                            P(-side, 0, -end))
        for (height, ring, corner), upward in ((sampled[0], -1), (sampled[-1], 1)):
            # Caps cover only the new wedge outside the existing lining arc.
            # They are above the floor, below/above all current wall cut modes.
            for ia, ib in zip(indices, indices[1:]):
                a, b = ring[ia], ring[ib]
                points = [(a[0], height, a[1]), (b[0], height, b[1]), (corner[0], height, corner[1])]
                corner_face(points, [wall_uv(arc[ia] / perimeter, (height - floor_y) / (top - floor_y)),
                                     wall_uv(arc[ib] / perimeter, (height - floor_y) / (top - floor_y)),
                                     wall_uv(arc[ia] / perimeter, (height - floor_y) / (top - floor_y))],
                            Vector((0, 0, upward)))
    cowl = spec.get("cowlReturn")
    if cowl:
        # A low measured return joins a bus's lining to its surviving native
        # cowl. It is part of the normally cut walls, not an opaque bulkhead.
        from mathutils.geometry import tessellate_polygon
        polygon, high = cowl["polygon"], cowl["height"]
        low = high - cowl["thickness"]
        left = min(x for x, z in polygon)
        rear = min(z for x, z in polygon)
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, polygon[1:] + polygon[:1]))
        winding = 1 if area > 0 else -1
        def cowl_uv(x, y, z):
            return wall_uv((x - left) / perimeter, (y - floor_y + z - rear) / (top - floor_y))
        for tri in tessellate_polygon([[Vector((x, z, 0)) for x, z in polygon]]):
            # Blender versions expose either input indices or Vector points.
            points = [(point.x, point.y) if hasattr(point, "x") else polygon[point] for point in tri]
            for height, upward in ((high, 1), (low, -1)):
                walls.poly([P(x, height, z) for x, z in points],
                           [cowl_uv(x, height, z) for x, z in points], Vector((0, 0, upward)))
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            points = [(a[0], low, a[1]), (a[0], high, a[1]), (b[0], high, b[1]), (b[0], low, b[1])]
            normal = P(winding * (b[1] - a[1]), 0, winding * (a[0] - b[0]))
            walls.poly([P(*point) for point in points], [cowl_uv(*point) for point in points], normal)
    closure=spec.get('rearClosure')
    if closure:
        rear=closure['z'];rim=.035
        section=closure['section']
        def rear_section_at(height):
            lo=max((s for s in section if s[0]<=height),default=section[0])
            hi=min((s for s in section if s[0]>=height),default=section[-1])
            t=(height-lo[0])/(hi[0]-lo[0]) if hi[0]>lo[0] else 0
            return (height,lo[1]+(hi[1]-lo[1])*t,lo[2]+(hi[2]-lo[2])*t)

        # The opening removes the last side-wall segments as well as the rear
        # wall. The measured closure is wider and slightly aft of that room:
        # a flat leaf/rim alone leaves a channel through both rear corners.
        # Follow the actual split floor arc, so returns meet surviving wall
        # edges without changing the authored room/navigation outline.
        join=spec['entryOpening']['z'][1]
        is_rear=[z<=join+1e-7 for x,z in floor_ring]
        start=next(i for i in range(n) if is_rear[i] and not is_rear[i-1])
        rear_indices=[]
        for offset in range(n):
            index=(start+offset)%n
            if not is_rear[index]:break
            rear_indices.append(index)
        if floor_ring[rear_indices[0]][0]>floor_ring[rear_indices[-1]][0]:
            rear_indices.reverse()
        left_index,right_index=rear_indices[0],rear_indices[-1]
        assert rear<min(floor_ring[i][1] for i in rear_indices), 'rear closure must be aft of the room floor'

        def edge_at(height,index):
            ring=shell_rings.ring_at(rings,height)
            if ring is None:ring=rings[0 if height<=rings[0][0] else -1][1]
            return ring[index]

        def return_face(points,facing,metal=False,double=False,builder=None):
            # Triangular corner wedges can repeat their rear endpoint. Keep
            # one vertex there; do not emit zero-area or overlapping quads.
            clean=[]
            for point in points:
                if not clean or point!=clean[-1]:clean.append(point)
            if len(clean)>1 and clean[0]==clean[-1]:clean.pop()
            if len(clean)<3:return
            corners=[P(*point) for point in clean]
            if (corners[1]-corners[0]).cross(corners[2]-corners[0]).length<1e-10:return
            if metal:
                _,left,right=rear_section_at(floor_y)
                uv=[swatch_uv('metal',(x-left)/(right-left),(z-rear)/(join-rear)) for x,y,z in clean]
            else:
                uv=[wall_uv((x-section[0][1])/perimeter,(y-floor_y)/(top-floor_y)) for x,y,z in clean]
            builder=walls if builder is None else builder
            builder.poly(corners,uv,facing)
            if double:builder.poly(corners,uv,-facing)

        # Split at both sources' heights so each return shares the exact edge
        # of the wall and the measured rim. Opposite-facing skins use the same
        # backface-culling convention as the rear closure, with no co-facing
        # overlap against either existing surface.
        heights=sorted({floor_y,min(top,rings[-1][0])} |
                       {h for h,_ in rings if floor_y<h<top} |
                       {s[0] for s in section if floor_y<s[0]<min(top,rings[-1][0])})
        for h0,h1 in zip(heights,heights[1:]):
            _,l0,r0=rear_section_at(h0);_,l1,r1=rear_section_at(h1)
            for index,side,x0,x1 in ((left_index,-1,l0+rim,l1+rim),(right_index,1,r0-rim,r1-rim)):
                a0,z0=edge_at(h0,index);a1,z1=edge_at(h1,index)
                return_face([(a0,h0,z0),(a1,h1,z1),(x1,h1,rear),(x0,h0,rear)],
                            P(-side,0,0),double=True)

        # Fill only the narrow space outside the existing rear floor arc.
        # Its side wedges end on the jambs and its rear edge on the leaf; the
        # doorway centre remains open when the leaf is hidden. Existing metal
        # swatches supply the sill without a new texture or coplanar floor.
        _,left,right=rear_section_at(floor_y)
        left+=rim;right-=rim
        rear_arc=[floor_ring[i] for i in rear_indices]
        def threshold_x(x):
            return left+(right-left)*(x-rear_arc[0][0])/(rear_arc[-1][0]-rear_arc[0][0])
        for (x0,z0),(x1,z1) in zip(rear_arc,rear_arc[1:]):
            return_face([(x0,floor_y,z0),(x1,floor_y,z1),
                         (threshold_x(x1),floor_y,rear),(threshold_x(x0),floor_y,rear)],
                        Vector((0,0,1)),metal=True)

        # Continuous bands follow the real body instead of the narrower room box.
        # Opposite faces retain both rear camera views; the static rim remains
        # around an open door. The closed leaf also reaches the measured lower skirt.
        def rear_face(builder,points):
            uv=[wall_uv((x-closure['section'][0][1])/perimeter,(y-floor_y)/(top-floor_y)) for x,y in points]
            corners=[P(x,y,rear) for x,y in points]
            for direction in (-1,1):builder.poly(corners,uv,Vector((0,direction,0)))
        for a,b in zip(closure['section'],closure['section'][1:]):
            y0,l0,r0=a;y1,l1,r1=b
            rear_face(walls,[(l0,y0),(l1,y1),(l1+rim,y1),(l0+rim,y0)])
            rear_face(walls,[(r0-rim,y0),(r1-rim,y1),(r1,y1),(r0,y0)])
            rear_face(entry,[(l0+rim,y0),(l1+rim,y1),(r1-rim,y1),(r0-rim,y0)])
        # The native rear posts stand aft of the flat inside leaf. Follow their
        # measured, height-dependent contour so the cutaway cannot look through
        # the channel behind the frame. Every station is inside the native skin;
        # no body-wide maximum-depth extrusion is used at the tapered roof.
        depth_sections=closure.get('depthSections',[])
        for (y0,row0),(y1,row1) in zip(depth_sections,depth_sections[1:]):
            assert len(row0)==len(row1), 'rear contour stations must align'
            for j in range(len(row0)-1):
                a0,a1,b0,b1=row0[j],row1[j],row0[j+1],row1[j+1]
                for side,column in ((-1,1),(1,2)):
                    # Outer and inner skins make a static jamb with a 35mm
                    # border. Its inner skin also closes the leaf volume's side
                    # when shut, avoiding coincident leaf/frame side faces.
                    for inset in (0,-side*rim):
                        return_face([(a0[column]+inset,y0,a0[0]),(a1[column]+inset,y1,a1[0]),
                                     (b1[column]+inset,y1,b1[0]),(b0[column]+inset,y0,b0[0])],
                                    P(-side,0,0),double=True)
            z0,l0,r0=row0[-1];z1,l1,r1=row1[-1]
            if z0<rear-1e-7 or z1<rear-1e-7:
                for side,x0,x1 in ((-1,l0,l1),(1,r0,r1)):
                    return_face([(x0,y0,z0),(x1,y1,z1),(x1-side*rim,y1,z1),(x0-side*rim,y0,z0)],
                                P(0,0,-1),double=True)
                # The aft centre belongs to the same entry model as the front
                # leaf. Open/missing-door visibility removes both together.
                return_face([(l0+rim,y0,z0),(l1+rim,y1,z1),(r1-rim,y1,z1),(r0-rim,y0,z0)],
                            P(0,0,-1),double=True,builder=entry)
        if depth_sections:
            for (height,row),upward in ((depth_sections[0],-1),(depth_sections[-1],1)):
                for a,b in zip(row,row[1:]):
                    for side,column in ((-1,1),(1,2)):
                        return_face([(a[column],height,a[0]),(b[column],height,b[0]),
                                     (b[column]-side*rim,height,b[0]),(a[column]-side*rim,height,a[0])],
                                    Vector((0,0,upward)),double=True)
                    return_face([(a[1]+rim,height,a[0]),(b[1]+rim,height,b[0]),
                                 (b[2]-rim,height,b[0]),(a[2]-rim,height,a[0])],
                                Vector((0,0,upward)),double=True,builder=entry)
    if not spec.get("reuseTexture"):
        wall_texture(os.path.join(tex_dir, "Vehicles", "MELensShell_%s_walls.png" % spec["texture"]),
                     perimeter, top - floor_y, rng, style)

    # Wheel wells. The skin is open around the wheels (the arches), and the tyres reach
    # above the floor, so the floor stops at each well's inner side and a sheet-metal box
    # covers the wheel inside. Its inside (seen from outside through the arch) is dark,
    # and reaches below the floor so nothing shows through.
    wells = spec.get("wheelWells", [])
    floor_poly = carve_wells(floor_ring, wells)
    E = 0.004   # the liner sits just inside the box, so the two never share a plane
    for well in wells:
        xin, xout = well["x"]
        z0, z1 = well["z"]
        top, bottom = well["top"], well["bottom"]
        side = 1.0 if xout > xin else -1.0
        # What shows outside: through the arch, from outside, the box's ends stand in the opening, and
        # anything of them beyond the hull's line shows against the grass or across the tyre. Their outer
        # edge stops at the hull's inside at floor height; the top, above the arch, reaches the wall's
        # lining (the skin hides it there).
        xplate = xout
        if hull_at_floor:
            line = tightest_crossing(hull_at_floor, z0, z1, side)
            if line is not None:
                xplate = side * max(abs(xin) + 0.1, min(abs(xout), line - 0.004))
        lining = lining_at(rings, top, z0, z1, side)
        xtop = xout if lining is None else side * max(abs(xplate), min(abs(xout), lining - 0.002))
        out = P(side, 0, 0) - P(0, 0, 0)
        back, front = P(0, 0, -1) - P(0, 0, 0), P(0, 0, 1) - P(0, 0, 0)
        # each face with its (s, t): s level along the face, t up it (across the top)
        box = [
            ([(xin, floor_y, z0), (xin, top, z0), (xin, top, z1), (xin, floor_y, z1)],
             [(0, 0), (0, 1), (1, 1), (1, 0)], -out),                                   # inner side
            ([(xin, floor_y, z0), (xplate, floor_y, z0), (xplate, top, z0), (xin, top, z0)],
             [(0, 0), (1, 0), (1, 1), (0, 1)], back),                                   # rear end
            ([(xin, floor_y, z1), (xplate, floor_y, z1), (xplate, top, z1), (xin, top, z1)],
             [(0, 0), (1, 0), (1, 1), (0, 1)], front),                                  # front end
            ([(xin, top, z0), (xtop, top, z0), (xtop, top, z1), (xin, top, z1)],
             [(0, 0), (0, 1), (1, 1), (1, 0)], Vector((0, 0, 1))),                      # top
        ]
        for corners, st, facing in box:
            walls.poly([P(*c) for c in corners], [swatch_uv("metal", s, t) for s, t in st], facing)
        xl = xin + side * E
        liner = [
            ([(xl, bottom, z0), (xl, top - E, z0), (xl, top - E, z1), (xl, bottom, z1)], out),
            ([(xl, top - E, z0), (xtop, top - E, z0), (xtop, top - E, z1), (xl, top - E, z1)], Vector((0, 0, -1))),
            ([(xl, bottom, z0 + E), (xplate, bottom, z0 + E), (xplate, top - E, z0 + E), (xl, top - E, z0 + E)], front),
            ([(xl, bottom, z1 - E), (xplate, bottom, z1 - E), (xplate, top - E, z1 - E), (xl, top - E, z1 - E)], back),
        ]
        for corners, facing in liner:
            walls.poly([P(*c) for c in corners], [swatch_uv("liner", 0, 0), swatch_uv("liner", 0, 1),
                                                  swatch_uv("liner", 1, 1), swatch_uv("liner", 1, 0)], facing)

    # The utility panel by the door: lights switch and the camper's dashboard.
    panel = spec.get("panel")
    if panel:
        px0 = panel["x"]                      # the wall's inside face
        side = 1.0 if px0 > 0 else -1.0
        px1 = px0 - side * panel.get("depth", 0.02)
        (y0, y1), (z0, z1) = panel["y"], panel["z"]
        inward = P(-side, 0, 0) - P(0, 0, 0)
        face = [(px1, y0, z0), (px1, y1, z0), (px1, y1, z1), (px1, y0, z1)]
        # the face's u runs along the camper towards the back on the right wall
        su = (lambda z: (z1 - z) / (z1 - z0)) if side < 0 else (lambda z: (z - z0) / (z1 - z0))
        walls.poly([P(*c) for c in face], [swatch_uv("panel", su(c[2]), (c[1] - y0) / (y1 - y0)) for c in face], inward)
        edges = [
            ([(px0, y1, z0), (px1, y1, z0), (px1, y1, z1), (px0, y1, z1)], Vector((0, 0, 1))),
            ([(px0, y0, z0), (px1, y0, z0), (px1, y0, z1), (px0, y0, z1)], Vector((0, 0, -1))),
            ([(px0, y0, z0), (px1, y0, z0), (px1, y1, z0), (px0, y1, z0)], P(0, 0, -1) - P(0, 0, 0)),
            ([(px0, y0, z1), (px1, y0, z1), (px1, y1, z1), (px0, y1, z1)], P(0, 0, 1) - P(0, 0, 0)),
        ]
        for corners, facing in edges:
            walls.poly([P(*c) for c in corners], [swatch_uv("plate", 0, 0), swatch_uv("plate", 0, 1),
                                                  swatch_uv("plate", 1, 1), swatch_uv("plate", 1, 0)], facing)

    # Floor: the carved outline, triangulated, mapped flat over its bounds (the wheel-well
    # boxes' metal tops are part of the walls object).
    from mathutils.geometry import tessellate_polygon
    xs = [p[0] for p in floor_poly]
    fz = [p[1] for p in floor_poly]
    bounds = (min(xs), max(xs), min(fz), max(fz))
    def fuv(px, pz):
        u = (px - bounds[0]) / (bounds[1] - bounds[0])
        v = (pz - bounds[2]) / (bounds[3] - bounds[2])
        return (min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0))
    floor = UVBuilder(name + "_floor")
    for tri in tessellate_polygon([[Vector((x, z, 0.0)) for x, z in floor_poly]]):
        pts = [floor_poly[k] for k in tri]
        (ax, az), (bx, bz), (qx, qz) = pts
        if abs((bx - ax) * (qz - az) - (qx - ax) * (bz - az)) < 1e-9:
            continue   # collinear outline points
        floor.poly([P(x, floor_y, z) for x, z in pts], [fuv(x, z) for x, z in pts], Vector((0, 0, 1)))
    if not spec.get("reuseTexture"):
        floor_texture(os.path.join(tex_dir, "Vehicles", "MELensShell_%s_floor.png" % spec["texture"]),
                      bounds, floor_poly, rng, style)
    objects = [floor.finish(), walls.finish()]
    if entry:
        # The original door is a thin exterior mesh. Supply its inside skin at
        # precisely the removed lining segments; Lua hides it for an open/missing door.
        objects.append(entry.finish())
    if spec.get("cabBulkhead"):
        # The cab and its cargo partition remain opaque at every wall setting.
        # A solid skin closes the otherwise exposed backfaces of factory cab parts.
        front = spec["cabBulkhead"].get("z", max(z for x, z in floor_ring) - 0.003)
        xs = [x for x, z in floor_ring if z > front - 0.05]
        left, right = min(xs), max(xs)
        high = spec["cabBulkhead"]["top"]
        partition = UVBuilder(name + "_bulkhead")
        low = floor_y-.015
        section = spec["cabBulkhead"].get("section", [])
        skin_inset = spec["cabBulkhead"].get("inset", .003)
        heights = []
        for y in sorted({low, high} | {y for segment in section for x,y in segment if y >= low}):
            if heights and y-heights[-1] < 1e-6:heights[-1]=y
            else:heights.append(y)
        lower, upper = [], []
        for y in heights:
            crossings = []
            for (x0,y0),(x1,y1) in section:
                if min(y0,y1)-1e-6 <= y <= max(y0,y1)+1e-6:
                    if abs(y1-y0) < 1e-6:
                        crossings.extend((x0,x1))
                    else:
                        t=min(1,max(0,(y-y0)/(y1-y0)))
                        crossings.append(x0+(x1-x0)*t)
            # Intersect the actual skin at each height, including the lower
            # floor cut. A convex hull bridges trim protrusions into a false
            # wedge outside the straight body below them; clamping low points
            # upward also imports an unrelated underbody width at the floor.
            # Keep the cap inside coincident native side skins. Native cap-hide
            # controls exposed the same fine seam on several body families.
            # Clamp each side to the centre at narrow roof-tip sections.
            if crossings and skin_inset:
                lo,hi = min(crossings),max(crossings)
                centre = (lo+hi)/2
                crossings = [min(centre,lo+skin_inset),max(centre,hi-skin_inset)]
            # Sparse sections can contain only internal cab edges at a height.
            # They must not narrow the opaque partition inside the room itself.
            # Above its ceiling, retain the measured roof contour.
            if y <= high+1e-6:
                crossings.extend((left,right))
            lower.append((min(crossings) if crossings else left,y))
            upper.append((max(crossings) if crossings else right,y))
        # Retain counter-clockwise winding for the perimeter's outward normals.
        outline = []
        for point in reversed(lower+list(reversed(upper))):
            if not outline or point != outline[-1]:outline.append(point)
        if outline[-1] == outline[0]:outline.pop()
        # A thin solid partition overlaps the native cut instead of sharing its
        # exact depth. Coplanar factory faces otherwise flicker through as dark
        # stripes or large black panels. Its forward skin and edge returns seal
        # the joint to the retained cab without a grass-visible slit.
        # Native interior clipping ends 30mm behind the cut plane. Cover that
        # retained band with 3mm clearance; measured cab backfaces farther aft
        # can supply an explicit depth. The front skin still seals the cab cut.
        cargo_face, cab_face = front-spec["cabBulkhead"].get("depth",.033), front+.002
        corners = [P(x, y, cargo_face) for x,y in outline]
        # Match the lining's wall panels instead of stretching its entire atlas.
        u0 = arc[max(range(n), key=lambda i: floor_ring[i][1])] / perimeter
        cap_height = max(y for x,y in outline)-floor_y
        uv = [wall_uv(u0+(x-left)/perimeter, (y-floor_y)/cap_height) for x,y in outline]
        partition.poly(corners, uv, Vector((0,-1,0)))
        partition.poly([P(x,y,cab_face) for x,y in outline],uv,Vector((0,1,0)))
        for i,(x0,y0) in enumerate(outline):
            x1,y1=outline[(i+1)%len(outline)]
            outward=Vector((-(y1-y0),0,-(x1-x0)))
            partition.poly([P(x0,y0,cargo_face),P(x1,y1,cargo_face),P(x1,y1,cab_face),P(x0,y0,cab_face)],
                           [uv[i],uv[(i+1)%len(uv)],uv[(i+1)%len(uv)],uv[i]],outward)
        objects.append(partition.finish())
    return objects


def ring_crossing(ring, z, side):
    """x where the closed outline `ring` ((x, z) points) crosses the line z on `side`'s wall (+1 the
    vehicle's left, -1 its right): the widest such crossing; None where it does not."""
    xs = []
    for i in range(len(ring)):
        (ax, az), (bx, bz) = ring[i], ring[(i + 1) % len(ring)]
        if (az - z) * (bz - z) <= 0 and az != bz:
            xs.append(ax + (bx - ax) * (z - az) / (bz - az))
    xs = [x for x in xs if x * side > 0]
    return max(xs, key=lambda x: x * side) if xs else None


def tightest_crossing(ring, z0, z1, side):
    """The narrowest half width (|x|) of the outline's wall on `side` over z0..z1: where a thing that
    must stay inside it has least room. Across a gap in the outline (an arch) its points' chord."""
    values = []
    for k in range(13):
        x = ring_crossing(ring, z0 + (z1 - z0) * k / 12, side)
        if x is not None:
            values.append(abs(x))
    return min(values) if values else None


def lining_at(rings, height, z0, z1, side):
    """The lining's narrowest half width on `side` over z0..z1 at `height`, between the rings (h, ring)."""
    for (ha, ra), (hb, rb) in zip(rings, rings[1:]):
        if ha <= height <= hb and hb > ha:
            xa, xb = tightest_crossing(ra, z0, z1, side), tightest_crossing(rb, z0, z1, side)
            if xa is None or xb is None:
                return None
            return xa + (xb - xa) * (height - ha) / (hb - ha)
    return None


def carve_wells(ring, wells):
    """The floor outline with the wheel wells cut out. A well covers x beyond its inner
    side `x[0]` (towards `x[1]`, the wall) for z in `z`. Outline points inside a well move
    to its inner side, and the well's corners are added where the outline crosses its
    ends, so its edges run straight."""
    poly = list(ring)
    for well in wells:
        xin, xout = well["x"]
        z0, z1 = well["z"]
        side = 1.0 if xout > xin else -1.0

        def inside(p):
            return z0 < p[1] < z1 and (p[0] - xin) * side > 0

        out = []
        n = len(poly)
        for i in range(n):
            p, q = poly[i], poly[(i + 1) % n]
            out.append((xin, p[1]) if inside(p) else p)
            # crossings of this edge with the well's ends, on the wall side, in order along it
            hits = []
            for zc in (z0, z1):
                if (p[1] - zc) * (q[1] - zc) < 0:
                    t = (zc - p[1]) / (q[1] - p[1])
                    x = p[0] + (q[0] - p[0]) * t
                    if (x - xin) * side > 0:
                        hits.append((t, x, zc))
            for t, x, zc in sorted(hits):
                entering = not inside(p) if len(hits) == 1 else (zc == hits[0][2])
                if entering:
                    out += [(x, zc), (xin, zc)]
                else:
                    out += [(xin, zc), (x, zc)]
        poly = out
    return poly


def shell_walk_grid(shells, spec, lua_dir):
    """The walkable floor of an empty shell (before furniture), as a Lua walk grid:
    rays straight down from head height; a cell is free where the first surface is the
    floor, then shrunk by the character radius. Same format as floorplan.py."""
    from mathutils.bvhtree import BVHTree
    g = spec["grid"]
    floor_y = spec["floorY"]
    cell = g["cell"]
    x0, x1 = g["xRange"]
    z0, z1 = g["zRange"]
    cols = int(round((x1 - x0) / cell))
    rows = int(round((z1 - z0) / cell))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    trees = [BVHTree.FromObject(shell, depsgraph) for shell in shells]
    head = floor_y + g.get("headroom", 1.05)
    free = [[False] * cols for _ in range(rows)]
    for r in range(rows):
        pz = z0 + (r + 0.5) * cell
        for c in range(cols):
            px = x0 + (c + 0.5) * cell
            best = None
            for tree in trees:
                hit = tree.ray_cast(Vector((-px, pz, head)), Vector((0, 0, -1)), head - floor_y + 0.3)
                if hit[0] is not None and (best is None or hit[3] < best[3]):
                    best = hit
            if best is not None and abs(best[0].z - floor_y) <= g.get("floorTolerance", 0.04):
                free[r][c] = True
    radius = g["radius"]
    rc = int(math.ceil(radius / cell))
    offsets = [(dr, dc) for dr in range(-rc, rc + 1) for dc in range(-rc, rc + 1)
               if (dr * dr + dc * dc) * cell * cell <= radius * radius]
    lines = ["-- Generated by tools-src/blender/rv_kit.py (empty shell); do not edit.",
             "MELens = MELens or {}",
             "MELens.WalkGrids = MELens.WalkGrids or {}",
             "MELens.WalkGrids[%s] = {" % json.dumps(g["name"]),
             "    x0 = %.4f, z0 = %.4f, cell = %.4f, cols = %d, rows = {" % (x0, z0, cell, cols)]
    walkable = 0
    for r in range(rows):
        row = []
        for c in range(cols):
            ok = free[r][c] and all(0 <= r + dr < rows and 0 <= c + dc < cols and free[r + dr][c + dc]
                                    for dr, dc in offsets)
            walkable += ok
            row.append("1" if ok else "0")
        lines.append('        "%s",' % "".join(row))
    lines += ["    },", "}"]
    # The room's outline for the cutaway: the floor's own outline (the lining stands on it), so
    # that KI5's body details standing inside the lining (the tips of a trailer tongue's arms at
    # the front corners) can be left out of the drawing: they show in front of the white walls
    # as black objects. The hull lies outside it.
    ring = ROOM_RINGS.get(g["name"])
    if ring:
        lines += ["MELens.RoomRings = MELens.RoomRings or {}",
                  "MELens.RoomRings[%s] = {" % json.dumps(g["name"])]
        lines += ["    { %.3f, %.3f }," % p for p in ring]
        lines += ["}"]
        print("ROOMRING %s: %d corners" % (g["name"], len(ring)))
    path = os.path.join(lua_dir, "MELens_WalkGrid_%s.lua" % g["file"])
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print("SHELLGRID %s: %d x %d, walkable %d" % (g["name"], cols, rows, walkable))


# ------------------------------------------------------------------------------------
# Export, icons, manifest
# ------------------------------------------------------------------------------------

def export(objects, path):
    for o in bpy.context.scene.objects:
        o.select_set(o in objects)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"},
                             axis_forward="-Z", axis_up="Y", apply_unit_scale=False,
                             apply_scale_options="FBX_SCALE_NONE", global_scale=1.0,
                             bake_space_transform=True, use_mesh_modifiers=True,
                             mesh_smooth_type="FACE", add_leaf_bones=False)


# Painted material textures (tools-src/art/generate.ps1, made with an image model in the
# game's hand-painted style): palette name -> (art file, tiles per repeat, calm). The texture is
# graded to the material's palette colour; `calm` blends it that much towards the plain colour
# (busy patterns: the laminate's boomerangs). Materials without one use their palette colour.
ART = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "art", "textures"))
TEXTURES = {
    "wood_light": ("wood_light", 0.5, 0.15),
    "wood_kick": ("wood_light", 0.5, 0.3),
    "wood_dark": ("wood_dark", 0.5, 0.15),
    "wood_birch": ("birch", 0.5, 0.15),
    "fabric_red": ("quilt", 1.1, 0.0),
    "mattress": ("vinyl", 0.6, 0.0),           # washable blue-grey stretcher pad
    "pillow": ("sheet", 0.5, 0.0),
    "sheet": ("sheet", 0.5, 0.0),
    "fabric_blue": ("vinyl", 0.45, 0.0),
    "laminate": ("laminate", 1.2, 0.6),
    "enamel": ("enamel", 0.8, 0.3),
    "paint_white": ("enamel", 0.8, 0.3),
    "paint_cream": ("enamel", 0.8, 0.3),
    "steel": ("steel", 0.4, 0.2),
    "basin": ("steel", 0.4, 0.2),
    "chrome": ("steel", 0.3, 0.2),
    "black": ("darkmetal", 0.6, 0.2),
    "heater_body": ("darkmetal", 0.6, 0.2),
    "cardboard": ("cardboard", 0.45, 0.1),
    "cardboard_dark": ("cardboard", 0.45, 0.1),
    "cardboard_light": ("cardboard", 0.45, 0.1),
    "tape": ("cardboard", 0.45, 0.6),
    "tape_brown": ("cardboard", 0.45, 0.6),
    "busvinyl": ("busvinyl", 0.45, 0.0),
    "floor_lino": ("lino", 0.35, 0.0),
}


def art_path(name):
    path = os.path.join(ART, name + ".png")
    return path if os.path.exists(path) else None


def load_art(name):
    """An art texture as an array of RGB rows (row 0 at the bottom), or None."""
    path = art_path(name)
    if not path:
        return None
    img = bpy.data.images.load(path)
    w, h = img.size
    pixels = np.array(img.pixels[:]).reshape(h, w, 4)[..., :3].copy()
    bpy.data.images.remove(img)
    return pixels


def shrink(img, nw, nh):
    """Area-averages an image (rows, cols, 3) down to nh rows and nw columns."""
    def along(a, n, axis):
        size = a.shape[axis]
        edges = np.linspace(0, size, n + 1)
        lo = np.floor(edges[:-1]).astype(int)
        hi = np.maximum(lo + 1, np.floor(edges[1:]).astype(int))
        c = np.cumsum(a, axis=axis)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
        shape = [-1 if i == axis else 1 for i in range(a.ndim)]
        return (np.take(c, hi, axis=axis) - np.take(c, lo, axis=axis)) / (hi - lo).reshape(shape)
    return along(along(img, nh, 0), nw, 1)


def grade(img, rgb, calm=0.0):
    """An art texture (rows, cols, 3; sRGB values) recoloured to average `rgb`, its detail kept; `calm`
    blends it that much towards the plain colour."""
    if rgb is None:
        return img
    rgb = np.array(rgb, dtype=float)
    mean = np.maximum(img.reshape(-1, 3).mean(axis=0), 1e-4)
    out = img / mean * rgb
    return out * (1.0 - calm) + rgb * calm


def tile_art(art, us, vs):
    """Samples a repeating art texture at (us, vs), measured in repeats; us picks the
    column (1D, length w), vs the row (1D, length h). The art is first averaged down to
    the output's own pixel size, so fine detail doesn't turn into sparkly noise."""
    h, w, _ = art.shape
    su = abs(us[1] - us[0]) * w if len(us) > 1 else 1.0     # art pixels per output pixel
    sv = abs(vs[1] - vs[0]) * h if len(vs) > 1 else 1.0
    if su > 1.2 or sv > 1.2:
        art = shrink(art, max(1, int(round(w / max(su, 1.0)))), max(1, int(round(h / max(sv, 1.0)))))
        h, w, _ = art.shape
    cols = (np.mod(us, 1.0) * w).astype(int) % w
    rows = (np.mod(vs, 1.0) * h).astype(int) % h
    return art[rows][:, cols]


def srgb_to_linear(c):
    c = np.asarray(c, dtype=float)
    return np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)


def procedural_material(name):
    """A shader for baking, in the style of the game's furniture sprites (measured next to them in the game):
    the painted texture graded to the material's colour, tops lighter than sides (SIDE_SHADE), undersides
    darker, the lower part darker and a little dirty, faint blotchy wear, and convex edges lighter, as if
    rounded and lit. The ambient occlusion baked on top darkens the seams and gaps. Object coordinates are
    tiles (every piece is built at the origin, so object and world space are the same)."""
    row, col, rgb, kind = PALETTE[name]
    target = srgb_to_linear(rgb)
    mat = bpy.data.materials.new("bake_" + name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    coord = nodes.new("ShaderNodeTexCoord")

    def multiply(a, b):
        mix = nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs["Fac"].default_value = 1.0
        links.new(a, mix.inputs["Color1"])
        links.new(b, mix.inputs["Color2"])
        return mix.outputs["Color"]

    def rgb_node(value):
        node = nodes.new("ShaderNodeRGB")
        node.outputs[0].default_value = (float(value[0]), float(value[1]), float(value[2]), 1.0)
        return node.outputs[0]

    def between(fac, lo, hi):
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (lo, lo, lo, 1.0)
        ramp.color_ramp.elements[1].color = (hi, hi, hi, 1.0)
        links.new(fac, ramp.inputs["Fac"])
        return ramp.outputs["Color"]

    def noise(scale, detail, stretch=None):
        tex = nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Detail"].default_value = detail
        if stretch:
            mapping = nodes.new("ShaderNodeMapping")
            mapping.inputs["Scale"].default_value = stretch
            links.new(coord.outputs["Object"], mapping.inputs["Vector"])
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        else:
            links.new(coord.outputs["Object"], tex.inputs["Vector"])
        return tex.outputs["Fac"]

    def map_range(value, a, b, c, d):
        node = nodes.new("ShaderNodeMapRange")
        node.clamp = True
        node.inputs["From Min"].default_value = a
        node.inputs["From Max"].default_value = b
        node.inputs["To Min"].default_value = c
        node.inputs["To Max"].default_value = d
        links.new(value, node.inputs["Value"])
        return node.outputs["Result"]

    source = TEXTURES.get(name)
    path = source and art_path(source[0])
    if path:
        # the painted texture, projected on every face from the side it faces, graded to the colour
        key = "art_" + source[0]
        image = bpy.data.images.get(key)
        if image is None:
            image = bpy.data.images.load(path)
            image.name = key
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.projection = "BOX"
        tex.projection_blend = 0.25
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (1.0 / source[1],) * 3
        links.new(coord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        px = np.array(image.pixels[:]).reshape(-1, 4)[:, :3]
        mean = np.maximum(srgb_to_linear(px).mean(axis=0), 1e-4)     # (the image's values are sRGB)
        colour = multiply(tex.outputs["Color"], rgb_node(target / mean))
        calm = 0.55 + 0.45 * (source[2] if len(source) > 2 else 0.0)    # smooth, painted: busy texture detail was annoying
        if calm:
            mix = nodes.new("ShaderNodeMixRGB")
            mix.inputs["Fac"].default_value = calm
            links.new(colour, mix.inputs["Color1"])
            links.new(rgb_node(target), mix.inputs["Color2"])
            colour = mix.outputs["Color"]
    else:
        colour = rgb_node(target)
        if kind == "grain":
            colour = multiply(colour, between(noise(6.0, 2.0, (1.0, 14.0, 14.0)), 0.90, 1.05))
        elif kind == "weave":
            colour = multiply(colour, between(noise(90.0, 1.0), 0.96, 1.03))
        elif kind == "brushed":
            colour = multiply(colour, between(noise(8.0, 2.0, (2.0, 2.0, 40.0)), 0.93, 1.05))
        elif kind == "speckle":
            colour = multiply(colour, between(noise(60.0, 2.0), 0.94, 1.04))
        elif kind == "slats":
            wave = nodes.new("ShaderNodeTexWave")
            wave.wave_type = "BANDS"
            wave.bands_direction = "Z"
            wave.inputs["Scale"].default_value = 60.0
            links.new(coord.outputs["Object"], wave.inputs["Vector"])
            colour = multiply(colour, between(wave.outputs["Fac"], 0.6, 1.15))
    geometry = nodes.new("ShaderNodeNewGeometry")
    # The sprites' painted light: tops lit, sides darker (SIDE_SHADE), undersides darker still, all taken from
    # a normal with the edges rounded (the Bevel node), so a side lightens towards its top edge and darkens
    # towards its bottom edge and a top dims a little at its rim: the light and dark borders the game's
    # furniture sprites draw round every part.
    bevel = nodes.new("ShaderNodeBevel")
    bevel.samples = 8
    bevel.inputs["Radius"].default_value = 0.022
    normal = nodes.new("ShaderNodeSeparateXYZ")
    links.new(bevel.outputs["Normal"], normal.inputs["Vector"])
    side = SIDE_SHADE.get(name, 0.92)
    colour = multiply(colour, map_range(normal.outputs["Z"], 0.0, 1.0, side, 1.0))
    colour = multiply(colour, map_range(normal.outputs["Z"], -1.0, 0.0, 0.62, 1.0))
    # convex edges catch the light, the upper ones most: a bright rim along a top's edge, a faint one up a
    # corner, none along a bottom edge
    dot = nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    links.new(bevel.outputs["Normal"], dot.inputs[0])
    links.new(geometry.outputs["Normal"], dot.inputs[1])
    rim = nodes.new("ShaderNodeMath")
    rim.operation = "MULTIPLY"
    links.new(map_range(dot.outputs["Value"], 0.70, 1.0, 1.0, 0.0), rim.inputs[0])
    links.new(map_range(normal.outputs["Z"], -0.1, 0.7, 0.15, 1.0), rim.inputs[1])
    colour = multiply(colour, map_range(rim.outputs["Value"], 0.0, 1.0, 1.0, 1.30))
    # darker towards the floor, with a little grime there, and a dark line where the piece stands on it
    position = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coord.outputs["Object"], position.inputs["Vector"])
    colour = multiply(colour, map_range(position.outputs["Z"], 0.0, 0.55, 0.80, 1.0))
    colour = multiply(colour, map_range(position.outputs["Z"], 0.0, 0.025, 0.50, 1.0))
    dirt = nodes.new("ShaderNodeMath")
    dirt.operation = "MULTIPLY"
    links.new(noise(9.0, 4.0), dirt.inputs[0])
    links.new(map_range(position.outputs["Z"], 0.0, 0.30, 1.0, 0.0), dirt.inputs[1])
    colour = multiply(colour, map_range(dirt.outputs["Value"], 0.25, 0.75, 1.0, 0.74))
    # streaks running down the faces, soft: wear and stains, as on the game's white goods and cabinets
    colour = multiply(colour, between(noise(7.0, 3.0, (9.0, 9.0, 1.0)), 0.90, 1.04))
    # faint large blotches of wear everywhere
    colour = multiply(colour, between(noise(2.5, 3.0), 0.93, 1.02))
    links.new(colour, bsdf.inputs["Base Color"])
    return mat


def fill_background(rgb, mask):
    """Fills the pixels outside the UV islands (mask False) with colours pushed out from
    the islands (push-pull), so the game's smaller mip levels never blend the islands
    with a black background: without it every face gets a dark outline."""
    levels = []
    c = rgb * mask[..., None]
    m = mask.astype(float)
    while min(c.shape[0], c.shape[1]) > 1:
        levels.append((c, m))
        h, w = c.shape[0] // 2, c.shape[1] // 2
        c = c[:h * 2, :w * 2].reshape(h, 2, w, 2, 3).sum(axis=(1, 3))
        m = m[:h * 2, :w * 2].reshape(h, 2, w, 2).sum(axis=(1, 3))
    fill = c / np.maximum(m, 1e-6)[..., None]
    for c_l, m_l in reversed(levels):
        up = np.repeat(np.repeat(fill, 2, axis=0), 2, axis=1)[:c_l.shape[0], :c_l.shape[1]]
        own = c_l / np.maximum(m_l, 1e-6)[..., None]
        weight = np.clip(m_l, 0.0, 1.0)[..., None]
        fill = own * weight + up * (1.0 - weight)
    return np.where(mask[..., None], rgb, fill)


# The bake cache (build/rv/bake-cache.json, outside the mod): per texture file, the key of what it was baked
# from and the hash of the file written, so a texture edited or replaced since is baked again.
BAKE_CACHE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build", "rv",
                                           "bake-cache.json"))


def file_hash(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def bake_key(obj, size):
    """Everything a piece's baked texture depends on: its mesh (corners, faces and their materials), the unwrap,
    the texture size, the materials it uses (colour, side shade, painted art and the art file itself) and the
    code that makes and bakes the materials."""
    mesh = obj.data
    h = hashlib.sha256()
    for items, attr, count, kind in ((mesh.vertices, "co", 3, np.float32), (mesh.loops, "vertex_index", 1, np.int32),
                                     (mesh.polygons, "loop_start", 1, np.int32),
                                     (mesh.polygons, "material_index", 1, np.int32),
                                     (mesh.uv_layers["BakeUV"].data, "uv", 2, np.float32)):
        values = np.empty(len(items) * count, dtype=kind)
        items.foreach_get(attr, values)
        h.update(values.tobytes())
    h.update(str(size).encode())
    h.update(repr((OUTLINE_CLEAR, OUTLINE_COLOUR)).encode())
    used = sorted({p.material_index for p in mesh.polygons})
    for index in used:
        name = MATERIAL_NAMES[index]
        source = TEXTURES.get(name)
        h.update(repr((name, PALETTE[name], SIDE_SHADE.get(name), source)).encode())
        art = source and art_path(source[0])
        if art:
            h.update(file_hash(art).encode())
    try:
        for fn in (srgb_to_linear, procedural_material, fill_background, save_image, bake_piece):
            h.update(inspect.getsource(fn).encode())
    except (OSError, TypeError):
        h.update(file_hash(os.path.abspath(__file__)).encode())    # (no source: any change to the kit)
    return h.hexdigest()


def read_bake_cache():
    try:
        with open(BAKE_CACHE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def cached_bake(path, key):
    """The texture baked earlier from the same key, if it is still the file that bake wrote."""
    if NO_CACHE or not os.path.exists(path):
        return None
    entry = read_bake_cache().get(os.path.normcase(os.path.abspath(path)))
    if not entry or entry.get("key") != key or entry.get("file") != file_hash(path):
        return None
    print("RVKIT cached", os.path.basename(path), flush=True)
    return bpy.data.images.load(path)


def remember_bake(path, key):
    cache = read_bake_cache()
    cache[os.path.normcase(os.path.abspath(path))] = {"key": key, "file": file_hash(path)}
    os.makedirs(os.path.dirname(BAKE_CACHE), exist_ok=True)
    with open(BAKE_CACHE, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(cache, handle, indent=1, sort_keys=True)


OUTLINE_CLEAR = 0.05                  # share of the texture kept free in the lower left corner
OUTLINE_COLOUR = (0.30, 0.22, 0.17)
OUTLINE_WIDTH = 0.0045                # about half a pixel of the game's sprites at the usual zoom: the game's furniture
                                      # is edged by a thin darker line, not a black comic-book one (0.012 black was too heavy)


def add_outline(obj):
    """The dark outline of the game's furniture sprites, as an "inverted hull": a copy of the piece pushed out along
    its vertex normals, faces turned inwards, mapped to the dark patch of its texture. With back faces not drawn
    only the far side of the shell shows, a dark rim round the silhouette and round every part that stands out
    (handles, door frames, the tops)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    original = list(bm.faces)
    result = bmesh.ops.duplicate(bm, geom=original)
    shell_faces = [g for g in result["geom"] if isinstance(g, bmesh.types.BMFace)]
    shell_verts = {v for f in shell_faces for v in f.verts}
    offset = {}
    for v in shell_verts:
        # the duplicate's own normal, smoothed over the faces that share the vertex
        normal = Vector((0.0, 0.0, 0.0))
        for f in v.link_faces:
            if f in shell_faces:
                normal += f.normal * f.calc_area()
        offset[v] = normal.normalized() * OUTLINE_WIDTH if normal.length > 1e-9 else Vector((0.0, 0.0, 0.0))
    for v, d in offset.items():
        v.co += d
    bmesh.ops.reverse_faces(bm, faces=shell_faces)
    uv = bm.loops.layers.uv.active
    corner = OUTLINE_CLEAR * 0.3
    for f in shell_faces:
        f.material_index = 0
        for loop in f.loops:
            loop[uv].uv = (corner, corner)
    bm.to_mesh(obj.data)
    bm.free()


def bake_piece(obj, path, size):
    """Unwrap the piece and bake its colour and ambient occlusion into one texture
    (colour x soft AO in its own tight gaps). Leaves the piece with only the new UV
    layer, as the game uses the first one."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("BakeWorld")
    # ambient occlusion only in tight gaps (door seams, drawer gaps): no contact shadow
    # on the floor, which in the game looked like a black shadow on every piece
    scene.world.light_settings.distance = 0.06
    # Clearing the slots resets every face to slot 0, so keep the faces' palette indices.
    indices = [p.material_index for p in obj.data.polygons]
    obj.data.materials.clear()
    for name in MATERIAL_NAMES:
        obj.data.materials.append(bpy.data.materials.get("bake_" + name) or procedural_material(name))
    for p, index in zip(obj.data.polygons, indices):
        p.material_index = index
    for o in scene.objects:
        o.select_set(o is obj)
    bpy.context.view_layer.objects.active = obj
    # Bake the piece on its own: every piece is built at the origin, so the ones baked
    # before it would stand inside it and darken its ambient occlusion in blocks (the
    # dark patches on the lower kitchen doors).
    others = [o for o in scene.objects if o is not obj and not o.hide_render]
    for o in others:
        o.hide_render = True
    bake_uv = obj.data.uv_layers.new(name="BakeUV")
    obj.data.uv_layers.active = bake_uv
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    # wide gaps between the islands, filled with each island's own colour by the bake
    # margin: the game's smaller mip levels then never mix a face with its neighbours
    # in the texture (thin dark lines along the edges when zoomed out)
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.03)
    bpy.ops.object.mode_set(mode="OBJECT")
    # keep the lower left corner of the texture free: the outline shell (add_outline) is mapped to a dark patch there
    for loop in obj.data.uv_layers["BakeUV"].data:
        loop.uv = (OUTLINE_CLEAR + (1.0 - OUTLINE_CLEAR) * loop.uv[0], OUTLINE_CLEAR + (1.0 - OUTLINE_CLEAR) * loop.uv[1])
    # Unchanged since its last bake (mesh, unwrap, materials, this code): keep the texture. Most rounds change
    # one or two pieces, and baking is most of rv_kit.py's time.
    key = bake_key(obj, size)
    cached = cached_bake(path, key)
    if cached is not None:
        for o in others:
            o.hide_render = False
        obj.data.uv_layers.remove(obj.data.uv_layers["UVMap"])
        return cached

    def target(img):
        for mat in obj.data.materials:
            nodes = mat.node_tree.nodes
            node = nodes.get("BakeTarget")
            if node is None:
                node = nodes.new("ShaderNodeTexImage")
                node.name = "BakeTarget"
            node.image = img
            nodes.active = node

    # with alpha: a bake leaves everything outside the islands transparent (the mask)
    colour = bpy.data.images.new(obj.name + "_colour", size, size, alpha=True)
    target(colour)
    scene.cycles.samples = 16
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=16, use_clear=True)
    for o in scene.objects:
        o.select_set(o is obj)
    bpy.context.view_layer.objects.active = obj
    ao = bpy.data.images.new(obj.name + "_ao", size, size, alpha=True)
    target(ao)
    scene.cycles.samples = 48
    bpy.ops.object.bake(type="AO", margin=16, use_clear=True)
    for o in others:
        o.hide_render = False
    c = np.array(colour.pixels[:]).reshape(size, size, 4)
    a = np.array(ao.pixels[:]).reshape(size, size, 4)
    mask = c[..., 3] > 0.5   # the AO image's alpha is 1 everywhere; the colour's marks the islands
    # (strong in the gaps: the game's sprites draw door seams, drawer gaps and the line under a counter's top
    # as dark lines)
    out = c[..., :3] * (0.58 + 0.42 * a[..., :1])
    out = fill_background(out, mask)
    out = pixelate(out, mask, 2 if size <= 512 else 3, np.random.default_rng(7))
    patch = int(size * OUTLINE_CLEAR * 0.8)
    out[:patch, :patch] = OUTLINE_COLOUR       # the dark patch the outline shell is mapped to
    image = save_image(os.path.basename(path)[:-4], out, path)
    remember_bake(path, key)
    obj.data.uv_layers.remove(obj.data.uv_layers["UVMap"])
    return image


def palette_material(obj, palette):
    """One material with the palette image on the piece (a FBX with one material per mesh, as the game
    expects); the faces keep the UVs that map them to their palette cell."""
    mat = bpy.data.materials.get("melens_palette")
    if mat is None:
        mat = bpy.data.materials.new("melens_palette")
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = palette
        tex.interpolation = "Closest"
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def render_icon(obj, image, path, size=64):
    scene = bpy.context.scene
    mat = bpy.data.materials.new("icon_" + obj.name)
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = image
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0
    for o in scene.objects:
        o.hide_render = o is not obj and o.type == "MESH"
    cam = bpy.data.objects.get("IconCam")
    if cam is None:
        cam = bpy.data.objects.new("IconCam", bpy.data.cameras.new("IconCam"))
        scene.collection.objects.link(cam)
        sun = bpy.data.objects.new("IconSun", bpy.data.lights.new("IconSun", "SUN"))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), 0, math.radians(30))
        scene.collection.objects.link(sun)
    cam.data.type = "ORTHO"
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    centre = sum(corners, Vector()) / 8
    extent = max((c - centre).length for c in corners)
    cam.data.ortho_scale = extent * 2.1
    direction = Vector((1.0, -1.0, 0.9)).normalized()
    cam.location = centre + direction * 10
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.film_transparent = True
    scene.render.resolution_x = size * 4
    scene.render.resolution_y = size * 4
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    icon = bpy.data.images.load(path)
    icon.scale(size, size)
    icon.filepath_raw = path
    icon.save()
    for o in scene.objects:
        o.hide_render = False


def check_extent(name, obj, spec):
    """A piece's mesh must stay inside the footprint it declares: placement, the walk grid and
    the rules for what fits where all go by that footprint, so a counter overhanging it would
    clip its neighbour. Nothing may stick out to the sides (or above, bar the 4 mm strip of
    tape on a box); handles may stand 0.02 out in front and the back may sit 0.014 into the
    wall. (Still centred here: back +y.)"""
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    half_w, half_d = spec["width"] / 2, spec["depth"] / 2
    problems = []
    if min(xs) < -half_w - 0.0025 or max(xs) > half_w + 0.0025:
        problems.append("width %.3f..%.3f, declared +-%.3f" % (min(xs), max(xs), half_w))
    if min(ys) < -half_d - 0.02:
        problems.append("front at %.3f, declared %.3f (+0.02 for handles)" % (min(ys), -half_d))
    if max(ys) > half_d + 0.014:
        problems.append("back at %.3f, declared %.3f (+0.014 into the wall)" % (max(ys), half_d))
    if max(zs) > spec["height"] + 0.004:
        problems.append("height %.3f, declared %.3f" % (max(zs), spec["height"]))
    if problems:
        raise SystemExit("RVKIT ERROR: piece %s leaves its declared footprint: %s" % (name, "; ".join(problems)))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    tex_dir = os.path.join(MEDIA, "textures")
    os.makedirs(os.path.join(tex_dir, "Vehicles"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA, "models_X", "vehicles"), exist_ok=True)
    palette = None if SHELLS_ONLY else build_palette(os.path.join(tex_dir, "Vehicles", "MELens_RV.png"))

    furniture = []
    textures = {}
    for name, spec in (PIECES.items() if not SHELLS_ONLY else ()):
        b = Builder("rv_" + name)
        spec["build"](b)
        obj = b.finish()
        check_extent(name, obj, spec)
        # origin at the middle of the back edge, so any piece lines up with a spot's wall
        for v in obj.data.vertices:
            v.co.y -= spec["depth"] / 2
        piece_texture = os.path.join(tex_dir, "Vehicles", "MELensRV_%s.png" % name)
        if FLAT:
            # every face already maps to its flat colour in the palette: the piece's texture is the palette
            shutil.copyfile(os.path.join(tex_dir, "Vehicles", "MELens_RV.png"), piece_texture)
            palette_material(obj, palette)
            textures[obj.name] = palette
        else:
            size = 512      # one size for every piece: the furniture shader samples it texel by texel (melens_cutaway_part.frag)
            textures[obj.name] = bake_piece(obj, piece_texture, size)
            if OUTLINES:
                add_outline(obj)
        furniture.append(obj)
    if not SHELLS_ONLY:
        export(furniture, os.path.join(MEDIA, "models_X", "vehicles", "MELens_RV.fbx"))

    lua_dir = os.path.join(MEDIA, "lua", "shared")
    os.makedirs(lua_dir, exist_ok=True)
    shells = []
    for spec_path in MEASURES:
        with open(spec_path, "r", encoding="utf-8-sig") as handle:
            spec = json.load(handle)
        with open(spec["measure"], "r", encoding="utf-8-sig") as handle:
            measure = json.load(handle)
        parts = build_shell(measure, spec, tex_dir)
        shells.extend(parts)
        if "grid" in spec:
            shell_walk_grid(parts, spec, lua_dir)
    if shells:
        # The flat picture of an item that has no 3D model (loose items, model MELensDecal): a one tile
        # square lying flat with its texture mapped across it; the game binds the item's icon when it draws.
        decal = UVBuilder("decal")
        decal.poly([Vector((-0.5, -0.5, 0.0)), Vector((0.5, -0.5, 0.0)), Vector((0.5, 0.5, 0.0)), Vector((-0.5, 0.5, 0.0))],
                   [(0, 1), (1, 1), (1, 0), (0, 0)], Vector((0.0, 0.0, 1.0)))
        shells.append(decal.finish())
        export(shells, os.path.join(MEDIA, "models_X", "vehicles", SHELL_FILE + ".fbx"))

    # Inventory icons come from the painted art (tools-src/art/icons.py); a render of the
    # model only stands in for a piece that has none yet.
    icon_art = os.path.normpath(os.path.join(ART, "..", "icons"))
    for obj in furniture:
        piece_name = obj.name[3:]
        if PIECES[piece_name]["kind"] == "model":
            continue
        if not os.path.exists(os.path.join(icon_art, "icon_%s.png" % piece_name)):
            render_icon(obj, textures[obj.name], os.path.join(tex_dir, "Item_MELensRV_%s.png" % piece_name))

    lines = ["-- Generated by tools-src/blender/rv_kit.py; do not edit.",
             "MELens = MELens or {}",
             "MELens.RVKit = {"]
    for name, spec in PIECES.items():
        if spec["kind"] == "model":
            continue
        lines.append('    %s = { width = %.3f, depth = %.3f, height = %.3f, capacity = %d, kind = "%s", label = "%s" },' % (
            name, spec["width"], spec["depth"], spec["height"], spec["capacity"], spec["kind"], spec["label"]))
    lines.append("}")
    with open(os.path.join(lua_dir, "MELens_RVKit.lua"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    print("RVKIT pieces=%d shells=%d" % (len(furniture), len(shells)))


main()
