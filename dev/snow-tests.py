"""Snow checks in a game owned by workshop-capture.ps1; run through run-heavy."""
import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_helpers", ROOT / "dev/final-feature-tests.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def wait(code, predicate, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = h.lua(code)
        if predicate(result):
            return result
        time.sleep(.15)
    raise AssertionError(f"Timed out: {code}: {result}")


def capture(run, name):
    source = run / f"home/Zomboid/Screenshots/{name}.png"
    h.lua(f"MEMCNativeLab.capture('{name}.png'); return true")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if source.exists() and source.read_bytes().endswith(b'IEND\xaeB`\x82'):
            shutil.copyfile(source, run / f"{name}.png")
            return
        time.sleep(.1)
    raise AssertionError(f"Missing completed capture: {name}")


STATE = '''local p=getPlayer(); local v=p:getVehicle(); local c=getClimateManager()
local o={inside=v~=nil,standing=MELens.isStanding(p),x=p:getX(),y=p:getY(),
snow=c:getSnowFracNow(),snowTarget=getCell():getSnowTarget(),
precipitation=c:getPrecipitationIntensity(),snowing=c:getPrecipitationIsSnow(),
temperature=c:getTemperature(),queue=#ISTimedActionQueue.getTimedActionQueue(p).queue}
if v then local q=Vector3f.new(); v:getPassengerLocalPos(v:getSeat(p),q); o.localX=q:x();o.localZ=q:z() end
return o'''


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', default=os.environ.get('RVI_CAPTURE_RUN'))
    parser.add_argument('--vehicle', default='Base.Trailer54FlyingCloud22')
    parser.add_argument('--heading', default='E', choices=['N', 'E', 'S', 'W'])
    parser.add_argument('--precipitation', default='snow', choices=['snow','rain'])
    parser.add_argument('--measure', action='store_true')
    parser.add_argument('--label', default='control')
    args = parser.parse_args(argv)
    assert args.run, '--run or RVI_CAPTURE_RUN is required'
    run = (ROOT / 'build/rv' / args.run).resolve()
    assert run.is_relative_to(ROOT / 'build/rv')
    snow=args.precipitation=='snow'
    report = {'vehicle':args.vehicle,'heading':args.heading,'precipitation':args.precipitation,'inputs':[], 'states':{}}
    report['jarSha256']=hashlib.sha256((run/'home/Zomboid/mods/RealVehicleInteriors/42.21/media/java/RealVehicleInteriors.jar').read_bytes()).hexdigest()
    try:
        assert not h.lua('return getPlayer():getVehicle()~=nil'), 'snow fixture must start outside'
        h.lua('local p=getPlayer();p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true')
        h.lua('local b=getPlayer():getBodyDamage();b:setHasACold(false);b:setColdStrength(0);b:setSneezeCoughActive(0);getGameTime():setTimeOfDay(12);return true')
        h.lua('''local c=getClimateManager()
for _,pair in ipairs({{ClimateManager.FLOAT_TEMPERATURE,-12},{ClimateManager.FLOAT_PRECIPITATION_INTENSITY,1},
{ClimateManager.FLOAT_WIND_INTENSITY,0.1},{ClimateManager.FLOAT_FOG_INTENSITY,0}}) do
local f=c:getClimateFloat(pair[1]); f:setEnableAdmin(true);f:setAdminValue(pair[2]) end
local b=c:getClimateBool(ClimateManager.BOOL_IS_SNOW);b:setEnableAdmin(true);b:setAdminValue(true)
getCore():setForceSnow(true);c:postCellLoadSetSnow();getCore():setOptionRenderPrecipitation(1)
getCore():setAutoZoom(0,false)
ISUIHandler.setVisibleAllUI(false); return true''')
        h.lua(f'getClimateManager():getClimateBool(ClimateManager.BOOL_IS_SNOW):setAdminValue({str(snow).lower()});return true')
        spawn = (ROOT / 'dev/lua/spawn_one.lua').read_text().replace('NAME',args.vehicle)
        spawn = spawn.replace('tonumber("7")','tonumber("-4")').replace('local HEADING = "E"',f'local HEADING = "{args.heading}"')
        print(h.lua(spawn),flush=True)
        h.lua('''local p=getPlayer();local v=MELensTest.vehicle
local q=Vector3f.new();local o=v:getPassengerPosition(MELens.cabinSeat(v),'outside')
v:getPassengerPositionWorldPos(o,q);p:setX(q:x());p:setY(q:y());p:setLastX(q:x());p:setLastY(q:y())
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q)
p:faceLocation(q:x(),q:y()); return true''')
        # Turn through the production movement input. The idle player can restore
        # its previous facing after a fixture's faceLocation call, especially at a bus door.
        approach=h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local q=Vector3f.new()
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q)
local dx,dy=q:x()-p:getX(),q:y()-p:getY();local sx,sy=dx-dy,dx+dy
local bind=math.abs(sx)>math.abs(sy) and (sx>0 and "Right" or "Left") or (sy>0 and "Backward" or "Forward")
return getCore():getKey(bind)''')
        h.lua(f'MEMCNativeLab.holdKey({int(approach)},150);return true')
        report['inputs'].append({'action':'doorway-approach','key':approach,'milliseconds':150,'fixtureOnly':True})
        time.sleep(.5)
        wait(STATE,lambda s:s['precipitation']>.99 and s['snowing']==snow)
        wait(STATE,lambda s:s['snow']>.69 and s['snowTarget']>=70)
        time.sleep(4)
        report['states']['outside']=h.lua(STATE)
        capture(run,args.label+'-outside')
        key=h.lua('return getCore():getKey("Interact")')
        h.lua(f'MEMCNativeLab.holdKey({int(key)},200); return true')
        report['inputs'].append({'action':'enter','key':key,'milliseconds':200})
        report['states']['inside']=wait(STATE,lambda s:s['standing'] and s['queue']==0)
        time.sleep(3)
        h.lua('MEMCNativeLab.freezeWeather(true);return true')
        report['identicalWeatherParticles']=True
        # Fixed climate and cabin; only the additional weather mask changes.
        # The control is the stock renderer from the same compiled build.
        for enabled in (False, True):
            h.lua(f'MEMCNativeLab.weatherMask({str(enabled).lower()}); return true')
            time.sleep(1)
            kind='fixed' if enabled else 'control'
            report['states'][kind]=json.loads(h.lua('return MELensRV.weatherInfo()'))
            for i in range(3):
                capture(run,f'{args.label}-{kind}-{i}')
                time.sleep(.5)
            if args.measure:
                h.lua('MEMCNativeLab.measure(120);return true')
                timing=wait('return MEMCNativeLab.measurement()',lambda value:json.loads(value)['remaining']==0)
                report.setdefault('frameTiming',{})[kind]=json.loads(timing)
        assert report['states']['fixed']['draws'] > report['states']['control']['draws'], 'cabin mask never reached native renderer'
        assert report['states']['fixed']['sheltered'] > report['states']['control']['sheltered'], 'no native snowflakes/raindrops were sheltered'
        h.lua('MEMCNativeLab.freezeWeather(false);return true')
        h.lua('local f=getClimateManager():getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY);f:setAdminValue(0);return true')
        wait('return getCell():getWeatherFX():getPrecipitationIntensity()',lambda value:value<.01)
        time.sleep(2)
        capture(run,args.label+'-ground-snow-only')
        report['states']['groundSnowOnly']=h.lua(STATE)
        h.lua('local f=getClimateManager():getClimateFloat(ClimateManager.FLOAT_PRECIPITATION_INTENSITY);f:setAdminValue(1);return true')
        before=h.lua(STATE)
        moved=False
        # All four production movement bindings, with collision left enabled.
        for binding in ('Forward','Backward','Left','Right'):
            key=h.lua(f'return getCore():getKey("{binding}")')
            h.lua(f'MEMCNativeLab.holdKey({int(key)},450);return true')
            report['inputs'].append({'action':binding,'key':key,'milliseconds':450})
            time.sleep(.8)
            position=h.lua(STATE)
            moved=moved or abs(before['localX']-position['localX'])+abs(before['localZ']-position['localZ']) > .01
        after=h.lua(STATE)
        assert moved, 'native walking did not move player'
        report['states']['walked']=after
        capture(run,f'{args.label}-walked')
        h.lua('''local p=getPlayer();local q=MELens.profileFor(p:getVehicle());
MELens.walkTo(p,q.exitMarker.x,q.exitMarker.z); return true''')
        wait(STATE,lambda s:s['queue']==0 and not h.lua('return MELens.pathing(getPlayer())'))
        key=h.lua('return getCore():getKey("Interact")')
        h.lua(f'MEMCNativeLab.holdKey({int(key)},200); return true')
        report['inputs'].append({'action':'exit','key':key,'milliseconds':200})
        report['states']['exited']=wait(STATE,lambda s:not s['inside'] and s['queue']==0)
        capture(run,args.label+'-exited')
        report['passed']=True
    finally:
        try:
            h.lua('MEMCNativeLab.freezeWeather(false);MEMCNativeLab.weatherMask(true);MEMCNativeLab.releaseKeys();return true')
        except Exception:
            pass
        (run / f'{args.label}-report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps({'case':args.label,'passed':report.get('passed',False),
                          'report':str(run/f'{args.label}-report.json')}),flush=True)


if __name__=='__main__':
    main()
