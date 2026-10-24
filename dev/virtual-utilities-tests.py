"""Native Lua callbacks with the engine's real VirtualVehicle (explicit state fixtures)."""
import importlib.util,json,os
from pathlib import Path
import traceback

ROOT=Path(__file__).resolve().parents[1]

def main():
    spec=importlib.util.spec_from_file_location('helpers',ROOT/'dev/final-feature-tests.py')
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN'];h.configure(run/'virtual-utilities')
    try:
        result=h.lua('''local U=MELens.Utilities
local owner=MELensDevVirtualUtilities.emptyOwner()
assert(owner.getModData==nil,"fixture must be the real lightweight owner")
assert(U.busy(owner)==false)
U.initGenerator(owner,nil);U.updateGenerator(owner,nil,60);U.runGenerator(owner,nil,60)
U.updateOven(owner,nil,60);U.updateFridge(owner,nil,60);U.updateHeater(owner,nil,60)
return {proxy=tostring(owner),missingVehicleModData=true,callbacks=7,passed=true}''')
        h.REPORT['realVirtualVehicle']=result
        # A loaded vehicle still follows the production generator path.
        spawn=(ROOT/'dev/lua/spawn_one.lua').read_text().replace('NAME','Base.Trailer54FlyingCloud22')
        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensTest={all={}};return true''');h.lua(spawn)
        h.REPORT['loadedVehicle']=h.lua('''local v=MELensTest.vehicle;local U=MELens.Utilities
local gen=assert(v:getPartById(MELens.Parts.GENERATOR));local d=gen:getModData()
d.on=true;d.fuel=7.25;gen:setCondition(73)
local rate=U.generatorFuelRate(v);U.updateGenerator(v,gen,1)
assert(math.abs(d.fuel-(7.25-rate/60))<.000001 and d.on and U.busy(v))
local water=v:getPartById(MELens.Parts.WATER);local wd=water:getModData();wd.water=11.5;wd.tainted=true
local owner=MELensDevVirtualUtilities.emptyOwner();local fuel=d.fuel
U.updateGenerator(owner,gen,60);assert(d.fuel==fuel and d.on and gen:getCondition()==73)
assert(wd.water==11.5 and wd.tainted==true)
return {passed=true,fuel=d.fuel,condition=gen:getCondition(),water=wd.water,tainted=wd.tainted}''')
        h.REPORT['nativeInput']=False
        h.REPORT['scope']=__doc__
        h.REPORT['unverified']=['actual chunk-unload scheduling','dedicated multiplayer','UI input']
        h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
    except Exception:
        h.write_report('failed',traceback.format_exc());raise

if __name__=='__main__':raise SystemExit(main())
