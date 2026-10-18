"""Developer helper: turn dev/preview_interiors.ps1's raw window captures into captioned
previews (client area only, cropped round the vehicle).
    python dev/preview_crop.py <captures dir> <out dir> key|Title|What is inside [key|...]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

CLIENT = (8, 31, 1288, 751)       # the game's client area inside the window capture
CROP = (120, 90, 1200, 710)       # round the vehicle (relative to the client area)


def font(size):
    for name in ("segoeui.ttf", "arial.ttf"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for spec in sys.argv[3:]:
        key, title, text = spec.split("|", 2)
        image = Image.open(os.path.join(src, key + ".png")).convert("RGB").crop(CLIENT).crop(CROP)
        band = Image.new("RGBA", (image.width, 54), (0, 0, 0, 150))
        image = image.convert("RGBA")
        image.alpha_composite(band, (0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((14, 5), title, fill=(255, 255, 255), font=font(24))
        draw.text((14, 32), text, fill=(215, 215, 215), font=font(15))
        path = os.path.join(out, key + ".png")
        image.convert("RGB").save(path)
        print("saved", path, image.size)


main()
