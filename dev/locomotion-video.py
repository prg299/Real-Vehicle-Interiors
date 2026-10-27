"""Record real keyboard walk/run input in the owned native locomotion prototype.

Only the disposable van is emptied before recording so the legs are visible.
The native recorder timestamps every captured frame; encoding preserves timing.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'dev' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    _, h = load('final-interior-tests').load_helpers()
    h.configure(run / 'motion')
    h.SCREENS = run / 'home/Zomboid/Screenshots'
    scan_code = load('final-mp-motion-tests').ROUTE_SCAN
    report = {'scope': __doc__, 'clips': [], 'passed': False}
    path = run / 'video-capture.json'

    def save():
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def keycodes(names):
        return [int(h.lua('return getCore():getKey(' + json.dumps(name) + ')')) for name in names]

    def hold(codes, milliseconds):
        h.lua(';'.join(f'MEMCNativeLab.holdKey({k},{milliseconds})' for k in codes) + ';return true')

    def state():
        return h.lua('''local p=getPlayer();local d=MELens.debugState()
return {x=d.x,z=d.z,standing=MELens.isStanding(p),alpha=p:getAlpha(0),
 targetAlpha=p:getTargetAlpha(0),animation=MELensRV.animInfo(p),
 tracks=MELensDevBones.tracks(p),worldX=p:getX(),worldY=p:getY()}''')

    def record(name, seconds, action):
        clip = {'name': name, 'seconds': seconds, 'events': [],
                'capture': 'Native GL_BACK, timestamped JPEG frames, bounded 15 FPS; silent',
                'input': 'MEMCNativeLab keyboard-state events through the production movement input path'}
        report['clips'].append(clip)
        h.lua(f'MELensMedia.clip({json.dumps(name)},{seconds});return true')
        started = time.monotonic()
        action(clip, started)
        time.sleep(max(0, seconds + 1.5 - (time.monotonic() - started)))
        csv = h.SCREENS / name / 'frames.csv'
        assert csv.is_file() and len(csv.read_text().splitlines()) > seconds * 5, 'too few native frames'
        clip['frameCount'] = len(csv.read_text().splitlines())
        save()
        print('RECORDED', name, clip['frameCount'], flush=True)

    def outside(clip, started):
        time.sleep(1)
        for keys, duration in [(('Forward',), 1.2), (('Backward', 'Run'), 1.2)]:
            clip['events'].append({'at': time.monotonic()-started, 'keys': keys, 'before': state()})
            hold(keycodes(keys), int(duration*1000))
            time.sleep(duration)
            h.lua('MEMCNativeLab.releaseKeys();return true')
            time.sleep(1)

    def inside(clip, started):
        time.sleep(1)
        for running in (False, False, True, True, False):
            scan = h.lua(scan_code)
            routes = h._sequence(scan['rows'])
            routes.sort(key=lambda r: (r['free'] > .6, r['free'] * (.8 + .2*r['longitudinal'])), reverse=True)
            route = routes[0]
            assert route['free'] > .35, 'no clear native keyboard route'
            codes = [int(k) for k in h._sequence(route['keys'])]
            if running:
                codes += keycodes(('Run',))
            origin = state()
            goal = min(1.25, max(.2, route['free']-.22))
            event = {'at': time.monotonic()-started, 'running': running,
                     'route': route, 'targetDistance': goal, 'before': origin, 'samples': []}
            clip['events'].append(event)
            hold(codes, 3000)
            limit = time.monotonic()+2.2
            while time.monotonic() < limit:
                now = state()
                event['samples'].append(now)
                assert now['standing'], 'native input unexpectedly left the interior'
                if math.hypot(now['x']-origin['x'], now['z']-origin['z']) >= goal:
                    break
                time.sleep(.075)
            h.lua('MEMCNativeLab.releaseKeys();return true')
            event['releasedAt'] = time.monotonic()-started
            time.sleep(.85)
            event['after'] = state()
            save()

    try:
        package = run / 'home/Zomboid/mods/RealVehicleInteriors'
        report['payloadHashes'] = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in package.rglob('*') if p.is_file()}
        h.lua('MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(false);getCore():setAutoZoom(0,false);return true')
        for _ in range(10):
            zoom = h.lua('return getCore():getZoom(0)')
            if abs(zoom-.5) < .02:
                break
            h.lua(f'getCore():doZoomScroll(0,{1 if zoom < .5 else -1});return true')
            time.sleep(.2)
        time.sleep(1)
        record('clip-outside-native-movement', 8, outside)
        load('bed-tests').enter(h, 'Base.StepVan', 'E')
        report['fixture'] = h.lua('''local v=MELensTest.vehicle;local q=MELens.profileFor(v);local P=MELens.Parts
local n=0
for i=1,#q.spots do local part=P.spotPart(v,i)
 if part then local c=part:getItemContainer();if c then c:clear() end
 if part:getInventoryItem() then n=n+1 end;part:setInventoryItem(nil);P.settle(v,part) end
end
ISUIHandler.setVisibleAllUI(false)
return {vehicle="Base.StepVan",heading="E",removedFittings=n,
 scope="Owned disposable van only; empty floor makes foot motion visible"}''')
        time.sleep(1.5)
        h.capture('interior-video-framing')
        record('clip-inside-native-movement', 20, inside)
        h.capture('interior-video-end')
        report['passed'] = True
        save()
    except Exception as error:
        report['error'] = str(error)
        report['traceback'] = traceback.format_exc()
        save()
        raise
    finally:
        try:
            h.lua('MEMCNativeLab.releaseKeys();return true')
        except Exception:
            pass


if __name__ == '__main__':
    main()
