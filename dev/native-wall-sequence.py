"""Run a finite, predeclared wall-review sequence inside one guarded lifetime."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from runpy import run_path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]


def await_review(run, filename, seconds=90):
    """Bounded offline-image gate; never extends the guarded native deadline."""
    assert Path(filename).name == filename and filename.endswith('.json')
    gate = run/filename
    until = time.monotonic()+seconds
    while not gate.exists() and time.monotonic()<until and not (run/'stop-capture.json').exists():
        time.sleep(.25)
    return gate.is_file() and json.loads(gate.read_text()).get('status') == 'accepted'


def phase_identity(process, name):
    # Reuse the pinned-handle identity reader already used by the release suite.
    # That module is import-safe: no game calls or launches at import time.
    ticks = run_path(str(ROOT/'dev/final-mp-release-suite.py'))['creation_ticks'](process)
    assert ticks is not None, 'Native phases require an exact Windows process identity'
    seconds, fraction = divmod(ticks - 621355968000000000, 10000000)
    created = datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    return dict(pid=process.pid, parentPid=os.getpid(), phase=name,
                creationUtcTicks=str(ticks), createdUtc=f'{created}.{fraction:07d}Z')


def main():
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    assert run.parent == ROOT/'build/rv' and run.name.startswith('ki5-walls-20261024-')
    plan = json.loads((run/'sequence.json').read_text('utf-8-sig'))
    assert isinstance(plan, list) and 1 <= len(plan) <= 8
    report = dict(scope='Finite renderer fixtures; visual review and full fleet acceptance remain separate', phases=[])
    code = 0
    deadline = json.loads((run/'whole-lifetime-deadline.json').read_text('utf-8-sig'))
    admitted = datetime.fromisoformat(deadline['admittedUtc'].replace('Z', '+00:00'))
    shutdown = threading.Event()
    def stop_at_deadline():
        remaining = 8 * 60 - (datetime.now(timezone.utc) - admitted).total_seconds()
        if not shutdown.wait(max(0, remaining)):
            receipt = dict(reason='Eight-minute capture cutoff within twelve-minute owned lifetime',
                           requestedAt=datetime.now(timezone.utc).isoformat())
            (run/'stop-capture.json').write_text(json.dumps(receipt)+'\n')
            (run/'automatic-cutoff.json').write_text(json.dumps(receipt)+'\n')
    watchdog = threading.Thread(target=stop_at_deadline, daemon=True)
    watchdog.start()
    try:
        for phase in plan:
            if (run/'stop-capture.json').exists():
                report['status'] = 'stopped'
                break
            name, args = phase['name'], phase['arguments']
            assert name and Path(name).name == name and isinstance(args, list) and all(isinstance(a, str) for a in args)
            assert '--output-name' not in args and '--keep-open' not in args
            driver = phase.get('driver', 'native-body-tests.py')
            assert driver in ('native-body-tests.py', 'native-preserved-state-tests.py'), 'Unsupported sequence driver'
            print('WALL_PHASE_START '+name, flush=True)
            entry = dict(name=name, driver=driver, exitCode=None)
            report['phases'].append(entry)
            with subprocess.Popen([sys.executable, str(ROOT/'dev'/driver),
                    '--output-name', name, '--keep-open', *args], cwd=ROOT) as process:
                entry['identity'] = phase_identity(process, name)
                # Persist before waiting, including phases too short for a poll.
                (run/'sequence-result.json').write_text(json.dumps(report, indent=2)+'\n')
                entry['exitCode'] = process.wait()
            (run/'sequence-result.json').write_text(json.dumps(report, indent=2)+'\n')
            if entry['exitCode']:
                code = entry['exitCode']
                report['status'] = 'failed'
                break
            phase_report = run/name/'native-feature-tests.json'
            if phase_report.exists() and json.loads(phase_report.read_text()).get('status') == 'stopped':
                report['status'] = 'stopped'
                break
            print('WALL_PHASE_DONE '+name, flush=True)
            if phase.get('reviewGate'):
                print('WALL_REVIEW_GATE '+phase['reviewGate'],flush=True)
                if not await_review(run,phase['reviewGate']):
                    report['status']='stopped'
                    entry['visualReview']='not accepted within bounded review gate'
                    break
                entry['visualReview']='accepted for scoped expansion'
        else:
            report['status'] = 'passed'
        return code
    finally:
        shutdown.set()
        watchdog.join(timeout=1)
        (run/'sequence-result.json').write_text(json.dumps(report, indent=2)+'\n')
        (run/'request.json').write_text('{"action":"stop"}')


if __name__ == '__main__':
    raise SystemExit(main())
