"""Clean native gameplay screenshots for manual Workshop gallery selection.

Character position and camera are capture fixtures; furnishing is factory stock.
No painted/generated content, UI feature proof or Workshop upload is implied.
"""
import importlib.util
import argparse
import json
import os
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-name',default='gallery')
    parser.add_argument('--only',action='append',help='Capture only these scene labels into a separate output folder')
    parser.add_argument('--zoom',type=float,choices=[.5,.75],help='Override each scene\'s fitted framing')
    args=parser.parse_args()
    assert args.output_name and all(c.isalnum() or c=='-' for c in args.output_name)
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h=load('final-feature-tests');h.configure(run/args.output_name)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    scenes=[
        ('vanilla-cargo-van','Base.Van','N',.5),
        ('vanilla-ambulance','Base.VanAmbulance','N',.5),
        ('bus','Base.87fordB700school','N',.75),
        ('econoline','Base.86fordE150long','N',.5),
        ('chevy-step-van','Base.85chevyStepVanCitrusWave','N',.75),
        ('armored-truck','Base.87fordF700bank','N',.75),
        ('ambulance','Base.90fordF350ambulance','N',.75),
        ('delivery-van','Base.StepVan_Zippee','W',.5),
        ('mystery-van','Base.86fordE150mm','W',.5),
        ('service-truck','Base.90fordF350SWAT','N',.75),
        ('cargo-truck','Base.87fordF700box','N',.75),
        ('radio-van','Base.VanRadio','N',.5),
        ('mobile-library','Base.StepVan_MobileLibrary','N',.75),
        ('catering-van','Base.StepVanAirportCatering','N',.5),
    ]
    if args.only:
        unknown=set(args.only)-{scene[0] for scene in scenes}
        if unknown:parser.error('unknown gallery scenes: '+', '.join(sorted(unknown)))
        scenes=[scene for scene in scenes if scene[0] in args.only]
    try:
        # Render-only captures may use a larger window. Native mouse tests keep
        # the input harness's established 1280x720 coordinate contract.
        h.lua('getCore():setResolutionAndFullScreen(1600,900,false);return true');time.sleep(2)
        h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
getGameTime():setTimeOfDay(12);return true''')
        h.lua('''local rain=getClimateManager():getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY)
rain:setEnableAdmin(true);rain:setAdminValue(0);return true''')
        h.REPORT['scenes']=[]
        for label,name,heading,preferred_zoom in scenes:
            target_zoom=args.zoom if args.zoom is not None else preferred_zoom
            h.lua('''local p=getPlayer();p:setX(10813.5);p:setY(10140.5)
p:setLastX(10813.5);p:setLastY(10140.5);return true''')
            spawn=(ROOT/'dev/lua/spawn_one.lua').read_text().replace('NAME',name)
            spawn=spawn.replace('tonumber("7")','tonumber("-4")').replace('local HEADING = "E"',f'local HEADING = "{heading}"')
            h.lua(spawn);time.sleep(1)
            h.lua('''local v=MELensTest.vehicle;local p=getPlayer();local pr=MELens.profileFor(v);local P=MELens.Parts
-- Keep the vehicle's actual factory fittings and cargo loot in review images.
assert(v:enter(MELens.cabinSeat(v),p));return true''')
            deadline=time.monotonic()+12
            while not h.lua('return MELens.isStanding(getPlayer())'):
                assert time.monotonic()<deadline,'gallery standing fixture failed'
                time.sleep(.1)
            # The entry highlight is useful in play, but should not cover the
            # furniture in the promotional frame. Put the character in the aisle.
            fraction=.25 if label=='radio-van' else .45
            h.lua(f'''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell*{fraction});return true''')
            deadline=time.monotonic()+20
            while h.lua('return MELens.pathing(getPlayer())'):
                assert time.monotonic()<deadline,'gallery capture position timed out'
                time.sleep(.1)
            for _ in range(12):
                zoom=h.lua('return getCore():getZoom(0)')
                if abs(zoom-target_zoom)<.02:break
                h.lua(f'getCore():doZoomScroll(0,{1 if zoom<target_zoom else -1});return true');time.sleep(.35)
            h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z(),q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
MELensGalleryClear=function() MELensRV.clearMarker();MELensRV.clearSpotMarkers() end
Events.OnTick.Add(MELensGalleryClear);ISUIHandler.setVisibleAllUI(false);return true''')
            time.sleep(.6)
            assert not h.lua('return MELensRV.shaderError()'),'gallery cutaway shader error'
            interior=h.capture(label+'-interior')
            h.lua('''local p=getPlayer();p:getVehicle():exit(p);return true''');time.sleep(.7)
            exterior=h.capture(label+'-exterior')
            h.lua('''Events.OnTick.Remove(MELensGalleryClear);MELensGalleryClear=nil
MELensMedia.cameraOff();return true''')
            h.REPORT['scenes'].append(dict(label=label,vehicle=name,heading=heading,interior=interior,exterior=exterior))
        h.lua('ISUIHandler.setVisibleAllUI(true);return true')
        h.REPORT['scope']='Native game renderer; full-resolution screenshots with UI hidden, capture fixtures only'
        print(h.write_report('passed'),flush=True);return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1
    finally:
        h.lua('''if MELensGalleryClear then Events.OnTick.Remove(MELensGalleryClear);MELensGalleryClear=nil end
MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true)
getCore():setResolutionAndFullScreen(1280,720,false);return true''')
        h.lua('getClimateManager():getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY):setEnableAdmin(false);return true')


if __name__=='__main__':raise SystemExit(main())
