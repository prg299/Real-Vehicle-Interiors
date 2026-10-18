"""Native entry, seating and Dashboard checks; importing performs no game calls.

Run after feature-fixture.lua in the parent's disposable native game. Fixtures
only position the test character at the exit/entry and read menu geometry.
Every tested feature uses real mouse/keyboard events. No game lifecycle control.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/rv/final-interior-tests"


def load_helpers():
    spec = importlib.util.spec_from_file_location("melens_interior_tap_driver", Path(__file__).with_name("final-water-tests.py"))
    tap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tap)
    return tap, tap.load_helpers()


FIXTURE = r'''
local p,F=getPlayer(),MELensFeatureTest
assert(p and F and F.vehicle and F.snapshot,"load the feature fixture before interior checks")
local v,M=F.vehicle,MELens
assert(p:getVehicle()==v and M.isStanding(p),"interior checks need the standing test player")
assert(#ISTimedActionQueue.getTimedActionQueue(p).queue==0 and not M.pathing(p),"interior checks need idle player")
assert(not p:isTimedActionInstant(),"interior checks require normal timed actions")
assert(v:isStopped(),"interior checks require stopped vehicle")
local T={player=p,vehicle=v,profile=M.profileFor(v)}
MELensInteriorTest=T
local P=M.Parts
function T.snapshot()
    local r=F.snapshot()
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
    local d,profile=M.Dashboard.instance,T.profile
    local inside=p:getVehicle()==v
    local seat=inside and v:getSeat(p) or -1
    local passenger=seat>=0 and v:getScript():getPassenger(seat)
    local id=passenger and passenger:getId()
    local pose=id and P.seatPose(v,profile,id)
    r.interior={inside=inside,standing=inside and M.isStanding(p),seat=seat,seatId=id,
        kind=id and P.seatKindAt(v,profile,id),pose=p:getVariableString("damnPosition"),
        expectedPose=pose and pose.pose,pathing=M.pathing(p),debug=M.debugState(),
        enterKey=getCore():getKey("Interact"),exitMarker=profile.exitMarker,
        nearWayIn=not inside and M.nearWayIn(p,v,profile)}
    if d and d:isVisible() and d.closeBox then
        r.interior.closePoint={x=d:getX()+d.closeBox.x+d.closeBox.w/2,
            y=d:getY()+d.closeBox.y+d.closeBox.h/2}
    end
    return r
end
function T.point(wanted)
    local profile=T.profile
    local offset=v:getScript():getModel():getOffset()
    local vec,origin=Vector3f.new(),Vector3f.new()
    local base=v:getWorldPos(0,0,0,origin):z()
    local zoom=getCore():getZoom(p:getPlayerNum())
    for index,spot in ipairs(profile.spots or {}) do
        local part=P.spotPart(v,index)
        local piece=P.pieceAt(part)
        if piece==wanted or index==wanted then
            local length,depth,height=P.footprint(spot,piece)
            for _,along in ipairs({0,-length*0.25,length*0.25}) do
                for _,out in ipairs({depth/2,depth*0.8,depth*0.2}) do
                    for _,lower in ipairs({0.02,0.08,0.15}) do
                        local x,z=P.spotPoint(spot,along,out)
                        local h=profile.floorY+(spot.rise or 0)+height-lower
                        v:getWorldPos(offset:x()+x,offset:y()+h,offset:z()+z,vec)
                        local sx,sy=ISCoordConversion.ToScreen(vec:x(),vec:y(),base+(offset:y()+h)/2.44949)
                        local hit=M.Interact.pick(v,profile,sx,sy)
                        local px,py=math.floor(sx/zoom+0.5),math.floor(sy/zoom+0.5)
                        if hit and (hit.kind=="piece" or hit.kind=="spot") and hit.index==index and px>20 and px<getCore():getScreenWidth()-20
                                and py>80 and py<getCore():getScreenHeight()-40 then
                            local item=part:getInventoryItem()
                            return {x=px,y=py,index=index,piece=piece,kind=hit.kind,
                                header=item and item:getDisplayName() or getText("ContextMenu_MELens_PlaceFurniture")}
                        end
                    end
                end
            end
        end
    end
    error("no visible unobstructed furniture point for "..wanted)
end
function T.positionAtExit()
    local marker=T.profile.exitMarker
    assert(marker and M.isStanding(p),"no standing exit marker")
    M.walkTo(p,marker.x,marker.z) -- fixture positioning, not claimed as native walking evidence
    return marker
end
function T.positionOutside()
    assert(not p:getVehicle(),"outside fixture must not eject the player")
    local pos=Vector3f.new()
    local outside=v:getPassengerPosition(M.cabinSeat(v),"outside")
    assert(outside,"missing outside standing-seat offset")
    v:getWorldPos(outside:getOffset(),pos)
    p:setX(pos:x());p:setY(pos:y());p:setLastX(pos:x());p:setLastY(pos:y())
    p:faceLocation(v:getX(),v:getY())
    return {x=pos:x(),y=pos:y(),fixtureOnly=true}
end
return T.snapshot()
'''


def read_state(h):
    state = h.lua("return MELensInteriorTest.snapshot()")
    h.check(isinstance(state, dict) and isinstance(state.get("interior"), dict), "missing interior test snapshot")
    for key in ("queue", "menus", "controls"):
        state[key] = h._sequence(state.get(key))
    for menu in state["menus"]:
        menu["options"] = h._sequence(menu.get("options"))
    return state


def poll(h, predicate, timeout=35, label="native interior state"):
    h.REPORT["activeWait"] = label
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        last = read_state(h)
        if time.monotonic() >= h._input_release and predicate(last):
            return last
        time.sleep(.10)
    raise AssertionError(f"Timeout waiting for {label}: {json.dumps(last, ensure_ascii=False)}")


def idle(state):
    return state["queueCount"] == 0 and not state["interior"]["pathing"]


def interact_key(h, label):
    code = int(read_state(h)["interior"]["enterKey"])
    h.check(0 < code < 256, f"invalid actual Interact binding: {code}")
    h.lua(f"MEMCNativeLab.holdKey({code},200);return true")
    h._input_release = time.monotonic() + .65
    h.REPORT["nativeInput"] = True
    h.REPORT["inputs"].append({"action": label, "api": "MEMCNativeLab.holdKey", "key": code, "durationMs": 200})


def choose(h, tap, point, labels, case):
    before = poll(h, idle, label=f"idle before {case}")
    tap.native_click(h, point["x"], point["y"], f"{case}:open-world-menu", right=True)
    for label in labels:
        state = poll(h, lambda s: tap.menu_option(s, label) is not None, timeout=8, label=f"menu {label}")
        option = tap.menu_option(state, label)
        h.check(option["enabled"], f"disabled {label}: {state['menus']}")
        tap.native_click(h, option["x"], option["y"], f"{case}:{label}")
    return before


def close_dashboard(h, tap):
    state = read_state(h)
    point = state["interior"].get("closePoint")
    if point:
        tap.native_click(h, point["x"], point["y"], "dashboard:close")
        return poll(h, lambda s: not s.get("dashboard"), timeout=8, label="Dashboard closed by mouse")
    return state


def run_interior_cases(h, tap):
    h.REPORT["scope"] = "native single-player keyboard entry/exit, bed/dinette seating and world-menu Dashboard"
    h.REPORT["fixtureState"] = "existing water-test character; walkTo exit marker and outside-door position are fixture setup only"
    h.REPORT["unverified"] = ["multiplayer", "normal storage-window transfer", "furniture pickup/place",
                              "loose-item placement/move/rotate/grab", "actual sleep progression"]
    h.lua(FIXTURE)
    close_dashboard(h, tap)
    marker = h.lua("return MELensInteriorTest.positionAtExit()")
    before = poll(h, lambda s: idle(s) and s["interior"]["standing"]
                  and abs(s["interior"]["debug"].get("x", 999) - marker["x"]) <= marker["halfX"]
                  and abs(s["interior"]["debug"].get("z", 999) - marker["z"]) <= marker["halfZ"],
                  label="fixture positioned at exit marker")
    interact_key(h, "keyboard-exit")
    after = poll(h, lambda s: idle(s) and not s["interior"]["inside"], label="actual Interact exit")
    h.record("keyboard-interior-exit", before, after, fixturePositioning=True, uiHandlersInvokedDirectly=False)
    h.capture("interior-keyboard-outside")
    outside = h.lua("return MELensInteriorTest.positionOutside()")
    before = poll(h, lambda s: idle(s) and s["interior"]["nearWayIn"], label="fixture outside doorway")
    interact_key(h, "keyboard-entry")
    after = poll(h, lambda s: idle(s) and s["interior"]["inside"] and s["interior"]["standing"], label="actual Interact entry")
    h.record("keyboard-interior-entry", before, after, outsideFixture=outside, uiHandlersInvokedDirectly=False)
    h.capture("interior-keyboard-entered")

    rest = h.lua('return getText("ContextMenu_Rest")')
    for piece, kind in (("bed", "bed"), ("dinette", "seat")):
        point = h.lua(f'return MELensInteriorTest.point("{piece}")')
        before = choose(h, tap, point, [point["header"], rest], f"{piece}-rest")
        after = poll(h, lambda s: idle(s) and s["interior"].get("kind") == kind
                     and not s["interior"]["standing"]
                     and s["interior"].get("pose") == s["interior"].get("expectedPose"), label=f"native {piece} pose")
        h.check(after["interior"].get("expectedPose"), f"no native furniture pose for {piece}")
        h.record(f"context-menu-{piece}-rest", before, after, pickedFurniture=point, uiHandlersInvokedDirectly=False)
        h.capture(f"interior-{piece}-rest")
        before = after
        interact_key(h, f"{piece}-stand")
        after = poll(h, lambda s: idle(s) and s["interior"]["inside"] and s["interior"]["standing"], label=f"E stands from {piece}")
        h.record(f"keyboard-stand-from-{piece}", before, after, uiHandlersInvokedDirectly=False)

    point = h.lua('return MELensInteriorTest.point("bed")')
    label = h.lua('return getText("ContextMenu_MELens_Dashboard")')
    before = choose(h, tap, point, [label], "dashboard")
    after = poll(h, lambda s: s.get("dashboard") and len(s["controls"]) >= 8, timeout=8, label="world-menu Dashboard visible")
    h.record("world-context-menu-dashboard", before, after, uiHandlersInvokedDirectly=False)
    h.capture("interior-world-menu-dashboard")
    final = close_dashboard(h, tap)
    h.check(final["interior"]["inside"] and final["interior"]["standing"] and idle(final), "driver must finish standing idle inside")
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--endpoint", default=None)
    args = parser.parse_args()
    tap, h = load_helpers()
    h.configure(args.output, args.endpoint)
    try:
        h.REPORT["final"] = run_interior_cases(h, tap)
        print(f"NATIVE_INTERIOR_TESTS_PASSED {h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT["lastSnapshot"] = read_state(h)
        except Exception:
            h.REPORT["lastSnapshot"] = None
        print(error, flush=True)
        print(f"NATIVE_INTERIOR_TESTS_FAILED {h.write_report('failed', error)}; parent-owned game left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
