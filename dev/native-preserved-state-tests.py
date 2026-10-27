"""Verify original AK fixture contents in its closed/reloaded private world.

No spawns, repairs, removals or item replacement. Relocation is a streaming
fixture; this does not prove a player menu/input workflow.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import traceback

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-name',required=True)
    parser.add_argument('--keep-open',action='store_true')
    parser.add_argument('--source-report',type=Path,required=True)
    parser.add_argument('--locations',type=Path,required=True)
    parser.add_argument('--world',required=True)
    args=parser.parse_args()
    assert Path(args.output_name).name==args.output_name
    source=args.source_report.resolve()
    assert source.is_relative_to(ROOT/'build/rv'), 'Only task-owned source reports'
    assert args.locations.resolve().is_relative_to(ROOT/'build/rv'), 'Only task-owned locations'
    assert args.world.startswith('melens-test-') and args.world.removeprefix('melens-test-').isdigit(), 'Only private test worlds'
    original=json.loads(source.read_text())
    assert original.get('world',args.world)==args.world, 'Source report belongs to another world'
    locations=json.loads(args.locations.read_text())
    assert original['status']=='failed' and 'preserved vehicle vanished' in original['error']
    assert original['preservedBefore'], 'No original state to verify'
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h=load('final-feature-tests');h.configure(run/args.output_name)
    h.REPORT.update(scope=__doc__,sourceReport=str(source),world=args.world,nativeInput=False,
        fixtures=['Relocation to saved vehicle location; exact SQL/script lookup'],
        unverified=['mechanics-menu input','visual/fleet acceptance','multiplayer','performance'])
    try:
        h.check(h.lua('return getWorld():getWorld()')==args.world,'Wrong private world loaded')
        h.check(not h.lua('return getPlayer():getVehicle()~=nil'),'Start preservation verification outside')
        snapshot=load('interior-lifecycle-tests').SNAPSHOT
        protection=load('vehicle-preservation')
        after={sql:protection.verify(h,expected,locations.get(sql),snapshot)
               for sql,expected in original['preservedBefore'].items()}
        h.check(after==original['preservedBefore'],'Original AK state differs after cold reload')
        h.REPORT['preservedAfterIdentical']=True
        h.write_report('passed')
        return 0
    except Exception:
        h.write_report('failed',traceback.format_exc());raise
    finally:
        if not args.keep_open:(run/'request.json').write_text('{"action":"stop"}')

if __name__=='__main__':raise SystemExit(main())
