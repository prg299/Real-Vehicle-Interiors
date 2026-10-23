"""Native cab-cap renders at all three production wall-height settings.

Option selection, spawn, heading, seat and camera are render fixtures. This does
not exercise the Mod Options menu or driving input.
"""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('native_checks', ROOT/'dev/final-feature-tests.py')
    h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h.configure(run/'cab-wall-settings')
    config = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=', 1)[1] for x in config['command'] if x.startswith('-cachedir=')))/'Screenshots'
    prior = h.lua('return PZAPI.ModOptions:getOptions("RealVehicleInteriors"):getOption("wallHeight"):getValue()')
    try:
        for name in ['Base.87fordF700bank', 'Base.85chevyStepVanCitrusWave', 'Base.VanAmbulance']:
            for heading in ['N', 'W']:
                h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true''')
                spawn = (ROOT/'dev/lua/spawn_one.lua').read_text().replace('NAME', name)
                spawn = spawn.replace('tonumber("7")', 'tonumber("-4")').replace('local HEADING = "E"', f'local HEADING = "{heading}"')
                h.lua(spawn); time.sleep(.4)
                h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
assert(v:enter(MELens.cabinSeat(v),getPlayer()));local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z(),q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
                for choice, label in [(1, 'low'), (2, 'medium'), (3, 'high')]:
                    h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({choice});o:apply();return true''')
                    time.sleep(.6)
                    h.check(not h.lua('return MELensRV.shaderError()'), 'cutaway shader error')
                    h.capture(name.split('.', 1)[1].lower()+'-'+heading.lower()+'-'+label)
                    h.record(name+'-'+heading+'-'+label, {}, {'wallHeight': choice}, scope=__doc__)
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
