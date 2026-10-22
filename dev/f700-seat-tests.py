"""Native rest/use and save of the furnished F700, in its parent-owned session."""
import importlib.util
import json
import os
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('f700_interiors', ROOT / 'dev/final-interior-tests.py')
    interior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(interior)
    tap, h = interior.load_helpers()
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    h.configure(run / 'seat-checks')
    h.SCREENS = run / 'home/Zomboid/Screenshots'
    try:
        interior.close_dashboard(h, tap)
        h.lua('''local old=MELensInteriorTest.snapshot
function MELensInteriorTest.snapshot()
 local r=old();local b=MELens.Bed.states[getPlayer()];r.bedPhase=b and b.phase;return r
end
return true''')
        rest = h.lua('return getText("ContextMenu_Rest")')
        for piece in ('bed', 'dinette'):
            point = h.lua('return MELensInteriorTest.point("' + piece + '")')
            before = interior.choose(h, tap, point, [point['header'], rest], 'f700-' + piece + '-rest')
            after = interior.poll(h, lambda s: interior.idle(s) and not s['interior']['standing']
                                  and (s.get('bedPhase') == 'Awake' if piece == 'bed' else s['interior'].get('kind') == 'seat'),
                                  label='F700 ' + piece + ' resting')
            h.record('f700-native-' + piece + '-rest', before, after)
            h.capture('f700-' + piece + '-rest')
            interior.interact_key(h, 'stand-from-' + piece)
            interior.poll(h, lambda s: interior.idle(s) and s['interior']['standing'], label='standing after ' + piece)
        saved = h.lua('''local p,v=getPlayer(),MELensTest.vehicle
local r={vehicle=v:getId(),parts={},cargo={}}
for _,i in ipairs({21,64,82,83}) do
 local part=MELens.Parts.spotPart(v,i);local item=part:getInventoryItem()
 r.parts[tostring(i)]={id=item:getID(),fullType=item:getFullType(),capacity=part:getItemContainer():getCapacity()}
 local c=part:getItemContainer();local ids={}
 for n=0,c:getItems():size()-1 do ids[#ids+1]=c:getItems():get(n):getID() end
 r.cargo[tostring(i)]=ids
end
saveGame();return r''')
        h.REPORT.update(passed=True, saved=saved)
        status = 0
    except Exception:
        h.REPORT.update(passed=False, error=traceback.format_exc())
        print(h.REPORT['error'], flush=True)
        status = 1
    (h.OUTPUT / 'report.json').write_text(json.dumps(h.REPORT, indent=2), encoding='utf-8')
    print('F700_SEATS_SAVE_PASSED' if status == 0 else 'F700_SEATS_SAVE_FAILED', flush=True)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
