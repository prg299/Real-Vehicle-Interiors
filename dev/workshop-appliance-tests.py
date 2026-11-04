"""Native F700 bank-truck power/propane controls and real food cooling.

Vehicle, fittings, supplies, climate and a one-hour clock advance are fixtures.
Switches and portable-supply installation use native Dashboard mouse input.
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
    h=load('final-feature-tests');h.configure(run/('f700-appliances-'+str(time.time_ns())));h.SCREENS=run/'home/Zomboid/Screenshots'
    def wait(code,label,timeout=35):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            result=h.lua(code)
            if result:return result
            time.sleep(.15)
        raise AssertionError(label)
    try:
        if not h.lua('local v=getPlayer():getVehicle();return v and v:getScriptName()=="Base.87fordF700bank"'):
            h.lua('MELens.leave(getPlayer());return true')
            wait('return getPlayer():getVehicle()==nil','previous vehicle exit')
            h.lua('local p=getPlayer();p:setX(10830.5);p:setY(10155.5);p:setLastX(p:getX());p:setLastY(p:getY());return true')
            load('bed-tests').enter(h,'Base.87fordF700bank','E')
        h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do local part=P.spotPart(v,i)
 if part:getItemContainer() then part:getItemContainer():clear() end
 part:setInventoryItem(nil);P.applyPiece(v,part)
end
for index,piece in pairs({[1]="kitchen",[4]="fridge"}) do local part=P.spotPart(v,index)
part:setInventoryItem(instanceItem(P.itemType(piece)));P.applyPiece(v,part) end
return true''')
        h.lua('MELensFeatureTestReset=true;return true')
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text())
        h.lua('ISUIHandler.setVisibleAllUI(true);MELens.Dashboard.open(getPlayer(),MELensTest.vehicle);local w=MELens.Dashboard.instance;w:setX(30);w:setY(25);return true')
        h.disabled_case('generator','empty-fuel-generator-rejected')
        empty=h.snapshot()
        h.check(not empty['utilities']['stoveOn'] and not any(c['action']=='stove' for c in empty['controls']),
                'empty propane should show its status instead of an available stove switch')
        before=h.click_control('addFuel');after=h.wait_idle()
        h.check(after['utilities']['generatorFuel']>0,'native fuel installation failed')
        h.record('native-generator-fuel-install',before,after)
        h._toggle('generator','generatorOn',True)
        before=h.click_control('addPropane');after=h.wait_idle()
        h.check(after['utilities']['propane']>0,'native propane installation failed')
        h.record('native-propane-install',before,after)
        h.wait_for(lambda state:any(c['action']=='stove' for c in state['controls']),
                   timeout=10,label='rendered stove switch after propane installation')
        h._toggle('stove','stoveOn',True)
        h.check(h.lua('return MELens.Utilities.ovenState(MELensTest.vehicle).on and MELens.Utilities.canBurn(MELensTest.vehicle)'),'F700 stove cannot burn inserted propane')
        h._toggle('stove','stoveOn',False)
        h.lua((ROOT/'dev/lua/utility-refrigeration.lua').read_text()+';MELensUtilityProbe.bind(MELensTest.vehicle);return true')
        before=h.lua('return MELensUtilityProbe.foodControls()')
        h.check(before['fridge'] and before['powered'] and abs(before['temperature']-.2)<.001,'custom fridge not powered/cold')
        h.lua('return MELensUtilityProbe.advance(1)')
        time.sleep(2)
        after=h.lua('return MELensUtilityProbe.ageControls()')
        prior={f['id']:f for f in h._sequence(before['foods'])}
        current={f['id']:f for f in h._sequence(after['foods'])}
        cold=current[before['controlColdId']];warm=current[before['controlWarmId']]
        cd=cold['age']-prior[cold['id']]['age'];wd=warm['age']-prior[warm['id']]['age']
        h.check(wd>.001 and 0<=cd<wd*.5 and cold['heat']<.3,'native food does not cool/age more slowly in the powered fridge')
        h.REPORT['nativeFoodAging']={'before':before,'after':after,'coldAgeDelta':cd,'warmAgeDelta':wd}
        h.capture('f700-fridge-and-stove-controls')
        h._toggle('generator','generatorOn',False)
        wait('return not MELensUtilityProbe.snapshot().powered and MELensUtilityProbe.snapshot().temperature==1','fridge remains powered after generator off')
        h.REPORT['unverified']=['Steam transport','every appliance/furniture combination']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error);return 1

if __name__=='__main__':raise SystemExit(main())
