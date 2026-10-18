"""Developer helper: put several captures on one sheet, so one iteration's result is one image to look at.
    python dev/contact_sheet.py <out.png> [--cols N] [--width W] <image> [<image> ...]
Each image is scaled to W pixels wide (default 540) and labelled with its file name."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for name in ("segoeui.ttf", "arial.ttf"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main():
    args = sys.argv[1:]
    out, cols, width = args.pop(0), 2, 540
    while args and args[0].startswith("--"):
        flag, value = args.pop(0), args.pop(0)
        if flag == "--cols":
            cols = int(value)
        elif flag == "--width":
            width = int(value)
    paths = [p for p in args if os.path.exists(p)]
    if not paths:
        sys.exit("no images")
    tiles = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
        draw = ImageDraw.Draw(image)
        label = os.path.splitext(os.path.basename(path))[0]
        draw.rectangle((0, image.height - 22, 8 + 9 * len(label), image.height), fill=(0, 0, 0))
        draw.text((4, image.height - 21), label, fill=(255, 255, 255), font=font(15))
        tiles.append(image)
    cols = min(cols, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    height = max(t.height for t in tiles)
    sheet = Image.new("RGB", (cols * width + (cols - 1) * 4, rows * height + (rows - 1) * 4), (30, 30, 30))
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % cols) * (width + 4), (i // cols) * (height + 4)))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print("sheet", out, sheet.size)


if __name__ == "__main__":
    main()
