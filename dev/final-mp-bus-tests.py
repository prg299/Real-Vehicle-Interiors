"""B700 smoke in already connected parent-owned MP clients; import is inert.

The KI5 bus has fifteen stock seats and one standing slot under the engine's
sixteen-passenger limit. Both players enter with real E and alternate standing
using native Rest context menus and E. Optional --drive adds actual W/Space.
Setup exits, approach paths, admin spawns/repair/key creation are fixture setup.
This driver never saves, launches, disconnects, stops or restarts a game/server.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
BUS = "Base.87fordB700school"
NAMES = {"A": "MELensAdmin", "B": "MELensGuest"}


def load_interiors():
    spec = importlib.util.spec_from_file_location("melens_native_mp_bus", Path(__file__).with_name("final-mp-interior-tests.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEAT_POINT = r'''
local p=getPlayer(); local v=p:getVehicle(); assert(v)
local q,P,I=MELens.profileFor(v),MELens.Parts,MELens.Interact
local o=v:getScript():getModel():getOffset(); local base=v:getWorldPos(0,0,0,Vector3f.new()):z()
local zoom=getCore():getZoom(p:getPlayerNum()); local candidates={}
for i,s in ipairs(q.spots) do local part=P.spotPart(v,i); local piece=P.pieceAt(part); local kit=piece and P.kit(piece)
    if kit and kit.kind=="seat" and not P.seatTaken(v,part) then
        candidates[#candidates+1]={index=i,spot=s,piece=piece,d=(s.x-q.door.x)^2+(s.z-q.door.z)^2}
    end
end
table.sort(candidates,function(a,b) return a.d<b.d end)
for _,c in ipairs(candidates) do local s=c.spot; local _,depth,height=P.footprint(s,c.piece)
    for _,a in ipairs({0,-.15,.15,-.3,.3}) do for _,d in ipairs({depth/2,depth-.08,.08}) do
        local x,z=P.spotPoint(s,a,d)
        for _,h in ipairs({.01,.1,.2}) do local top=q.floorY+(s.rise or 0)+height-h
            local w=v:getWorldPos(o:x()+x,o:y()+top,o:z()+z,Vector3f.new())
            local sx,sy=ISCoordConversion.ToScreen(w:x(),w:y(),base+(o:y()+top)/2.44949)
            local hit=I.pick(v,q,sx,sy); local px,py=math.floor(sx/zoom+.5),math.floor(sy/zoom+.5)
            if px>10 and px<1270 and py>10 and py<710 and hit and hit.index==c.index then
                return {index=c.index,piece=c.piece,x=px,y=py}
            end
        end
    end end
end
return false
'''

REST_MENU = r'''
local c=getPlayerContextMenu(0); if not c or not c:isVisible() then return false end
for i,o in ipairs(c.options) do local sub=o.subOption and c:getSubMenu(o.subOption)
    for j,k in ipairs(sub and sub.options or {}) do if k.name==getText('ContextMenu_Rest') then
        return {parentX=math.floor(c:getX()+math.min(c:getWidth()/2,70)),parentY=math.floor(c:getItemY(i)+c.itemHgt/2),
            x=math.floor(sub:getX()+math.min(sub:getWidth()/2,70)),y=math.floor(sub:getItemY(j)+sub.itemHgt/2),
            visible=sub:isVisible(),disabled=k.notAvailable==true or k.isDisabled==true}
    end end
end
return false
'''


def player(states, side, name):
    return states.get(side, {}).get("players", {}).get(name, {})


def all_player(states, name, predicate):
    return all(state.get("ready") and predicate(state.get("players", {}).get(name, {})) for state in states.values())


class BusSmoke:
    def __init__(self, session, output):
        self.module = load_interiors()
        self.lab = self.module.InteriorLab(session, output)
        self.h, self.b = self.lab.h, self.lab.b
        self.metadata = json.loads((session / "session.json").read_text(encoding="utf-8-sig"))
        self.h.REPORT.update(scope=__doc__.strip(), bus=BUS, standingCapacityLimit=1,
                             lootNativeMouseInput=False, lootUsesProductionTransferAction=False,
                             inputCoverage=["E entry", "native Rest context menu", "E stand", "E driver-seat entry"])
        self.logs = {}
        for record in self.metadata["clients"]:
            path = Path(record["cache"]) / "console.txt"
            self.logs[path] = path.stat().st_size if path.is_file() else 0
        path = Path(self.metadata["serverConsole"])
        self.logs[path] = path.stat().st_size if path.is_file() else 0

    def setup(self):
        lab, h = self.lab, self.h
        h.check(lab.server('return tostring(isServer()).."/"..tostring(MELensRV==nil)') == "true/true", "server must run without RVI Java")
        for api in (h, self.b):
            api.lua('local p=getPlayer(); if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end; '
                    'MEMCNativeLab.releaseKeys(); ISUIHandler.setVisibleAllUI(false); local v=p:getVehicle(); '
                    'if v then if MELens.isStanding(p) then MELens.leave(p) else ISVehicleMenu.onExit(p,v:getSeat(p)) end end; return true')
            lab.wait(lambda api=api: api.lua('return getPlayer():getVehicle()==nil'), bool, "ordinary setup exit from previous test vehicle", timeout=75)
        h.lua("SendCommandToServer('/teleportto 10845,10144,0'); return true")
        lab.wait(lambda: h.lua('local p=getPlayer(); return p:getCurrentSquare() and math.abs(p:getX()-10845)<2 and math.abs(p:getY()-10144)<2'), bool, "admin at owned bus field")
        h.lua('SendCommandToServer(\'/teleportplayer "MELensGuest" "MELensAdmin"\'); return true')
        lab.wait(lambda: self.b.lua('local p=getPlayer(); return p:getCurrentSquare() and math.abs(p:getX()-10845)<4 and math.abs(p:getY()-10144)<4'), bool, "guest at owned bus field")
        find = ('local a={}; local it=getCell():getVehicles():iterator(); while it:hasNext() do local v=it:next(); '
                f'if v:getScript():getFullName()=="{BUS}" and (v:getX()-10845)^2+(v:getY()-10144)^2<40000 then a[#a+1]=v:getId() end end; ')
        def ids():
            return set(h._sequence(json.loads(lab.server(self.module.JSON_ENCODER + find + "return enc(a)"))))
        old = ids(); attempts = []
        for x, y in ((10830, 10144), (10830, 10154), (10830, 10134), (10823, 10144)):
            fresh = ids() - old
            if not fresh:
                h.lua(f"SendCommandToServer('/addvehicle {BUS} {x},{y},0'); return true")
                attempts.append({"x": x, "y": y})
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    fresh = ids() - old
                    if fresh: break
                    time.sleep(.2)
            if fresh:
                h.check(len(fresh) == 1, f"ambiguous fresh bus spawn: {fresh}")
                lab.vid = int(next(iter(fresh))); break
        h.check(lab.vid >= 0, "no bus spawned on clear owned field")
        h.REPORT["spawn"] = {"vehicleId": lab.vid, "attempts": attempts, "oldVehiclesPreserved": True}
        lab.server(f'local v=getVehicleById({lab.vid}); assert(v); '
                   'for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); local door=part:getDoor(); '
                   'if door then door:setLocked(false); v:transmitPartDoor(part) end end; '
                   'local gas=v:getPartById("GasTank"); if gas then gas:setContainerContentAmount(gas:getContainerCapacity()); v:transmitPartUsedDelta(gas) end; '
                   'local ps=getOnlinePlayers(); for i=0,ps:size()-1 do local p=ps:get(i); if p:getUsername()=="MELensAdmin" then '
                   'local key=v:createVehicleKey(); p:getInventory():AddItem(key); sendAddItemToContainer(p:getInventory(),key) end end; return "prepared"')
        extra = f'local v=getVehicleById({lab.vid}); assert(v); local p=MELens.profileFor(v); return {{max=v:getMaxPassengers(),standing=#MELens.standingIds(p)}}'
        for side, api in (("A", h), ("B", self.b)):
            lab.wait(lambda api=api: api.lua(f'return getVehicleById({lab.vid})~=nil'), bool, f"{side} sees bus")
        capacities = {"A": h.lua(extra), "B": None, "server": None}
        capacities["B"] = self.b.lua(extra)
        server_code = extra.replace("return {", "local r={") + "\nreturn enc(r)"
        capacities["server"] = json.loads(lab.server(self.module.JSON_ENCODER + server_code))
        h.check(all(row["max"] <= 16 and row["max"] == capacities["A"]["max"] and row["standing"] == 1 for row in capacities.values()), "bus passenger/standing limit differs or exceeds engine capacity")
        h.REPORT["capacities"] = capacities
        states = lab.all_states()
        h.check(states["A"]["partIds"] == states["B"]["partIds"] == states["server"]["partIds"], "bus network part order differs")
        for side, api in (("A", h), ("B", self.b)):
            api.lua(f'MELensTest=MELensTest or {{}}; MELensTest.vehicle=getVehicleById({lab.vid}); return true')
        lab.wait(lambda: h.lua('local ok=MELens.canWalkIn(getPlayer(),MELensTest.vehicle); return ok==true'), bool, "bus settled and first standing entry available")
        lab.enter_e("A")
        after = lab.wait(lab.all_states, lambda ss: all_player(ss, NAMES["A"], lambda p: p.get("standing") is True), "A first standing bus entry reaches no-Java server")
        h.record("bus-sixteen-seat-limit-identical-parts-and-a-native-entry", states, after, capacities=capacities)

    def rest(self, side):
        lab, api = self.lab, self.h if side == "A" else self.b
        before = lab.all_states()
        point = api.lua(SEAT_POINT)
        self.h.check(point, f"{side} has no visible free bus seat")
        lab.input(side, x=point["x"], y=point["y"], right=True)
        menu = lab.wait(lambda: api.lua(REST_MENU), bool, f"{side} genuine bus Rest menu")
        self.h.check(not menu["disabled"], "free bus Rest option is disabled")
        lab.capture(side, "mp-bus-" + side.lower() + "-rest-menu")
        lab.input(side, x=menu["parentX"], y=menu["parentY"])
        menu = lab.wait(lambda: api.lua(REST_MENU), lambda s: bool(s) and s["visible"], "bus seat submenu opens through native click")
        lab.input(side, x=menu["x"], y=menu["y"])
        after = lab.wait(lab.all_states, lambda ss: all_player(ss, NAMES[side], lambda p: p.get("vehicleId") == lab.vid and p.get("standing") is False and p.get("seat", -1) > 0),
                         f"{side} native Rest seats the player on A/B/server")
        self.h.record("bus-" + side.lower() + "-native-rest", before, after, furnitureIndex=point["index"])
        return after

    def run(self, drive):
        lab, h = self.lab, self.h
        self.setup()
        self.rest("A")
        lab.enter_e("B")
        before = lab.wait(lab.all_states, lambda ss: all_player(ss, NAMES["A"], lambda p: p.get("standing") is False and p.get("seat", -1) > 0)
                          and all_player(ss, NAMES["B"], lambda p: p.get("standing") is True)
                          and all(s["players"][NAMES["A"]]["seat"] != s["players"][NAMES["B"]]["seat"] for s in ss.values()),
                          "second native E bus entry uses the freed standing slot and distinct seats")
        h.record("bus-two-real-players-enter-and-occupy-distinct-seats", {}, before, simultaneousStandingSupported=False)
        self.rest("B")
        lab.input("A", key=18)
        after = lab.wait(lab.all_states, lambda ss: all_player(ss, NAMES["A"], lambda p: p.get("standing") is True)
                         and all_player(ss, NAMES["B"], lambda p: p.get("standing") is False and p.get("seat", -1) > 0), "A native E stands after B frees the only standing slot")
        h.record("bus-native-e-get-up-alternates-standing-slot", before, after)
        lab.capture("A", "mp-bus-a-standing")
        lab.capture("B", "mp-bus-b-seated")
        h.lua('local p=getPlayer(); local x,z=MELens.driverStandPoint(MELens.profileFor(p:getVehicle())); MELens.walkTo(p,x,z); return true')
        lab.wait(lambda: h.lua('local p=getPlayer(); local q=ISTimedActionQueue.queues[p]; return not MELens.pathing(p) and (not q or #q.queue==0)'), bool, "normal aisle walk reaches driver's seat")
        lab.input("A", key=18)
        after = lab.wait(lab.all_states, lambda ss: all_player(ss, NAMES["A"], lambda p: p.get("seat") == 0 and p.get("standing") is False), "native E sits in bus driver's seat on A/B/server")
        lab.input("B", key=18)
        before = lab.wait(lab.all_states, lambda ss: all_player(ss, NAMES["B"], lambda p: p.get("standing") is True), "guest native E stands while admin drives")
        h.record("bus-native-driver-entry-keeps-guest-standing-slot", after, before)
        if drive:
            h.lua('ISTimedActionQueue.add(ISStartVehicleEngine:new(getPlayer())); return true')
            lab.wait(lab.all_states, lambda ss: all(s["vehicle"]["engine"] for s in ss.values()), "bus engine starts authoritatively", timeout=30)
            self.b.lua('MEMCNativeLab.releaseKeys(); return true')
            lab.input("A", key=17, milliseconds=2000)
            samples = []; deadline = time.monotonic() + 2.5
            while time.monotonic() < deadline:
                samples.append(lab.all_states()); time.sleep(.15)
            lab.input("A", key=57, milliseconds=2000)
            after = lab.wait(lab.all_states, lambda ss: all(lab.aligned(s) for s in ss.values()) and abs(ss["A"]["vehicle"]["speed"]) < .5, "bus stops and standing guest stays aligned")
            distance = math.hypot(after["A"]["vehicle"]["x"]-before["A"]["vehicle"]["x"], after["A"]["vehicle"]["y"]-before["A"]["vehicle"]["y"])
            h.check(distance > 1, "actual W did not move bus sufficiently")
            significant = [s for s in samples if abs(s["A"]["vehicle"]["speed"]) > 1]
            h.check(significant and all(lab.aligned(s["A"], 1) for s in significant), "driver observer left standing bus passenger behind")
            h.record("bus-actual-w-driving-keeps-standing-guest-aligned", before, after, displacementTiles=distance, samples=samples)
            ignition = h.lua('return getCore():getKey(KeybindId.START_VEHICLE_ENGINE)')
            h.check(isinstance(ignition, (int, float)) and ignition > 0, "configured native engine key missing")
            lab.input("A", key=int(ignition))
            stopped = lab.wait(lab.all_states, lambda ss: all(not s["vehicle"]["engine"] for s in ss.values()), "native ignition key stops bus engine on A/B/server")
            h.record("bus-native-ignition-stops-engine-before-persistence", after, stopped)
        final = lab.all_states()
        lab.capture("A", "mp-bus-final-driver")
        lab.capture("B", "mp-bus-final-standing-guest")
        failures = []
        for path, offset in self.logs.items():
            if not path.is_file(): continue
            with path.open("rb") as stream:
                if path.stat().st_size >= offset: stream.seek(offset)
                tail = stream.read().decode("utf-8", errors="replace")
            for line in tail.splitlines():
                if re.search(r"PassengerMap|ArrayIndexOutOfBoundsException|doDisconnect|MELens[A-Za-z_]*\.lua:\d+\)", line):
                    failures.append({"path": str(path), "line": line})
        h.check(not failures, f"new bus-period engine/mod/disconnect errors: {failures[:8]}")
        h.REPORT["newLogErrors"] = failures
        h.REPORT["final"] = final
        lab.server(f'local v=getVehicleById({lab.vid}); local m=v:getModData(); '
                   'm.MELensNativeBusSmoke206={script=v:getScript():getFullName(),vehicleId=v:getId(),maxPassengers=v:getMaxPassengers()}; '
                   'v:transmitModData(); return "marked for parent persistence checkpoint"')
        return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-206")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-bus")
    parser.add_argument("--drive", action="store_true")
    args = parser.parse_args()
    smoke = None
    try:
        smoke = BusSmoke(args.session.resolve(), args.output.resolve())
        smoke.run(args.drive)
        print(f"NATIVE_MP_BUS_PASSED {smoke.h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        if smoke is not None:
            try: smoke.h.REPORT["lastSnapshot"] = smoke.lab.all_states()
            except Exception: pass
            path = smoke.h.write_report("failed", error)
        else:
            args.output.mkdir(parents=True, exist_ok=True); path = args.output / "native-feature-tests.json"
            path.write_text(json.dumps({"status": "failed", "nativeInput": False, "preconditionFailure": True, "error": error}, indent=2) + "\n", encoding="utf-8")
        print(error, flush=True); print(f"NATIVE_MP_BUS_FAILED {path}; parent-owned clients/server left running", flush=True)
        return 1
    finally:
        if smoke is not None:
            for api in (smoke.h, smoke.b):
                try: api.lua('MEMCNativeLab.releaseKeys(); return true')
                except Exception: pass
            try: smoke.h.lua('local p=getPlayer(); if p:getVehicle() and p:getVehicle():isDriver(p) then MEMCNativeLab.holdKey(57,1500) end; return true')
            except Exception: pass


if __name__ == "__main__":
    raise SystemExit(main())
