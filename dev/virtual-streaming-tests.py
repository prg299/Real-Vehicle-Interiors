"""Real chunk-unload regression for the reported Chevrolet painting-services van.

Entry uses production keyboard input. Spawn, cargo markers, engine state, clock
advance and player relocation are explicit fixtures in an owned disposable save.
The part's engine-owned update timestamp proves scheduling while its owner is
VirtualVehicle. No virtual update is called directly; retain and inspect logs.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "Base.85chevyStepVanSePaintingServices"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-source', default=os.environ.get('RVI_VERIFY_STREAMING_RUN'))
    args = parser.parse_args()
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h = load('final-feature-tests')
    h.configure(run/'virtual-streaming')
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=', 1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    snapshot = load('interior-lifecycle-tests').SNAPSHOT

    def wait(code, timeout=75):
        deadline = time.monotonic()+timeout
        while not h.lua(code):
            h.check(time.monotonic()<deadline, 'timeout: '+code)
            time.sleep(.2)

    def models():
        return sorted(json.loads(h.lua('return MEMCNativeLab.interiorModels(MELensLifecycle.vehicle)')),
                      key=lambda row: (row['part'], row['model'], row['live']))

    def virtual_inventory(state):
        # Meta simulation omits seat containers, including empty cabin seats.
        # Compare every installed item and cargo ID here; require all capacities
        # (including seats) to be identical again on the loaded vehicle.
        result = json.loads(json.dumps(state))
        for name, part in result['parts'].items():
            if name.startswith('Seat'):
                part.pop('capacity', None)
        return result

    def camera():
        h.lua('''local v=MELensLifecycle.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')

    try:
        h.REPORT['scope'] = __doc__
        h.REPORT['vehicle'] = SCRIPT
        h.REPORT['fixtures'] = ['spawn/repair/unlock', 'native and interior cargo markers',
                                'running engine for actual meta scheduling', 'seven-minute clock advance',
                                '400-tile relocation', 'post-streaming re-entry', 'saveGame API']
        if args.verify_source:
            expected = json.loads((ROOT/'build/rv'/args.verify_source/'virtual-streaming/native-feature-tests.json').read_text('utf-8'))
            h.lua('''local v=assert(getPlayer():getVehicle());assert(v:getScriptName()=="'''+SCRIPT+'''")
MELensLifecycle={vehicle=v};MELensTest={vehicle=v,all={}};return true''')
            wait('return MELens.isStanding(getPlayer())')
            time.sleep(1)
            actual = h.lua(snapshot)
            h.check(actual == expected['savedInventory'], 'fresh process changed saved items, furniture, capacities or utilities')
            h.check(models() == expected['savedModels'], 'fresh process left missing/stale interior model bindings')
            camera()
            h.capture('cold-reloaded-painting-van')
            h.REPORT['coldReload'] = {'inventoryIdentical': True, 'modelsIdentical': True, 'sqlId': actual['sqlId'], 'source': args.verify_source}
        else:
            h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);MELensMedia.cameraOff()
p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
            wait('return getCell():getGridSquare(10809,10140,0)~=nil')
            time.sleep(1)
            h.lua('''local stale={};local it=getCell():getVehicles():iterator()
while it:hasNext() do local v=it:next();local marker=v:getModData().RVIVirtualFixture
if type(marker)=="string" and marker:find("^rvi%-virtual%-streaming/") then stale[#stale+1]=v end end
for _,v in ipairs(stale) do v:permanentlyRemove() end
MELensTest={all={}};return true''')
            load('bed-tests').enter(h, SCRIPT, 'N')
            h.check(h.lua('return getPlayer():getVehicle()==MELensTest.vehicle'), 'Interact entered wrong vehicle')
            h.REPORT['nativeInput'] = True
            h.REPORT['inputs'].append({'action': 'enter requested van', 'api': 'MEMCNativeLab.holdKey', 'key': h.lua('return getCore():getKey("Interact")')})
            marker = 'rvi-virtual-streaming/'+os.environ['RVI_CAPTURE_RUN']
            h.REPORT['cargoMarkers'] = h.lua('''MELensLifecycle={vehicle=MELensTest.vehicle,marker='''+json.dumps(marker)+'''}
local v=MELensLifecycle.vehicle;v:getModData().RVIVirtualFixture=MELensLifecycle.marker
local gen=assert(v:getPartById(MELens.Parts.GENERATOR));gen:getModData().fuel=7.25;gen:getModData().on=false;gen:setCondition(73)
local water=assert(v:getPartById(MELens.Parts.WATER));water:getModData().water=11.5;water:getModData().tainted=true
v:getModData().MELensPropane=.33
local native,interior
for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i);local c=part:getItemContainer();local id=part:getId()
if c and c:getCapacity()>0 then
if not native and (id=="TruckBed" or id:find("Trunk")) then native={part=id,item=assert(c:AddItem("Base.Screwdriver")):getID()} end
if not interior and id:find("^MELensSpot") then interior={part=id,item=assert(c:AddItem("Base.Hammer")):getID()} end end end
assert(native and interior,"requires original cargo and new interior storage")
v:setKeysInIgnition(true);v:engineDoRunning();assert(v:isEngineRunning())
return {native=native,interior=interior}''')
            h.lua('saveGame();return true')
            camera();time.sleep(1)
            before = h.lua(snapshot); bindings = models()
            h.check(len(bindings)>1 and all(row['live'] for row in bindings), 'initial model bindings missing')
            h.REPORT['initialInventory'] = before
            h.REPORT['initialModels'] = bindings
            h.capture('painting-van-before-unload')
            time.sleep(1)
            h.check(h.lua(snapshot)==before, 'unchanged-input control changed committed storage/utilities')
            h.REPORT['unchangedControl'] = True
            for cycle in range(2):
                h.lua('''local p=getPlayer();local v=MELensLifecycle.vehicle
MELensLifecycle.anchor={x=v:getX(),y=v:getY()};MELensLifecycle.oldPart=v:getPartById(MELens.Parts.SHELL)
MELensLifecycle.generatorPart=v:getPartById(MELens.Parts.GENERATOR)
v:exit(p);MELensMedia.cameraOff();p:setX(v:getX()+400);p:setY(v:getY());p:setLastX(p:getX());p:setLastY(p:getY());return true''')
                wait('return not getCell():getVehicles():contains(MELensLifecycle.vehicle)')
                wait('return MELensLifecycle.generatorPart:getOwner().getModData==nil')
                owner = h.lua('return tostring(MELensLifecycle.generatorPart:getOwner())')
                dispatch_before = h.lua('''local part=MELensLifecycle.generatorPart
assert(part:getLuaFunction("update")=="MELens.Utilities.updateGenerator")
local last=part:getLastUpdated();local g=getGameTime();g:setTimeOfDay(g:getTimeOfDay()+.12);return last''')
                wait('return MELensLifecycle.generatorPart:getLastUpdated()>'+str(dispatch_before+.08), 25)
                dispatch_after = h.lua('return MELensLifecycle.generatorPart:getLastUpdated()')
                virtual_state = h.lua(snapshot)
                h.REPORT.setdefault('virtualInventory', []).append(virtual_state)
                h.check(virtual_inventory(virtual_state)==virtual_inventory(before), 'virtual updates altered committed storage/furniture/utilities')
                h.lua('''local p=getPlayer();local a=MELensLifecycle.anchor;p:setX(a.x+5);p:setY(a.y);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
                wait('''local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next()
if v:getModData().RVIVirtualFixture==MELensLifecycle.marker then MELensLifecycle.vehicle=v;MELensTest.vehicle=v;return true end end;return false''')
                time.sleep(.8)
                h.check(h.lua(snapshot)==before, 'streaming changed items, furniture, capacities or utilities')
                h.lua('local v=MELensLifecycle.vehicle;assert(v:enter(MELens.cabinSeat(v),getPlayer()));return true')
                wait('return MELens.isStanding(getPlayer())')
                camera();time.sleep(.8)
                h.check(models()==bindings, 'streaming left stale/missing/duplicate interior bindings')
                h.capture('painting-van-reloaded-'+str(cycle+1))
                h.REPORT.setdefault('streaming', []).append({'cycle': cycle+1, 'actualChunkUnload': True,
                    'owner': owner, 'virtualCallbackScheduled': True, 'lastUpdatedBefore': dispatch_before,
                    'lastUpdatedAfter': dispatch_after, 'inventoryIdentical': True, 'modelsIdentical': True,
                    'shellPartReplaced': h.lua('return MELensLifecycle.vehicle:getPartById(MELens.Parts.SHELL)~=MELensLifecycle.oldPart')})
                print('PASS real virtual streaming cycle '+str(cycle+1), flush=True)
            h.lua('MELensLifecycle.vehicle:engineDoIdle();saveGame();return true')
            time.sleep(1)
            h.REPORT['savedInventory'] = h.lua(snapshot)
            h.REPORT['savedModels'] = models()
            h.REPORT['world'] = h.lua('return getWorld():getWorld()')
        h.REPORT['unverified'] = ['dedicated multiplayer', 'ordinary driving route', 'Save/Continue menu input', 'offscreen appliance catch-up']
        # Startup diagnostics from the read-only game installation are retained.
        # Reject every gameplay error, including errors thrown by this fixture.
        errors = (run/'stderr.log').read_text('utf-8', errors='replace')
        gameplay = [line for line in errors.splitlines()
                    if line.startswith('ERROR:') and re.search(r'\bf:[1-9][0-9]*\b', line)]
        h.REPORT['logReview'] = {'gameplayErrorHeaders': gameplay,
                                'rviLuaError': bool(re.search(r'MELens_[\w]+\.lua|Lua\(\(MOD:Real Vehicle Interiors', errors)),
                                'startupErrorHeaders': sum(line.startswith('ERROR:') for line in errors.splitlines())-len(gameplay)}
        h.check(not gameplay and not h.REPORT['logReview']['rviLuaError'], 'native log contains gameplay/RVI errors')
        h.write_report('passed')
        (run/'request.json').write_text('{"action":"stop"}')
        return 0
    except Exception:
        error = traceback.format_exc();print(error, flush=True);h.write_report('failed', error)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
