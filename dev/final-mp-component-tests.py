"""Run the native utility component probes on an owned no-Java MP server.

Importing this module is inert. The parent owns the server and both clients;
the wrapper uses the admin client's existing Lua bridge only to submit one
authoritative server evaluation. This proves real engine component behavior,
not Dashboard input or multiplayer UI acceptance.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import traceback


ROOT = Path(__file__).resolve().parents[1]


def load_driver(name: str):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load sibling driver {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def server_probe_code(actor_id: int, observer_id: int, vehicle_id: int, encoder: str, probe: str) -> str:
    """Build one server eval, restoring the shared fixture global even on error."""
    # ISTimedActionQueue is loaded from client/TimedActions. On the no-Java
    # dedicated server, the engine-owned character action stack is the shared
    # authority for whether an actor has a running timed action.
    sp_idle_assert = 'assert(#ISTimedActionQueue.getTimedActionQueue(p).queue == 0, "wait for timed actions")'
    if sp_idle_assert not in probe:
        raise ValueError("native utility probe idle precondition changed; review before running")
    probe = probe.replace(sp_idle_assert,
                          'assert(p:getCharacterActions():isEmpty(), "wait for server character actions")', 1)
    probe = probe.replace(
        'assert(MELens.VERSION=="2.0.6", "wrong native release")',
        'assert(isServer() and not isClient(), "probe must run on no-Java MP server")',
        1,
    )
    creation = "groundGenerator=IsoGenerator.new(item,getCell(),ground);"
    tagged_creation = (creation +
                       ' groundGenerator:getModData().MELensMPComponentFixture="final-mp-components-206";')
    if creation not in probe:
        raise ValueError("native utility probe ground-generator fixture changed; review before running")
    probe = probe.replace(creation, tagged_creation, 1)
    ending = 'return {passed=true,scope="native component probes; real engine objects; direct update calls; no UI claim",cases=results}'
    replacement = ('return {passed=true,scope="native component probes; real engine objects; direct update calls; no UI claim",'
                   'cases=results,groundGenerator={tag=groundGenerator:getModData().MELensMPComponentFixture,'
                   'x=groundGenerator:getSquare():getX(),y=groundGenerator:getSquare():getY(),'
                   'fuel=groundGenerator:getFuel(),activated=groundGenerator:isActivated()}}')
    if ending not in probe:
        raise ValueError("native utility probe result contract changed; review before running")
    probe = probe.replace(ending, replacement, 1)

    preflight = f'''
assert(isServer() and not isClient(),"component fixtures must run on no-Java server")
assert(MELensRV==nil,"server unexpectedly loaded the client-only Java bridge")
local aid,bid,vid={actor_id},{observer_id},{vehicle_id}
local p,b
local players=getOnlinePlayers()
for i=0,players:size()-1 do local q=players:get(i)
    if q:getOnlineID()==aid then p=q elseif q:getOnlineID()==bid then b=q end
end
local v=getVehicleById(vid)
assert(p and b and v and p:getVehicle()==v and b:getVehicle()==v,
    "both actors must remain inside the requested camper")
assert(v:getScript():getFullName()=="Base.Trailer54FlyingCloud22",
    "MP component fixture requires the furnished Flying Cloud 22 camper")
assert(math.abs(v:getCurrentSpeedKmHour())<.1,"component fixture camper must be stopped")
local standing={{}}
for _,id in ipairs(MELens.standingIds(MELens.profileFor(v))) do standing[id]=true end
for _,q in ipairs({{p,b}}) do
    local seat=v:getSeat(q)
    assert(seat>=0 and standing[v:getScript():getPassenger(seat):getId()],
        "both actors must occupy standing places before the probe")
    assert(q:getCharacterActions():isEmpty(),
        "both server character action stacks must be empty before the component probe")
end
local square=getCell():getGridSquare(v:getSquare():getX()+3,v:getSquare():getY(),v:getSquare():getZ())
assert(square and not square:getGenerator(),"three-tile ground-generator fixture square is occupied or missing")
local previous=MELensFeatureTest
MELensFeatureTest={{player=p,observer=b,vehicle=v}}
local ok,result=pcall(function()
    {probe}
end)
MELensFeatureTest=previous
if not ok then error(result) end
return enc(result)
'''
    return encoder + preflight


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-206",
                        help="parent-owned two-client/server session label or directory")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-components")
    parser.add_argument("--vehicle-id", type=int, required=True,
                        help="furnished, stopped Flying Cloud 22 occupied by both standing actors")
    parser.add_argument("--endpoint-a", default="http://127.0.0.1:18470/lua?depth=8&sandbox=false")
    parser.add_argument("--endpoint-b", default="http://127.0.0.1:18472/lua?depth=8&sandbox=false")
    args = parser.parse_args()

    h = load_driver("final-feature-tests")
    mp = load_driver("final-mp-features")
    interior = load_driver("final-mp-interior-tests")
    h.configure(args.output, args.endpoint_a)
    b = load_driver("final-feature-tests")
    b.ENDPOINT = args.endpoint_b
    h.REPORT.update(scope="real no-Java MP server component probe; direct production update calls; no UI/input claim",
                    nativeInput=False, componentOnly=True, session=str(args.session.resolve()),
                    vehicleId=args.vehicle_id, gameLifecycleOwnedByParent=True)
    output = h.OUTPUT / "native-mp-component-tests.json"
    try:
        a_info = h.lua('local p=getPlayer(); local v=p and p:getVehicle(); return p and v and '
                       '{client=isClient(),id=p:getOnlineID(),vehicleId=v:getId(),'
                       'standing=MELens.isStanding(p),idle=#ISTimedActionQueue.getTimedActionQueue(p).queue==0} or false')
        b_info = b.lua('local p=getPlayer(); local v=p and p:getVehicle(); return p and v and '
                       '{client=isClient(),id=p:getOnlineID(),vehicleId=v:getId(),'
                       'standing=MELens.isStanding(p),idle=#ISTimedActionQueue.getTimedActionQueue(p).queue==0} or false')
        h.check(isinstance(a_info, dict) and isinstance(b_info, dict),
                "both parent-owned clients must be inside the camper")
        h.check(a_info.get("client") and b_info.get("client") and a_info.get("id") != b_info.get("id")
                and a_info.get("vehicleId") == args.vehicle_id == b_info.get("vehicleId")
                and a_info.get("standing") and b_info.get("standing")
                and a_info.get("idle") and b_info.get("idle"),
                "both distinct actors must be idle and standing in the requested camper")
        probe = (ROOT / "dev/lua/native-utility-components.lua").read_text(encoding="utf-8")
        code = server_probe_code(int(a_info["id"]), int(b_info["id"]), args.vehicle_id,
                                 interior.JSON_ENCODER, probe)
        server = mp.ServerEval(h)
        result = json.loads(server(code, timeout=45))
        h.check(isinstance(result, dict) and result.get("passed"), "native MP component probes failed")
        h.REPORT.update(status="passed", actors={"A": a_info, "B": b_info},
                        serverNoJava=True, serverVersionAssertion="omitted; MELens.VERSION is client-only",
                        packageIdentity="inherited from parent source/package hash verification",
                        nativeComponents=result,
                        caveat="Direct production utility updates on server-owned real engine objects; not native Dashboard input or two-client replication acceptance.")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(h.REPORT, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"NATIVE_MP_COMPONENTS_PASSED {output}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        h.REPORT.update(status="failed", error=error)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(h.REPORT, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(error, flush=True)
        print(f"NATIVE_MP_COMPONENTS_FAILED {output}; parent-owned clients/server left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
