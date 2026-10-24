"""Compare native Run input outside and inside an owned, guarded game.

Spawn/position/pathing are fixtures. Movement uses production keyboard dispatch;
per-tick samples measure steady travel and the active native animation.
"""
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
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h = load('final-feature-tests')
    h.configure(run/'running')
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=', 1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    try:
        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);MELensMedia.cameraOff();p:setPrimaryHandItem(nil);p:setSecondaryHandItem(nil)
p:setSneaking(false);p:setIsAiming(false);p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY())
ISUIHandler.setVisibleAllUI(false);return true''')
        bindings = h.lua('return {forward=getCore():getKey("Forward"),left=getCore():getKey("Left"),run=getCore():getKey("Run")}')
        h.REPORT['scope'] = __doc__
        h.REPORT['bindings'] = bindings
        h.REPORT['trials'] = {}

        def trial(label, keys, duration=900, steady_start=250, steady_end=550):
            h.lua('''if RVIRunSample then Events.OnTick.Remove(RVIRunSample) end
RVIRunRows={};RVIRunStart=getTimestampMs();RVIRunSampleUntil='''+str(duration+200)+'''
RVIRunSample=function()
local p=getPlayer();local s=MELens.debugState();local t=getTimestampMs()-RVIRunStart
if t>RVIRunSampleUntil then Events.OnTick.Remove(RVIRunSample);return end
RVIRunRows[#RVIRunRows+1]={t=t,x=p:getX(),y=p:getY(),localX=s.x,localZ=s.z,pose=s.pose,
running=p:isRunning(),cabinRunning=s.running,animation=MELensRV.animInfo(p),tracks=MELensDevBones.tracks(p)} end
Events.OnTick.Add(RVIRunSample);return true''')
            h.lua(';'.join(f'MEMCNativeLab.holdKey({int(key)},{duration})' for key in keys)+';return true' if keys else 'return true')
            time.sleep((steady_start+steady_end)/2000)
            h.capture(label)
            time.sleep((duration+200-(steady_start+steady_end)/2)/1000+.1)
            rows = h._sequence(h.lua('return RVIRunRows'))
            for row in rows:
                row['tracks'] = json.loads(row['tracks'])
            h.REPORT['trials'][label] = dict(samples=rows)
            h.lua('MEMCNativeLab.releaseKeys();Events.OnTick.Remove(RVIRunSample);return true')
            steady = [r for r in rows if steady_start <= r['t'] <= steady_end]
            h.check(len(steady) >= 5, 'too few steady samples for '+label)
            a, b = steady[0], steady[-1]
            elapsed = (b['t']-a['t'])/1000
            speed = math.hypot(b['x']-a['x'], b['y']-a['y'])/elapsed
            local_speed = math.hypot(b['localX']-a['localX'], b['localZ']-a['localZ'])/elapsed if 'localX' in a else None
            h.REPORT['trials'][label] = dict(samples=rows, steadyWorldSpeed=speed, steadyLocalSpeed=local_speed,
                                            steadyWindowMs=[steady_start, steady_end])
            h.write_report('running')
            h.REPORT['inputs'].append(dict(action=label, keys=keys, milliseconds=duration, api='MEMCNativeLab.holdKey'))
            h.REPORT['nativeInput'] = True
            time.sleep(.4)
            return speed

        for kind in ('walk', 'run'):
            h.lua('''local p=getPlayer();p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY());
p:faceLocation(p:getX()-1,p:getY()-1);return true''')
            time.sleep(.8)
            trial('outside-'+kind, [bindings['forward']] + ([bindings['run']] if kind=='run' else []),
                  duration=2400, steady_start=1400, steady_end=2100)

        load('bed-tests').enter(h, 'Base.87fordF700box', 'N')
        h.check(h.lua('return getPlayer():getVehicle()==MELensTest.vehicle'), 'entered unexpected vehicle')
        route = h.lua('''local v=MELensTest.vehicle;local p=getPlayer();local best,wall
local combos={{"Forward",nil,0,-1},{"Backward",nil,0,1},{"Left",nil,-1,0},{"Right",nil,1,0},
{"Forward","Left",-1,-1},{"Forward","Right",1,-1},{"Backward","Left",-1,1},{"Backward","Right",1,1}}
for _,c in ipairs(combos) do local a,b=Vector3f.new(),Vector3f.new();local wx,wy=c[4]+c[3],c[4]-c[3]
v:getLocalPos(p:getX(),p:getY(),0,a);v:getLocalPos(p:getX()+wx,p:getY()+wy,0,b)
local dx,dz=b:x()-a:x(),b:z()-a:z();local n=math.sqrt(dx*dx+dz*dz);dx,dz=dx/n,dz/n
local keys={getCore():getKey(c[1])};if c[2] then keys[2]=getCore():getKey(c[2]) end
if dz<-.94 and math.abs(dx)<.34 then best=keys end
if dx>.94 and math.abs(dz)<.34 then wall=keys end end
return {travel=assert(best,"no clear local -Z keys"),wall=assert(wall,"no lateral wall keys")}''')
        wall_keys = h._sequence(route['wall'])
        route = h._sequence(route['travel'])
        h.REPORT['interiorDirectionKeys'] = route
        def position():
            h.lua('MELens.walkTo(getPlayer(),0,-.3);return true')
            deadline = time.monotonic()+30
            while h.lua('return MELens.pathing(getPlayer())'):
                h.check(time.monotonic()<deadline, 'fixture path did not finish')
                time.sleep(.1)
            time.sleep(.35)
        for kind in ('idle', 'walk', 'run'):
            position()
            keys = [] if kind=='idle' else list(route)
            if kind=='run': keys.append(bindings['run'])
            trial('inside-'+kind, keys)
        rows = h.REPORT['trials']
        h.REPORT['runRatioToVanilla'] = rows['inside-run']['steadyWorldSpeed']/rows['outside-run']['steadyWorldSpeed']
        h.REPORT['insideRunToWalkRatio'] = rows['inside-run']['steadyWorldSpeed']/rows['inside-walk']['steadyWorldSpeed']
        h.check(rows['inside-idle']['steadyWorldSpeed'] < .01, 'idle drift')
        h.check(rows['inside-run']['steadyWorldSpeed'] > rows['inside-walk']['steadyWorldSpeed'], 'Run did not move faster')
        if os.environ.get('RVI_EXPECT_RUN_PARITY') == '1':
            h.check(.93 <= h.REPORT['runRatioToVanilla'] <= 1.07, 'interior running differs from vanilla by over 7%')
            outside = [r for r in rows['outside-run']['samples'] if 1400 <= r['t'] <= 2100]
            h.check(all(r['running'] and any(t['name']=='Bob_Run' and t['blend']>0 for t in r['tracks'])
                        and not any(t['name']=='Bob_IdleToRun' and t['blend']>0 for t in r['tracks'])
                        for r in outside), 'vanilla run-up did not finish before measurement')
            active = [r for r in rows['inside-run']['samples'] if 250 <= r['t'] <= 550]
            h.check(all(r.get('pose')=='Run' and r.get('cabinRunning') for r in active), 'running pose flickers')
            h.check(all(any(t['name']=='Bob_Run' and t['blend']>0 for t in r['tracks']) for r in active), 'native Run clip not blending in')
            h.check(any(any(t['name']=='Bob_Run' and t['blend']>.9 for t in r['tracks']) for r in active), 'native Run clip never reached full weight')
            position()
            trial('inside-wall-run', wall_keys+[bindings['run']])
            h.REPORT['collision'] = h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local valid=true;for _,row in ipairs(RVIRunRows) do if not MELens.walkableAt(pr,row.localX,row.localZ) then valid=false end end
return {everySampleWalkable=valid,stillStanding=MELens.isStanding(p) and p:getVehicle()==v,stoppedPose=MELens.debugState().pose}''')
            h.check(h.REPORT['collision']['everySampleWalkable'] and h.REPORT['collision']['stillStanding'], 'running crossed furniture or a wall')
            h.check(h.REPORT['collision']['stoppedPose']=='Idle', 'blocked running did not settle to Idle')
        h.REPORT['unverified'] = ['dedicated multiplayer', 'controller', 'injured/encumbered characters']
        h.write_report('passed')
        print(json.dumps({k:v for k,v in h.REPORT.items() if k in ('runRatioToVanilla','insideRunToWalkRatio')}, indent=2), flush=True)
        (run/'request.json').write_text(json.dumps({'action':'stop'}))
        return 0
    except Exception:
        h.REPORT['error'] = traceback.format_exc()
        h.write_report('failed')
        print(h.REPORT['error'], flush=True)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
