"""Native Transfer All input into F700 storage; view selection/positioning are fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('f700_storage_features', ROOT / 'dev/final-feature-tests.py')
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    run = ROOT / 'build/rv' / os.environ['RVI_CAPTURE_RUN']
    source = ROOT / 'build/rv' / os.environ.get('RVI_CAPTURE_SOURCE', os.environ['RVI_CAPTURE_RUN'])
    h.configure(run / 'storage-checks')
    h.SCREENS = source / 'home/Zomboid/Screenshots'
    try:
        h.lua('MELensTest={vehicle=assert(getPlayer():getVehicle())};ISUIHandler.setVisibleAllUI(true);return true')
        for index, piece in ((21, 'box'), (64, 'fridge')):
            item_id = h.lua(f'''local p,v=getPlayer(),MELensTest.vehicle
if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end
local spot=MELens.profileFor(v).spots[{index}]
local x,z=MELens.Parts.spotPoint(spot,0,MELens.RVKit.{piece}.depth+.10)
MELens.walkTo(p,x,z)
local item=p:getInventory():AddItem("Base.Sledgehammer");assert(item);return item:getID()''')
            deadline = time.monotonic() + 30
            while not h.lua(f'return not MELens.pathing(getPlayer()) and MELens.Parts.canReach(MELensTest.vehicle,MELens.Parts.spotPart(MELensTest.vehicle,{index}),getPlayer())'):
                h.check(time.monotonic() < deadline, 'storage positioning did not finish')
                time.sleep(.1)
            h.lua(f'''local p=getPlayer();local w=getPlayerInventory(0);local loot=getPlayerLoot(0)
w:setVisible(true);w:setIsCollapsed(false);w:setX(20);w:setY(50)
loot:setVisible(true);loot:setIsCollapsed(false);loot:setX(660);loot:setY(50)
loot:refreshBackpacks();loot:setNewContainer(MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer())
return true''')
            point = None
            deadline = time.monotonic() + 10
            while not point:
                point = h.lua('''local seen={};local label=getText("IGUI_invpage_Transfer_all")
local function find(w)
 if not w or seen[w] then return end;seen[w]=true
 if w.title==label and w:isVisible() then return {x=w:getAbsoluteX()+w:getWidth()/2,y=w:getAbsoluteY()+w:getHeight()/2} end
 for _,c in pairs(w.children or {}) do local p=find(c);if p then return p end end
end
return find(getPlayerInventory(0))''')
                h.check(time.monotonic() < deadline, 'native Transfer All button was not visible')
                time.sleep(.1)
            h.lua(f'MEMCNativeLab.clickAt({int(point["x"])},{int(point["y"])});return true')
            h.REPORT.setdefault('inputs', []).append(dict(action='transfer-to-' + piece, api='MEMCNativeLab.clickAt', **point))
            h.REPORT['nativeInput'] = True
            deadline = time.monotonic() + 40
            while not h.lua(f'''local c=MELens.Parts.spotPart(MELensTest.vehicle,{index}):getItemContainer()
return c:getItemById({int(item_id)})~=nil and getPlayer():getInventory():getItemById({int(item_id)})==nil'''):
                h.check(time.monotonic() < deadline, 'native storage transfer did not commit')
                time.sleep(.15)
            h.REPORT.setdefault('transfers', []).append(dict(piece=piece, itemId=item_id, fullType='Base.Sledgehammer', index=index))
            h.capture('f700-native-transfer-' + piece)
        h.REPORT['passed'] = True
        status = 0
    except Exception:
        h.REPORT.update(passed=False, error=traceback.format_exc())
        print(h.REPORT['error'], flush=True)
        status = 1
    (h.OUTPUT / 'report.json').write_text(json.dumps(h.REPORT, indent=2), encoding='utf-8')
    print('F700_STORAGE_NATIVE_PASSED' if status == 0 else 'F700_STORAGE_NATIVE_FAILED', flush=True)
    return status


if __name__ == '__main__':
    raise SystemExit(main())
