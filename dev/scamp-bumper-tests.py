"""Fixed-camera ownership control for the Scamp rear bumper's floor penetration.

Diagnostic fixtures only: spawn, cabin entry, camera and individual keep planes.
The normal exterior and workflow are verified separately by the final shell pass.
"""
import json
import os
from pathlib import Path
import time
import traceback
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    isolation = load('shell-isolation-tests')
    h = load('final-feature-tests')
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h.configure(run/'scamp-bumper-isolation')
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=', 1)[1] for x in session['command']
                         if x.startswith('-cachedir=')))/'Screenshots'
    prior = h.lua('''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
return {height=o:getOption("wallHeight"):getValue(),camera=o:getOption("cameraWalls"):getValue()}''')
    active = False
    try:
        h.REPORT['scope'] = __doc__
        h.REPORT['nativeInput'] = False
        for name in ('Base.Trailer87Scamp13', 'Base.Trailer87Scamp16'):
            for heading in ('E', 'S'):
                isolation.setup(h, name, heading)
                key = 'Scamp13' if name.endswith('13') else 'Scamp16'
                identity = isolation.models(h, key, None, 'scamp16_spare_rear')
                bumper = isolation.find_mesh(identity['survey'], 'scamp16_bumper')
                h.check(bumper['model'] == '87scampCamperRear0', 'unexpected rear bumper alias')
                baseline = h.lua(isolation.BASELINE)
                active = True
                h.lua('''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue(2);o:getOption("cameraWalls"):setValue(true);o:apply();return true''')
                h.lua(isolation.RESTORE)
                time.sleep(.5)
                prefix = key.lower()+'-'+heading.lower()
                frames = {'baseline': h.capture(prefix+'-baseline')}
                h.lua('MELensRV.setKeepPlane("87scampCamperRear0",0,0,0,1);return true')
                time.sleep(.4)
                frames['bumper-hidden'] = h.capture(prefix+'-bumper-hidden')
                h.lua(isolation.RESTORE)
                h.lua('MELensRV.setKeepPlane("87scampCamperRear0",0,0,-1,4.310444);return true')
                time.sleep(.4)
                frames['bumper-below-floor'] = h.capture(prefix+'-bumper-below-floor')
                h.check(not h.lua('return MELensRV.shaderError()'), 'shader error')
                h.lua(isolation.RESTORE)
                time.sleep(.4)
                frames['restored'] = h.capture(prefix+'-restored')
                h.record(prefix, {'alias':bumper, 'profileBaseline':baseline},
                         {'keepPlane':[0,0,-1,4.310444], 'physicalMaximumY':-.328},
                         frames=frames, sameCamera=True, visualReview='pending')
                h.lua('MELensShellIsolation=nil;return true')
                active = False
        h.REPORT['unverified'] = ['human visual adjudication', 'production input', 'exterior restoration']
        h.write_report('passed')
        return 0
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        h.write_report('failed', error)
        return 1
    finally:
        if active:
            h.lua(isolation.RESTORE)
            h.lua('MELensShellIsolation=nil;return true')
        h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({int(prior['height'])});o:getOption("cameraWalls"):setValue({str(prior['camera']).lower()});o:apply()
local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return true''')


if __name__ == '__main__':
    raise SystemExit(main())
