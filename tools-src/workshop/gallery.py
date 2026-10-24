"""Export titled gallery layouts from real native captures and the authored header.

Run through the resource guard. JPEG exports must pass TinyPNG before publication.
No gameplay pixels are painted, generated or retouched. Crops and sizes are recorded.
"""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps,ImageSequence

ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'tools-src/art/workshop-gallery-20261024'
FONT='C:/Windows/Fonts/bahnschrift.ttf'
FONT_BODY='C:/Windows/Fonts/segoeui.ttf'
INK=(238,237,227);MUTED=(187,193,176);BG=(23,25,23)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def font(size,body=False):return ImageFont.truetype(FONT_BODY if body else FONT,size)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vanilla-run',default='gallery-20261024-vanilla')
    parser.add_argument('--neat-run',default='gallery-20261024-neat-clean')
    parser.add_argument('--output',type=Path,default=ROOT/'build/rv/gallery-20261024-layouts')
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    legacy=ART/'originals'
    photos=ROOT/'build/rv'/args.vanilla_run/'vehicles'
    header=Image.open(ART/'header-master.png').convert('RGB')
    rows=[]
    def card(title,sub,size):
        im=Image.new('RGB',(size,size),BG);h=size//8
        if size==2048:band=header.crop((0,336,2243,616)).resize((size,h),Image.Resampling.LANCZOS)
        else:band=ImageOps.fit(header,(size,h),Image.Resampling.LANCZOS)
        im.paste(band,(0,0));d=ImageDraw.Draw(im);ratio=size/2048
        d.text((int(40*ratio),int(22*ratio)),'REAL VEHICLE INTERIORS',font=font(max(14,int(29*ratio))),fill=MUTED)
        f=font(int(90*ratio))
        while d.textbbox((0,0),title,font=f)[2]>size-int(80*ratio):f=font(f.size-1)
        d.text((int(40*ratio),int(74*ratio)),title,font=f,fill=INK)
        d.text((int(40*ratio),int(183*ratio)),sub,font=font(max(16,int(38*ratio)),True),fill=MUTED)
        return im
    def save(im,name,title,sub,sources,**extra):
        p=out/name;im.save(p,'JPEG',quality=94,optimize=True,subsampling=0)
        rows.append(dict(file=name,title=title,info=sub,dimensions=list(im.size),format='JPEG',bytesBeforeCompression=p.stat().st_size,
                         sourceFiles=[dict(path=s.relative_to(ROOT).as_posix(),sha256=sha(s)) for s in sources],sha256BeforeCompression=sha(p),**extra))
    def collage(name,title,sub,panels):
        if len(panels)>4:
            raise ValueError('Workshop collages must contain no more than four scenes')
        im=card(title,sub,2048);d=ImageDraw.Draw(im);crops=[]
        for i,(label,stem,box) in enumerate(panels):
            x=24+(i%2)*1012;y=280+(i//2)*864
            d.text((x+14,y+1),label,font=font(49),fill=INK)
            src=photos/(stem+'-interior.png');shot=Image.open(src).convert('RGB').crop(box)
            tile=ImageOps.fit(shot,(988,784),Image.Resampling.LANCZOS)
            im.paste(tile,(x,y+56));crops.append(dict(file=src.name,crop=list(box),label=label))
        d.text((40,1997),'Counts include livery and specialist variants. Four examples shown.',font=font(31,True),fill=MUTED)
        save(im,name,title,sub,[photos/(p[1]+'-interior.png') for p in panels],panels=crops)
    collage('01-vanilla-vehicles.jpg','96 VANILLA VARIANTS SUPPORTED','Cargo vans, ambulances, radio vans and step vans',[
        ('Cargo van','vanilla-cargo-van',(425,90,1295,780)),
        ('Ambulance','vanilla-ambulance',(455,65,1325,755)),
        ('Delivery step van','delivery-van',(295,65,1165,755)),
        ('Radio van','radio-van',(505,45,1375,735))])
    collage('02-ki5-vehicles.jpg','107 KI5 VARIANTS SUPPORTED','Campers, buses, trucks and vans • Vehicle packs required',[
        ('Ford Econoline E150','econoline',(435,85,1375,830)),
        ('Chevrolet Step-Van','chevy-step-van',(570,135,1165,607)),
        ('Ford F350 Ambulance','ambulance',(515,215,1205,762)),
        ('Ford F700 Armored Truck','armored-truck',(550,145,1240,692))])
    for name,title,sub,stem,box in [
        ('05-bus-interior.jpg','WALK AROUND YOUR BUS','Passenger seating and a clear centre aisle','bus',(450,65,1310,748)),
        ('06-cargo-storage.jpg','TAKE YOUR SUPPLIES WITH YOU','Vehicle-specific fittings and usable cargo storage','cargo-truck',(470,35,1330,718))]:
        im=card(title,sub,2048);src=photos/(stem+'-interior.png');tile=ImageOps.contain(Image.open(src).convert('RGB').crop(box),(2000,1680),Image.Resampling.LANCZOS)
        im.paste(tile,((2048-tile.width)//2,280+(1680-tile.height)//2));save(im,name,title,sub,[src],crop=list(box))
    title='CUSTOM RV FURNITURE';sub='Pick up, place and rearrange your interior'
    im=card(title,sub,1024);src=legacy/'furniture-ground.jpg';tile=ImageOps.contain(Image.open(src).convert('RGB'),(1024,730),Image.Resampling.LANCZOS)
    im.paste(tile,((1024-tile.width)//2,168+(730-tile.height)//2));ImageDraw.Draw(im).text((32,946),'Beds • Kitchenettes • Storage • Heating',font=font(30,True),fill=MUTED)
    save(im,'07-custom-furniture.jpg',title,sub,[src])
    for neat,run,name,title,sub in [
        (False,args.vanilla_run,'08-vanilla-dashboard.jpg','VANILLA DASHBOARD','Vanilla-style window and controls by default'),
        (True,args.neat_run,'09-neat-dashboard.jpg','NEAT UI DASHBOARD','Automatically matches enabled NEAT UI mods')]:
        folder=ROOT/'build/rv'/run/'dashboard';src=folder/('dashboard-neat.png' if neat else 'dashboard-vanilla.png')
        if not src.exists():continue
        report=json.loads((folder/'native-feature-tests.json').read_text());b=report['bounds'];box=(b['x'],b['y'],b['x']+b['width'],b['y']+b['height'])
        tile=ImageOps.contain(Image.open(src).convert('RGB').crop(box),(960,740),Image.Resampling.LANCZOS)
        im=card(title,sub,1024);im.paste(tile,((1024-tile.width)//2,160+(740-tile.height)//2));ImageDraw.Draw(im).text((32,948),'Fuel, water, power, appliances and your home.',font=font(29,True),fill=MUTED)
        save(im,name,title,sub,[src],crop=list(box),nativeWindow=b,actualNeatActive=report['neat'])
    for name,source,title,sub in [
        ('03-enter-your-camper.gif','cover-entering-camper.gif','STEP INSIDE','The interior travels with your vehicle.'),
        ('04-walk-inside.gif','walking-inside-camper.gif','MOVE FREELY','Walk around your home on the road.'),
        ('10-zombies-outside.gif','zombies-attacking-rv.gif','THE WORLD KEEPS MOVING','Zombies can still hear you and attack.')]:
        src=legacy/source;original=Image.open(src);frames=[];durations=[]
        for frame in ImageSequence.Iterator(original):
            im=Image.new('RGB',(512,512),BG);im.paste(ImageOps.fit(header,(512,128),Image.Resampling.LANCZOS),(0,0))
            im.paste(frame.convert('RGB').resize((512,288),Image.Resampling.LANCZOS),(0,128))
            draw=ImageDraw.Draw(im)
            draw.text((18,16),'REAL VEHICLE INTERIORS',font=font(14),fill=MUTED)
            draw.text((18,49),title,font=font(32),fill=INK)
            words=sub.split();lines=['']
            for word in words:
                trial=(lines[-1]+' '+word).strip()
                if draw.textbbox((0,0),trial,font=font(22,True))[2]>476:lines.append(word)
                else:lines[-1]=trial
            for i,line in enumerate(lines):draw.text((18,438+i*28),line,font=font(22,True),fill=INK)
            frames.append(im);durations.append(frame.info.get('duration',100))
        sample=Image.new('RGB',(512,len(frames)*128))
        for i,frame in enumerate(frames):sample.paste(frame.resize((512,128)),(0,i*128))
        target=out/name
        for colors in (192,160,128,96,80,64):
            palette=sample.quantize(colors=colors,method=Image.Quantize.MEDIANCUT)
            encoded=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames]
            encoded[0].save(target,save_all=True,append_images=encoded[1:],duration=durations,loop=0,disposal=1,optimize=True)
            if target.stat().st_size<980000:break
        assert target.stat().st_size<1000000,(name,target.stat().st_size)
        rows.append(dict(file=name,title=title,info=sub,dimensions=[512,512],format='GIF',frames=len(frames),durationMs=sum(durations),colors=colors,bytes=target.stat().st_size,
                         sha256=sha(target),sourceFiles=[dict(path=src.relative_to(ROOT).as_posix(),sha256=sha(src))],compression='Shared palette and delta export. TinyPNG does not support GIF.'))
    rows.sort(key=lambda r:r['file'])
    manifest=dict(version='2.0.13',workshopId='3811728541',supportCounts=dict(vanillaVariants=96,ki5Variants=107,totalVariants=203),
                  artwork=dict(master=(ART/'header-master.png').relative_to(ROOT).as_posix(),masterSha256=sha(ART/'header-master.png'),tool='built-in ImageGen',usage='Title-band background only'),
                  gameplay='Native production screenshots/footage only; no generated or retouched gameplay. Crops, resizing and titles only.',images=rows)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Gallery exported:',len(rows),'images to',out)
if __name__=='__main__':main()
