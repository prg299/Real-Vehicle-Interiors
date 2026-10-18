"""Run the release MP drivers sequentially inside the parent's guarded job.

Import performs no game calls or process launches. The MP parent owns the server
and both clients. Each step invokes the shared guard without changing its
environment or limits; only the step's own child tree is stopped on a timeout.
Use a fresh --output inside --session for every attempt. To start at camper,
provide the completed interior driver's --f700-report. Later starts require a
--prior-suite containing passed reports for every skipped step.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
GUARD = Path(os.environ.get("RVI_RESOURCE_GUARD", str(Path.home() / ".codex/tools/run-heavy.mjs")))
STEPS = ("interiors", "camper", "loot", "loot-floor", "features", "water",
         "furniture", "personalization", "food", "bus", "persistence")
SCRIPTS = {
    "interiors": "final-mp-interior-tests.py", "camper": "final-mp-camper-setup.py",
    "loot": "final-mp-loot-ui-tests.py", "loot-floor": "final-mp-loot-ui-tests.py",
    "features": "final-mp-features.py", "water": "final-mp-water-tests.py",
    "furniture": "final-mp-furniture-tests.py", "personalization": "final-mp-personalization.py",
    "food": "final-food-tests.py", "bus": "final-mp-bus-tests.py",
    "persistence": "final-mp-persistence.py",
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def owned_path(path, boundary):
    path, boundary = Path(path).resolve(), Path(boundary).resolve()
    require(path != boundary and path.is_relative_to(boundary), f"Path must remain inside {boundary}: {path}")
    return path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_report(step, path):
    report = read_json(path)
    require(report.get("status") == "passed" and not report.get("error"), f"{step}: report did not pass: {path}")
    require(report.get("finishedAt") or report.get("finishedUtc"), f"{step}: report has no completion timestamp")
    if step != "food":
        require(isinstance(report.get("cases"), list) and report["cases"], f"{step}: no completed cases")
        require(isinstance(report.get("final"), dict) and report["final"] if step != "persistence" else report.get("baseline"),
                f"{step}: terminal evidence is missing")
    if step in ("interiors", "bus"):
        vehicle = report["final"]["server"]["vehicle"]
        require(isinstance(vehicle["id"], int) and not isinstance(vehicle["id"], bool), f"{step}: missing vehicle ID")
    if step == "features":
        actor = report["fixture"]["actor"]
        require(actor["script"] == "Base.Trailer54FlyingCloud22", "Features report is not the tested Flying Cloud 22")
        require(isinstance(actor["vehicleId"], int) and not isinstance(actor["vehicleId"], bool), "Features report lacks camper ID")
    if step == "food":
        require(report.get("foodCooking", {}).get("passed") is True, "Food component did not pass")
    if step == "persistence":
        baseline = read_json(report["baseline"])
        require(set(baseline["states"]["server"]["vehicles"]) == {"f700", "camper", "bus"}, "Persistence baseline is incomplete")
    return report


def report_record(step, path, session, expected_hash=None):
    path = owned_path(path, session)
    digest = sha256(path)
    require(expected_hash is None or digest == expected_hash, f"{step}: prior report changed since it was recorded")
    report = validate_report(step, path)
    return {"step": step, "path": str(path), "sha256": digest, "status": "passed",
            "nativeInput": report.get("nativeInput"), "sourceScope": report.get("scope")}


def prior_reports(args, session):
    reports = {}
    if args.prior_suite:
        source = owned_path(args.prior_suite, session)
        if source.is_dir():
            source /= "liveprogress.json"
        prior = read_json(source)
        require(Path(prior["session"]).resolve() == session, "Prior suite belongs to a different native session")
        for step, record in prior.get("reports", {}).items():
            if step in STEPS and record.get("status") == "passed":
                reports[step] = report_record(step, record["path"], session, record["sha256"])
    for step, value in (("interiors", args.f700_report), ("camper", args.camper_setup_report),
                        ("features", args.camper_report), ("bus", args.bus_report)):
        if value:
            reports[step] = report_record(step, value, session)
    skipped = STEPS[:STEPS.index(args.start_at)]
    for step in skipped:
        require(step in reports, f"Starting at {args.start_at} requires a passed {step} report; use --prior-suite or its explicit report option")
    return {step: reports[step] for step in skipped}


def step_arguments(step, session, output, screens_a, reports):
    common = ["--session", str(session), "--output", str(output)]
    if step == "loot-floor":
        return common + ["--part", "MELensFloor"]
    if step == "features":
        return ["--output", str(output), "--screens-a", str(screens_a), "--lamp-seconds", "30"]
    if step == "food":
        camper = validate_report("features", reports["features"]["path"])["fixture"]["actor"]["vehicleId"]
        return ["--output", str(output), "--server", "--vehicle-id", str(camper)]
    if step == "bus":
        return common + ["--drive"]
    if step == "persistence":
        return ["capture"] + common + ["--quiesce-fixture", "--f700-report", reports["interiors"]["path"],
                                      "--camper-report", reports["features"]["path"], "--bus-report", reports["bus"]["path"]]
    return common


def creation_ticks(process):
    """Get .NET UTC creation ticks from the pinned Windows Popen handle."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    fields = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(int(process._handle), *(ctypes.byref(field) for field in fields)):
        raise ctypes.WinError(ctypes.get_last_error())
    value = (fields[0].dwHighDateTime << 32) | fields[0].dwLowDateTime
    return value + 504911232000000000


def stop_owned_tree(process, ticks, node):
    if process.poll() is not None:
        return {"alreadyExited": True}
    require(os.name == "nt" and ticks is not None, "Native suite cleanup requires the owned Windows process handle")
    # .NET pins the exact process before comparing creation time and Kill(true).
    # The target is one step's nested guard, never the parent or native games.
    code = (f"$ErrorActionPreference='Stop'; $owned=$null; try {{ "
            f"$owned=[Diagnostics.Process]::GetProcessById({int(process.pid)}); "
            "$owned.EnableRaisingEvents=$true; [void]$owned.Handle; "
            f"if($owned.StartTime.ToUniversalTime().Ticks -ne {int(ticks)}){{throw 'Owned step identity changed'}}; "
            "if(-not $owned.HasExited){$owned.Kill($true); [void]$owned.WaitForExit(5000)} "
            "} catch [ArgumentException] {} finally {if($owned){$owned.Dispose()}}")
    result = subprocess.run([node, str(GUARD), "--", "pwsh", "-NoProfile", "-NonInteractive", "-Command", code],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=12)
    require(result.returncode == 0, f"Owned step cleanup failed: {result.stdout}")
    process.wait(timeout=5)
    return {"ownedTreeStopped": True, "identityCreationTicks": ticks, "cleanupExitCode": result.returncode,
            "cleanupLog": result.stdout}


def completed_report(step, output):
    if step == "persistence":
        matches = list(output.glob("capture-*.json"))
        require(len(matches) == 1, "Persistence step did not write exactly one final capture report")
        return matches[0]
    return output / "native-feature-tests.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start-at", choices=STEPS, default="interiors")
    parser.add_argument("--prior-suite", type=Path)
    parser.add_argument("--f700-report", type=Path)
    parser.add_argument("--camper-setup-report", type=Path)
    parser.add_argument("--camper-report", type=Path, help="Completed Dashboard/features report; contains fixture.actor.vehicleId")
    parser.add_argument("--bus-report", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1700, help="Whole suite deadline; set parent dispatcher timeout to 1800")
    parser.add_argument("--step-timeout-seconds", type=int, default=600)
    args = parser.parse_args(argv)
    progress = None
    process = None
    ticks = None
    node = None
    try:
        require(os.name == "nt", "MP native suite is Windows-only")
        require(30 <= args.timeout_seconds <= 3500, "Suite timeout must be 30..3500 seconds and shorter than parent review")
        require(10 <= args.step_timeout_seconds <= 1200, "Step timeout must be 10..1200 seconds")
        session = owned_path(args.session, ROOT / "build/rv")
        metadata = read_json(session / "session.json")
        require(metadata.get("serverNoJava") and metadata.get("stockClientClasses") and metadata.get("inactiveDesktops"), "Wrong MP session harness")
        require(metadata.get("status") == "review-ready" and not metadata.get("finishedUtc"), "MP parent is not in a live bounded review")
        clients = {record["name"]: record for record in metadata["clients"]}
        require(clients["client-a"]["port"] == 18470 and clients["client-b"]["port"] == 18472, "Unexpected native endpoint ports")
        screens_a = owned_path(Path(clients["client-a"]["cache"]) / "Screenshots", session)
        output = owned_path(args.output, session)
        require(not output.exists(), "Suite output already exists; use a new directory to preserve prior reports")
        reports = prior_reports(args, session)
        node = shutil.which("node")
        require(node and GUARD.is_file(), "Node/shared resource guard is unavailable")
        output.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        deadline = started + args.timeout_seconds
        progress = {"schema": 1, "session": str(session), "output": str(output), "startedUtc": utc(),
                    "status": "running", "startAt": args.start_at, "guard": str(GUARD),
                    "inheritedGuardEnvironmentUnchanged": True, "parentOwnsNativeLifetimes": True,
                    "timeoutSeconds": args.timeout_seconds, "stepTimeoutSeconds": args.step_timeout_seconds,
                    "reusedSteps": list(reports), "executedSteps": [], "reports": reports, "steps": [],
                    "scope": "Sequential existing drivers; native-input and component-only evidence remain separate in each report"}
        write_json(output / "liveprogress.json", progress)
        for index, step in enumerate(STEPS):
            if index < STEPS.index(args.start_at):
                continue
            require(time.monotonic() < deadline, "Whole suite deadline reached before next step")
            step_root = output / f"{index+1:02d}-{step}"
            step_root.mkdir()
            step_output = step_root / "output"
            arguments = step_arguments(step, session, step_output, screens_a, reports)
            script = ROOT / "dev" / SCRIPTS[step]
            require(script.is_file(), f"Missing driver: {script}")
            command = [node, str(GUARD), "--", sys.executable, str(script)] + arguments
            row = {"step": step, "script": str(script), "args": arguments, "status": "running", "startedUtc": utc(),
                   "stdout": str(step_root / "stdout.log"), "stderr": str(step_root / "stderr.log"),
                   "receipt": str(step_root / "receipt.json"), "output": str(step_output), "guarded": True}
            progress["steps"].append(row)
            progress["activeStep"] = step
            write_json(row["receipt"], row)
            write_json(output / "liveprogress.json", progress)
            print(f"MP_SUITE_STEP_STARTED {step}", flush=True)
            with open(row["stdout"], "w", encoding="utf-8") as stdout, open(row["stderr"], "w", encoding="utf-8") as stderr:
                process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
                ticks = creation_ticks(process)
                row.update(pid=process.pid, creationTicks=ticks)
                write_json(row["receipt"], row)
                step_deadline = min(deadline, time.monotonic() + args.step_timeout_seconds)
                heartbeat = 0.0
                while process.poll() is None:
                    now = time.monotonic()
                    if now >= step_deadline:
                        row["cleanup"] = stop_owned_tree(process, ticks, node)
                        row["status"] = "timed-out"
                        break
                    if now >= heartbeat:
                        progress.update(updatedUtc=utc(), elapsedSeconds=round(now-started, 2))
                        write_json(output / "liveprogress.json", progress)
                        heartbeat = now + 1
                    time.sleep(.2)
                row["exitCode"] = process.wait(timeout=5)
                process = None
            row["finishedUtc"] = utc()
            if row.get("status") == "timed-out" or row["exitCode"] != 0:
                row["status"] = row["status"] if row["status"] == "timed-out" else "failed"
                write_json(row["receipt"], row)
                raise AssertionError(f"{step} stopped with status={row['status']} exit={row['exitCode']}; remaining steps were not started")
            try:
                path = completed_report(step, step_output)
                reports[step] = report_record(step, path, session)
            except Exception:
                row["status"] = "invalid-or-incomplete-report"
                write_json(row["receipt"], row)
                raise
            row.update(status="passed", report=reports[step])
            progress["executedSteps"].append(step)
            write_json(row["receipt"], row)
            write_json(output / "liveprogress.json", progress)
            print(f"MP_SUITE_STEP_PASSED {step} {path}", flush=True)
        require(set(reports) == set(STEPS), "The suite lacks a passed report for a required step")
        progress.update(status="passed", activeStep=None, finishedUtc=utc(), allRequiredStepReportsPassed=True)
        write_json(output / "liveprogress.json", progress)
        write_json(output / "suite-report.json", progress)
        print(f"NATIVE_MP_RELEASE_SUITE_PASSED {output/'suite-report.json'}", flush=True)
        return 0
    except BaseException:
        error = traceback.format_exc()
        if process is not None:
            try:
                cleanup = stop_owned_tree(process, ticks, node)
                if progress and progress["steps"]:
                    progress["steps"][-1]["cleanup"] = cleanup
            except Exception:
                error += "\nOwned step cleanup error:\n" + traceback.format_exc()
        if progress is not None:
            if progress["steps"] and progress["steps"][-1].get("status") == "running":
                row = progress["steps"][-1]
                row.update(status="failed", finishedUtc=utc(), error=error)
                if process is not None:
                    row["exitCode"] = process.poll()
                write_json(row["receipt"], row)
            progress.update(status="failed", error=error, finishedUtc=utc(), allRequiredStepReportsPassed=False)
            write_json(Path(progress["output"]) / "liveprogress.json", progress)
            write_json(Path(progress["output"]) / "suite-report.json", progress)
        print(error, file=sys.stderr, flush=True)
        print("NATIVE_MP_RELEASE_SUITE_FAILED; parent-owned server/clients left running", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
