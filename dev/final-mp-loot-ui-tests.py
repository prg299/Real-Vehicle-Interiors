"""Actual MP loot-window container/row/Grab input; import performs no game calls.

Both clients must stand in the same stopped interior. The server adds one tagged
pencil to each chosen storage container without removing any existing contents.
The real UI selects its container and item and submits Grab; exact IDs are checked
on the server and each owning client. Parent owns all native process lifetimes.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import traceback


ROOT = Path(__file__).resolve().parents[1]


def load_driver():
    spec = importlib.util.spec_from_file_location("melens_mp_loot_interiors", Path(__file__).with_name("final-mp-interior-tests.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


UI_READ = r'''
local p=getPlayer();local v=getVehicleById(VEHICLE_ID)
local pid,itemId=PART_ID,ITEM_ID
local r={inside=v and p:getVehicle()==v,standing=MELens.isStanding(p),
    inventoryKey=getCore():getKey(KeybindId.TOGGLE_INVENTORY),menus={},windows={}}
local inv=p:getInventory()
r.itemInInventory=itemId>=0 and inv:getItemById(itemId)~=nil
local queue=ISTimedActionQueue.queues[p]
r.queueCount=queue and #queue.queue or 0
r.pathing=MELens.pathing(p)
local function center(c) return {x=c:getAbsoluteX()+c:getWidth()/2,y=c:getAbsoluteY()+c:getHeight()/2} end
local function window(which,w)
    if not w then return end
    local pane=w.inventoryPane
    local t={visible=w:isVisible(),collapsed=w.isCollapsed,pinned=w.pin,buttons={},mainSelected=pane.inventory==inv,
        title={x=w:getX()+math.min(90,w:getWidth()/3),y=w:getY()+w:titleBarHeight()/2}}
    r.windows[which]=t
    t.pin=w.pinButton and w.pinButton:isVisible() and center(w.pinButton)
    local target=v and v:getPartById(pid)
    t.targetSelected=target and pane.inventory==target:getItemContainer()
    local panel=w.containerButtonPanel
    for _,button in ipairs(w.backpacks or {}) do
        local partId
        if v then for i=0,v:getPartCount()-1 do
            local part=v:getPartByIndex(i)
            if part:getItemContainer()==button.inventory then partId=part:getId();break end
        end end
        local point=center(button)
        local visible=button:isVisible() and point.y>=panel:getAbsoluteY()+2 and point.y<=panel:getAbsoluteY()+panel:getHeight()-2
        if partId then t.buttons[#t.buttons+1]={partId=partId,x=point.x,y=point.y,visible=visible} end
        if button.inventory==inv and visible then t.mainButton=point end
        if partId==pid and visible then t.targetButton=point end
    end
    local bar=pane.vscroll
    if bar then
        t.scrollUp={x=bar:getAbsoluteX()+bar:getWidth()/2,y=bar:getAbsoluteY()+6}
        t.scrollDown={x=bar:getAbsoluteX()+bar:getWidth()/2,y=bar:getAbsoluteY()+bar:getHeight()-6}
    end
    for index,entry in ipairs(pane.items or {}) do
        local match=false
        if instanceof(entry,"InventoryItem") then match=entry:getID()==itemId
        elseif entry.items then for _,item in ipairs(entry.items) do if item:getID()==itemId then match=true end end end
        if match and not t.row then
            local top=pane:getAbsoluteY()+pane.headerHgt+(index-1)*pane.itemHgt+pane:getYScroll()
            t.row={x=pane:getAbsoluteX()+math.min(pane.column2+60,pane.column3-10),y=top+pane.itemHgt/2,index=index,
                above=top<pane:getAbsoluteY()+pane.headerHgt,below=top+pane.itemHgt>pane:getAbsoluteY()+pane:getHeight()}
        end
    end
end
window("inventory",getPlayerInventory(p:getPlayerNum()))
window("loot",getPlayerLoot(p:getPlayerNum()))
local root=getPlayerContextMenu(p:getPlayerNum());local seen={}
local function menu(m)
    if not m or seen[m] or not m:isVisible() then return end
    seen[m]=true
    for index,option in ipairs(m.options or {}) do
        local y=m:getItemY(index)+m.itemHgt/2
        if y>=m:getY() and y<=m:getY()+m:getHeight() then
            r.menus[#r.menus+1]={name=tostring(option.name),enabled=not option.notAvailable and not option.isDisabled,
                x=m:getX()+m:getWidth()/2,y=y}
        end
    end
end
menu(root);if root then for _,m in ipairs(root.instanceMap or {}) do menu(m) end end
return r
'''


class InventoryLab:
    """Reuses InteriorLab's real MEMCNativeLab input and server receipt channel."""
    def __init__(self, lab, module):
        self.lab, self.module, self.h = lab, module, lab.h
        self.part, self.item_id = "", -1

    def api(self, side):
        return self.lab.h if side == "A" else self.lab.b

    def read(self, side):
        code = UI_READ.replace("VEHICLE_ID", str(self.lab.vid)).replace("PART_ID", json.dumps(self.part)).replace("ITEM_ID", str(self.item_id))
        value = self.api(side).lua(code)
        value["menus"] = self.h._sequence(value.get("menus"))
        for window in value.get("windows", {}).values():
            window["buttons"] = self.h._sequence(window.get("buttons"))
        return value

    def wait(self, side, predicate, label, timeout=20):
        return self.lab.wait(lambda: self.read(side), predicate, f"{side} {label}", timeout)

    def click(self, side, point, label, right=False):
        self.h.REPORT["activeCase"] = label
        self.lab.input(side, x=point["x"], y=point["y"], right=right)

    def open(self, side):
        state = self.read(side)
        self.h.check(state["inside"] and state["standing"], f"{side} must already stand inside")
        # Restore the test harness's hidden HUD only; actual inventory opening uses its key.
        self.api(side).lua('if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end;ISUIHandler.setVisibleAllUI(true);return true')
        state = self.read(side)
        if state["windows"]["inventory"]["visible"]:
            self.lab.input(side, key=int(state["inventoryKey"]))
            self.wait(side, lambda s: not s["windows"]["inventory"]["visible"], "inventory key closes window")
        self.lab.input(side, key=int(state["inventoryKey"]))
        state = self.wait(side, lambda s: all(w["visible"] for w in s["windows"].values()), "inventory key opens both windows")
        for which in ("inventory", "loot"):
            window = state["windows"][which]
            if window["collapsed"]:
                self.click(side, window["title"], f"{which}:expand-title")
                state = self.wait(side, lambda s: not s["windows"][which]["collapsed"], f"{which} title expands")
            window = state["windows"][which]
            if not window["pinned"] and window.get("pin"):
                self.click(side, window["pin"], f"{which}:pin")
                state = self.wait(side, lambda s: s["windows"][which]["pinned"], f"{which} pin")
        if not state["windows"]["inventory"]["mainSelected"]:
            point = state["windows"]["inventory"].get("mainButton")
            self.h.check(point, f"{side} ordinary inventory button missing")
            self.click(side, point, "select-ordinary-destination-inventory")
            state = self.wait(side, lambda s: s["windows"]["inventory"]["mainSelected"], "ordinary destination selected")
        return state

    def authority(self):
        code = f'''
local v=getVehicleById({self.lab.vid});local part=v and v:getPartById({json.dumps(self.part)})
local function ids(c) local out={{}};if c then for i=0,c:getItems():size()-1 do out[#out+1]=c:getItems():get(i):getID() end end;return out end
local r={{source=ids(part and part:getItemContainer()),players={{}}}}
local ps=getOnlinePlayers();for i=0,ps:size()-1 do local p=ps:get(i);r.players[p:getUsername()]=ids(p:getInventory()) end
return enc(r)
'''
        result = json.loads(self.lab.server(self.module.JSON_ENCODER + code))
        result["source"] = self.h._sequence(result.get("source"))
        result["players"] = {key: self.h._sequence(value) for key, value in result["players"].items()}
        return result

    def select_container(self, side, part_id):
        """Select through visible buttons; bottom selections reveal the next clipped buttons."""
        self.part = part_id
        previous = None
        repeated = 0
        for _ in range(45):
            state = self.read(side)
            window = state["windows"]["loot"]
            if window.get("targetButton"):
                self.click(side, window["targetButton"], "select-interior-storage-container")
                return self.wait(side, lambda s: s["windows"]["loot"]["targetSelected"], "correct interior container selected")
            visible = [button for button in window["buttons"] if button["visible"]]
            self.h.check(visible, f"{side} no visible loot-container buttons")
            point = max(visible, key=lambda button: button["y"])
            signature = (point["partId"], int(point["y"]))
            repeated = repeated + 1 if signature == previous else 0
            self.h.check(repeated < 3, f"{side} target container cannot be revealed by native button selection: {part_id}")
            previous = signature
            self.click(side, point, "reveal-lower-loot-container-buttons")
            self.wait(side, lambda s: True, "container panel delivery")
        raise AssertionError(f"{side} container button not reached: {part_id}")

    def run(self, preferred_part=None):
        self.h.REPORT.update(scope=__doc__.strip(), lootNativeMouseInput=True, lootUsesProductionTransferAction=True,
                             fixtureOnly=["restore hidden test HUD", "one tagged pencil per case added on server"],
                             inputCoverage=["inventory key", "window title/pin", "container button", "item row context Grab"])
        info = self.lab.h.lua('local p=getPlayer();local v=p:getVehicle();return v and {id=v:getId(),standing=MELens.isStanding(p),speed=v:getCurrentSpeedKmHour()} or false')
        self.h.check(info and info["standing"] and abs(info["speed"]) < .2, "A must stand in stopped interior")
        self.lab.vid = int(info["id"])
        self.h.check(self.lab.b.lua(f'return getPlayer():getVehicle()==getVehicleById({self.lab.vid}) and MELens.isStanding(getPlayer())'), "B must stand in same interior")
        receipts = []
        for side, username in (("A", "MELensAdmin"), ("B", "MELensGuest")):
            self.part, self.item_id = "", -1
            state = self.open(side)
            choices = [b for b in state["windows"]["loot"]["buttons"] if
                       (b["partId"] == preferred_part if preferred_part else b["visible"] and b["partId"].startswith("MELensSpot"))]
            self.h.check(choices, f"{side} no visible requested interior storage button: {state['windows']['loot']}")
            self.part = choices[0]["partId"]
            fixture = f'''
local v=getVehicleById({self.lab.vid});local c=v:getPartById({json.dumps(self.part)}):getItemContainer();assert(c)
local item=c:AddItem("Base.Pencil");assert(item);item:setName("Native UI loot {side}");item:getModData().MELensMPLootUIFixture={json.dumps(side)}
sendAddItemToContainer(c,item);return tostring(item:getID())
'''
            self.item_id = int(self.lab.server(fixture))
            before = self.authority()
            self.select_container(side, self.part)
            state = self.wait(side, lambda s: s["windows"]["loot"]["targetSelected"] and s["windows"]["loot"].get("row"), "correct container and exact item row visible/loaded")
            for _ in range(45):
                row = state["windows"]["loot"]["row"]
                if not row["above"] and not row["below"]:
                    break
                point = state["windows"]["loot"]["scrollUp" if row["above"] else "scrollDown"]
                self.click(side, point, "loot-scrollbar-to-exact-item")
                state = self.wait(side, lambda s: True, "scrollbar delivery")
            self.h.check(not row["above"] and not row["below"], "target row remained clipped")
            self.lab.capture(side, f"mp-loot-ui-{side.lower()}-exact-row")
            self.click(side, row, "loot-item-context-menu", right=True)
            label = self.api(side).lua('return getText("ContextMenu_Grab")')
            state = self.wait(side, lambda s: any(o["name"] == label for o in s["menus"]), "native row Grab option")
            options = [o for o in state["menus"] if o["name"] == label]
            self.h.check(len(options) == 1 and options[0]["enabled"], "native row Grab is ambiguous/disabled")
            self.click(side, options[0], "loot-context-Grab")
            after_local = self.wait(side, lambda s: s["itemInInventory"] and s["queueCount"] == 0, "native Grab owns exact ID")
            after = self.lab.wait(self.authority, lambda s: self.item_id not in s["source"] and
                                  s["players"].get(username, []).count(self.item_id) == 1,
                                  f"{side} Grab accepted once by dedicated server")
            for name, ids in after["players"].items():
                self.h.check(name == username or self.item_id not in ids, "Grab duplicated exact item into another player")
            receipt = self.h.record(f"mp-{side.lower()}-loot-window-context-grab", before, after,
                                   client=side,partId=self.part,itemId=self.item_id,localUI=after_local,
                                   uiHandlersInvokedDirectly=False,actionsQueuedDirectly=False)
            receipts.append(receipt)
            self.lab.capture(side, f"mp-loot-ui-{side.lower()}-grab-accepted")
        return {"passed": True, "cases": len(receipts), "vehicleId": self.lab.vid}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-206")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-loot-ui")
    parser.add_argument("--part", default=None, help="Optional exact visible part, e.g. MELensFloor; default first visible furniture storage")
    args = parser.parse_args()
    if args.part and not re.fullmatch(r"MELens[A-Za-z0-9]+", args.part):
        parser.error("--part must be an interior part ID")
    lab = None
    try:
        module = load_driver()
        lab = module.InteriorLab(args.session.resolve(), args.output.resolve())
        lab.h.REPORT["final"] = InventoryLab(lab, module).run(args.part)
        print(f"NATIVE_MP_LOOT_UI_PASSED {lab.h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        if lab:
            path = lab.h.write_report("failed", error)
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            path = args.output / "native-feature-tests.json"
            path.write_text(json.dumps({"status": "failed", "error": error}), encoding="utf-8")
        print(error, flush=True)
        print(f"NATIVE_MP_LOOT_UI_FAILED {path}; parent-owned clients/server left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
