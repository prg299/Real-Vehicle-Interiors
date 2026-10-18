"""The dashboard's UI shapes, drawn by code (no image model, nothing taken from another mod): white,
anti-aliased quarter discs and quarter rings for rounded corners, and a disc for switch knobs. The
dashboard tints them when it draws (MELens_Dashboard.lua).
    python tools-src/art/ui_shapes.py mod/RealVehicleInteriors/common/media
Writes <media>/ui/MELens/{corner,ring}_{tl,tr,bl,br}.png and knob.png."""
import os
import sys

from PIL import Image

SIZE = 32          # drawn large and scaled down by the game: smooth at any corner radius
SAMPLES = 4        # sub-pixel samples per axis for the anti-aliasing
RING = 2.2         # the ring's width at SIZE (about 1 px at a radius of 12-16)


def coverage(size, inside):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    px = img.load()
    for y in range(size):
        for x in range(size):
            hit = 0
            for sy in range(SAMPLES):
                for sx in range(SAMPLES):
                    if inside(x + (sx + 0.5) / SAMPLES, y + (sy + 0.5) / SAMPLES):
                        hit += 1
            px[x, y] = (255, 255, 255, round(255 * hit / SAMPLES ** 2))
    return img


def main():
    out = os.path.join(sys.argv[1], "ui", "MELens")
    os.makedirs(out, exist_ok=True)
    # the circle's centre is the corner of the texture that faces the rectangle's inside
    centres = {"tl": (SIZE, SIZE), "tr": (0, SIZE), "bl": (SIZE, 0), "br": (0, 0)}
    for name, (cx, cy) in centres.items():
        def disc(x, y, cx=cx, cy=cy):
            return (x - cx) ** 2 + (y - cy) ** 2 <= SIZE ** 2

        def ring(x, y, cx=cx, cy=cy):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            return SIZE - RING <= d <= SIZE
        coverage(SIZE, disc).save(os.path.join(out, "corner_%s.png" % name))
        coverage(SIZE, ring).save(os.path.join(out, "ring_%s.png" % name))
    half = SIZE / 2
    coverage(SIZE, lambda x, y: (x - half) ** 2 + (y - half) ** 2 <= half ** 2).save(os.path.join(out, "knob.png"))
    print("ui shapes in", out)


if __name__ == "__main__":
    main()
