"""Additional native window, door, orientation and scope checks; parent owns game."""
import json
import os
import time
import traceback
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'dev' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def main():
    vision, bed, interior = load('vision-tests'), load('bed-tests'), load('final-interior-tests')
    tap, h = interior.load_helpers()
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    h.configure(run / 'vision-coverage'); h.SCREENS = run / 'home/Zomboid/Screenshots'
    h.REPORT['scope'] = 'real native vehicle/zombie fixtures, same-clock spotting contracts and natural window acquisition; entry/exit inputs are covered by the separate core/UI runs'

    def wait(predicate, label, seconds=40):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if h.lua(predicate): return
            time.sleep(.15)
        raise AssertionError(label)

    def exit_vehicle():
        h.lua('if MELensVisionTest then MELensVisionTest.clear() end;return true')
        if not h.lua('return getPlayer():getVehicle()~=nil'): return
        h.lua('getPlayer():getVehicle():exit(getPlayer());return true')
        time.sleep(.3)

    def enter(name, heading='E'):
        exit_vehicle()
        # Keep every spawn on the same reviewed grass patch. Otherwise repeated
        # rear-door exits accumulate displacement toward trees/buildings.
        h.lua('local p=getPlayer();p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true')
        spawn = (ROOT/'dev/lua/spawn_one.lua').read_text().replace('NAME', name)
        spawn = spawn.replace('tonumber("7")','tonumber("-4")').replace('local HEADING = "E"',f'local HEADING = "{heading}"')
        h.lua(spawn)
        h.lua('assert(MELensTest.vehicle:enter(MELens.cabinSeat(MELensTest.vehicle),getPlayer()));return true')
        wait('return MELens.isStanding(getPlayer())', 'native seat fixture did not establish interior')
        time.sleep(.7)
        h.lua((ROOT / 'dev/lua/vision-fixture.lua').read_text())
        h.REPORT.setdefault('vehicleFixtures', []).append(dict(vehicle=name, heading=heading, seatFixture=True))

    def check_pair(label, x, z, blocked=True, old=False):
        result = vision.pair(h, x, z, old=old, blocked=blocked)
        h.record(label, None, result, scope='same-clock forced native sight contract')
        h.lua('MELensVisionTest.clear();return true')

    try:
        for heading in ('E','S','W'):
            enter('Base.87fordF700box', heading)
            check_pair('f700-rotated-solid-hull-' + heading, 5,-2)
        # Missing/destroyed doors must remain real openings, not invulnerable hull.
        h.lua('local d=MELensTest.vehicle:getPartById("TrunkDoor");d:getDoor():setOpen(false);d:setCondition(0);return true')
        check_pair('f700-destroyed-door-exposes-interior', 0,-8, blocked=False)
        h.lua('local d=MELensTest.vehicle:getPartById("TrunkDoor");d:setCondition(100);d:setInventoryItem(nil);return true')
        check_pair('f700-removed-door-exposes-interior', 0,-8, blocked=False)

        enter('Base.Trailer54FlyingCloud22')
        h.lua('MELens.walkTo(getPlayer(),.02,1.7);return true')
        wait('return not MELens.pathing(getPlayer())', 'camper window setup path failed')
        check_pair('camper-solid-side-section', 5,-5)
        check_pair('camper-intact-window-transmits-sight', 5,1.7, blocked=False)
        h.lua('MELensVisionTest.spawn(5,1.7);return true')
        end = time.monotonic() + 12
        seen = None
        while time.monotonic() < end:
            s = vision.state(h)
            if s['native']['targetPlayer']: seen=s; break
            time.sleep(.15)
        h.check(seen is not None, 'normal zombie AI did not see the player through intact camper glass')
        h.record('camper-natural-window-acquisition', None, seen)
        h.capture('camper-visible-through-glass')
        h.lua('MELensVisionTest.clear();return true')

        enter('Base.87fordB700school')
        check_pair('bus-window-strip-transmits-sight', 5,-2, blocked=False)

        enter('Base.VanSeats')
        h.lua('MELens.walkTo(getPlayer(),0,-.2);return true')
        wait('return not MELens.pathing(getPlayer())', 'stock window setup path failed')
        check_pair('stock-parent-door-area-window-transmits-sight', 5,-.2, blocked=False)
        check_pair('stock-front-partition-blocks-nearby-cab-glass', 5,4)

        # A native cab-seat fixture checks classification without relying on the
        # local standing/render state being cleared by the next player update.
        h.lua('local p=getPlayer();local v=p:getVehicle();v:switchSeat(p,0);return true')
        h.lua('MELensVisionTest.spawn(5,0);return true')
        s = vision.state(h)
        h.check(not s['vision']['enclosed'] and not s['vision']['blocked'], 'normal driver seat acquired hull concealment')
        h.record('native-driver-seat-retains-vanilla-vision', None, s, fixture='native vehicle seat switch')
        exit_vehicle()

        # Finish in the camper for the final-version dashboard regression suite.
        enter('Base.Trailer54FlyingCloud22')
        h.lua('MELensVisionTest.clear();return true')
        h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
        h.REPORT['passed'] = True; h.write_report('passed')
        print('VISION_COVERAGE_NATIVE_PASSED', flush=True); return 0
    except Exception:
        error=traceback.format_exc(); h.REPORT['passed']=False
        h.write_report('failed',error); print(error,flush=True); return 1


if __name__ == '__main__':
    raise SystemExit(main())
