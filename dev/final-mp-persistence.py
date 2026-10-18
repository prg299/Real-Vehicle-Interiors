"""Capture/verify MP save data around a parent-owned server restart.

Import is inert. No save, launch, quit, disconnect or process control occurs.
Capture adds identity markers to the three tested vehicles. Optional explicit
--quiesce-fixture stops their utilities/engines and current weather as fixture
setup. Verify never applies that setup, resets values or injects saved items.
Lazy inventory requests only refresh observations. Automatic passenger recovery
is measured before optional --allow-reentry uses ordinary entry paths.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
KEY = "MELensNativePersistence206"
NAMES = {"A": "MELensAdmin", "B": "MELensGuest"}
SCRIPTS = {"f700": "Base.87fordF700box", "camper": "Base.Trailer54FlyingCloud22", "bus": "Base.87fordB700school"}


def load_interiors():
    spec = importlib.util.spec_from_file_location("melens_mp_persistence", Path(__file__).with_name("final-mp-interior-tests.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


SNAPSHOT = r'''
local token="TOKEN"; local key="MELensNativePersistence206"
local r={version=MELens.VERSION,vehicles={},players={},server=isServer(),ageHours=getGameTime():getWorldAgeHours(),rain=getClimateManager():getRainIntensity()}
local function items(c)
    local out={}
    if c then for i=0,c:getItems():size()-1 do local it=c:getItems():get(i); local fc=it:getFluidContainer()
        local row={id=it:getID(),type=it:getFullType(),condition=it:getCondition(),fluid=fc and fc:getAmount() or false,
            delta=instanceof(it,"DrainableComboItem") and it:getUsedDelta() or false}
        if instanceof(it,"InventoryContainer") then row.children=items(it:getInventory()) end
        out[tostring(it:getID())]=row
    end end
    return out
end
local function installed(it)
    if not it then return false end
    return {id=it:getID(),type=it:getFullType(),condition=it:getCondition(),
        delta=instanceof(it,"DrainableComboItem") and it:getUsedDelta() or false}
end
local function standing(v,seat)
    if not v or seat<0 then return false end
    local passenger=v:getScript():getPassenger(seat)
    for _,id in ipairs(MELens.standingIds(MELens.profileFor(v))) do if passenger:getId()==id then return true end end
    return false
end
local vehicles=getCell():getVehicles():iterator()
while vehicles:hasNext() do local v=vehicles:next(); local mark=v:getModData()[key]
    if mark and mark.token==token then
        assert(not r.vehicles[mark.label],"duplicate persisted vehicle marker")
        local U,H,P=MELens.Utilities,MELens.Home,MELens.Parts
        local g,w=U.generatorState(v),U.waterState(v); assert(g and w,"saved utility part missing")
        local pr,pg,pb=H.paint(v); local floor=v:getPartById(P.FLOOR); local oven=v:getPartById(P.OVEN)
        local stable={script=v:getScript():getFullName(),maxPassengers=v:getMaxPassengers(),parts={},partOrder={},
            name=H.givenName(v) or "",paint=pr and {r=pr,g=pg,b=pb} or false,
            loose=floor and floor:getModData().loose or {},utilities={generatorOn=g.on,generatorFuel=g.fuel,
                generatorCondition=g.condition,generatorWear=g.part:getModData().wear or 0,
                water=w.water,tainted=w.tainted,propane=U.propaneLevel(v),
                stoveOn=U.isOn(v,"stove"),heaterOn=U.isOn(v,"heater"),lightsOff=v:getModData().MELensLightsOff==true,
                ovenHeat=oven and (oven:getModData().heat or 1) or 1}}
        for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i); local id=part:getId()
            stable.partOrder[#stable.partOrder+1]=id
            stable.parts[id]={condition=part:getCondition(),installed=installed(part:getInventoryItem()),contents=items(part:getItemContainer())}
        end
        r.vehicles[mark.label]={networkId=v:getId(),sqlId=v:getSqlId(),x=v:getX(),y=v:getY(),z=v:getZ(),engine=v:isEngineRunning(),payload=stable}
    end
end
local function person(p)
    local name=p:getUsername(); if name~="MELensAdmin" and name~="MELensGuest" then return end
    local v=p:getVehicle(); local mark=v and v:getModData()[key]; local seat=v and v:getSeat(p) or -1
    local role={vehicle=mark and mark.token==token and mark.label or false,seatId=seat>=0 and v:getScript():getPassenger(seat):getId() or false,
        standing=v and standing(v,seat) or false}
    local row={role=role,x=p:getX(),y=p:getY(),z=p:getZ(),onlineId=p:getOnlineID()}
    if v and seat>=0 then local q=v:getPassengerLocalPos(seat,Vector3f.new()); local w=v:getPassengerWorldPos(seat,Vector3f.new())
        row.localPosition={x=q:x(),y=q:y(),z=q:z()}; row.expectedWorld={x=w:x(),y=w:y(),z=w:z()}
    end
    if isServer() or p==getPlayer() then row.inventory=items(p:getInventory()) end
    r.players[name]=row
end
local players=getOnlinePlayers(); for i=0,players:size()-1 do person(players:get(i)) end
if not isServer() and getPlayer() then person(getPlayer()) end
return r
'''


class Persistence:
    def __init__(self, session, output, fuel_tolerance=0, propane_tolerance=0):
        self.module = load_interiors(); self.lab = self.module.InteriorLab(session, output)
        self.h, self.b = self.lab.h, self.lab.b
        self.h.ENDPOINT = self.h.ENDPOINT.replace("depth=8", "depth=14")
        self.b.ENDPOINT = self.b.ENDPOINT.replace("depth=8", "depth=14")
        self.session = session; self.metadata = json.loads((session / "session.json").read_text(encoding="utf-8-sig"))
        self.tolerances = {"generatorFuel": fuel_tolerance, "propane": propane_tolerance}
        self.h.REPORT.update(scope=__doc__.strip(), nativeInput=False, dataPersistenceVerified=False,
                             automaticPassengerRestorationVerified=False, ordinaryReentryVerified=False,
                             tolerances=self.tolerances, token=None, snapshots={})
        self.token = None
        self.h.check(self.lab.server('return tostring(isServer()).."/"..tostring(MELensRV==nil)') == "true/true", "no-Java dedicated server required")

    def server(self, code):
        return json.loads(self.lab.server(self.module.JSON_ENCODER + code))

    def snapshot(self, side):
        code = SNAPSHOT.replace("TOKEN", self.token)
        if side == "server":
            code = code.rsplit("return r", 1)[0] + "return enc(r)"
            state = self.server(code)
        else: state = (self.h if side == "A" else self.b).lua(code)
        for vehicle in state["vehicles"].values():
            vehicle["payload"]["partOrder"] = self.h._sequence(vehicle["payload"].get("partOrder"))
        return state

    def snapshots(self):
        return {side: self.snapshot(side) for side in ("server", "A", "B")}

    def differences(self, before, after, path="", errors=None):
        errors = [] if errors is None else errors
        if len(errors) >= 30: return errors
        if isinstance(before, dict) and isinstance(after, dict):
            for key in before.keys() | after.keys():
                if len(errors) >= 30: break
                label = path + "." + str(key)
                if key not in before or key not in after: errors.append({"path": label, "before": before.get(key, "<missing>"), "after": after.get(key, "<missing>")})
                else: self.differences(before[key], after[key], label, errors)
        elif isinstance(before, list) and isinstance(after, list):
            if len(before) != len(after): errors.append({"path": path, "beforeLength": len(before), "afterLength": len(after)})
            else:
                for index, pair in enumerate(zip(before, after)): self.differences(*pair, path + f"[{index}]", errors)
        elif before != after or isinstance(before, bool) != isinstance(after, bool):
            tolerance = self.tolerances.get(path.rsplit(".", 1)[-1], 0) if ".utilities." in path else 0
            if isinstance(before, (int, float)) and not isinstance(before, bool) and isinstance(after, (int, float)) and not isinstance(after, bool) and abs(before-after) <= tolerance: return errors
            errors.append({"path": path, "before": before, "after": after, "tolerance": tolerance})
        return errors

    def replica_differences(self, states):
        errors = []; authority = states["server"]
        if set(authority["vehicles"]) != set(SCRIPTS): return [{"missingServerVehicles": sorted(set(SCRIPTS)-set(authority["vehicles"]))}]
        for side in ("A", "B"):
            client = states[side]
            for label, server_vehicle in authority["vehicles"].items():
                self.differences(server_vehicle["payload"], client.get("vehicles", {}).get(label, {}).get("payload"), side + "." + label, errors)
            name = NAMES[side]
            self.differences(authority.get("players", {}).get(name, {}).get("inventory"), client.get("players", {}).get(name, {}).get("inventory"), side + ".inventory", errors)
        return errors

    def wait(self, read, predicate, label, seconds=60):
        return self.lab.wait(read, predicate, label, timeout=seconds)

    def refresh_containers(self):
        # Requesting an engine container refresh changes observations, not item
        # ownership. It avoids mistaking an unrequested lazy container for empty.
        self.wait(self.snapshots, lambda ss: all(set(s["vehicles"]) == set(SCRIPTS) for s in ss.values()), "all three persisted vehicle markers replicated", seconds=90)
        code = 'local it=getCell():getVehicles():iterator(); local n=0; while it:hasNext() do local v=it:next(); local m=v:getModData().' + KEY + '; '
        code += f'if m and m.token=="{self.token}" then for i=0,v:getPartCount()-1 do local c=v:getPartByIndex(i):getItemContainer(); '
        code += 'if c then c:requestServerItemsForContainer(); n=n+1 end end end end; return n'
        self.h.REPORT["containerObservationRequests"] = {side: api.lua(code) for side, api in (("A", self.h), ("B", self.b))}

    def capture(self, args):
        baseline_path = args.output / "before.json"
        self.h.check(not baseline_path.exists(), "baseline exists; use a new output directory to preserve it")
        ids = {}
        for label in SCRIPTS:
            explicit = getattr(args, label + "_id")
            if explicit is not None: ids[label] = explicit; continue
            report_path = getattr(args, label + "_report")
            report = json.loads(report_path.read_text(encoding="utf-8-sig"))
            self.h.check(report.get("status") == "passed", f"{label} report did not pass")
            ids[label] = int(report["fixture"]["actor"]["vehicleId"] if label == "camper" else report["final"]["server"]["vehicle"]["id"])
        self.token = uuid.uuid4().hex
        rows = ",".join(f'{{label="{label}",id={vid},script="{SCRIPTS[label]}"}}' for label, vid in ids.items())
        self.lab.server('local rows={' + rows + '}; for _,row in ipairs(rows) do local v=assert(getVehicleById(row.id)); '
                        'assert(v:getScript():getFullName()==row.script,"wrong tested vehicle"); '
                        f'v:getModData().{KEY}={{token="{self.token}",label=row.label}}; v:transmitModData(); end; return "marked"')
        if args.quiesce_fixture:
            self.lab.server('for _,row in ipairs({' + rows + '}) do local v=getVehicleById(row.id); local U=MELens.Utilities; '
                            'U.setSwitch(v,"generator",false); U.setSwitch(v,"stove",false); U.setSwitch(v,"heater",false); '
                            'v:getModData().MELensLightsOff=true; U.observeLamps(v,true); v:transmitModData(); '
                            'if v:isEngineRunning() then v:engineDoShuttingDown(); v:transmitEngine() end end; '
                            'getClimateManager():stopWeatherAndThunder(); return "quiescence fixture applied without changing item IDs or quantities"')
            for api in (self.h, self.b): api.lua('getPlayer():getStats():setThirst(0); return true')
        self.h.REPORT["quiescenceFixture"] = args.quiesce_fixture
        def quiescent(states):
            if set(states["server"]["vehicles"]) != set(SCRIPTS): return False
            for v in states["server"]["vehicles"].values():
                u=v["payload"]["utilities"]
                if v["engine"] or u["generatorOn"] or u["stoveOn"] or u["heaterOn"] or not u["lightsOff"] or u["ovenHeat"] > 1.001: return False
            return states["server"]["rain"] <= .02
        self.wait(self.snapshots, quiescent, "all engines, utilities and lights off; oven cool and weather dry", seconds=120)
        self.refresh_containers()
        states = self.wait(self.snapshots, lambda ss: not self.replica_differences(ss), "A/B match authority including original container/item IDs", seconds=90)
        self.h.REPORT["snapshots"]["before"] = states
        baseline = {"schema": 1, "token": self.token, "session": str(self.session), "capturedUtc": datetime.now(timezone.utc).isoformat(),
                    "payloadHashes": json.loads((self.session / "payload-hashes.json").read_text()), "states": states,
                    "quiescenceFixture": args.quiesce_fixture, "quantitiesExplicitlySetByFixture": False}
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        for side in ("A", "B"): self.lab.capture(side, "mp-persistence-" + side.lower() + "-before")
        self.h.REPORT["token"] = self.token; self.h.REPORT["baseline"] = str(baseline_path)
        self.h.record("three-vehicle-authority-and-two-client-checkpoint-captured", {}, states, noSaveCalled=True)
        return baseline

    def roles_match(self, expected, states):
        mismatches = []
        for side, state in states.items():
            for name, row in expected.items():
                self.differences(row["role"], state.get("players", {}).get(name, {}).get("role"), side + "." + name + ".role", mismatches)
        return mismatches

    def verify(self, args):
        baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig")); self.token = baseline["token"]
        self.h.REPORT["token"] = self.token
        self.h.check(self.metadata.get("resumed") and Path(self.metadata["resumeFrom"]).resolve() == Path(baseline["session"]).resolve(), "verification must use a fresh ResumeFrom lifetime of this baseline")
        self.h.check(json.loads((self.session / "payload-hashes.json").read_text()) == baseline["payloadHashes"], "RVI payload changed across persistence test")
        initial = self.snapshots(); self.h.REPORT["snapshots"]["firstAfterReconnect"] = initial
        self.refresh_containers()
        expected = baseline["states"]["server"]
        def data_errors(states):
            errors=[]
            for label, old in expected["vehicles"].items():
                new = states["server"].get("vehicles", {}).get(label, {})
                self.differences(old["payload"], new.get("payload"), "server." + label, errors)
                if old["sqlId"] > 0: self.differences(old["sqlId"], new.get("sqlId"), "server." + label + ".sqlId", errors)
            for name, old in expected["players"].items():
                self.differences(old["inventory"], states["server"].get("players", {}).get(name, {}).get("inventory"), "server." + name + ".inventory", errors)
            return errors + self.replica_differences(states)
        states = self.wait(self.snapshots, lambda ss: not data_errors(ss), "saved IDs, containers, conditions, utilities, name/paint and loose positions preserved", seconds=90)
        self.h.REPORT["dataPersistenceVerified"] = True
        try:
            automatic = self.wait(self.snapshots, lambda ss: not self.roles_match(expected["players"], ss), "automatic passenger membership restoration", seconds=20)
            self.h.REPORT["automaticPassengerRestorationVerified"] = True
        except AssertionError:
            automatic = self.snapshots()
            self.h.REPORT["automaticPassengerDifferences"] = self.roles_match(expected["players"], automatic)
        self.h.REPORT["snapshots"]["automaticRestoration"] = automatic
        if not self.h.REPORT["automaticPassengerRestorationVerified"] and args.allow_reentry:
            for side, name in NAMES.items():
                role = expected["players"][name]["role"]
                if not role["vehicle"]: continue
                api = self.h if side == "A" else self.b
                current = api.lua('local v=getPlayer():getVehicle(); return v and v:getId() or false')
                vid = states["server"]["vehicles"][role["vehicle"]]["networkId"]
                self.h.check(current is False or current == vid, "ordinary reentry will not overwrite another vehicle membership")
                if current is not False: continue
                self.lab.vid = vid
                if role["standing"]: self.lab.enter_e(side)
                else:
                    api.lua(f'local v=getVehicleById({vid}); local seat=v:getScript():getPassengerIndex("{role["seatId"]}"); assert(seat>=0); ISVehicleMenu.onEnter(getPlayer(),v,seat); return true')
            states = self.wait(self.snapshots, lambda ss: not self.roles_match(expected["players"], ss), "ordinary reentry restores expected passenger membership", seconds=90)
            self.h.REPORT["ordinaryReentryVerified"] = True
        self.h.check(self.h.REPORT["automaticPassengerRestorationVerified"] or self.h.REPORT["ordinaryReentryVerified"], "data persisted, but automatic passenger restoration failed; parent session remains available")
        self.h.check(not data_errors(self.snapshots()), "reentry changed persisted vehicle/item data")
        self.h.REPORT["snapshots"]["after"] = self.snapshots()
        for side in ("A", "B"): self.lab.capture(side, "mp-persistence-" + side.lower() + "-after-" + str(time.time_ns()))
        self.h.record("no-java-server-fresh-restart-and-two-client-data-persistence", baseline["states"], self.h.REPORT["snapshots"]["after"],
                      automaticPassengerRestoration=self.h.REPORT["automaticPassengerRestorationVerified"], ordinaryReentry=self.h.REPORT["ordinaryReentryVerified"])


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("mode",choices=("capture","verify"))
    p.add_argument("--session",type=Path,default=ROOT/"build/rv/final-mp-206b")
    p.add_argument("--output",type=Path,default=ROOT/"build/rv/final-mp-persistence")
    p.add_argument("--baseline",type=Path,default=ROOT/"build/rv/final-mp-persistence/before.json")
    p.add_argument("--quiesce-fixture",action="store_true"); p.add_argument("--allow-reentry",action="store_true")
    p.add_argument("--fuel-tolerance",type=float,default=0); p.add_argument("--propane-tolerance",type=float,default=0)
    p.add_argument("--tolerance-reason",default="exact: all consuming utilities off")
    for label,folder in (("f700","final-mp-interiors"),("camper","final-mp-features"),("bus","final-mp-bus")):
        p.add_argument("--"+label+"-id",type=int); p.add_argument("--"+label+"-report",type=Path,default=ROOT/"build/rv"/folder/"native-feature-tests.json")
    args=p.parse_args(); args.session=args.session.resolve(); args.output=args.output.resolve()
    if args.fuel_tolerance<0 or args.propane_tolerance<0: p.error("tolerances must be nonnegative")
    lab=None
    try:
        lab=Persistence(args.session,args.output,args.fuel_tolerance,args.propane_tolerance)
        lab.h.REPORT["toleranceReason"]=args.tolerance_reason
        lab.capture(args) if args.mode=="capture" else lab.verify(args)
        status="passed"; code=0
    except Exception:
        status="failed"; code=1; error=traceback.format_exc(); print(error,flush=True)
        if lab is not None:
            lab.h.REPORT["error"]=error
            try: lab.h.REPORT["lastSnapshot"]=lab.snapshots() if lab.token else None
            except Exception: pass
        else:
            args.output.mkdir(parents=True,exist_ok=True)
    report=lab.h.REPORT if lab is not None else {"error":error,"nativeInput":False,"preconditionFailure":True}
    report.update(status=status,mode=args.mode,finishedUtc=datetime.now(timezone.utc).isoformat(),parentLifecycleUntouched=True)
    target=args.output/(args.mode+"-"+str(time.time_ns())+".json")
    target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(f"NATIVE_MP_PERSISTENCE_{status.upper()} {target}",flush=True)
    return code


if __name__=="__main__": raise SystemExit(main())
