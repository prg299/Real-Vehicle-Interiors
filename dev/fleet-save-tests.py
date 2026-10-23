"""Save/cold-load furniture and cargo identity in the disposable native fleet profile.

Placement uses native inventory input. saveGame is the production persistence API;
this check does not claim menu Save/Continue input coverage.
"""
import importlib.util
import json
import os
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'dev' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    furniture, beds = load('final-furniture-tests'), load('bed-tests')
    interior, tap, h = furniture.load_helpers()
    reload_source = os.environ.get('RVI_FLEET_RELOAD_SOURCE')
    h.configure(run / ('reload-checks' if reload_source else 'save-checks'))
    config = json.loads((run / 'native-session.json').read_text('utf-8-sig'))
    cache = next(x.split('=', 1)[1] for x in config['command'] if x.startswith('-cachedir='))
    h.SCREENS = Path(cache) / 'Screenshots'
    try:
        if reload_source:
            expected = json.loads((ROOT / 'build/rv' / reload_source / 'save-checks/expected.json').read_text())
            h.lua('local v=assert(getPlayer():getVehicle());assert(v:getScriptName()=="Base.Van");MELensTest={vehicle=v,all={}};return true')
        else:
            beds.enter(h, 'Base.Van', 'E')
        h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
        h.lua(interior.FIXTURE)
        if not reload_source:
            item_id = h.lua('local i=getPlayer():getInventory():AddItem("Base.MELensRV_Bed");assert(i);return i:getID()')
            h.lua(furniture.FIXTURE.replace('"heater"', '"bed"'))
            h.lua('MELensInteriorTest.heaterIndex=1;return true')
            state = interior.read_state(h)
            furniture.place_heater_from_inventory(h, interior, tap, state['furniture'])
            h.lua('''local v=MELensTest.vehicle;local c=MELens.Parts.spotPart(v,1):getItemContainer()
c:AddItem("Base.Hammer");v:getPartById("TruckBed"):getItemContainer():AddItem("Base.Screwdriver");return true''')
        state = h.lua('''local v=MELensTest.vehicle;local part=MELens.Parts.spotPart(v,1)
local item=assert(part:getInventoryItem());local c=part:getItemContainer();local trunk=v:getPartById("TruckBed"):getItemContainer()
local function ids(c) local r={};for i=0,c:getItems():size()-1 do r[#r+1]=c:getItems():get(i):getID() end;return r end
return {world=getWorld():getWorld(),script=v:getScriptName(),bed=item:getID(),capacity=c:getCapacity(),
cargo=ids(c),trunkCapacity=trunk:getCapacity(),trunkCargo=ids(trunk)}''')
        h.check(state['capacity'] == 20 and state['trunkCapacity'] > 1, 'installed bed or original trunk capacity invalid')
        if reload_source:
            h.check(state == expected, 'cold load changed furniture, cargo IDs or original trunk capacity')
            h.REPORT['saveReload'] = dict(expected=expected, actual=state)
            h.capture('van-cold-loaded')
            h.lua('return MELensInteriorTest.positionAtExit()')
            interior.poll(h, lambda s: interior.idle(s), label='reloaded exit fixture')
            interior.interact_key(h, 'exit-cold-loaded-van')
            interior.poll(h, lambda s: not s['interior']['inside'], label='outside cold-loaded van')
        else:
            h.check(state['bed'] == item_id, 'placed furniture identity changed before save')
            (h.OUTPUT / 'expected.json').write_text(json.dumps(state, indent=2))
            h.lua('saveGame();return true')
            h.REPORT['saved'] = state
            h.capture('van-saved-inside')
        h.REPORT['unverified'] = ['dedicated server', 'Save/Continue menu input']
        print(h.write_report('passed'), flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        print(h.write_report('failed', error), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
