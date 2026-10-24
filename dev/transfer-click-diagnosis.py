"""Observe one real Transfer All click in the parent's existing native game.

UI visibility, layout and selected container are fixtures. The probe never moves,
adds or removes inventory items and never invokes a UI handler directly. Temporary
wrappers observe native button dispatch and call the original production methods.
Root must execute through run-heavy; this script does not own game lifecycle.
"""
import argparse
import json
import os
from pathlib import Path
import time
import traceback

import importlib.util

ROOT = Path(__file__).resolve().parents[1]

HIT_TEST = r'''
local w=getPlayerInventory(0);local button
for _,c in ipairs(w.controlsUI.controls) do
if c.title==getText("IGUI_invpage_Transfer_all") then button=c;break end end
assert(button,"Transfer All control missing")
local x,y=button:getAbsoluteX()+button:getWidth()/2,button:getAbsoluteY()+button:getHeight()/2
local function info(u)
local t=u:getTable();local ax,ay=u:getAbsoluteX(),u:getAbsoluteY()
return {type=t and t.Type or tostring(u),title=t and t.title,x=ax,y=ay,w=u:getWidth(),h=u:getHeight(),
maxDrawHeight=u:getMaxDrawHeight(),visible=u:isVisible(),enabled=u:isEnabled(),
rectContains=x>=ax and x<ax+u:getWidth() and y>=ay and y<ay+u:getHeight(),
pointOver=u:isPointOver(x,y),mouseOver=u:isMouseOver()}
end
local out={mouseX=getMouseX(),mouseY=getMouseY(),x=x,y=y,parents={},topLevel={}}
local u=button.javaObject
while u do
local node=info(u);node.children={};local children=u:getControls()
for i=0,children:size()-1 do
local entry=info(children:get(i));if entry.rectContains then node.children[#node.children+1]=entry end end
out.parents[#out.parents+1]=node;u=u:getParent()
end
local ui=UIManager.getUI()
for i=0,ui:size()-1 do
local ok,entry=pcall(info,ui:get(i))
if ok and entry.rectContains then entry.order=i;out.topLevel[#out.topLevel+1]=entry end end
return out
'''


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALL = r'''
if RVITransferProbe then RVITransferProbe.restore();RVITransferProbe=nil end
local p=getPlayer();local w=getPlayerInventory(0);local loot=getPlayerLoot(0)
local wanted=MELens.Parts.spotPart(MELensTest.vehicle,INDEX):getItemContainer()
local button
for _,c in ipairs(w.controlsUI.controls) do
if c.title==getText("IGUI_invpage_Transfer_all") then button=c;break end end
assert(button,"Transfer All control missing")
local d={events={},saved={},frames=0,arranges=0,down=0,up=0,onclick=0,perform=0,pane=0,weighted=0}
RVITransferProbe=d
local function ids(c)
local out={};for i=0,c:getItems():size()-1 do out[#out+1]=c:getItems():get(i):getID() end
table.sort(out);return out end
function d.state()
local q={};for _,a in ipairs(ISTimedActionQueue.getTimedActionQueue(p).queue) do q[#q+1]=tostring(a.Type) end
local eligible={};local hotbar=getPlayerHotbar(0)
for i=0,p:getInventory():getItems():size()-1 do local it=p:getInventory():getItems():get(i)
eligible[#eligible+1]={id=it:getID(),type=it:getFullType(),equipped=it:isEquipped(),favorite=it:isFavorite(),
hotbar=hotbar:isInHotbar(it),allowed=wanted:isItemAllowed(it)} end
return {ids=ids(wanted),inventoryIds=ids(p:getInventory()),queue=q,eligible=eligible,
paused=isGamePaused(),multiplier=getGameTime():getMultiplier(),pathing=MELens.pathing(p),
inventorySelected=w.inventoryPane.inventory==p:getInventory(),
lootSelected=loot.inventoryPane.inventory==wanted,lootPageSelected=loot.inventory==wanted,
frames=d.frames,arranges=d.arranges,down=d.down,up=d.up,onclick=d.onclick,perform=d.perform,
pane=d.pane,weighted=d.weighted,
button={x=button:getAbsoluteX(),y=button:getAbsoluteY(),w=button:getWidth(),h=button:getHeight(),
visible=button:isReallyVisible(),enabled=button.enable,pressed=button.pressed,
mouseOver=button:isMouseOver(),attached=button.parent==w.controlsUI},
events=d.events}
end
local function event(name,extra)
d.events[#d.events+1]={name=name,at=getTimestampMs(),paused=isGamePaused(),
pressed=button.pressed,visible=button:isReallyVisible(),enabled=button.enable,
lootSelected=loot.inventoryPane.inventory==wanted,extra=extra}
end
local function wrap(object,key,fn)
local original=object[key];assert(type(original)=="function",key.." is not callable")
d.saved[#d.saved+1]={object=object,key=key,own=rawget(object,key)}
object[key]=function(...) return fn(original,...) end
end
function d.restore()
for i=#d.saved,1,-1 do local s=d.saved[i];rawset(s.object,s.key,s.own) end
d.saved={}
end
wrap(button,"prerender",function(original,self,...)
d.frames=d.frames+1;return original(self,...) end)
wrap(w.controlsUI,"arrange",function(original,self,...)
d.arranges=d.arranges+1;return original(self,...) end)
wrap(button,"onMouseDown",function(original,self,x,y,...)
d.down=d.down+1;event("button-down",{x=x,y=y});return original(self,x,y,...) end)
wrap(button,"onMouseUp",function(original,self,x,y,...)
d.up=d.up+1;event("button-up",{x=x,y=y});return original(self,x,y,...) end)
wrap(button,"onMouseUpOutside",function(original,self,x,y,...)
event("button-up-outside",{x=x,y=y});return original(self,x,y,...) end)
wrap(button,"onclick",function(original,...)
d.onclick=d.onclick+1;event("button-onclick");return original(...) end)
wrap(button.target,"perform",function(original,self,...)
d.perform=d.perform+1;event("handler-perform");return original(self,...) end)
wrap(w.inventoryPane,"transferAll",function(original,self,...)
d.pane=d.pane+1;event("pane-transfer-all");return original(self,...) end)
wrap(w.inventoryPane,"transferItemsByWeight",function(original,self,items,container,...)
d.weighted=d.weighted+1;local selected={};for _,it in ipairs(items) do selected[#selected+1]=it:getID() end
event("transfer-items-by-weight",{ids=selected,targetMatches=container==wanted})
return original(self,items,container,...) end)
wrap(luautils,"walkToContainer",function(original,container,player,...)
local result=original(container,player,...)
event("walk-to-container",{sourceMatches=container==p:getInventory(),result=result});return result end)
return d.state()
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=45)
    parser.add_argument('--output-name', default='transfer-click-diagnosis')
    parser.add_argument('--inspect-only', action='store_true', help='Read current hit-test bounds; no UI refresh or input')
    args = parser.parse_args()
    if not args.output_name or any(not (c.isalnum() or c == '-') for c in args.output_name):
        parser.error('output-name must contain only letters, digits and hyphens')
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    source = json.loads((run/'open-storage-visual/native-feature-tests.json').read_text('utf-8-sig'))
    original = next(c['before'] for c in source['cases'] if c['name']=='workbench-take-all')
    storage = load('open-storage-visual-tests')
    h = load('final-feature-tests')
    expected = set(h._sequence(original['ids']))
    h.configure(run/args.output_name)
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    h.REPORT.update(scope=__doc__, expectedIds=sorted(expected), sourceReceipt=str(run/'open-storage-visual/native-feature-tests.json'))
    if args.inspect_only:
        h.REPORT['hitTest'] = h.lua(HIT_TEST)
        h.write_report('inspected')
        return 0
    installed = False
    try:
        # Preserve the failed item state. Only refresh the current inventory UI.
        storage.capture_mode(h, False)
        index = storage.select_slot(h, 'workbench')['index']
        h.REPORT['slot'] = index
        storage.inventory_windows(h, index)
        installed = True
        h.REPORT['initial'] = h.lua(INSTALL.replace('INDEX', str(index)))
        deadline = time.monotonic()+10
        while True:
            state = h.lua('return RVITransferProbe.state()')
            b = state['button']
            if state['frames'] >= 3 and b['visible'] and b['enabled'] and b['attached'] and state['lootSelected']:
                break
            h.check(time.monotonic()<deadline, 'Transfer All UI did not settle: '+json.dumps(state))
            time.sleep(.1)
        h.REPORT['before'] = state
        h.check(expected.issubset(set(h._sequence(state['inventoryIds']))), 'failed-run originals no longer all in player inventory')
        h.capture('transfer-click-before')
        # Read geometry again after capture; dispatch one real native click only.
        state = h.lua('return RVITransferProbe.state()')
        b = state['button'];x=int(b['x']+b['w']/2);y=int(b['y']+b['h']/2)
        h.lua(f'MEMCNativeLab.clickAt({x},{y});return true')
        h.REPORT['nativeInput']=True
        h.REPORT['inputs'].append(dict(action='diagnostic-transfer-all',api='MEMCNativeLab.clickAt',x=x,y=y))
        deadline=time.monotonic()+args.timeout; earliest=time.monotonic()+.7;seen=set()
        while True:
            state=h.lua('return RVITransferProbe.state()')
            queue=h._sequence(state['queue']);seen.update(queue)
            if time.monotonic()>=earliest and set(h._sequence(state['ids']))==expected and not queue:
                break
            if time.monotonic()>=deadline:
                break
            time.sleep(.15)
        h.REPORT['after']=state
        h.REPORT['observedTimedActions']=sorted(seen)
        h.REPORT['uiHandlersInvokedDirectly']=False
        restored=set(h._sequence(state['ids']))==expected and not h._sequence(state['queue'])
        h.REPORT['sameIdsRestored']=restored
        h.capture('transfer-click-after')
        h.write_report('passed' if restored else 'failed')
        return 0 if restored else 1
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        if installed:
            try:h.REPORT['after']=h.lua('return RVITransferProbe.state()')
            except Exception:pass
        h.write_report('failed',error)
        return 1
    finally:
        if installed:
            h.lua('if RVITransferProbe then RVITransferProbe.restore();RVITransferProbe=nil end;return true')


if __name__=='__main__':
    raise SystemExit(main())
