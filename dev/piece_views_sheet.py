"""Developer helper: join dev/piece_views.py's renders into one sheet, one row per piece, one column per corner.

    python dev/piece_views_sheet.py <views dir> <sheet.png> <piece> [<piece> ...]"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

src, out, names = sys.argv[1], sys.argv[2], sys.argv[3:]
font = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf"), 18)
corners = (45, 135, 225, 315)
words = {45: "front, right", 135: "back, right", 225: "back, left", 315: "front, left"}
tile = 400
sheet = Image.new("RGB", (tile * 4 + 6, (tile + 4) * len(names)), (25, 25, 28))
for r, name in enumerate(names):
    for c, yaw in enumerate(corners):
        im = Image.open(os.path.join(src, "%s_%d.png" % (name, yaw))).convert("RGB")
        sheet.paste(im, (c * (tile + 2), r * (tile + 4)))
        d = ImageDraw.Draw(sheet)
        label = "%s  %s" % (name, words[yaw])
        x, y = c * (tile + 2), r * (tile + 4)
        d.rectangle((x, y, x + d.textlength(label, font=font) + 16, y + 26), fill=(0, 0, 0))
        d.text((x + 8, y + 3), label, fill=(255, 255, 255), font=font)
sheet.save(out)
print("sheet", out, sheet.size)
