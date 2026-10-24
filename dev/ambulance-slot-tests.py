"""Native furniture placement in the two retained empty KI5 side-door bays."""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN'];furniture=load('final-furniture-tests')
    interior,tap,h=furniture.load_helpers();h.configure(run/'empty-shelf-slots')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    try:
        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();p:setTimedActionInstantCheat(false);p:setX(10813.5);p:setY(10140.5)
p:setLastX(p:getX());p:setLastY(p:getY());return true''')
        load('bed-tests').enter(h,'Base.90fordF350ambulance','N')
        h.REPORT['nativeInput']=True
        h.REPORT['fixtureState']='Spawn/repair and initial position; front shelf 7 emptied to permit pickup. Every furniture pickup and placement uses mouse/UI/timed-action dispatch.'
        initial=h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts;local pr=MELens.profileFor(v)
assert(#pr.spots==12);for _,i in ipairs({11,12}) do assert(not P.pieceAt(P.spotPart(v,i))) end
local source=P.spotPart(v,7);assert(P.pieceAt(source)=="medlocker");source:getItemContainer():getItems():clear()
return {slots=#pr.spots,sourceItem=source:getInventoryItem():getID(),empty={11,12}}''')
        h.REPORT['initial']=initial
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
        h.lua(furniture.FIXTURE.replace('"heater"','"medlocker"'))
        h.lua('''local T=MELensInteriorTest;T.heaterIndex=7;T.heater=MELens.Parts.spotPart(T.vehicle,7):getInventoryItem();return true''')
        time.sleep(.8)
        for source,destination in ((7,11),(11,12),(12,7)):
            target=interior.read_state(h)['furniture']
            point=h.lua(f'return MELensInteriorTest.point({source})')
            pickup=h.lua('return getText("ContextMenu_MELens_PickUp")')
            before=interior.choose(h,tap,point,[point['header'],pickup],f'shelf-{source}-pickup')
            after,seen=furniture.finish(h,interior,lambda s:s['furniture'].get('heaterInstalledId') is None
                                        and s['furniture']['heaterInInventory'],'MELensPickUpFurniture','shelf pickup')
            h.check(after['furniture']['heaterId']==initial['sourceItem'],'pickup changed shelf item ID')
            h.record(f'shelf-{source}-pickup',before,after,observedTimedActions=seen,uiHandlersInvokedDirectly=False)
            h.lua(f'MELensInteriorTest.heaterIndex={destination};return true')
            furniture.place_heater_from_inventory(h,interior,tap,target,capture_label=f'empty-bay-{destination}')
            h.check(h.lua(f'return MELens.Parts.spotPart(MELensTest.vehicle,{destination}):getInventoryItem():getID()')==initial['sourceItem'],
                    'placement selected the wrong bay')
            h.capture(f'shelf-in-bay-{destination}')
        h.REPORT['final']=h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
for _,i in ipairs({11,12}) do local part=P.spotPart(v,i);assert(not P.pieceAt(part));P.createSpot(v,part);assert(not P.pieceAt(part)) end
return {sourceItem=P.spotPart(v,7):getInventoryItem():getID(),emptySlotsRemainBare=true}''')
        h.check(h.REPORT['final']['sourceItem']==initial['sourceItem'],'roundtrip changed shelf identity')
        h.REPORT['scope']=__doc__;h.REPORT['unverified']=['dedicated multiplayer','cold save reload']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('slot-failure')
        except Exception:pass
        h.write_report('failed',error);return 1

if __name__=='__main__':raise SystemExit(main())
