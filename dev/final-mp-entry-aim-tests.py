"""Focused entry/aim checks inside the parent-owned dedicated-server session.

Spawning, equipping and approaching are fixture setup. E and Aim use native input
polling; mouse targets use the production event queue. No user profile is touched.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"A": "MELensAdmin", "B": "MELensGuest"}


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ready(lab, sides):
    result = {}
    for side in sides:
        api = lab.h if side == "A" else lab.b
        result[side] = lab.wait(lambda: api.lua(
            'local p=getPlayer(); local v=p:getVehicle(); local q=ISTimedActionQueue.queues[p]; '
            'return v and {standing=MELens.isStanding(p),entering=p:getVariableBoolean("bEnteringVehicle"),'
            'queue=q and #q.queue or 0,vehicleId=v:getId()} or false'),
            lambda s: s and s["standing"] and not s["entering"] and s["queue"] == 0 and s["vehicleId"] == lab.vid,
            f"{side} standing entry finishes and releases action queue", timeout=30)
    return result


def aim(lab, label, sides):
    h = lab.h
    # Keep the native target list nonempty at several vehicle-relative angles.
    lab.server(f'local v=getVehicleById({lab.vid}); assert(v); '
               'for _,d in ipairs({{3,0},{-3,0},{0,3},{0,-3}}) do '
               'local zs=addZombiesInOutfit(math.floor(v:getX()+d[1]),math.floor(v:getY()+d[2]),0,1,nil,0,'
               'false,false,false,false,true,false,1,false,0,false,false); '
               'if zs then for i=0,zs:size()-1 do zs:get(i):setUseless(true) end end end; return "targets spawned"')
    for side in sides:
        api = h if side == "A" else lab.b
        # Equipment is fixture setup; no firing or damage assertions are made.
        lab.server('local ps=getOnlinePlayers(); for i=0,ps:size()-1 do local p=ps:get(i); '
                   f'if p:getUsername()=="{NAMES[side]}" then local w=p:getInventory():AddItem("Base.Pistol"); '
                   'assert(w); sendAddItemToContainer(p:getInventory(),w) end end; return true')
        lab.wait(lambda: api.lua('local p=getPlayer(); local items=p:getInventory():getItems(); '
                                'for i=0,items:size()-1 do local w=items:get(i); if w:getFullType()=="Base.Pistol" then '
                                'p:setPrimaryHandItem(w); p:setSecondaryHandItem(nil); return true end end; return false'),
                 bool, f"{side} authoritative fixture pistol replicated")
        targets = lab.wait(lambda: api.lua(
            'local p=getPlayer(); local out={}; local zs=getCell():getZombieList(); '
            'for i=0,zs:size()-1 do local z=zs:get(i); if p:DistToSquared(z:getX(),z:getY())<144 then '
            'local x,y=ISCoordConversion.ToScreen(z:getX(),z:getY(),z:getZ()); local zoom=getCore():getZoom(0); '
            'x=math.floor(x/zoom); y=math.floor(y/zoom); '
            'if x>20 and x<1260 and y>20 and y<700 then out[#out+1]={x=x,y=y} end end end; return out'),
            lambda value: len(h._sequence(value)) >= 2, f"{side} replicated zombies in aim range", timeout=30)
        rows = []
        key = int(api.lua('return getCore():getKey(KeybindId.AIM)'))
        h.check(key > 0, "Aim key is unbound")
        for target in h._sequence(targets)[:4]:
            api.lua(f'MEMCNativeLab.holdKey({key},2000); return true')
            time.sleep(.2)
            lab.input(side, x=target["x"], y=target["y"], right=True)
            state = lab.wait(lambda: api.lua(
                'local p=getPlayer(); local v=p:getVehicle(); local c=v:getPartForSeatContainer(v:getSeat(p)):getItemContainer(); '
                'return {aiming=p:isAiming(),standing=MELens.isStanding(p),weight=c:getCapacityWeight(),'
                'capacity=c:getCapacity(),weapon=p:getPrimaryHandItem():getFullType()}'),
                lambda s: s["aiming"] and s["standing"], f"{side} native Aim while standing")
            h.check(state["weight"] == 0 and state["capacity"] == 0, "native combat container is not empty")
            rows.append(state)
            time.sleep(.4)
        lab.capture(side, f"{label}-{side.lower()}-aim")
        api.lua('MEMCNativeLab.releaseKeys(); return true')
        h.record(f"{label}-{side.lower()}-native-aim-at-zombies", {}, rows, targetCount=len(h._sequence(targets)))


def camper(lab, module):
    for api in (lab.h, lab.b):
        api.lua('MELens.leave(getPlayer()); return true')
        lab.wait(lambda: api.lua('return getPlayer():getVehicle()==nil'), bool, "fixture exit before camper")
    loaded = json.loads(lab.server(module.JSON_ENCODER + 'local out={}; local it=getCell():getVehicles():iterator(); '
                                  'while it:hasNext() do local v=it:next(); out[#out+1]={x=v:getX(),y=v:getY()} end; return enc(out)'))
    points = module.clear_spawn_candidates(lab.h._sequence(loaded))
    lab.h.check(points, "no clear camper spawn point")
    x, y = points[0]
    script = "Base.Trailer54FlyingCloud22"
    lab.h.lua(f'SendCommandToServer("/addvehicle {script} {x},{y},0"); return true')
    vid = lab.wait(lambda: lab.h.lua(
        f'local it=getCell():getVehicles():iterator(); while it:hasNext() do local v=it:next(); '
        f'if v:getScript():getFullName()=="{script}" and math.abs(v:getX()-{x})<5 and math.abs(v:getY()-{y})<5 then return v:getId() end end; return false'),
        lambda value: isinstance(value, (int, float)) and not isinstance(value, bool), "fresh camper replication", timeout=30)
    lab.vid = int(vid)
    lab.server(f'local v=getVehicleById({lab.vid}); v:repair(); for i=0,v:getPartCount()-1 do local p=v:getPartByIndex(i); '
               'if p:getDoor() then p:getDoor():setLocked(false); v:transmitPartDoor(p) end end; return true')
    for side, api in (("A", lab.h), ("B", lab.b)):
        lab.wait(lambda: api.lua(f'local v=getVehicleById({lab.vid}); return v and MELens.canWalkIn(getPlayer(),v)'), bool, "camper settled")
        lab.enter_e(side)
    ready(lab, ("A", "B"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    module = load("final-mp-interior-tests")
    lab = module.InteriorLab(args.session.resolve(), args.output.resolve())
    metadata = json.loads((args.session / "session.json").read_text(encoding="utf-8-sig"))
    logs = {Path(r["cache"]) / "console.txt": 0 for r in metadata["clients"]}
    logs[Path(metadata["serverConsole"])] = 0
    logs = {p: p.stat().st_size for p in logs}
    try:
        lab.prepare(allow_server_java=True)
        ready(lab, ("A", "B"))
        audit = (ROOT / "dev/lua/entry_profile_audit.lua").read_text(encoding="utf-8")
        lab.h.REPORT["nativeSeatAudit"] = {"A": lab.h.lua(audit), "B": lab.b.lua(audit)}
        aim(lab, "f700", ("A", "B"))
        camper(lab, module)
        aim(lab, "camper", ("A", "B"))
        lab.h.REPORT["final"] = lab.all_states()
        for path, offset in logs.items():
            with path.open("rb") as stream:
                stream.seek(offset)
                text = stream.read().decode("utf-8", errors="replace")
            lab.h.check("CombatManager.calculateHitChanceData" not in text, f"combat exception in {path.name}")
        print(f"NATIVE_ENTRY_AIM_PASSED {lab.h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        print(f"NATIVE_ENTRY_AIM_FAILED {lab.h.write_report('failed', error)}\n{error}", flush=True)
        return 1
    finally:
        for api in (lab.h, lab.b):
            try:
                api.lua('MEMCNativeLab.releaseKeys(); return true')
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
