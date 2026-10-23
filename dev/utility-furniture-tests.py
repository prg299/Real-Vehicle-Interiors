"""Production mouse pickup and inventory placement of the new service fittings."""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h=load('final-feature-tests');h.configure(run/'utility-furniture')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    furniture,beds=load('final-furniture-tests'),load('bed-tests')
    interior,tap,_=furniture.load_helpers()
    try:
        for piece,name,index in [('metalcase','Base.87fordF700swat',3),('stretcher','Base.90fordF350ambulance',1)]:
            h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setTimedActionInstantCheat(false)
p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5)
local inv=p:getInventory();local items=inv:getItems();for i=items:size()-1,0,-1 do
local item=items:get(i);if item:getType()=="CarKey" or MELens.Parts.pieceOfItem(item) then inv:Remove(item) end end
return true''')
            beds.enter(h,name,'N')
            h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
            h.lua(furniture.FIXTURE.replace('"heater"',json.dumps(piece)))
            h.lua(f'''local T=MELensInteriorTest;local P=MELens.Parts
T.heaterIndex={index};T.heater=P.spotPart(T.vehicle,{index}):getInventoryItem()
assert(P.pieceOfItem(T.heater)=="{piece}");return true''')
            target=interior.read_state(h)['furniture']
            point=h.lua(f'return MELensInteriorTest.point({index})')
            label=h.lua('return getText("ContextMenu_MELens_PickUp")')
            before=interior.choose(h,tap,point,[point['header'],label],piece+'-pickup')
            after,seen=furniture.finish(h,interior,lambda s:s['furniture'].get('heaterInstalledId') is None
                                       and s['furniture']['heaterInInventory'],'MELensPickUpFurniture',piece+' pickup')
            h.check(after['furniture']['heaterId']==target['heaterId'],'pickup changed '+piece+' identity')
            h.record(piece+'-native-pickup',before,after,observedTimedActions=seen,uiHandlersInvokedDirectly=False)
            h.capture(piece+'-inventory-icon')
            furniture.place_heater_from_inventory(h,interior,tap,target)
            h.capture(piece+'-reinstalled')
            h.lua('return MELensInteriorTest.positionAtExit()')
            interior.poll(h,lambda s:interior.idle(s),label=piece+' exit approach')
            interior.interact_key(h,piece+'-exit')
            interior.poll(h,lambda s:not s['interior']['inside'],label=piece+' outside')
        h.REPORT['scope']='Native mouse context pickup, inventory icon/menu and placement preview; actual production timed actions'
        h.REPORT['unverified']=['dedicated server','save/reload']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
