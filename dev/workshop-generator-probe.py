import importlib.util,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('h',root/'dev/final-feature-tests.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
run=root/'build/rv'/os.environ['RVI_CAPTURE_RUN'];h.configure(run/'generator-capacity')
r=h.lua('''local p=getPlayer();local v=p:getVehicle();local floor=MELens.Loose.floorContainer(v)
local item=assert(floor:AddItem("Base.Generator"));local d=MELens.debugState();MELens.Loose.set(v,item,d.x,MELens.profileFor(v).floorY,d.z,0,0)
local a=MELensGrabLoose:new(p,v,item:getID(),item:getActualWeight())
return {id=item:getID(),weight=item:getActualWeight(),inventoryWeight=p:getInventory():getCapacityWeight(),hasRoom=p:getInventory():hasRoomFor(p,item),valid=a:isValid(),inFloor=item:getContainer()==floor}''')
(run/'generator-baseline.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
