"""Real mouse generator Grab/Drop in a parent-owned isolated native game.

Seeded items, ordinary held equipment and emptied fitting slots are setup
fixtures. Tested pickups and drops use production context menus and queues.
"""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    furniture = load('final-furniture-tests')
    interior, tap, h = furniture.load_helpers()
    h.configure(run/'generator-input')
    h.SCREENS = run/'home/Zomboid/Screenshots'
    def wait(code, label, timeout=30):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            result = h.lua(code)
            if result and time.monotonic() >= h._input_release:
                return result
            time.sleep(.1)
        raise AssertionError(label)
    def state():
        return h.lua('''local p=getPlayer();local T=MELensInteriorTest;local id=T.hammer:getID()
local floor=MELens.Loose.floorContainer(T.vehicle);local a=p:getPrimaryHandItem();local b=p:getSecondaryHandItem()
return {id=id,inFloor=floor:getItemById(id)~=nil,inInventory=p:getInventory():getItemById(id)~=nil,
primary=a and a:getID(),secondary=b and b:getID(),position=MELens.Loose.entry(T.vehicle,id),
queue=#ISTimedActionQueue.getTimedActionQueue(p).queue,weight=T.hammer:getActualWeight(),
normalCapacity=p:getInventory():hasRoomFor(p,T.hammer)}''')
    def seed():
        return h.lua('''local T=MELensInteriorTest;local v=T.vehicle;local L=MELens.Loose
local floor=L.floorContainer(v);local items=floor:getItems()
for i=items:size()-1,0,-1 do local item=items:get(i)
 if item:getName()=="Native pickup test generator" and not L.entry(v,item:getID()) then floor:Remove(item) end
end
local item=assert(floor:AddItem("Base.Generator"));item:setName("Native pickup test generator")
-- Position is setup, not placement acceptance. A carried generator's model
-- need not satisfy the small-item placement preview's surface-fit chooser.
local point=T.looseFixturePoint(item) or {x=0.3,z=-0.9}
L.set(v,item,point.x,T.profile.floorY,point.z,0,0);T.hammer=item;return item:getID()''')
    def grab(label):
        point = wait('return MELensInteriorTest.loosePoint()', 'generator not clickable')
        interior.choose(h,tap,point,[point['header'],h.lua('return getText("ContextMenu_Grab")')],label)
    def drop(label):
        h.lua('MELensInteriorTest.heater=MELensInteriorTest.hammer;return true')
        furniture.open_inventory_item_menu(h,interior,tap)
        title = h.lua('return getText("ContextMenu_Drop")')
        menu = interior.poll(h,lambda s:tap.menu_option(s,title) is not None,timeout=8,label='native generator Drop')
        option = tap.menu_option(menu,title)
        tap.native_click(h,option['x'],option['y'],label)
        wait('local T=MELensInteriorTest;local p=getPlayer();return MELens.Loose.floorContainer(T.vehicle):getItemById(T.hammer:getID())~=nil and p:getPrimaryHandItem()==nil and p:getSecondaryHandItem()==nil and #ISTimedActionQueue.getTimedActionQueue(p).queue==0', 'native generator drop did not complete')
        h.lua('local w=getPlayerInventory(0);if w then w:setVisible(false) end;return true')
    try:
        h.lua('getPlayer():setTimedActionInstantCheat(false);ISUIHandler.setVisibleAllUI(true);return true')
        if not h.lua('return MELens.isStanding(getPlayer())'):
            load('bed-tests').enter(h,'Base.StepVan','E')
        h.lua('''local v=getPlayer():getVehicle();local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do local part=P.spotPart(v,i)
if part:getItemContainer() then part:getItemContainer():clear() end
part:setInventoryItem(nil);P.applyPiece(v,part) end;return true''')
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text())
        h.lua(interior.FIXTURE)
        h.lua(furniture.FIXTURE)
        first = seed()
        before = state()
        h.check(not before['normalCapacity'], 'fixture fails to reproduce ordinary generator capacity rejection')
        grab('generator-first-grab')
        wait(f'local p=getPlayer();local a=p:getPrimaryHandItem();local b=p:getSecondaryHandItem();return a and b and a:getID()=={first} and b:getID()=={first}', 'generator not carried in both hands')
        after = state()
        h.check(after['inInventory'] and not after['inFloor'] and not after.get('position'), 'generator transfer lost identity or loose cleanup')
        h.record('generator-native-grab-same-id',before,after,uiHandlersInvokedDirectly=False)
        wait('return #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0','generator pickup action still active')
        time.sleep(1)
        h.capture('generator-carried')
        second = seed()
        before = state()
        grab('generator-second-rejected')
        interior.poll(h,interior.idle,label='rejected second generator settles')
        after = state()
        h.check(after['inFloor'] and after.get('primary')==first and after.get('secondary')==first and not after['inInventory'], 'second generator pickup dropped or replaced the carried item')
        h.record('generator-existing-heavy-preserved',before,after,uiHandlersInvokedDirectly=False)
        h.lua(f'MELensInteriorTest.hammer=getPlayer():getInventory():getItemById({first});return true')
        drop('generator-native-drop')
        after = state()
        h.check(after['id']==first and after['inFloor'] and after.get('position'), 'native drop lost same generator or interior position')
        h.record('generator-native-drop-same-id',{},after,uiHandlersInvokedDirectly=False)
        time.sleep(1)
        h.capture('generator-dropped-inside')
        h.lua('''local p=getPlayer();local item=assert(p:getInventory():AddItem("Base.Hammer"))
p:setPrimaryHandItem(item);MELensInteriorTest.ordinaryHeld=item;return true''')
        before = state()
        grab('generator-ordinary-hand-grab')
        wait(f'local p=getPlayer();local a=p:getPrimaryHandItem();local b=p:getSecondaryHandItem();return a and b and a:getID()=={first} and b:getID()=={first}', 'ordinary item did not unequip for generator')
        after = state()
        h.check(h.lua('return getPlayer():getInventory():contains(MELensInteriorTest.ordinaryHeld)'), 'ordinary held item was dropped outside')
        h.record('generator-native-ordinary-unequip',before,after,uiHandlersInvokedDirectly=False)
        drop('generator-final-drop')
        h.REPORT['generatorIds']=[first,second]
        h.REPORT['unverified']=['multiplayer replication','cold save/reload']
        h.write_report('passed')
        return 0
    except Exception:
        error=traceback.format_exc()
        print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error)
        return 1
    finally:
        try:h.lua('MEMCNativeLab.releaseKeys();return true')
        except Exception:pass


if __name__=='__main__':
    raise SystemExit(main())
