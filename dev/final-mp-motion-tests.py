"""Native two-client cabin motion and standing-to-furniture cleanup checks.

Import is inert. Parent owns guarded client/server lifetime. Both players must
already stand in the same camper. Movement, Rest-menu selection and E use real
native input; pathing only establishes repeatable test positions and exit setup.
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
NAMES = {"A": "MELensAdmin", "B": "MELensGuest"}


def load_driver(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOTION_STATE = r'''
local p=getPlayer();local d=MELens.debugState();local c=getCore()
local function key(bind)
    local k=c:getKey(bind);if k and k>0 then return k end
    k=c:getAltKey(bind);return k and k>0 and k or 0
end
local ok,anim=pcall(function() return MELensRV.animInfo(p) end)
local setOk,animSet=pcall(function() return p:GetAnimSetName() end)
local v=p and p:getVehicle()
return {username=p and p:getUsername(),vehicleId=v and v:getId() or -1,seat=v and v:getSeat(p) or -1,
    x=d.x,z=d.z,facing=d.facing,standing=d.standing==true,moving=d.moving==true,
    running=d.running==true,pose=d.pose or "",pathing=d.pathing==true,
    forward=key("Forward"),backward=key("Backward"),left=key("Left"),right=key("Right"),
    run=key(KeybindId and KeybindId.RUN or "Run"),interact=key(KeybindId and KeybindId.INTERACT or "Interact"),
    cabin=p and p:getVariableString("MELensCabin") or false,
    seatFlag=p and p:getVariableBoolean("MELensCabinSeat") or false,
    animOk=ok,anim=ok and anim or tostring(anim),animSetOk=setOk,animSet=setOk and animSet or tostring(animSet),
    trackJson=MELensDevBones.tracks(p)}
'''

REMOTE_STATE = r'''
local target;local ps=getOnlinePlayers()
for i=0,ps:size()-1 do local p=ps:get(i);if p:getUsername()==TARGET then target=p;break end end
if not target then return {ready=false} end
local v=target:getVehicle();local seat=v and v:getSeat(target) or -1
local standing=v and seat>=0 and MELens.isStandingSeat(v,nil,seat) or false
local r=MELens.Sync and MELens.Sync.remote and MELens.Sync.remote[target:getOnlineID()]
local ok,anim=pcall(function() return MELensRV.animInfo(target) end)
local setOk,animSet=pcall(function() return target:GetAnimSetName() end)
return {ready=true,vehicleId=v and v:getId() or -1,seat=seat,standing=standing,
    cabin=target:getVariableString("MELensCabin") or false,seatFlag=target:getVariableBoolean("MELensCabinSeat"),
    animOk=ok,anim=ok and anim or tostring(anim),animSetOk=setOk,animSet=setOk and animSet or tostring(animSet),
    received=r and r.received or false,
    renderX=r and r.renderX or false,renderZ=r and r.renderZ or false,
    targetX=r and r.x or false,targetZ=r and r.z or false,snap=r and r.snap or false,
    pose=r and (r.running and "Run" or r.w and "Walk" or "Idle") or false,
    trackJson=MELensDevBones.tracks(target)}
'''

# Translate each actual WASD-style axis/chord through the vehicle's current
# world-to-local transform, then retain only a collision-free cabin route.
ROUTE_SCAN = r'''
local p=getPlayer();local v=p:getVehicle();local q=MELens.profileFor(v);local d=MELens.debugState()
local combos={
    {"Forward",0,-1},{"Backward",0,1},{"Left",-1,0},{"Right",1,0},
    {"Forward","Left",-1,-1},{"Forward","Right",1,-1},
    {"Backward","Left",-1,1},{"Backward","Right",1,1}}
local function dir(ix,iy)
    local wx,wy=iy+ix,iy-ix;local length=math.sqrt(wx*wx+wy*wy);wx,wy=wx/length,wy/length
    local a,b=Vector3f.new(),Vector3f.new();v:getLocalPos(p:getX(),p:getY(),0,a);v:getLocalPos(p:getX()+wx,p:getY()+wy,0,b)
    local dx,dz=b:x()-a:x(),b:z()-a:z();local n=math.sqrt(dx*dx+dz*dz);return dx/n,dz/n
end
local rows={}
for _,c in ipairs(combos) do
    local ix,iy=c[#c-1],c[#c];local dx,dz=dir(ix,iy);local free=0
    for step=.04,3.0,.04 do if not MELens.walkableAt(q,d.x+dx*step,d.z+dz*step) then break end;free=step end
    local keys={};for i=1,#c-2 do local name=c[i];local k=getCore():getKey(name);if not k or k<=0 then k=getCore():getAltKey(name) end;keys[#keys+1]=k or 0 end
    rows[#rows+1]={keys=keys,ix=ix,iy=iy,dx=dx,dz=dz,free=free,longitudinal=math.abs(dz)}
end
return {x=d.x,z=d.z,facing=d.facing,rows=rows}
'''


def unset(value):
    return value is None or value is False or value == "" or value == "null"


def track_rows(sample):
    raw = sample.get("trackJson")
    if not isinstance(raw, str):
        raise AssertionError(f"developer animation-track probe missing from sample: {sample}")
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise AssertionError(f"developer animation-track probe returned a non-list: {raw!r}")
    return rows


def advancing_clip(samples, expected):
    """Find three consecutive blended samples for one named track that advances."""
    token = expected.lower()
    parsed = [track_rows(sample) for sample in samples]
    for start in range(max(0, len(parsed) - 2)):
        first = parsed[start]
        for track in first:
            name = str(track.get("name", ""))
            if token not in name.lower() or track.get("blend", 0) < .75:
                continue
            chain = [track]
            for rows in parsed[start + 1:start + 3]:
                match = next((row for row in rows if row.get("id") == track.get("id")
                              and row.get("name") == track.get("name") and row.get("blend", 0) >= .75), None)
                if match is None:
                    break
                chain.append(match)
            if len(chain) != 3:
                continue
            advances = []
            for before, after in zip(chain, chain[1:]):
                time_delta = float(after.get("time", 0)) - float(before.get("time", 0))
                fraction_delta = (float(after.get("fraction", 0)) - float(before.get("fraction", 0))) % 1.0
                advances.append(time_delta > .0001 or .0001 < fraction_delta < .5)
            if all(advances):
                return {"id": track["id"], "name": track["name"], "samples": chain}
    return None


class MotionLab:
    def __init__(self, session: Path, output: Path):
        self.interior = load_driver("final-mp-interior-tests")
        self.ui = load_driver("final-mp-bus-tests")
        self.lab = self.interior.InteriorLab(session, output)
        self.h, self.b = self.lab.h, self.lab.b
        self.lab.vid = int(self.h.lua("local v=getPlayer():getVehicle();return v and v:getId() or -1"))
        self.h.check(self.lab.vid >= 0, "admin must already be standing inside a vehicle")
        self.h.REPORT.update(scope=__doc__.strip(), vehicleId=self.lab.vid,
                             inputCoverage=["idle control", "native collision-free movement keys",
                                            "native configured Run chord", "native Rest UI", "native E stand/exit"],
                             setupMutations="No saved furniture, inventory or vehicle parts are changed")

    def state(self, side):
        return (self.h if side == "A" else self.b).lua(MOTION_STATE)

    def remote(self, observer, username):
        code = REMOTE_STATE.replace("TARGET", json.dumps(username))
        return (self.h if observer == "A" else self.b).lua(code)

    def wait_pose_clear(self, side, username, animation_set="player"):
        observer = "B" if side == "A" else "A"
        result = self.lab.wait(lambda: {"local": self.state(side), "remote": self.remote(observer, username)},
                               lambda r: unset(r["local"].get("cabin")) and not r["local"].get("seatFlag")
                                   and not r["local"].get("standing")
                                   and r["remote"].get("ready") and unset(r["remote"].get("cabin"))
                                   and not r["remote"].get("seatFlag") and not r["remote"].get("standing"),
                               f"{username} RVI variables clear locally and remotely", timeout=20)
        for location in ("local", "remote"):
            state = result[location]
            anim = state.get("anim", "")
            if anim != "none":
                self.h.check(state.get("animOk") is True and f"animSet={animation_set}" in anim
                             and "standing=false" in anim,
                             f"{location} animation context does not match {animation_set}: {state}")
            self.h.check(state.get("animSetOk") is True and state.get("animSet") == animation_set,
                         f"{location} animation set/state is not the ordinary outside player: {state}")
        return result

    def record_rest_seat(self, side):
        """Use native context-menu clicks to sit in a real existing interior seat."""
        api = self.h if side == "A" else self.b
        before = self.lab.all_states()
        point = api.lua(self.ui.SEAT_POINT)
        self.h.check(point, f"{side} has no visible, available interior seat for the Rest test")
        self.lab.input(side, x=point["x"], y=point["y"], right=True)
        menu = self.lab.wait(lambda: api.lua(self.ui.REST_MENU), bool, f"{side} native Rest context menu")
        self.h.check(not menu["disabled"], f"{side} Rest option is disabled")
        self.lab.capture(side, f"mp-motion-{side.lower()}-rest-menu")
        self.lab.input(side, x=menu["parentX"], y=menu["parentY"])
        menu = self.lab.wait(lambda: api.lua(self.ui.REST_MENU), lambda s: bool(s) and s["visible"],
                             f"{side} native Rest submenu")
        self.lab.input(side, x=menu["x"], y=menu["y"])
        seated = self.lab.wait(self.lab.all_states,
                               lambda ss: all(ss.get(k, {}).get("players", {}).get(NAMES[side], {}).get("vehicleId") == self.lab.vid
                                   and ss[k]["players"][NAMES[side]].get("seat", -1) >= 0
                                   and not ss[k]["players"][NAMES[side]].get("standing") for k in ("A", "B", "server")),
                               f"{side} native Rest seats player on A/B/server", timeout=45)
        self.h.record(f"{side.lower()}-native-rest-seats-standing-player", before, seated, furnitureIndex=point["index"])
        self.wait_pose_clear(side, NAMES[side], "player-vehicle")
        own = self.state(side)
        self.h.check(own.get("animSetOk") is True and own.get("animSet") == "player-vehicle",
                     f"seated interior character did not return to vehicle animation set: {own}")

    def stand_native(self, side):
        api = self.h if side == "A" else self.b
        before = self.lab.all_states()
        state = self.state(side)
        self.h.check(state.get("interact", 0) > 0, "configured Interact binding unavailable")
        self.lab.input(side, key=int(state["interact"]))
        after = self.lab.wait(self.lab.all_states,
                              lambda ss: all(ss.get(k, {}).get("players", {}).get(NAMES[side], {}).get("vehicleId") == self.lab.vid
                                  and ss[k]["players"][NAMES[side]].get("standing") is True for k in ("A", "B", "server")),
                              f"{side} native E stands up inside the camper", timeout=45)
        self.h.record(f"{side.lower()}-native-e-stands-from-furniture", before, after,
                      interactKey=state["interact"])
        observer = "B" if side == "A" else "A"
        pair = self.lab.wait(lambda: {"local": self.state(side), "remote": self.remote(observer, NAMES[side])},
                             lambda row: row["local"].get("standing") is True
                                 and row["local"].get("cabin") in ("Idle", "Walk", "Run")
                                 and row["local"].get("seatFlag") is True
                                 and row["local"].get("animSetOk") is True
                                 and row["local"].get("animSet") == "player"
                                 and row["remote"].get("ready")
                                 and row["remote"].get("standing") is True
                                 and row["remote"].get("cabin") in ("Idle", "Walk", "Run")
                                 and row["remote"].get("seatFlag") is True,
                             f"{side} standing pose rebinds on both clients after E", timeout=20)
        self.h.record(f"{side.lower()}-standing-pose-restored-after-e", {}, pair)
        return api

    def exit_native(self, side):
        api = self.h if side == "A" else self.b
        marker = api.lua('local p=getPlayer();local q=MELens.profileFor(p:getVehicle());'
                         'return {x=q.exitMarker.x,z=q.exitMarker.z}')
        # Fixture pathing positions the test character at the actual door marker;
        # the resulting exit is still dispatched by the configured native E.
        api.lua(f'local p=getPlayer();MELens.walkTo(p,{marker["x"]:.8f},{marker["z"]:.8f});return true')
        ready = self.lab.wait(lambda: self.state(side),
                              lambda s: s.get("standing") and not s.get("pathing")
                                  and math.dist((s.get("x", 999), s.get("z", 999)), (marker["x"], marker["z"])) < .08,
                              f"{side} setup path reaches the authored cabin exit marker", timeout=60)
        before = self.lab.all_states()
        self.h.check(ready.get("interact", 0) > 0, "configured Interact binding unavailable")
        self.lab.input(side, key=int(ready["interact"]))
        after = self.lab.wait(self.lab.all_states,
                              lambda ss: all(ss.get(k, {}).get("players", {}).get(NAMES[side], {}).get("vehicleId") != self.lab.vid
                                             for k in ("A", "B", "server")),
                              f"{side} native E exits at the cabin entrance", timeout=90)
        self.h.record(f"{side.lower()}-native-e-normal-exit", before, after,
                      fixtureSetup="MELens.walkTo authored exit marker", interactKey=ready["interact"])
        return self.wait_pose_clear(side, NAMES[side])

    def choose_route(self):
        scan = self.h.lua(ROUTE_SCAN)
        rows = self.h._sequence(scan["rows"])
        # Lua numeric tables are serialized as JSON objects by the test endpoint
        # when nested (for example {"1": 17, "2": 31}), while the top-level
        # rows are normalized by _sequence. Normalize the key chord too, before
        # validating it or passing it to holdKey.
        normalized = []
        for source in rows:
            row = dict(source)
            row["keys"] = self.h._sequence(row.get("keys"))
            normalized.append(row)
        clear = [row for row in normalized if len(row.get("keys", [])) in (1, 2)
                 and all(int(k) > 0 for k in row["keys"]) and row.get("free", 0) >= 2.0]
        self.h.check(clear, f"no collision-free 2-tile cabin path for real movement keys: {normalized}")
        longitudinal = [row for row in clear if row.get("longitudinal", 0) >= .75]
        self.h.check(longitudinal, f"no clear route aligned with vehicle length: {clear}")
        chosen = max(longitudinal, key=lambda r: (r["free"], r["longitudinal"]))
        return {"scan": scan, "route": chosen}

    def fixture_to(self, x, z, label):
        self.h.lua(f'local p=getPlayer();assert(MELens.isStanding(p));MELens.walkTo(p,{x:.8f},{z:.8f});return true')
        return self.lab.wait(lambda: self.state("A"),
                             lambda s: s.get("standing") and not s.get("pathing")
                                 and math.dist((s.get("x", 999), s.get("z", 999)), (x, z)) < .04,
                             label, timeout=45)

    def move_test(self, kind, route, duration=1200):
        before = self.state("A")
        h = self.h
        codes = list(route["keys"])
        if kind == "run":
            self.h.check(before.get("run", 0) > 0, "configured Run binding unavailable")
            codes.append(int(before["run"]))
        self.h.check(before.get("standing") and not before.get("pathing"), f"{kind}: actor not settled in cabin")
        # Start the movement chord and Run binding in one endpoint dispatch so
        # diagonal movement keys overlap for the full measured interval.
        hold_calls = ";".join(f"MEMCNativeLab.holdKey({int(code)},{duration})" for code in codes)
        self.h.lua(hold_calls + ";return true")
        for code in codes:
            h.REPORT["inputs"].append({"client": "A", "api": "holdKey", "key": int(code),
                                       "milliseconds": duration, "phase": kind})
        h.REPORT["nativeInput"] = True
        h.REPORT["activeCase"] = kind
        end = time.monotonic() + duration / 1000 + .6
        actor, remote = [], []
        while time.monotonic() < end:
            actor.append(self.state("A")); remote.append(self.remote("B", NAMES["A"])); time.sleep(.045)
        self.h.check(any(s.get("moving") for s in actor), f"native {kind} key chord made no cabin movement")
        expected = "Run" if kind == "run" else "Walk"
        self.h.check(any(s.get("pose") == expected and s.get("moving") for s in actor),
                     f"native {kind} chord failed to produce local {expected} pose")
        self.h.check(any(s.get("pose") == expected for s in remote),
                     f"observer never received {expected} pose for {kind}")
        local_clip = advancing_clip(actor, expected)
        remote_clip = advancing_clip(remote, expected)
        self.h.check(local_clip is not None,
                     f"local {expected} clip had no advancing stable track over three blended samples")
        self.h.check(remote_clip is not None,
                     f"observer {expected} clip had no advancing stable track over three blended samples")
        points = [(s.get("x"), s.get("z")) for s in actor if isinstance(s.get("x"), (int, float))
                  and isinstance(s.get("z"), (int, float))]
        displacement = math.dist(points[0], points[-1]) if len(points) > 1 else 0
        render = [(s["renderX"], s["renderZ"]) for s in remote if isinstance(s.get("renderX"), (int, float))
                  and isinstance(s.get("renderZ"), (int, float))]
        steps = [math.dist(a, b) for a, b in zip(render, render[1:])]
        interpolated = [s for s in remote if s.get("snap") is False
                        and isinstance(s.get("renderX"), (int, float)) and isinstance(s.get("targetX"), (int, float))
                        and math.dist((s["renderX"], s["renderZ"]), (s["targetX"], s["targetZ"])) > .0005]
        h.check(len({(round(x, 4), round(z, 4)) for x, z in render}) >= 2,
                f"observer render position did not change during {kind}")
        h.check(not steps or max(steps) < .5, f"observer had an unsmoothed render jump: {max(steps)}")
        h.check(interpolated, f"observer sampled no intermediate interpolated {kind} position")
        result = {"before": before, "durationMs": duration, "displacement": displacement,
                  "actorSamples": actor, "remoteSamples": remote, "remoteInterpolationSamples": interpolated,
                  "animationTrackEvidence":{"local":local_clip,"remote":remote_clip},
                  "remoteMaxStep": max(steps, default=0), "route": route}
        h.record(f"native-{kind}-same-open-cabin-route", before, actor[-1], durationMs=duration,
                 displacement=displacement, remoteMaxStep=max(steps, default=0),
                 remoteInterpolationSamples=len(interpolated), animationTrackEvidence=result["animationTrackEvidence"])
        return result

    def run(self):
        h, lab = self.h, self.lab
        initial = lab.all_states()
        h.check(all(s.get("ready") for s in initial.values()), "A/B/server vehicle replication is incomplete")
        for side in ("A", "B", "server"):
            for name in NAMES.values():
                p = initial[side].get("players", {}).get(name, {})
                h.check(p.get("vehicleId") == lab.vid and p.get("standing") is True,
                        f"both players must begin standing in the same camper ({side}, {name}): {p}")
        for api in (h, self.b):
            api.lua("MEMCNativeLab.releaseKeys();ISUIHandler.setVisibleAllUI(false);return true")
        route_info = self.choose_route()
        route = route_info["route"]
        start = route_info["scan"]
        h.check(start.get("x") is not None and start.get("facing") is not None,
                "repeatable route start/facing was not captured")
        idle = []
        until = time.monotonic() + 1.2
        while time.monotonic() < until:
            idle.append(self.state("A")); time.sleep(.1)
        h.check(all(not p.get("moving") and not p.get("running") and p.get("pose") == "Idle" for p in idle),
                "1200ms idle control did not remain at Idle")
        h.record("idle-control-1200ms", {}, idle[-1], samples=idle)
        self.h.check("animSetOk" in idle[-1] and idle[-1]["animSetOk"] is True
                     and idle[-1]["animSet"] == "player",
                     f"standing idle does not use the normal player animation set: {idle[-1]}")
        run_key = idle[-1].get("run", 0)
        h.check(run_key > 0 and int(run_key) not in route["keys"],
                f"Run key is unavailable or collides with chosen movement chord: {route}")
        # Establish the same session-owned facing as well as the same cabin
        # offset by following the identical short setup path before each run.
        walk_start = self.fixture_to(start["x"] + route["dx"] * .30,
                                     start["z"] + route["dz"] * .30,
                                     "walk setup reaches a point along the chosen open route")
        walk_start = self.fixture_to(start["x"], start["z"], "walk setup restores exact movement origin")
        start = dict(start, facing=walk_start.get("facing"))
        h.check(start.get("facing") is not None, "walk setup did not establish the movement facing")
        walk = self.move_test("walk", route)
        self.exit_native("A")
        lab.enter_e("A")
        # Repeat the same setup path to establish the exact original point and
        # the same movement-session facing without mutating presentation state.
        self.fixture_to(start["x"] + route["dx"] * .30, start["z"] + route["dz"] * .30,
                        "setup reaches a point along the chosen open route")
        same_start = self.fixture_to(start["x"], start["z"], "setup restores exact movement origin")
        same_start = self.state("A")
        self.h.check(math.dist((same_start["x"], same_start["z"]), (start["x"], start["z"])) < .04,
                     "setup failed to restore the exact route origin")
        self.h.check(abs((same_start.get("facing") or 0) - start["facing"]) < .01,
                     f"walk/run setup facing differs: walk={start['facing']}, run={same_start.get('facing')}")
        run = self.move_test("run", route)
        h.check(walk["durationMs"] == run["durationMs"], "walk and run durations differ")
        h.check(run["displacement"] > walk["displacement"] * 1.1,
                f"Run was not faster along the scanned open route: walk={walk['displacement']:.3f}, run={run['displacement']:.3f}")
        h.record("equal-duration-open-route-run-faster", walk, run,
                 route=route, routeScan=route_info["scan"], speedRatio=run["displacement"] / max(walk["displacement"], .0001))
        # Seating is the transition that reaches MELens_Sync.release while the
        # character remains in the same vehicle. Observe flags from the other client.
        for side in ("A", "B"):
            self.record_rest_seat(side)
            self.stand_native(side)
            self.exit_native(side)
        final = lab.all_states()
        h.record("both-clients-normal-outside-animation-after-rest-and-exit", {}, final,
                 animationEvidence={side: self.state(side).get("anim") for side in ("A", "B")},
                 expectedOutside="animSet=player, standing=false, MELensCabin unset, MELensCabinSeat=false")
        h.REPORT["final"] = final
        # Restore the owned starting fixture for the next independent driver.
        # Exit acceptance is retained above before either re-entry occurs.
        for side in ("A", "B"):
            lab.enter_e(side)
        restored = lab.wait(lab.all_states,
                            lambda states: all(row.get("players", {}).get(name, {}).get("standing") is True
                                for row in states.values() for name in NAMES.values()),
                            "both native re-entries restore the owned standing fixture", timeout=45)
        h.REPORT["restoredStandingFixture"] = restored
        return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, default=ROOT / "build/rv/final-mp-208")
    parser.add_argument("--output", type=Path, default=ROOT / "build/rv/final-mp-motion")
    args = parser.parse_args()
    lab = None
    try:
        lab = MotionLab(args.session.resolve(), args.output.resolve())
        lab.run()
        print(f"NATIVE_MP_MOTION_PASSED {lab.h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        if lab is not None:
            try: lab.h.REPORT["lastSnapshot"] = lab.lab.all_states()
            except Exception: pass
            path = lab.h.write_report("failed", error)
        else:
            args.output.mkdir(parents=True, exist_ok=True)
            path = args.output / "native-feature-tests.json"
            path.write_text(json.dumps({"status": "failed", "nativeInput": False,
                                        "preconditionFailure": True, "error": error}, indent=2) + "\n",
                            encoding="utf-8")
        print(error, flush=True)
        print(f"NATIVE_MP_MOTION_FAILED {path}; parent-owned clients/server left running", flush=True)
        return 1
    finally:
        if lab is not None:
            for api in (lab.h, lab.b):
                try: api.lua("MEMCNativeLab.releaseKeys();return true")
                except Exception: pass


if __name__ == "__main__":
    raise SystemExit(main())
