"""Real propane Floor cargo: native model fit, inventory UI and cold-load identity.

Run only through run-heavy in the parent's already guarded disposable game.
Spawning/positioning, inventory-window selection, a temporary 50-capacity bag
with 100 percent weight reduction, unlimited carry, clearing unrelated unequipped actor items, and repeated floor lifecycle
callbacks are labelled fixtures. Loot All/Transfer All use real mouse input,
inventory UI dispatch and timed actions. No item is directly moved by this test.
The following service-save stage saves the preserved, marked vehicles.
Both factory and returned tanks receive full native-size geometry validation.
Unpositioned returned items use production matching-type factory floor cells;
the test does not assign item positions after either inventory transfer.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("Base.VanKnobCreekGas", "VanillaVan"),
    ("Base.StepVan_Propane", "VanillaStepVan"),
    ("Base.86fordE150knobCreek", "E150Short"),
    ("Base.85chevyStepVanPropane", "ChevyStepVan"),
]
MARKER = "propane-cargo-v1"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT/"dev"/(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SNAPSHOT = r"""
local M,P,L=MELens,MELens.Parts,MELens.Loose
local v=assert(MELensPropaneAuditVehicle,"propane fixture not selected")
local pr=assert(M.profileFor(v));local part=assert(L.floorPart(v));local c=assert(part:getItemContainer())
local visible,display={},{}
for _,e in ipairs(L.list(v,pr)) do
 visible[e.id]=e;display[#display+1]={id=e.id,t=e.t,x=e.x,y=e.y,z=e.z,r=e.r,s=e.s}
end
local floor={};local pending=false
for i=0,c:getItems():size()-1 do
 local item=c:getItems():get(i);local size=MELensRV.itemSize(item)
 local entry=L.entry(v,item:getID());local shown=visible[item:getID()];local corners={}
 if size and shown then
  local sx,sy,sz=string.match(size,"([^,]+),([^,]+),([^,]+)")
  local hx,hz=L.half(tonumber(sx),tonumber(sz),shown.r)
  for _,x in ipairs({shown.x-hx,shown.x,shown.x+hx}) do
   for _,z in ipairs({shown.z-hz,shown.z,shown.z+hz}) do
    corners[#corners+1]=L.inRoom(pr,x,z)
   end
  end
 end
 if not size then pending=true end
 floor[#floor+1]={id=item:getID(),t=item:getFullType(),size=size,
  hasModel=MELensRV.hasItemModel(item),entry=entry,display=shown,corners=corners}
end
table.sort(floor,function(a,b)return a.id<b.id end)
local function contents(container)
 local ids={};for i=0,container:getItems():size()-1 do ids[#ids+1]=container:getItems():get(i):getID() end
 table.sort(ids);return ids
end
local native,fit={},{};
for i=0,v:getPartCount()-1 do
 local p=v:getPartByIndex(i);local container=p:getItemContainer()
 if container and not p:getId():find("^MELens") then
  native[p:getId()]={capacity=container:getCapacity(),ids=contents(container)}
 end
end
for i,s in ipairs(pr.spots) do if s.factory then
 local p=P.spotPart(v,i);local item=p:getInventoryItem()
 fit[#fit+1]={index=i,piece=P.pieceAt(p),id=item and item:getID(),ids=contents(p:getItemContainer())}
end end
local positions={};for id,e in pairs(L.positions(v,false) or {}) do positions[id]=e end
local inv=getPlayer():getInventory();local actor={}
local function held(container)
for i=0,container:getItems():size()-1 do
 local item=container:getItems():get(i);if item:getFullType()=="Base.PropaneTank" then actor[#actor+1]=item:getID() end
end
end
held(inv)
if MELensPropaneCarryFixture then held(MELensPropaneCarryFixture.bag:getInventory()) end
table.sort(actor)
local queue={};for _,a in ipairs(ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue) do queue[#queue+1]=tostring(a.Type) end
return {world=getWorld():getWorld(),script=v:getScriptName(),marker=v:getModData().RVIPropaneAudit,
 factoryLayout=v:getModData().MELensFactoryLayout,floorInitialized=part:getModData()[P.INITIALIZED_KEY],
 floorY=pr.floorY,capacity=c:getCapacity(),weight=c:getCapacityWeight(),floor=floor,positions=positions,
 planned=pr.factoryFloor,solids=L.solids(v,pr),nativeCargo=native,fittings=fit,
 actorTankIds=actor,queue=queue,pending=pending,display=display}
"""


def snapshot(h):
    state = h.lua(SNAPSHOT)
    for key in ("floor", "planned", "solids", "fittings", "actorTankIds", "queue", "display"):
        state[key] = h._sequence(state.get(key))
    for row in state["floor"]:
        row["corners"] = h._sequence(row.get("corners"))
    return state


def ids(state):
    return [row["id"] for row in state["floor"]]


def persistence(state):
    # Runtime sizes/corners/queue are diagnostic, not saved state.
    return {key: state[key] for key in (
        "world", "script", "marker", "factoryLayout", "floorInitialized",
        "capacity", "weight", "positions", "display", "nativeCargo", "fittings"
    )} | {"floor": [{"id": row["id"], "t": row["t"]} for row in state["floor"]]}


def wait(h, predicate, label, timeout=120):
    deadline = time.monotonic()+timeout
    observed = set()
    while True:
        state = snapshot(h)
        observed.update(state["queue"])
        if predicate(state):
            return state, sorted(observed)
        h.check(time.monotonic() < deadline, label)
        time.sleep(.15)


def validate_factory(h, state, spec, require_saved=True):
    planned, floor = state["planned"], state["floor"]
    h.check(2 <= len(floor) <= 6 and len(floor) == len(planned), "factory Floor lost or duplicated cylinders")
    h.check(len(set(ids(state))) == len(floor), "duplicate real cylinder ID")
    h.check(state["floorInitialized"] is True and state["factoryLayout"] == "cargo-service-1", "factory initialization stamp missing")
    h.check(state["weight"] <= state["capacity"], "Floor exceeds inventory capacity")
    h.check(abs(state["floorY"]-spec["floorY"]) < .0001, "native floor differs from source measurement")
    h.check(len(state["fittings"]) == 1 and state["fittings"][0]["piece"] == "metalcase", "propane has extra furniture")
    solids = [(s["x0"], s["x1"], s["z0"], s["z1"]) for s in state["solids"]]
    used = set()
    for item in floor:
        h.check(item["t"] == "Base.PropaneTank" and item["hasModel"], "cylinder is not the real native world item")
        size = [float(v) for v in item["size"].split(",")]
        h.check(all(v > 0 for v in size), "invalid native model dimensions")
        entry = item.get("display")
        h.check(entry is not None and entry["s"] == 0, "cylinder has no rendered Floor placement")
        if require_saved:
            h.check(item.get("entry") is not None, "factory cylinder has no saved placement")
        match = next((i for i,p in enumerate(planned) if abs(entry["x"]-p["x"]) < .0001
                      and abs(entry["z"]-p["z"]) < .0001 and entry["r"] == p["r"]), None)
        h.check(match is not None and match not in used, "factory placement differs from declared source or duplicates a point")
        used.add(match)
        p = planned[match]
        # Native size reports passenger-space x/y/z; no model scaling is permitted.
        h.check(size[0] <= 2*p["hx"]+.0001 and size[2] <= 2*p["hz"]+.0001,
                f"native tank exceeds planned footprint: {size} vs {p}")
        h.check(abs(entry["y"]-state["floorY"]) < .0001 and entry["y"]+size[1] <= spec["ceiling"]-.02,
                f"native tank intersects roof/floor: {size}")
        h.check(len(item["corners"]) == 9 and all(item["corners"]), "native full footprint crosses room lining")
        x0,x1 = entry["x"]-size[0]/2,entry["x"]+size[0]/2
        z0,z1 = entry["z"]-size[2]/2,entry["z"]+size[2]/2
        h.check(abs(entry["x"])-size[0]/2 >= .175, "native tank narrows central aisle")
        for a,b,c,d in solids:
            h.check(not (x0 < b and x1 > a and z0 < d and z1 > c), "native tank intersects solid/another cylinder")
        solids.append((x0,x1,z0,z1))


def windows(h, target="bag"):
    h.lua(r"""local p=getPlayer();local w=getPlayerInventory(0);local loot=getPlayerLoot(0)
w:setVisible(true);w.isCollapsed=false;w.pin=true;w:clearMaxDrawHeight();w:setX(80);w:setY(50);w:setHeight(350)
loot:setVisible(true);loot.isCollapsed=false;loot.pin=true;loot:clearMaxDrawHeight();loot:setX(660);loot:setY(50);loot:setHeight(350)
loot:refreshBackpacks();w:refreshBackpacks()
w:setNewContainer(assert(MELensPropaneCarryFixture).bag:getInventory());loot:setNewContainer(MELens.Loose.floorContainer(MELensPropaneAuditVehicle))
return true""")
    time.sleep(.5)
    # Refresh may choose a nearby cupboard; fixture-select the actual Floor again.
    h.lua("getPlayerLoot(0):setNewContainer(MELens.Loose.floorContainer(MELensPropaneAuditVehicle));return true")
    if target == "body":
        h.lua("getPlayerInventory(0):setNewContainer(getPlayer():getInventory());return true")
    h.check(h.lua("return getPlayerLoot(0).inventoryPane.inventory==MELens.Loose.floorContainer(MELensPropaneAuditVehicle)"),
            "Floor inventory UI target changed")


def click(h, cargo, window, key, label):
    point = cargo.button(h, window, key)
    h.check(point.get("hitTest") is not False, "inventory control is obscured")
    h.lua(f'MEMCNativeLab.clickAt({int(point["x"])},{int(point["y"])});return true')
    h.REPORT["inputs"].append(dict(action=label, api="MEMCNativeLab.clickAt", **point))
    h.REPORT["nativeInput"] = True
    time.sleep(.65)


def clean_capture(h, label, count):
    h.lua("getPlayerInventory(0):setVisible(false);getPlayerLoot(0):setVisible(false);return true")
    def renderer():
        status=h.lua("return MELensRV.looseStatus()")
        values=dict(re.findall(r"(entries|drawn|disabled)=([^ ]+)",status))
        return status,values
    initial,baseline=renderer()
    deadline=time.monotonic()+20
    while True:
        status,values=renderer()
        h.check(values.get("disabled")=="false" and " error=" not in status,"native loose-item renderer failed: "+status)
        if int(values["entries"])==count and (count==0 or int(values["drawn"])>int(baseline["drawn"])):
            break
        h.check(time.monotonic()<deadline,"native item draw list did not become ready: "+status)
        time.sleep(.1)
    time.sleep(.35)
    image=h.capture(label)
    h.REPORT.setdefault("renderReceipts",[]).append(dict(image=image,expectedEntries=count,
                                                        before=initial,ready=status))
    return image


def detach(h):
    # spawn_one removes MELensTest.vehicle; retain only this owned saved fixture.
    h.lua(r"""local v=MELensPropaneAuditVehicle;local p=getPlayer()
if v and p:getVehicle()==v then v:exit(p) end
if MELensTest then
 if MELensTest.vehicle==v then MELensTest.vehicle=nil end
 for name,entry in pairs(MELensTest.all or {}) do if entry==v then MELensTest.all[name]=nil end end
end
MELensPropaneAuditVehicle=nil
return true""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-source")
    args = parser.parse_args()
    # Run folders are owned junctions into RVI-TestArtifacts. Validate the input
    # name lexically, retaining the workspace path instead of rejecting its target.
    run_name = os.environ["RVI_CAPTURE_RUN"]
    if not run_name or Path(run_name).name != run_name or run_name in (".", ".."):
        raise ValueError("capture run must be one workspace artifact folder name")
    run = ROOT/"build/rv"/run_name
    h = load("final-feature-tests")
    h.configure(run/("propane-cargo-reload" if args.verify_source else "propane-cargo"))
    session = json.loads((run/"native-session.json").read_text("utf-8-sig"))
    h.SCREENS = Path(next(x.split("=",1)[1] for x in session["command"] if x.startswith("-cachedir=")))/"Screenshots"
    carry = None
    try:
        if args.verify_source:
            if Path(args.verify_source).name != args.verify_source or args.verify_source in (".", ".."):
                raise ValueError("verify source must be one workspace artifact folder name")
            source = ROOT/"build/rv"/args.verify_source/"propane-cargo/expected.json"
            expected = json.loads(source.read_text("utf-8"))
            actual = {}
            for name, _ in CASES:
                marker = MARKER+":"+name
                found = h.lua(f"""local matches={{}};local it=getCell():getVehicles():iterator()
while it:hasNext() do local v=it:next()
 if v:getScriptName()=={json.dumps(name)} and v:getModData().RVIPropaneAudit=={json.dumps(marker)} then matches[#matches+1]=v end
end
assert(#matches==1,"saved propane fixture missing/duplicated")
MELensPropaneAuditVehicle=matches[1];return true""")
                h.check(found, "saved propane vehicle not loaded")
                state = snapshot(h)
                actual[name] = persistence(state)
                h.check(actual[name] == expected["vehicles"][name],
                        "cold load replaced cylinders, positions, capacity, initialized stamp, tools or original cargo: "+name)
                h.record("cold-load-"+name.split(".")[-1].lower(), expected["vehicles"][name], actual[name])
            h.lua("MELensPropaneAuditVehicle=nil;return true")
            h.REPORT["saveReload"] = {"expected": expected, "actual": actual,
                                     "savedBy": "following service-save stage"}
        else:
            # A failed previous pass may retain marked vehicles at these exact
            # fixture positions. Remove only this test's disposable marked cars
            # before repeating; overlapping spawns can overturn the next van.
            h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);getPlayerInventory(0):setVisible(false);getPlayerLoot(0):setVisible(false)
local remove={};local it=getCell():getVehicles():iterator()
while it:hasNext() do local v=it:next();local m=v:getModData().RVIPropaneAudit
 if type(m)=="string" and m:find("^propane%-cargo%-v1:") then remove[#remove+1]=v end end
for _,v in ipairs(remove) do
 if MELensTest and MELensTest.vehicle==v then MELensTest.vehicle=nil end
 if MELensTest then for n,x in pairs(MELensTest.all or {}) do if x==v then MELensTest.all[n]=nil end end end
 v:permanentlyRemove()
end
MELensPropaneAuditVehicle=nil
local inv=p:getInventory();for i=inv:getItems():size()-1,0,-1 do
 local item=inv:getItems():get(i);if not p:isEquipped(item) then inv:Remove(item) end end
return true''')
            carry = h.lua("local p=getPlayer();local old={carry=p:isUnlimitedCarry(),instant=p:isTimedActionInstant()};p:setUnlimitedCarry(true);p:setTimedActionInstantCheat(false);return old")
            h.lua('''local p=getPlayer();local old=p:getClothingItem_Back()
local bag=assert(p:getInventory():AddItem("Base.Bag_DuffelBag"))
bag:setCapacity(50);bag:getInventory():setCapacity(50);bag:setWeightReduction(100)
p:setClothingItem_Back(bag);MELensPropaneCarryFixture={bag=bag,oldBack=old};return true''')
            h.REPORT["fixtures"] = [
                "four explicit vanilla/KI5 vehicle spawns and real Interact entry",
                "actor positioning and inventory-window/container selection",
                "unlimited carry enabled for 20-60kg cargo; ordinary timed actions retained",
                "temporary test bag capacity 50 and weight reduction 100 percent; loads above 50kg use a second native UI batch into body inventory; cylinder weights are unchanged",
                "unrelated unequipped actor inventory removed before each transfer case",
                "repeat createFloor/initFloor after native Loot All to test no-refill",
                "vehicles marked and retained for following service-save whole-world save",
            ]
            expected = {"marker": MARKER, "vehicles": {}}
            cargo, beds = load("cargo-loot-tests"), load("bed-tests")
            for index,(name,key) in enumerate(CASES):
                h.lua(f"""MELensMedia.cameraOff();local p=getPlayer()
if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY({10154.5+8*index});p:setLastX(10813.5);p:setLastY({10154.5+8*index})
return true""")
                beds.enter(h,name,"N")
                h.lua(f"""MELensPropaneAuditVehicle=MELensTest.vehicle
MELensPropaneAuditVehicle:getModData().RVIPropaneAudit={json.dumps(MARKER+":"+name)}
local p=getPlayer();local inv=p:getInventory()
for i=inv:getItems():size()-1,0,-1 do local item=inv:getItems():get(i);if not p:isEquipped(item) then inv:Remove(item) end end
return true""")
                before,_ = wait(h, lambda s: not s["pending"], "native propane model did not load", 30)
                spec = json.loads((ROOT/"tools-src/vehicles/specs"/(key+".json")).read_text())
                validate_factory(h,before,spec)
                original = set(ids(before))
                clean_capture(h,key.lower()+"-factory-cylinders",len(original))
                windows(h)
                click(h,cargo,"getPlayerLoot(0)","IGUI_invpage_Loot_all",key+"-loot-all")
                first_batch,seen = wait(h, lambda s: bool(s["actorTankIds"]) and not s["queue"],
                                        "native first Loot All batch did not finish")
                if first_batch["floor"]:
                    h.check(set(ids(first_batch)) | set(first_batch["actorTankIds"]) == original,
                            "first batch lost tank IDs")
                    windows(h,"body")
                    click(h,cargo,"getPlayerLoot(0)","IGUI_invpage_Loot_all",key+"-loot-all-remainder-to-body")
                emptied,seen_second = wait(h, lambda s: not s["floor"] and not s["queue"]
                                          and original.issubset(set(s["actorTankIds"])),
                                          "native Loot All did not transfer all original tank IDs")
                seen += seen_second
                # Let production pruning remove the old saved placement records.
                emptied,_ = wait(h, lambda s: not s["positions"], "looted tanks retain ghost placement records", 15)
                h.lua("local v=MELensPropaneAuditVehicle;local p=MELens.Loose.floorPart(v);MELens.Parts.createFloor(v,p);MELens.Parts.initFloor(v,p);return true")
                time.sleep(.6)
                no_refill = snapshot(h)
                h.check(not no_refill["floor"] and not no_refill["positions"], "initialized empty Floor was restocked")
                h.check(len(no_refill["actorTankIds"]) == len(original)
                        and set(no_refill["actorTankIds"]) == original, "Loot All duplicated/lost native tanks")
                h.lua("getPlayerInventory(0):setVisible(false);getPlayerLoot(0):setVisible(false);return true")
                clean_capture(h,key.lower()+"-emptied-cylinders",0)
                body_ids=h.lua('''local ids={};local inv=getPlayer():getInventory()
for i=0,inv:getItems():size()-1 do local item=inv:getItems():get(i)
 if item:getFullType()=="Base.PropaneTank" then ids[#ids+1]=item:getID() end end
return ids''')
                if h._sequence(body_ids):
                    windows(h,"body")
                    click(h,cargo,"getPlayerInventory(0)","IGUI_invpage_Transfer_all",key+"-return-body-remainder")
                    wait(h,lambda s: bool(s["floor"]) and not s["queue"],"body return batch did not finish")
                windows(h)
                click(h,cargo,"getPlayerInventory(0)","IGUI_invpage_Transfer_all",key+"-transfer-all-floor")
                returned,seen_return = wait(h, lambda s: set(ids(s)) == original and not s["queue"]
                                           and not s["actorTankIds"],
                                           "native Transfer All did not return the same tanks to Floor")
                h.check(len(ids(returned)) == len(original), "Transfer All duplicated tank IDs")
                validate_factory(h,returned,spec,require_saved=False)
                h.check(any("Transfer" in action for action in seen+seen_return),
                        "no inventory transfer timed action was observed")
                h.check(returned["capacity"] == before["capacity"], "UI transfer changed Floor capacity")
                h.check(returned["nativeCargo"] == before["nativeCargo"]
                        and returned["fittings"] == before["fittings"], "UI transfer altered original vehicle cargo or tool cabinet")
                h.check(set(returned["positions"]).issubset({str(int(i)) for i in original}),
                        "Floor has position records for nonexistent/duplicate items")
                h.lua("getPlayerInventory(0):setVisible(false);getPlayerLoot(0):setVisible(false);return true")
                clean_capture(h,key.lower()+"-returned-cylinders",len(original))
                h.record(key+"-real-floor-cargo",before,returned,
                         emptied=no_refill,observedTimedActions=sorted(set(seen+seen_return)),
                         nativeBoundsValidated=True,uiHandlersInvokedDirectly=False,
                         returnCoordinates="production orphan placement selects free matching-type factory floor cells; no test position assignments")
                expected["vehicles"][name] = persistence(returned)
                detach(h)
            (h.OUTPUT/"expected.json").write_text(json.dumps(expected,indent=2)+"\n",encoding="utf-8")
            h.REPORT["persistencePrepared"] = "expected.json; following service-save must save the retained fixtures before cold-load verification"
        h.REPORT["scope"] = __doc__
        h.REPORT["unverified"] = ["dedicated server", "ordinary carry-limit behavior",
                                "Save/Continue menu input"]
        h.write_report("passed")
        return 0
    except Exception:
        error = traceback.format_exc()
        print(error,flush=True)
        try:h.capture("failure")
        except Exception:pass
        h.write_report("failed",error)
        return 1
    finally:
        if carry is not None:
            try:
                h.lua(f"local p=getPlayer();p:setUnlimitedCarry({str(carry['carry']).lower()});p:setTimedActionInstantCheat({str(carry['instant']).lower()});return true")
                h.lua('''local f=MELensPropaneCarryFixture;if f then local p=getPlayer()
p:setClothingItem_Back(f.oldBack)
if f.bag:getInventory():isEmpty() then p:getInventory():Remove(f.bag);MELensPropaneCarryFixture=nil end end;return true''')
            except Exception:pass


if __name__ == "__main__":
    raise SystemExit(main())
