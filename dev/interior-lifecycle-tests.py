"""Native model-loss recovery and real chunk-streaming fixtures in an owned game.

Initial entry uses the normal keyboard/action queue. Model loss is an explicit
causal fixture; player relocation drives real world streaming, not road-trip input.
No inventory, furniture, capacity or utility is recreated during recovery.
"""
import argparse
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

SNAPSHOT='''local v=MELensLifecycle.vehicle;local rows={}
for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i);local c=part:getItemContainer();local ids={}
if c then for j=0,c:getItems():size()-1 do ids[#ids+1]=c:getItems():get(j):getID() end;table.sort(ids) end
local item=part:getInventoryItem();local d=part:getModData();rows[part:getId()]={item=item and item:getID(),items=ids,capacity=c and c:getCapacity(),
condition=(part:getId():find("^MELensSpot") or part:getId():find("^SeatMELens")) and item and item:getCondition()
    or (part:getId()==MELens.Parts.GENERATOR and part:getCondition() or nil),
data={initialized=d.MELensInitialized,on=d.on,fuel=d.fuel,water=d.water,tainted=d.tainted}} end
return {sqlId=v:getSqlId(),script=v:getScriptName(),parts=rows,factoryLayout=v:getModData().MELensFactoryLayout}'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true')
    parser.add_argument('--vehicle',default='Base.87fordF700box')
    parser.add_argument('--verify-source',help='Cold-load the saved F700 from this earlier owned run')
    parser.add_argument('--source-output',default='interior-lifecycle')
    parser.add_argument('--output-name',default='interior-lifecycle');args=parser.parse_args()
    if Path(args.output_name).name!=args.output_name:parser.error('output must be a single folder name')
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN'];h=load('final-feature-tests');h.configure(run/args.output_name)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    def wait(code,timeout=40):
        end=time.monotonic()+timeout
        while not h.lua(code):
            h.check(time.monotonic()<end,'timeout: '+code);time.sleep(.15)
    def models():return sorted(json.loads(h.lua('return MEMCNativeLab.interiorModels(MELensLifecycle.vehicle)')),key=lambda row:(row['part'],row['model'],row['live']))
    try:
        h.REPORT['scope']=__doc__;h.REPORT['fixtures']=['spawn/repair/unlock','one marked screwdriver','native model loss','world relocation for chunk streaming','re-entry after streaming']
        h.REPORT['stateScope']='All installed item IDs, RVI furniture/generator conditions, container contents/capacities, initialization and generator/water state. Native component conditions are excluded: KI5 jack/vent placeholders normalize on reload.'
        if args.verify_source:
            expected=json.loads((ROOT/'build/rv'/args.verify_source/args.source_output/'native-feature-tests.json').read_text())
            h.lua('''local v=assert(getPlayer():getVehicle());assert(v:getScriptName()=="Base.87fordF700box")
MELensLifecycle={vehicle=v};MELensTest={vehicle=v,all={}};return true''')
            wait('return MELens.isStanding(getPlayer())');time.sleep(1)
            actual=h.lua(SNAPSHOT)
            committed=json.loads(json.dumps(expected['initialInventory']))
            for name,row in committed['parts'].items():
                if name!='MELensGenerator' and (not name.startswith(('MELensSpot','SeatMELens')) or 'item' not in row):
                    row.pop('condition',None)
            h.check(actual==committed,'cold load changes saved fittings, cargo, capacities or utility state')
            h.check(models()==expected['modelLoss']['before'],'cold load leaves missing/stale interior models')
            h.capture('cold-loaded-interior')
            h.REPORT['coldReload']={'source':args.verify_source,'inventoryIdentical':True,'modelsIdentical':True,'sqlId':actual['sqlId']}
            h.REPORT['bridgeGuard']=h.lua('''local bridge=MELensRV;MELensRV={};local ok,value=pcall(MELens.java)
MELensRV=bridge;return {partialRejected=ok and value==nil,completeRestored=MELens.java()==bridge}''')
            h.check(all(h.REPORT['bridgeGuard'].values()),'native partial bridge guard failed')
            h.REPORT['unverified']=['dedicated server','Save/Continue menu input']
            h.write_report('passed');return 0
        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);MELensMedia.cameraOff()
-- Earlier owned cold-load fixtures may be untracked by the ordinary spawn helper.
-- Remove only this suite's marked cars so the native Interact cache cannot pick
-- a second vehicle occupying the same test bay.
local stale={};local it=getCell():getVehicles():iterator()
while it:hasNext() do local v=it:next();local marker=v:getModData().RVILifecycleFixture
if type(marker)=="string" and marker:find("^interior%-lifecycle%-20261024%-") and (not MELensTest or v~=MELensTest.vehicle) then stale[#stale+1]=v end end
for _,v in ipairs(stale) do v:permanentlyRemove() end
p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
        load('bed-tests').enter(h,args.vehicle,'N')
        h.check(h.lua('return getPlayer():getVehicle()==MELensTest.vehicle'),'native Interact entered another vehicle')
        h.REPORT['nativeInput']=True
        h.REPORT['inputs'].append({'action':'enter requested interior','api':'MEMCNativeLab.holdKey',
                                  'key':h.lua('return getCore():getKey("Interact")'),'target':args.vehicle})
        marker=os.environ['RVI_CAPTURE_RUN']+'/'+args.output_name+'/'+str(time.monotonic_ns())
        h.lua('MELensLifecycle={vehicle=MELensTest.vehicle,marker='+json.dumps(marker)+'''};local v=MELensLifecycle.vehicle
v:getModData().RVILifecycleFixture=MELensLifecycle.marker
local gen=v:getPartById(MELens.Parts.GENERATOR);gen:getModData().fuel=7.25;gen:getModData().on=false;gen:setCondition(73)
local water=v:getPartById(MELens.Parts.WATER);water:getModData().water=11.5;water:getModData().tainted=true
for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i);if part:getId():find("^MELensSpot") and part:getItemContainer() and part:getItemContainer():getCapacity()>0 then
assert(part:getItemContainer():AddItem("Base.Screwdriver"));break end end
local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell*.45)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949);ISUIHandler.setVisibleAllUI(false);return true''')
        wait('return not MELens.pathing(getPlayer())');time.sleep(2)
        h.lua('saveGame();return true')
        for _ in range(6):
            zoom=h.lua('return getCore():getZoom(0)')
            if abs(zoom-.75)<.02:break
            h.lua('getCore():doZoomScroll(0,'+str(1 if zoom<.75 else -1)+');return true');time.sleep(.2)
        before=h.lua(SNAPSHOT);expected=models();h.check(len(expected)>=2 and all(row['live'] for row in expected),'initial owned models absent/stale')
        h.REPORT['initialInventory']=before
        h.capture('initial-interior')
        # Unchanged-input control at the same model/inventory state.
        time.sleep(1);control=models();control_inventory=h.lua(SNAPSHOT)
        h.REPORT['unchangedControl']={'before':expected,'after':control,'inventory':control_inventory}
        h.check(control==expected and control_inventory==before,'unchanged control changed models or committed inventory')
        removed=h.lua('return MEMCNativeLab.dropInteriorModels(MELensLifecycle.vehicle)');h.check(removed==len(expected),'model-loss fixture did not remove exactly the owned models')
        time.sleep(1.2);after=models();h.capture('after-model-loss')
        h.check(h.lua(SNAPSHOT)==before,'model loss/recovery changed inventory, capacities or utilities')
        recovered=after==expected
        h.check(not recovered if args.baseline else recovered,'unexpected model-loss recovery outcome')
        h.REPORT['modelLoss']={'before':expected,'after':after,'recovered':recovered,'inventoryIdentical':True,'removed':removed}
        if args.baseline:
            h.lua('''local v=MELensLifecycle.vehicle;local P=MELens.Parts;P.initShell(v,v:getPartById(P.SHELL))
for i in ipairs(MELens.profileFor(v).spots) do P.showPiece(P.spotPart(v,i),true,false) end;return true''')
        # A 400-tile relocation exceeds loaded chunks; wait for actual unloading.
        h.lua('''local p=getPlayer();local v=MELensLifecycle.vehicle
MELensLifecycle.anchor={x=v:getX(),y=v:getY()};MELensLifecycle.oldPart=v:getPartById(MELens.Parts.SHELL)
v:exit(p);MELensMedia.cameraOff();p:setX(v:getX()+400);p:setY(v:getY());p:setLastX(p:getX());p:setLastY(p:getY());return true''')
        wait('return not getCell():getVehicles():contains(MELensLifecycle.vehicle)',75)
        h.lua('''local p=getPlayer();local a=MELensLifecycle.anchor;p:setX(a.x+5);p:setY(a.y);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
        wait('''local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next()
if v:getModData().RVILifecycleFixture==MELensLifecycle.marker then MELensLifecycle.vehicle=v;MELensTest.vehicle=v;return true end end;return false''',75)
        time.sleep(.7)
        replaced=h.lua('return MELensLifecycle.vehicle:getPartById(MELens.Parts.SHELL)~=MELensLifecycle.oldPart')
        # Relocation/entry are labelled fixtures for the lifecycle gate.
        h.lua('''local v=MELensLifecycle.vehicle;assert(v:enter(MELens.cabinSeat(v),getPlayer()))
local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid];local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949);return true''')
        wait('return MELens.isStanding(getPlayer())')
        h.lua('''local v=MELensLifecycle.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell*.45);return true''')
        wait('return not MELens.pathing(getPlayer())');time.sleep(1)
        streamed=models();h.capture('after-real-streaming')
        loaded_inventory=h.lua(SNAPSHOT)
        h.REPORT['streaming']={'before':expected,'after':streamed,'shellPartReplaced':replaced,
            'inventoryIdentical':loaded_inventory==before,'nativeChunkUnloadObserved':True,'loadedInventory':loaded_inventory}
        h.check(loaded_inventory==before,'real streaming changed committed inventory, capacities or utilities')
        if not args.baseline:h.check(streamed==expected,'streaming left stale, missing or duplicate interior model bindings')
        h.REPORT['world']=h.lua('return getWorld():getWorld()')
        h.REPORT['unverified']=['dedicated server','ordinary driving route to Louisville','controller input']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1

if __name__=='__main__':raise SystemExit(main())
