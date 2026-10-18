"""Optional native bed Sleep/confirmation/natural-wake acceptance; import is safe.

Run after utility conservation checks with appliances off: normal sleeping advances
world time and invokes the game's own save. Parent owns all game lifecycle work.
Only tiredness/thirst/last-sleep are fixtures; Sleep, No, Yes and standing use input.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import traceback


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build/rv/final-sleep-tests"


def load_helpers():
    spec = importlib.util.spec_from_file_location("melens_sleep_interior_driver", Path(__file__).with_name("final-interior-tests.py"))
    interior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(interior)
    tap, h = interior.load_helpers()
    return interior, tap, h


FIXTURE = r'''
local T,M=MELensInteriorTest,MELens
local p,v=T.player,T.vehicle
assert(not isClient(),"this sleep check is single-player only")
local stats=p:getStats()
T.sleepFixture={originalFatigue=stats:get(CharacterStat.FATIGUE),originalThirst=stats:get(CharacterStat.THIRST),
    originalLastSleep=p:getLastHourSleeped()}
stats:set(CharacterStat.FATIGUE,0.35) -- native sleep formula stays below eight hours even with bad-bed/+18% trait
stats:set(CharacterStat.THIRST,0)
p:setLastHourSleeped(math.floor(p:getHoursSurvived())-3) -- native setter takes int, verified locally
assert(M.sleepBlocker(p,v)==nil,"native sleep prerequisites are blocked: "..tostring(M.sleepBlocker(p,v)))
local prior=T.snapshot
local function center(c)
    return {x=c:getAbsoluteX()+c:getWidth()/2,y=c:getAbsoluteY()+c:getHeight()/2}
end
function T.snapshot()
    local r=prior()
    local data=getPlayerData(p:getPlayerNum())
    local modal=data and data.vehicleSleepModal
    r.sleep={asleep=p:isAsleep(),fatigue=stats:get(CharacterStat.FATIGUE),thirst=stats:get(CharacterStat.THIRST),
        conservativeMaxHours=(stats:get(CharacterStat.FATIGUE)*13+2)*1.18,
        worldHours=getGameTime():getWorldAgeHours(),lastSleep=p:getLastHourSleeped(),
        asleepTime=p:getAsleepTime(),modal=false,fixture=T.sleepFixture}
    if modal and modal:isVisible() then
        r.sleep.modal={yes=center(modal.yes),no=center(modal.no),text=modal.text,
            yesEnabled=modal.yes:isEnabled(),noEnabled=modal.no:isEnabled()}
    end
    return r
end
return T.snapshot()
'''


def run_cases(h, interior, tap, wake_timeout=240):
    h.REPORT["scope"] = "single-player bed Sleep via world menu, No/Yes confirmation and natural wake"
    h.REPORT["fixtureState"] = "fatigue 0.35 (native sleep bound below eight hours), thirst zero and last-sleep time reset; native sleep advances time and saves"
    h.REPORT["unverified"] = ["multiplayer sleeping", "every bed quality or character trait", "nightmare/event variants"]
    h.lua(interior.FIXTURE)
    interior.close_dashboard(h, tap)
    h.lua(FIXTURE)
    label = h.lua('return getText("ContextMenu_Sleep")')
    point = h.lua('return MELensInteriorTest.point("bed")')
    before = interior.choose(h, tap, point, [point["header"], label], "bed-sleep-confirmation")
    modal = interior.poll(h, lambda s: s["sleep"].get("modal") and s["interior"].get("kind") == "bed",
                          timeout=35, label="native Sleep confirmation")
    h.check(not modal["sleep"]["asleep"], "Sleep began before native confirmation")
    h.check(modal["sleep"]["conservativeMaxHours"] < 8, "fixture fatigue would permit more than eight hours of native sleep")
    h.check(modal["sleep"]["modal"]["yesEnabled"] and modal["sleep"]["modal"]["noEnabled"], "sleep confirmation buttons disabled")
    h.record("context-bed-sleep-confirmation", before, modal, uiHandlersInvokedDirectly=False)
    h.capture("sleep-native-confirmation")
    no = modal["sleep"]["modal"]["no"]
    tap.native_click(h, no["x"], no["y"], "sleep:cancel-No")
    cancelled = interior.poll(h, lambda s: not s["sleep"].get("modal") and not s["sleep"]["asleep"],
                              timeout=8, label="native No cancels sleeping")
    h.check(abs(cancelled["sleep"]["fatigue"] - modal["sleep"]["fatigue"]) < .01,
            "cancelled sleep unexpectedly rested character")
    h.check(cancelled["interior"].get("kind") == "bed" and cancelled["interior"]["inside"],
            "cancel input triggered underlying scene interaction")
    h.record("native-sleep-confirmation-cancel", modal, cancelled, uiHandlersInvokedDirectly=False)

    point = h.lua('return MELensInteriorTest.point("bed")')
    before = interior.choose(h, tap, point, [point["header"], label], "bed-sleep-accept")
    modal = interior.poll(h, lambda s: s["sleep"].get("modal"), timeout=8, label="second native Sleep confirmation")
    h.check(modal["sleep"]["conservativeMaxHours"] < 8, "native sleep fatigue bound changed before acceptance")
    yes = modal["sleep"]["modal"]["yes"]
    tap.native_click(h, yes["x"], yes["y"], "sleep:accept-Yes")
    asleep = interior.poll(h, lambda s: s["sleep"]["asleep"] and not s["sleep"].get("modal"),
                           timeout=15, label="native Yes starts sleeping")
    h.check(asleep["interior"]["inside"] and asleep["interior"].get("kind") == "bed", "sleep left the installed bed")
    h.record("native-sleep-confirmation-accept", before, asleep, uiHandlersInvokedDirectly=False)
    print("WAITING_FOR_NATURAL_WAKE; no backend wake or time-setting calls", flush=True)
    woke = interior.poll(h, lambda s: not s["sleep"]["asleep"], timeout=wake_timeout, label="natural engine wake")
    h.check(woke["sleep"]["worldHours"] > asleep["sleep"]["worldHours"] + .05, "natural wake did not advance world time")
    h.check(woke["sleep"]["fatigue"] < asleep["sleep"]["fatigue"] - .01, "sleep did not reduce native fatigue")
    h.check(woke["interior"]["inside"] and woke["interior"].get("kind") == "bed", "wake lost bed occupancy")
    h.record("native-bed-sleep-natural-wake", asleep, woke, uiHandlersInvokedDirectly=False, forcedWake=False)
    interior.interact_key(h, "sleep:stand-after-wake")
    final = interior.poll(h, lambda s: interior.idle(s) and s["interior"]["inside"] and s["interior"]["standing"],
                          label="native Interact stands after sleeping")
    h.record("keyboard-stand-after-sleep", woke, final, uiHandlersInvokedDirectly=False)
    h.capture("sleep-natural-wake-standing")
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--endpoint", default=None)
    parser.add_argument("--wake-timeout", type=int, default=240)
    args = parser.parse_args()
    interior, tap, h = load_helpers()
    h.configure(args.output, args.endpoint)
    try:
        h.REPORT["final"] = run_cases(h, interior, tap, args.wake_timeout)
        print(f"NATIVE_SLEEP_TESTS_PASSED {h.write_report('passed')}", flush=True)
        return 0
    except Exception:
        error = traceback.format_exc()
        try:
            h.REPORT["lastSnapshot"] = interior.read_state(h)
        except Exception:
            h.REPORT["lastSnapshot"] = None
        print(error, flush=True)
        print(f"NATIVE_SLEEP_TESTS_FAILED {h.write_report('failed', error)}; parent-owned game left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
