"""Viewpoint 0.1.6.1 camera/entry checks in the parent's guarded inactive desktop.

The disposable profile starts with Viewpoint setup completed as a settings fixture.
Camera changes, entry/exit, walking and furniture menus use production keyboard
and mouse dispatch. No camera setter or feature handler is invoked by this driver.
"""
import importlib.util
import json
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
    interior = load('final-interior-tests')
    tap, h = interior.load_helpers()
    h.configure(run / 'camera-checks')
    config = json.loads((run / 'native-session.json').read_text('utf-8-sig'))
    cache = next(arg.split('=', 1)[1] for arg in config['command'] if arg.startswith('-cachedir='))
    h.SCREENS = Path(cache) / 'Screenshots'

    def state():
        return h.lua('''local p=getPlayer();local v=p:getVehicle()
local q=v and MELens.profileFor(v)
return {active=MELensRV.viewpointActive(),nextView=Viewpoint.View.next(),
 inside=v~=nil,standing=MELens.isStanding(p),vanilla=v and MELens.inVanillaSeat(p,v,q),
 queue=#ISTimedActionQueue.getTimedActionQueue(p).queue,java=MELensRV.status(),
 x=p:getX(),y=p:getY(),cabin=MELens.debugState()}''')

    def until(predicate, label, timeout=35):
        end = time.monotonic() + timeout
        last = None
        while time.monotonic() < end:
            last = state()
            if time.monotonic() >= h._input_release and predicate(last):
                return last
            time.sleep(.12)
        raise AssertionError(f'{label}: {json.dumps(last)}')

    def key(code, label, shift=False, ms=200):
        h.lua(f'MEMCNativeLab.holdKey({int(code)},{ms});' +
              (f'MEMCNativeLab.holdKey(Keyboard.KEY_LSHIFT,{ms});' if shift else '') + 'return true')
        h._input_release = time.monotonic() + ms / 1000 + .5
        h.REPORT['inputs'].append(dict(action=label, key=code, shift=shift, durationMs=ms,
                                       api='MEMCNativeLab.holdKey'))
        h.REPORT['nativeInput'] = True

    def view_key():
        return int(h.lua('return Viewpoint.Keys.trigger(Viewpoint.Keys.get("keys.firstPerson"))'))

    def perspective(third, label):
        before = state()
        if not before['active']:
            key(view_key(), label + '-on')
            until(lambda s: s['active'], label + ' enabled')
        if (state()['nextView'] == 'isometric') != third:
            # The profile's declared third-person binding, including its modifier.
            code = int(h.lua('return Viewpoint.Keys.trigger(Viewpoint.Keys.get("keys.thirdPerson"))'))
            key(code, label + '-third-person', shift=True)
        return until(lambda s: s['active'] and s['nextView'] == ('isometric' if third else 'third'), label)

    def approach():
        code = int(h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local q=Vector3f.new()
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q)
local dx,dy=q:x()-p:getX(),q:y()-p:getY();local sx,sy=dx-dy,dx+dy
return getCore():getKey(math.abs(sx)>math.abs(sy) and (sx>0 and "Right" or "Left") or (sy>0 and "Backward" or "Forward"))'''))
        key(code, 'fixture-door-approach', ms=150)
        time.sleep(.8)

    def spawn(vehicle):
        h.check(not state()['inside'], 'spawn fixture requires an outside character')
        h.lua('''local p=getPlayer();p:setX(10813.5);p:setY(10140.5)
p:setLastX(10813.5);p:setLastY(10140.5);return true''')
        source = (ROOT / 'dev/lua/spawn_one.lua').read_text().replace('NAME', vehicle)
        h.lua(source.replace('tonumber("7")', 'tonumber("-4")'))
        h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local q=Vector3f.new()
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"outside"),q)
p:setX(q:x());p:setY(q:y());p:setLastX(q:x());p:setLastY(q:y())
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q)
p:faceLocation(q:x(),q:y());local dx,dy=q:x()-p:getX(),q:y()-p:getY()
local n=math.sqrt(dx*dx+dy*dy);p:setForwardDirection(dx/n,dy/n)
p:setTimedActionInstantCheat(false)
ISUIHandler.setVisibleAllUI(true);return true''')
        # Refresh the native player square/near-vehicle state via ordinary movement.
        approach()

    def leave(label):
        h.lua('return MELensInteriorTest.positionAtExit()')
        interior.poll(h, lambda s: interior.idle(s), label='at exit fixture')
        key(int(h.lua('return getCore():getKey("Interact")')), label)
        return until(lambda s: not s['inside'] and s['queue'] == 0, label)

    try:
        h.check(state()['nextView'] == 'first', 'test must start isometric')
        for vehicle, third, label in [
            ('Base.Trailer54FlyingCloud22', False, 'camper-first-person'),
            ('Base.87fordB700school', True, 'bus-third-person'),
        ]:
            spawn(vehicle)
            before = perspective(third, label)
            h.capture(label + '-outside')
            key(int(h.lua('return getCore():getKey("Interact")')), label + '-enter')
            after = until(lambda s: s['standing'] and s['queue'] == 0 and not s['active'], label + ' entry')
            h.check(after['nextView'] == 'first' and 'shader=ok' in after['java'], 'entry did not restore isometric renderer')
            h.record(label + '-entry-handoff', before, after, fixture='outside door position only')
            h.capture(label + '-inside-isometric')
            h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
            h.lua(interior.FIXTURE)
            if not third:
                # Existing driver: real world-menu bed/dinette Rest, E stand, Dashboard, exit and entry.
                interior.run_interior_cases(h, tap, before_entry=approach)
            before = state()
            code = int(h.lua('return getCore():getKey("Forward")'))
            key(code, label + '-walk', ms=450)
            after = until(lambda s: s['standing'] and not s['active'], label + ' walk')
            h.check(abs(after['cabin']['x'] - before['cabin']['x']) +
                    abs(after['cabin']['z'] - before['cabin']['z']) > .02, 'native interior movement was blocked')
            h.record(label + '-walking', before, after)
            key(view_key(), label + '-camera-key-inside')
            after = until(lambda s: not s['active'] and s['standing'], label + ' stays isometric')
            h.record(label + '-interior-camera-guard', before, after)
            leave(label + '-exit')
            outside = perspective(third, label + '-after-exit')
            h.capture(label + '-after-exit')
            h.record(label + '-viewpoint-after-exit', after, outside)
            key(view_key(), label + '-back-to-isometric')
            until(lambda s: not s['active'], 'back to isometric')

        spawn('Base.87fordF700box')
        # Driver membership is fixture setup. Test only that normal Viewpoint input
        # remains usable in the cab; it must not be treated as a walk-in interior.
        h.lua('''local p=getPlayer();local v=MELensTest.vehicle;assert(v:enter(0,p))
v:setCharacterPosition(p,0,"inside");v:playPassengerAnim(0,"idle");return true''')
        before = state()
        h.check(before['vanilla'], 'cab fixture is not a vanilla seat')
        after = perspective(False, 'f700-driver-camera')
        time.sleep(1)
        h.check(state()['active'], 'walk-in camera guard disabled the driver camera')
        h.record('vanilla-driver-camera-unaffected', before, after, directEntryIsFixture=True)
        h.capture('f700-driver-first-person')
        key(view_key(), 'driver-back-to-isometric')
        until(lambda s: not s['active'], 'driver isometric')
        h.REPORT['passed'] = True
        h.REPORT['unverified'] = ['dedicated multiplayer', 'split screen', 'controller', 'human acceptance']
        status = 0
    except Exception:
        h.REPORT.update(passed=False, error=traceback.format_exc())
        try:
            h.REPORT['lastState'] = state()
            h.capture('viewpoint-failure')
        except Exception:
            pass
        print(h.REPORT['error'], flush=True)
        status = 1
    (h.OUTPUT / 'report.json').write_text(json.dumps(h.REPORT, indent=2), encoding='utf-8')
    print('VIEWPOINT_NATIVE_PASSED' if status == 0 else 'VIEWPOINT_NATIVE_FAILED', flush=True)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
