"""Native rename/paint checks in a parent-owned disposable game; import does no I/O.

Requires the next isolated workshop-capture boot, including MELensNativeText, the
feature-fixture.lua setup and an open Interior Manager. Fixture code only supplies
inventory state. All feature edits use production mouse/text/UI/timed-action paths.
The caller owns launch, save and shutdown, including on failure.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/rv/final-personalization-tests"


def load_helpers():
    spec = importlib.util.spec_from_file_location(
        "melens_personalization_features", Path(__file__).with_name("final-feature-tests.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = r'''
local F=MELensFeatureTest
local p=getPlayer()
assert(F and p and F.vehicle and p:getVehicle()==F.vehicle,"personalization requires the standing feature-test player")
assert(not p:isTimedActionInstant(),"personalization requires normal timed actions")
assert(#ISTimedActionQueue.getTimedActionQueue(p).queue==0,"wait for idle before personalization setup")
assert(MELensNativeText and MELensNativeText.queued,"fresh native boot needs the dev TextInput adapter")
local M,H=MELens,MELens.Home
assert(M.Dashboard.instance and M.Dashboard.instance:isVisible(),"open the Interior Manager before personalization setup")
local v,inv=F.vehicle,p:getInventory()
local T=MELensPersonalizationTest
if not T or T.vehicle~=v then T={vehicle=v,player=p} end
MELensPersonalizationTest=T
local function own(key,full)
    local item=inv:getFirstEvalRecurse(function(i) return i:getModData().MELensPersonalFixture==key end)
    if not item then item=inv:AddItem(full) end
    assert(item and item:getFullType()==full,"missing native personalization item "..full)
    if item:getContainer()~=inv then local c=item:getContainer(); if c then c:Remove(item) end; inv:AddItem(item) end
    item:getModData().MELensPersonalFixture=key
    return item
end
if not T.initialized then
    T.can=own("paint","Base.PaintGreen")
    T.brush=own("brush","Base.Paintbrush")
    T.can:setUsedDelta(1)
    T.can:syncItemFields()
    T.initialized=true
end
local choice
for _,entry in ipairs(H.paints()) do if entry.paint==T.can:getType() then choice=entry end end
assert(choice and choice.color,"native shared palette lacks fixture paint")
T.color={r=choice.color[1],g=choice.color[2],b=choice.color[3]}
T.paintLabel=getText(choice.text)
T.stripLabel=getText("IGUI_MELens_StripPaint")
local function rect(c)
    return {x=c:getAbsoluteX()+c:getWidth()/2,y=c:getAbsoluteY()+c:getHeight()/2,
        width=c:getWidth(),height=c:getHeight()}
end
function T.snapshot()
    local r=F.snapshot()
    local red,green,blue=H.paint(v)
    r.personal={name=H.givenName(v) or "",maxName=H.NAME_MAX,
        paint=red and {r=red,g=green,b=blue} or false,
        canId=T.can:getID(),canUses=T.can:getCurrentUses(),canInMain=inv:contains(T.can),
        brushId=T.brush:getID(),brushInMain=inv:contains(T.brush),brushCondition=T.brush:getCondition(),
        paintLabel=T.paintLabel,stripLabel=T.stripLabel,color=T.color,
        nativeTextQueued=MELensNativeText.queued(),nativeTextSent=MELensNativeText.sent(),
        nativeTextFailure=MELensNativeText.failure()}
    r.dialog=false
    local ui=UIManager.getUI()
    local dashboard=M.Dashboard.instance
    local root=getPlayerContextMenu(p:getPlayerNum())
    r.paintMenuLayer={dashboard=-1,menu=-1}
    r.personal.dashboardPaint=false
    if dashboard then
        for _,card in ipairs(dashboard.cards or {}) do
            for _,row in ipairs(card.rows or {}) do
                if row.swatch then
                    r.personal.dashboardPaint={r=row.swatch[1],g=row.swatch[2],b=row.swatch[3]}
                end
            end
        end
    end
    for i=0,ui:size()-1 do
        local t=ui:get(i):getTable()
        if t==dashboard then r.paintMenuLayer.dashboard=i end
        if t==root then r.paintMenuLayer.menu=i end
        if t and t.Type=="ISTextBox" and t.target==dashboard and t.onclick==dashboard.onRenamed and t:isVisible() then
            assert(not r.dialog,"duplicate rename dialogs")
            r.dialog={text=t.entry:getText(),focused=t.entry.javaObject:isFocused(),
                entry=rect(t.entry),ok=rect(t.yes),cancel=rect(t.no),okEnabled=t.yes:isEnabled()}
        end
    end
    r.menus={}
    local seen={}
    local function menu(m)
        if not m or seen[m] or not m:isVisible() then return end
        seen[m]=true
        local options={}
        for i,option in ipairs(m.options or {}) do
            local y=m:getItemY(i)+m.itemHgt/2
            if y>=m:getY() and y<=m:getY()+m:getHeight() then
                options[#options+1]={name=tostring(option.name),enabled=not option.notAvailable and not option.isDisabled,
                    x=m:getX()+m:getWidth()/2,y=y}
            end
        end
        r.menus[#r.menus+1]={options=options}
    end
    menu(root)
    if root then for _,m in ipairs(root.instanceMap or {}) do menu(m) end end
    return r
end
return T.snapshot()
'''


def read_state(h):
    state = h.lua("return MELensPersonalizationTest.snapshot()")
    h.check(isinstance(state, dict) and isinstance(state.get("personal"), dict), "missing personalization snapshot")
    for key in ("controls", "queue", "menus"):
        state[key] = h._sequence(state.get(key))
    for menu in state["menus"]:
        menu["options"] = h._sequence(menu.get("options"))
    return state


def poll(h, predicate, timeout=25, label="native personalization state", seen=None):
    h.REPORT["activeWait"] = label
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        last = read_state(h)
        if seen is not None:
            seen.update(str(action.get("type", "")) for action in last["queue"])
        if time.monotonic() >= h._input_release and predicate(last):
            return last
        time.sleep(.10)
    raise AssertionError(f"Timeout waiting for {label}: {json.dumps(last, ensure_ascii=False)}")


def click(h, point, label):
    x, y = int(point["x"]), int(point["y"])
    h.check(0 <= x < 1280 and 0 <= y < 720, f"offscreen native click {label}: {x},{y}")
    h.lua(f"MEMCNativeLab.clickAt({x},{y}); return true")
    h._input_release = time.monotonic() + .60
    h.REPORT["nativeInput"] = True
    h.REPORT["inputs"].append({"action": label, "api": "MEMCNativeLab.clickAt", "x": x, "y": y})


def assert_scene_still(h, before, after):
    for key in ("x", "y", "z", "passengerX", "passengerZ"):
        a, b = before["player"].get(key), after["player"].get(key)
        if a is not None and b is not None:
            h.check(abs(a - b) < .05, f"personalization input moved the underlying scene: {key}")
    h.check(not after["player"].get("aiming"), "personalization input leaked to scene aiming")


def assert_supplies_same(h, before, after):
    for key in ("canId", "canUses", "canInMain", "brushId", "brushInMain", "brushCondition"):
        h.check(before["personal"][key] == after["personal"][key], f"unexpected personalization supply change: {key}")


def type_draft(h, draft):
    state = poll(h, lambda s: bool(s["dialog"]), label="rename dialog")
    click(h, state["dialog"]["entry"], "focus-rename-entry")
    state = poll(h, lambda s: s["dialog"] and s["dialog"]["focused"], label="native rename entry focus")
    old = state["dialog"]["text"]
    h.check(all(ord(char) < 128 for char in old + draft), "test uses ASCII for native byte/character max parity")
    code = 'MELensNativeText.key("END",1); '
    if old:
        code += f'MELensNativeText.key("BACKSPACE",{len(old)}); '
    code += f"MELensNativeText.text({json.dumps(draft)}); return true"
    h.lua(code)
    h._input_release = time.monotonic() + .10
    h.REPORT["inputs"].append({"action": "type-rename-draft", "api": "MELensNativeText",
                               "text": draft, "replacedCharacters": len(old)})
    state = poll(h, lambda s: s["dialog"] and s["dialog"]["text"] == draft
                 and s["personal"]["nativeTextQueued"] == 0, label=f"native draft {draft!r}")
    h.check(not state["personal"]["nativeTextFailure"], "native text queue reported focus loss or expiration")
    return state


def rename_case(h, name, draft, expected=None, cancel=False, capture=False):
    before = read_state(h)
    h.click_control("rename")
    drafted = type_draft(h, draft)
    h.check(drafted["personal"]["name"] == before["personal"]["name"], "editing draft changed committed name")
    if capture:
        h.capture("personalization-rename-draft")
    click(h, drafted["dialog"]["cancel" if cancel else "ok"], name)
    seen = set()
    expected = before["personal"]["name"] if cancel else expected
    after = poll(h, lambda s: not s["dialog"] and s["queueCount"] == 0
                 and s["personal"]["name"] == expected, label=name, seen=seen)
    assert_supplies_same(h, before, after)
    assert_scene_still(h, before, after)
    if cancel:
        h.check(not seen, f"cancel queued a timed action: {seen}")
    else:
        h.check(any("MELensRename" in action for action in seen), f"rename action not observed: {seen}")
    h.record(name, before, after, draft=draft, expectedName=expected, cancelled=cancel,
             observedTimedActions=sorted(seen), nativeTextEvents=True, uiHandlersInvokedDirectly=False)
    return after


def option_of(state, label):
    found = [o for menu in state["menus"] for o in menu["options"] if o["name"] == label]
    if not found:
        return None
    if len(found) != 1:
        raise AssertionError(f"ambiguous native paint menu {label!r}: {found}")
    return found[0]


def paint_case(h, name, strip=False):
    before = read_state(h)
    h.click_control("paint")
    label = before["personal"]["stripLabel" if strip else "paintLabel"]
    state = poll(h, lambda s: option_of(s, label) is not None
                 and s["paintMenuLayer"]["menu"] > s["paintMenuLayer"]["dashboard"],
                 timeout=10, label=f"visible topmost native paint menu {label}")
    h.check(state["queueCount"] == 0 and state["personal"]["canUses"] == before["personal"]["canUses"]
            and state["personal"]["paint"] == before["personal"]["paint"],
            "opening the paint menu automatically selected a coat")
    idle_until = time.monotonic() + 1.0
    while time.monotonic() < idle_until:
        state = read_state(h)
        h.check(state["queueCount"] == 0 and state["personal"]["canUses"] == before["personal"]["canUses"]
                and state["personal"]["paint"] == before["personal"]["paint"]
                and option_of(state, label) is not None,
                "opening click selected paint before an explicit menu choice")
        time.sleep(.10)
    option = option_of(state, label)
    h.check(option["enabled"], f"native paint menu disabled {label}")
    click(h, option, name)
    seen = set()
    expected = False if strip else before["personal"]["color"]
    def matches(s):
        actual, displayed = s["personal"]["paint"], s["personal"]["dashboardPaint"]
        if strip:
            return actual is False and displayed is False
        return isinstance(actual, dict) and isinstance(displayed, dict) and all(
            abs(actual[k] - expected[k]) < .00001 and abs(displayed[k] - expected[k]) < .00001
            for k in ("r", "g", "b"))
    after = poll(h, lambda s: s["queueCount"] == 0 and matches(s), timeout=90, label=name, seen=seen)
    h.check(any("MELensPaintWalls" in action for action in seen), f"paint action not observed: {seen}")
    delta = before["personal"]["canUses"] - after["personal"]["canUses"]
    h.check(delta == (0 if strip else 4), f"paint use conservation failed: consumed {delta}")
    for key in ("canId", "canInMain", "brushId", "brushInMain", "brushCondition", "name"):
        h.check(before["personal"][key] == after["personal"][key], f"paint changed {key}")
    assert_scene_still(h, before, after)
    h.record(name, before, after, consumedPaintUses=delta, observedTimedActions=sorted(seen),
             uiHandlersInvokedDirectly=False)
    return after


def run_personalization_cases(h=None, skip_insufficient=False):
    if h is None:
        h = load_helpers()
        h.configure(OUTPUT)
    h.REPORT["scope"] = "native rename and paint in parent-owned disposable single-player game"
    h.lua(FIXTURE)
    initial = read_state(h)
    h.check(initial.get("dashboard") and initial["player"]["inside"], "open the Interior Manager inside the fixture camper")
    rename_case(h, "rename-cancel-preserves-committed-state", "Cancelled draft", cancel=True, capture=True)
    rename_case(h, "rename-valid-text-events", "Road Home", "Road Home")
    rename_case(h, "rename-trims-whitespace", "  Trimmed Home  ", "Trimmed Home")
    draft = "  ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789  "
    expected = draft.strip()[:initial["personal"]["maxName"]]
    rename_case(h, "rename-clamps-to-24", draft, expected)
    rename_case(h, "rename-empty-restores-default", "   ", "")
    rename_case(h, "rename-final-personal-name", "Road Home", "Road Home")
    if read_state(h)["personal"]["paint"]:
        paint_case(h, "strip-existing-fixture-paint", strip=True)
    paint_case(h, "paint-walls-consumes-four-real-uses")
    h.capture("personalization-painted-walls")
    paint_case(h, "strip-paint-consumes-no-supplies", strip=True)
    h.capture("personalization-name-and-default-walls")
    if skip_insufficient:
        return read_state(h)
    # Supply setup only: verify a genuinely insufficient can disables the UI.
    # Do not replenish paint already consumed by the native coat above.
    h.lua('local T=MELensPersonalizationTest; T.can:setUsedDelta(T.can:getUseDelta()*3.01); '
          'T.can:syncItemFields(); return true')
    state = poll(h, lambda s: s["personal"]["canUses"] == 3 and not h._control(s, "paint")["enabled"],
                 label="three-use can disables paint; no other full carried paint cans")
    before = read_state(h)
    h.click_control("paint", enabled=False)
    after = poll(h, lambda s: s["queueCount"] == 0 and not s["menus"], label="disabled paint leaves no menu or action")
    assert_supplies_same(h, before, after)
    assert_scene_still(h, before, after)
    h.check(before["personal"]["paint"] == after["personal"]["paint"], "disabled paint changed committed walls")
    h.record("insufficient-paint-disabled-preserves-supplies", before, after, rejectedInput=True, sceneInputConsumed=True)
    return read_state(h)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--endpoint", default=None)
    args = parser.parse_args()
    h = load_helpers()
    h.configure(args.output, args.endpoint)
    try:
        h.REPORT["final"] = run_personalization_cases(h)
        path = h.write_report("passed")
        print(f"NATIVE_PERSONALIZATION_PASSED {path}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT["lastSnapshot"] = read_state(h)
        except Exception:
            h.REPORT["lastSnapshot"] = None
        path = h.write_report("failed", error)
        print(error, flush=True)
        print(f"NATIVE_PERSONALIZATION_FAILED {path}; parent-owned game left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
