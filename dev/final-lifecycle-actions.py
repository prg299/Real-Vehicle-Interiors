"""Owned lifecycle-profile cleanup/stock-drive inputs; import performs no game I/O.

Ordinary cargo uses real inventory actions (not mouse drag/drop acceptance).
Boxes use native context-menu pickup. --discard-custom-fixtures explicitly
deletes only the just-picked custom test boxes, after verifying their identities;
that disposal is fixture setup and is not claimed as a player uninstall workflow.
No save, mod toggle, launch, quit or process termination occurs here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import traceback
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SNAPSHOT = r'''
local T=MELensLifecycleTest; assert(T and T.vehicle,"run a lifecycle checkpoint first")
local v,p=T.vehicle,getPlayer(); local pv=p:getVehicle(); local queue=ISTimedActionQueue.queues[p]
local r={vehicleId=v:getId(),x=v:getX(),y=v:getY(),speed=v:getCurrentSpeedKmHour(),engine=v:isEngineRunning(),
    inside=pv==v,seat=v:getSeat(p),idle=not queue or #queue.queue==0,boxes={},customContents={},carriedCustom={},nativeCargo={}}
local function ids(c)
    local a={}; if c then for i=0,c:getItems():size()-1 do a[#a+1]=c:getItems():get(i):getID() end end
    table.sort(a); return a
end
for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); local id=part:getId()
    if id:find("^MELensSpot") then local item=part:getInventoryItem(); r.boxes[id]=item and item:getID() or -1 end
    if id:find("^MELens") then r.customContents[id]=ids(part:getItemContainer()) end
end
for i=0,p:getInventory():getItems():size()-1 do local item=p:getInventory():getItems():get(i)
    if item:getFullType():find("MELensRV_") then r.carriedCustom[#r.carriedCustom+1]={id=item:getID(),fullType=item:getFullType()} end
end
r.nativeCargo=ids(v:getPartById("F700TrunkBX"):getItemContainer())
r.inventory=ids(p:getInventory())
r.standing=MELens and MELens.isStanding and MELens.isStanding(p) or false
r.pathing=MELens and MELens.pathing and MELens.pathing(p) or false
return r
'''


class LifecycleActions:
    def __init__(self, run, output):
        expected = json.loads((run / "lifecycle.json").read_text(encoding="utf-8-sig"))
        self.shared = load("final-mp-interior-tests")
        self.h = load("final-feature-tests")
        self.h.configure(output)
        self.h.SCREENS = run / "home/Zomboid/Screenshots"
        self.h.check(self.h.lua('return getWorld():getWorld()') == expected["world"], "Lua endpoint is not the owned lifecycle world")
        self.h.REPORT.update(scope=__doc__.strip(), fixtureDisposal=False)
        # Reuse exactly the reviewed native-menu/key dispatch helpers, without
        # constructing a multiplayer fixture or ever requesting server eval.
        self.lab = self.shared.InteriorLab.__new__(self.shared.InteriorLab)
        self.lab.h = self.h; self.lab.b = self.h; self.lab.input_until = 0
        self.lab.capture = lambda side, name: self.h.capture("lifecycle-first-box-menu") if not self.picked else None
        self.picked = []

    def snapshot(self):
        state = self.h.lua(SNAPSHOT)
        for key in ("carriedCustom", "nativeCargo", "inventory"):
            state[key] = self.h._sequence(state.get(key))
        state["customContents"] = {key: self.h._sequence(value) for key, value in state["customContents"].items()}
        return state

    def wait(self, predicate, label, timeout=90):
        return self.lab.wait(self.snapshot, predicate, label, timeout)

    def enter_native(self):
        self.h.lua('local T=MELensLifecycleTest; local p=getPlayer(); MELensTest={vehicle=T.vehicle}; '
                   'ISTimedActionQueue.add(ISPathFindAction:pathToVehicleSeat(p,T.vehicle,MELens.cabinSeat(T.vehicle))); return true')
        self.wait(lambda s: s["idle"] and self.h.lua('return MELens.nearWayIn(getPlayer(),MELensTest.vehicle,MELens.profileFor(MELensTest.vehicle))'), "at native rear entrance")
        # A long box truck's centre does not define its usable rear door
        # direction. Face the actual outside point so getUseablePart resolves
        # TrunkDoor through the production E/vehicle dispatch path.
        self.h.lua('local p=getPlayer(); local v=MELensTest.vehicle; local q=MELens.profileFor(v); '
                   'local seat=MELens.cabinSeat(v,q); local outside=v:getPassengerPosition(seat,"outside"); '
                   'local point=Vector3f.new(); v:getPassengerPositionWorldPos(outside,point); '
                   'p:faceLocation(point:x(),point:y()); return true')
        self.wait(lambda s: self.h.lua('local p=getPlayer(); local v=MELensTest.vehicle; local part=v:getUseablePart(p); '
                                      'return part and part:getId()==MELens.profileFor(v).standing.door'),
                  "faces the usable rear door before native entry")
        key = self.h.lua('return getCore():getKey(KeybindId.INTERACT)')
        self.h.check(isinstance(key, (int, float)) and key > 0, "interact key is unbound")
        self.lab.input("A", key=int(key))
        return self.wait(lambda s: s["standing"] and s["idle"], "native E standing entry")

    def cleanup(self, discard, documented_removal):
        before = self.snapshot()
        already_inside = before["inside"]
        if already_inside:
            self.h.check(documented_removal and before["standing"],
                         "continuing an already-entered fixture requires documented-removal mode and a standing player")
        else:
            self.enter_native()
        # Enumerate before queuing so ordinary items are conserved, never removed.
        transfer = self.h.lua(r'''
local v,p=MELensLifecycleTest.vehicle,getPlayer(); local dst=v:getPartById("F700TrunkBX"):getItemContainer()
local planned={}
for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); local id=part:getId(); local src=part:getItemContainer()
    if id:find("^MELens") and src then for j=0,src:getItems():size()-1 do local item=src:getItems():get(j)
        assert(not item:getFullType():find("MELensRV_"),"unexpected loose custom fixture item in cargo")
        planned[#planned+1]={item=item,src=src,id=item:getID()}
    end end
end
local ids={}
for _,row in ipairs(planned) do
    ISTimedActionQueue.add(ISInventoryTransferAction:new(p,row.item,row.src,dst)); ids[#ids+1]=row.id
end
return ids
''')
        transferred = self.h._sequence(transfer)
        after = self.wait(lambda s: s["idle"] and all(not ids for ids in s["customContents"].values())
                          and all(item_id in s["nativeCargo"] for item_id in transferred), "ordinary cargo preserved in retained KI5 trunk", timeout=300)
        self.h.record("ordinary-interior-cargo-moved-to-ki5-trunk", before, after, transferredItemIds=transferred,
                      productionInventoryAction=True, mouseDragDropVerified=False)
        self.h.check(not after["carriedCustom"], "unexpected carried custom items predate this cleanup")
        if documented_removal:
            self.h.check(all(not ids for ids in after["customContents"].values()), "documented removal requires every custom storage empty")
            remaining = {key: value for key, value in after["boxes"].items() if value != -1}
            self.h.check(bool(remaining), "expected installed empty test furniture for documented-removal boundary")
            receipt = self.h.lua(r'''
local T=MELensLifecycleTest; local cargo=assert(T.vehicle:getPartById("F700TrunkBX"):getItemContainer())
local rows={}; for i=0,cargo:getItems():size()-1 do local item=cargo:getItems():get(i)
    rows[#rows+1]={id=item:getID(),fullType=item:getFullType()}
end
table.sort(rows,function(a,b) return a.id<b.id end)
T.saved.documentedRemovalMode=true; T.saved.documentedCargo=rows
return {count=#rows,items=rows,emptyInstalledBoxIds={
'''+",".join(str(item_id) for item_id in remaining.values())+r'''}}
''')
            self.h.check(receipt and receipt["count"] == len(after["nativeCargo"]), "clean cargo manifest count mismatch")
            self.h.REPORT["documentedRemovalMode"] = True
            self.h.REPORT["expectedEmptyFurnitureLoss"] = receipt["emptyInstalledBoxIds"]
            self.h.REPORT["fullCleanCargoManifest"] = receipt["items"]
            self.h.record("documented-removal-empty-installed-furniture-boundary", before, after,
                          emptyInstalledFurnitureIds=receipt["emptyInstalledBoxIds"],
                          fullCleanCargoManifest=receipt["items"], fixtureOnly=True,
                          emptyStorageRequired=True, userRemovalWorkflowAcceptance=False)
        else:
            for _ in range(64):
                before = self.snapshot()
                remaining = {key: value for key, value in before["boxes"].items() if value != -1}
                if not remaining: break
                point_code = self.shared.PICK_POINT.replace('(s.level or 1)>=2 and ', '')
                point = self.h.lua(point_code)
                self.h.check(point, "no remaining box can be natively picked")
                part_id = "MELensSpot" + str(int(point["index"]))
                item_id = remaining[part_id]
                expected = dict(before["boxes"]); expected[part_id] = -1
                self.lab.pickup_menu(point)
                after = self.wait(lambda s: s["idle"] and s["boxes"] == expected and item_id in s["inventory"], "native pickup removes only the exact target box")
                row = next((item for item in after["carriedCustom"] if item["id"] == item_id), None)
                self.h.check(row and row["fullType"] == "Base.MELensRV_Box", "picked furniture identity changed")
                self.picked.append({"partId": part_id, "itemId": item_id, "level": point["level"]})
                if discard:
                    self.h.lua(f'local item=getPlayer():getInventory():getItemWithID({item_id}); '
                               'assert(item and item:getFullType()=="Base.MELensRV_Box","fixture disposal identity mismatch"); '
                               'getPlayer():getInventory():Remove(item); return true')
                    self.h.REPORT["fixtureDisposal"] = True
                else:
                    raise AssertionError("One native box pickup passed. Dispose of this custom item manually, or rerun in a fresh phase with --discard-custom-fixtures for explicit fixture disposal.")
            after = self.snapshot()
            self.h.check(all(value == -1 for value in after["boxes"].values()), "bounded box cleanup did not finish")
        self.h.check(not after["carriedCustom"], "custom test furniture still carried")
        if documented_removal:
            # Escape is not consistently bound in the isolated profile; close
            # the native context menu with a real click on its blank backdrop.
            self.lab.input("A", x=10, y=10)
            self.wait(lambda s: self.h.lua('local c=getPlayerContextMenu(0); return not c or not c:isVisible()'),
                      "close the native context menu before exit")
        self.h.lua('local p=getPlayer(); local q=MELens.profileFor(p:getVehicle()); MELens.walkTo(p,q.exitMarker.x,q.exitMarker.z); return true')
        self.wait(lambda s: s["idle"] and not s["pathing"], "at exit marker after cleanup")
        self.lab.input("A", key=18)
        after = self.wait(lambda s: not s["inside"] and s["idle"], "native E exits before removal checkpoint")
        name = ("documented-removal-empty-installed-furniture-boundary" if documented_removal
                else "all-custom-boxes-picked-through-native-menus")
        self.h.record(name, {}, after, boxes=self.picked,
                      customFixtureDisposal=discard, disposalUserWorkflowVerified=False,
                      documentedRemovalMode=documented_removal)
        self.h.capture("lifecycle-clean-outside")
        return after

    def disabled_drive(self):
        self.h.check(self.h.lua('return (not MELens or MELens.VERSION==nil) and MELensRV==nil'), "RVI must be disabled in a fresh process")
        before = self.snapshot()
        self.h.check(not before["inside"], "disabled driving test must start outside")
        approach = self.h.lua(r'''
local p,v=getPlayer(),MELensLifecycleTest.vehicle
ISTimedActionQueue.add(ISPathFindAction:pathToVehicleSeat(p,v,0))
return true
''')
        self.wait(lambda s: s["idle"] and not s["pathing"], "stock KI5 driver-seat approach")
        self.h.lua('ISVehicleMenu.onEnter(getPlayer(),MELensLifecycleTest.vehicle,0); return true')
        self.wait(lambda s: s["seat"] == 0 and s["idle"], "stock KI5 entry from reached driver door", timeout=20)
        self.h.lua('ISTimedActionQueue.add(ISStartVehicleEngine:new(getPlayer())); return true')
        self.wait(lambda s: s["engine"], "stock KI5 engine starts with preserved key", timeout=30)
        self.lab.input("A", key=17, milliseconds=2000)
        driven = self.wait(lambda s: (s["x"]-before["x"])**2+(s["y"]-before["y"])**2 > 1, "stock KI5 vehicle moves through real W input", timeout=15)
        self.lab.input("A", key=57, milliseconds=2000)
        self.wait(lambda s: abs(s["speed"]) < .5, "stock KI5 vehicle stops through Space input", timeout=30)
        self.h.capture("lifecycle-disabled-stock-driving")
        self.lab.input("A", key=18)
        after = self.wait(lambda s: not s["inside"] and s["idle"], "stock native E driver exit")
        self.h.record("ki5-stock-driving-with-rvi-disabled", before, after, driven=driven,
                      queuedDriverEntry=True, actualWAndSpaceAndExit=True,
                      driverEntryFixtureAction="stock ISVehicleMenu.onEnter after native seat path")
        self.h.capture("lifecycle-disabled-stock-outside")
        return after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("clean", "disabled-drive"))
    parser.add_argument("--run", type=Path, default=ROOT / "build/rv/final-lifecycle-206")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--discard-custom-fixtures", action="store_true")
    parser.add_argument("--documented-removal", action="store_true",
                        help="fixture only: leave empty installed boxes for the documented removal boundary")
    args = parser.parse_args()
    output = (args.output or args.run / (args.mode + "-inputs")).resolve()
    lab = None
    try:
        lab = LifecycleActions(args.run.resolve(), output)
        if args.documented_removal and args.mode != "clean":
            raise ValueError("--documented-removal applies only to clean mode")
        lab.h.REPORT["final"] = lab.cleanup(args.discard_custom_fixtures, args.documented_removal) if args.mode == "clean" else lab.disabled_drive()
        print(f"NATIVE_LIFECYCLE_ACTIONS_PASSED {lab.h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        if lab is not None:
            try: lab.h.REPORT["lastSnapshot"] = lab.snapshot()
            except Exception: pass
            path = lab.h.write_report('failed', error)
        else:
            output.mkdir(parents=True, exist_ok=True)
            path = output / "native-feature-tests.json"
            path.write_text(json.dumps({"status": "failed", "nativeInput": False, "preconditionFailure": True,
                                        "error": error}, indent=2) + "\n", encoding="utf-8")
        print(error, flush=True)
        print(f"NATIVE_LIFECYCLE_ACTIONS_FAILED {path}; parent-owned game left running", flush=True)
        return 1
    finally:
        if lab is not None:
            try: lab.h.lua('MEMCNativeLab.releaseKeys(); return true')
            except Exception: pass


if __name__ == "__main__":
    raise SystemExit(main())
