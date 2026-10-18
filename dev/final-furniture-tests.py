"""Focused native furniture/loose-item mouse checks; import has no game calls.

Parent owns the guarded disposable game. A dedicated hammer is seeded as a Floor
fixture; its Turn, Move, R rotation, placement and Grab use actual native input.
No UI handlers, feature actions or queues are called directly. No lifecycle calls.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/rv/final-furniture-tests"


def load_helpers():
    spec = importlib.util.spec_from_file_location("melens_furniture_interior_driver", Path(__file__).with_name("final-interior-tests.py"))
    interior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(interior)
    tap, h = interior.load_helpers()
    return interior, tap, h


FIXTURE = r'''
local T,M=MELensInteriorTest,MELens
local p,v,profile=T.player,T.vehicle,T.profile
local P,L,UI=M.Parts,M.Loose,M.LooseUI
local prior=T.snapshot
local resumeId=nil
for index,spot in ipairs(profile.spots or {}) do
    local part=P.spotPart(v,index)
    if P.pieceAt(part)=="heater" then
        T.heater,T.heaterIndex=part:getInventoryItem(),index
        break
    elseif spot.default=="heater" and part and not part:getInventoryItem() then
        T.heaterIndex=index
    end
end
if not T.heater then
    local items=p:getInventory():getItems()
    for i=0,items:size()-1 do
        local item=items:get(i)
        if P.pieceOfItem(item)=="heater" and (not resumeId or item:getID()==resumeId) then
            assert(not T.heater,"multiple carried heaters; specify --heater-id")
            T.heater=item
        end
    end
end
if resumeId then assert(T.heater and T.heater:getID()==resumeId,"requested original heater ID was not found") end
local function center(c)
    return c and {x=c:getAbsoluteX()+c:getWidth()/2,y=c:getAbsoluteY()+c:getHeight()/2}
end
function T.snapshot()
    local r=prior()
    local part=T.heaterIndex and P.spotPart(v,T.heaterIndex)
    local installed=part and part:getInventoryItem()
    local inv=p:getInventory()
    -- By ID: in multiplayer the client receives a picked-up or placed piece as a new object with the same ID, so the
    -- object captured before the move is never contained; follow the current object for the later steps.
    local carried=T.heater and inv:getItemById(T.heater:getID())
    local current=carried or (installed and T.heater and installed:getID()==T.heater:getID() and installed)
    if current then T.heater=current end
    r.furniture={heaterIndex=T.heaterIndex,heaterId=T.heater and T.heater:getID(),
        heaterName=T.heater and T.heater:getDisplayName(),heaterInInventory=carried~=nil,
        heaterInstalledId=installed and installed:getID(),heaterCondition=T.heater and T.heater:getCondition()}
    local placement=M.Placement.active
    r.furniture.placementActive=placement~=nil
    r.furniture.placementItemId=placement and placement.item and placement.item:getID()
    local window=getPlayerInventory(p:getPlayerNum())
    local pane=window and window.inventoryPane
    r.inventoryUI={visible=window and window:isVisible(),collapsed=window and window.isCollapsed,
        pinned=window and window.pin,toggleKey=getCore():getKey(KeybindId.TOGGLE_INVENTORY)}
    if window and pane then
        local ui=r.inventoryUI
        ui.title={x=window:getX()+math.min(90,window:getWidth()/3),y=window:getY()+window:titleBarHeight()/2}
        ui.pin=window.pinButton and window.pinButton:isVisible() and center(window.pinButton)
        ui.mainSelected=pane.inventory==inv
        for _,button in ipairs(window.backpacks or {}) do
            if button.inventory==inv then ui.mainButton=center(button) end
        end
        local bar=pane.vscroll
        if bar then
            ui.scrollUp={x=bar:getAbsoluteX()+bar:getWidth()/2,y=bar:getAbsoluteY()+6}
            ui.scrollDown={x=bar:getAbsoluteX()+bar:getWidth()/2,y=bar:getAbsoluteY()+bar:getHeight()-6}
        end
        for index,entry in ipairs(pane.items or {}) do
            local match=false
            if instanceof(entry,"InventoryItem") then
                match=T.heater and entry:getID()==T.heater:getID()
            elseif entry.items then
                for _,item in ipairs(entry.items) do
                    if T.heater and item:getID()==T.heater:getID() then match=true end
                end
            end
            if match and not ui.heaterRow then
                local top=pane:getAbsoluteY()+pane.headerHgt+(index-1)*pane.itemHgt+pane:getYScroll()
                ui.heaterRow={x=pane:getAbsoluteX()+math.min(pane.column2+60,pane.column3-10),y=top+pane.itemHgt/2,
                    index=index,above=top<pane:getAbsoluteY()+pane.headerHgt,
                    below=top+pane.itemHgt>pane:getAbsoluteY()+pane:getHeight()}
            end
        end
    end
    if T.hammer then
        local e=L.entry(v,T.hammer:getID())
        local floor=L.floorContainer(v)
        local mode=UI.active
        -- by ID, following the current object (multiplayer moves arrive as new objects with the same ID)
        local inInv=inv:getItemById(T.hammer:getID())
        local onFloor=floor and floor:getItemById(T.hammer:getID())
        if inInv or onFloor then T.hammer=inInv or onFloor end
        r.loose={id=T.hammer:getID(),name=T.hammer:getDisplayName(),entry=e,
            inInventory=inInv~=nil,inFloor=onFloor~=nil,
            hasRoomForGrab=inv:hasRoomFor(p,T.hammer),
            modeActive=mode~=nil,modeYaw=mode and mode.yaw,
            modeItemId=mode and mode:current() and mode:current():getID(),
            rotateKey=KeybindId and getCore():getKey(KeybindId.ROTATE_BUILDING)}
    end
    return r
end
function T.looseFixturePoint(item)
    -- Read-only geometry shared by the SP setup and the MP server-authoritative fixture.
    local x,z=P.characterAt(v,p)
    local offset=v:getScript():getModel():getOffset()
    local vec,origin=Vector3f.new(),Vector3f.new()
    local base=v:getWorldPos(0,0,0,origin):z()
    local chosen
    for _,point in ipairs(L.floorPoints(v,profile)) do
        if (point[1]-x)^2+(point[2]-z)^2>0.16 then
            local h=profile.floorY
            v:getWorldPos(offset:x()+point[1],offset:y()+h,offset:z()+point[2],vec)
            local sx,sy=ISCoordConversion.ToScreen(vec:x(),vec:y(),base+(offset:y()+h)/2.44949)
            local hover=UI.hoverFor(v,profile,item,0,sx,sy)
            if hover and hover.valid and hover.surface.s==0 then
                chosen={x=hover.x,z=hover.z}
                break
            end
        end
    end
    return chosen
end
function T.seedLoose()
    local floor=L.floorContainer(v)
    assert(floor and M.isStanding(p),"loose fixture needs Floor storage and standing player")
    local item=floor:getFirstEvalRecurse(function(i) return i:getModData().MELensNativeFurnitureFixture==true end)
        or p:getInventory():getFirstEvalRecurse(function(i) return i:getModData().MELensNativeFurnitureFixture==true end)
    local reused=item~=nil
    if not item then item=floor:AddItem("Base.Hammer") end
    assert(item,"native hammer fixture missing")
    if item:getContainer()~=floor then local source=item:getContainer();if source then source:Remove(item) end;floor:AddItem(item) end
    item:setName("Native input test hammer")
    item:getModData().MELensNativeFurnitureFixture=true
    local part=L.floorPart(v)
    local positions=part:getModData()[L.KEY] or {}
    part:getModData()[L.KEY]=positions
    local chosen=assert(T.looseFixturePoint(item),"no exposed valid floor location for the owned hammer fixture")
    positions[string.format("%d",item:getID())]={t=item:getFullType(),x=chosen.x,y=profile.floorY,z=chosen.z,r=0,s=0}
    T.hammer=item -- fixture metadata only; no tested feature handlers are called
    T.hammerFixture={reused=reused,id=item:getID(),x=chosen.x,z=chosen.z,fixtureOnly=true}
    return T.snapshot()
end
local function project(x,y,z)
    local offset=v:getScript():getModel():getOffset()
    local vec,origin=Vector3f.new(),Vector3f.new()
    local base=v:getWorldPos(0,0,0,origin):z()
    v:getWorldPos(offset:x()+x,offset:y()+y,offset:z()+z,vec)
    local sx,sy=ISCoordConversion.ToScreen(vec:x(),vec:y(),base+(offset:y()+y)/2.44949)
    local zoom=getCore():getZoom(p:getPlayerNum())
    return sx,sy,math.floor(sx/zoom+0.5),math.floor(sy/zoom+0.5)
end
function T.loosePoint()
    local e=L.entry(v,T.hammer:getID())
    if not e then return nil end
    local w,h,d=UI.size(T.hammer)
    if not w then return nil end
    for _,height in ipairs({math.max(h or 0.1,0.12)/2,0.02,0.1}) do
        for _,dx in ipairs({0,-0.025,0.025}) do
            local sx,sy,px,py=project(e.x+dx,e.y+height,e.z)
            local hit=M.Interact.pick(v,profile,sx,sy)
            if hit and hit.kind=="loose" and hit.id==T.hammer:getID() and px>20 and px<1260 and py>80 and py<680 then
                return {x=px,y=py,id=T.hammer:getID(),header=T.hammer:getDisplayName()}
            end
        end
    end
    local sx,sy=project(e.x,e.y+0.06,e.z)
    local zoom=getCore():getZoom(p:getPlayerNum())
    for dy=-20,20,3 do
        for dx=-20,20,3 do
            local hit=M.Interact.pick(v,profile,sx+dx,sy+dy)
            if hit and hit.kind=="loose" and hit.id==T.hammer:getID() then
                return {x=math.floor((sx+dx)/zoom+0.5),y=math.floor((sy+dy)/zoom+0.5),id=T.hammer:getID(),header=T.hammer:getDisplayName()}
            end
        end
    end
    return nil
end
function T.placementPoint()
    local mode=M.Placement.active
    if not mode then return nil end
    for _,place in ipairs(mode.places) do
        if place.index==T.heaterIndex then
            local x,z=(place.x0+place.x1)/2,(place.z0+place.z1)/2
            local _,_,px,py=project(x,profile.floorY+place.rise,z)
            if px>10 and px<1270 and py>20 and py<700 then return {x=px,y=py,index=place.index} end
        end
    end
    return nil
end
function T.movePoint()
    local mode=UI.active
    if not mode or not T.hammer then return nil end
    local old=L.entry(v,T.hammer:getID())
    for _,point in ipairs(L.floorPoints(v,profile)) do
        if not old or (old.x-point[1])^2+(old.z-point[2])^2>0.12 then
            local sx,sy,px,py=project(point[1],profile.floorY,point[2])
            if px>40 and px<1240 and py>100 and py<650 then
                local hover=UI.hoverFor(v,profile,T.hammer,mode.yaw,sx,sy)
                if hover and hover.valid and hover.surface.s==0 then
                    return {x=px,y=py,passengerX=hover.x,passengerZ=hover.z,yaw=mode.yaw}
                end
            end
        end
    end
    return nil
end
return T.snapshot()
'''


def wait_point(h, expression, label):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        value = h.lua(expression)
        if value:
            return value
        time.sleep(.15)
    raise AssertionError(f"no usable native geometry: {label}")


def finish(h, interior, predicate, action, label):
    seen = set()
    deadline = time.monotonic() + 45
    last = None
    while time.monotonic() < deadline:
        last = interior.read_state(h)
        seen.update(str(entry.get("type", "")) for entry in last["queue"])
        if time.monotonic() >= h._input_release and interior.idle(last) and predicate(last):
            h.check(any(action in kind for kind in seen), f"{label}: production action not observed: {seen}")
            return last, sorted(seen)
        time.sleep(.08)
    raise AssertionError(f"{label}: native completion timeout: {last}")


def open_inventory_item_menu(h, interior, tap):
    state = interior.read_state(h)
    if not state["inventoryUI"]["visible"]:
        key = int(state["inventoryUI"]["toggleKey"])
        h.check(0 < key < 256, "invalid native inventory binding")
        h.lua(f"MEMCNativeLab.holdKey({key},180);return true")
        h._input_release = time.monotonic() + .60
        h.REPORT["inputs"].append({"action": "inventory-open", "api": "MEMCNativeLab.holdKey", "key": key})
        state = interior.poll(h, lambda s: s["inventoryUI"]["visible"], timeout=8, label="actual inventory key opens window")
    if state["inventoryUI"]["collapsed"]:
        point = state["inventoryUI"]["title"]
        tap.native_click(h, point["x"], point["y"], "inventory-expand-title")
        state = interior.poll(h, lambda s: not s["inventoryUI"]["collapsed"], timeout=8, label="inventory title expands window")
    if not state["inventoryUI"]["pinned"] and state["inventoryUI"].get("pin"):
        point = state["inventoryUI"]["pin"]
        tap.native_click(h, point["x"], point["y"], "inventory-pin")
        state = interior.poll(h, lambda s: s["inventoryUI"]["pinned"], timeout=8, label="inventory pinned by mouse")
    if not state["inventoryUI"]["mainSelected"]:
        point = state["inventoryUI"].get("mainButton")
        h.check(point, "no native main inventory button")
        tap.native_click(h, point["x"], point["y"], "inventory-main-container")
        state = interior.poll(h, lambda s: s["inventoryUI"]["mainSelected"], timeout=8, label="main inventory selected by mouse")
    for _ in range(45):
        state = interior.read_state(h)
        row = state["inventoryUI"].get("heaterRow")
        h.check(row, "heater missing from native main inventory rows")
        if not row["above"] and not row["below"]:
            tap.native_click(h, row["x"], row["y"], "heater:inventory-context-menu", right=True)
            return
        direction = "scrollUp" if row["above"] else "scrollDown"
        point = state["inventoryUI"].get(direction)
        h.check(point, "heater row offscreen without native scrollbar")
        tap.native_click(h, point["x"], point["y"], "inventory:" + direction)
        interior.poll(h, lambda s: True, timeout=3, label="native scrollbar dispatch")
    raise AssertionError("heater row remained offscreen after native scrollbar clicks")


def place_heater_from_inventory(h, interior, tap, target):
    before = interior.read_state(h)
    open_inventory_item_menu(h, interior, tap)
    label = h.lua('return getText("ContextMenu_MELens_PlaceFurniture")')
    menu = interior.poll(h, lambda s: tap.menu_option(s, label) is not None, timeout=8, label="inventory Place furniture option")
    option = tap.menu_option(menu, label)
    h.check(option["enabled"], "native inventory Place furniture option disabled")
    tap.native_click(h, option["x"], option["y"], "heater:inventory-Place-furniture")
    interior.poll(h, lambda s: s["furniture"]["placementActive"]
                  and s["furniture"].get("placementItemId") == target["heaterId"], timeout=8, label="furniture placement preview")
    point = wait_point(h, "return MELensInteriorTest.placementPoint()", "original empty heater spot in placement mode")
    tap.native_click(h, point["x"], point["y"], "heater:click-original-empty-spot")
    after, seen = finish(h, interior, lambda s: s["furniture"].get("heaterInstalledId") == target["heaterId"]
                         and not s["furniture"]["heaterInInventory"], "MELensPlaceFurniture", "inventory heater replacement")
    h.check(after["furniture"]["heaterCondition"] == target["heaterCondition"], "heater placement changed condition")
    h.record("inventory-context-heater-place-same-item", before, after, destination=point,
             observedTimedActions=seen, uiHandlersInvokedDirectly=False)
    if after["inventoryUI"]["visible"]:
        key = int(after["inventoryUI"]["toggleKey"])
        h.lua(f"MEMCNativeLab.holdKey({key},180);return true")
        h._input_release = time.monotonic() + .60
        h.REPORT["inputs"].append({"action": "inventory-close", "api": "MEMCNativeLab.holdKey", "key": key})
        interior.poll(h, lambda s: not s["inventoryUI"]["visible"], timeout=8, label="inventory closed by key")
    h.capture("furniture-heater-restored")


def run_cases(h, interior, tap, scope="all", resume_placement=False, heater_id=None, seed_loose=None):
    h.REPORT["scope"] = f"native single-player furniture/loose workflows ({scope})"
    h.REPORT["fixtureState"] = "existing standing feature player; one dedicated hammer seeded in Floor storage only for loose checks"
    h.REPORT["unverified"] = ["multiplayer", "normal storage-window transfer", "inventory-menu initial loose Place", "sleep progression"]
    h.REPORT["resumedHeaterPlacement"] = resume_placement
    h.lua(interior.FIXTURE)
    h.lua(FIXTURE.replace("local resumeId=nil", f"local resumeId={int(heater_id) if heater_id is not None else 'nil'}"))
    interior.close_dashboard(h, tap)
    if scope in ("all", "furniture"):
        initial = interior.read_state(h)
        target = initial["furniture"]
        h.check(target.get("heaterId") is not None, "camper needs its installed heater for this test")
        if not resume_placement:
            point = h.lua('return MELensInteriorTest.point("heater")')
            pickup = h.lua('return getText("ContextMenu_MELens_PickUp")')
            before = interior.choose(h, tap, point, [point["header"], pickup], "heater-pickup")
            after, seen = finish(h, interior, lambda s: s["furniture"].get("heaterInstalledId") is None
                                 and s["furniture"]["heaterInInventory"], "MELensPickUpFurniture", "heater pickup")
            h.check(after["furniture"]["heaterId"] == target["heaterId"], "heater pickup changed item identity")
            h.record("context-heater-pickup", before, after, observedTimedActions=seen, uiHandlersInvokedDirectly=False)
            h.capture("furniture-heater-picked-up")
        else:
            h.check(target.get("heaterInstalledId") is None and target["heaterInInventory"], "resume expects original heater carried and spot empty")
        place_heater_from_inventory(h, interior, tap, target)

    if scope in ("all", "loose"):
        seeded = seed_loose() if seed_loose else h.lua("return MELensInteriorTest.seedLoose()")
        h.check(seeded["loose"]["hasRoomForGrab"], "fixture player lacks inventory capacity for normal Grab; free carry space before loose checks")
        point = wait_point(h, "return MELensInteriorTest.loosePoint()", "seeded hammer picker")
        labels = h.lua('return {turn=getText("ContextMenu_MELens_TurnItem"),move=getText("ContextMenu_MELens_MoveItem"),grab=getText("ContextMenu_Grab")}')
        before = interior.choose(h, tap, point, [point["header"], labels["turn"]], "hammer-turn")
        after, seen = finish(h, interior, lambda s: s["loose"].get("entry", {}).get("r") == 45,
                             "MELensTurnLoose", "hammer turn")
        h.record("context-loose-turn", before, after, observedTimedActions=seen, uiHandlersInvokedDirectly=False)
        point = wait_point(h, "return MELensInteriorTest.loosePoint()", "turned hammer picker")
        before = interior.choose(h, tap, point, [point["header"], labels["move"]], "hammer-move")
        active = interior.poll(h, lambda s: s["loose"]["modeActive"], timeout=8, label="actual Move opens placement preview")
        old_yaw = active["loose"]["modeYaw"]
        code = int(active["loose"]["rotateKey"])
        h.check(0 < code < 256, "invalid native rotate binding")
        h.lua(f"MEMCNativeLab.holdKey({code},180);return true")
        h._input_release = time.monotonic() + .60
        h.REPORT["inputs"].append({"action": "loose-preview-rotate", "api": "MEMCNativeLab.holdKey", "key": code, "durationMs": 180})
        rotated = interior.poll(h, lambda s: s["loose"]["modeActive"] and abs((s["loose"]["modeYaw"]-old_yaw)%360-15)<.01,
                                timeout=8, label="actual R rotates placement preview")
        h.record("keyboard-loose-preview-rotate", active, rotated, uiHandlersInvokedDirectly=False)
        destination = wait_point(h, "return MELensInteriorTest.movePoint()", "clear floor destination")
        tap.native_click(h, destination["x"], destination["y"], "hammer-move:place-preview")
        after, seen = finish(h, interior, lambda s: not s["loose"]["modeActive"] and s["loose"]["inFloor"]
                             and s["loose"].get("entry") and abs(s["loose"]["entry"]["x"]-destination["passengerX"])<.06
                             and abs(s["loose"]["entry"]["z"]-destination["passengerZ"])<.06,
                             "MELensPlaceLoose", "hammer Move placement")
        h.check(abs(after["loose"]["entry"]["r"]-destination["yaw"])<.01, "placed hammer ignored native R rotation")
        h.record("context-loose-move-and-place", before, after, destination=destination, observedTimedActions=seen, uiHandlersInvokedDirectly=False)
        h.capture("furniture-loose-moved")
        point = wait_point(h, "return MELensInteriorTest.loosePoint()", "moved hammer picker")
        before = interior.choose(h, tap, point, [point["header"], labels["grab"]], "hammer-grab")
        after, seen = finish(h, interior, lambda s: s["loose"]["inInventory"] and not s["loose"]["inFloor"]
                             and not s["loose"].get("entry"), "MELensGrabLoose", "hammer Grab")
        h.check(after["loose"]["id"] == before["loose"]["id"], "Grab changed hammer identity")
        h.record("context-loose-grab-same-item", before, after, observedTimedActions=seen, uiHandlersInvokedDirectly=False)
    final = interior.read_state(h)
    h.check(final["interior"]["standing"] and interior.idle(final), "driver must end standing idle inside")
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--scope", choices=("all", "furniture", "loose"), default="all")
    parser.add_argument("--resume-placement", action="store_true")
    parser.add_argument("--heater-id", type=int, default=None)
    args = parser.parse_args()
    interior, tap, h = load_helpers()
    h.configure(args.output, args.endpoint)
    try:
        h.REPORT["final"] = run_cases(h, interior, tap, args.scope, args.resume_placement, args.heater_id)
        print(f"NATIVE_FURNITURE_TESTS_PASSED {h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT["lastSnapshot"] = interior.read_state(h)
        except Exception:
            h.REPORT["lastSnapshot"] = None
        print(error, flush=True)
        print(f"NATIVE_FURNITURE_TESTS_FAILED {h.write_report('failed', error)}; parent-owned game left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
