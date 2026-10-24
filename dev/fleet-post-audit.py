"""Run focused follow-ups inside the same guarded owned session after all variants."""
import importlib.util
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]

def invoke(name,arguments=()):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    previous=sys.argv
    try:
        sys.argv=[str(ROOT/'dev'/(name+'.py')),*arguments]
        return module.main()
    finally:sys.argv=previous


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior',type=Path,action='append',default=[],help='Earlier audit directory with unchanged variant results')
    parser.add_argument('--retest',action='append',default=[],help='Exact script ID changed since earlier captures')
    parser.add_argument('--extra-marker',action='append',default=[],help='Additional floor/marker control vehicle')
    args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    rows={}
    for audit in [*args.prior,run/'visual-all']:
        for line in (audit/'variants.jsonl').read_text().splitlines():
            row=json.loads(line);rows[row['name']]=row
    expected={row['name'] for row in json.loads((run/'visual-all/inventory.json').read_text())}
    assert set(rows)==expected,'Complete the per-variant audit before follow-ups'
    if args.retest:
        options=['--output-name','visual-fixes']
        for name in args.retest:options.extend(['--only',name])
        result=invoke('fleet-visual-tests',options)
        if result:return result
        for line in (run/'visual-fixes/variants.jsonl').read_text().splitlines():
            row=json.loads(line);rows[row['name']]=row
    (run/'audit-combined.json').write_text(json.dumps(sorted(rows.values(),key=lambda r:r['number']),indent=2))
    for name in ('fleet-marker-checks','f700-adjacent-tests'):
        result=invoke(name)
        if result:return result
    for index,vehicle in enumerate(args.extra_marker):
        result=invoke('fleet-marker-checks',['--vehicle',vehicle,'--heading','E','--output-name',f'marker-extra-{index}'])
        if result:return result
    return 0


if __name__=='__main__':raise SystemExit(main())
