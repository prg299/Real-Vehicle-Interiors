"""F700 native inventory-placement checks in the parent's guarded disposable game."""
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
    furniture, beds = load('final-furniture-tests'), load('bed-tests')
    interior, tap, h = furniture.load_helpers()
    h.configure(run / 'checks')
    h.SCREENS = run / 'home/Zomboid/Screenshots'
    try:
        if not h.lua('return getPlayer():getVehicle()~=nil'):
            beds.enter(h, 'Base.87fordF700box', 'E')
        h.lua('''local p,v=getPlayer(),MELensTest.vehicle
local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do
 local part=P.spotPart(v,i);local c=part:getItemContainer()
 if c then c:getItems():clear() end
 part:setInventoryItem(nil);P.applyPiece(v,part)
end
local inventory=p:getInventory()
for i=inventory:getItems():size()-1,0,-1 do
 local item=inventory:getItems():get(i)
 if P.pieceOfItem(item) then inventory:Remove(item) end
end
p:setUnlimitedCarry(true);p:setTimedActionInstantCheat(false)
return {passengers=v:getMaxPassengers(),vehicle=v:getScriptName()}''')
        h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
        h.lua(interior.FIXTURE)
        placements = []
        for piece, target in [('bed', 82), ('dinette', 83), ('fridge', 64), ('box', 21)]:
            full = 'Base.MELensRV_' + piece.capitalize()
            item_id = h.lua(f'local i=getPlayer():getInventory():AddItem("{full}");assert(i);return i:getID()')
            # Reuse the established inventory driver, with its heater fixture alias
            # bound to the furniture under test. All placement inputs remain native.
            h.lua('MELensInteriorTest.heater=nil;MELensInteriorTest.heaterIndex=nil;return true')
            h.lua(furniture.FIXTURE.replace('"heater"', json.dumps(piece)))
            h.lua(f'MELensInteriorTest.heaterIndex={target};return true')
            state = interior.read_state(h)
            furniture.place_heater_from_inventory(h, interior, tap, state['furniture'])
            receipt = h.lua(f'''local v=MELensTest.vehicle;local p=MELens.Parts.spotPart(v,{target})
local i=p:getInventoryItem();assert(i and i:getID()=={int(item_id)})
return {{piece="{piece}",index={target},id=i:getID(),capacity=p:getItemContainer():getCapacity(),itemCapacity=i:getMaxCapacity()}}''')
            placements.append(receipt)
            h.capture('f700-' + piece + '-placed')
        h.REPORT['placements'] = placements
        h.check([x['capacity'] for x in placements] == [20, 15, 30, 20], 'native installed storage capacities')
        probe = h.lua('''local v=MELensTest.vehicle;local P,U=MELens.Parts,MELens.Utilities
local r={storage={}}
for _,index in ipairs({21,64}) do
 local part=P.spotPart(v,index);local c=part:getItemContainer();local original=part:getInventoryItem()
 local cargo=c:AddItem("Base.Hammer");local id=cargo:getID()
 c:setCapacity(0);P.showPiece(part)
 part:doInventoryItemStats(original,0)
 assert(c:getCapacity()==(index==21 and 20 or 30));assert(c:getItemById(id)==cargo)
 r.storage[#r.storage+1]={index=index,capacity=c:getCapacity(),preservedItemId=id,
   acceptsHammer=c:hasRoomFor(getPlayer(),cargo)}
end
local gen=v:getPartById(P.GENERATOR);local d=gen:getModData()
d.on=false;d.fuel=10;gen:setCondition(100)
gen:setLastUpdated(getGameTime():getWorldAgeHours()-72)
r.beforeFuel=d.fuel;r.rate=U.generatorFuelRate(v)
return r''')
        h.REPORT['nativeComponents'] = probe
        h.check(all(x['acceptsHammer'] for x in h._sequence(probe['storage'])), 'native storage rejects normal cargo')
        h.check(abs(probe['rate'] - .2) < 1e-6, 'native fridge-only fuel rate')
        h.capture('f700-complete-interior')
        h.REPORT['passed'] = True
        h.REPORT['unverified'] = ['multiplayer', 'save/reload', 'natural long-term fuel use', 'human acceptance']
        status = 0
    except Exception:
        h.REPORT.update(passed=False, error=traceback.format_exc())
        print(h.REPORT['error'], flush=True)
        status = 1
    (h.OUTPUT / 'report.json').write_text(json.dumps(h.REPORT, indent=2), encoding='utf-8')
    print('F700_NATIVE_PASSED' if status == 0 else 'F700_NATIVE_FAILED', flush=True)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
