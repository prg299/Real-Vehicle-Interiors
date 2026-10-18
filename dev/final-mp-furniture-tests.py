"""MP authority wrapper around the genuine furniture/loose native input cases.

Run after MP camper Dashboard setup. Only server fixtures tag the original heater
and create/position the owned hammer. No client creates, transfers or positions
items as setup. Normal UI container selection obtains replicated Floor contents.
Every feature mutation uses actual native mouse/keyboard events. Parent owns all
game lifetimes. Final actual inventory Place leaves the same hammer in Floor.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback


ROOT=Path(__file__).resolve().parents[1]


def load_driver(name):
    spec=importlib.util.spec_from_file_location(name.replace("-","_"),Path(__file__).with_name(name+".py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


WORLD_READ=r'''
local v=getVehicleById(VEHICLE_ID);assert(v,"replicated camper missing")
local M,P,L=MELens,MELens.Parts,MELens.Loose
local part=v:getPartById(HEATER_PART)
local heater=part and part:getInventoryItem()
local floor=L.floorContainer(v)
local function ids(c) local out={};if c then for i=0,c:getItems():size()-1 do out[#out+1]=c:getItems():get(i):getID() end end;return out end
local r={vehicleId=v:getId(),heaterId=heater and heater:getID(),heaterCondition=heater and heater:getCondition(),
    floor=ids(floor),entry=HAMMER_ID>=0 and L.entry(v,HAMMER_ID) or nil,players={}}
local list=getOnlinePlayers()
for i=0,list:size()-1 do
    local p=list:get(i)
    if isServer() or p==getPlayer() then
        r.players[p:getUsername()]={inside=p:getVehicle()==v,inventory=ids(p:getInventory())}
    end
end
if not isServer() then
    local p=getPlayer();r.players[p:getUsername()]={inside=p:getVehicle()==v,inventory=ids(p:getInventory())}
end
'''


class FurnitureLab:
    def __init__(self, lab, module):
        self.lab,self.module,self.h=lab,module,lab.h
        self.furniture=load_driver("final-furniture-tests")
        self.interior,self.tap,_=self.furniture.load_helpers()
        self.inventory=load_driver("final-mp-loot-ui-tests").InventoryLab(lab,module)
        self.heater_id,self.hammer_id,self.heater_part=-1,-1,""

    def server(self, code):
        return self.lab.server(code)

    def world(self, side):
        code=WORLD_READ.replace("VEHICLE_ID",str(self.lab.vid)).replace("HEATER_PART",json.dumps(self.heater_part)).replace("HAMMER_ID",str(self.hammer_id))
        if side=="server":
            result=json.loads(self.server(self.module.JSON_ENCODER+code+"return enc(r)"))
        else:
            result=(self.lab.h if side=="A" else self.lab.b).lua(code+"return r")
        result["floor"]=self.h._sequence(result.get("floor"))
        for value in result["players"].values(): value["inventory"]=self.h._sequence(value.get("inventory"))
        return result

    def all_worlds(self):
        return {side:self.world(side) for side in ("A","B","server")}

    def prepare(self):
        self.h.check(self.server('return tostring(isServer()).."/"..tostring(MELensRV==nil)')=="true/true",
                     "MP furniture receipt requires the ordinary server without MELensRV Java")
        info=self.h.lua('local p=getPlayer();local v=p:getVehicle();return v and {id=v:getId(),standing=MELens.isStanding(p),script=v:getScript():getFullName()}')
        self.h.check(info and info["standing"] and info["script"]=="Base.Trailer54FlyingCloud22","A must stand inside the prepared Flying Cloud")
        self.lab.vid=int(info["id"])
        self.h.check(self.lab.b.lua(f'return getPlayer():getVehicle()==getVehicleById({self.lab.vid}) and MELens.isStanding(getPlayer())'),"B must stand in same camper")
        code=f'''
local v=getVehicleById({self.lab.vid});assert(v and v:isStopped())
local p;local list=getOnlinePlayers();for i=0,list:size()-1 do if list:get(i):getUsername()=="MELensAdmin" then p=list:get(i) end end
assert(p and p:getVehicle()==v,"server actor membership missing")
local T=MELensMPFurnitureTest
if not T or T.vehicle~=v then T={{vehicle=v,actor=p}};MELensMPFurnitureTest=T end
if not T.heaterId then
    for i,spot in ipairs(MELens.profileFor(v).spots) do
        local part=MELens.Parts.spotPart(v,i)
        if MELens.Parts.pieceAt(part)=="heater" then
            T.heaterId=part:getInventoryItem():getID();T.heaterPart=part:getId();break
        end
    end
end
assert(T.heaterId,"server original heater missing")
local part=v:getPartById(T.heaterPart)
local heater=part:getInventoryItem() or p:getInventory():getItemById(T.heaterId)
assert(heater and heater:getID()==T.heaterId,"original heater identity was lost")
heater:getModData().MELensMPFurnitureFixture="heater"
if part:getInventoryItem() then v:transmitPartItem(part) end
return enc({{heaterId=T.heaterId,heaterPart=T.heaterPart,installed=part:getInventoryItem()~=nil}})
'''
        original=json.loads(self.server(self.module.JSON_ENCODER+code))
        self.heater_id,self.heater_part=int(original["heaterId"]),original["heaterPart"]
        self.h.REPORT["originalHeaterFixture"]=original
        return original

    def close_inventory(self,side):
        state=self.inventory.read(side)
        if state["windows"]["inventory"]["visible"]:
            self.lab.input(side,key=int(state["inventoryKey"]))
            self.inventory.wait(side,lambda s:not s["windows"]["inventory"]["visible"],"close inventory for world interaction")

    def seed_loose(self):
        code='''
local T=MELensMPFurnitureTest;local floor=MELens.Loose.floorContainer(T.vehicle);assert(floor)
local item=T.hammerId and (floor:getItemById(T.hammerId) or T.actor:getInventory():getItemById(T.hammerId))
if not item then item=floor:AddItem("Base.Hammer");assert(item);T.hammerId=item:getID()
else local source=item:getContainer();if source~=floor then source:Remove(item);sendRemoveItemFromContainer(source,item);floor:AddItem(item) end end
item:setName("Native input test hammer");item:getModData().MELensMPFurnitureFixture="hammer"
sendAddItemToContainer(floor,item)
return tostring(T.hammerId)
'''
        self.hammer_id=int(self.server(code))
        self.inventory.part,self.inventory.item_id="MELensFloor",self.hammer_id
        for side in ("A","B"):
            self.inventory.open(side)
            self.inventory.select_container(side,"MELensFloor")
            self.inventory.wait(side,lambda s:s["windows"]["loot"].get("row") is not None,"server-created hammer row replicated through normal Floor UI")
            self.close_inventory(side)
        self.h.lua(f'local T=MELensInteriorTest;T.hammer=MELens.Loose.floorContainer(T.vehicle):getItemById({self.hammer_id});assert(T.hammer);return true')
        point=self.furniture.wait_point(self.h,"return MELensInteriorTest.looseFixturePoint(MELensInteriorTest.hammer)","client read-only exposed Floor geometry")
        self.server(f'''
local T=MELensMPFurnitureTest;local v=T.vehicle;local part=MELens.Loose.floorPart(v)
local positions=part:getModData()[MELens.Loose.KEY] or {{}};part:getModData()[MELens.Loose.KEY]=positions
positions[string.format("%d",T.hammerId)]={{t="Base.Hammer",x={point['x']},y=MELens.profileFor(v).floorY,z={point['z']},r=0,s=0}}
v:transmitPartModData(part);return "server-positioned"
''')
        actor=self.interior.poll(self.h,lambda s:s["loose"].get("entry") and abs(s["loose"]["entry"]["r"])<.01
                                 and abs(s["loose"]["entry"]["x"]-point["x"])<.02
                                 and abs(s["loose"]["entry"]["z"]-point["z"])<.02,
                                 timeout=20,label="server-only hammer position replicated to A")
        self.wait_receipt("server-only-hammer-fixture",actor,expected_rotation=0)
        self.h.REPORT["serverHammerFixture"]={"itemId":self.hammer_id,"point":point,"clientAuthorityMutation":False}
        return self.interior.read_state(self.h)

    def wait_receipt(self,case,actor,expected_rotation=None):
        def matches(worlds):
            truth=worlds["server"]
            if not all(world["players"].get("MELensAdmin" if side=="A" else "MELensGuest",{}).get("inside")
                       for side,world in worlds.items() if side!="server"):
                return False
            if not all(p.get("inside") for p in truth["players"].values()): return False
            expected_heater=actor["furniture"].get("heaterInstalledId")
            if any(world.get("heaterId")!=expected_heater for world in worlds.values()): return False
            if expected_heater is not None and any(world.get("heaterCondition")!=actor["furniture"]["heaterCondition"] for world in worlds.values()): return False
            owner=truth["players"].get("MELensAdmin",{}).get("inventory",[])
            if owner.count(self.heater_id)!=(1 if actor["furniture"]["heaterInInventory"] else 0): return False
            if self.hammer_id<0: return True
            loose=actor.get("loose",{})
            expected=loose.get("entry")
            for world in worlds.values():
                if world["floor"].count(self.hammer_id)!=(1 if loose.get("inFloor") else 0): return False
                actual=world.get("entry")
                if bool(actual)!=bool(expected): return False
                if expected:
                    if any(abs(float(actual[key])-float(expected[key]))>.02 for key in ("x","y","z","r","s")): return False
                    if expected_rotation is not None and abs(float(actual["r"])-expected_rotation)>.02: return False
            if owner.count(self.hammer_id)!=(1 if loose.get("inInventory") else 0): return False
            if self.hammer_id in truth["players"].get("MELensGuest",{}).get("inventory",[]): return False
            return True
        receipt=self.lab.wait(self.all_worlds,matches,f"{case} exact-ID authority/observer receipt",timeout=30)
        self.h.REPORT["lastMPFurnitureReceipt"]=receipt
        return receipt

    def final_inventory_place(self):
        before=self.interior.read_state(self.h)
        self.inventory.part,self.inventory.item_id="MELensFloor",self.hammer_id
        state=self.inventory.open("A")
        for _ in range(45):
            state=self.inventory.read("A");row=state["windows"]["inventory"].get("row")
            self.h.check(row,"grabbed original hammer missing from ordinary inventory UI")
            if not row["above"] and not row["below"]: break
            point=state["windows"]["inventory"]["scrollUp" if row["above"] else "scrollDown"]
            self.inventory.click("A",point,"ordinary inventory scrollbar to original hammer")
            self.inventory.wait("A",lambda s:True,"inventory scroll delivery")
        self.h.check(not row["above"] and not row["below"],"hammer inventory row remains clipped")
        self.inventory.click("A",row,"hammer inventory row context",right=True)
        label=self.h.lua('return getText("ContextMenu_MELens_PlaceItem")')
        state=self.inventory.wait("A",lambda s:any(option["name"]==label for option in s["menus"]),"native inventory Place option")
        options=[option for option in state["menus"] if option["name"]==label]
        self.h.check(len(options)==1 and options[0]["enabled"],"inventory Place disabled or ambiguous")
        self.inventory.click("A",options[0],"native inventory Place hammer")
        self.interior.poll(self.h,lambda s:s["loose"]["modeActive"],timeout=8,label="inventory Place opens loose preview")
        point=self.furniture.wait_point(self.h,"return MELensInteriorTest.movePoint()","valid final Floor placement")
        self.tap.native_click(self.h,point["x"],point["y"],"hammer final inventory Place commit")
        after,seen=self.furniture.finish(self.h,self.interior,lambda s:s["loose"]["inFloor"] and not s["loose"]["inInventory"]
                                         and not s["loose"]["modeActive"] and s["loose"].get("entry"),
                                         "MELensPlaceLoose","MP final inventory Place")
        self.h.record("inventory-place-loose-same-item-for-persistence",before,after,
                      observedTimedActions=seen,uiHandlersInvokedDirectly=False,serverFixture=False)
        self.close_inventory("A")
        self.lab.capture("A","mp-furniture-final-floor-for-persistence")
        return after

    def run(self):
        original=self.prepare()
        self.h.REPORT.update(mpAuthorityWrapper=True,serverNoJava=True,fixtureAuthority="dedicated-server only")
        for side in ("A","B"):
            self.close_inventory(side)
        native_record=self.h.record
        def checked_record(name,before,after,**details):
            receipt=self.wait_receipt(name,after)
            return native_record("mp-"+name,before,after,**details,authorityAndObserver=receipt)
        self.h.record=checked_record
        try:
            self.furniture.run_cases(self.h,self.interior,self.tap,"all",not original["installed"],self.heater_id,seed_loose=self.seed_loose)
            final=self.final_inventory_place()
            self.h.REPORT.update(scope=__doc__.strip(),serverNoJava=True,fixtureAuthority="dedicated-server only",
                                 unverified=["multiplayer sleep progression","other vehicle furniture layouts"],
                                 persistenceItemId=self.hammer_id,persistenceHeaterId=self.heater_id)
            return {"actorA":final,"worlds":self.all_worlds(),"hammerId":self.hammer_id,"heaterId":self.heater_id}
        finally:
            self.h.record=native_record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session",type=Path,default=ROOT/"build/rv/final-mp-206")
    parser.add_argument("--output",type=Path,default=ROOT/"build/rv/final-mp-furniture")
    args=parser.parse_args();lab=None
    try:
        module=load_driver("final-mp-interior-tests")
        lab=module.InteriorLab(args.session.resolve(),args.output.resolve())
        lab.h.REPORT["final"]=FurnitureLab(lab,module).run()
        print(f"NATIVE_MP_FURNITURE_PASSED {lab.h.write_report('passed')}",flush=True)
        return 0
    except Exception:
        error=traceback.format_exc()
        if lab: path=lab.h.write_report("failed",error)
        else:
            args.output.mkdir(parents=True,exist_ok=True);path=args.output/"native-feature-tests.json"
            path.write_text(json.dumps({"status":"failed","error":error}),encoding="utf-8")
        print(error,flush=True)
        print(f"NATIVE_MP_FURNITURE_FAILED {path}; parent-owned clients/server left running",flush=True)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
