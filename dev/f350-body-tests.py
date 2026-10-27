"""F350-only live-body comparison. Parent owns the isolated native process.

Entry uses production keyboard input; door states and cutaway choices are explicit
renderer fixtures. Saves use the production save API, followed by a new process.
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
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def main():
    phase = os.environ.get('RVI_F350_PHASE', 'prototype')
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h = load('final-feature-tests'); h.configure(run/'f350-body')
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    snapshot = load('interior-lifecycle-tests').SNAPSHOT
    def snap(): return h.lua(snapshot)
    def snap_id(sql_id):
        h.lua('''local it=getCell():getVehicles():iterator();MELensF350Check=nil
while it:hasNext() do local v=it:next();if v:getSqlId()=='''+str(int(sql_id))+''' then MELensF350Check=v;break end end
assert(MELensF350Check,"saved fixture SQL id not loaded");return true''')
        return h.lua(snapshot.replace('MELensLifecycle.vehicle','MELensF350Check'))
    def mark_utilities():
        h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
local g=v:getPartById(P.GENERATOR);g:getModData().on=false;g:getModData().fuel=7.25;g:setCondition(73)
local w=v:getPartById(P.WATER);w:getModData().water=11.5;w:getModData().tainted=true
v:getModData().MELensLightsOff=true
local c=P.spotPart(v,7):getItemContainer();assert(c:AddItem("Base.Screwdriver"));return true''')
    def camera():
        h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949);ISUIHandler.setVisibleAllUI(false);return true''')
        for _ in range(10):
            zoom=h.lua('return getCore():getZoom(0)')
            if abs(zoom-.5)<.02: break
            h.lua(f'getCore():doZoomScroll(0,{1 if zoom<.5 else -1});return true');time.sleep(.12)
    def options(height, near):
        h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors");o:getOption("wallHeight"):setValue({height})
o:getOption("cameraWalls"):setValue({str(near).lower()});o:apply();return true''');time.sleep(.4)
    def settle(predicate, reason, timeout=40):
        deadline=time.monotonic()+timeout
        while not h.lua('return ('+predicate+') and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0 and not MELens.pathing(getPlayer())'):
            h.check(time.monotonic()<deadline,reason);time.sleep(.15)
    def centre():
        h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell/2);return true''')
        settle('MELens.isStanding(getPlayer())','centre walk timed out')
    def reenter():
        # Earlier interrupted matrix runs can leave overlapping test fixtures.
        # Only the owned save's known test scripts/pad are eligible; preserve
        # the target by identity and record each removed fixture SQL id.
        removed=h.lua('''local target=MELensTest.vehicle;local doomed={};local ids={}
local names={['Base.90fordF350ambulance']=true,['Base.90fordF350SWAT']=true,
['Base.87fordF700box']=true,['Base.Van']=true}
local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next()
local occupied=false;for seat=0,v:getMaxPassengers()-1 do if v:getCharacter(seat) then occupied=true end end
if v~=target and v~=MELensF350Saved and names[v:getScriptName()] and math.abs(v:getX()-10809)<8
and math.abs(v:getY()-10140)<8 and not occupied then doomed[#doomed+1]=v end end
for _,v in ipairs(doomed) do ids[#ids+1]=v:getSqlId();v:permanentlyRemove() end;return ids''')
        if removed:h.REPORT.setdefault('removedOwnedOverlaps',[]).append(removed)
        h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local q=Vector3f.new()
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"outside"),q)
p:setX(q:x());p:setY(q:y());p:setLastX(q:x());p:setLastY(q:y())
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q)
p:faceLocation(q:x(),q:y());return true''')
        time.sleep(.5)
        key=int(h.lua('return getCore():getKey("Interact")'))
        h.lua(f'MEMCNativeLab.holdKey({key},200);return true')
        settle('MELens.isStanding(getPlayer()) and getPlayer():getVehicle()==MELensTest.vehicle','native re-entry timed out')
        centre()
    def collect(label):
        state = h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
return {active=MELensRV.nativeBodyWallsActive and MELensRV.nativeBodyWallsActive() or false,
flat=MELensRV.flatWheelArchActive and MELensRV.flatWheelArchActive() or false,
side=v:getPartById("DoorRearRight"):getDoor():isOpen(),rear=v:getPartById("DoorRear"):getDoor():isOpen(),
slots=#pr.spots,stamp=v:getModData().MELensFactoryLayout}''')
        h.REPORT.setdefault('frames',[]).append(dict(label=label,**state));h.capture(label)
        if os.environ.get('RVI_F350_FRONT_INSET')=='1':
            front=h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);local out={}
for _,i in ipairs({7,8}) do local s=pr.spots[i];out[#out+1]={index=i,x=s.x,z=s.z,wall=s.wall} end;return out''')
            front=h._sequence(front)
            h.check(len(front)==2 and all(s['wall']=='front' and abs(s['z']+.46)<.0001 for s in front),
                    'front furniture correction absent '+label)
            h.REPORT['frontSpots']=front
        native_expected = phase not in ('baseline', 'checkpoint', 'fallback', 'legacy')
        h.check(state['active'] == native_expected, 'feature scope mismatch '+label)
        flat_expected=native_expected and os.environ.get('RVI_F350_FLAT')=='1'
        h.check(state['flat']==flat_expected,'flat wheel scope mismatch '+label)
        if os.environ.get('RVI_F350_FLAT')=='1' and phase not in ('checkpoint','legacy'):
            bindings=h.lua('''local p=MELensTest.vehicle:getPartById(MELens.Parts.SHELL)
return {floor=MELensRV.isPartModelVisible(p,"MELensShell1"),covers=MELensRV.isPartModelVisible(p,"MELensShell8"),
infill=MELensRV.isPartModelVisible(p,"MELensShell9"),wall=MELensRV.isPartModelVisible(p,"MELensShell10")}''')
            h.check(bindings==dict(floor=True,covers=not flat_expected,infill=flat_expected,wall=flat_expected),'wheel surface bindings mismatch '+label+str(bindings))
            h.REPORT['frames'][-1]['wheelSurfaces']=bindings
            if flat_expected:
                counts={k:int(v) for k,v in (pair.split('=',1) for pair in h.lua('return MELensRV.flatWheelArchInfo()').split(';'))}
                h.check(counts['wheels']>0 and counts['interiors']>0,'reciprocal wheel mask draw path inactive')
                h.REPORT['wheelMask']=counts
        if native_expected:
            counts={k:int(v) for k,v in (pair.split('=',1) for pair in h.lua('return MELensRV.nativeBodyWallsInfo()').split(';'))}
            h.REPORT['culling']=counts
            h.check(counts['draws']>0 and counts['stateErrors']==0,'native mesh culling hook is inactive or leaks state')
    try:
        if phase == 'checkpoint':
            sql_id=int(os.environ['RVI_F350_SQL'])
            h.lua('''local it=getCell():getVehicles():iterator();local v;while it:hasNext() do local c=it:next()
if c:getSqlId()=='''+str(sql_id)+''' then v=c;break end end
assert(v and v:getScriptName()=="Base.90fordF350ambulance","checkpoint F350 not loaded")
MELensTest={vehicle=v,all={}};MELensLifecycle={vehicle=v};return true''')
            before=snap();reenter();camera();collect('stable-old-save-checkpoint')
            h.check(snap()==before,'checkpoint entry changed saved state')
            h.lua('GameWindow.save(true);return true')
            committed={'world':h.lua('return getWorld():getWorld()'),'state':snap()}
            (h.OUTPUT/'committed.json').write_text(json.dumps(committed,indent=2))
            h.REPORT['saved']=committed
            h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
        source=os.environ.get('RVI_F350_SOURCE')
        if source:
            expected=json.loads((ROOT/'build/rv'/source/'f350-body/committed.json').read_text())
            h.lua('''local v;local it=getCell():getVehicles():iterator();while it:hasNext() do local candidate=it:next()
if candidate:getSqlId()=='''+str(expected['state']['sqlId'])+''' then v=candidate;break end end
assert(v,"saved F350 SQL id not loaded");assert(v:getScriptName()=="Base.90fordF350ambulance")
MELensTest={vehicle=v,all={}};MELensLifecycle={vehicle=v};return true''')
            actual=snap();h.check(actual==expected['state'],'upgrade/cold load changed committed state')
            h.REPORT['coldLoad']={'source':source,'identical':True,'state':actual}
            if expected.get('companion'):
                companion=snap_id(expected['companion']['sqlId'])
                h.check(companion==expected['companion'],'cold load changed marked fixture IDs/loot/utilities')
                h.REPORT['markedFixtureColdLoad']={'identical':True,'state':companion}
            if not h.lua('return getPlayer():getVehicle()==MELensTest.vehicle and MELens.isStanding(getPlayer())'):reenter()
            centre();camera()
            collect('cold-load-'+phase)
            if phase in ('reload', 'prototype') and os.environ.get('RVI_F350_CONTROLS') == '1':
                h.lua('MELensF350Saved=MELensTest.vehicle;MELensTest={all={}};return true')
                try:
                    for script,label in (('Base.90fordF350SWAT','swat'),('Base.87fordF700box','f700'),('Base.Van','van')):
                        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();p:setX(10830.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
                        load('bed-tests').enter(h,script,'N')
                        h.check(h.lua('return getPlayer():getVehicle()==MELensTest.vehicle'),'control entered another vehicle')
                        h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell/2);return true''')
                        deadline=time.monotonic()+30
                        while h.lua('return MELens.pathing(getPlayer())'):
                            h.check(time.monotonic()<deadline,'control aisle walk timed out');time.sleep(.1)
                        options(2,False);camera();h.capture('control-'+label)
                        state=h.lua('''return {script=MELensTest.vehicle:getScriptName(),
native=MELensRV.nativeBodyWallsActive(),flat=MELensRV.flatWheelArchActive and MELensRV.flatWheelArchActive() or false,
profile=MELens.profileFor(MELensTest.vehicle).nativeBodyWalls or false}''')
                        h.check(not state['native'] and not state['flat'] and not state['profile'],'F350 experiment leaked into '+label)
                        h.REPORT.setdefault('controls',[]).append(state)
                finally:
                    h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
local old=MELensTest.vehicle;if old and old~=MELensF350Saved then old:permanentlyRemove() end
MELensTest={vehicle=MELensF350Saved,all={}};MELensLifecycle={vehicle=MELensF350Saved}
MELensMedia.cameraOff();return true''')
                    reenter()
                h.check(snap()==expected['state'],'vehicle controls changed preserved F350 state')
                camera();collect('returned-f350-after-controls')
            if phase == 'diagnostic':
                options(3,False)
                before=snap()
                for ids,label in (([], 'closed-control'),(['WindowRearRight','WindshieldRear'],'no-glass'),
                                  (['DoorRearRight'],'no-side-door'),(['DoorRear'],'no-rear-door'),
                                  (['DoorRearRight','DoorRear'],'no-doors')):
                    h.lua('MELensTest.hidden={};local v=MELensTest.vehicle;for _,id in ipairs({'+','.join('"'+i+'"' for i in ids)+'''}) do
local part=v:getPartById(id);MELensTest.hidden[id]=part:getInventoryItem();part:setInventoryItem(nil) end;return true''')
                    time.sleep(.5);collect('isolate-'+label)
                    h.lua('''for id,item in pairs(MELensTest.hidden) do MELensTest.vehicle:getPartById(id):setInventoryItem(item) end;return true''')
                h.check(snap()==before,'diagnostic fixtures changed inventory or utilities')
                h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
            if phase in ('reload', 'fallback', 'legacy'):
                h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
            if phase == 'arch-diagnostic':
                h.lua('MELensDiagnosticSaved=MELensTest.vehicle;return true')
                try:
                    for heading in ('E','S'):
                        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();p:setX(10813.5);p:setY(10120.5);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
                        load('bed-tests').enter(h,'Base.90fordF350ambulance',heading)
                        centre();options(3,False);camera();h.capture(heading.lower()+'-isolate-control')
                        for aliases,label in ((['mesh:f350_body'],'body'),
                                (['MELensShell_fleet_f350ambulance_support'],'support'),
                                (['MELensShell_fleet_f350ambulance_support_seals'],'seals'),
                                (['MELensShell_fleet_f350ambulance_wheel_wall'],'arch-wall'),
                                (['90fordF350ambulanceWheels'],'rear-tyres'),
                                (['MELensRV_stretcher'],'stretcher')):
                            for alias in aliases: h.lua('MELensRV.setKeepPlane('+json.dumps(alias)+',0,0,0,1);return true')
                            time.sleep(.4);h.capture(heading.lower()+'-isolate-no-'+label)
                            for alias in aliases: h.lua('MELensRV.setKeepPlane('+json.dumps(alias)+',0,0,0,-1);return true')
                            time.sleep(.3)
                finally:
                    h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
local v=MELensDiagnosticSaved;MELensTest={vehicle=v,all={}};MELensLifecycle={vehicle=v};return true''')
                    reenter();camera();collect('diagnostic-restored-original')
                h.check(snap()==expected['state'],'arch visibility fixtures changed saved state')
                h.lua('GameWindow.save(true);return true')
                (h.OUTPUT/'committed.json').write_text(json.dumps(expected,indent=2))
                h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
        if source:
            h.lua('''MELensF350Saved=MELensTest.vehicle;local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensTest={all={}};return true''')
        pad=h.lua('''local survey={};local chosen
for _,pad in ipairs({{10789,10140},{10789,10160},{10809,10160},{10789,10120},{10809,10180}}) do
local missing,blocked=0,0
for x=pad[1]-7,pad[1]+7 do for y=pad[2]-7,pad[2]+7 do local sq=getCell():getGridSquare(x,y,0)
if not sq then missing=missing+1 else for i=1,sq:getObjects():size()-1 do
local s=sq:getObjects():get(i):getSprite();local n=s and s:getName() or '?'
if not n:find('^vegetation_') and not n:find('^e_') and not n:find('^f_bushes')
and not n:find('^d_plants') and not n:find('^d_generic') and not n:find('^boulders') then blocked=blocked+1 end end end end end
local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next()
if math.abs(v:getX()-pad[1])<9 and math.abs(v:getY()-pad[2])<9 then blocked=blocked+1 end end
survey[#survey+1]={x=pad[1],y=pad[2],missing=missing,blocked=blocked}
if not chosen and missing==0 and blocked==0 then chosen={x=pad[1],y=pad[2]} end end
assert(chosen,'no clear loaded matrix pad');return {chosen=chosen,survey=survey}''')
        h.REPORT['matrixPad']=pad
        px,py=pad['chosen']['x']+4.5,pad['chosen']['y']+.5
        for heading in ('E','N','S','W'):
            h.lua(f'''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();p:setX({px});p:setY({py});p:setLastX(p:getX());p:setLastY(p:getY());return true''')
            load('bed-tests').enter(h,'Base.90fordF350ambulance',heading)
            h.lua('''MELensLifecycle={vehicle=MELensTest.vehicle};MELens.walkTo(getPlayer(),0,-1.9)
local v=MELensTest.vehicle
for _,id in ipairs({"DoorRearRight","DoorRear"}) do local part=v:getPartById(id)
part:getDoor():setOpen(false);v:playPartAnim(part,"Closed") end;return true''')
            deadline=time.monotonic()+20
            while h.lua('return MELens.pathing(getPlayer())'):
                h.check(time.monotonic()<deadline,'walk fixture timeout');time.sleep(.1)
            camera()
            before=snap()
            for height in (1,2,3):
                options(height,False);collect(heading.lower()+'-closed-height-'+str(height))
            options(2,True);collect(heading.lower()+'-closed-camera-cut')
            if phase!='baseline':
                options(3,False)
                for side,rear,label in ((True,False,'side-open'),(False,True,'rear-open'),(True,True,'both-open'),(False,False,'restored')):
                    h.lua(f'''local v=MELensTest.vehicle
for _,d in ipairs({{{{"DoorRearRight",{str(side).lower()}}},{{"DoorRear",{str(rear).lower()}}}}}) do
local part=v:getPartById(d[1]);part:getDoor():setOpen(d[2]);v:playPartAnim(part,d[2] and "Opened" or "Closed") end;return true''')
                    time.sleep(.4);collect(heading.lower()+'-'+label)
                for door,label in (('DoorRearRight','side-missing'),('DoorRear','rear-missing')):
                    h.lua(f'''local part=MELensTest.vehicle:getPartById("{door}")
MELensTest.removedDoor=part:getInventoryItem();part:setInventoryItem(nil);return true''')
                    time.sleep(.4);collect(heading.lower()+'-'+label)
                    h.lua(f'''MELensTest.vehicle:getPartById("{door}"):setInventoryItem(MELensTest.removedDoor);return true''')
                    time.sleep(.4);collect(heading.lower()+'-'+label+'-restored')
            h.check(snap()==before,'cutaway/door fixtures changed inventory or utilities')
            if os.environ.get('RVI_F350_FLAT')=='1':
                h.lua('''local p=getPlayer();local m=MELens.profileFor(MELensTest.vehicle).exitMarker
MELens.walkTo(p,m.x,m.z);return true''')
                settle('MELens.isStanding(getPlayer())','exit-marker approach timed out')
                key=int(h.lua('return getCore():getKey("Interact")'))
                h.lua(f'MEMCNativeLab.holdKey({key},200);return true')
                settle('getPlayer():getVehicle()==nil','native exit timed out')
                time.sleep(.4);camera();h.capture(heading.lower()+'-exterior-after-exit')
                h.check(h.lua('return not MELensRV.nativeBodyWallsActive() and not MELensRV.flatWheelArchActive()'),'experiment retained after exit')
                reenter();camera();collect(heading.lower()+'-interior-after-reentry')
                h.check(snap()==before,'entry/exit changed inventory or utilities')
        if source:
            # Keep a separate marked fixture for a meaningful nonzero utility
            # reload check while leaving every old-save value untouched.
            mark_utilities();time.sleep(.3);companion=snap()
            h.REPORT['markedFixtureSaved']=companion
            h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensTest={vehicle=MELensF350Saved,all={}};MELensLifecycle={vehicle=MELensF350Saved};return true''')
            reenter();camera();collect('matrix-restored-original')
            h.check(snap()==expected['state'],'matrix changed original saved F350 state')
        else:
            # Known non-default values before the first old/new process boundary.
            mark_utilities()
        time.sleep(.3);h.lua('GameWindow.save(true);return true')
        committed={'world':h.lua('return getWorld():getWorld()'),'state':snap()}
        if source:committed['companion']=companion
        (h.OUTPUT/'committed.json').write_text(json.dumps(committed,indent=2))
        h.REPORT['saved']=committed;h.REPORT['scope']=__doc__
        h.REPORT['nativeInput']=True
        h.REPORT['unverified']=['dedicated multiplayer','mechanics-menu door input','human acceptance']
        h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
    except Exception:
        h.write_report('failed',traceback.format_exc());raise

if __name__=='__main__':raise SystemExit(main())
