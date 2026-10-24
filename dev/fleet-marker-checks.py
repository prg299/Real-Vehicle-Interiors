"""Controlled native render captures separating floor highlights from geometry gaps."""
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
    parser.add_argument('--vehicle',default='Base.86fordE150LVairportShuttle')
    parser.add_argument('--heading',choices=['E','N','S','W'],default='W')
    parser.add_argument('--output-name',default='marker-checks')
    args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    interior,beds=load('final-interior-tests'),load('bed-tests')
    assert args.output_name and all(c.isalnum() or c=='-' for c in args.output_name)
    tap,h=interior.load_helpers();h.configure(run/args.output_name)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    try:
        assert not h.lua('return getPlayer():getVehicle()~=nil')
        h.lua('''MELensMedia.cameraOff();getGameTime():setTimeOfDay(12)
local p=getPlayer();p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true''')
        beds.enter(h,args.vehicle,args.heading)
        h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
for i,spot in ipairs(MELens.profileFor(v).spots) do
if spot.default=="bed" or spot.default=="kitchen" then local part=P.spotPart(v,i)
part:setInventoryItem(instanceItem(P.itemType(spot.default)));P.applyPiece(v,part) end end
return true''')
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
        for _ in range(10):
            zoom=h.lua('return getCore():getZoom(0)')
            if abs(zoom-.75)<.02:break
            h.lua(f'getCore():doZoomScroll(0,{1 if zoom<.75 else -1});return true');time.sleep(.5)
        h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local g=MELens.WalkGrids[pr.walkGrid];local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);getGameTime():setMultiplier(0);return true''')
        time.sleep(.5)
        h.REPORT['controlWorldAge']=h.lua('return getGameTime():getWorldAgeHours()')
        h.capture('marker-control-a');h.capture('marker-control-b')
        h.lua('''MELensMarkerDiagnosticClear=function() MELensRV.clearMarker();MELensRV.clearSpotMarkers() end
Events.OnTick.Add(MELensMarkerDiagnosticClear);MELensMarkerDiagnosticClear();return true''')
        time.sleep(.3);h.capture('marker-disabled')
        h.REPORT['disabledWorldAge']=h.lua('return getGameTime():getWorldAgeHours()')
        h.check(h.REPORT['controlWorldAge']==h.REPORT['disabledWorldAge'],'world time advanced during marker control')
        h.lua('''Events.OnTick.Remove(MELensMarkerDiagnosticClear);MELensMarkerDiagnosticClear=nil
getGameTime():setMultiplier(1);MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return true''')
        h.lua('return MELensInteriorTest.positionAtExit()')
        interior.poll(h,lambda s:interior.idle(s),label='marker diagnostic exit position')
        interior.interact_key(h,'marker diagnostic exit')
        interior.poll(h,lambda s:not s['interior']['inside'],label='marker diagnostic outside')
        h.REPORT['scope']='Native renderer control only; scene furnishing, framing and marker switch are fixtures'
        print(h.write_report('passed'),flush=True);return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1
    finally:
        h.lua('''if MELensMarkerDiagnosticClear then
Events.OnTick.Remove(MELensMarkerDiagnosticClear);MELensMarkerDiagnosticClear=nil end
getGameTime():setMultiplier(1);MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return true''')


if __name__=='__main__':raise SystemExit(main())
