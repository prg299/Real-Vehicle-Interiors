"""Native Dashboard start/stop and vehicle-update clock probes in the owned F700 session."""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('f700_native_features', ROOT / 'dev/final-feature-tests.py')
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    h.configure(run / 'fuel-checks')
    source = ROOT / 'build/rv' / os.environ.get('RVI_CAPTURE_SOURCE', os.environ['RVI_CAPTURE_RUN'])
    h.SCREENS = source / 'home/Zomboid/Screenshots'
    try:
        h.lua('''local p,v=getPlayer(),MELensTest.vehicle
local g=v:getPartById(MELens.Parts.GENERATOR)
g:getModData().on=false
-- A nonnegative clock is required to exercise native catch-up (negative means uninitialized).
getGameTime():setNightsSurvived(4)
g:getModData().fuel=10;g:setCondition(100)
g:setLastUpdated(getGameTime():getWorldAgeHours()-72)
MELens.Dashboard.open(p,v);local w=MELens.Dashboard.instance;w:setX(25);w:setY(35)
return true''')
        h.click_control('generator')
        on = h.wait_for(lambda s: s['queueCount'] == 0 and s['utilities']['generatorRunning'], label='native generator start')
        h.check(9.98 < on['utilities']['generatorFuel'] <= 10, 'native start charged 72 hours parked off')
        h.capture('f700-generator-start')
        before = h.lua('''local g=MELensTest.vehicle:getPartById(MELens.Parts.GENERATOR)
local fuel=g:getModData().fuel
g:setLastUpdated(getGameTime():getWorldAgeHours()-1/6)
return fuel''')
        consumed = h.wait_for(lambda s: s['utilities']['generatorFuel'] < before - .03, timeout=12,
                              label='native ten game-minute callback')
        delta = before - consumed['utilities']['generatorFuel']
        h.check(.03 < delta < .045, f'fridge-only native fuel consumption: {delta}')
        h.record('native-ten-game-minute-fridge-consumption', on, consumed,
                 fuelUsedLitres=delta, clockFixture='native lastUpdated advanced by ten game minutes; unchanged appliance load')
        h.click_control('generator')
        off = h.wait_for(lambda s: s['queueCount'] == 0 and not s['utilities']['generatorRunning'], label='native generator stop')
        h.lua('''local g=MELensTest.vehicle:getPartById(MELens.Parts.GENERATOR)
g:setLastUpdated(getGameTime():getWorldAgeHours()-48);return true''')
        h.click_control('generator')
        restarted = h.wait_for(lambda s: s['queueCount'] == 0 and s['utilities']['generatorRunning'], label='native generator restart')
        h.check(abs(off['utilities']['generatorFuel']-restarted['utilities']['generatorFuel']) < .01,
                'native restart charged 48 hours switched off')
        h.record('native-start-stop-restart-preserves-idle-fuel', off, restarted, parkedHours=48)
        h.capture('f700-generator-restarted')
        h.REPORT['passed'] = True
        status = 0
    except Exception:
        h.REPORT.update(passed=False, error=traceback.format_exc())
        print(h.REPORT['error'], flush=True)
        status = 1
    (h.OUTPUT / 'report.json').write_text(json.dumps(h.REPORT, indent=2), encoding='utf-8')
    print('F700_FUEL_NATIVE_PASSED' if status == 0 else 'F700_FUEL_NATIVE_FAILED', flush=True)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
