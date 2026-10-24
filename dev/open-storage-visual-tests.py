"""Unobscured native open-storage views around real Take All / Transfer All input.

Run through run-heavy in an already owned disposable game. Root owns lifecycle.
Spawn, inventory cleanup, approach, container selection, camera and UI visibility
are fixtures. Container contents are untouched factory stock; both transfers use
native mouse events, the production inventory controls and timed actions.
"""
import argparse
import json
import os
from pathlib import Path
import time
import traceback
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
PIECES = ('medlocker', 'equipmentrack', 'workbench')
PREFERRED = {
    'medlocker': ('Base.90fordF350ambulance', 'Base.VanAmbulance'),
    'equipmentrack': ('Base.90fordF350SWAT', 'Base.87fordF700swat'),
    'workbench': ('Base.VanRadio', 'Base.VanRadio_3N',
                  'Base.85chevyStepVanTheCompleteRepair'),
}


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def poll(h, read, ready, label, timeout=45):
    deadline = time.monotonic() + timeout
    h.REPORT['activeWait'] = label
    while True:
        state = read()
        if ready(state):
            return state
        h.check(time.monotonic() < deadline, label + ': ' + json.dumps(state))
        time.sleep(.15)


def capture_mode(h, enabled):
    """Keep asynchronously refreshed inventory panels out of the actual capture."""
    h.lua('''if MELensOpenStorageCapture then
Events.OnTick.Remove(MELensOpenStorageCapture);MELensOpenStorageCapture=nil end
ISUIHandler.setVisibleAllUI(true);return true''')
    if enabled:
        h.lua('''MELensOpenStorageCapture=function()
getPlayerInventory(0):setVisible(false);getPlayerLoot(0):setVisible(false)
MELensRV.clearMarker();MELensRV.clearSpotMarkers()
end
MELensOpenStorageCapture();Events.OnTick.Add(MELensOpenStorageCapture)
ISUIHandler.setVisibleAllUI(false);return true''')


def choose_vehicle(h, piece, override):
    if override:
        return override
    candidates = h._sequence(h.lua(f'''local out={{}};local wanted={json.dumps(piece)}
for name,pr in pairs(MELens.Profiles) do
for _,s in ipairs(pr.spots or {{}}) do
if s.factory and s.default==wanted then out[#out+1]=name;break end end end
table.sort(out);return out'''))
    h.check(candidates, 'no loaded factory profile contains ' + piece)
    return next((name for name in PREFERRED[piece] if name in candidates), candidates[0])


def select_slot(h, piece):
    # A left-wall cabinet faces this camera. Prefer the rearmost matching slot so
    # neighbouring front cabinets cannot hide the board whose contents change.
    return h.lua(f'''local v=MELensTest.vehicle;local P=MELens.Parts
local pr=MELens.profileFor(v);local wanted={json.dumps(piece)};local selected,score
for i,s in ipairs(pr.spots) do if P.pieceAt(P.spotPart(v,i))==wanted then
local rank=(s.wall=="left" and 0 or (s.wall=="right" and 100 or 200))+(s.z or 0)
if not score or rank<score then selected=i;score=rank end end end
assert(selected,"Factory fitting missing: "..wanted)
local s=pr.spots[selected];return {{index=selected,wall=s.wall,x=s.x,z=s.z,
role=pr.factoryRole,factoryUse=pr.factoryUse}}''')


def snapshot(h, index):
    state = h.lua(f'''local p=getPlayer();local v=MELensTest.vehicle;local P=MELens.Parts
local part=P.spotPart(v,{index});local c=part:getItemContainer()
local ids,types,inventory,queue,visible={{}},{{}},{{}},{{}},{{}}
for i=0,c:getItems():size()-1 do local item=c:getItems():get(i)
ids[#ids+1]=item:getID();types[#types+1]=item:getFullType() end
for i=0,p:getInventory():getItems():size()-1 do
inventory[#inventory+1]=p:getInventory():getItems():get(i):getID() end
for _,a in ipairs(ISTimedActionQueue.getTimedActionQueue(p).queue) do queue[#queue+1]=tostring(a.Type) end
for _,s in ipairs(MELens.LooseView.shelfItems(v,MELens.profileFor(v),64)) do
if s.e.s=={index} then visible[#visible+1]=s.e.id end end
return {{ids=ids,types=types,inventoryIds=inventory,queue=queue,visibleIds=visible,
capacity=c:getCapacity(),weight=c:getCapacityWeight(),model=P.shown[part],
pathing=MELens.pathing(p),inventoryVisible=getPlayerInventory(0):isReallyVisible(),
lootVisible=getPlayerLoot(0):isReallyVisible()}}''')
    for key in ('ids', 'types', 'inventoryIds', 'queue', 'visibleIds'):
        state[key] = h._sequence(state.get(key))
    return state


def approach(h, index, piece):
    capture_mode(h, False)
    h.lua(f'''MELensMedia.cameraOff();local v=MELensTest.vehicle;local P=MELens.Parts
local s=MELens.profileFor(v).spots[{index}]
local x,z=P.spotPoint(s,0,P.kit({json.dumps(piece)}).depth+.13)
MELens.walkTo(getPlayer(),x,z);return true''')
    poll(h, lambda: h.lua(f'''return not MELens.pathing(getPlayer()) and
MELens.Parts.canReach(MELensTest.vehicle,MELens.Parts.spotPart(MELensTest.vehicle,{index}),getPlayer())'''),
         bool, 'approach selected storage')


def inventory_windows(h, index):
    h.lua(f'''local p=getPlayer();local w=getPlayerInventory(0);local loot=getPlayerLoot(0)
w:setVisible(true);w.isCollapsed=false;w.pin=true;w:clearMaxDrawHeight()
w:setX(80);w:setY(50);w:setHeight(350)
loot:setVisible(true);loot.isCollapsed=false;loot.pin=true;loot:clearMaxDrawHeight()
loot:setX(660);loot:setY(50);loot:setHeight(350)
w:refreshBackpacks();loot:refreshBackpacks();w:setNewContainer(p:getInventory())
loot:setNewContainer(MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer())
return true''')
    time.sleep(.7)
    h.lua(f'''getPlayerLoot(0):setNewContainer(
MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer());return true''')


def transfer(h, cargo, index, piece, restore, original):
    approach(h, index, piece)
    inventory_windows(h, index)
    window = 'getPlayerInventory(0)' if restore else 'getPlayerLoot(0)'
    key = 'IGUI_invpage_Transfer_all' if restore else 'IGUI_invpage_Loot_all'
    point = cargo.button(h, window, key)
    h.check(0 <= point['x'] < 1280 and 0 <= point['y'] < 720, 'offscreen inventory control')
    h.check(point.get('hitTest') is True, 'inventory control is covered or clipped: '+json.dumps(point))
    before = snapshot(h, index)
    h.lua(f'MEMCNativeLab.clickAt({int(point["x"])},{int(point["y"])});return true')
    h.REPORT['nativeInput'] = True
    h.REPORT['inputs'].append(dict(action=('restore-' if restore else 'take-all-') + piece,
                                    api='MEMCNativeLab.clickAt', **point))
    seen = set()
    dispatched_after = time.monotonic() + .65
    original_ids = set(original['ids'])

    def read():
        state = snapshot(h, index)
        seen.update(state['queue'])
        return state

    def finished(state):
        contents = set(state['ids'])
        settled = time.monotonic() >= dispatched_after and not state['queue']
        if restore:
            return settled and contents == original_ids and bool(state['visibleIds'])
        return settled and not contents and not state['visibleIds']

    after = poll(h, read, finished, ('restore ' if restore else 'empty ') + piece, 120)
    h.check(after['capacity'] == original['capacity'], 'storage capacity changed during transfer')
    if restore:
        h.check(set(after['visibleIds']).issubset(original_ids), 'display contains non-stored item IDs')
    else:
        h.check(original_ids.issubset(set(after['inventoryIds'])), 'Take All lost original item IDs')
    h.record(piece + ('-transfer-all' if restore else '-take-all'), before, after,
             observedTimedActions=sorted(seen), uiHandlersInvokedDirectly=False)
    return after


def clean_capture(h, index, piece, label, zoom, expected_ids):
    capture_mode(h, True)
    framing = h.lua(f'''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local g=MELens.WalkGrids[pr.walkGrid];local P=MELens.Parts;local s=pr.spots[{index}]
local lo,hi=g.z0+.35,g.z0+#g.rows*g.cell-.45
local pose=math.abs(lo-s.z)>math.abs(hi-s.z) and lo or hi
MELens.walkTo(getPlayer(),pr.aisleX or 0,pose)
local x,z=P.spotPoint(s,0,P.kit({json.dumps(piece)}).depth/2)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x()+x,o:y()+pr.floorY,o:z()+z,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
return {{slot={index},focusX=x,focusZ=z,playerX=pr.aisleX or 0,playerZ=pose}}''')
    poll(h, lambda: snapshot(h, index), lambda s: not s['pathing'] and not s['queue'],
         'unobscured capture position')
    for _ in range(12):
        actual = h.lua('return getCore():getZoom(0)')
        if abs(actual-zoom) < .02:
            break
        h.lua(f'getCore():doZoomScroll(0,{1 if actual < zoom else -1});return true')
        time.sleep(.25)
    actual = h.lua('return getCore():getZoom(0)')
    h.check(abs(actual-zoom) < .02, 'requested close capture zoom unavailable')
    time.sleep(.7)
    state = snapshot(h, index)
    h.check(not state['inventoryVisible'] and not state['lootVisible'], 'inventory covers clean capture')
    h.check(set(state['ids']) == set(expected_ids), 'capture fixture changed storage contents')
    h.check(not h.lua('return MELensRV.shaderError()'), 'native cutaway shader error')
    path = h.capture(label)
    h.REPORT.setdefault('cleanViews', []).append(dict(image=path, piece=piece, state=state,
                                                       framing=framing, zoom=actual,
                                                       visualReview='pending'))
    capture_mode(h, False)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--piece', choices=PIECES)
    parser.add_argument('--vehicle', help='Exact script ID; requires --piece')
    parser.add_argument('--heading', choices=('N', 'E', 'S', 'W'), default='N')
    parser.add_argument('--zoom', type=float, choices=(.5, .75), default=.5)
    parser.add_argument('--output-name', default='open-storage-visual')
    args = parser.parse_args()
    if args.vehicle and not args.piece:
        parser.error('--vehicle requires --piece')
    if not args.output_name or any(not (c.isalnum() or c == '-') for c in args.output_name):
        parser.error('--output-name must contain only letters, digits and hyphens')
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    cargo = load('cargo-loot-tests')
    h = cargo.load('final-feature-tests')
    h.configure(run/args.output_name)
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=', 1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    h.REPORT['scope'] = __doc__
    h.REPORT['unverified'] = ['manual visual acceptance of clean captures', 'dedicated server',
                              'save/reload', 'driving retention', 'all item-size combinations']
    try:
        h.lua('getCore():setResolutionAndFullScreen(1280,720,false);return true')
        time.sleep(.6)
        for piece in ([args.piece] if args.piece else PIECES):
            name = choose_vehicle(h, piece, args.vehicle)
            capture_mode(h, False)
            h.lua('''MELensMedia.cameraOff();local p=getPlayer()
if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setTimedActionInstantCheat(false)
p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5)
getGameTime():setTimeOfDay(12);return true''')
            cargo.load('bed-tests').enter(h, name, args.heading)
            h.REPORT['inputs'].append(dict(vehicle=name, action='enter', path='production Interact key'))
            # The entering fixture creates a vehicle key. Keep equipped clothes,
            # remove other pre-existing inventory so Transfer All returns exactly
            # the factory contents, with no unrelated key or previous case loot.
            h.lua('''local p=getPlayer();local inv=p:getInventory()
for i=inv:getItems():size()-1,0,-1 do local item=inv:getItems():get(i)
if not p:isEquipped(item) then inv:Remove(item) end end;return true''')
            slot = select_slot(h, piece)
            index = slot['index']
            original = poll(h, lambda: snapshot(h, index),
                            lambda s: bool(s['ids']) and bool(s['visibleIds']),
                            'factory contents visible on ' + piece, 15)
            h.check(set(original['visibleIds']).issubset(set(original['ids'])),
                    'stocked display contains item IDs outside selected container')
            h.REPORT.setdefault('scenes', []).append(dict(piece=piece, vehicle=name,
                                                          heading=args.heading, slot=slot,
                                                          original=original))
            clean_capture(h, index, piece, piece+'-stocked-clear', args.zoom, original['ids'])
            transfer(h, cargo, index, piece, False, original)
            clean_capture(h, index, piece, piece+'-empty-clear', args.zoom, [])
            transfer(h, cargo, index, piece, True, original)
            clean_capture(h, index, piece, piece+'-restored-clear', args.zoom, original['ids'])
            h.write_report('running')
        h.write_report('passed')
        return 0
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        try:
            h.capture('open-storage-failure')
        except Exception:
            pass
        h.write_report('failed', error)
        return 1
    finally:
        capture_mode(h, False)
        h.lua('MELensMedia.cameraOff();return true')


if __name__ == '__main__':
    raise SystemExit(main())
