"""Fleet entry/walking/furniture checks in the parent's guarded inactive desktop.

Spawns and inventory items are disposable fixtures. Entry, walking, placement,
furniture menus and exit use the native keyboard/mouse dispatch paths.
"""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family', default=os.environ.get('RVI_FLEET_FAMILY'))
    parser.add_argument('--heading', default='E', choices=['N', 'E', 'S', 'W'])
    args = parser.parse_args()
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    furniture, beds = load('final-furniture-tests'), load('bed-tests')
    interior, tap, h = furniture.load_helpers()
    h.configure(run / ('fleet-checks' if not args.family else 'fleet-checks-' + args.family.lower() + '-' + args.heading.lower()))
    config = json.loads((run / 'native-session.json').read_text('utf-8-sig'))
    cache = next(x.split('=', 1)[1] for x in config['command'] if x.startswith('-cachedir='))
    h.SCREENS = Path(cache) / 'Screenshots'
    families = json.loads((ROOT / 'tools-src/vehicles/coverage.json').read_text())['families']
    selected = args.family
    if selected:
        families = [f for f in families if f['family'] == selected]

    def key(code, label, ms=350):
        h.lua(f'MEMCNativeLab.holdKey({int(code)},{ms});return true')
        h._input_release = time.monotonic() + ms / 1000 + .5
        h.REPORT['inputs'].append(dict(action=label, key=code, durationMs=ms, api='MEMCNativeLab.holdKey'))
        h.REPORT['nativeInput'] = True

    try:
        if h.lua('return getPlayer():getVehicle()~=nil'):
            h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
            h.lua(interior.FIXTURE)
            h.lua('return MELensInteriorTest.positionAtExit()')
            interior.poll(h, lambda s: interior.idle(s), label='previous run exit fixture')
            interior.interact_key(h, 'previous-run-exit')
            interior.poll(h, lambda s: not s['interior']['inside'], label='previous run outside')
        native = []
        for f in families:
            for name in f['vehicles']:
                native.append(h.lua('''local name=%s
local s=ScriptManager.instance:getVehicle(name);assert(s,"missing vehicle "..name)
local pr=MELens.Profiles[name];assert(pr,"missing profile "..name)
local door=s:getPartById(pr.standing.door);assert(door,"missing entry part "..name)
assert(s:getAreaById(pr.standing.area),"missing entry area "..name)
assert(s:getPassengerCount()<=16,"too many passengers "..name)
local ids={};for i=0,s:getPassengerCount()-1 do local id=s:getPassenger(i):getId();assert(not ids[id],"duplicate seat "..name);ids[id]=true end
assert(ids[pr.seatId],"missing cabin "..name)
for _,model in ipairs(pr.shell.models) do assert(ScriptManager.instance:getModelScript(model),"missing shell model "..model) end
assert(math.abs(s:getModel():getScale()-(pr.vehicleScale or .9))<.001,"incorrect scale "..name)
return {name=name,passengers=s:getPassengerCount(),scale=s:getModel():getScale(),door=pr.standing.door}''' % json.dumps(name)))
        h.REPORT['nativeScriptContracts'] = native
        print(f'FLEET_SCRIPT_CONTRACTS {len(native)}', flush=True)
        for f in families:
            label, name = f['family'].lower(), f['representative']
            print('FLEET_START ' + label, flush=True)
            h.lua('''local p=getPlayer();assert(not p:getVehicle());p:setX(10813.5);p:setY(10140.5)
p:setLastX(10813.5);p:setLastY(10140.5);p:setTimedActionInstantCheat(false);return true''')
            beds.enter(h, name, args.heading)
            h.check(h.lua('local v=MELensTest.vehicle;return v:getPartById(MELens.profileFor(v).standing.door):getDoor()~=nil'), label + ' native entry part has no door')
            h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
            h.lua(interior.FIXTURE)
            before = interior.read_state(h)
            h.capture(label + '-empty-interior')
            # Choose a normal movement binding directed into the rear compartment.
            code = h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local q=Vector3f.new()
v:getWorldPos(0,0,1,q);local dx,dy=q:x()-v:getX(),q:y()-v:getY();local sx,sy=dx-dy,dx+dy
return getCore():getKey(math.abs(sx)>math.abs(sy) and (sx>0 and "Right" or "Left") or (sy>0 and "Backward" or "Forward"))''')
            key(code, label + '-walk', ms=500)
            time.sleep(1.1)
            after = interior.read_state(h)
            h.check(after['interior']['standing'], label + ' stopped standing')
            a, b = before['interior']['debug'], after['interior']['debug']
            h.check((a['x']-b['x'])**2+(a['z']-b['z'])**2 > .015, label + ' walking did not move')
            h.record(label + '-entry-and-walking', before, after)
            # A carried item is a fixture; choose Place through its actual inventory row.
            piece = 'bed' if f['family'] in ('VanillaVan', 'E150Long') else 'fridge'
            target = 1 if piece == 'bed' else len(h._sequence(h.lua('return MELens.profileFor(MELensTest.vehicle).spots')))
            item_id = h.lua(f'local i=getPlayer():getInventory():AddItem("Base.MELensRV_{piece.capitalize()}");assert(i);return i:getID()')
            h.lua('MELensInteriorTest.heater=nil;MELensInteriorTest.heaterIndex=nil;return true')
            h.lua(furniture.FIXTURE.replace('"heater"', json.dumps(piece)))
            h.lua(f'MELensInteriorTest.heaterIndex={target};return true')
            state = interior.read_state(h)
            furniture.place_heater_from_inventory(h, interior, tap, state['furniture'])
            receipt = h.lua(f'''local v=MELensTest.vehicle;local part=MELens.Parts.spotPart(v,{target})
local i=part:getInventoryItem();assert(i and i:getID()=={int(item_id)})
local c=part:getItemContainer();assert(c and c:getCapacity()==i:getMaxCapacity())
return {{family="{label}",piece="{piece}",index={target},id=i:getID(),capacity=c:getCapacity(),passengers=v:getMaxPassengers()}}''')
            h.REPORT.setdefault('placements', []).append(receipt)
            h.capture(label + '-furnished-interior')
            if piece == 'bed':
                point = h.lua(f'return MELensInteriorTest.point({target})')
                rest = h.lua('return getText("ContextMenu_Rest")')
                before = interior.choose(h, tap, point, [point['header'], rest], label + '-rest')
                interior.poll(h, lambda s: h.lua('return getPlayer():getVariableString("MELensBed")=="Awake"'), label=label + ' resting on bed')
                h.capture(label + '-resting-on-bed')
                interior.interact_key(h, label + '-get-up')
                after = interior.poll(h, lambda s: s['interior']['standing'] and interior.idle(s), label=label + ' standing after rest')
                h.record(label + '-rest-and-get-up', before, after)
            h.lua('return MELensInteriorTest.positionAtExit()')
            interior.poll(h, lambda s: interior.idle(s), label=label + ' exit fixture')
            interior.interact_key(h, label + '-exit')
            interior.poll(h, lambda s: not s['interior']['inside'], label=label + ' outside')
            h.capture(label + '-outside-after-exit')
            print('FLEET_PASS ' + label, flush=True)
        h.REPORT['unverified'] = ['dedicated server', 'save/reload', 'human acceptance']
        print(h.write_report('passed'), flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        try:
            h.capture('failure')
        except Exception:
            pass
        print(h.write_report('failed', error), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
