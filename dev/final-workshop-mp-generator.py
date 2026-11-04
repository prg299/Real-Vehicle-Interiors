"""Dedicated authority and observer receipt for native interior generator Grab.

Run after the existing two-client movement driver. Only the server creates and
positions the fixture. Clients obtain Floor contents through normal loot UI.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();d=load('final-mp-interior-tests');lab=d.InteriorLab(args.session,args.output);h=lab.h
    furniture=load('final-furniture-tests');interior,tap,_=furniture.load_helpers()
    inventory=load('final-mp-loot-ui-tests').InventoryLab(lab,d)
    def server(code):return json.loads(lab.server(d.JSON_ENCODER+'local r=(function() '+code+' end)();return enc(r)'))
    try:
        lab.vid=int(h.lua('return assert(getPlayer():getVehicle()):getId()'))
        h.check(lab.b.lua(f'return getPlayer():getVehicle()==getVehicleById({lab.vid}) and MELens.isStanding(getPlayer())'),'observer not in same interior')
        h.lua('''local p=getPlayer();local v=p:getVehicle();MELensTest={vehicle=v}
MELensFeatureTest={player=p,vehicle=v,snapshot=function()
 local queue=ISTimedActionQueue.getTimedActionQueue(p).queue;local out={queue={},queueCount=#queue,controls={}}
 for _,action in ipairs(queue) do out.queue[#out.queue+1]={type=tostring(action.Type)} end
 return out
end};return true''')
        h.lua(interior.FIXTURE);h.lua(furniture.FIXTURE)
        point=h.lua('local x,z=MELens.Parts.characterAt(getPlayer():getVehicle(),getPlayer());local q=MELens.profileFor(getPlayer():getVehicle());local a,b=MELens.nearestWalkableAt(q,x+.55,z+.4);return {x=a,z=b}')
        item_id=server(f'''local v=getVehicleById({lab.vid});local L=MELens.Loose;local floor=L.floorContainer(v)
local item=assert(floor:AddItem("Base.Generator"));item:setName("MP native pickup test generator")
sendAddItemToContainer(floor,item);L.set(v,item,{point['x']},MELens.profileFor(v).floorY,{point['z']},0,0)
v:transmitPartModData(L.floorPart(v));return item:getID()''')
        inventory.part,inventory.item_id='MELensFloor',item_id
        for side in ('A','B'):
            inventory.open(side);inventory.select_container(side,'MELensFloor')
            inventory.wait(side,lambda s:s['windows']['loot'].get('row') is not None,'server generator replicated through Floor UI')
            state=inventory.read(side);lab.input(side,key=int(state['inventoryKey']))
            inventory.wait(side,lambda s:not s['windows']['inventory']['visible'],'close inventory before world context')
        h.lua(f'MELensInteriorTest.hammer=assert(MELens.Loose.floorContainer(getPlayer():getVehicle()):getItemById({item_id}));return true')
        before=server(f'''local v=getVehicleById({lab.vid});local item=MELens.Loose.floorContainer(v):getItemById({item_id})
return {{id=item:getID(),floor=true,weight=item:getActualWeight()}}''')
        point=lab.wait(lambda:h.lua('return MELensInteriorTest.loosePoint()'),lambda p:p is not None,'generator world pick geometry')
        interior.choose(h,tap,point,[point['header'],h.lua('return getText("ContextMenu_Grab")')],'mp-generator-world-grab')
        read=f'''local v=getVehicleById({lab.vid});local out={{floor=MELens.Loose.floorContainer(v):getItemById({item_id})~=nil,
position=MELens.Loose.entry(v,{item_id})~=nil,players={{}}}}
local function player(p) local a=p:getPrimaryHandItem();local b=p:getSecondaryHandItem()
out.players[p:getUsername()]={{inInventory=p:getInventory():getItemById({item_id})~=nil,primary=a and a:getID(),secondary=b and b:getID()}} end
local list=getOnlinePlayers();for i=0,list:size()-1 do player(list:get(i)) end
if not isServer() then player(getPlayer()) end
return out'''
        def receipt():return {'server':server(read),'A':h.lua(read),'B':lab.b.lua(read)}
        def accepted(all_states):
            for side,state in all_states.items():
                actor=state['players'].get('MELensAdmin',{})
                if state['floor'] or state['position'] or actor.get('primary')!=item_id or actor.get('secondary')!=item_id:return False
                # Remote player inventory contents are not normally synchronized
                # to other clients; authority and the owning client must contain it.
                if side!='B' and not actor.get('inInventory'):return False
            return True
        after=lab.wait(receipt,accepted,'server/actor/observer generator equipment and Floor removal',timeout=45)
        h.record('mp-generator-native-grab-authority-and-observer',before,after,itemId=item_id,uiHandlersInvokedDirectly=False)
        time.sleep(1);lab.capture('A','generator-actor');lab.capture('B','generator-observer')
        h.lua(f'MELensInteriorTest.heater=getPlayer():getInventory():getItemById({item_id});return true')
        furniture.open_inventory_item_menu(h,interior,tap)
        label=h.lua('return getText("ContextMenu_Drop")')
        menu=interior.poll(h,lambda s:tap.menu_option(s,label) is not None,timeout=8,label='native MP generator Drop')
        option=tap.menu_option(menu,label);tap.native_click(h,option['x'],option['y'],'mp-generator-drop')
        def dropped(states):
            for state in states.values():
                actor=state['players'].get('MELensAdmin',{})
                if not state['floor'] or not state['position'] or actor.get('primary')==item_id or actor.get('secondary')==item_id:return False
            return True
        final=lab.wait(receipt,dropped,'same generator returns to interior Floor on all peers',timeout=45)
        h.record('mp-generator-native-drop-same-id',after,final,itemId=item_id,uiHandlersInvokedDirectly=False)
        h.REPORT['unverified']=['Steam transport','cold restart with a generator held']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1
    finally:
        for api in (h,lab.b):
            try:api.lua('MEMCNativeLab.releaseKeys();return true')
            except Exception:pass

if __name__=='__main__':raise SystemExit(main())
