"""Native SP release checks: steady travel, stop, aim, collision and furnished bed UI."""
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    _,h=load('final-interior-tests').load_helpers()
    h.configure(run/'movement');h.SCREENS=run/'home/Zomboid/Screenshots'
    report={'scope':__doc__,'trials':{},'passed':False}
    path=run/'movement-release.json'
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    def wait(code,timeout=30):
        end=time.monotonic()+timeout
        while not h.lua(code):
            if time.monotonic()>=end:
                report['timeoutState']=h.lua('local p=getPlayer();return {state=MELens.debugState(),turn=MELensDevBones.turning(p),tracks=MELensDevBones.tracks(p),queue=#ISTimedActionQueue.getTimedActionQueue(p).queue,busy=p:isPerformingAnAction(),aiming=p:isAiming(),nativeDistance=MELensRV.nativeMovementDistance(p)}')
                h.capture('timeout-state');save()
                raise AssertionError('native wait timed out: '+code)
            time.sleep(.12)
    def key(name):return int(h.lua('return getCore():getKey('+json.dumps(name)+')'))
    def trial(label,codes,duration=2100,steady_start=1400,steady_end=2000):
        hold=';'.join(f'MEMCNativeLab.holdKey({int(k)},{duration})' for k in codes)
        h.lua('RVI_MoveProbe.rows={};RVI_MoveProbe.start=getTimestampMs();RVI_MoveProbe.active=true;'+hold+';return true')
        # PNG capture blocks the render thread. Keep it outside the timed input
        # and stop interval so it cannot create a catch-up spike in the samples.
        time.sleep((duration+1000)/1000)
        rows=h._sequence(h.lua('MEMCNativeLab.releaseKeys();RVI_MoveProbe.active=false;return RVI_MoveProbe.rows'))
        assert rows,label+': no native samples'
        for r in rows:r['tracks']=json.loads(r['tracks'])
        steady=[r for r in rows if steady_start<=r['t']<=steady_end]
        assert len(steady)>5,label+': insufficient steady samples'
        first,last=steady[0],steady[-1]
        speed=math.hypot(last['x']-first['x'],last['y']-first['y'])/((last['t']-first['t'])/1000)
        stop=min(rows,key=lambda r:abs(r['t']-duration))
        tail=math.hypot(rows[-1]['x']-stop['x'],rows[-1]['y']-stop['y'])
        result={'samples':rows,'steadyWorldSpeed':speed,'stopTailDistance':tail,'keys':codes,'durationMs':duration,
                'steadyWindow':[steady_start,steady_end]}
        report['trials'][label]=result;save()
        assert all(r['alpha']==1 and r['targetAlpha']==1 for r in rows),label+': opacity changed'
        assert all(r.get('walkable',True) for r in rows),label+': crossed a wall/furniture'
        if label.endswith('-run'):
            assert all(any(t['name']=='Bob_Run' and t['blend']>.05 for t in r['tracks'])
                       and not any('IdleToRun' in t['name'] and t['blend']>.01 for t in r['tracks'])
                       for r in steady),label+': native run-up did not finish before measurement'
        h.capture(label+'-stopped')
        print('MOVEMENT_TRIAL',label,'speed',round(speed,4),'stop',round(tail,4),flush=True)
        return result
    def bus_origin():
        point=report['route']
        h.lua(f'MELens.walkTo(getPlayer(),{point["startX"]},{point["startZ"]});return true')
        wait('return not MELens.pathing(getPlayer())')
        wait(f'return MELens.facePoint(getPlayer(),{point["startX"]+point["dx"]},{point["startZ"]+point["dz"]})')
        time.sleep(.8)
    try:
        h.lua('''RVI_MoveProbe={rows={},active=false}
local T=RVI_MoveProbe
T.tick=function()
 if not T.active or #T.rows>=400 then return end
 local ok,err=pcall(function()
 local p=getPlayer();local d=MELens.debugState();local v=p:getVehicle();local q=MELens.profileFor(v)
 T.rows[#T.rows+1]={t=getTimestampMs()-T.start,x=p:getX(),y=p:getY(),localX=d.x,localZ=d.z,
 pose=d.pose,alpha=p:getAlpha(0),targetAlpha=p:getTargetAlpha(0),aiming=p:isAiming(),
 nativeDistance=MELensRV.nativeMovementDistance(p),animation=MELensRV.animInfo(p),
 tracks=MELensDevBones.tracks(p),walkable=not q or MELens.walkableAt(q,d.x,d.z)}
 end)
 if not ok then T.error=tostring(err);Events.OnPostRender.Remove(T.tick) end
end
Events.OnPostRender.Add(T.tick);ISUIHandler.setVisibleAllUI(false)
getPlayer():setPrimaryHandItem(nil);getPlayer():setSecondaryHandItem(nil);return true''')
        for kind in ('walk','run'):
            h.lua('''local p=getPlayer();p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY())
p:setTargetAndCurrentDirection(-1,-1);return true''')
            time.sleep(.8)
            trial('outside-'+kind,[key('Forward')]+([key('Run')] if kind=='run' else []))
        trial('outside-aim-strafe',[key('Forward'),key('Aim')])
        h.lua('getPlayer():setTargetAndCurrentDirection(-1,-1);return true');time.sleep(.8)
        trial('outside-short-stop',[key('Forward'),key('Run')],duration=1000,steady_start=700,steady_end=900)
        load('bed-tests').enter(h,'Base.87fordB700school','N')
        # addVehicleDebug randomizes yaw within its requested compass heading.
        # Align this disposable measurement fixture exactly with a real keyboard
        # chord, so a long straight run measures travel rather than aisle collisions.
        report['vehicleAlignmentFixture']=h.lua('local v=getPlayer():getVehicle();local before={x=v:getAngleX(),y=v:getAngleY(),z=v:getAngleZ()};v:setAngles(0,0,0);return before')
        time.sleep(.7)
        scan_code=load('final-mp-motion-tests').ROUTE_SCAN.replace('3.0,.04','7.0,.04')
        scan_code=scan_code.replace('local d=MELens.debugState()','local d=RVI_MoveCandidate')
        route=h.lua('local scan=function() '+scan_code+''' end
local p=getPlayer();local q=MELens.profileFor(p:getVehicle());local best
for z=-4.4,1.4,.1 do
 if MELens.walkableAt(q,0,z) then
  RVI_MoveCandidate={x=0,z=z,facing=0}
  for _,r in ipairs(scan().rows) do
   if r.longitudinal>.98 and (not best or r.free>best.free) then
    r.startX=0;r.startZ=z;best=r
   end
  end
 end
end
RVI_MoveCandidate=nil;return best''')
        report['route']=route;save()
        assert route and route['free']>3.5, 'bus does not have a clear native-input measurement route'
        codes=[int(k) for k in h._sequence(route['keys'])]
        for kind in ('walk','run'):
            bus_origin()
            h.lua('ISUIHandler.setVisibleAllUI(false);return true')
            speed=report['trials']['outside-'+kind]['steadyWorldSpeed']
            duration=2100 if kind=='walk' else 1650
            # Measure a complete native walk/run cycle (2/3 s at 1.04 speed).
            # A partial stride depends on its current foot phase and can report
            # different speeds even when both use the identical native motion.
            end=duration-100;start=end-round(1000*(2/3)/1.04)
            assert end-start>=250,'native run-up needs a longer unobstructed route'
            trial('inside-'+kind,codes+([key('Run')] if kind=='run' else []),duration,start,end)
        for kind in ('walk','run'):
            a,b=report['trials']['outside-'+kind],report['trials']['inside-'+kind]
            begin,end=b['steadyWindow']
            control=[r for r in a['samples'] if begin<=r['t']<=end]
            control_speed=math.hypot(control[-1]['x']-control[0]['x'],control[-1]['y']-control[0]['y'])/((control[-1]['t']-control[0]['t'])/1000)
            ratio=b['steadyWorldSpeed']/control_speed
            report[kind+'Ratio']=ratio;save()
            assert .93<ratio<1.07,kind+': native steady speed differs by over 7%'
        bus_origin()
        aim=key('Aim');assert aim>0,'Aim binding unavailable'
        aimed=trial('inside-aim-strafe',codes+[aim],duration=2100)
        assert any(r['aiming'] for r in aimed['samples']),'native Aim input did not aim'
        assert any('strafe' in r['animation'].lower() for r in aimed['samples']),'native strafe state did not run'
        assert aimed['steadyWorldSpeed']>.05,'aiming blocks cabin movement'
        bus_origin()
        stopped=trial('inside-short-stop',codes+[key('Run')],duration=1000,steady_start=700,steady_end=900)
        expected=report['trials']['outside-short-stop']['stopTailDistance']
        report['stopTailRatio']=stopped['stopTailDistance']/expected;save()
        assert .8<report['stopTailRatio']<1.2,'native stop travel is lost or excessive'
        bus_origin()
        routes=h._sequence(h.lua(load('final-mp-motion-tests').ROUTE_SCAN)['rows'])
        wall=max((r for r in routes if r['longitudinal']<.2),key=lambda r:r['free'])
        blocked=trial('inside-wall',[int(k) for k in h._sequence(wall['keys'])]+[key('Run')])
        assert blocked['samples'][-1]['pose']=='Idle','wall running did not stop'
        h.lua('Events.OnPostRender.Remove(RVI_MoveProbe.tick);MELens.leave(getPlayer());return true')
        wait('return getPlayer():getVehicle()==nil')
        # Existing driver clicks the real bed menu, sleep confirmation and E.
        command=[sys.executable,str(ROOT/'dev/bed-tests.py'),'--run',os.environ['RVI_CAPTURE_RUN'],
                 '--vehicle','Base.Trailer54FlyingCloud22','--heading','E','--label','release-camper-bed']
        result=subprocess.run(command,check=False)
        report['bedDriverExit']=result.returncode;save()
        assert result.returncode==0,'furnished bed input checks failed'
        turns=subprocess.run([sys.executable,str(ROOT/'dev/turning-tests.py')],check=False)
        report['turnDriverExit']=turns.returncode;save()
        assert turns.returncode==0,'native turn comparison failed'
        report['passed']=True;save()
    except Exception as error:
        report['error']=str(error);report['traceback']=traceback.format_exc();save();raise
    finally:
        try:h.lua('MEMCNativeLab.releaseKeys();if RVI_MoveProbe then Events.OnPostRender.Remove(RVI_MoveProbe.tick) end;return true')
        except Exception:pass

if __name__=='__main__':main()
