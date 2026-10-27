"""Four native views of one saved F350. Rotation/camera are presentation fixtures.

Entry uses normal Interact keyboard dispatch. Preserve fittings, loot, utilities,
door state and original angles; never save the temporary photography poses.
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


def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h=load('final-feature-tests');h.configure(run/'showcase')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    expected=json.loads((ROOT/'build/rv'/os.environ['RVI_F350_SOURCE']/'f350-body/committed.json').read_text())
    snapshot=load('interior-lifecycle-tests').SNAPSHOT
    def snap():return h.lua(snapshot)
    def wait_inside():
        deadline=time.monotonic()+40
        while not h.lua('return MELens.isStanding(getPlayer()) and getPlayer():getVehicle()==MELensPhoto.vehicle and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0'):
            h.check(time.monotonic()<deadline,'showcase keyboard entry timed out');time.sleep(.15)
    try:
        h.lua('''local it=getCell():getVehicles():iterator();local primary,target
while it:hasNext() do local v=it:next();if v:getSqlId()=='''+str(expected['state']['sqlId'])+''' then primary=v end
if v:getSqlId()=='''+str(expected['companion']['sqlId'])+''' then target=v end end
assert(primary and target,'saved showcase identities not loaded')
MELensPhoto={vehicle=target,primary=primary,angles={target:getAngleX(),target:getAngleY(),target:getAngleZ()},doors={}}
for _,id in ipairs({'DoorRearRight','DoorRear'}) do MELensPhoto.doors[id]=target:getPartById(id):getDoor():isOpen() end
MELensLifecycle={vehicle=primary};return true''')
        h.check(snap()==expected['state'],'original vehicle state changed before showcase')
        h.lua('MELensLifecycle.vehicle=MELensPhoto.vehicle;return true')
        h.check(snap()==expected['companion'],'marked vehicle state changed before showcase')
        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
local v=MELensPhoto.vehicle;local q=Vector3f.new();v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),'outside'),q)
p:setX(q:x());p:setY(q:y());p:setLastX(q:x());p:setLastY(q:y())
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),'inside'),q);p:faceLocation(q:x(),q:y());return true''')
        time.sleep(.6)
        key=int(h.lua('return getCore():getKey("Interact")'));h.lua(f'MEMCNativeLab.holdKey({key},200);return true');wait_inside()
        h.lua('''local v=MELensPhoto.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell/2)
for _,id in ipairs({'DoorRearRight','DoorRear'}) do local part=v:getPartById(id);part:getDoor():setOpen(false);v:playPartAnim(part,'Closed') end
local o=PZAPI.ModOptions:getOptions('RealVehicleInteriors');o:getOption('wallHeight'):setValue(3);o:getOption('cameraWalls'):setValue(false);o:apply()
ISUIHandler.setVisibleAllUI(false);return true''')
        deadline=time.monotonic()+30
        while h.lua('return MELens.pathing(getPlayer())'):
            h.check(time.monotonic()<deadline,'showcase aisle approach timed out');time.sleep(.1)
        # Wider than the interior review camera, centred on the whole native body.
        for _ in range(12):
            zoom=h.lua('return getCore():getZoom(0)')
            if zoom>=.625-.01:break
            h.lua('getCore():doZoomScroll(0,1);return true');time.sleep(.25)
        for yaw in (0,90,180,270):
            h.lua(f'MELensPhoto.vehicle:setAngles(0,{yaw},0);return true');time.sleep(.8)
            pose=h.lua('''local v=MELensPhoto.vehicle;local pr=MELens.profileFor(v);local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()-.984,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
return {sql=v:getSqlId(),yaw=v:getAngleY(),zoom=getCore():getZoom(0),front1=pr.spots[7].z,front2=pr.spots[8].z}''')
            time.sleep(.3);h.capture('angle-'+str(yaw));h.REPORT.setdefault('poses',[]).append(pose)
            h.check(abs(pose['front1']+.46)<.0001 and abs(pose['front2']+.46)<.0001,'showcase uses stale front spots')
            h.check(snap()==expected['companion'],'photography changed marked vehicle contents')
        # A side-on view exposes the doorway instead of foreshortening it behind
        # the open leaf. Capture the diagonal headings too; no door geometry or
        # opening angle is changed for these presentation fixtures.
        h.lua('''local v=MELensPhoto.vehicle;local part=v:getPartById('DoorRearRight')
part:getDoor():setOpen(true);v:playPartAnim(part,'Opened');return true''');time.sleep(.6)
        for _ in range(12):
            if h.lua('return getCore():getZoom(0)')<=.5+.01:break
            h.lua('getCore():doZoomScroll(0,-1);return true');time.sleep(.25)
        for yaw in (0,45,90,135,180,225,270,315):
            h.lua(f'MELensPhoto.vehicle:setAngles(0,{yaw},0);return true');time.sleep(.8)
            h.lua('''local v=MELensPhoto.vehicle;local pr=MELens.profileFor(v);local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x()-1,o:y()+pr.floorY,o:z()-1.347,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949);return true''')
            time.sleep(.3);h.capture('door-open-angle-'+str(yaw))
            h.check(snap()==expected['companion'],'doorway photography changed marked vehicle contents')
        h.REPORT['savedIdentitiesPreserved']=True;h.REPORT['nativeInput']=True
        h.REPORT['scope']=__doc__;h.write_report('passed')
    except Exception:
        h.write_report('failed',traceback.format_exc());raise
    finally:
        h.lua('''if MELensPhoto then local v=MELensPhoto.vehicle;local a=MELensPhoto.angles;v:setAngles(a[1],a[2],a[3])
for id,opened in pairs(MELensPhoto.doors) do local part=v:getPartById(id);part:getDoor():setOpen(opened);v:playPartAnim(part,opened and 'Opened' or 'Closed') end end;return true''')
        (run/'request.json').write_text('{"action":"stop"}')
    return 0


if __name__=='__main__':raise SystemExit(main())
