"""Native cab-cap renders at all three production wall-height settings.

Option selection, spawn, heading, seat and camera are render fixtures. This does
not exercise the Mod Options menu or driving input.
"""
import importlib.util
import argparse
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', action='append', help='Exact supported vehicle script IDs')
    parser.add_argument('--empty', action='store_true', help='Remove furniture in this disposable render fixture')
    parser.add_argument('--all-headings', action='store_true')
    parser.add_argument('--output-name', default='cab-wall-settings')
    parser.add_argument('--front-positions', nargs='+', type=float,
                        help='Fixed-camera native front-protection controls in passenger metres, restored after each wall setting')
    parser.add_argument('--front-tops', nargs='+', type=float,
                        help='Cross front controls with these protected top heights, restoring the profile default afterward')
    parser.add_argument('--native-exterior-control', action='store_true',
                        help='Capture the normal exterior after each heading without moving the camera')
    args = parser.parse_args()
    if args.front_tops and not args.front_positions:parser.error('--front-tops requires --front-positions')
    assert args.output_name and all(c.isalnum() or c=='-' for c in args.output_name)
    spec = importlib.util.spec_from_file_location('native_checks', ROOT/'dev/final-feature-tests.py')
    h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h.configure(run/args.output_name)
    config = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=', 1)[1] for x in config['command'] if x.startswith('-cachedir=')))/'Screenshots'
    prior = h.lua('return PZAPI.ModOptions:getOptions("RealVehicleInteriors"):getOption("wallHeight"):getValue()')
    try:
        for name in args.only or ['Base.87fordF700bank', 'Base.85chevyStepVanCitrusWave', 'Base.VanAmbulance']:
            for heading in (['E', 'N', 'S', 'W'] if args.all_headings else ['N', 'W']):
                h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true''')
                spawn = (ROOT/'dev/lua/spawn_one.lua').read_text().replace('NAME', name)
                spawn = spawn.replace('tonumber("7")', 'tonumber("-4")').replace('local HEADING = "E"', f'local HEADING = "{heading}"')
                h.lua(spawn); time.sleep(.4)
                if args.empty:
                    h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local P=MELens.Parts
for i in ipairs(pr.spots) do local part=P.spotPart(v,i)
if part then if part:getItemContainer() then part:getItemContainer():getItems():clear() end
part:setInventoryItem(nil);P.applyPiece(v,part) end end;return true''')
                h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
assert(v:enter(MELens.cabinSeat(v),getPlayer()));local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
                deadline=time.monotonic()+15
                while not h.lua('return MELens.isStanding(getPlayer())'):
                    h.check(time.monotonic()<deadline,'standing render fixture timed out')
                    time.sleep(.1)
                h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);local g=MELens.WalkGrids[pr.walkGrid]
getGameTime():setTimeOfDay(12)
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell*.45);return true''')
                deadline=time.monotonic()+20
                while h.lua('return MELens.pathing(getPlayer()) or #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue>0'):
                    h.check(time.monotonic()<deadline,'centered render fixture timed out')
                    time.sleep(.1)
                length=h.lua('local g=MELens.WalkGrids[MELens.profileFor(MELensTest.vehicle).walkGrid];return #g.rows*g.cell')
                target=.75 if length>4 else .5
                for _ in range(8):
                    zoom=h.lua('return getCore():getZoom(0)')
                    if abs(zoom-target)<.02:break
                    h.lua(f'getCore():doZoomScroll(0,{1 if zoom<target else -1});return true');time.sleep(.2)
                for choice, label in [(1, 'low'), (2, 'medium'), (3, 'high')]:
                    h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({choice});o:apply();return true''')
                    time.sleep(.6)
                    h.check(not h.lua('return MELensRV.shaderError()'), 'cutaway shader error')
                    prefix=name.split('.', 1)[1].lower()+'-'+heading.lower()+'-'+label
                    h.capture(prefix)
                    if args.front_positions:
                        default=h.lua('local pr=MELens.profileFor(MELensTest.vehicle);return {front=pr.cutFront,top=pr.cutFrontTop}')
                        h.check(default.get('front') is not None and default.get('top') is not None,
                                'front-protection diagnostic requires both profile values')
                        def front(position, top=None):
                            top=default['top'] if top is None else top
                            h.lua(f'''local pr=MELens.profileFor(MELensTest.vehicle)
MELensRV.setCutFront({position}/pr.mesh.scale)
MELensRV.setCutFrontTop(pr.mesh.lift-{top}/pr.mesh.scale);return true''')
                        try:
                            for position in args.front_positions:
                                for top in args.front_tops or [default['top']]:
                                    front(position,top);time.sleep(.4)
                                    tag=('-front-%04dmm'%round(position*1000))
                                    if args.front_tops:tag+='-top-%04dmm'%round(top*1000)
                                    h.capture(prefix+tag)
                        finally:front(default['front'])
                        time.sleep(.4);h.capture(prefix+'-front-restored-control')
                    details={'wallHeight': choice,'emptyFixture':args.empty}
                    if args.front_positions:
                        details.update(frontControls=args.front_positions,topControls=args.front_tops,
                                       restoredProfileDefault=default)
                    h.record(name+'-'+heading+'-'+label, {}, details, scope=__doc__)
                if args.native_exterior_control:
                    h.lua('MELensTest.vehicle:exit(getPlayer());return true');time.sleep(.7)
                    h.check(h.lua('return getPlayer():getVehicle()==nil'),'native exterior control failed to exit')
                    h.capture(name.split('.',1)[1].lower()+'-'+heading.lower()+'-native-exterior-control')
        h.REPORT['scope'] = __doc__
        h.REPORT['unverified'] = ['Mod Options menu input', 'human acceptance']
        h.write_report('passed'); return 0
    except Exception:
        error = traceback.format_exc(); print(error, flush=True)
        h.write_report('failed', error); return 1
    finally:
        h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({int(prior)});o:apply()
local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return true''')


if __name__ == '__main__':
    raise SystemExit(main())
