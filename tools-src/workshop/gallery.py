"""Export widescreen Workshop gallery cards from original native captures.

Run through the resource guard. JPEG derivatives need TinyPNG before publication.
The square main cover is separate: additional previews target the 16:9 gallery.
No gameplay pixels are generated or retouched. Only cropping, layout and titles.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageSequence

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / 'tools-src/art/workshop-gallery-20261024'
FONT = 'C:/Windows/Fonts/bahnschrift.ttf'
FONT_BODY = 'C:/Windows/Fonts/segoeui.ttf'
INK, MUTED, BG = (238, 237, 227), (187, 193, 176), (23, 25, 23)
STILL_SIZE, CLIP_SIZE = (1920, 1080), (640, 360)
MAX_SCENES = 4
PREVIEW_MAX_BYTES = 990000  # leave room within app 108600's 1 MB staging quota


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size, body=False):
    return ImageFont.truetype(FONT_BODY if body else FONT, size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vanilla-run', default='gallery-20261024-vanilla')
    parser.add_argument('--neat-run', default='gallery-20261024-neat-clean')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/rv/gallery-20261024-widescreen')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    originals = ART / 'originals'
    photos = ROOT / 'build/rv' / args.vanilla_run / 'vehicles'
    header = Image.open(ART / 'header-master.png').convert('RGB')
    rows = []

    def source_record(path):
        return dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path))

    def card(title, sub):
        im = Image.new('RGB', STILL_SIZE, BG)
        im.paste(ImageOps.fit(header, (1920, 150), Image.Resampling.LANCZOS), (0, 0))
        draw = ImageDraw.Draw(im)
        title_font = font(72)
        while draw.textbbox((0, 0), title, font=title_font)[2] > 1848:
            title_font = font(title_font.size - 1)
        draw.text((36, 14), title, font=title_font, fill=INK)
        draw.text((38, 100), sub, font=font(34, True), fill=MUTED)
        return im

    def fit_photo(path, size, crop=None):
        original = Image.open(path).convert('RGB')
        x0, y0, x1, y1 = crop or (0, 0, original.width, original.height)
        width, height = x1-x0, y1-y0
        ratio = size[0] / size[1]
        if width / height > ratio:
            trim = (width - height * ratio) / 2
            x0, x1 = x0+trim, x1-trim
        else:
            trim = (height - width / ratio) / 2
            y0, y1 = y0+trim, y1-trim
        actual = tuple(round(v) for v in (x0, y0, x1, y1))
        return original.crop(actual).resize(size, Image.Resampling.LANCZOS), list(actual)

    def save(im, name, title, sub, sources, **extra):
        assert im.width * 9 == im.height * 16, 'Gallery previews must be 16:9'
        path = out / name
        im.save(path, 'JPEG', quality=94, optimize=True, subsampling=0)
        rows.append(dict(file=name, title=title, info=sub, dimensions=list(im.size),
                         format='JPEG', bytesBeforeCompression=path.stat().st_size,
                         sourceFiles=[source_record(p) for p in sources],
                         sha256BeforeCompression=sha(path), **extra))

    def collage(name, title, sub, panels):
        if len(panels) > MAX_SCENES:
            raise ValueError('Workshop collages must contain no more than four scenes')
        im = card(title, sub)
        draw, crops = ImageDraw.Draw(im), []
        for i, (label, stem, crop) in enumerate(panels):
            x, y = 18 + (i % 2) * 951, 160 + (i // 2) * 438
            draw.text((x+10, y), label, font=font(43), fill=INK)
            path = photos / (stem + '-interior.png')
            tile, actual = fit_photo(path, (933, 370), crop)
            im.paste(tile, (x, y+52))
            crops.append(dict(file=path.name, crop=actual, label=label))
        draw.text((28, 1043), 'Counts include livery and specialist variants. Four examples shown.',
                  font=font(27, True), fill=MUTED)
        save(im, name, title, sub, [photos / (p[1]+'-interior.png') for p in panels],
             panels=crops, sceneCount=len(panels))

    collage('01-vanilla-vehicles.jpg', '96 VANILLA VARIANTS SUPPORTED',
            'Cargo vans, ambulances, radio vans and step vans', [
        ('Cargo van', 'vanilla-cargo-van', (300, 205, 1420, 650)),
        ('Ambulance', 'vanilla-ambulance', (280, 190, 1450, 654)),
        ('Delivery step van', 'delivery-van', (50, 180, 1460, 740)),
        ('Radio van', 'radio-van', (310, 195, 1480, 659))])
    collage('02-ki5-vehicles.jpg', '107 KI5 VARIANTS SUPPORTED',
            'Campers, buses, trucks and vans • Vehicle packs required', [
        ('Ford Econoline E150', 'econoline', (120, 140, 1530, 700)),
        ('Chevrolet Step-Van', 'chevy-step-van', (420, 215, 1370, 592)),
        ('Ford F350 Ambulance', 'ambulance', (390, 280, 1390, 677)),
        ('Ford F700 Armored Truck', 'armored-truck', (385, 230, 1415, 639))])

    for name, title, sub, path in [
        ('05-bus-interior.jpg', 'WALK AROUND YOUR BUS', 'Passenger seating and a clear centre aisle', photos / 'bus-interior.png'),
        ('06-cargo-storage.jpg', 'TAKE YOUR SUPPLIES WITH YOU', 'Vehicle-specific fittings and usable cargo storage', photos / 'cargo-truck-interior.png'),
        ('07-custom-furniture.jpg', 'CUSTOM RV FURNITURE', 'Pick up, place and rearrange your interior', originals / 'furniture-ground.jpg')]:
        im = card(title, sub)
        tile, actual = fit_photo(path, (1920, 930))
        im.paste(tile, (0, 150))
        save(im, name, title, sub, [path], crop=actual, sceneCount=1)

    for neat, run, name, title, sub in [
        (False, args.vanilla_run, '08-vanilla-dashboard.jpg', 'VANILLA DASHBOARD', 'Vanilla-style window and controls by default'),
        (True, args.neat_run, '09-neat-dashboard.jpg', 'NEAT UI DASHBOARD', 'Automatically matches enabled NEAT UI mods')]:
        folder = ROOT / 'build/rv' / run / 'dashboard'
        path = folder / ('dashboard-neat.png' if neat else 'dashboard-vanilla.png')
        report = json.loads((folder / 'native-feature-tests.json').read_text())
        bounds = report['bounds']
        crop = (bounds['x'], bounds['y'], bounds['x']+bounds['width'], bounds['y']+bounds['height'])
        tile = ImageOps.contain(Image.open(path).convert('RGB').crop(crop), (1176, 884), Image.Resampling.LANCZOS)
        im = card(title, sub)
        im.paste(tile, (24, 172+(884-tile.height)//2))
        draw = ImageDraw.Draw(im)
        for y, heading, lines in [
            (220, 'GENERATOR & BATTERY', ['Fuel, condition and charging', 'Power your lights and fridge']),
            (485, 'WATER & APPLIANCES', ['Fresh water and propane', 'Cooking, cooling and heating']),
            (750, 'YOUR HOME', ['Rename your vehicle', 'Repaint the interior walls'])]:
            draw.text((1250, y), heading, font=font(43), fill=INK)
            for i, line in enumerate(lines):
                draw.text((1250, y+66+i*54), line, font=font(35, True), fill=MUTED)
        save(im, name, title, sub, [path], crop=list(crop), nativeWindow=bounds,
             actualNeatActive=report['neat'], sceneCount=1)

    for name, source, title, sub in [
        ('03-enter-your-camper.gif', 'cover-entering-camper.gif', 'STEP INSIDE', 'The interior travels with your vehicle.'),
        ('04-walk-inside.gif', 'walking-inside-camper.gif', 'MOVE FREELY', 'Walk around your home on the road.'),
        ('10-zombies-outside.gif', 'zombies-attacking-rv.gif', 'THE WORLD KEEPS MOVING', 'Zombies can still hear you and attack.')]:
        path = originals / source
        frames, durations = [], []
        for frame in ImageSequence.Iterator(Image.open(path)):
            im = ImageOps.fit(frame.convert('RGB'), CLIP_SIZE, Image.Resampling.LANCZOS)
            draw = ImageDraw.Draw(im)
            title_font = font(26)
            badge_width = draw.textbbox((0, 0), title, font=title_font)[2] + 28
            # Keep the walking character at the back of the camper unobscured.
            badge_x = 628 - badge_width
            im.paste(ImageOps.fit(header, (badge_width, 46), Image.Resampling.LANCZOS), (badge_x, 10))
            draw.text((badge_x+14, 16), title, font=title_font, fill=INK)
            draw.rectangle((0, 327, 640, 360), fill=BG)
            draw.text((15, 330), sub, font=font(19, True), fill=INK)
            frames.append(im)
            durations.append(frame.info.get('duration', 100))
        sample = Image.new('RGB', (640, len(frames)*90))
        for i, frame in enumerate(frames):
            sample.paste(frame.resize((640, 90)), (0, i*90))
        target = out / name
        for colors in (192, 160, 128, 96, 80, 64, 48):
            palette = sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
            encoded = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
            encoded[0].save(target, save_all=True, append_images=encoded[1:], duration=durations,
                            loop=0, disposal=1, optimize=True)
            if target.stat().st_size < PREVIEW_MAX_BYTES:
                break
        assert target.stat().st_size < PREVIEW_MAX_BYTES, (name, target.stat().st_size)
        rows.append(dict(file=name, title=title, info=sub, dimensions=list(CLIP_SIZE), format='GIF',
                         frames=len(frames), durationMs=sum(durations), colors=colors, bytes=target.stat().st_size,
                         sha256=sha(target), sourceFiles=[source_record(path)], sceneCount=1,
                         compression='Shared palette and delta export. TinyPNG does not support GIF.'))

    rows.sort(key=lambda row: row['file'])
    for row in rows:
        width, height = row['dimensions']
        if width * 9 != height * 16 or row['sceneCount'] > MAX_SCENES:
            raise ValueError('Gallery previews require a 16:9 canvas and at most four scenes')
    manifest = dict(version='2.0.13', workshopId='3811728541',
        supportCounts=dict(vanillaVariants=96, ki5Variants=107, totalVariants=203),
        deliveryTarget=dict(surface='Additional Steam Workshop gallery previews, separate from main cover',
            aspectRatio='16:9', stillDimensions=list(STILL_SIZE), clipDimensions=list(CLIP_SIZE), maxScenes=MAX_SCENES,
            nonPowerOfTwoReason='Match the destination landscape viewer, measured at 637x358; owner rejected square letterboxed cards.'),
        artwork=dict(master=(ART / 'header-master.png').relative_to(ROOT).as_posix(),
            masterSha256=sha(ART / 'header-master.png'), tool='built-in ImageGen', usage='Existing title-band background only; unchanged master'),
        gameplay='Native production screenshots/footage only. Crops, resizing, layout and titles; no generated or retouched gameplay.',
        images=rows, order=[row['file'] for row in rows])
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Widescreen gallery exported:', len(rows), 'images to', out)


if __name__ == '__main__':
    main()
