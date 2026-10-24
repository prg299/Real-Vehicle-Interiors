"""Native entry/exit and close/open/missing rear-door lining captures.

Entry and exit use production keyboard input. Open/missing states are labelled
fixtures to isolate model visibility; they do not claim a mechanics-menu test.
"""
import importlib.util
import argparse
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-bodies',action='store_true')
    parser.add_argument('--only',action='append',help='Restrict the selected body families to these exact script IDs')
    parser.add_argument('--output-name',default='rear-doors')
    diagnostic=parser.add_mutually_exclusive_group()
    diagnostic.add_argument('--cap-isolation-only',action='store_true',help='Same-camera cap hidden/restored controls; skip door workflow checks')
    parser.add_argument('--white-passenger',action='store_true',help='White VanSeats paint fixture exposes low-contrast exterior seams')
    parser.add_argument('--headings',nargs='+',choices=('E','N','S','W'),default=('E','N','S','W'))
    parser.add_argument('--height-choice',type=int,choices=(1,2,3),help='Fixed wall-height fixture for a diagnostic pass')
    parser.add_argument('--height-headings',nargs='+',choices=('E','N','S','W'),default=('N',),help='Headings receiving low/high/full-wall controls')
    parser.add_argument('--missing-headings',nargs='+',choices=('E','N','S','W'),default=('E',),help='Headings receiving the missing-door fixture')
    diagnostic.add_argument('--cut-inset-sweep',help='Comma-separated uniform native inset distances in metres; diagnostic fixtures only')
    diagnostic.add_argument('--cut-inset-presets',help='Comma-separated far:near:door native inset triples in metres; fixed-camera diagnostic fixtures only')
    diagnostic.add_argument('--native-exterior-control',action='store_true',help='Same-camera inside/native exterior/restored controls')
    diagnostic.add_argument('--body-lining-sweep',action='store_true',help='Same-camera body lining off/on/normal classes/restored controls')
    args=parser.parse_args()
    insets=[float(value) for value in args.cut_inset_sweep.split(',')] if args.cut_inset_sweep else []
    assert all(0<=value<=.3 for value in insets)
    try:
        presets=[tuple(float(value) for value in preset.split(':')) for preset in args.cut_inset_presets.split(',')] if args.cut_inset_presets else []
    except ValueError:
        parser.error('--cut-inset-presets requires numeric far:near:door triples')
    if any(len(preset)!=3 or not all(0<=value<=.3 for value in preset) for preset in presets):
        parser.error('--cut-inset-presets requires three distances from 0 to .3 metres per preset')
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    assert Path(args.output_name).name==args.output_name,'Output must be a child directory name'
    h=load('final-feature-tests');h.configure(run/args.output_name)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    furniture=load('final-furniture-tests');interior,tap,_=furniture.load_helpers()
    prior=h.lua('''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
return {height=o:getOption("wallHeight"):getValue(),camera=o:getOption("cameraWalls"):getValue()}''')
    if args.white_passenger:h.REPORT['appearanceFixture']='VanSeats native paint set to white; no user vehicle is loaded'
    if presets:h.REPORT['scope']='Independent native body-far/body-near/door inset presets; fixed-camera diagnostic render fixtures with restored zero, no user workflow acceptance'
    if args.height_choice:
        h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({args.height_choice});o:getOption("cameraWalls"):setValue(true);o:apply();return true''')
    try:
        names=['Base.Van','Base.StepVan','Base.85chevyStepVan']
        if args.all_bodies:
            families=[f['representative'] for f in json.loads((ROOT/'tools-src/vehicles/coverage.json').read_text())['families']]
            priority=['Base.90fordF350ambulance','Base.VanRadio','Base.86fordE150','Base.85chevyStepVan']
            names=priority+[name for name in families if name not in priority]
        if args.only:
            assert not set(args.only)-set(names),'Unknown selected body family'
            names=[name for name in names if name in args.only]
        for name in names:
            for heading in args.headings:
                label=name.split('.',1)[-1].lower()+'-'+heading.lower()
                h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true''')
                load('bed-tests').enter(h,name,heading)
                if args.white_passenger and name=='Base.VanSeats':
                    h.lua('MELensTest.vehicle:setColorHSV(0,0,1);return true')
                h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local P=MELens.Parts
-- Empty-furniture fixture exposes every part of the rear wall, floor and door.
for i in ipairs(pr.spots) do local part=P.spotPart(v,i)
if part then if part:getItemContainer() then part:getItemContainer():getItems():clear() end
part:setInventoryItem(nil);P.applyPiece(v,part) end end
local leaf=v:getPartById(pr.shell.entryDoor);assert(leaf:getInventoryItem());assert(not leaf:getDoor():isOpen())
P.syncShellDoors(v,pr);assert(P.shellDoorStates[v]==true)
local g=MELens.WalkGrids[pr.walkGrid];MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell*.65)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
                deadline=time.monotonic()+20
                while h.lua('return MELens.pathing(getPlayer()) or #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue>0'):
                    assert time.monotonic()<deadline,'rear door approach timed out';time.sleep(.1)
                length=h.lua('local g=MELens.WalkGrids[MELens.profileFor(MELensTest.vehicle).walkGrid];return #g.rows*g.cell')
                target=.75 if length>4 else .5
                for _ in range(8):
                    zoom=h.lua('return getCore():getZoom(0)')
                    if abs(zoom-target)<.02:break
                    h.lua(f'getCore():doZoomScroll(0,{1 if zoom<target else -1});return true');time.sleep(.2)
                if args.body_lining_sweep:
                    enabled=h.lua('return MELensRV.bodyLiningActive()')
                    expected=h.lua('return MELens.profileFor(MELensTest.vehicle).nativeBodyLining~=nil')
                    h.check(enabled==expected,'native body finish leaked across profile eligibility')
                    h.lua('MELensRV.clearBodyLining();return true')
                    h.REPORT['baselineFixture']='Body finish explicitly disabled before baseline and restored disabled; vehicle defaults are tested separately'
                time.sleep(.5);h.capture(label+'-closed-empty')
                if args.body_lining_sweep:
                    try:
                        h.lua('MELensRV.setBodyLining(.55,.57,.59);return true');time.sleep(.35)
                        h.capture(label+'-body-lining-finish')
                        h.lua('MELensRV.setBodyLiningDebug(true);return true');time.sleep(.35)
                        h.capture(label+'-body-lining-normal-classes')
                        h.lua('MELensRV.setBodyLiningDebugMode(2);return true');time.sleep(.35)
                        h.capture(label+'-body-lining-native-texel')
                        h.lua('MELensRV.setBodyLiningDebugMode(3);return true');time.sleep(.35)
                        h.capture(label+'-body-lining-native-part-mask')
                        h.lua('MELensRV.setBodyLiningDebugMode(4);return true');time.sleep(.35)
                        h.capture(label+'-body-lining-native-paint-alpha')
                    finally:h.lua('MELensRV.clearBodyLining();return true')
                    time.sleep(.35);h.capture(label+'-body-lining-restored-control')
                    h.record(label+'-body-lining-sweep',{},dict(diagnosticFixture=True,
                             profileDefaultEnabled=enabled,probeOverridesDefault=True,
                             normalClasses='RGB: native inward, native upward, backface'))
                    continue
                if insets or presets:
                    def inset(values):
                        call=('setNativeCutInsets('+','.join(str(value)+'/pr.mesh.scale' for value in values)
                              if presets else 'setNativeCutInset('+str(values[0])+'/pr.mesh.scale')
                        h.lua(f'''local pr=MELens.profileFor(MELensTest.vehicle)
local p=pr.cutPlanes[{args.height_choice or int(prior['height'])}]
MELensRV.{call},
-p[3]*(pr.mesh.lift-(pr.floorY+.015)/pr.mesh.scale));return true''')
                    sweep=presets or [(value,value,value) for value in insets]
                    tag='native-preset' if presets else 'native-inset'
                    try:
                        for values in sweep:
                            inset(values);time.sleep(.35)
                            suffix=('f%03d-n%03d-d%03dmm'%tuple(round(value*1000) for value in values)
                                    if presets else '%03dmm'%round(values[0]*1000))
                            h.capture(label+'-'+tag+'-'+suffix)
                    finally:inset((0,0,0))
                    time.sleep(.35);h.capture(label+'-'+tag+'-restored-control')
                    details=(dict(presetsMetres=[dict(zip(('far','near','door'),values)) for values in presets])
                             if presets else dict(insetsMetres=insets))
                    h.record(label+'-'+tag+'-sweep',{},dict(details,diagnosticFixture=True,sameCamera=True,restoredZero=True))
                    continue
                if args.native_exterior_control:
                    h.lua('MELensTest.vehicle:exit(getPlayer());return true');time.sleep(.6)
                    h.check(h.lua('return getPlayer():getVehicle()==nil'),'native exterior fixture did not exit')
                    h.capture(label+'-native-exterior-control')
                    h.lua('local v=MELensTest.vehicle;assert(v:enter(MELens.cabinSeat(v),getPlayer()));return true')
                    deadline=time.monotonic()+15
                    while not h.lua('return MELens.isStanding(getPlayer())'):
                        assert time.monotonic()<deadline,'restored standing fixture timeout';time.sleep(.1)
                    time.sleep(.5);h.capture(label+'-inside-restored-control')
                    h.record(label+'-native-exterior-control',{},dict(outsideAndRestored=True,diagnosticFixture=True))
                    continue
                if args.cap_isolation_only:
                    cap=h.lua('local pr=MELens.profileFor(MELensTest.vehicle);return pr.shell.models[3]')
                    h.check(cap.endswith('_bulkhead'),'selected shell model is not a cap')
                    h.lua(f'MELensRV.setKeepPlane({json.dumps(cap)},0,0,0,1);return true')
                    try:
                        time.sleep(.3);h.capture(label+'-cap-hidden')
                    finally:
                        h.lua(f'MELensRV.setKeepPlane({json.dumps(cap)},0,0,0,-1);return true')
                    time.sleep(.3);h.capture(label+'-cap-restored-control')
                    h.record(label+'-cap-isolation',dict(model=cap),dict(hiddenAndRestored=True,diagnosticFixture=True))
                    continue
                if heading in args.height_headings:
                    for choice,setting in ((1,'low'),(3,'high')):
                        h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({choice});o:apply();return true''');time.sleep(.35)
                        h.check(h.lua('return PZAPI.ModOptions:getOptions("RealVehicleInteriors"):getOption("wallHeight"):getValue()')==choice,'wall height fixture did not apply')
                        h.capture(label+'-closed-'+setting)
                    h.lua('''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue(2);o:getOption("cameraWalls"):setValue(false);o:apply();return true''');time.sleep(.35)
                    h.check(h.lua('return PZAPI.ModOptions:getOptions("RealVehicleInteriors"):getOption("cameraWalls"):getValue()') is False,'camera-wall fixture did not apply')
                    h.capture(label+'-closed-full-wall')
                    h.lua('''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("cameraWalls"):setValue(true);o:apply();return true''');time.sleep(.3)
                h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
v:getPartById(pr.shell.entryDoor):getDoor():setOpen(true);return true''');time.sleep(.3)
                h.check(h.lua('return MELens.Parts.shellDoorStates[MELensTest.vehicle]') is False,'open door still has a closed lining')
                h.capture(label+'-open-fixture')
                h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
v:getPartById(pr.shell.entryDoor):getDoor():setOpen(false);return true''');time.sleep(.3)
                h.check(h.lua('return MELens.Parts.shellDoorStates[MELensTest.vehicle]') is True,'reclosed door lacks lining')
                if heading in args.missing_headings:
                    h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
MELensTest.doorItem=v:getPartById(pr.shell.entryDoor):getInventoryItem()
v:getPartById(pr.shell.entryDoor):setInventoryItem(nil);return true''');time.sleep(.3)
                    h.check(h.lua('return MELens.Parts.shellDoorStates[MELensTest.vehicle]') is False,'missing door still has a lining')
                    h.capture(label+'-missing-fixture')
                    h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
v:getPartById(pr.shell.entryDoor):setInventoryItem(MELensTest.doorItem);return true''');time.sleep(.3)
                h.lua('MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return true')
                h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
                marker=h.lua('return MELensInteriorTest.positionAtExit()')
                interior.poll(h,lambda s:interior.idle(s) and s['interior']['standing']
                              and abs(s['interior']['debug'].get('x',999)-marker['x'])<=marker['halfX']
                              and abs(s['interior']['debug'].get('z',999)-marker['z'])<=marker['halfZ'],label=label+' exit approach')
                interior.interact_key(h,label+'-exit');interior.poll(h,lambda s:not s['interior']['inside'],label=label+' outside')
                h.record(label+'-door-lining',{},dict(closed=True,openHidden=True,reclosed=True,nativeEntryExit=True))
        h.REPORT['scope']=('Same-camera cap visibility fixtures with unchanged/restored controls; no door workflow acceptance.'
                           if args.cap_isolation_only else __doc__)
        if insets:h.REPORT['scope']='Native-only cut-plane inset sweep; fixed camera and restored zero control; render fixtures, no user workflow acceptance'
        if presets:h.REPORT['scope']='Independent native body-far/body-near/door inset presets; fixed-camera diagnostic render fixtures with restored zero, no user workflow acceptance'
        if args.native_exterior_control:h.REPORT['scope']='Fixed-camera native exterior and restored interior comparison; actor/seat fixtures, no door workflow acceptance'
        if args.body_lining_sweep:h.REPORT['scope']='Fixed-camera native body lining finish and normal-classification fixtures with unchanged/restored controls; no user workflow acceptance'
        h.REPORT['unverified']=['dedicated server','mechanics menu removal input']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error);return 1
    finally:
        h.lua(f'''MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true)
local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors")
o:getOption("wallHeight"):setValue({int(prior['height'])})
o:getOption("cameraWalls"):setValue({str(prior['camera']).lower()});o:apply();return true''')


if __name__=='__main__':raise SystemExit(main())
