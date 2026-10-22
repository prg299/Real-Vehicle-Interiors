"""Cold-load the owned F700 save and verify furniture/cargo identity before fuel-input checks."""
import importlib.util
import json
import os
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'dev' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    h = load('final-feature-tests')
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    source = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_SOURCE']
    h.configure(run / 'reload-checks')
    h.SCREENS = source / 'home/Zomboid/Screenshots'
    expected = json.loads((source / 'seat-checks/report.json').read_text())['saved']
    try:
        actual = h.lua('''local v=getPlayer():getVehicle();assert(v and v:getScriptName()=="Base.87fordF700box")
MELensTest={vehicle=v,all={}};local r={vehicle=v:getId(),parts={},cargo={}}
for _,i in ipairs({21,64,82,83}) do
 local part=MELens.Parts.spotPart(v,i);local item=assert(part:getInventoryItem())
 r.parts[tostring(i)]={id=item:getID(),fullType=item:getFullType(),capacity=part:getItemContainer():getCapacity()}
 local c=part:getItemContainer();local ids={}
 for n=0,c:getItems():size()-1 do ids[#ids+1]=c:getItems():get(n):getID() end
 r.cargo[tostring(i)]=ids
end
return r''')
        h.check(actual['parts'] == expected['parts'] and actual['cargo'] == expected['cargo'],
                'cold save reload changed original furniture, cargo IDs or capacities')
        h.REPORT['saveReload'] = dict(expected=expected, actual=actual)
        h.capture('f700-cold-reloaded')
        h.lua((ROOT / 'dev/lua/feature-fixture.lua').read_text())
        h.check(load('f700-fuel-tests').main() == 0, 'cold-run fuel checks failed')
        h.REPORT['passed'] = True
        status = 0
    except Exception:
        h.REPORT.update(passed=False, error=traceback.format_exc())
        print(h.REPORT['error'], flush=True)
        status = 1
    (h.OUTPUT / 'report.json').write_text(json.dumps(h.REPORT, indent=2), encoding='utf-8')
    print('F700_COLD_RELOAD_PASSED' if status == 0 else 'F700_COLD_RELOAD_FAILED', flush=True)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
