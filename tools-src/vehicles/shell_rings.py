"""The rings the inside shell's walls are built from: shared by rv_kit.py (which models the shell, in
Blender) and make_vehicles.py (which fits the furniture to the same walls), so both see one lining.

A ring is `segments` points (x, z) round the vehicle, evenly by angle from its middle, taken from a
measured outline of the body (tools-src/blender/measure_vehicle.py: the inside of KI5's hull at a
height) and moved towards the middle by the inset. The lining stands on rings from `lowestOutline`
up. Where the hull tucks in under the floor (a trailer's rounded ends and bilges: spec floorOutline)
the floor follows the hull's inside at floor height, and the wall slopes up from it to the lowest ring,
inside the hull all the way."""
import math


def resample(outline, centre, n):
    """n points of the outline, evenly by angle around centre (x, z in passenger space)."""
    cx, cz = centre
    pts = sorted(((math.atan2(z - cz, x - cx), x, z) for x, z in outline))
    out = []
    for i in range(n):
        a = -math.pi + (i + 0.5) * 2 * math.pi / n
        # interpolate between the two neighbours in angle
        for j in range(len(pts)):
            a0, x0, z0 = pts[j - 1]
            a1, x1, z1 = pts[j]
            if j == 0:
                a0 -= 2 * math.pi
            if a0 <= a <= a1:
                t = (a - a0) / (a1 - a0) if a1 > a0 else 0.0
                out.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t))
                break
        else:
            # past the last point's angle: between it and the first point, a turn on
            a0, x0, z0 = pts[-1]
            a1, x1, z1 = pts[0]
            a1 += 2 * math.pi
            t = (a - a0) / (a1 - a0) if a1 > a0 else 0.0
            out.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t))
    return out


def resample_corners(outline, centre, n, turn=35.0):
    """resample(), with the outline's own corners among the points: a point of the ring that is nearest a
    corner (a turn of more than `turn` degrees) in angle is the corner itself. Angular samples alone cut a
    rectangle's corners off with a chord, leaving a gap between the shell and the hull's corner."""
    ring = resample(outline, centre, n)
    cx, cz = centre
    pts = sorted(outline, key=lambda p: math.atan2(p[1] - cz, p[0] - cx))
    count = len(pts)
    taken = set()
    for i in range(count):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % count]
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 < 1e-6 or l2 < 1e-6:
            continue
        if (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2) > math.cos(math.radians(turn)):
            continue
        angle = math.atan2(b[1] - cz, b[0] - cx)
        index = min(range(len(ring)), key=lambda k: abs((math.atan2(ring[k][1] - cz, ring[k][0] - cx) - angle + math.pi) % (2 * math.pi) - math.pi))
        if index not in taken:
            taken.add(index)
            ring[index] = (b[0], b[1])
    return ring


def resample_bridging(outline, centre, n, gap=0.08):
    """resample(), but where the outline has a gap (an arch: the hull's skin is open round a wheel, so no
    point in those directions is the hull's) the ring runs straight between the two ends of the gap,
    where resample() would bend towards whatever it found beyond."""
    ring = resample(outline, centre, n)
    far = [min(math.hypot(x - px, z - pz) for px, pz in outline) > gap for x, z in ring]
    if all(far) or not any(far):
        return ring
    count = len(ring)
    for start in range(count):
        if far[start] and not far[start - 1]:
            end = start
            while far[end % count]:
                end += 1
            a, b = ring[start - 1], ring[end % count]
            span = end - start + 1
            for k in range(start, end):
                t = (k - start + 1) / span
                ring[k % count] = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    return ring


def inset_ring(ring, distance):
    """The closed ring moved `distance` inwards along its edges' normals, with mitred corners: a rectangle
    stays a rectangle, `distance` smaller on every side (toward() would pull a corner along the diagonal to
    the middle and leave the walls kinked there)."""
    n = len(ring)
    area = sum(ring[i][0] * ring[(i + 1) % n][1] - ring[(i + 1) % n][0] * ring[i][1] for i in range(n)) / 2
    sign = 1.0 if area > 0 else -1.0

    def normal(p, q):
        dx, dz = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dz) or 1.0
        return (-dz / length * sign, dx / length * sign)

    out = []
    for i in range(n):
        a, b, c = ring[i - 1], ring[i], ring[(i + 1) % n]
        n1, n2 = normal(a, b), normal(b, c)
        k = distance / max(0.3, 1.0 + n1[0] * n2[0] + n1[1] * n2[1])
        out.append((b[0] + (n1[0] + n2[0]) * k, b[1] + (n1[1] + n2[1]) * k))
    return out


def toward(point, centre, distance):
    """`point` moved `distance` towards `centre`."""
    x, z = point
    cx, cz = centre
    d = max(1e-6, math.hypot(cx - x, cz - z))
    return (x + (cx - x) * distance / d, z + (cz - z) * distance / d)


def floor_key(measure, floor_y):
    """The key of the measured outline at the floor's height, or None when there is none near it."""
    key = min(measure["outlines"], key=lambda k: abs(float(k) - floor_y))
    if abs(float(key) - floor_y) > 0.03 or not measure["outlines"][key]:
        return None
    return key


def build(measure, cfg, floor_measure=None):
    """The lining for a shell config `cfg` (keys floorY, top, refHeight, lowestOutline, segments, inset and
    optionally floorOutline {inset, band}) measured by `measure`; `floor_measure` is a second measurement
    that has the floor's height among its outlines (default: `measure`).

    Returns a dict: rings [(height, ring)] from the floor up, room ring (the ring the walls stand on, for the
    cutaway's clip of KI5's body details), the centre (x, z), and hull_at_floor (the measured outline at the
    floor's height, or None)."""
    floor_y = cfg["floorY"]
    top = cfg.get("top", 1.5)
    inset = cfg.get("inset", 0.03)
    lowest = cfg.get("lowestOutline", 0.10)
    heights = sorted(float(h) for h in measure["outlines"] if measure["outlines"][h])
    heights = [h for h in heights if lowest <= h <= top]
    ref = measure["outlines"][min(measure["outlines"], key=lambda k: abs(float(k) - cfg.get("refHeight", 0.3)))]
    centre = (sum(p[0] for p in ref) / len(ref), sum(p[1] for p in ref) / len(ref))
    n = cfg.get("segments", 72)
    rings = []
    sample = resample_corners if cfg.get("sharpCorners") else resample
    for h in [floor_y] + heights:
        outline = measure["outlines"]["%.2f" % max(h, heights[0])]
        raw = sample(outline, centre, n)
        rings.append((h, inset_ring(raw, inset) if cfg.get("sharpCorners") else [toward(p, centre, inset) for p in raw]))
    room_ring = list(rings[0][1])

    floor_measure = floor_measure or measure
    key = floor_key(floor_measure, floor_y)
    hull_at_floor = floor_measure["outlines"][key] if key else None
    if cfg.get("floorOutline"):
        if not hull_at_floor:
            raise ValueError("no measured outline at the floor height %.2f" % floor_y)
        spec = cfg["floorOutline"]
        lined = rings[0][1]
        snug = []
        for p, (lx, lz) in zip(resample_bridging(hull_at_floor, centre, n), lined):
            fx, fz = toward(p, centre, spec.get("inset", 0.004))
            # the outline can bulge where the hull has an opening: never beyond the ring above
            if math.hypot(fx - centre[0], fz - centre[1]) > math.hypot(lx - centre[0], lz - centre[1]):
                fx, fz = lx, lz
            snug.append((fx, fz))
        band = spec.get("band", 0.06)
        t = band / (rings[1][0] - floor_y)
        # (a hair further in than the straight line: the hull's outlines are measured 0.1 apart in height, and
        # its skin curves between them)
        slope = [toward((sx + (lx - sx) * t, sz + (lz - sz) * t), centre, spec.get("slopeInset", 0.008))
                 for (sx, sz), (lx, lz) in zip(snug, lined)]
        rings = [(floor_y, snug), (floor_y + band, slope)] + rings[1:]
    return {"rings": rings, "room_ring": room_ring, "centre": centre, "hull_at_floor": hull_at_floor}


def ring_at(rings, height):
    """The lining's outline at `height`, between the rings (points interpolated pairwise), or None."""
    for (ha, ra), (hb, rb) in zip(rings, rings[1:]):
        if ha <= height <= hb and hb > ha:
            t = (height - ha) / (hb - ha)
            return [(ax + (bx - ax) * t, az + (bz - az) * t) for (ax, az), (bx, bz) in zip(ra, rb)]
    return None
