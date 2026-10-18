"""Five native MP tap/wash cases after Dashboard; importing performs no I/O.

The parent owns the guarded no-Java server and both inactive clients. All item,
tank, thirst and body fixtures are created on the server. A uses the genuine
world context menus through final-water-tests.py native input helpers. Every
case checks server authority and B's public tank/body replication. A's private
inventory is verified on server/A; no B inventory replication claim is made.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]


def load_driver(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


READERS = r'''
local function bodyRead(p)
    local r={dirtyParts=0,blood=0,dirt=0}
    local visual=p:getHumanVisual()
    for i=0,BloodBodyPartType.MAX:index()-1 do
        local part=BloodBodyPartType.FromIndex(i)
        local blood,dirt=visual:getBlood(part),visual:getDirt(part)
        if blood+dirt>0 then r.dirtyParts=r.dirtyParts+1 end
        r.blood=r.blood+blood; r.dirt=r.dirt+dirt
    end
    return r
end
local function tapRead(p,inv,W)
    local body=bodyRead(p)
    local fc=W.bottle:getFluidContainer()
    local cloth,soap=W.cloth,W.soap
    local blood,dirt=0,0
    local parts=BloodClothingType.getCoveredParts(cloth:getBloodClothingType())
    for i=0,parts:size()-1 do
        blood=blood+cloth:getBlood(parts:get(i)); dirt=dirt+cloth:getDirt(parts:get(i))
    end
    local r={thirst=p:getStats():get(CharacterStat.THIRST),dirtyParts=body.dirtyParts,body=body,
        bottleId=W.bottle:getID(),bottleAmount=fc:getAmount(),bottleCapacity=fc:getCapacity(),
        bottlePureWater=fc:isPureFluid(Fluid.Water),bottleName=W.bottle:getDisplayName(),
        bottleInMainInventory=W.bottle:getContainer()==inv,
        dirtyId=W.dirty:getID(),dirtyInMainInventory=W.dirty:getContainer()==inv,
        dirtyName=W.dirty:getDisplayName(),dirtyAfterCleaning=W.dirty:getItemAfterCleaning(),
        bandageWater=W.bandageWater,cleanBandages={},
        clothId=cloth:getID(),clothName=cloth:getDisplayName(),clothInMainInventory=cloth:getContainer()==inv,
        clothBlood=blood,clothDirt=dirt,clothDirtiness=cloth:getDirtiness(),clothWetness=cloth:getWetness(),
        clothCondition=cloth:getCondition(),clothWater=ISWashClothing.GetRequiredWater(cloth),
        clothSoap=ISWashClothing.GetRequiredSoap(cloth),soapId=soap:getID(),soapUses=soap:getCurrentUses(),
        soapInMainInventory=soap:getContainer()==inv}
    local items=inv:getItems()
    for i=0,items:size()-1 do
        local item=items:get(i)
        if item:getFullType()=="Base.Bandage" and not W.knownClean[tostring(item:getID())] then
            r.cleanBandages[#r.cleanBandages+1]={id=item:getID(),favorite=item:isFavorite()}
        end
    end
    return r
end
'''


SERVER_FIXTURE = r'''
assert(isServer() and not isClient(),"water fixtures must run on the server")
local p,b
local players=getOnlinePlayers()
for i=0,players:size()-1 do local q=players:get(i)
    if q:getOnlineID()==ACTOR_ID then p=q elseif q:getOnlineID()==OBSERVER_ID then b=q end
end
local v=getVehicleById(VEHICLE_ID)
assert(p and b and v and p:getVehicle()==v and b:getVehicle()==v,"both players must occupy the camper")
assert(v:getScript():getFullName()=="Base.Trailer54FlyingCloud22","water fixture requires FlyingCloud22")
assert(not p:isGodMod(),"turn off actor god mode normally before MP thirst/body fixtures")
assert(not MELensMPWaterTest or RESET_ALLOWED,"water fixture exists; explicit --reset-fixture required")
local inv,U=p:getInventory(),MELens.Utilities
local T={player=p,observer=b,vehicle=v,knownClean={},knownCleanIds={},serverOnlySetup=true}
MELensMPWaterTest=T
local fresh={}
local function own(key,full,name)
    local item=inv:getFirstEvalRecurse(function(i)
        return i:getFullType()==full and i:getModData().MELensWaterFixture==key
    end)
    local created=item==nil
    if created then item=inv:AddItem(full) end
    assert(item and item:getContainer()==inv,"tagged water fixture must be in actor main inventory")
    item:getModData().MELensWaterFixture=key; item:setName(name)
    T[key]=item
    if created then fresh[#fresh+1]=item end
    return item
end
local bottle=own("bottle","Base.WaterBottle","MP tap test bottle")
local fc=bottle:getFluidContainer(); assert(fc,"native bottle fluid component missing")
if fc:getAmount()>0 then fc:removeFluid(fc:getAmount()) end
local dirty=own("dirty","Base.BandageDirty","MP tap test dirty bandage")
assert(dirty:getItemAfterCleaning()=="Base.Bandage","native cleaning replacement missing")
dirty:setFavorite(true)
T.bandageWater=ISWashClothing.GetRequiredWater(dirty)
local cloth=own("cloth","Base.Shirt_Denim","MP tap test bloody denim shirt")
local parts=BloodClothingType.getCoveredParts(cloth:getBloodClothingType())
assert(parts and parts:size()>0,"denim shirt has no blood-covered body parts")
for i=0,parts:size()-1 do cloth:setBlood(parts:get(i),0); cloth:setDirt(parts:get(i),0) end
cloth:setBlood(parts:get(0),0.5); cloth:setDirt(parts:get(0),0.25); cloth:setDirtiness(25)
cloth:setWetness(0)
local soap=own("soap","Base.Soap2","MP tap test soap")
soap:setUsedDelta(1)
local soaps=inv:getSoapList(nil,true)
assert(soaps and soaps:size()>0 and soaps:get(0)==soap,"another carried soap precedes the exact fixture")
assert(soap:getCurrentUses()>=10 and ISWashClothing.GetRequiredSoap(cloth)==1,"unexpected native soap contract")
local items=inv:getItems()
for i=0,items:size()-1 do local item=items:get(i)
    if item:getFullType()=="Base.Bandage" then
        T.knownClean[tostring(item:getID())]=true; T.knownCleanIds[#T.knownCleanIds+1]=item:getID()
    end
end
local tank=U.waterState(v); assert(tank,"camper water tank missing")
tank.part:getModData().water=20; tank.part:getModData().tainted=false
U.transmit(v,tank.part)
p:getStats():set(CharacterStat.THIRST,0.3)
syncPlayerStats(p,SyncPlayerStatsPacket.Stat_Thirst)
local visual=p:getHumanVisual()
for i=0,BloodBodyPartType.MAX:index()-1 do local part=BloodBodyPartType.FromIndex(i)
    visual:setBlood(part,0); visual:setDirt(part,0)
end
visual:setDirt(BloodBodyPartType.FromIndex(0),1)
visual:setBlood(BloodBodyPartType.FromIndex(1),0.5)
sendHumanVisual(p)
for _,item in ipairs(fresh) do sendAddItemToContainer(inv,item) end
for _,key in ipairs({"bottle","dirty","cloth","soap"}) do T[key]:syncItemFields() end
function T.snapshot()
    local tank=MELens.Utilities.waterState(T.vehicle)
    return {server=isServer(),vehicleId=T.vehicle:getId(),actorInside=T.player:getVehicle()==T.vehicle,
        observerInside=T.observer:getVehicle()==T.vehicle,water=tank.water,tainted=tank.tainted,
        tap=tapRead(T.player,T.player:getInventory(),T),knownCleanIds=T.knownCleanIds}
end
return enc(T.snapshot())
'''


def server_state(server, encoder):
    state = json.loads(server(encoder + 'assert(MELensMPWaterTest,"server water fixture missing"); return enc(MELensMPWaterTest.snapshot())'))
    if state.get("server") is not True:
        raise AssertionError(f"invalid water authority receipt: {state}")
    clean = state["tap"]["cleanBandages"]
    state["tap"]["cleanBandages"] = sorted(clean.values() if isinstance(clean, dict) else clean, key=lambda v: v["id"])
    return state


def observer_state(b, actor_id, vehicle_id):
    return b.lua(READERS + f'''
local v=getVehicleById({vehicle_id}); local p
local players=getOnlinePlayers()
for i=0,players:size()-1 do local q=players:get(i); if q:getOnlineID()=={actor_id} then p=q end end
if not p or not v then return false end
local tank=MELens.Utilities.waterState(v)
return {{vehicleId=v:getId(),inside=getPlayer():getVehicle()==v,actorInside=p:getVehicle()==v,
    water=tank and tank.water,tainted=tank and tank.tainted,body=bodyRead(p)}}
''')


def client_fixture_code(water, authority, vehicle_id):
    t = authority["tap"]
    ids = {key: int(t[field]) for key, field in (("bottle", "bottleId"), ("dirty", "dirtyId"), ("cloth", "clothId"), ("soap", "soapId"))}
    ids_lua = ",".join(f"{key}={value}" for key, value in ids.items())
    known_ids = authority.get("knownCleanIds", [])
    known = ",".join(str(int(value)) for value in (known_ids.values() if isinstance(known_ids, dict) else known_ids))
    # Extract only read functions from the SP fixture. Its inventory/body/tank
    # initialization is deliberately never sent to the multiplayer client.
    reads = water.FIXTURE[water.FIXTURE.index("function W.pickPoint()"):]
    code = READERS + f'''
local p=getPlayer(); local v=getVehicleById({vehicle_id}); local inv=p:getInventory()
assert(isClient() and v and p:getVehicle()==v and not p:isGodMod(),"normal MP actor must occupy target camper")
local F=MELensFeatureTest
assert(F and F.initialized and F.vehicle==v,"run server-owned MP Dashboard fixture first")
local ids={{{ids_lua}}}; local found={{}}
local types={{bottle="Base.WaterBottle",dirty="Base.BandageDirty",cloth="Base.Shirt_Denim",soap="Base.Soap2"}}
for key,id in pairs(ids) do
    local item=inv:getFirstEvalRecurse(function(i)
        return i:getID()==id and i:getModData().MELensWaterFixture==key and i:getFullType()==types[key]
    end)
    if not item then return false end; found[key]=item
end
if found.bottle:getFluidContainer():getAmount()>0.001 or found.soap:getCurrentUses()<10
        or ISWashClothing.GetRequiredSoap(found.cloth)~=1 then return false end
local M,U,P=MELens,MELens.Utilities,MELens.Parts
local W={{player=p,vehicle=v,bottle=found.bottle,dirty=found.dirty,cloth=found.cloth,soap=found.soap,
    knownClean={{}},bandageWater={authority['tap']['bandageWater']},serverOnlySetup=true}}
for _,id in ipairs({{{known}}}) do W.knownClean[tostring(id)]=true end
MELensWaterTest=W
''' + reads
    # The SP read chunk ends in a return. Replace that final expression with
    # a snapshot extension, keeping native world-menu geometry/menu reads shared.
    code = code.rsplit("return W.snapshot()", 1)[0] + r'''
local originalSnapshot=W.snapshot
function W.snapshot()
    local r=originalSnapshot(); r.tap=tapRead(p,inv,W); return r
end
return true
'''
    return ids, code


def seed_client(h, water, authority, vehicle_id):
    ids, code = client_fixture_code(water, authority, vehicle_id)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if h.lua(code) is True:
            return ids
        time.sleep(.15)
    raise TimeoutError("server water item IDs/tags and bloody cloth/soap did not replicate to A")


def verify_receipt(h, b, water, server, encoder, actor_id, vehicle_id, expected, case, timeout=25, pending_water=False):
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        truth = server_state(server, encoder)
        actor = water.read_state(h)
        observer = observer_state(b, actor_id, vehicle_id)
        errors = []
        if not truth.get("actorInside") or not truth.get("observerInside"):
            errors.append("server occupants")
        for field in ("water", "tainted"):
            value = truth[field]
            local_value = actor["utilities"][field]
            if isinstance(value, bool):
                if local_value is not value or not isinstance(observer, dict) or observer.get(field) is not value:
                    errors.append(f"A/B/server {field}")
            elif not h._near(value, local_value, .001) or not isinstance(observer, dict) or not h._near(value, observer.get(field, -999), .001):
                errors.append(f"A/B/server {field}")
        if not isinstance(observer, dict) or not observer.get("inside") or not observer.get("actorInside"):
            errors.append("B occupant membership")
        for field, value in truth["tap"].items():
            if field in ("thirst", "clothWetness"):
                tolerance = .02 if field == "thirst" else 5
                if not h._near(value, actor["tap"].get(field, -999), tolerance):
                    errors.append(f"A/server {field}")
            elif field == "body":
                for key in ("dirtyParts", "blood", "dirt"):
                    if not h._near(value[key], actor["tap"]["body"][key], .001) or not isinstance(observer, dict) or not h._near(value[key], observer.get("body", {}).get(key, -999), .001):
                        errors.append(f"A/B/server body.{key}")
            elif field == "cleanBandages":
                actual = sorted(actor["tap"][field], key=lambda item: item["id"])
                wanted = sorted(expected["tap"][field], key=lambda item: item["id"])
                if value != actual or value != wanted:
                    errors.append("A/server replacement bandage IDs/favorite")
            elif isinstance(value, bool) or isinstance(value, str):
                if actor["tap"].get(field) != value or expected["tap"].get(field) != value:
                    errors.append(f"A/server {field}")
            elif not h._near(value, actor["tap"].get(field, -999), .001) or not h._near(value, expected["tap"].get(field, -999), .001):
                errors.append(f"A/server {field}")
        if not pending_water and not h._near(truth["water"], expected["utilities"]["water"], .001):
            errors.append("expected/server tank level")
        last = {"server": truth, "actorA": actor, "observerB": observer, "mismatches": errors}
        h.REPORT["lastMPReceipt"] = last
        if not errors:
            return last
        time.sleep(.15)
    raise AssertionError(f"{case}: MP tap authority/replication did not settle: {json.dumps(last, ensure_ascii=False)}")


def run_cases(h, b, mp, water, encoder, reset_fixture=False):
    info = []
    for api in (h, b):
        info.append(api.lua('local p=getPlayer(); local v=p:getVehicle(); return v and '
                            '{client=isClient(),id=p:getOnlineID(),vehicleId=v:getId(),standing=MELens.isStanding(p),'
                            'god=p:isGodMod(),instant=p:isTimedActionInstant()} or false'))
    a, other = info
    h.check(isinstance(a, dict) and isinstance(other, dict) and a["client"] and other["client"]
            and a["id"] != other["id"] and a["standing"] and other["standing"]
            and a["vehicleId"] == other["vehicleId"] and not a["god"] and not a["instant"],
            "MP taps need both clients standing in the camper, actor god/instant actions off")
    actor_id, vehicle_id = int(a["id"]), int(a["vehicleId"])
    server = mp.ServerEval(h)
    code = SERVER_FIXTURE.replace("ACTOR_ID", str(actor_id)).replace("OBSERVER_ID", str(int(other["id"])))
    code = code.replace("VEHICLE_ID", str(vehicle_id)).replace("RESET_ALLOWED", "true" if reset_fixture else "false")
    authority = json.loads(server(encoder + READERS + code))
    ids = seed_client(h, water, authority, vehicle_id)
    h.REPORT.update(scope=__doc__.strip(), serverOnlyFixtureSetup=True, clientItemTankBodyInitializationSkipped=True,
                    replicatedTaggedItemIDs=ids, initialServer=authority,
                    observerClaim="B receives public tank/body state; private actor supplies checked on server/A")
    h.lua('if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end; '
          'ISUIHandler.setVisibleAllUI(false); MEMCNativeLab.releaseKeys(); return true')
    initial = water.poll(h, lambda s: s["queueCount"] == 0 and s["tap"]["thirst"] > .25
                         and s["tap"]["dirtyParts"] == 2 and s["utilities"]["water"] > 19.99,
                         label="server thirst/body/tank fixture replicated to A")
    baseline = verify_receipt(h, b, water, server, encoder, actor_id, vehicle_id, initial, "server-owned-tap-fixture")
    h.REPORT["initialMPReceipt"] = baseline
    h.capture("mp-water-initial")
    labels = h.lua('return {drink=getText("ContextMenu_Drink"),fill=getText("ContextMenu_Fill"),'
                   'washBody=getText("ContextMenu_MELens_WashYourself"),washClothes=getText("ContextMenu_MELens_WashClothes")}')
    previous = baseline

    def receipt_for(after, name):
        # Native body/inventory completion can arrive before the tank packet.
        # Wait for fresh A/B/server agreement, then each case below checks its
        # exact authoritative water consumption against the prior receipt.
        return verify_receipt(h, b, water, server, encoder, actor_id, vehicle_id, after, name, pending_water=True)

    def record(name, before, after, seen, receipt):
        nonlocal previous
        h.record(name, before, receipt["actorA"], observedTimedActions=seen, uiHandlersInvokedDirectly=False,
                 multiplayerBefore=previous, multiplayer=receipt,
                 serverAuthorityVerified=True, observerBPublicReplicationVerified=True)
        previous = receipt

    before = water.select_tap(h, [labels["drink"]], "mp-drink")
    after, seen = water.finish(h, "mp-tap-drink", before, lambda s: s["tap"]["thirst"] < before["tap"]["thirst"]-.1
                              and s["utilities"]["water"] < before["utilities"]["water"]-.1, "MELensDrinkFromTank")
    receipt = receipt_for(after, "mp-tap-drink")
    h.check(receipt["server"]["tap"]["thirst"] < baseline["server"]["tap"]["thirst"]-.1,
            "drinking did not reduce authoritative thirst")
    h.check(abs((baseline["server"]["water"]-receipt["server"]["water"])-baseline["server"]["tap"]["thirst"]*2)<.05,
            "authoritative drink water not conserved")
    record("mp-tap-drink", before, after, seen, receipt)

    before = water.select_tap(h, [labels["fill"], after["tap"]["bottleName"]], "mp-fill-bottle")
    after, seen = water.finish(h, "mp-tap-fill-bottle", before,
                              lambda s: s["tap"]["bottleAmount"] >= s["tap"]["bottleCapacity"]-.001, "MELensFillFromTank")
    truth_before = previous["server"]
    receipt = receipt_for(after, "mp-tap-fill-bottle")
    truth = receipt["server"]
    h.check(truth["tap"]["bottleId"] == truth_before["tap"]["bottleId"] and truth["tap"]["bottlePureWater"],
            "authoritative bottle identity/pure water changed")
    h.check(abs((truth_before["water"]-truth["water"])-(truth["tap"]["bottleAmount"]-truth_before["tap"]["bottleAmount"]))<.001,
            "authoritative fill water not conserved")
    record("mp-tap-fill-bottle", before, after, seen, receipt)

    before = water.select_tap(h, [labels["washBody"]], "mp-wash-body")
    after, seen = water.finish(h, "mp-tap-wash-yourself", before, lambda s: s["tap"]["dirtyParts"] == 0, "MELensWashFromTank")
    truth_before = previous["server"]
    receipt = receipt_for(after, "mp-tap-wash-yourself")
    h.check(receipt["server"]["tap"]["dirtyParts"] == 0
            and abs(truth_before["water"]-receipt["server"]["water"]-truth_before["tap"]["dirtyParts"]*.5)<.001,
            "authoritative body washing/part water not conserved")
    record("mp-tap-wash-yourself", before, after, seen, receipt)

    before = water.select_tap(h, [labels["washClothes"], after["tap"]["dirtyName"]], "mp-wash-bandage")
    after, seen = water.finish(h, "mp-tap-wash-dirty-bandage", before,
                              lambda s: not s["tap"]["dirtyInMainInventory"] and len(s["tap"]["cleanBandages"]) == 1,
                              "MELensWashClothing")
    truth_before = previous["server"]
    receipt = receipt_for(after, "mp-tap-wash-dirty-bandage")
    truth = receipt["server"]
    clean = truth["tap"]["cleanBandages"]
    h.check(len(clean) == 1 and clean[0]["favorite"] and clean[0]["id"] != truth_before["tap"]["dirtyId"],
            "authoritative bandage replacement/favorite incorrect")
    h.check(abs(truth_before["water"]-truth["water"]-truth_before["tap"]["bandageWater"])<.001,
            "authoritative bandage water not conserved")
    record("mp-tap-wash-dirty-bandage", before, after, seen, receipt)

    before = water.select_tap(h, [labels["washClothes"], after["tap"]["clothName"]], "mp-wash-bloody-shirt")
    truth_before = previous["server"]
    h.check(truth_before["tap"]["clothBlood"] > 0 and truth_before["tap"]["clothSoap"] == 1,
            "shirt must still be bloody before its real menu action")
    after, seen = water.finish(h, "mp-tap-wash-bloody-shirt-with-soap", before,
                              lambda s: s["tap"]["clothBlood"] == 0 and s["tap"]["clothDirt"] == 0
                              and s["tap"]["soapUses"] < before["tap"]["soapUses"], "MELensWashClothing")
    receipt = receipt_for(after, "mp-tap-wash-bloody-shirt-with-soap")
    truth = receipt["server"]
    h.check(truth["tap"]["clothId"] == truth_before["tap"]["clothId"] and truth["tap"]["clothInMainInventory"]
            and truth["tap"]["clothCondition"] == truth_before["tap"]["clothCondition"]
            and truth["tap"]["clothDirtiness"] == 0 and truth["tap"]["clothWetness"] > 90,
            "washing changed shirt ownership/identity/condition or did not wet/clean it")
    h.check(truth_before["tap"]["soapUses"]-truth["tap"]["soapUses"] == truth_before["tap"]["clothSoap"]
            and abs(truth_before["water"]-truth["water"]-truth_before["tap"]["clothWater"])<.001,
            "authoritative bloody-shirt soap/water not conserved")
    record("mp-tap-wash-bloody-shirt-with-soap", before, after, seen, receipt)
    h.capture("mp-water-five-actions-complete")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-206b")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-water-tests")
    parser.add_argument("--reset-fixture", action="store_true", help="Explicitly replenish prior owned server water fixtures")
    args = parser.parse_args()
    mp, water, interior = (load_driver(name) for name in ("final-mp-features", "final-water-tests", "final-mp-interior-tests"))
    h, b = mp.load_helpers(), mp.load_helpers()
    h.configure(args.output, mp.ENDPOINT_A)
    b.ENDPOINT = mp.ENDPOINT_B
    metadata = json.loads((args.session / "session.json").read_text(encoding="utf-8-sig"))
    clients = {row["name"]: row for row in metadata["clients"]}
    h.SCREENS = Path(clients["client-a"]["cache"]) / "Screenshots"
    try:
        h.REPORT["final"] = run_cases(h, b, mp, water, interior.JSON_ENCODER, args.reset_fixture)
        print(f'NATIVE_MP_WATER_PASSED cases={len(h.REPORT["cases"])} {h.write_report("passed")}', flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT["lastSnapshot"] = water.read_state(h)
        except Exception:
            h.REPORT["lastSnapshot"] = None
        print(error, flush=True)
        print(f'NATIVE_MP_WATER_FAILED {h.write_report("failed", error)}; parent-owned clients/server left running', flush=True)
        return 1
    finally:
        try:
            h.lua('MEMCNativeLab.releaseKeys(); return true')
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
