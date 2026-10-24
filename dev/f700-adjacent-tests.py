"""Reported F700 empty-cargo bed/kitchen case; native inventory mouse/UI actions."""
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
    furniture,beds=load('final-furniture-tests'),load('bed-tests')
    interior,tap,h=furniture.load_helpers();h.configure(run/'f700-adjacent')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    try:
        if h.lua('return getPlayer():getVehicle()~=nil'):
            h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
            h.lua('return MELensInteriorTest.positionAtExit()')
            interior.poll(h,lambda s:interior.idle(s),label='prior exit position')
            interior.interact_key(h,'prior exit');interior.poll(h,lambda s:not s['interior']['inside'],label='outside')
        h.lua('MELensMedia.cameraOff();local p=getPlayer();p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true')
        # The outside point is the approach fixture. A diagonal cardinal-key
        # approximation can step sideways out of this narrow rear-door area.
        beds.enter(h,'Base.87fordF700box','N',walk_approach=False)
        h.lua('''local p=getPlayer();local v=p:getVehicle();local P=MELens.Parts
-- Empty-cargo fixture matches the report's already cleared truck. Native box
-- pickup is not claimed by this test; the player's real save is never opened.
for i in ipairs(MELens.profileFor(v).spots) do local part=P.spotPart(v,i)
local c=part:getItemContainer();if c then c:getItems():clear() end
part:setInventoryItem(nil);P.applyPiece(v,part) end
local inv=p:getInventory();for i=inv:getItems():size()-1,0,-1 do local item=inv:getItems():get(i)
if P.pieceOfItem(item) then inv:Remove(item) end end
p:setUnlimitedCarry(true);p:setTimedActionInstantCheat(false);return true''')
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
        h.lua('getCore():setAutoZoom(0,false);return true')
        for _ in range(8):
            zoom=h.lua('return getCore():getZoom(0)')
            if abs(zoom-1)<.02:break
            h.lua(f'getCore():doZoomScroll(0,{1 if zoom<1 else -1});return true');time.sleep(.5)
        h.REPORT['placements']=[]
        # Same wall, neighbouring usable footprints: bed [-1.91,-.41],
        # kitchenette [-.16,.84]. The .25m gap is genuine, not disabled collision.
        for piece,index in [('bed',82),('kitchen',64)]:
            item_id=h.lua(f'local i=getPlayer():getInventory():AddItem("Base.MELensRV_{piece.capitalize()}");assert(i);return i:getID()')
            h.lua('MELensInteriorTest.heater=nil;MELensInteriorTest.heaterIndex=nil;return true')
            h.lua(furniture.FIXTURE.replace('"heater"',json.dumps(piece)))
            h.lua(f'MELensInteriorTest.heaterIndex={index};return true')
            state=interior.read_state(h)
            furniture.place_heater_from_inventory(h,interior,tap,state['furniture'])
            receipt=h.lua(f'''local part=MELens.Parts.spotPart(MELensTest.vehicle,{index})
assert(part:getInventoryItem():getID()=={int(item_id)})
return {{index={index},piece="{piece}",id=part:getInventoryItem():getID(),capacity=part:getItemContainer():getCapacity()}}''')
            h.REPORT['placements'].append(receipt)
        point=h.lua('return MELensInteriorTest.point(82)');rest=h.lua('return getText("ContextMenu_Rest")')
        before=interior.choose(h,tap,point,[point['header'],rest],'f700-adjacent-bed-rest')
        interior.poll(h,lambda s:h.lua('return getPlayer():getVariableString("MELensBed")=="Awake"'),label='F700 resting')
        h.capture('f700-adjacent-resting')
        interior.interact_key(h,'F700 get up')
        after=interior.poll(h,lambda s:s['interior']['standing'] and interior.idle(s),label='F700 stood up')
        h.record('f700-adjacent-bed-rest-and-get-up',before,after,uiHandlersInvokedDirectly=False)
        h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local o=v:getScript():getModel():getOffset()
local q=Vector3f.new();v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()-1.2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''');time.sleep(.5)
        h.capture('f700-adjacent-bed-and-kitchen')
        h.lua('MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return MELensInteriorTest.positionAtExit()')
        interior.poll(h,lambda s:interior.idle(s),label='F700 clear exit route')
        interior.interact_key(h,'F700 native exit')
        interior.poll(h,lambda s:not s['interior']['inside'],label='F700 outside')
        h.REPORT['unverified']=['dedicated server','native cargo-box removal; empty truck is a fixture','human acceptance']
        print(h.write_report('passed'),flush=True);return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
