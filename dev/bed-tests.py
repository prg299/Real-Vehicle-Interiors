"""Native bed transition and sleep-dialog checks in a guarded, parent-owned game."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def enter(h, vehicle, heading, walk_approach=True):
    assert not h.lua('return getPlayer():getVehicle()~=nil'), 'start outside'
    spawn = (ROOT/'dev/lua/spawn_one.lua').read_text().replace('NAME',vehicle)
    spawn = spawn.replace('tonumber("7")','tonumber("-4")').replace('local HEADING = "E"',f'local HEADING = "{heading}"')
    h.lua(spawn)
    if not walk_approach:time.sleep(1)
    h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local q=Vector3f.new()
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"outside"),q)
p:setX(q:x());p:setY(q:y());p:setLastX(q:x());p:setLastY(q:y())
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q)
p:faceLocation(q:x(),q:y());ISUIHandler.setVisibleAllUI(true);return true''')
    approach=h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local q=Vector3f.new()
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q)
local dx,dy=q:x()-p:getX(),q:y()-p:getY();local sx,sy=dx-dy,dx+dy
return getCore():getKey(math.abs(sx)>math.abs(sy) and (sx>0 and "Right" or "Left") or (sy>0 and "Backward" or "Forward"))''')
    if walk_approach:h.lua(f'MEMCNativeLab.holdKey({int(approach)},150);return true')
    time.sleep(.6)
    # The approach updates the game's nearby-vehicle cache, but its final point
    # can fall outside a small trailer's native door-use area. Re-centre this
    # setup fixture before testing Interact; do not call an entry handler.
    usable=h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local part=v:getUseablePart(p)
return part and part:getId()==MELens.profileFor(v).standing.door or false''')
    if not usable:
        position=h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local q=Vector3f.new()
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"outside"),q)
p:setX(q:x());p:setY(q:y());p:setLastX(q:x());p:setLastY(q:y());return {x=q:x(),y=q:y()}''')
        h.REPORT.setdefault('entryPositionFixtures',[]).append(dict(vehicle=vehicle,**position))
        time.sleep(.5)
    key=int(h.lua('return getCore():getKey("Interact")'))
    h.lua(f'MEMCNativeLab.holdKey({key},200);return true')
    deadline=time.monotonic()+40
    while not h.lua('return MELens.isStanding(getPlayer()) and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0'):
        assert time.monotonic()<deadline,'native entry timed out'
        time.sleep(.2)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',default=os.environ.get('RVI_CAPTURE_RUN'))
    p.add_argument('--vehicle',default='Base.Trailer54FlyingCloud22')
    p.add_argument('--heading',default='E',choices=['N','E','S','W'])
    p.add_argument('--label',default='cloud-e')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--sex',choices=['male','female'])
    p.add_argument('--bed-index',type=int,default=1)
    a=p.parse_args()
    logical_run=ROOT/'build/rv'/a.run
    assert logical_run.parent==ROOT/'build/rv', 'run must be one owned folder name'
    run=logical_run.resolve()
    artifact_root=(Path(os.environ['LOCALAPPDATA'])/'RVI-TestArtifacts').resolve()
    assert run.is_relative_to(ROOT/'build/rv') or run.is_relative_to(artifact_root)
    interior=load('final-interior-tests')
    tap,h=interior.load_helpers()
    h.configure(output=run/a.label)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    def sample_until(case,predicate,timeout=35):
        seen=[];end=time.monotonic()+timeout;next_shot=0
        while time.monotonic()<end:
            s=interior.read_state(h)
            seen.append(s)
            if time.monotonic()>=next_shot:
                h.capture(f'{a.label}-{case}-{len(seen):03}')
                next_shot=time.monotonic()+.3
            if time.monotonic()>=h._input_release and predicate(s):
                h.REPORT.setdefault('transitions',{})[case]=seen
                return s
            time.sleep(.12)
        h.REPORT.setdefault('transitions',{})[case]=seen
        raise AssertionError(f'Timeout {case}: {json.dumps(s)}')
    def check_contact(state):
        bed=state['bedGeometry']
        wall={'front':((-1,0),(0,-1)),'back':((1,0),(0,1)),
              'left':((0,1),(-1,0)),'right':((0,-1),(1,0))}[bed['wall']]
        turn=state['bedTurn']
        bones={entry.split(':')[0]:[float(v) for v in entry.split(':')[1].split(',')]
               for entry in state['bones'].strip(';').split(';')}
        clearances={}
        for name,(x,y,z) in bones.items():
            px=state['player']['passengerX']+1.5*(math.cos(turn)*x+math.sin(turn)*z)
            pz=state['player']['passengerZ']+1.5*(math.sin(turn)*x-math.cos(turn)*z)
            along=(px-bed['x'])*wall[0][0]+(pz-bed['z'])*wall[0][1]
            depth=(px-bed['x'])*wall[1][0]+(pz-bed['z'])*wall[1][1]
            h.check(abs(along)<.85 and -.1<depth<.65,f'{name} outside mattress footprint: {along},{depth}')
            clearances[name]=state['passengerY']-bed['modelOffsetY']+1.5*y-bed['top']
        h.check(.02<clearances['Bip01_Pelvis']<.23,f'pelvis height outside bed clip range: {clearances}')
        return clearances
    try:
        if a.sex:
            female=str(a.sex=='female').lower()
            h.lua(f'local p=getPlayer();p:setFemale({female});p:getDescriptor():setFemale({female});p:resetModel();return true')
        if not a.resume: enter(h,a.vehicle,a.heading)
        # An unattached trailer can roll on the field's slope. Park only this
        # owned animation fixture so the native moving-vehicle sleep rule does
        # not turn this into an unrelated vehicle-physics test.
        h.lua('getPlayer():getVehicle():setPhysicsActive(false);return true')
        time.sleep(.5)
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text())
        h.lua(interior.FIXTURE)
        h.lua(f'MELensBedTestSpotIndex={a.bed_index};return true')
        h.lua('''local old=MELensInteriorTest.snapshot
function MELensInteriorTest.snapshot()
local r=old();local p=getPlayer();local d=getPlayerData(0).vehicleSleepModal
r.asleep=p:isAsleep();r.bedPhase=p:getVariableString("MELensBed")
r.female=p:isFemale();r.alpha=p:getAlpha(0)
r.bedFinished=p:getVariableBoolean("MELensBedFinished_"..(r.bedPhase or ""))
r.side=p:getVariableString("MELensBedSide")
r.entryProgress=MELensRV.animationProgress(p,"Bob_GetInBed_"..(r.side or ""))
r.exitProgress=MELensRV.animationProgress(p,"Bob_GetOutBed"..(r.side or ""))
r.bones=MEMCNativeLab.animationBones()
local v=p:getVehicle()
if v then
local q=Vector3f.new();v:getPassengerLocalPos(v:getSeat(p),q);r.passengerY=q:y()
local bs=MELens.Bed.states[p];r.bedTurn=bs and (bs.phase=="Enter" and bs.entryTurn or bs.place.turn)
local P=MELens.Parts;local pr=MELens.profileFor(v);local spot=pr.spots[MELensBedTestSpotIndex]
local o=v:getScript():getModel():getOffset();local origin=Vector3f.new();local base=v:getWorldPos(0,0,0,origin):z()
local piece=P.pieceAt(P.spotPart(v,MELensBedTestSpotIndex));local mattressTop=P.kit(piece).height-.02
r.bedGeometry={x=spot.x,z=spot.z,wall=spot.wall,top=pr.floorY+mattressTop,modelOffsetY=o:y()}
r.bedCorners={}
for i,pair in ipairs({{-.75,0},{.75,0},{.75,.55},{-.75,.55}}) do
local x,z=P.spotPoint(spot,pair[1],pair[2]);local h=pr.floorY+mattressTop
v:getWorldPos(o:x()+x,o:y()+h,o:z()+z,q)
local sx,sy=ISCoordConversion.ToScreen(q:x(),q:y(),base+(o:y()+h)/2.44949)
r.bedCorners[i]={x=sx/getCore():getZoom(0),y=sy/getCore():getZoom(0)}
end
end
r.sleepDialog=d~=nil and d:isVisible()
if r.sleepDialog then
r.sleepYes={x=d:getX()+d.yes:getX()+d.yes:getWidth()/2,y=d:getY()+d.yes:getY()+d.yes:getHeight()/2}
r.sleepNo={x=d:getX()+d.no:getX()+d.no:getWidth()/2,y=d:getY()+d.no:getY()+d.no:getHeight()/2}
end
return r end
return true''')
        rest=h.lua('return getText("ContextMenu_Rest")')
        point=h.lua(f'return MELensInteriorTest.point({a.bed_index})')
        before=interior.choose(h,tap,point,[point['header'],rest],'bed-rest')
        after=sample_until('get-in',lambda s:s.get('bedPhase')=='Awake')
        h.check(any(s.get('bedPhase')=='Enter' and s.get('entryProgress',0)>0 for s in h.REPORT['transitions']['get-in']),'get-in clip did not play')
        h.check(all(s.get('alpha',1)>.05 for s in h.REPORT['transitions']['get-in']),'bed entry hid the character')
        h.record('bed-rest-entry',before,after,uiHandlersInvokedDirectly=False)
        time.sleep(.5);h.capture(f'{a.label}-resting')
        h.REPORT['restingPose']=interior.read_state(h)
        h.REPORT['restingBoneClearances']=check_contact(h.REPORT['restingPose'])
        interior.interact_key(h,'get-up-from-bed')
        after=sample_until('get-out',lambda s:s['interior']['standing'])
        h.check(any(s.get('bedPhase')=='Exit' and s.get('exitProgress',0)>0 for s in h.REPORT['transitions']['get-out']),'get-out clip did not play')
        h.lua('''local p=getPlayer();p:setGodMod(false);p:getStats():set(CharacterStat.FATIGUE,0.8)
p:getStats():set(CharacterStat.PANIC,0);p:setLastHourSleeped(-100);return true''')
        sleep=h.lua('return getText("ContextMenu_Sleep")')
        point=h.lua(f'return MELensInteriorTest.point({a.bed_index})')
        before=interior.choose(h,tap,point,[point['header'],sleep],'sleep-cancel')
        dialog=interior.poll(h,lambda s:s.get('sleepDialog'),label='normal sleep confirmation')
        h.capture(f'{a.label}-sleep-confirm')
        tap.native_click(h,dialog['sleepNo']['x'],dialog['sleepNo']['y'],'cancel-sleep')
        after=interior.poll(h,lambda s:not s.get('sleepDialog') and not s['asleep'],label='sleep cancelled')
        h.check(after['interior']['standing'],'cancelling sleep moved the player onto the bed')
        h.record('sleep-cancel',before,after,nativeDialog=True,uiHandlersInvokedDirectly=False)
        point=h.lua(f'return MELensInteriorTest.point({a.bed_index})')
        before=interior.choose(h,tap,point,[point['header'],sleep],'sleep-accept')
        dialog=interior.poll(h,lambda s:s.get('sleepDialog'),label='second sleep confirmation')
        tap.native_click(h,dialog['sleepYes']['x'],dialog['sleepYes']['y'],'confirm-sleep')
        after=sample_until('go-to-sleep',lambda s:s['asleep'] and not s.get('sleepDialog'),timeout=45)
        phases={s.get('bedPhase') for s in h.REPORT['transitions']['go-to-sleep']}
        h.check({'Enter','Sleep','Asleep'}.issubset(phases),f'missing native sleep stages: {phases}')
        h.record('sleep-accept',before,after,nativeDialog=True,uiHandlersInvokedDirectly=False)
        h.REPORT['asleepPose']=after
        h.REPORT['asleepBoneClearances']=check_contact(after)
        h.lua('getPlayer():forceAwake();return true') # cleanup; natural overnight progression is separate
        sample_until('wake',lambda s:s.get('bedPhase')=='Awake')
        interior.interact_key(h,'get-up-after-sleep')
        sample_until('wake-get-out',lambda s:s['interior']['standing'])
        marker=h.lua('return MELensInteriorTest.positionAtExit()')
        interior.poll(h,lambda s:interior.idle(s) and abs(s['interior']['debug'].get('x',999)-marker['x'])<.05
                      and abs(s['interior']['debug'].get('z',999)-marker['z'])<.05,label='exit fixture')
        interior.interact_key(h,'exit-after-bed-use')
        interior.poll(h,lambda s:not s['interior']['inside'],label='outside after bed use')
        h.REPORT['unverified']=['multiplayer','natural overnight progression','human acceptance']
        print(h.write_report('passed'),flush=True)
        return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        print(h.write_report('failed',error),flush=True)
        return 1

if __name__=='__main__': raise SystemExit(main())
