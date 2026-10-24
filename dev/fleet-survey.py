"""Read-only renderer diagnostics with native entry/exit in the owned fleet test session."""
import importlib.util
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'dev' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    interior, beds = load('final-interior-tests'), load('bed-tests')
    tap, h = interior.load_helpers()
    h.configure(run / 'fleet-survey')
    config = json.loads((run / 'native-session.json').read_text('utf-8-sig'))
    cache = next(x.split('=', 1)[1] for x in config['command'] if x.startswith('-cachedir='))
    h.SCREENS = Path(cache) / 'Screenshots'
    for label, name in [('e150','Base.86fordE150'),('chevy','Base.85chevyStepVan'),
                        ('swat','Base.87fordF700swat'),('ambulance','Base.90fordF350ambulance'),
                        ('original-f700','Base.87fordF700box'),('original-camper','Base.Trailer54FlyingCloud22')]:
        h.lua('''local p=getPlayer();assert(not p:getVehicle());p:setX(10813.5);p:setY(10140.5)
p:setLastX(10813.5);p:setLastY(10140.5);p:setTimedActionInstantCheat(false);return true''')
        beds.enter(h, name, 'E')
        h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
        h.lua(interior.FIXTURE)
        h.lua('MELensRV.setSurvey(true);return true')
        time.sleep(.5)
        h.REPORT.setdefault('renderSurveys', {})[label] = h.lua('return MELensRV.surveyInfo()')
        h.lua('MELensRV.setSurvey(false);return true')
        h.capture(label + '-interior')
        before = interior.read_state(h)
        h.lua('return MELensInteriorTest.positionAtExit()')
        interior.poll(h, lambda s: interior.idle(s), label=label + ' exit fixture')
        interior.interact_key(h, label + '-exit')
        after = interior.poll(h, lambda s: not s['interior']['inside'], label=label + ' outside')
        h.capture(label + '-outside')
        h.record(label + '-native-entry-exit', before, after)
        print('FLEET_SURVEY_PASS ' + label, flush=True)
    print(h.write_report('passed'), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
