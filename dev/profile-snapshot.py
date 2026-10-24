"""Read-only runtime profile receipt for reusing captures of unchanged variants.

This records loaded profile data, not pixels, input, or gameplay acceptance.
Run inside the owned guarded game before/after a narrowly scoped profile repair.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def authored(value):
    """Exclude only Parts.links' three derived stack caches, never profile data."""
    if isinstance(value,dict):
        return {key:authored(child) for key,child in value.items() if key not in ('_linked','_under','_over')}
    if isinstance(value,list):return [authored(child) for child in value]
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare-run')
    parser.add_argument('--changed',action='append',default=[])
    args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    spec=importlib.util.spec_from_file_location('native_checks',ROOT/'dev/final-feature-tests.py')
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    h.configure(run/'profile-snapshot')
    profiles=authored(h.lua('return MELens.Profiles'))
    h.check(len(profiles)==203,'unexpected runtime profile coverage')
    (h.OUTPUT/'profiles.json').write_text(json.dumps(profiles,sort_keys=True,indent=2)+'\n')
    result={'profiles':len(profiles),'nativeInput':False}
    if args.compare_run:
        before=authored(json.loads((ROOT/'build/rv'/args.compare_run/'profile-snapshot/profiles.json').read_text()))
        h.check(set(before)==set(profiles),'supported vehicle set changed')
        changed=sorted(name for name in profiles if profiles[name]!=before[name])
        h.check(changed==sorted(args.changed),'unexpected changed runtime profiles: '+str(changed))
        result.update(comparedRun=args.compare_run,changed=changed,unchanged=len(profiles)-len(changed))
    h.REPORT['scope']=__doc__
    h.record('loaded-profile-receipt',{},result)
    print(h.write_report('passed'),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
