"""Actual MP Dashboard input in two already owned clients; import performs no I/O.

A (admin,18470) and B (18472) must stand inside the same Flying Cloud 22. The
parent owns both clients/server and their guarded lifetime. Setup mutations run
only in the server's admin MELensDev eval. Feature work uses native A mouse input;
each case checks server authority and B replication before recording success.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/rv/final-mp-features"
ENDPOINT_A = "http://127.0.0.1:18470/lua?depth=8&sandbox=false"
ENDPOINT_B = "http://127.0.0.1:18472/lua?depth=8&sandbox=false"
SCREENS_A = ROOT / "build/rv/final-mp-206/client-a/home/Zomboid/Screenshots"


def load_helpers():
    spec = importlib.util.spec_from_file_location("melens_mp_features", Path(__file__).with_name("final-feature-tests.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lua_long(text):
    equals = "="
    while f"]{equals}]" in text:
        equals += "="
    return f"[{equals}[{text}]{equals}]"


class ServerEval:
    """Single outstanding admin eval: the dev mod has one shared response slot."""
    def __init__(self, helpers):
        self.h = helpers
        self.id = 600000 + int(time.time() * 1000) % 1000000

    def __call__(self, code, timeout=20):
        self.id += 1
        request_id = self.id
        self.h.lua('MELensDevResult=nil; sendClientCommand(getPlayer(),"MELensDev","eval",'
                   f'{{id={request_id},code={lua_long(code)}}}); return true')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            reply = self.h.lua("return MELensDevResult")
            if isinstance(reply, dict) and reply.get("id") == request_id:
                result = str(reply.get("text", ""))
                if result.startswith(("error:", "compile error:")):
                    raise RuntimeError(f"Authoritative server eval failed: {result}")
                return result
            time.sleep(.10)
        raise TimeoutError(f"Admin server eval {request_id} did not reply")


UTILITIES_READ = r'''
local U=MELens.Utilities
local g,w=U.generatorState(v),U.waterState(v)
assert(g and w,"replicated utility parts missing")
local u={generatorOn=g.on,generatorRunning=g.running,generatorFuel=g.fuel,
    generatorCapacity=g.capacity,generatorCondition=g.condition,water=w.water,
    waterCapacity=w.capacity,tainted=w.tainted,propane=U.propaneLevel(v),
    stoveOn=U.isOn(v,"stove"),heaterOn=U.isOn(v,"heater"),
    lightsOn=v:getModData().MELensLightsOff~=true,hasPower=U.hasPower(v)}
'''


SERVER_FIXTURE = r'''
assert(isServer() and not isClient(),"fixture must run on the dedicated server")
local aid,bid,vid=ACTOR_ID,OBSERVER_ID,VEHICLE_ID
local p,b
local players=getOnlinePlayers()
for i=0,players:size()-1 do
    local q=players:get(i)
    if q:getOnlineID()==aid then p=q end
    if q:getOnlineID()==bid then b=q end
end
local v=getVehicleById(vid)
assert(p and b and v and p:getVehicle()==v and b:getVehicle()==v,"both server characters must occupy the same camper")
assert(v:getScript():getFullName()=="Base.Trailer54FlyingCloud22","MP feature fixture requires FlyingCloud22")
local M,U,P=MELens,MELens.Utilities,MELens.Parts
local inv=p:getInventory()
local T=MELensMPFeatureTest
assert(not T or RESET_ALLOWED,"fixture already exists; explicit --reset-fixture required to replenish supplies")
T={player=p,observer=b,vehicle=v,items={},serverOnlySetup=true}
MELensMPFeatureTest=T
-- Remove unrelated automatic drinking as a fixture variable before supplies
-- arrive. B42 uses CharacterStat, with the normal authoritative stats packet.
p:getStats():set(CharacterStat.THIRST,0)
syncPlayerStats(p,SyncPlayerStatsPacket.Stat_Thirst)
local function own(key,full)
    local item=inv:getFirstEvalRecurse(function(i)
        return i:getFullType()==full and i:getModData().MELensFeatureFixture==key
    end)
    local fresh=item==nil
    if fresh then item=inv:AddItem(full) end
    assert(item,"missing native server item "..full)
    assert(item:getContainer()==inv,"move existing tagged fixture item into the admin's main inventory first")
    item:getModData().MELensFeatureFixture=key
    T.items[key]=item
    return item,fresh
end
local function fill(item,kind,amount)
    local fc=item:getFluidContainer()
    assert(fc,"native fixture item has no fluid component")
    if fc:getAmount()>0 then fc:removeFluid(fc:getAmount()) end
    fc:addFluid(kind,amount)
end
local petrol,np=own("petrol","Base.PetrolCan")
local water,nw=own("water","Base.WaterBottle")
local propane,ng=own("propane","Base.PropaneTank")
local scrap,ns=own("scrap","Base.ElectronicsScrap")
fill(petrol,Fluid.Petrol,.5); fill(water,Fluid.Water,.5); propane:setUsedDelta(.1)
for _,pair in ipairs({{petrol,np},{water,nw},{propane,ng},{scrap,ns}}) do
    if pair[2] then sendAddItemToContainer(inv,pair[1]) end
    pair[1]:syncItemFields()
end
-- Do not silently remove competing supplies from the owned character.
assert(inv:getFirstEvalRecurse(function(i) return P.fluidIn(i,"petrol")~=nil end)==petrol,"another petrol supply precedes the tagged fixture")
assert(inv:getFirstEvalRecurse(function(i) return P.fluidIn(i,"water")~=nil end)==water,"another water supply precedes the tagged fixture")
assert(inv:getFirstEvalRecurse(function(i) return P.propaneIn(i)>0 end)==propane,"another propane supply precedes the tagged fixture")
assert(inv:getFirstTypeRecurse("ElectronicsScrap")==scrap,"another repair scrap precedes the tagged fixture")
local g,w=U.generatorState(v),U.waterState(v)
local oven,heater=v:getPartById(P.OVEN),U.heaterPart(v)
local battery=v:getBattery()
assert(g and w and oven and heater and battery and battery:getInventoryItem(),"camper needs generator/water/oven/heater/battery parts")
g.part:getModData().on=false; g.part:getModData().fuel=0
g.part:getModData().wear=0; g.part:getModData().sync=0; g.part:setCondition(80)
w.part:getModData().water=0; w.part:getModData().tainted=false
oven:getModData().on=false; oven:getModData().heat=1
heater:getModData().on=false
U.setPropane(v,0,true)
v:getModData().MELensLightsOff=true
if U.observeLamps then U.observeLamps(v,true) end
battery:getInventoryItem():setUsedDelta(.5)
v:transmitPartUsedDelta(battery)
v:transmitPartCondition(g.part)
for _,part in ipairs({g.part,w.part,oven,heater}) do U.transmit(v,part) end
v:transmitModData()
U.wake(v)
function T.snapshotText()
    local v,p,b=T.vehicle,T.player,T.observer
    UTILITIES_BODY
    local rows={}
    local function put(key,value) rows[#rows+1]=key.."="..tostring(value) end
    put("isServer",isServer()); put("vehicleId",v:getId())
    put("actorInside",p:getVehicle()==v); put("observerInside",b:getVehicle()==v)
    put("actorElectricity",p:getPerkLevel(Perks.Electricity))
    put("worldHour",getGameTime():getWorldAgeHours())
    put("batteryCharge",v:getBattery():getInventoryItem():getCurrentUsesFloat())
    put("lampRate",MELens.Utilities.LAMP_DRAIN_PER_HOUR)
    put("engineRunning",v:isEngineRunning()); put("headlightsOn",v:getHeadlightsOn())
    local occupants=0
    for seat=0,v:getMaxPassengers()-1 do
        local occupant=v:getCharacter(seat)
        if occupant and occupant:getVehicle()==v and not occupant:isDead() then occupants=occupants+1 end
    end
    put("occupants",occupants)
    for key,value in pairs(u) do put("utilities."..key,value) end
    for key,item in pairs(T.items) do
        local fc=item:getFluidContainer()
        put("inventory."..key..".id",item:getID())
        put("inventory."..key..".inMainInventory",p:getInventory():contains(item))
        put("inventory."..key..".amount",fc and fc:getAmount() or 0)
        put("inventory."..key..".propane",MELens.Parts.propaneIn(item))
    end
    table.sort(rows)
    return table.concat(rows,";")
end
function T.fullCapacity()
    local v,U=T.vehicle,MELens.Utilities
    local g,w=U.generatorState(v),U.waterState(v)
    assert(not g.on and not U.isOn(v,"stove") and not U.isOn(v,"heater"),"stop appliances before capacity fixture")
    g.part:getModData().fuel=g.capacity
    U.changeWater(v,w.capacity-w.water,false)
    U.setPropane(v,U.PROPANE_CAPACITY,true)
    T.items.petrol:getFluidContainer():addFluid(Fluid.Petrol,.25)
    T.items.water:getFluidContainer():addFluid(Fluid.Water,.25)
    T.items.propane:setUsedDelta(.1)
    for _,key in ipairs({"petrol","water","propane"}) do T.items[key]:syncItemFields() end
    U.transmit(v,g.part); U.transmit(v,w.part)
    return T.snapshotText()
end
return T.snapshotText()
'''


def parse_server(text):
    result = {}
    for row in text.split(";"):
        key, value = row.split("=", 1)
        if value in ("true", "false"):
            value = value == "true"
        else:
            try:
                value = float(value)
                if value.is_integer():
                    value = int(value)
            except ValueError:
                pass
        target = result
        fields = key.split(".")
        for field in fields[:-1]:
            target = target.setdefault(field, {})
        target[fields[-1]] = value
    return result


def server_state(server):
    state = parse_server(server("assert(MELensMPFeatureTest,'server fixture missing'); return MELensMPFeatureTest.snapshotText()"))
    if state.get("isServer") is not True:
        raise AssertionError(f"invalid authority receipt: {state}")
    return state


def observer_state(b, vehicle_id):
    code = f'local v=getVehicleById({vehicle_id}); if not v then return false end; '
    code += UTILITIES_READ
    code += 'return {vehicleId=v:getId(),inside=getPlayer():getVehicle()==v,utilities=u}'
    return b.lua(code)


def compatible(h, expected, actual, key, running=False):
    if isinstance(expected, bool):
        return actual is expected
    if isinstance(expected, (float, int)):
        # Production batches generator state every ten game minutes and propane
        # every .01 tank. These are replication bounds, recorded in the receipt.
        tolerance = .134 if key == "generatorFuel" and running else .0101 if key == "propane" else .0003
        return actual is not None and h._near(expected, actual, tolerance)
    return actual == expected


def verify_receipt(h, b, server, vehicle_id, after, name, previous=None, timeout=20):
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        authority = server_state(server)
        observer = observer_state(b, vehicle_id)
        actor = h.snapshot()
        mismatch = []
        if not authority.get("actorInside") or not authority.get("observerInside"):
            mismatch.append("server occupants")
        if not isinstance(observer, dict) or not observer.get("inside"):
            mismatch.append("B not inside the replicated camper")
        else:
            for key, expected in after["utilities"].items():
                truth = authority["utilities"].get(key)
                running = authority["utilities"].get("generatorOn", False)
                if not compatible(h, expected, truth, key, running):
                    mismatch.append(f"case/server {key}")
                if not compatible(h, truth, observer["utilities"].get(key), key, running):
                    mismatch.append(f"server/B {key}")
                if not compatible(h, truth, actor["utilities"].get(key), key, running):
                    mismatch.append(f"server/A {key}")
        for key, expected in after["inventory"].items():
            truth = authority.get("inventory", {}).get(key, {})
            for field in ("id", "inMainInventory", "amount", "propane"):
                if not compatible(h, expected[field], truth.get(field), field):
                    mismatch.append(f"A/server {key}.{field}")
        if name == "generator-burns-fuel" and previous:
            if authority["utilities"]["generatorFuel"] >= previous["server"]["utilities"]["generatorFuel"] - .00001:
                mismatch.append("no authoritative generator fuel burn")
            if not isinstance(observer, dict) or observer["utilities"]["generatorFuel"] >= previous["observerB"]["utilities"]["generatorFuel"] - .00001:
                mismatch.append("B has not received generator fuel burn")
        last = {"server": authority, "observerB": observer, "actorA": actor, "mismatches": mismatch}
        if not mismatch:
            return last
        time.sleep(.20)
    raise AssertionError(f"{name}: authority/replication did not settle: {json.dumps(last, ensure_ascii=False)}")


def seed_client(h, state, vehicle_id):
    ids = {key: row["id"] for key, row in state["inventory"].items()}
    rows = ",".join(f'{key}={int(value)}' for key, value in ids.items())
    code = f'''
local p=getPlayer(); local v=getVehicleById({vehicle_id}); local ids={{{rows}}}
assert(isClient() and v and p:getVehicle()==v,"A must stand in the target replicated camper")
local items={{}}
for key,id in pairs(ids) do
    local item=p:getInventory():getFirstEvalRecurse(function(i)
        return i:getID()==id and i:getModData().MELensFeatureFixture==key
    end)
    if not item then return false end
    items[key]=item
end
MELensTest=MELensTest or {{}}; MELensTest.vehicle=v
MELensFeatureTest={{player=p,vehicle=v,initialized=true,items=items,setupCount=1,
    setupNote="server-created native MP supplies, matched by replicated tag and item ID"}}
MELensFeatureTestReset=nil
return true
'''
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if h.lua(code) is True:
            # Initialized is already true: loading this only defines the read-only
            # snapshot; it does not enter its SP inventory/part initialization.
            h.lua((ROOT / "dev/lua/feature-fixture.lua").read_text(encoding="utf-8"))
            return ids
        time.sleep(.15)
    raise TimeoutError("Server-created fixture item IDs/tags did not replicate to A")


def battery_replicas(h, b, server, vehicle_id, timeout=15):
    code = (f'local v=getVehicleById({vehicle_id}); local battery=v and v:getBattery(); '
            'local item=battery and battery:getInventoryItem(); '
            'return item and {charge=item:getCurrentUsesFloat(),lightsOn=v:getModData().MELensLightsOff~=true} or false')
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        truth, actor, observer = server_state(server), h.lua(code), b.lua(code)
        last = {"server": truth, "actorA": actor, "observerB": observer}
        if isinstance(actor, dict) and isinstance(observer, dict) and all(
                # The observed stable authority/client float gap is
                # 0.000010014 on both clients. This
                # replication bound does not relax authoritative drain checks.
                h._near(copy["charge"], truth["batteryCharge"], .00002)
                and copy["lightsOn"] is truth["utilities"]["lightsOn"] for copy in (actor, observer)):
            return last
        time.sleep(.15)
    raise AssertionError(f"native battery replicas differ: {json.dumps(last, ensure_ascii=False)}")


def run_lamp_case(h, b, server, vehicle_id, seconds=30):
    """Paired real elapsed off/on windows; no time setters or direct lamp callbacks."""
    h.check(30 <= seconds <= 120, "lamp window must be 30..120 real seconds")
    initial_actor = h.snapshot()
    h.check(not initial_actor["utilities"]["lightsOn"], "lamp control must begin switched off")
    off_before = battery_replicas(h, b, server, vehicle_id)
    h.check(off_before["server"]["occupants"] == 2 and not off_before["server"]["engineRunning"]
            and not off_before["server"]["headlightsOn"]
            and not off_before["server"]["utilities"]["generatorRunning"],
            "lamp control needs two occupants, engine/generator/headlights off")
    def window():
        began, samples = time.monotonic(), []
        while time.monotonic() - began < seconds:
            current = server_state(server)
            h.check(current["occupants"] == 2 and not current["engineRunning"]
                    and not current["utilities"]["generatorRunning"], "lamp control occupants or charging source changed")
            samples.append({"realSeconds": time.monotonic() - began, "worldHour": current["worldHour"],
                            "batteryCharge": current["batteryCharge"], "lightsOn": current["utilities"]["lightsOn"]})
            time.sleep(min(.50, max(0, seconds - (time.monotonic() - began))))
        return samples, time.monotonic() - began
    off_samples, off_seconds = window()
    off_after = battery_replicas(h, b, server, vehicle_id)
    h.check(all(not row["lightsOn"] for row in off_samples), "off control lamp switch changed")
    h.check(h._near(off_before["server"]["batteryCharge"], off_after["server"]["batteryCharge"], .000001),
            "occupied switched-off camper drained its battery")
    h.record("mp-occupied-lamps-off-elapsed-control", initial_actor, h.snapshot(),
             realElapsedSeconds=off_seconds, batteryBefore=off_before, batteryAfter=off_after,
             samples=off_samples, worldTimeChangedByTest=False, lampCallbackCalledDirectly=False)
    switched_on = False
    try:
        h.click_control("lights")
        h.wait_for(lambda s: s["queueCount"] == 0 and s["utilities"]["lightsOn"], label="native MP lamp toggle on")
        switched_on = True
        h.capture("mp-occupied-lamps-on")
        on_before = server_state(server)
        h.check(on_before["utilities"]["lightsOn"] and on_before["occupants"] == 2, "authoritative lamp switch did not turn on")
        on_samples, on_seconds = window()
        on_after = server_state(server)
        h.check(all(row["lightsOn"] for row in on_samples), "on control lamp switch changed")
        hours = on_after["worldHour"] - on_before["worldHour"]
        expected = on_before["lampRate"] * hours
        actual = on_before["batteryCharge"] - on_after["batteryCharge"]
        h.check(hours > 0 and actual > 0, "native server did not drain occupied lamps over elapsed time")
        # The authority tick samples every .5 real seconds. Window endpoints may
        # lie between samples; 8% bounds that edge while rejecting a doubled rate.
        h.check(abs(actual - expected) <= max(expected * .08, .000002),
                f"lamp drain is not one vehicle's .0018/hour: expected {expected}, actual {actual}")
        h.click_control("lights")
        h.wait_for(lambda s: s["queueCount"] == 0 and not s["utilities"]["lightsOn"], label="native MP lamp toggle off")
        switched_on = False
        replicated = battery_replicas(h, b, server, vehicle_id)
        h.record("mp-occupied-lamps-drain-once-for-two-passengers", initial_actor, h.snapshot(),
                 realElapsedSeconds=on_seconds, worldElapsedHours=hours, expectedSingleVehicleDrain=expected,
                 actualServerDrain=actual, rateRatio=actual / expected, occupants=2,
                 serverBefore=on_before, serverAfter=on_after, stableOffBatteryReplicas=replicated,
                 samples=on_samples, worldTimeChangedByTest=False, lampCallbackCalledDirectly=False,
                 claim="actual native UI switch and elapsed authoritative tick; not an artificial clock advance")
        return replicated
    finally:
        if switched_on:
            try:
                if h.snapshot()["utilities"]["lightsOn"]:
                    h.click_control("lights")
                    h.wait_for(lambda s: s["queueCount"] == 0 and not s["utilities"]["lightsOn"],
                               timeout=15, label="cleanup native lamp toggle off")
            except Exception:
                pass


def run_mp_cases(h, b, reset_fixture=False, lamp_seconds=0):
    a_info = h.lua('local p=getPlayer(); local v=p and p:getVehicle(); return p and v and '
                   '{client=isClient(),id=p:getOnlineID(),vehicleId=v:getId(),script=v:getScript():getFullName(),'
                   'normalActions=not p:isTimedActionInstant()} or false')
    b_info = b.lua('local p=getPlayer(); local v=p and p:getVehicle(); return p and v and '
                   '{client=isClient(),id=p:getOnlineID(),vehicleId=v:getId()} or false')
    h.check(isinstance(a_info, dict) and isinstance(b_info, dict), "both clients must already be inside the camper")
    h.check(a_info["client"] and b_info["client"] and a_info["id"] != b_info["id"], "two distinct live MP characters required")
    h.check(a_info["normalActions"] and a_info["vehicleId"] == b_info["vehicleId"]
            and a_info["script"] == "Base.Trailer54FlyingCloud22", "same FlyingCloud22 and normal A timed actions required")
    vehicle_id = a_info["vehicleId"]
    server = ServerEval(h)
    code = SERVER_FIXTURE.replace("ACTOR_ID", str(int(a_info["id"]))).replace("OBSERVER_ID", str(int(b_info["id"])))
    code = code.replace("VEHICLE_ID", str(int(vehicle_id))).replace("RESET_ALLOWED", "true" if reset_fixture else "false")
    code = code.replace("UTILITIES_BODY", UTILITIES_READ)
    authority = parse_server(server(code))
    h.REPORT["fixture"] = {"serverAuthorityOnly": True, "clientInitializationSkipped": True,
                           "actor": a_info, "observer": b_info, "initialServer": authority,
                           "replicatedTaggedItemIDs": seed_client(h, authority, vehicle_id)}
    h.REPORT["scope"] = "two real multiplayer clients; native A Dashboard clicks, dedicated-server authority, B replication"
    h.REPORT["replicationTolerances"] = {"stableNumbers": .0003, "runningGeneratorFuelLitres": .134,
                                          "propaneTanks": .0101,
                                          "reason": "production generator 10-minute and propane .01-tank batching"}
    # Opening/positioning the panel is fixture setup. Feature buttons themselves
    # are clicked through the production native mouse/UI/action dispatch.
    h.lua('local p=getPlayer(); MELens.Dashboard.open(p,p:getVehicle()); '
          'local w=MELens.Dashboard.instance; w:setX(45); w:setY(45); w:setVisible(true); '
          'MEMCNativeLab.releaseKeys(); return true')
    h.wait_for(lambda s: len(s["controls"]) > 0, timeout=15, label="MP Dashboard rendered")
    baseline = verify_receipt(h, b, server, vehicle_id, h.snapshot(), "initial-server-fixture")
    last = baseline
    original_record = h.record
    def checked_record(name, before, after, **details):
        nonlocal last
        receipt = verify_receipt(h, b, server, vehicle_id, after, name, previous=last)
        details["multiplayer"] = receipt
        details["serverAuthorityVerified"] = True
        details["observerBReplicationVerified"] = True
        result = original_record(name, before, after, **details)
        last = receipt
        return result
    h.record = checked_record
    try:
        # A multi-hour day makes the native ten-game-minute replication batch
        # longer than the shared SP timeout.
        h.run_dashboard_cases(skip_full_capacity=True, generator_fuel_timeout=120)
        full = parse_server(server("return MELensMPFeatureTest.fullCapacity()"))
        h.REPORT["fullCapacityServerFixture"] = full
        h.wait_for(lambda s: s["utilities"]["generatorFuel"] >= s["utilities"]["generatorCapacity"] - .0003
                   and s["utilities"]["water"] >= s["utilities"]["waterCapacity"] - .0003
                   and s["utilities"]["propane"] >= 1.999
                   and s["inventory"]["petrol"]["amount"] > .24
                   and s["inventory"]["water"]["amount"] > .24
                   and s["inventory"]["propane"]["propane"] > .099,
                   timeout=25, label="server full-capacity setup replicated to A")
        verify_receipt(h, b, server, vehicle_id, h.snapshot(), "full-capacity-server-fixture")
        h.disabled_case("addFuel", "full-generator-rejected-with-portable-fuel")
        h.disabled_case("addWater", "full-water-tank-rejected-with-portable-water")
        h.disabled_case("addPropane", "full-propane-storage-rejected-with-portable-propane")
        h.capture("mp-features-full-capacity")
        if lamp_seconds:
            h.REPORT["occupiedLampDrain"] = run_lamp_case(h, b, server, vehicle_id, lamp_seconds)
        return {"actorA": h.snapshot(), "server": server_state(server), "observerB": observer_state(b, vehicle_id)}
    finally:
        h.record = original_record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--endpoint-a", default=ENDPOINT_A)
    parser.add_argument("--endpoint-b", default=ENDPOINT_B)
    parser.add_argument("--screens-a", type=Path, default=SCREENS_A)
    parser.add_argument("--reset-fixture", action="store_true", help="Explicitly replenish an earlier owned MP fixture on the server")
    parser.add_argument("--lamp-seconds", type=int, default=0,
                        help="Optional paired occupied-lamp off/on windows, 30..120 real seconds each; default skip")
    parser.add_argument("--lamps-only", action="store_true", help="Use an existing settled MP utility fixture; do not replenish or rerun Dashboard cases")
    parser.add_argument("--expected-version", help="Require this runtime version on both real clients before testing")
    args = parser.parse_args()
    if args.lamp_seconds != 0 and not 30 <= args.lamp_seconds <= 120:
        parser.error("--lamp-seconds must be 0 (skip) or 30..120")
    if args.lamps_only and not args.lamp_seconds:
        parser.error("--lamps-only needs --lamp-seconds")
    h, b = load_helpers(), load_helpers()
    h.configure(args.output, args.endpoint_a)
    h.SCREENS = args.screens_a.resolve()
    b.ENDPOINT = args.endpoint_b
    try:
        versions = {"A": h.lua('return MELens.VERSION'), "B": b.lua('return MELens.VERSION')}
        h.REPORT["runtimeVersions"] = versions
        if args.expected_version:
            h.check(all(value == args.expected_version for value in versions.values()), f"unexpected client runtime versions: {versions}")
        if args.lamps_only:
            vehicle_id = h.lua('local p=getPlayer(); return p and p:getVehicle() and p:getVehicle():getId() or false')
            h.check(isinstance(vehicle_id, (int, float)) and not isinstance(vehicle_id, bool), "existing MP fixture vehicle required")
            h.REPORT["scope"] = "Actual two-occupant native lamp UI input and elapsed authoritative tick; existing utility fixture retained"
            h.REPORT["batteryReplicationTolerance"] = .00002
            h.REPORT["final"] = run_lamp_case(h, b, ServerEval(h), int(vehicle_id), args.lamp_seconds)
        else:
            h.REPORT["final"] = run_mp_cases(h, b, args.reset_fixture, args.lamp_seconds)
        path = h.write_report("passed")
        print(f'NATIVE_MP_FEATURES_PASSED cases={len(h.REPORT["cases"])} {path}', flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT["lastSnapshot"] = h.snapshot()
        except Exception:
            h.REPORT["lastSnapshot"] = None
        path = h.write_report("failed", error)
        print(error, flush=True)
        print(f"NATIVE_MP_FEATURES_FAILED {path}; parent-owned clients/server left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
