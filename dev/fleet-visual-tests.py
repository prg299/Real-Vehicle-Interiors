"""Per-variant native-renderer audit in the guarded parent's inactive desktop.

Every variant receives native entry/exit and four furnished renderer captures.
Each body family's bed+kitchen is placed through inventory mouse/UI dispatch;
other variants use explicitly labelled furniture fixtures. Additional headings
use fresh vehicle/seat fixtures, not driving, entry or camera-control evidence.
"""
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--only', action='append', help='Exact script ID; repeat to retest affected variants')
    parser.add_argument('--output-name', help='Separate artifact folder for focused retests')
    parser.add_argument('--stale-cut-height', action='store_true', help='Seed a previous vehicle height before each native entry')
    args = parser.parse_args()
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    furniture, beds = load('final-furniture-tests'), load('bed-tests')
    interior, tap, h = furniture.load_helpers()
    output_name=args.output_name or ('visual-pilot' if args.pilot else 'visual-all')
    assert output_name and all(c.isalnum() or c=='-' for c in output_name)
    h.configure(run/output_name)
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    cache = next(x.split('=', 1)[1] for x in session['command'] if x.startswith('-cachedir='))
    h.SCREENS = Path(cache)/'Screenshots'
    families = json.loads((ROOT/'tools-src/vehicles/coverage.json').read_text())['families']
    family_for = {n: f for f in families for n in f['vehicles']}
    contracts = h._sequence(h.lua('''local rows={};for name,pr in pairs(MELens.Profiles) do
local s=ScriptManager.instance:getVehicle(name)
rows[#rows+1]={name=name,available=s~=nil,family=pr.walkGrid,spots=#pr.spots}
end;table.sort(rows,function(a,b) return a.name<b.name end);return rows'''))
    (h.OUTPUT/'inventory.json').write_text(json.dumps(contracts, indent=2))
    missing = [r['name'] for r in contracts if not r['available']]
    assert not missing, 'Supported scripts unavailable in native test: '+str(missing)
    rows = contracts
    if args.pilot:
        names = ['Base.Van', 'Base.85chevyStepVanCitrusWave', 'Base.87fordF700swat']
        rows = [next(r for r in rows if r['name']==name) for name in names]
    rows = rows[args.start:args.start+args.limit if args.limit else None]
    h.REPORT['inventory'] = contracts
    manifest = h.OUTPUT/'variants.jsonl'

    def input_key(code, ms, label):
        h.lua(f'MEMCNativeLab.holdKey({int(code)},{ms});return true')
        h._input_release = time.monotonic()+ms/1000+.5
        h.REPORT['inputs'].append(dict(action=label,key=code,durationMs=ms,api='MEMCNativeLab.holdKey'))
        h.REPORT['nativeInput'] = True
        time.sleep(ms/1000+.55)

    def frame():
        h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local g=MELens.WalkGrids[pr.walkGrid];local z=g.z0+#g.rows*g.cell/2
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+z,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
        time.sleep(.4)

    try:
        if h.lua('return getPlayer():getVehicle()~=nil'):
            h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text())
            h.lua(interior.FIXTURE)
            h.lua('return MELensInteriorTest.positionAtExit()')
            interior.interact_key(h, 'previous-case-exit')
            interior.poll(h, lambda s: not s['interior']['inside'], label='previous outside')
        for number, row in enumerate(rows, args.start):
            if args.only and row['name'] not in args.only:continue
            name = row['name']
            label = ('v%03d-'%number)+name.split('.',1)[1].lower()
            label = ''.join(c if c.isalnum() else '-' for c in label)
            h.REPORT['activeVariant'] = name
            print('VISUAL_START '+str(number)+' '+name, flush=True)
            h.lua('''MELensMedia.cameraOff();local p=getPlayer();assert(not p:getVehicle())
getGameTime():setTimeOfDay(12)
p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5)
p:setTimedActionInstantCheat(false)
local inv=p:getInventory();local items=inv:getItems();for i=items:size()-1,0,-1 do
local item=items:get(i);if MELens.Parts.pieceOfItem(item) or item:getType()=="CarKey" then inv:Remove(item) end end;return true''')
            if args.stale_cut_height:
                h.lua('MELensRV.setCutFrontTop(0);return true')
            beds.enter(h,name,'E')
            appearance=h.lua('''local v=MELensTest.vehicle;return {h=v:getColorHue(),s=v:getColorSaturation(),
v=v:getColorValue(),skin=v:getSkinIndex()}''')
            h.REPORT['inputs'].append(dict(action=name+'-enter',api='MEMCNativeLab.holdKey',fixture='spawn and outside position',binding='Interact'))
            h.REPORT['nativeInput'] = True
            h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text())
            h.lua(interior.FIXTURE)
            family = family_for.get(name)
            placement_ui = family and name == family['representative']
            if args.pilot: placement_ui = True
            target_zoom=1.25 if not family else (1 if family['family']=='F350Ambulance' else .75)
            for _ in range(10):
                zoom=h.lua('return getCore():getZoom(0)')
                if abs(zoom-target_zoom)<.02:break
                h.lua(f'getCore():doZoomScroll(0,{1 if zoom<target_zoom else -1});return true')
                time.sleep(.5)
            pieces = h._sequence(h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local r={}
for i,s in ipairs(pr.spots) do if s.default=="bed" or s.default=="kitchen" then
r[#r+1]={index=i,piece=s.default,empty=MELens.Parts.pieceAt(MELens.Parts.spotPart(v,i))==nil} end end;return r'''))
            if not family:
                pieces=[]  # Existing campers/buses/trucks keep their factory furnished scene.
            if family and family['family'] in ('E150Long','VanillaRadioVan'):
                pieces.sort(key=lambda item:item['piece']=='bed')
            receipts=[]
            for item in pieces:
                if not item['empty']: continue
                piece,index = item['piece'],item['index']
                if placement_ui:
                    h.lua(f'local i=getPlayer():getInventory():AddItem("Base.MELensRV_{piece.capitalize()}");assert(i);return i:getID()')
                    h.lua('MELensInteriorTest.heater=nil;MELensInteriorTest.heaterIndex=nil;return true')
                    h.lua(furniture.FIXTURE.replace('"heater"',json.dumps(piece)))
                    h.lua(f'MELensInteriorTest.heaterIndex={index};return true')
                    state=interior.read_state(h)
                    furniture.place_heater_from_inventory(h,interior,tap,state['furniture'])
                else:
                    h.lua(f'''local v=MELensTest.vehicle;local P=MELens.Parts;local pr=MELens.profileFor(v)
assert(P.fits(pr.spots[{index}],"{piece}"));assert(P.roomFor(pr,P.standing(v,pr),{index},"{piece}"))
local part=P.spotPart(v,{index});part:setInventoryItem(instanceItem(P.itemType("{piece}")))
P.applyPiece(v,part);v:updatePartStats();v:updateTotalMass();return true''')
                receipts.append(dict(piece=piece,index=index,path='inventory mouse/UI' if placement_ui else 'furniture fixture'))
            if placement_ui and row['spots']==3:
                # An overlapping front fridge must still reject placement, with
                # the carried item and installed furniture IDs unchanged.
                h.lua('local i=getPlayer():getInventory():AddItem("Base.MELensRV_Fridge");assert(i);return i:getID()')
                h.lua('MELensInteriorTest.heater=nil;MELensInteriorTest.heaterIndex=nil;return true')
                h.lua(furniture.FIXTURE.replace('"heater"','"fridge"'))
                h.lua('MELensInteriorTest.heaterIndex=3;return true')
                ids_before=h.lua('''local v=MELensTest.vehicle;local r={};for i=1,3 do
local item=MELens.Parts.spotPart(v,i):getInventoryItem();r[i]=item and item:getID() or false end;return r''')
                before_reject=interior.read_state(h)
                furniture.open_inventory_item_menu(h,interior,tap)
                option_label=h.lua('return getText("ContextMenu_MELens_PlaceFurniture")')
                menu=interior.poll(h,lambda s:tap.menu_option(s,option_label) is not None,timeout=8,label='overlap Place menu')
                option=tap.menu_option(menu,option_label)
                tap.native_click(h,option['x'],option['y'],'overlapping-fridge-place')
                time.sleep(.8)
                rejected=interior.read_state(h)
                assert not rejected['furniture']['placementActive'] and rejected['furniture']['heaterInInventory']
                assert rejected['furniture']['heaterId']==before_reject['furniture']['heaterId']
                assert not rejected['furniture'].get('heaterInstalledId')
                assert h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
return P.pieceAt(P.spotPart(v,1))=="bed" and P.pieceAt(P.spotPart(v,2))=="kitchen"''')
                assert ids_before==h.lua('''local v=MELensTest.vehicle;local r={};for i=1,3 do
local item=MELens.Parts.spotPart(v,i):getInventoryItem();r[i]=item and item:getID() or false end;return r''')
                h.record(label+'-reject-overlapping-fridge',before_reject,rejected,uiHandlersInvokedDirectly=False)
                h.capture(label+'-overlap-rejected')
                input_key(rejected['inventoryUI']['toggleKey'],180,'inventory-close-after-rejection')
            # Exercise normal movement along the aisle with both pieces present.
            h.lua('return MELensInteriorTest.positionAtExit()')
            interior.poll(h,lambda s:interior.idle(s),label=label+' furnished exit approach')
            before=interior.read_state(h)
            code=h.lua('''local v=MELensTest.vehicle;local q=Vector3f.new();v:getWorldPos(0,0,1,q)
local dx,dy=q:x()-v:getX(),q:y()-v:getY();local sx,sy=dx-dy,dx+dy
return getCore():getKey(math.abs(sx)>math.abs(sy) and (sx>0 and "Right" or "Left") or (sy>0 and "Backward" or "Forward"))''')
            input_key(code,500,label+'-walk-furnished')
            after=interior.read_state(h)
            a,b=before['interior']['debug'],after['interior']['debug']
            assert (a['x']-b['x'])**2+(a['z']-b['z'])**2>.015, 'Furnished aisle blocked '+name
            if placement_ui:
                bed_index=next(item['index'] for item in pieces if item['piece']=='bed')
                point=h.lua(f'return MELensInteriorTest.point({bed_index})')
                rest=h.lua('return getText("ContextMenu_Rest")')
                before_rest=interior.choose(h,tap,point,[point['header'],rest],label+'-rest')
                interior.poll(h,lambda s:h.lua('return getPlayer():getVariableString("MELensBed")=="Awake"'),label=label+' resting')
                h.capture(label+'-resting')
                interior.interact_key(h,label+'-get-up')
                standing=interior.poll(h,lambda s:s['interior']['standing'] and interior.idle(s),label=label+' up')
                h.record(label+'-rest-and-get-up',before_rest,standing,uiHandlersInvokedDirectly=False)
            scene=h.lua('return MELens.Parts.standing(MELensTest.vehicle,MELens.profileFor(MELensTest.vehicle))')
            images=[]
            h.lua('MELensRV.setSurvey(true);return true')
            frame();images.append(h.capture(label+'-interior-e'))
            assert not h.lua('return MELensRV.shaderError()'),'Native cutaway shader failed'
            render_survey=h.lua('return MELensRV.surveyInfo()')
            h.lua('MELensRV.setSurvey(false);return true')
            h.lua('MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return MELensInteriorTest.positionAtExit()')
            interior.poll(h,lambda s:interior.idle(s),label=label+' exit fixture')
            interior.interact_key(h,label+'-exit')
            interior.poll(h,lambda s:not s['interior']['inside'],label=label+' outside')
            frame();images.append(h.capture(label+'-outside'))
            for heading in ('N','S','W'):
                h.lua('''MELensMedia.cameraOff();local p=getPlayer();assert(not p:getVehicle())
p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true''')
                spawn=(ROOT/'dev/lua/spawn_one.lua').read_text().replace('NAME',name)
                spawn=spawn.replace('tonumber("7")','tonumber("-4")').replace('local HEADING = "E"',f'local HEADING = "{heading}"')
                h.lua(spawn)
                h.lua('MELensTest.vehicle:setColorHSV(%s,%s,%s);MELensTest.vehicle:setSkinIndex(%s);return true'%(
                    appearance['h'],appearance['s'],appearance['v'],appearance['skin']))
                scene_lua='{'+','.join('[%s]="%s"'%(index,piece) for index,piece in scene.items())+'}'
                h.lua('''local v=MELensTest.vehicle;local p=getPlayer();local P=MELens.Parts
for index,piece in pairs(%s) do local part=P.spotPart(v,index)
part:setInventoryItem(instanceItem(P.itemType(piece)))
P.applyPiece(v,part) end
assert(v:enter(MELens.cabinSeat(v),p));return true'''%scene_lua)
                deadline=time.monotonic()+10
                while not h.lua('return MELens.isStanding(getPlayer())'):
                    assert time.monotonic()<deadline,'capture seat fixture failed'
                    time.sleep(.1)
                time.sleep(.7);frame();images.append(h.capture(label+'-interior-'+heading.lower()))
                h.lua('MELensMedia.cameraOff();MELensTest.vehicle:exit(getPlayer());return true')
                time.sleep(.25)
            effective_family=h.lua('return MELens.profileFor(MELensTest.vehicle).walkGrid')
            record=dict(number=number,name=name,family=effective_family,catalogueFamily=row['family'],staleHeightFixture=args.stale_cut_height,appearance=appearance,renderSurvey=render_survey,placements=receipts,images=images,
                        nativeEntry=True,nativeFurnishedWalk=True,nativeExit=True,visualReview='pending')
            with manifest.open('a',encoding='utf-8') as out: out.write(json.dumps(record)+'\n')
            print('VISUAL_PASS '+str(number)+' '+name,flush=True)
            h.write_report('running')
        h.REPORT['unverified']=['dedicated server','human acceptance','driving input; extra headings use capture fixtures']
        h.write_report('passed')
        return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error)
        return 1


if __name__=='__main__':raise SystemExit(main())
