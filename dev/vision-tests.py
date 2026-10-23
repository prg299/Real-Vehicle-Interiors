"""Native zombie sight/hearing checks in a guarded, inactive-desktop test game."""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'dev' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def state(h, index=1):
    value = h.lua(f'return MELensVisionTest.snapshot({index})')
    value['native'] = json.loads(value['native']); value['vision'] = json.loads(value['vision'])
    return value


def pair(h, x, z, old=False, blocked=True):
    result = h.lua(f'return MELensVisionTest.pair({x},{z},{str(old).lower()})')
    for key in ('control', 'treatment', 'unchanged', 'memory'):
        result[key] = json.loads(result[key])
    h.check(result['ageBefore'] == result['ageAfter'], 'paired perception comparison advanced simulation')
    h.check(result['control']['targetPlayer'], 'vanilla spotting control could not see the passenger')
    h.check(result['treatment']['targetPlayer'] is not blocked, 'hull spotting did not match sight opening')
    h.check(result['unchanged']['targetPlayer'] == result['treatment']['targetPlayer'], 'unchanged sight input changed target')
    h.check(result['memory']['targetPlayer'], 'occlusion erased prior native target memory')
    return result


def main():
    bed, interior = load('bed-tests'), load('final-interior-tests')
    tap, h = interior.load_helpers()
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    h.configure(run / 'vision-checks'); h.SCREENS = run / 'home/Zomboid/Screenshots'
    try:
        if not h.lua('return getPlayer():getVehicle()~=nil'):
            bed.enter(h, 'Base.87fordF700box', 'N', walk_approach=False)
        h.REPORT['scope'] = 'native single-player zombie sight/hearing, paired deterministic native spotting at the same world age; actual E/Shout keyboard input'
        h.REPORT['nativeInput'] = True
        h.REPORT['inputs'].append(dict(action='F700 native E entry', api='MEMCNativeLab.holdKey'))
        h.lua((ROOT / 'dev/lua/vision-fixture.lua').read_text())

        for old in (False, True):
            result = pair(h, 5, -2, old)
            h.record('f700-solid-wall-' + ('old' if old else 'new') + '-same-clock-control', None, result,
                     scope='deterministic native spotting contract; forced native call, no simulation advance')
        h.lua('MELensVisionTest.clear();MELensVisionTest.spawn(5,-2);return true')
        samples = []
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            s = state(h); samples.append(s)
            h.check(s['vision']['registered'] and s['vision']['enclosed'] and s['vision']['blocked'], 'quiet wall probe lost its hull')
            h.check(not s['native']['targetPlayer'], 'unseen quiet passenger acquired through solid hull')
            time.sleep(.2)
        h.record('f700-natural-quiet-idle-no-acquisition', samples[0], samples[-1], samples=samples)
        h.capture('f700-quiet-zombie-outside')
        # Actual input first: verify normal player noise still reaches native AI.
        shout = h.lua('return getCore():getKey("Shout")')
        h.lua(f'MEMCNativeLab.holdKey({int(shout)},250);return true')
        h.REPORT['inputs'].append(dict(action='interior-shout', key=shout, api='MEMCNativeLab.holdKey'))
        deadline = time.monotonic() + 10
        heard = None
        while time.monotonic() < deadline:
            s = state(h)
            if s['native']['heardPlayer'] or s['native']['goalSound']:
                heard = s; break
            time.sleep(.2)
        h.check(heard is not None, 'native interior Shout did not produce a heard/investigated sound')
        h.record('native-interior-shout-attracts-through-closed-wall', samples[-1], heard)
        h.capture('f700-heard-interior-player')
        h.lua('MELensVisionTest.clear();local d=MELensTest.vehicle:getPartById("TrunkDoor");assert(d:getDoor());d:getDoor():setOpen(true);return true')
        result = pair(h, 0, -8, blocked=False)
        h.record('f700-open-rear-door-allows-native-sight', None, result)
        h.lua('MELensVisionTest.clear();MELensTest.vehicle:getPartById("TrunkDoor"):getDoor():setOpen(false);return true')
        result = pair(h, 0, -8)
        h.record('f700-closed-rear-door-blocks-native-sight', None, result)
        h.REPORT['passed'] = True
        h.write_report('passed'); print('VISION_NATIVE_PASSED', flush=True); return 0
    except Exception:
        error = traceback.format_exc(); h.REPORT['passed'] = False
        h.write_report('failed', error); print(error, flush=True); return 1


if __name__ == '__main__':
    raise SystemExit(main())
