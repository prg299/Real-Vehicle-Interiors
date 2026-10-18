"""Inert-on-import setup from the completed F700 MP test to a fresh camper.

The parent owns both inactive clients and the no-Java server. This preserves
inventories and the tested truck, queues ordinary exits/pathfinding, spawns one
fresh Flying Cloud 22 with the admin command, and uses actual E for both entries.
This is fixture setup, not additional exit/pathfinding acceptance evidence.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]


def interior_driver():
    path = Path(__file__).with_name("final-mp-interior-tests.py")
    spec = importlib.util.spec_from_file_location("melens_camper_setup_interiors", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_setup(lab, module):
    h, b = lab.h, lab.b
    h.REPORT.update(scope=__doc__.strip(), fixtureSetupOnly=True,
                    inventoriesPreserved=True, nativeEntryInput=True,
                    inputCoverage=["Space braking if required", "engine-toggle key if running",
                                   "E entry into fresh camper"])
    info = h.lua('local p=getPlayer(); local v=p:getVehicle(); return v and '
                 '{id=v:getId(),script=v:getScript():getFullName(),driver=v:isDriver(p),speed=v:getCurrentSpeedKmHour()} or false')
    h.check(isinstance(info, dict) and info["script"] == "Base.87fordF700box" and info["driver"],
            "setup must follow the completed F700 test with A in the driver seat")
    lab.vid = int(info["id"])
    h.check(b.lua(f'return getPlayer():getVehicle()==getVehicleById({lab.vid}) and MELens.isStanding(getPlayer())') is True,
            "B must still stand inside the tested F700")
    before = lab.all_states()
    h.REPORT["originalTruckId"] = lab.vid
    for api in (h, b):
        api.lua('if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end; '
                'MEMCNativeLab.releaseKeys(); return true')
    if abs(info["speed"]) >= .2:
        lab.input("A", key=57, milliseconds=1200)
        lab.wait(lab.all_states, lambda states: all(abs(s["vehicle"]["speed"]) < .5 for s in states.values()),
                 "old F700 stops before normal exits", timeout=20)
    engine_before = lab.wait(lab.all_states, lambda states: all(
        s.get("ready") and s["vehicle"]["engine"] == states["A"]["vehicle"]["engine"]
        for s in states.values()), "old F700 engine state agrees before its native stop input", timeout=20)
    stop_key = None
    if engine_before["A"]["vehicle"]["engine"]:
        stop_key = h.lua('return getCore():getKey(KeybindId.START_VEHICLE_ENGINE)')
        h.check(isinstance(stop_key, (int, float)) and stop_key > 0,
                f"vehicle engine-toggle key is unbound: {stop_key}")
        lab.input("A", key=int(stop_key))
    engine_after = lab.wait(lab.all_states, lambda states: all(
        s.get("ready") and s["vehicle"]["engine"] is False for s in states.values()),
        "old F700 engine is off on A/B/server before driver exit", timeout=30)
    h.REPORT["oldTruckEngineStop"] = {
        "before": {side: state["vehicle"]["engine"] for side, state in engine_before.items()},
        "after": {side: state["vehicle"]["engine"] for side, state in engine_after.items()},
        "nativeToggleKey": stop_key,
    }
    old_key = h.lua(f'local v=getVehicleById({lab.vid}); return v:getKeyId()')
    h.lua('local p=getPlayer(); local v=p:getVehicle(); ISVehicleMenu.onExit(p,v:getSeat(p)); return true')
    b.lua('MELens.leave(getPlayer()); return true')
    lab.wait(lab.all_states, lambda states: all(
        s["players"][name]["vehicleId"] != lab.vid for s in states.values()
        for name in ("MELensAdmin", "MELensGuest")), "ordinary client exits replicated to both clients/server", timeout=75)
    position = h.lua('local p=getPlayer(); return {x=p:getX(),y=p:getY()}')
    x0, y0 = math.floor(position["x"]), math.floor(position["y"])
    find = (f'local found={{}}; local it=getCell():getVehicles():iterator(); while it:hasNext() do local v=it:next(); '
            'if v:getScript():getFullName()=="Base.Trailer54FlyingCloud22" '
            f'and (v:getX()-{x0})^2+(v:getY()-{y0})^2<40000 then found[#found+1]=v:getId() end end; ')
    def server_ids():
        value = json.loads(lab.server(module.JSON_ENCODER + find + "return enc(found)"))
        return set(h._sequence(value))
    existing = server_ids()
    chosen = None
    attempts = []
    for dx, dy in ((-9, 0), (-9, 8), (-9, -8), (-15, 0)):
        # Query again before a retry so a delayed previous spawn is adopted,
        # rather than blindly sending another mutation after an unknown outcome.
        fresh = server_ids() - existing
        if fresh:
            h.check(len(fresh) == 1, f"ambiguous fresh camper spawn: {fresh}")
            chosen = int(next(iter(fresh)))
            break
        sx, sy = x0 + dx, y0 + dy
        h.lua(f"SendCommandToServer('/addvehicle Base.Trailer54FlyingCloud22 {sx},{sy},0'); return true")
        attempts.append({"x": sx, "y": sy, "command": "/addvehicle Base.Trailer54FlyingCloud22"})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            fresh = server_ids() - existing
            if fresh:
                h.check(len(fresh) == 1, f"ambiguous fresh camper spawn: {fresh}")
                chosen = int(next(iter(fresh)))
                break
            time.sleep(.25)
        if chosen is not None:
            break
    h.check(chosen is not None, f"no fresh camper spawned on the owned field: {attempts}")
    lab.vid = chosen
    h.REPORT["spawn"] = {"vehicleId": chosen, "attempts": attempts, "previousIds": sorted(existing),
                          "serverNoJava": True, "oldTruckPreserved": True}
    lab.server(f'local v=getVehicleById({chosen}); assert(v); v:repair(); '
               'for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); local door=part:getDoor(); '
               'if door then door:setLocked(false); v:transmitPartDoor(part) end end; return "repaired/unlocked"')
    for side, api in (("A", h), ("B", b)):
        lab.wait(lambda api=api: api.lua(f'local v=getVehicleById({chosen}); return v and v:getPartCount()>0 '
                                        'and v:getPartById("MELensGenerator")~=nil and v:getPartById("MELensWaterTank")~=nil'),
                 bool, f"{side} sees fresh camper and utility part IDs", timeout=35)
        api.lua(f'MELensTest=MELensTest or {{}}; MELensTest.vehicle=getVehicleById({chosen}); return true')
        lab.wait(lambda api=api: api.lua('local ok=MELens.canWalkIn(getPlayer(),MELensTest.vehicle); return ok==true'),
                 bool, f"{side} camper physics settled and entry available", timeout=45)
        lab.enter_e(side)  # queues only the approach; E itself enters normally
    after = lab.wait(lab.all_states, lambda states: all(
        s.get("ready") and s["players"].get(name, {}).get("vehicleId") == chosen
        and s["players"].get(name, {}).get("standing") is True
        for s in states.values() for name in ("MELensAdmin", "MELensGuest")),
        "both real E entries have authoritative standing membership", timeout=35)
    # The driver getting out of the old truck pockets its ignition key (the game's own exit in multiplayer, whatever
    # the client's leave-key option says). That one item, and nothing else, may be new in A's inventory.
    pocketed = h.lua(f'local out={{}}; local items=getPlayer():getInventory():getItems(); '
                     f'for i=0,items:size()-1 do local it=items:get(i); '
                     f'if it:getFullType()=="Base.CarKey" and it:getKeyId()=={int(old_key)} then out[#out+1]=it:getID() end end; '
                     f'local v=getVehicleById({lab.vid}); return {{ids=out, inIgnition=v:isKeysInIgnition()}}')
    h.REPORT["oldTruckIgnitionKey"] = {"keyId": old_key, "carriedKeyIds": pocketed}
    for side, name in (("A", "MELensAdmin"), ("B", "MELensGuest"),
                       ("server", "MELensAdmin"), ("server", "MELensGuest")):
        old = h._sequence(before[side]["players"][name].get("inventory"))
        new = h._sequence(after[side]["players"][name].get("inventory"))
        added = sorted(set(new) - set(old))
        if name == "MELensAdmin" and len(added) == 1 and isinstance(pocketed, dict)                 and added[0] in h._sequence(pocketed.get("ids")):
            h.REPORT["oldTruckIgnitionKey"]["pocketedOn" + side] = added[0]
            new = [i for i in new if i != added[0]]
        h.check(sorted(old) == sorted(new), f"camper setup altered {side}/{name} inventory IDs")
    lab.h.record("fresh-camper-both-native-e-entries-ready-for-dashboard", before, after,
                 setupOnly=True, noInventoryCleared=True, oldTruckPreserved=True)
    lab.capture("A", "mp-camper-actor-ready")
    lab.capture("B", "mp-camper-observer-ready")
    return after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-206")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-camper-setup")
    args = parser.parse_args()
    module = interior_driver()
    lab = module.InteriorLab(args.session.resolve(), args.output.resolve())
    try:
        lab.h.REPORT["final"] = run_setup(lab, module)
        print(f"MP_CAMPER_SETUP_READY {lab.h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            lab.h.REPORT["lastSnapshot"] = lab.all_states()
        except Exception:
            lab.h.REPORT["lastSnapshot"] = None
        path = lab.h.write_report("failed", error)
        print(error, flush=True)
        print(f"MP_CAMPER_SETUP_FAILED {path}; parent-owned clients/server left running", flush=True)
        return 1
    finally:
        for api in (lab.h, lab.b):
            try:
                api.lua('MEMCNativeLab.releaseKeys(); return true')
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
