"""Native Dashboard input checks in an already owned, guarded test game.

Importing this module performs no I/O or game calls. Root owns game lifecycle.
Fixture state is set separately; feature actions use only MEMCNativeLab.clickAt,
which feeds the production mouse event queue and UI dispatch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import time
import traceback
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "http://127.0.0.1:18470/lua?depth=8&sandbox=false"
OUTPUT = ROOT / "build/rv/final-feature-tests"
SCREENS = ROOT / "build/rv/testhome/Zomboid/Screenshots"
REPORT = {}
_input_release = 0.0


def configure(output=None, endpoint=None):
    """Configure a report destination; no game calls. Also reset case records."""
    global OUTPUT, ENDPOINT, REPORT, _input_release
    if output is not None:
        OUTPUT = Path(output).resolve()
    if endpoint is not None:
        ENDPOINT = endpoint
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORT = {"startedAt": datetime.now(timezone.utc).isoformat(), "nativeInput": False,
              "scope": "disposable single-player native game; production mouse/UI/timed-action paths",
              "gameLifecycleOwnedByParent": True, "cases": [], "inputs": [], "captures": []}
    _input_release = 0.0


def lua(code):
    request = urllib.request.Request(ENDPOINT, code.encode("utf-8"), {"Content-Type": "text/plain"})
    with urllib.request.urlopen(request, timeout=15) as response:
        body = json.load(response)
    if not body.get("ok"):
        raise RuntimeError(f"Lua request failed: {body}")
    return body.get("result")


def _sequence(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [entry for _, entry in sorted(value.items(), key=lambda pair: int(pair[0]))]


def snapshot():
    state = lua("return MELensFeatureTest.snapshot()")
    check(isinstance(state, dict), "missing feature-fixture snapshot")
    state["controls"] = _sequence(state.get("controls"))
    state["queue"] = _sequence(state.get("queue"))
    return state


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def wait_for(predicate, timeout=60, label="expected native state"):
    REPORT["activeWait"] = label
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = snapshot()
        # A mouse event has a bounded hover/press/release schedule. Never mistake
        # the pre-dispatch idle state for a completed click.
        if time.monotonic() >= _input_release and predicate(last):
            return last
        time.sleep(.10)
    raise AssertionError(f"Timeout waiting for {label}: {json.dumps(last, ensure_ascii=False)}")


def wait_idle(timeout=60):
    return wait_for(lambda state: state["queueCount"] == 0, timeout, "empty timed-action queue")


def _control(state, action):
    controls = [entry for entry in state["controls"] if entry["action"] == action]
    check(len(controls) == 1, f"expected one Dashboard control for {action}: {controls}")
    return controls[0]


def click_control(action, enabled=True, timeout=10):
    """Click a live control center using native input only; return before state."""
    global _input_release
    REPORT["activeCase"] = action
    before = wait_for(lambda state: _control(state, action)["enabled"] is enabled,
                      timeout, f"{action} enabled={enabled}")
    control = _control(before, action)
    x, y = int(control["centerX"]), int(control["centerY"])
    check(0 <= x < 1280 and 0 <= y < 720, f"offscreen {action} control: {control}")
    lua(f"MEMCNativeLab.clickAt({x},{y}); return true")
    _input_release = time.monotonic() + .55
    REPORT.setdefault("inputs", []).append({"action": action, "api": "MEMCNativeLab.clickAt",
                                            "x": x, "y": y, "enabledAtClick": enabled})
    REPORT["nativeInput"] = True
    return before


def record(name, before, after, **details):
    entry = {"name": name, "passed": True, "before": before, "after": after}
    entry.update(details)
    REPORT.setdefault("cases", []).append(entry)
    REPORT["activeCase"] = None
    print(f"PASS {name}", flush=True)
    return entry


def capture(name):
    check(name and all(char in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in name), "capture name")
    source = SCREENS / f"{name}.png"
    if source.is_file():
        source.unlink()
    lua(f'MEMCNativeLab.capture("{name}.png"); return true')
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if source.is_file() and source.stat().st_size > 0:
            try:
                # Native PNG is written asynchronously. File existence alone
                # does not establish that the complete image has reached disk.
                complete = False
                with source.open("rb") as image:
                    if source.stat().st_size >= 12:
                        image.seek(-12, 2)
                        complete = image.read() == b"\x00\x00\x00\x00IEND\xaeB`\x82"
                if complete:
                    target = OUTPUT / source.name
                    shutil.copy2(source, target)
                    REPORT.setdefault("captures", []).append(str(target))
                    return str(target)
            except PermissionError:
                pass
        time.sleep(.10)
    raise AssertionError(f"native screenshot did not arrive: {source}")


def write_report(status, error=None):
    REPORT["status"] = status
    REPORT["finishedAt"] = datetime.now(timezone.utc).isoformat()
    if error is not None:
        REPORT["error"] = error
    path = OUTPUT / "native-feature-tests.json"
    path.write_text(json.dumps(REPORT, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _near(a, b, tolerance=.0003):
    return math.isclose(float(a), float(b), abs_tol=tolerance, rel_tol=0)


def _assert_same_committed(before, after):
    for key, expected in before["utilities"].items():
        actual = after["utilities"].get(key)
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            check(_near(actual, expected), f"disabled click changed {key}: {expected} -> {actual}")
        else:
            check(actual == expected, f"disabled click changed {key}: {expected} -> {actual}")
    for key, expected in before["inventory"].items():
        actual = after["inventory"][key]
        for field in ("id", "inMainInventory", "amount", "propane"):
            if isinstance(expected[field], (float, int)) and field not in ("id", "inMainInventory"):
                check(_near(actual[field], expected[field]), f"disabled click changed {key}.{field}")
            else:
                check(actual[field] == expected[field], f"disabled click changed {key}.{field}")
    check(after["queueCount"] == 0, "disabled click queued an action")
    for key in ("x", "y", "z", "passengerX", "passengerZ"):
        if key in before["player"]:
            check(_near(after["player"][key], before["player"][key], .02), f"UI input leaked into player movement ({key})")
    check(not after["player"].get("aiming", False), "UI click leaked into aiming")
    check(after["player"].get("pathActive", False) == before["player"].get("pathActive", False),
          "UI click changed scene path state")


def disabled_case(action, name):
    before = click_control(action, enabled=False)
    # Observe the whole input delivery window plus several later frames. Every
    # sample is checked; a fixed sleep alone never counts as successful evidence.
    deadline = time.monotonic() + 1.0
    after = before
    while time.monotonic() < deadline or time.monotonic() < _input_release:
        after = snapshot()
        _assert_same_committed(before, after)
        time.sleep(.10)
    return record(name, before, after, rejectedInput=True, sceneInputConsumed=True)


def _toggle(action, state_key, on):
    before = click_control(action)
    check(before["utilities"][state_key] is not on, f"{action} already equals requested target")
    after = wait_for(lambda state: state["queueCount"] == 0 and state["utilities"][state_key] is on,
                     label=f"{action}={on}")
    record(f"{action}-{'on' if on else 'off'}", before, after)
    return after


def run_dashboard_cases(skip_full_capacity=False, generator_fuel_timeout=30):
    initial = wait_idle()
    check(initial["player"]["inside"], "test player must stand inside the camper")
    check(not initial["player"]["timedActionInstant"], "normal timed-action evidence requires instant actions disabled")
    check(_near(initial["utilities"]["generatorFuel"], 0), "feature fixture must start empty")
    capture("features-initial")
    disabled_case("generator", "empty-generator-rejected")

    before = click_control("addFuel")
    after = wait_for(lambda state: state["queueCount"] == 0 and state["utilities"]["generatorFuel"] > .49
                     and state["inventory"]["petrol"]["amount"] < .001, label="native Add fuel transfer")
    check(_near(before["sums"]["petrol"], after["sums"]["petrol"]), "petrol transfer failed conservation")
    record("add-fuel-conserves-real-fluid", before, after)
    disabled_case("addFuel", "missing-petrol-rejected")

    on = _toggle("generator", "generatorOn", True)
    check(on["utilities"]["generatorRunning"] and on["utilities"]["hasPower"], "generator did not provide power")
    burned = wait_for(lambda state: state["utilities"]["generatorFuel"] < on["utilities"]["generatorFuel"] - .00001,
                      timeout=generator_fuel_timeout, label="running generator fuel consumption")
    record("generator-burns-fuel", on, burned)
    capture("features-generator-running")
    _toggle("generator", "generatorOn", False)

    before = click_control("fixGenerator")
    expected = min(100, before["utilities"]["generatorCondition"] + 4 + int(before["player"]["electricity"] / 2))
    after = wait_for(lambda state: state["queueCount"] == 0 and state["utilities"]["generatorCondition"] == expected
                     and not state["inventory"]["scrap"]["inMainInventory"], label="generator repair and scrap consumption")
    record("repair-consumes-scrap", before, after)
    disabled_case("fixGenerator", "missing-scrap-rejected")

    before = click_control("addWater")
    after = wait_for(lambda state: state["queueCount"] == 0 and state["utilities"]["water"] > .49
                     and state["inventory"]["water"]["amount"] < .001, label="native Add water transfer")
    check(_near(before["sums"]["water"], after["sums"]["water"]), "water transfer failed conservation")
    record("add-water-conserves-real-fluid", before, after)
    disabled_case("addWater", "missing-water-rejected")

    before = click_control("addPropane")
    after = wait_for(lambda state: state["queueCount"] == 0 and state["utilities"]["propane"] > .099
                     and state["inventory"]["propane"]["propane"] < .001, label="native propane transfer")
    check(_near(before["sums"]["propane"], after["sums"]["propane"]), "propane transfer failed conservation")
    record("add-propane-conserves-portable-tank", before, after)
    disabled_case("addPropane", "missing-propane-rejected")

    for action, key in (("stove", "stoveOn"), ("heater", "heaterOn"), ("lights", "lightsOn")):
        _toggle(action, key, True)
        _toggle(action, key, False)
    capture("features-refilled-and-repaired")

    if skip_full_capacity:
        return snapshot()

    # Explicit state-only setup for full-capacity rejection. Real portable supply
    # remains available, so the full tank itself is what disables each button.
    lua('local F=MELensFeatureTest; local v=F.vehicle; local U=MELens.Utilities; '
        'local g=U.generatorState(v); g.part:getModData().fuel=g.capacity; '
        'local w=U.waterState(v); U.changeWater(v,w.capacity-w.water,false); '
        'U.setPropane(v,U.PROPANE_CAPACITY,true); '
        'local fc=F.items.petrol:getFluidContainer(); fc:addFluid(Fluid.Petrol,.25); '
        'fc=F.items.water:getFluidContainer(); fc:addFluid(Fluid.Water,.25); '
        'F.items.propane:setUsedDelta(.1); F.items.petrol:syncItemFields(); '
        'F.items.water:syncItemFields(); F.items.propane:syncItemFields(); U.transmit(v,g.part); return true')
    disabled_case("addFuel", "full-generator-rejected-with-portable-fuel")
    disabled_case("addWater", "full-water-tank-rejected-with-portable-water")
    disabled_case("addPropane", "full-propane-storage-rejected-with-portable-propane")
    capture("features-full-capacity")
    return snapshot()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--endpoint", default=ENDPOINT)
    args = parser.parse_args()
    configure(args.output, args.endpoint)
    try:
        REPORT["final"] = run_dashboard_cases()
        path = write_report("passed")
        print(f"NATIVE_FEATURES_PASSED {path}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        REPORT["lastSnapshot"] = None
        try:
            REPORT["lastSnapshot"] = snapshot()
        except Exception:
            pass
        REPORT["cases"].append({"name": REPORT.get("activeCase") or REPORT.get("activeWait") or "fixture",
                                "passed": False, "error": error,
                                "after": REPORT["lastSnapshot"]})
        path = write_report("failed", error)
        print(error, flush=True)
        print(f"NATIVE_FEATURES_FAILED {path}; parent-owned game left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
