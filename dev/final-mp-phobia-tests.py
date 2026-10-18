"""Native authoritative-tick checks for RVI phobia adaptation.

Import is inert. Parent owns the guarded MP server and clients. Traits and panic
are temporary fixture state on MELensAdmin and are restored in finally. Vehicle
entry/exit uses the existing native E driver; production trait lookups are
observed through the server-side Java native-tick receipt.
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
ACTOR = "MELensAdmin"


def load_interiors():
    spec = importlib.util.spec_from_file_location(
        "melens_mp_phobia_interiors", Path(__file__).with_name("final-mp-interior-tests.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STATE = r'''
local function readState()
local name="MELensAdmin"; local p
local ps=getOnlinePlayers()
for i=0,ps:size()-1 do local q=ps:get(i); if q:getUsername()==name then p=q; break end end
if not p then return false end
local v=p:getVehicle(); local seat=v and v:getSeat(p) or -1
local f=MELensRV and MELensRV.phobiaInfo and MELensRV.phobiaInfo(p)
return {x=p:getX(),y=p:getY(),z=p:getZ(),vehicleId=v and v:getId() or -1,seat=seat,
    profile=v and MELens.profileFor(v) and MELens.profileFor(v).name or false,
    profileScript=v and v:getScript():getFullName() or false,
    panic=p:getStats():get(CharacterStat.PANIC),beta=p:getBetaEffect(),betaDelta=p:getBetaDelta(),
    godMode=p:isGodMod(),
    agoraphobic=p:getCharacterTraits():get(CharacterTrait.AGORAPHOBIC)==true,
    claustrophobic=p:getCharacterTraits():get(CharacterTrait.CLAUSTROPHOBIC)==true,
    receipt=f or false,ageHours=getGameTime():getWorldAgeHours(),multiplier=getGameTime():getThirtyFPSMultiplier()}
end
return enc(readState())
'''


class PhobiaLab:
    def __init__(self, session: Path, output: Path):
        self.module = load_interiors()
        self.lab = self.module.InteriorLab(session, output)
        self.h, self.b = self.lab.h, self.lab.b
        self.lab.vid = int(self.h.lua("local v=getPlayer():getVehicle(); return v and v:getId() or -1"))
        self.h.check(self.lab.vid >= 0, "admin must already be inside the starting Flying Cloud")
        self.original = None
        self.traits_saved = False
        self.h.check(self.server("return tostring(MELensRV~=nil and type(MELensRV.phobiaInfo)=='function')") == "true",
                     "native phobia receipt contract is not present")
        self.h.REPORT.update(scope=__doc__.strip(), nativeInput=False,
                             productionTickEvidence="dedicated-server Java trait lookup receipt from IsoGameCharacter.updateInternal",
                             fixturePlayer=ACTOR, fixtureRestored=False, cases=[])
        self.h.check(self.lab.server("return tostring(isServer())..\"/\"..tostring(isClient())") == "true/false",
                     "dedicated authoritative server is required for this test")

    def server(self, code: str):
        return self.lab.server(code)

    def state(self):
        raw = self.server(self.module.JSON_ENCODER + STATE)
        return json.loads(raw) if isinstance(raw, str) else raw

    def owner_state(self):
        # MELensAdmin is owned by client A in this fixture.
        return self.h.lua("local p=getPlayer(); return p and {username=p:getUsername(), "
                          "panic=p:getStats():get(CharacterStat.PANIC), "
                          "panicMoodle=p:getMoodles():getMoodleLevel(MoodleType.PANIC), "
                          "vehicleId=p:getVehicle() and p:getVehicle():getId() or -1} or false")

    def configure_traits(self, agor: bool, claustro: bool, panic: float = 25.0,
                         beta: float = 0.0, beta_delta: float = 0.0):
        self.server("local p; local ps=getOnlinePlayers(); for i=0,ps:size()-1 do local q=ps:get(i); "
                    "if q:getUsername()=='MELensAdmin' then p=q; break end end; assert(p); "
                    "local t=p:getCharacterTraits(); "
                    f"t:set(CharacterTrait.AGORAPHOBIC,{str(agor).lower()}); "
                    f"t:set(CharacterTrait.CLAUSTROPHOBIC,{str(claustro).lower()}); "
                    f"p:getStats():set(CharacterStat.PANIC,{panic:.6f}); "
                    f"p:setBetaEffect({beta:.6f}); p:setBetaDelta({beta_delta:.6f}); "
                    "p:setGodMod(false); "
                    "return 'configured'")

    def snapshot_original(self):
        s = self.state()
        self.h.check(s, "MELensAdmin is not available on the authoritative server")
        self.original = s
        self.traits_saved = True
        return s

    def collect(self, seconds=1.5):
        samples = []
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            row = self.state()
            self.h.check(row, "MELensAdmin vanished during authoritative sample")
            row["ownerA"] = self.owner_state()
            samples.append(row)
            time.sleep(.10)
        return samples

    def await_owner_sync(self, case, timeout=4.0):
        # Allow a bounded network/tick lag instead of assuming server and owner
        # RPC reads land on the same simulation frame.
        deadline = time.monotonic() + timeout
        latest = None
        while time.monotonic() < deadline:
            server_state, owner_state = self.state(), self.owner_state()
            self.h.check(owner_state and owner_state.get("username") == ACTOR,
                         f"{case}: client A is not the actual MELensAdmin owner: {owner_state}")
            latest = {"serverPanic": server_state["panic"], "ownerPanic": owner_state["panic"],
                      "error": abs(float(owner_state["panic"]) - float(server_state["panic"])),
                      "ownerMoodle": owner_state["panicMoodle"]}
            latest["expectedMoodle"] = sum(float(owner_state["panic"]) > t for t in (6,30,65,80))
            if latest["error"] <= .35 and latest["ownerMoodle"] == latest["expectedMoodle"]:
                return latest
            time.sleep(.1)
        self.h.check(False, f"{case}: server PANIC did not reach owning client within bounded lag: {latest}")

    def assert_receipt(self, case: str, samples, expected_profile=None):
        receipts = []
        for sample in samples:
            raw = sample.get("receipt")
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError:
                    continue
            if isinstance(raw, dict):
                receipts.append(raw)
        receipt = next((r for r in reversed(receipts) if r.get("inside")), None)
        self.h.check(receipt is not None,
                     f"{case}: no production server native-tick receipt; last={receipts[-1:]}")
        self.h.check(receipt.get("profile") == expected_profile,
                     f"{case}: unexpected profile in tick receipt: {receipt}")
        sequences = [r.get("sequence") for r in receipts if isinstance(r.get("sequence"), (int, float))]
        self.h.check(len(sequences) >= 2 and sequences[-1] > sequences[0],
                     f"{case}: Java native-tick receipt sequence did not advance: {sequences}")
        return receipt

    def sample_inside(self, case: str, profile: str, agor: bool, claustro: bool,
                      panic: float = 25.0, beta: float = 0.0, beta_delta: float = 0.0):
        self.configure_traits(agor, claustro, panic=panic, beta=beta, beta_delta=beta_delta)
        start = self.state()
        owner_start = self.owner_state()
        self.h.check(start.get("seat", -1) >= 0 and start.get("profile") == profile,
                     f"{case}: actor must occupy the expected RVI vehicle: {start}")
        if beta <= 0:
            self.h.check(start.get("beta", 0) <= 0,
                         f"{case}: unexpected vanilla beta panic decay: {start}")
        else:
            self.h.check(start.get("beta", 0) > 0,
                         f"{case}: configured beta fixture did not start active: {start}")
        samples = self.collect()
        finish = self.state()
        owner_finish = self.owner_state()
        sync = self.await_owner_sync(case)
        receipt = self.assert_receipt(case, samples, start.get("profileScript"))
        if agor:
            self.h.check(receipt.get("agoraSuppressed") is True,
                         f"{case}: native Agoraphobic trait lookup was not suppressed: {receipt}")
            self.h.check(finish["panic"] < start["panic"],
                         f"{case}: vanilla panic recovery did not continue inside the cabin: "
                         f"{start['panic']} -> {finish['panic']}")
            if case == "camper-near-cap-agoraphobic":
                self.h.check(max(row["panic"] for row in samples) < 100,
                             f"{case}: suppressed native Agora increment nevertheless reached panic cap")
        else:
            self.h.check(receipt.get("agoraSuppressed") is False,
                         f"{case}: control unexpectedly suppressed Agoraphobic lookup: {receipt}")
        if claustro:
            room = receipt.get("area")
            mult = receipt.get("multiplier")
            self.h.check(isinstance(room, (int, float)) and room > 0 and mult > 0,
                         f"{case}: missing room area or active simulation multiplier: {receipt}")
            expected = .6 * max(0, 1 - room / 70) * mult
            self.h.check(math.isclose(receipt.get("claustroAdded", -1), expected,
                                      rel_tol=1e-5, abs_tol=1e-5),
                         f"{case}: cabin-size rate does not match room area: {receipt}")
            self.h.check(receipt.get("claustroAdded", 0) > 0,
                         f"{case}: native Claustrophobic lookup added no cabin panic: {receipt}")
            self.h.check(math.isclose(receipt.get("panicAtLookupAfter", -1),
                                      min(100, receipt.get("panicAtLookupBefore", 0)
                                          + receipt.get("claustroAdded", 0)),
                                      rel_tol=1e-5, abs_tol=1e-4),
                         f"{case}: native Claustrophobic addition was not applied at trait lookup: {receipt}")
            if case == "camper-near-cap-claustrophobic":
                self.h.check(receipt.get("panicAtLookupAfter") == 100,
                             f"{case}: native Claustrophobic lookup did not exercise the panic cap: {receipt}")
        beta_samples = [row.get("beta", 0) for row in samples]
        if case == "camper-claustrophobic-beta-expiring":
            self.h.check(any(value > 0 for value in beta_samples)
                         and any(value <= 0 for value in beta_samples),
                         f"{case}: native beta did not transition from active to expired: {beta_samples}")
        elif beta > 0:
            self.h.check(all(value > 0 for value in beta_samples),
                         f"{case}: active-beta control expired during sampling: {beta_samples}")
        self.h.REPORT["cases"].append({"name": case, "profile": profile,
                                      "roomArea": receipt.get("area"), "receipt": receipt,
                                      "before": start, "after": finish, "ownerBefore": owner_start,
                                      "ownerAfter": owner_finish, "ownerSync": sync, "samples": samples})
        return receipt

    def native_exit(self):
        s = self.state()
        vid = int(s["vehicleId"])
        marker = self.h.lua(f'local v=getVehicleById({vid}); local q=MELens.profileFor(v); '
                            'return {x=q.exitMarker.x,z=q.exitMarker.z}')
        # Fixture pathing only places the actor at the authored exit; configured E
        # is the actual transition input.
        self.h.lua(f'local p=getPlayer(); MELens.walkTo(p,{marker["x"]:.8f},{marker["z"]:.8f}); return true')
        self.lab.wait(lambda: self.h.lua('local p=getPlayer(); local d=MELens.debugState(); '
                                          'return {moving=d.moving,pathing=MELens.pathing(p),x=d.x,z=d.z}'),
                      lambda r: not r["moving"] and not r["pathing"]
                          and math.dist((r["x"], r["z"]), (marker["x"], marker["z"])) < .08,
                      "native exit fixture reaches authored door marker", timeout=60)
        interact = int(self.h.lua('return getCore():getKey(KeybindId.INTERACT)'))
        self.lab.input("A", key=interact)
        self.lab.wait(lambda: self.state(), lambda r: r and r["vehicleId"] != vid,
                      "configured native E exits RVI", timeout=45)

    def outside_control(self):
        self.native_exit()
        self.configure_traits(True, False)
        initial = self.state()
        self.h.check(initial.get("vehicleId", -1) < 0,
                     f"outside Agoraphobic control is still in a vehicle: {initial}")
        self.h.check(initial.get("beta", 0) <= 0,
                     f"outside Agoraphobic control has beta panic decay active: {initial}")
        before = initial["panic"]
        samples = self.collect()
        final = self.state()
        owner_final = self.owner_state()
        owner_sync = self.await_owner_sync("outside-agoraphobic-unchanged-control")
        after = final["panic"]
        self.h.check(after > before,
                     f"outside Agoraphobic control did not gain native panic: before={before}, after={after}")
        self.h.REPORT["cases"].append({"name": "outside-agoraphobic-unchanged-control",
                                      "before": before, "after": after, "samples": samples,
                                      "finalState": final,
                                      "ownerFinal": owner_final,
                                      "ownerSync": owner_sync,
                                      "nativeVanillaPanicPreserved": True})

    def run(self):
        states = self.lab.all_states()
        self.h.check(all(s.get("ready") for s in states.values()), "A/B/server replication is not ready")
        for side, row in states.items():
            actor = row.get("players", {}).get(ACTOR, {})
            self.h.check(actor.get("vehicleId", -1) >= 0 and actor.get("standing") is True,
                         f"{side}: MELensAdmin must start standing in the same supported interior: {actor}")
        initial = self.snapshot_original()
        self.h.REPORT["originalFixtureState"] = initial
        self.h.lua("ISUIHandler.setVisibleAllUI(true); return true")
        self.h.check(initial.get("profile") == "Flying Cloud 22",
                     f"initial small-cabin fixture must be Flying Cloud 22: {initial}")

        # Start the production server's weak tracking through an actual targeted
        # cabin update, before the no-trait control resets its fixture baseline.
        self.configure_traits(True, False)
        self.h.REPORT["trackingWarmup"] = self.await_owner_sync("targeted-cabin-tracking-warmup")
        self.sample_inside("camper-no-phobia-native-control", "Flying Cloud 22", False, False)
        self.sample_inside("camper-agoraphobic-correction", "Flying Cloud 22", True, False)
        control = self.h.REPORT["cases"][-2]
        agora = self.h.REPORT["cases"][-1]
        control_delta = control["after"]["panic"] - control["before"]["panic"]
        agora_delta = agora["after"]["panic"] - agora["before"]["panic"]
        self.h.check(control_delta < -.5,
                     f"same-time native control did not show vanilla panic recovery: {control_delta}")
        self.h.check(abs(agora_delta - control_delta) <= .3,
                     f"Agoraphobic cabin differs from unchanged panic-recovery control: "
                     f"control={control_delta}, agora={agora_delta}")
        self.sample_inside("camper-near-cap-agoraphobic", "Flying Cloud 22", True, False,
                           panic=99.8)
        small = self.sample_inside("camper-claustrophobic-size-rate", "Flying Cloud 22", False, True)
        self.sample_inside("camper-near-cap-claustrophobic", "Flying Cloud 22", False, True,
                           panic=99.8)
        self.lab.capture("A", "phobia-claustrophobic-panic-moodle")
        self.sample_inside("camper-claustrophobic-beta-active", "Flying Cloud 22", False, True,
                           beta=60, beta_delta=.001)
        self.sample_inside("camper-claustrophobic-beta-expiring", "Flying Cloud 22", False, True,
                           beta=12, beta_delta=.5)
        self.outside_control()

        # The shared fixture helper leaves the camper, spawns/repairs an isolated
        # F700 in the owned test world, and has both clients enter it with native E.
        self.lab.prepare(allow_server_java=True)
        large = self.sample_inside("f700-claustrophobic-size-rate", "F700 Box Truck", False, True)
        self.h.check(small.get("area", 0) != large.get("area", 0),
                     f"room-size fixtures are not distinct: camper={small}, F700={large}")
        small_rate = small["claustroAdded"] / small["multiplier"]
        large_rate = large["claustroAdded"] / large["multiplier"]
        if small["area"] < large["area"]:
            self.h.check(small_rate > large_rate,
                         f"smaller cabin did not receive more claustrophobic panic: {small}, {large}")
        else:
            self.h.check(large_rate > small_rate,
                         f"smaller cabin did not receive more claustrophobic panic: {small}, {large}")
        return {"small": small, "large": large}

    def restore(self):
        if not self.traits_saved or not self.original:
            return
        before = self.original
        self.server("local p; local ps=getOnlinePlayers(); for i=0,ps:size()-1 do local q=ps:get(i); "
                    "if q:getUsername()=='MELensAdmin' then p=q; break end end; assert(p); "
                    "local t=p:getCharacterTraits(); "
                    f"t:set(CharacterTrait.AGORAPHOBIC,{str(before['agoraphobic']).lower()}); "
                    f"t:set(CharacterTrait.CLAUSTROPHOBIC,{str(before['claustrophobic']).lower()}); "
                    f"p:getStats():set(CharacterStat.PANIC,{float(before['panic']):.6f}); "
                    f"p:setBetaEffect({float(before['beta']):.6f}); "
                    f"p:setBetaDelta({float(before['betaDelta']):.6f}); "
                    f"p:setGodMod({str(before['godMode']).lower()}); return 'restored'")
        after = self.state()
        self.h.check(after and after["agoraphobic"] == before["agoraphobic"]
                     and after["claustrophobic"] == before["claustrophobic"]
                     and math.isclose(after["panic"], before["panic"], abs_tol=1e-4)
                     and math.isclose(after["beta"], before["beta"], abs_tol=1e-4)
                     and math.isclose(after["betaDelta"], before["betaDelta"], abs_tol=1e-4)
                     and after["godMode"] == before["godMode"],
                     f"trait fixture was not restored: {after}")
        self.h.REPORT["fixtureRestored"] = True
        self.h.REPORT["restoredState"] = after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-208")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-phobia")
    args = parser.parse_args()
    lab = None
    try:
        lab = PhobiaLab(args.session.resolve(), args.output.resolve())
        result = lab.run()
        lab.restore()
        print(f"NATIVE_MP_PHOBIA_PASSED {lab.h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        if lab is not None:
            try:
                lab.restore()
            except Exception:
                error += "\nFixture restoration failed:\n" + traceback.format_exc()
            try:
                lab.h.REPORT["lastSnapshot"] = lab.state()
                path = lab.h.write_report("failed", error)
            except Exception:
                path = args.output / "native-feature-tests.json"
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            path = args.output / "native-feature-tests.json"
            path.write_text(json.dumps({"status": "failed", "nativeInput": False,
                                        "preconditionFailure": True, "error": error}, indent=2) + "\n",
                            encoding="utf-8")
        print(error, flush=True)
        print(f"NATIVE_MP_PHOBIA_FAILED {path}; parent-owned clients/server left running", flush=True)
        return 1
    finally:
        if lab is not None:
            for api in (lab.h, lab.b):
                try:
                    api.lua("MEMCNativeLab.releaseKeys(); return true")
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
