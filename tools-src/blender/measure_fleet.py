"""Run the shared measurement tool over a prepared local body-family manifest."""
import json
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[2]
manifest = Path(sys.argv[sys.argv.index('--') + 1])
for cfg in json.loads(manifest.read_text('utf-8-sig')):
    path = root / 'build/rv/floorplans' / ('measure-config_' + cfg['key'] + '.json')
    path.write_text(json.dumps(cfg, indent=2))
    sys.argv = ['measure_vehicle.py', '--', str(path)]
    runpy.run_path(str(Path(__file__).with_name('measure_vehicle.py')), run_name='__main__')
