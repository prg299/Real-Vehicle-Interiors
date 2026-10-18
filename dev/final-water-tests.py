"""Native tap tests in a parent-owned, guarded disposable game; import performs no game calls.

Fixtures may set inventory/body/tank state. Menus and actions use only actual
MEMCNativeLab click events, never UI handlers, action queues or complete().
The parent owns launch, save and shutdown, including after failures.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/rv/final-water-tests"


def load_helpers():
    spec = importlib.util.spec_from_file_location("melens_final_features", Path(__file__).with_name("final-feature-tests.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = r'''
local p=getPlayer()
local F=MELensFeatureTest
assert(p and F and F.vehicle and p:getVehicle()==F.vehicle, "tap tests need the standing feature-test player")
assert(not p:isTimedActionInstant(), "tap tests require normal timed actions")
assert(#ISTimedActionQueue.getTimedActionQueue(p).queue==0, "wait for idle before tap setup")
local v,inv=F.vehicle,p:getInventory()
local M,U,P=MELens,MELens.Utilities,MELens.Parts
if M.Dashboard.instance then M.Dashboard.instance:close() end -- fixture cleanup only
local W={player=p,vehicle=v,knownClean={},setupOnly=true}
MELensWaterTest=W
W.originalGodMod=p:isGodMod()
p:setGodMod(false) -- normal thirst must not be reset by the test character's god mode
local function own(key,full,name)
    local i=inv:getFirstEvalRecurse(function(c) return c:getModData().MELensWaterFixture==key end)
    if not i then i=inv:AddItem(full) end
    assert(i and i:getFullType()==full,"missing tap fixture "..full)
    if i:getContainer()~=inv then local c=i:getContainer(); if c then c:Remove(i) end; inv:AddItem(i) end
    i:getModData().MELensWaterFixture=key
    i:setName(name)
    return i
end
W.bottle=own("bottle","Base.WaterBottle","Tap test bottle")
local fc=W.bottle:getFluidContainer()
assert(fc,"tap bottle has no real fluid component")
if fc:getAmount()>0 then fc:removeFluid(fc:getAmount()) end
W.bottle:syncItemFields()
W.dirty=own("bandage","Base.BandageDirty","Tap test dirty bandage")
assert(W.dirty:getItemAfterCleaning()=="Base.Bandage","native dirty bandage fixture has no cleaning replacement")
W.dirty:setFavorite(true)
local all=inv:getItems()
for i=0,all:size()-1 do
    local item=all:get(i)
    if item:getFullType()=="Base.Bandage" then W.knownClean[tostring(item:getID())]=true end
end
W.bandageWater=ISWashClothing.GetRequiredWater(W.dirty)
assert(W.bandageWater<15,"unexpected native bandage water requirement")
local tank=U.waterState(v)
assert(tank,"camper has no water tank")
tank.part:getModData().water=20
tank.part:getModData().tainted=false
U.transmit(v,tank.part)
p:getStats():set(CharacterStat.THIRST,0.3)
local visual=p:getHumanVisual()
for i=0,BloodBodyPartType.MAX:index()-1 do
    local part=BloodBodyPartType.FromIndex(i)
    visual:setBlood(part,0); visual:setDirt(part,0)
end
visual:setDirt(BloodBodyPartType.FromIndex(0),1)
visual:setBlood(BloodBodyPartType.FromIndex(1),0.5)
sendHumanVisual(p)

function W.pickPoint()
    local profile=M.profileFor(v)
    local offset=v:getScript():getModel():getOffset()
    local vec,origin=Vector3f.new(),Vector3f.new()
    local base=v:getWorldPos(0,0,0,origin):z()
    local zoom=getCore():getZoom(p:getPlayerNum())
    for index,spot in ipairs(profile.spots or {}) do
        local part=P.spotPart(v,index)
        local piece=P.pieceAt(part)
        if piece=="kitchen" or piece=="washroom" then
            local _,depth,height=P.footprint(spot,piece)
            for _,along in ipairs({0,-0.15,0.15}) do
                for _,out in ipairs({depth/2,depth*0.8,depth*0.2}) do
                    local x,z=P.spotPoint(spot,along,out)
                    local h=profile.floorY+(spot.rise or 0)+height-0.02
                    v:getWorldPos(offset:x()+x,offset:y()+h,offset:z()+z,vec)
                    local sx,sy=ISCoordConversion.ToScreen(vec:x(),vec:y(),base+(offset:y()+h)/2.44949)
                    local hit=M.Interact.pick(v,profile,sx,sy)
                    local px,py=math.floor(sx/zoom+0.5),math.floor(sy/zoom+0.5)
                    if hit and hit.index==index and px>20 and px<getCore():getScreenWidth()-20
                            and py>80 and py<getCore():getScreenHeight()-40 then
                        return {x=px,y=py,index=index,header=part:getInventoryItem():getDisplayName()}
                    end
                end
            end
        end
    end
    error("no visible unobstructed tap furniture point found")
end

function W.snapshot()
    local r=F.snapshot()
    local body=p:getHumanVisual()
    local dirtyParts=0
    for i=0,BloodBodyPartType.MAX:index()-1 do
        local part=BloodBodyPartType.FromIndex(i)
        if body:getBlood(part)+body:getDirt(part)>0 then dirtyParts=dirtyParts+1 end
    end
    local fc=W.bottle:getFluidContainer()
    r.tap={thirst=p:getStats():get(CharacterStat.THIRST),dirtyParts=dirtyParts,
        bottleId=W.bottle:getID(),bottleAmount=fc:getAmount(),bottleCapacity=fc:getCapacity(),
        bottlePureWater=fc:isPureFluid(Fluid.Water),bottleName=W.bottle:getDisplayName(),
        dirtyId=W.dirty:getID(),dirtyInMainInventory=inv:contains(W.dirty),dirtyName=W.dirty:getDisplayName(),
        dirtyBloodLevel=W.dirty:getBloodLevel(),
        dirtyAfterCleaning=W.dirty:getItemAfterCleaning(),
        bandageWater=W.bandageWater,cleanBandages={}}
    local items=inv:getItems()
    for i=0,items:size()-1 do
        local item=items:get(i)
        if item:getFullType()=="Base.Bandage" and not W.knownClean[tostring(item:getID())] then
            table.insert(r.tap.cleanBandages,{id=item:getID(),favorite=item:isFavorite()})
        end
    end
    local root=getPlayerContextMenu(p:getPlayerNum())
    r.menus={}
    local seen={}
    local function menu(m)
        if not m or seen[m] or not m:isVisible() then return end
        seen[m]=true
        local entries={}
        for i,option in ipairs(m.options or {}) do
            local y=m:getItemY(i)+m.itemHgt/2
            if y>=m:getY() and y<=m:getY()+m:getHeight() then
                entries[#entries+1]={name=tostring(option.name),enabled=not option.notAvailable and not option.isDisabled,
                    submenu=option.subOption~=nil,x=m:getX()+m:getWidth()/2,y=y}
            end
        end
        r.menus[#r.menus+1]={x=m:getX(),y=m:getY(),options=entries}
    end
    menu(root)
    if root then for _,m in ipairs(root.instanceMap or {}) do menu(m) end end
    return r
end
return W.snapshot()
'''


def read_state(h):
    state = h.lua("return MELensWaterTest.snapshot()")
    h.check(isinstance(state, dict) and isinstance(state.get("tap"), dict), "missing native tap snapshot")
    state["queue"] = h._sequence(state.get("queue"))
    state["menus"] = h._sequence(state.get("menus"))
    state["tap"]["cleanBandages"] = h._sequence(state["tap"].get("cleanBandages"))
    for menu in state["menus"]:
        menu["options"] = h._sequence(menu.get("options"))
    return state


def poll(h, predicate, timeout=75, label="native tap state", seen=None):
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        last = read_state(h)
        if seen is not None:
            seen.update(str(action.get("type", "")) for action in last["queue"])
        if time.monotonic() >= h._input_release and predicate(last):
            return last
        time.sleep(.10)
    raise AssertionError(f"Timeout waiting for {label}: {json.dumps(last, ensure_ascii=False)}")


def native_click(h, x, y, label, right=False):
    x, y = int(x), int(y)
    h.check(0 <= x < 1280 and 0 <= y < 720, f"offscreen native input: {label} {x},{y}")
    api = "clickButtonAt" if right else "clickAt"
    args = f"{x},{y},1" if right else f"{x},{y}"
    h.lua(f"MEMCNativeLab.{api}({args}); return true")
    h._input_release = time.monotonic() + .60
    h.REPORT["nativeInput"] = True
    h.REPORT.setdefault("inputs", []).append({"action": label, "api": f"MEMCNativeLab.{api}", "x": x, "y": y})


def menu_option(state, label):
    matches = [option for menu in state["menus"] for option in menu["options"] if option["name"] == label]
    if not matches:
        return None
    if len(matches) != 1:
        raise AssertionError(f"ambiguous context-menu label {label!r}: {matches}")
    return matches[0]


def select_tap(h, labels, case):
    """Open the genuine world menu; click each parent and finally its action once."""
    before = poll(h, lambda s: s["queueCount"] == 0, label="idle before tap menu")
    point = h.lua("return MELensWaterTest.pickPoint()")
    native_click(h, point["x"], point["y"], f"{case}:open-world-menu", right=True)
    for label in [point["header"], *labels]:
        state = poll(h, lambda s: menu_option(s, label) is not None, timeout=8, label=f"visible menu {label}")
        option = menu_option(state, label)
        h.check(option["enabled"], f"native menu option disabled: {label}; {state['menus']}")
        native_click(h, option["x"], option["y"], f"{case}:{label}")
    return before


def finish(h, name, before, predicate, expected_action):
    seen = set()
    after = poll(h, lambda s: s["queueCount"] == 0 and predicate(s), label=name, seen=seen)
    h.check(any(expected_action in action for action in seen), f"{name}: expected production action not observed: {seen}")
    return after, sorted(seen)


def run_water_cases(h=None):
    if h is None:
        h = load_helpers()
        h.configure(OUTPUT)
    h.REPORT["scope"] = "four native tap interactions in an already owned disposable single-player game"
    h.REPORT["fixtureState"] = "20 L clean water, thirst, two dirty body parts, empty bottle and dirty bandage"
    h.lua(FIXTURE)
    initial = read_state(h)
    h.check(initial["player"]["inside"] and not initial["player"]["timedActionInstant"], "tap fixture needs normal standing actions")
    h.capture("water-initial")
    labels = h.lua('return {drink=getText("ContextMenu_Drink"),fill=getText("ContextMenu_Fill"),'
                   'washBody=getText("ContextMenu_MELens_WashYourself"),washClothes=getText("ContextMenu_MELens_WashClothes")}')

    before = select_tap(h, [labels["drink"]], "drink")
    after, seen = finish(h, "tap-drink", before,
                   lambda s: s["tap"]["thirst"] < before["tap"]["thirst"] - .1
                   and s["utilities"]["water"] < before["utilities"]["water"] - .1, "MELensDrinkFromTank")
    h.check(abs((before["utilities"]["water"] - after["utilities"]["water"]) - before["tap"]["thirst"] * 2) < .05,
            "native drink did not consume the thirst-limited amount")
    h.record("tap-drink", before, after, observedTimedActions=seen, uiHandlersInvokedDirectly=False)

    current = read_state(h)
    before = select_tap(h, [labels["fill"], current["tap"]["bottleName"]], "fill-bottle")
    after, seen = finish(h, "tap-fill-bottle", before,
                   lambda s: s["tap"]["bottleAmount"] >= s["tap"]["bottleCapacity"] - .001, "MELensFillFromTank")
    h.check(after["tap"]["bottleId"] == before["tap"]["bottleId"] and after["tap"]["bottlePureWater"], "tap bottle identity/fluid changed")
    h.check(abs((before["utilities"]["water"] - after["utilities"]["water"])
                - (after["tap"]["bottleAmount"] - before["tap"]["bottleAmount"])) < .001, "tap bottle water not conserved")
    h.record("tap-fill-bottle", before, after, observedTimedActions=seen, uiHandlersInvokedDirectly=False)

    before = select_tap(h, [labels["washBody"]], "wash-body")
    after, seen = finish(h, "tap-wash-yourself", before, lambda s: s["tap"]["dirtyParts"] == 0, "MELensWashFromTank")
    h.check(abs((before["utilities"]["water"] - after["utilities"]["water"])
                - before["tap"]["dirtyParts"] * .5) < .001, "body washing water not conserved")
    h.record("tap-wash-yourself", before, after, observedTimedActions=seen, uiHandlersInvokedDirectly=False)

    current = read_state(h)
    before = select_tap(h, [labels["washClothes"], current["tap"]["dirtyName"]], "wash-bandage")
    after, seen = finish(h, "tap-wash-dirty-bandage", before,
                   lambda s: not s["tap"]["dirtyInMainInventory"] and len(s["tap"]["cleanBandages"]) == 1,
                   "MELensWashClothing")
    h.check(after["tap"]["cleanBandages"][0]["favorite"], "clean bandage lost favorite flag")
    h.check(after["tap"]["cleanBandages"][0]["id"] != before["tap"]["dirtyId"], "dirty bandage was not replaced")
    h.check(abs((before["utilities"]["water"] - after["utilities"]["water"]) - before["tap"]["bandageWater"]) < .001,
            "bandage cleaning water not conserved")
    h.record("tap-wash-dirty-bandage", before, after, observedTimedActions=seen, uiHandlersInvokedDirectly=False)
    h.capture("water-four-actions-complete")
    return read_state(h)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--endpoint", default=None)
    args = parser.parse_args()
    h = load_helpers()
    h.configure(args.output, args.endpoint)
    try:
        h.REPORT["final"] = run_water_cases(h)
        path = h.write_report("passed")
        print(f"NATIVE_WATER_TESTS_PASSED {path}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT["lastSnapshot"] = read_state(h)
        except Exception:
            h.REPORT["lastSnapshot"] = None
        path = h.write_report("failed", error)
        print(error, flush=True)
        print(f"NATIVE_WATER_TESTS_FAILED {path}; parent-owned game left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
