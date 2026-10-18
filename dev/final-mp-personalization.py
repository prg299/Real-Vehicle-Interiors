"""Native MP rename/paint cases; importing this file performs no I/O or game calls.

Run after final-mp-features.py with both players standing inside the same camper.
Only the admin server fixture creates or changes paint supplies. A types through
the native text queue and clicks the actual Dashboard/dialog/context-menu UI.
Each accepted, cancelled or disabled case verifies server state and B replication.
The caller owns the guarded clients/server lifetime, including after failure.
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


SERVER_FIXTURE = r'''
assert(isServer() and not isClient(),"personalization fixture must run on server")
local aid,bid,vid=ACTOR_ID,OBSERVER_ID,VEHICLE_ID
local p,b
local players=getOnlinePlayers()
for i=0,players:size()-1 do
    local q=players:get(i)
    if q:getOnlineID()==aid then p=q elseif q:getOnlineID()==bid then b=q end
end
local v=getVehicleById(vid)
assert(p and b and v and p:getVehicle()==v and b:getVehicle()==v,"both authoritative players must occupy the same camper")
assert(v:getScript():getFullName()=="Base.Trailer54FlyingCloud22","personalization fixture requires FlyingCloud22")
assert(not MELensMPPersonalizationTest or RESET_ALLOWED,"personalization fixture exists; explicit --reset-fixture required")
local inv,H=p:getInventory(),MELens.Home
local T={actor=p,observer=b,vehicle=v}
MELensMPPersonalizationTest=T
local function own(key,full)
    local item=inv:getFirstEvalRecurse(function(i)
        return i:getFullType()==full and i:getModData().MELensPersonalFixture==key
    end)
    local fresh=item==nil
    if fresh then item=inv:AddItem(full) end
    assert(item and item:getContainer()==inv,"fixture paint/brush must be in the actor's main inventory")
    item:getModData().MELensPersonalFixture=key
    return item,fresh
end
local can,newCan=own("paint","Base.PaintGreen")
local brush,newBrush=own("brush","Base.Paintbrush")
can:setUsedDelta(1)
T.can,T.brush=can,brush
if newCan then sendAddItemToContainer(inv,can) end
if newBrush then sendAddItemToContainer(inv,brush) end
can:syncItemFields(); brush:syncItemFields()
assert(H.brushOf(p)==brush,"another carried brush precedes the fixture")
for _,entry in ipairs(H.paints()) do
    local first=inv:getFirstEvalRecurse(function(i) return i:getType()==entry.paint and i:getCurrentUses()>=H.PAINT_USES end)
    assert(not first or first==can,"another carried full paint can prevents a precise insufficient-paint control")
end
function T.snapshot()
    local H,v,inv=MELens.Home,T.vehicle,T.actor:getInventory()
    local r,g,b=H.paint(v)
    return {server=isServer(),vehicleId=v:getId(),actorInside=T.actor:getVehicle()==v,
        observerInside=T.observer:getVehicle()==v,
        personal={name=H.givenName(v) or "",paint=r and {r=r,g=g,b=b} or false,
            canId=T.can:getID(),canUses=T.can:getCurrentUses(),canInMain=inv:contains(T.can),
            canFullType=T.can:getFullType(),brushId=T.brush:getID(),brushInMain=inv:contains(T.brush),
            brushFullType=T.brush:getFullType(),brushCondition=T.brush:getCondition()}}
end
return enc(T.snapshot())
'''


def server_state(server, encoder):
    state = json.loads(server(encoder + 'assert(MELensMPPersonalizationTest,"server fixture missing"); return enc(MELensMPPersonalizationTest.snapshot())'))
    if state.get("server") is not True:
        raise AssertionError(f"invalid native authority receipt: {state}")
    return state


def observer_state(b, vehicle_id):
    return b.lua(f'local v=getVehicleById({vehicle_id}); if not v then return false end; '
                 'local H=MELens.Home; local r,g,blue=H.paint(v); return {vehicleId=v:getId(),'
                 'inside=getPlayer():getVehicle()==v,personal={name=H.givenName(v) or "",'
                 'paint=r and {r=r,g=g,b=blue} or false}}')


def same_paint(a, b):
    if a is False or b is False:
        return a is b
    return isinstance(a, dict) and isinstance(b, dict) and all(abs(a[k] - b[k]) < .00001 for k in ("r", "g", "b"))


def verify_receipt(h, personal, b, server, encoder, vehicle_id, expected, case, timeout=20):
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        authority, actor, observer = server_state(server, encoder), personal.read_state(h), observer_state(b, vehicle_id)
        errors = []
        if not authority.get("actorInside") or not authority.get("observerInside"):
            errors.append("server occupant membership")
        if not isinstance(observer, dict) or not observer.get("inside") or observer.get("vehicleId") != vehicle_id:
            errors.append("observer B membership")
        truth = authority["personal"]
        for field in ("name", "canId", "canUses", "canInMain", "brushId", "brushInMain", "brushCondition"):
            if truth.get(field) != expected["personal"].get(field) or truth.get(field) != actor["personal"].get(field):
                errors.append(f"A/server {field}")
        if not same_paint(truth["paint"], expected["personal"]["paint"]) or not same_paint(truth["paint"], actor["personal"]["paint"]):
            errors.append("A/server paint")
        if truth.get("canFullType") != "Base.PaintGreen" or truth.get("brushFullType") != "Base.Paintbrush":
            errors.append("authoritative supply type")
        if isinstance(observer, dict):
            if observer["personal"]["name"] != truth["name"]:
                errors.append("server/B name")
            if not same_paint(observer["personal"]["paint"], truth["paint"]):
                errors.append("server/B paint")
        last = {"server": authority, "actorA": actor, "observerB": observer, "mismatches": errors}
        h.REPORT["lastMPReceipt"] = last
        if not errors:
            return last
        time.sleep(.15)
    raise AssertionError(f"{case}: native MP personalization receipt did not settle: {json.dumps(last, ensure_ascii=False)}")


def seed_client(h, authority, vehicle_id):
    can_id, brush_id = int(authority["personal"]["canId"]), int(authority["personal"]["brushId"])
    code = f'''
local p=getPlayer(); local v=getVehicleById({vehicle_id})
assert(isClient() and v and p:getVehicle()==v,"A must be in the replicated camper")
assert(MELensFeatureTest and MELensFeatureTest.vehicle==v and MELensFeatureTest.initialized,"run MP Dashboard fixture first")
local inv=p:getInventory()
local can=inv:getFirstEvalRecurse(function(i)
    return i:getID()=={can_id} and i:getModData().MELensPersonalFixture=="paint" and i:getFullType()=="Base.PaintGreen"
end)
local brush=inv:getFirstEvalRecurse(function(i)
    return i:getID()=={brush_id} and i:getModData().MELensPersonalFixture=="brush" and i:getFullType()=="Base.Paintbrush"
end)
if not can or not brush or can:getCurrentUses()~=10 then return false end
MELensPersonalizationTest={{vehicle=v,player=p,initialized=true,can=can,brush=brush}}
return true
'''
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if h.lua(code) is True:
            return {"paint": can_id, "brush": brush_id}
        time.sleep(.15)
    raise TimeoutError("Server-created paint/brush IDs and tags did not replicate to A")


def run_cases(h, b, mp, personal, encoder, reset_fixture=False):
    a = h.lua('local p=getPlayer(); local v=p:getVehicle(); return v and '
              '{client=isClient(),id=p:getOnlineID(),vehicleId=v:getId(),standing=MELens.isStanding(p)} or false')
    observer = b.lua('local p=getPlayer(); local v=p:getVehicle(); return v and '
                     '{client=isClient(),id=p:getOnlineID(),vehicleId=v:getId(),standing=MELens.isStanding(p)} or false')
    h.check(isinstance(a, dict) and isinstance(observer, dict) and a["client"] and observer["client"]
            and a["id"] != observer["id"] and a["standing"] and observer["standing"]
            and a["vehicleId"] == observer["vehicleId"], "both real MP clients must stand inside the same camper")
    vehicle_id = int(a["vehicleId"])
    server = mp.ServerEval(h)
    fixture = SERVER_FIXTURE.replace("ACTOR_ID", str(int(a["id"]))).replace("OBSERVER_ID", str(int(observer["id"])))
    fixture = fixture.replace("VEHICLE_ID", str(vehicle_id)).replace("RESET_ALLOWED", "true" if reset_fixture else "false")
    authority = json.loads(server(encoder + fixture))
    ids = seed_client(h, authority, vehicle_id)
    h.REPORT.update(scope=__doc__.strip(), serverOnlySupplySetup=True, clientSupplyInitializationSkipped=True,
                    replicatedTaggedIDs=ids, initialServer=authority,
                    observerClaim="replicated name/paint state; B Dashboard rendering is not separately asserted")
    h.lua('MELens.Dashboard.open(getPlayer(),getPlayer():getVehicle()); local w=MELens.Dashboard.instance; '
          'w:setX(45); w:setY(45); w:setVisible(true); MEMCNativeLab.releaseKeys(); return true')
    h.wait_for(lambda s: len(s["controls"]) > 0, timeout=15, label="MP personalization Dashboard rendered")
    # T.initialized=true, so the SP fixture only defines its read-only snapshot;
    # its item creation and setUsedDelta(1) setup branch is never entered on A.
    h.lua(personal.FIXTURE)
    initial = personal.read_state(h)
    verify_receipt(h, personal, b, server, encoder, vehicle_id, initial, "authoritative-personalization-fixture")
    record = h.record
    def checked_record(name, before, after, **details):
        details["multiplayer"] = verify_receipt(h, personal, b, server, encoder, vehicle_id, after, name)
        details.update(serverAuthorityVerified=True, observerBReplicationVerified=True)
        return record(name, before, after, **details)
    h.record = checked_record
    try:
        personal.run_personalization_cases(h, skip_insufficient=True)
        # Exact same rejection boundary as SP, with mutation owned by the server.
        boundary = server(encoder + 'local T=MELensMPPersonalizationTest; '
                          'T.can:setUsedDelta(T.can:getUseDelta()*3.01); T.can:syncItemFields(); return enc(T.snapshot())')
        h.REPORT["insufficientPaintServerFixture"] = json.loads(boundary)
        before = personal.poll(h, lambda s: s["personal"]["canUses"] == 3 and not h._control(s, "paint")["enabled"],
                               label="server-created three-use paint boundary replicated to A")
        h.click_control("paint", enabled=False)
        deadline = time.monotonic() + 1.0
        after = before
        while time.monotonic() < deadline or time.monotonic() < h._input_release:
            after = personal.read_state(h)
            personal.assert_supplies_same(h, before, after)
            personal.assert_scene_still(h, before, after)
            h.check(after["queueCount"] == 0 and not after["menus"], "disabled paint dispatched an action or menu")
            h.check(after["personal"]["name"] == before["personal"]["name"]
                    and same_paint(after["personal"]["paint"], before["personal"]["paint"]),
                    "disabled paint changed committed personalization")
            time.sleep(.10)
        h.record("insufficient-paint-disabled-preserves-supplies", before, after,
                 rejectedInput=True, sceneInputConsumed=True, fixtureAuthority="server")
        return {"actorA": personal.read_state(h), "server": server_state(server, encoder),
                "observerB": observer_state(b, vehicle_id)}
    finally:
        h.record = record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-206")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-personalization")
    parser.add_argument("--reset-fixture", action="store_true", help="Explicitly replenish a prior owned server paint fixture")
    args = parser.parse_args()
    mp, personal, interior = (load_driver(name) for name in (
        "final-mp-features", "final-personalization-tests", "final-mp-interior-tests"))
    h, b = mp.load_helpers(), mp.load_helpers()
    h.configure(args.output, mp.ENDPOINT_A)
    b.ENDPOINT = mp.ENDPOINT_B
    metadata = json.loads((args.session / "session.json").read_text(encoding="utf-8-sig"))
    clients = {entry["name"]: entry for entry in metadata["clients"]}
    h.SCREENS = Path(clients["client-a"]["cache"]) / "Screenshots"
    try:
        h.REPORT["final"] = run_cases(h, b, mp, personal, interior.JSON_ENCODER, args.reset_fixture)
        print(f'NATIVE_MP_PERSONALIZATION_PASSED cases={len(h.REPORT["cases"])} {h.write_report("passed")}', flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT["lastSnapshot"] = personal.read_state(h)
        except Exception:
            h.REPORT["lastSnapshot"] = None
        path = h.write_report("failed", error)
        print(error, flush=True)
        print(f"NATIVE_MP_PERSONALIZATION_FAILED {path}; parent-owned clients/server left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
