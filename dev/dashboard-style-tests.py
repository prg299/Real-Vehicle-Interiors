"""Native dashboard styling/input checks in the parent-owned inactive desktop."""
import argparse
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


def stale_click(h):
    # Supply setup only. Invalidate the water bottle when the real ISButton has
    # received its native press; never invoke a UI/action handler from this probe.
    h.lua('''local F=MELensFeatureTest;local U=MELens.Utilities
local tank=U.waterState(F.vehicle);U.changeWater(F.vehicle,-tank.water,false)
local fc=F.items.water:getFluidContainer();fc:removeFluid(fc:getAmount());fc:addFluid(Fluid.Water,.5)
F.items.water:syncItemFields();MELensStaleWaterPressed=false
MELensStaleWaterProbe=function()
local w=MELens.Dashboard.instance;local b=w and w.actionButtons[w.onAddWater]
if b and b.pressed then
MELensStaleWaterPressed=true;local f=F.items.water:getFluidContainer();f:removeFluid(f:getAmount())
F.items.water:syncItemFields();Events.OnTick.Remove(MELensStaleWaterProbe)
end end
Events.OnTick.Add(MELensStaleWaterProbe);return true''')
    before = h.click_control('addWater')
    after = h.wait_for(lambda s: s['inventory']['water']['amount'] == 0 and s['queueCount'] == 0
                       and not h._control(s, 'addWater')['enabled'], label='water supply invalidated during native held press')
    h.check(h.lua('return MELensStaleWaterPressed'), 'probe did not observe a native ISButton press')
    h.check(after['utilities']['water'] == 0, 'stale release filled the tank')
    for key in ('x', 'y', 'z', 'passengerX', 'passengerZ'):
        if key in before['player']:
            h.check(abs(after['player'][key] - before['player'][key]) < .02, 'stale click moved the scene')
    h.record('native-held-button-revalidates-removed-water', before, after,
             fixture='bottle drained only after native ISButton.pressed', rejectedInput=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--neat', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    interior, bed, personal = load('final-interior-tests'), load('bed-tests'), load('final-personalization-tests')
    tap, h = interior.load_helpers()
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    h.configure(run / ('dashboard-recheck' if args.resume else 'dashboard-checks'))
    h.SCREENS = run / 'home/Zomboid/Screenshots'
    try:
        h.check(h.lua('return MELens.Dashboard.isNeatActive()') is args.neat, 'actual active-mod selection differs from this test')
        h.REPORT['activeMods'] = h.lua('local a=getActivatedMods();local r={};for i=0,a:size()-1 do r[#r+1]=a:get(i) end;return r')
        if not args.resume:
            bed.enter(h, 'Base.Trailer54FlyingCloud22', 'E')
            h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
        h.lua(interior.FIXTURE)
        interior.close_dashboard(h, tap)
        point = h.lua('return MELensInteriorTest.point("bed")')
        label = h.lua('return getText("ContextMenu_MELens_Dashboard")')
        before = interior.choose(h, tap, point, [label], 'dashboard-open')
        after = h.wait_for(lambda s: s.get('dashboard') and len(s['controls']) >= 8, timeout=10, label='native world-menu dashboard')
        h.record('native-context-menu-opens-selected-style', before, after)
        selected = h.lua('''local w=MELens.Dashboard.instance;local r={type=w.Type,
width=w:getWidth(),height=w:getHeight(),screenW=getCore():getScreenWidth(),screenH=getCore():getScreenHeight(),
nativeButtons=0,closeTexture=w.closeButton~=nil};for _,c in ipairs(w.controls) do
if c.nativeButton then r.nativeButtons=r.nativeButtons+1 end end;return r''')
        h.check(selected['type'] == ('MELensDashboard' if args.neat else 'MELensVanillaDashboard'), 'wrong live window class')
        h.check(selected['width'] <= selected['screenW'] and selected['height'] <= selected['screenH'], 'dashboard exceeds native screen')
        h.check((selected['nativeButtons'] == len(after['controls'])) is not args.neat, 'vanilla controls must use native ISButtons')
        h.REPORT['presentation'] = selected
        h.capture('dashboard-neat-default' if args.neat else 'dashboard-vanilla-default')
        if args.resume and not args.neat and args.quick:
            stale_click(h)
        if not args.quick:
            h.run_dashboard_cases(skip_full_capacity=False)
            personal.run_personalization_cases(h)
        else:
            before = h.snapshot()
            h._toggle('lights', 'lightsOn', not before['utilities']['lightsOn'])
        before = h.snapshot()
        after = interior.close_dashboard(h, tap)
        h.check(not after.get('dashboard'), 'standard close control failed')
        h.record('native-titlebar-close', before, after)
        h.REPORT['passed'] = True
        h.write_report('passed')
        print('DASHBOARD_STYLE_NATIVE_PASSED', flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        h.REPORT['passed'] = False
        h.write_report('failed', error)
        print(error, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
