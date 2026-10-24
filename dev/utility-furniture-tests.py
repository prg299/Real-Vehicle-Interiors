"""Production mouse pickup and inventory placement of the new service fittings."""
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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cargo',action='store_true');parser.add_argument('--only')
    parser.add_argument('--vehicle',help='Focused fit/removal/seat verification in another factory layout');args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    suffix=('-'+args.vehicle.split('.',1)[-1].lower()) if args.vehicle else ''
    h=load('final-feature-tests');h.configure(run/(('utility-furniture-'+args.only if args.only else 'utility-furniture')+suffix))
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    furniture,beds=load('final-furniture-tests'),load('bed-tests')
    interior,tap,_=furniture.load_helpers()
    try:
        targets=[('metalcase','Base.87fordF700swat'),('stretcher','Base.90fordF350ambulance')]
        if args.cargo:
            targets=[('safe','Base.87fordF700bank'),
                     ('parcels','Base.85chevyStepVanCitrusWave'),('medlocker','Base.90fordF350ambulance'),
                     ('medbench','Base.90fordF350ambulance'),('equipmentrack','Base.90fordF350SWAT'),
                     ('workbench','Base.VanRadio')]
        for piece,name in targets:
            if args.only and piece!=args.only:continue
            if args.vehicle:name=args.vehicle
            h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setTimedActionInstantCheat(false)
p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5)
local inv=p:getInventory();local items=inv:getItems();for i=items:size()-1,0,-1 do
local item=items:get(i);if item:getType()=="CarKey" or MELens.Parts.pieceOfItem(item) then inv:Remove(item) end end
return true''')
            beds.enter(h,name,'N')
            index=h.lua(f'''local v=MELensTest.vehicle;local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do if P.pieceAt(P.spotPart(v,i))=="{piece}" then return i end end
error("Factory fitting not found: {piece}")''')
            # The pickup workflow requires an emptied fitting. Loot transfer has its own native-input pass.
            h.lua(f'MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer():getItems():clear();return true')
            h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
            h.lua(furniture.FIXTURE.replace('"heater"',json.dumps(piece)))
            h.lua(f'''local T=MELensInteriorTest;local P=MELens.Parts
T.heaterIndex={index};T.heater=P.spotPart(T.vehicle,{index}):getInventoryItem()
assert(P.pieceOfItem(T.heater)=="{piece}");return true''')
            # Entry can finish before the isometric camera reaches the player.
            # Read projected click coordinates only after that pan has settled.
            time.sleep(.7)
            target=interior.read_state(h)['furniture']
            point=h.lua(f'return MELensInteriorTest.point({index})')
            label=h.lua('return getText("ContextMenu_MELens_PickUp")')
            before=interior.choose(h,tap,point,[point['header'],label],piece+'-pickup')
            after,seen=furniture.finish(h,interior,lambda s:s['furniture'].get('heaterInstalledId') is None
                                       and s['furniture']['heaterInInventory'],'MELensPickUpFurniture',piece+' pickup')
            h.check(after['furniture']['heaterId']==target['heaterId'],'pickup changed '+piece+' identity')
            h.record(piece+'-native-pickup',before,after,observedTimedActions=seen,uiHandlersInvokedDirectly=False)
            furniture.place_heater_from_inventory(h,interior,tap,target,capture_label=piece)
            h.capture(piece+'-reinstalled')
            if piece=='medbench':
                point=h.lua(f'return MELensInteriorTest.point({index})')
                rest=h.lua('return getText("ContextMenu_Rest")')
                before=interior.choose(h,tap,point,[point['header'],rest],'medbench-rest')
                after=interior.poll(h,lambda s:interior.idle(s) and s['interior'].get('kind')=='seat'
                                    and not s['interior']['standing']
                                    and s['interior'].get('pose')==s['interior'].get('expectedPose'),label='medical bench seated')
                h.record('medbench-native-rest',before,after,uiHandlersInvokedDirectly=False)
                time.sleep(.7)
                h.capture('medbench-resting')
                interior.interact_key(h,'medbench-get-up')
                interior.poll(h,lambda s:interior.idle(s) and s['interior']['standing'],label='medical bench get up')
            marker=h.lua('return MELensInteriorTest.positionAtExit()')
            interior.poll(h,lambda s:interior.idle(s) and s['interior']['standing']
                          and abs(s['interior']['debug'].get('x',999)-marker['x'])<=marker['halfX']
                          and abs(s['interior']['debug'].get('z',999)-marker['z'])<=marker['halfZ'],label=piece+' exit approach')
            interior.interact_key(h,piece+'-exit')
            interior.poll(h,lambda s:not s['interior']['inside'],label=piece+' outside')
        h.REPORT['scope']='Native mouse context pickup, inventory icon/menu, placement preview and medical bench resting; actual production timed actions. Empty containers before pickup are labelled fixtures.'
        h.REPORT['unverified']=['dedicated server','save/reload']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
