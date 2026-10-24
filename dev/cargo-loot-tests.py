"""Native Loot All input for factory supplies and empty shelf visuals.

Spawning, positioning and selecting the container are fixtures. Transfer uses
the game's actual inventory button and timed actions; item IDs must survive.
"""
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


def button(h,window,key):
    point=h.lua(f'''local seen={{}};local label=getText("{key}");local window={window}
local function find(w)
if not w or seen[w] then return end;seen[w]=true
if w.title==label and w:isReallyVisible() then
local x,y=w:getAbsoluteX()+w:getWidth()/2,w:getAbsoluteY()+w:getHeight()/2
return {{x=x,y=y,enabled=w.enable,hitTest=w:isPointOver(x,y)}} end
for _,c in pairs(w.children or {{}}) do local p=find(c);if p then return p end end end
for _,control in ipairs(window.controlsUI and window.controlsUI.controls or {{}}) do
local p=find(control);if p then return p end end
return find(window)''')
    h.check(point and point.get('enabled') is not False,'native inventory control unavailable: '+key)
    return point


def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h=load('final-feature-tests');h.configure(run/'cargo-loot')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    try:
        for piece,name in [('safe','Base.87fordF700bank'),('medlocker','Base.90fordF350ambulance'),
                           ('equipmentrack','Base.90fordF350SWAT'),('parcels','Base.StepVan_Zippee')]:
            h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5)
local inv=p:getInventory();for n=inv:getItems():size()-1,0,-1 do
local item=inv:getItems():get(n);if not p:isEquipped(item) then inv:Remove(item) end end
return true''')
            load('bed-tests').enter(h,name,'N')
            index=h.lua(f'''local v=MELensTest.vehicle;local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do if P.pieceAt(P.spotPart(v,i))=="{piece}" then return i end end
error("Factory fitting missing")''')
            before=h.lua(f'''local v=MELensTest.vehicle;local P=MELens.Parts
local s=MELens.profileFor(v).spots[{index}];local x,z=P.spotPoint(s,0,P.kit("{piece}").depth+.13)
MELens.walkTo(getPlayer(),x,z);local c=P.spotPart(v,{index}):getItemContainer();local ids={{}};local types={{}}
for i=0,c:getItems():size()-1 do local item=c:getItems():get(i);ids[#ids+1]=item:getID();types[#types+1]=item:getFullType() end
return {{ids=ids,types=types,capacity=c:getCapacity(),weight=c:getCapacityWeight()}}''')
            before['ids']=h._sequence(before['ids']);before['types']=h._sequence(before['types'])
            h.check(before['ids'],'factory supplies empty')
            deadline=time.monotonic()+30
            while not h.lua(f'return not MELens.pathing(getPlayer()) and MELens.Parts.canReach(MELensTest.vehicle,MELens.Parts.spotPart(MELensTest.vehicle,{index}),getPlayer())'):
                h.check(time.monotonic()<deadline,'container approach did not finish');time.sleep(.15)
            h.lua(f'''local p=getPlayer();local w=getPlayerInventory(0);local loot=getPlayerLoot(0)
w:setVisible(true);w.isCollapsed=false;w.pin=true;w:clearMaxDrawHeight();w:setX(20);w:setY(50);w:setHeight(350)
loot:setVisible(true);loot.isCollapsed=false;loot.pin=true;loot:clearMaxDrawHeight();loot:setX(660);loot:setY(50);loot:setHeight(350)
loot:refreshBackpacks();w:setNewContainer(p:getInventory());loot:setNewContainer(MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer())
return true''')
            time.sleep(.7)
            h.lua(f'''local loot=getPlayerLoot(0)
loot:setNewContainer(MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer())
return true''')
            point=button(h,'getPlayerLoot(0)','IGUI_invpage_Loot_all')
            h.capture(piece+'-stocked')
            h.lua(f'MEMCNativeLab.clickAt({int(point["x"])},{int(point["y"])});return true')
            h.REPORT['inputs'].append(dict(action='loot-all-'+piece,api='MEMCNativeLab.clickAt',**point))
            h.REPORT['nativeInput']=True
            seen=set();deadline=time.monotonic()+120
            while True:
                state=h.lua(f'''local p=getPlayer();local part=MELens.Parts.spotPart(MELensTest.vehicle,{index});local c=part:getItemContainer()
local queue={{}};for _,a in ipairs(ISTimedActionQueue.getTimedActionQueue(p).queue) do queue[#queue+1]=tostring(a.Type) end
local ids={{}};for i=0,p:getInventory():getItems():size()-1 do ids[#ids+1]=p:getInventory():getItems():get(i):getID() end
return {{remaining=c:getItems():size(),ids=ids,queue=queue,model=MELens.Parts.shown[part],capacity=c:getCapacity()}}''')
                state['queue']=h._sequence(state['queue']);state['ids']=h._sequence(state['ids'])
                seen.update(state['queue'])
                if state['remaining']==0 and not state['queue']:break
                h.check(time.monotonic()<deadline,'native Loot All did not empty '+piece);time.sleep(.15)
            h.check(set(before['ids']).issubset(set(state['ids'])),'loot lost original item IDs')
            h.check(state['capacity']==before['capacity'],'loot changed capacity')
            time.sleep(.5)
            if piece in ('medlocker','equipmentrack'):
                visible=h.lua(f'''local out={{}};local v=MELensTest.vehicle
for _,s in ipairs(MELens.LooseView.shelfItems(v,MELens.profileFor(v),64)) do
if s.e.s=={index} then out[#out+1]=s.e.id end end;return out''')
                visible=h._sequence(visible)
                h.check(not visible,'looted shelf still displays stored items')
            h.lua('getPlayerInventory(0):setVisible(false);getPlayerLoot(0):setVisible(false);return true')
            h.capture(piece+'-emptied')
            h.record(piece+'-loot-all',before,state,observedTimedActions=sorted(seen),uiHandlersInvokedDirectly=False)
            if piece in ('medlocker','equipmentrack'):
                h.lua(f'''local w=getPlayerInventory(0);local loot=getPlayerLoot(0)
w:setVisible(true);loot:setVisible(true);w:setNewContainer(getPlayer():getInventory())
loot:setNewContainer(MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer())
return true''')
                time.sleep(.4)
                point=button(h,'getPlayerInventory(0)','IGUI_invpage_Transfer_all')
                h.lua(f'MEMCNativeLab.clickAt({int(point["x"])},{int(point["y"])});return true')
                h.REPORT['inputs'].append(dict(action='return-items-to-'+piece,api='MEMCNativeLab.clickAt',**point))
                deadline=time.monotonic()+120
                while True:
                    visible=h.lua(f'''local out={{}};local v=MELensTest.vehicle
for _,s in ipairs(MELens.LooseView.shelfItems(v,MELens.profileFor(v),64)) do
if s.e.s=={index} then out[#out+1]=s.e.id end end;return out''')
                    visible=h._sequence(visible)
                    committed=h.lua(f'''local c=MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer()
for _,id in ipairs({{{','.join(str(int(i)) for i in before['ids'])}}}) do if not c:getItemById(id) then return false end end
return #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0''')
                    if visible and committed:break
                    h.check(time.monotonic()<deadline,'stored items did not render on '+piece);time.sleep(.2)
                h.check(set(visible).issubset(set(state['ids'])),'shelf displays item IDs absent from the transferred inventory')
                h.lua('getPlayerInventory(0):setVisible(false);getPlayerLoot(0):setVisible(false);return true')
                h.capture(piece+'-returned-real-items')
                h.REPORT.setdefault('shelfContents',[]).append(dict(piece=piece,visibleItemIds=visible,
                    transferredInventoryIds=state['ids'],originalFactoryIds=before['ids']))
        h.REPORT['scope']=__doc__;h.REPORT['unverified']=['dedicated server']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
