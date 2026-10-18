"""Lays the pick map from dev/lua/pick_map.lua over a screenshot of the test game: each spot index the right-click
pick finds gets its own colour, outlined where the pick changes, and the index is written at the middle of the top
of every piece. Compare the colours with the pieces drawn under them: a box should be covered by its own colour.

    python dev/pick_map.py build/rv/dbg/pick_map.txt build/rv/dbg/pick_map_shot.png build/rv/dbg/pick_map.png
    [--offset 8,31]   game screen point -> screenshot pixel (window border and title bar)
"""
import argparse
import colorsys

from PIL import Image, ImageDraw


def colour(key):
    if key == "-":
        return None
    if key in ("p", "d", "l"):
        return (255, 255, 255)
    n = int(key)
    h = (n * 0.618034) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("map")
    ap.add_argument("shot")
    ap.add_argument("out")
    ap.add_argument("--offset", default="8,31")
    ap.add_argument("--alpha", type=int, default=110)
    ap.add_argument("--wire", help="corner file from dev/lua/box_wire.lua: draw the pieces as the pick projects them")
    args = ap.parse_args()
    ox, oy = (int(v) for v in args.offset.split(","))
    if args.wire:
        shot = Image.open(args.shot).convert("RGB")
        draw = ImageDraw.Draw(shot)
        for entry in open(args.wire, encoding="utf-8-sig").read().strip().split(";"):
            index, pts = entry.split(":")
            p = [tuple(float(v) for v in xy.split(",")) for xy in pts.split()]
            p = [(ox + x, oy + y) for x, y in p]
            col = colour(index)
            for a, b in ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)):
                draw.line([p[a], p[b]], fill=col, width=1)
            cx = sum(x for x, _ in p[4:]) / 4
            cy = sum(y for _, y in p[4:]) / 4
            draw.text((cx - 6, cy - 6), index, fill=(255, 255, 255))
        shot.save(args.out)
        print("saved", args.out, shot.size)
        return
    text = open(args.map, encoding="utf-8-sig").read().strip()
    head, cells, labels = text.split("|")
    x0, y0, step, cols, rows = (int(v) for v in head.split())
    cells = cells.split(",")
    shot = Image.open(args.shot).convert("RGBA")
    over = Image.new("RGBA", shot.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(over)
    for r in range(rows):
        for c in range(cols):
            key = cells[r * cols + c]
            col = colour(key)
            if not col:
                continue
            px, py = ox + x0 + c * step - step / 2, oy + y0 + r * step - step / 2
            draw.rectangle([px, py, px + step - 1, py + step - 1], fill=col + (args.alpha,))
            # outline where the pick changes
            right = cells[r * cols + c + 1] if c + 1 < cols else "-"
            below = cells[(r + 1) * cols + c] if r + 1 < rows else "-"
            if right != key:
                draw.line([px + step - 1, py, px + step - 1, py + step - 1], fill=(0, 0, 0, 255))
            if below != key:
                draw.line([px, py + step - 1, px + step - 1, py + step - 1], fill=(0, 0, 0, 255))
    out = Image.alpha_composite(shot, over)
    draw = ImageDraw.Draw(out)
    for label in labels.split(";"):
        if not label:
            continue
        index, sx, sy = label.split(":")
        px, py = ox + int(sx), oy + int(sy)
        draw.text((px - 6, py - 6), index, fill=(0, 0, 0, 255))
        draw.text((px - 7, py - 7), index, fill=(255, 255, 255, 255))
    out.convert("RGB").save(args.out)
    print("saved", args.out, out.size)


if __name__ == "__main__":
    main()
