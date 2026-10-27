"""Verify existing SQL vehicles in a copied private save.

The parent owns the complete guarded native lifetime.
This driver never launches PZ or creates, repairs, seeds or removes game state.
It commits the copied world after verification; this is not Save-menu input proof.
Entry/exit use existing native Interact; relocation is a streaming fixture.
The old-package baseline must precede the candidate's FIRST load of this copy.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--case', required=True, type=Path)
    p.add_argument('--mode', required=True, choices=('baseline', 'verify'))
    p.add_argument('--baseline', required=True, type=Path)
    p.add_argument('--package-receipt', required=True, type=Path)
    p.add_argument('--allow-artifact-root', type=Path, action='append', default=[],
                   help='Explicit task artifact directory in another checkout; never a save directory')
    p.add_argument('--output-name', default='upgrade-preservation')
    a = p.parse_args()
    root = a.root.resolve()
    outroot = (root/'build/rv').resolve()
    run = (outroot/os.environ['RVI_CAPTURE_RUN']).resolve()
    assert run.is_relative_to(outroot) and run != outroot
    assert Path(a.output_name).name == a.output_name
    artifact_roots = [outroot]
    for directory in a.allow_artifact_root:
        directory = directory.resolve()
        assert directory.name == 'update-prep-20261027-2.0.21'
        assert directory.parent.name == 'rv' and directory.parent.parent.name == 'build'
        artifact_roots.append(directory)
    for path in (a.baseline, a.case, a.package_receipt):
        assert path.suffix == '.json' and any(path.resolve().is_relative_to(d) for d in artifact_roots)
    case = json.loads(a.case.read_text('utf-8-sig'))
    assert case['copyOnly'] is True and case['sourceVersion'] in ('2.0.13', '2.0.14', '2.0.20')
    world = case['world']
    assert world.startswith('melens-test-') and world.removeprefix('melens-test-').isdigit()
    assert case['vehicles'] and len(case['vehicles']) <= 6
    receipt = json.loads(a.package_receipt.read_text('utf-8-sig'))
    assert receipt['version'] == (case['sourceVersion'] if a.mode == 'baseline' else case['candidateVersion'])
    assert len(receipt['packageSha256']) == 64

    def load(name):
        spec = importlib.util.spec_from_file_location(name.replace('-', '_'), root/'dev'/(name+'.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    h = load('final-feature-tests')
    h.configure(run/a.output_name)
    h.ENDPOINT = 'http://127.0.0.1:18470/lua?depth=16&sandbox=false'
    h.ENDPOINT = h.ENDPOINT.replace('depth=8', 'depth=14')
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(v.split('=', 1)[1] for v in session['command'] if v.startswith('-cachedir=')))/'Screenshots'
    protection = load('vehicle-preservation')
    legacy = load('interior-lifecycle-tests').SNAPSHOT
    # Reuse the production preservation projection, then add missing upgrade
    # contracts: part order, nested item types/IDs, loose positions and propane.
    snapshot = '''local preserved=(function()\n''' + legacy + '''\nend)()
local v=MELensLifecycle.vehicle;local order,trees={},{ }
local function tree(item)
 if not item then return nil end
 local fluid=item:getFluidContainer()
 local r={id=item:getID(),type=item:getFullType(),fluid=fluid and fluid:getAmount() or false,
          uses=instanceof(item,"DrainableComboItem") and item:getCurrentUsesFloat() or false}
 if instanceof(item,"InventoryContainer") then
  r.children={};local inv=item:getInventory()
  for j=0,inv:getItems():size()-1 do r.children[#r.children+1]=tree(inv:getItems():get(j)) end
  table.sort(r.children,function(a,b)return a.id<b.id end)
 end
 return r
end
for i=0,v:getPartCount()-1 do
 local part=v:getPartByIndex(i);local id=part:getId();order[#order+1]=id
 local r={installed=tree(part:getInventoryItem()),contents={}};local c=part:getItemContainer()
 if c then for j=0,c:getItems():size()-1 do r.contents[#r.contents+1]=tree(c:getItems():get(j)) end end
 table.sort(r.contents,function(a,b)return a.id<b.id end);trees[id]=r
 -- Seat-container capacity depends on its temporary bound owner while inside.
 -- Keep its items/IDs, but compare persistent RVI storage capacities only.
 if id:find("^Seat") then preserved.parts[id].capacity=nil end
end
local floor=v:getPartById("MELensFloor");local data=floor and floor:getModData() or {}
preserved.partOrder=order;preserved.itemTrees=trees
preserved.loose=data.loose;preserved.tumbles=data.tumbles
preserved.propane=v:getModData().MELensPropane
return preserved'''
    snapshot = snapshot.replace('MELensLifecycle.vehicle', 'MELensPreservationFixture.vehicle')

    def wait(code, timeout=40):
        deadline = time.monotonic()+timeout
        while not h.lua(code):
            h.check(time.monotonic()<deadline, 'bounded wait failed: '+code)
            time.sleep(.15)

    def locate(v):
        sql, script = v['sqlId'], v['script']
        assert isinstance(sql, int) and sql > 0
        lookup = '''local found;local it=getCell():getVehicles():iterator()
while it:hasNext() do local v=it:next();if v:getSqlId()==SQL then
assert(v:getScriptName()==SCRIPT,'SQL/script mismatch');found=v;break end end
MELensPreservationFixture={vehicle=found};return found~=nil'''.replace('SQL',str(sql)).replace('SCRIPT',json.dumps(script))
        if not h.lua(lookup):
            pos = v['position']
            h.check(not h.lua('return getPlayer():getVehicle()~=nil'), 'unloaded fixture requires outside player')
            h.lua('local p=getPlayer();MELensMedia.cameraOff();p:setX('+str(pos['x']+4)+');p:setY('+str(pos['y'])+');p:setZ('+str(pos['z'])+');p:setLastX(p:getX());p:setLastY(p:getY());return true')
            wait(lookup)

    def exit_input():
        h.lua('''local p=getPlayer();local v=assert(p:getVehicle());assert(MELens.isStanding(p))
local marker=assert(MELens.profileFor(v).exitMarker);MELens.walkTo(p,marker.x,marker.z);return true''')
        wait('return not MELens.pathing(getPlayer()) and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0')
        key = int(h.lua('return getCore():getKey("Interact")'))
        h.lua(f'MEMCNativeLab.holdKey({key},200);return true')
        h.REPORT['inputs'].append({'action':'exit existing saved interior','api':'holdKey','key':key})
        wait('return getPlayer():getVehicle()==nil')

    try:
        h.REPORT.update(scope=__doc__,mode=a.mode,sourceVersion=case['sourceVersion'],
                        packageReceipt=str(a.package_receipt),caseSha256=hashlib.sha256(a.case.read_bytes()).hexdigest(),
                        unverified=['Save/Continue menu input','multiplayer authority','performance'])
        h.check(h.lua('return getWorld():getWorld()') == world, 'Wrong copied private world')
        h.check(h.lua('return MELensRV.version()') == receipt['version'], 'Loaded Java does not match staged release')
        expected = None
        if a.mode == 'verify':
            expected = json.loads(a.baseline.read_text('utf-8-sig'))
            h.check(expected['status']=='passed' and expected['world']==world, 'Baseline/world mismatch')
            h.check(expected['sourceVersion']==case['sourceVersion'], 'Baseline origin mismatch')
            h.check(set(expected['vehicles'])=={str(v['sqlId']) for v in case['vehicles']}, 'Baseline vehicle set mismatch')
        else:
            h.check(not a.baseline.exists(), 'Never overwrite an old-package baseline')
        before = {}
        for vehicle in case['vehicles']:
            locate(vehicle)
            sql = str(vehicle['sqlId'])
            if expected:
                before[sql] = protection.verify(h, expected['vehicles'][sql], vehicle['position'], snapshot)
                # Shared verifier releases its temporary selector in finally.
                locate(vehicle)
            else:
                before[sql] = h.lua(snapshot)
            h.REPORT.setdefault('inspectionBefore', {})[sql] = before[sql]
            if a.mode=='verify' and vehicle['script']=='Base.90fordF350ambulance':
                presentation=h.lua('''local v=MELensPreservationFixture.vehicle;local L=MELens.Loose
local raw=v:getPartById("MELensFloor"):getModData().loose;local out={}
for id,e in pairs(raw or {}) do if e.s==7 or e.s==8 then
 local a,b=L.entry(v,tonumber(id)),L.entry(v,tonumber(id))
 assert(math.abs(a.z-(e.z-.06))<.000001 and b.z==a.z and a.s==e.s and a.x==e.x)
 local shown;for _,it in ipairs(L.list(v,MELens.profileFor(v))) do if tostring(it.id)==id then shown=it end end
 assert(shown and math.abs(shown.z-a.z)<.000001,"Shelf draw list does not follow cabinet")
 out[#out+1]={id=id,rawZ=e.z,displayZ=a.z,slot=e.s}
end end
assert(#out>0,"Prepared old shelf edge item absent");return out''')
                h.REPORT.setdefault('shelfProjection',{})[sql]=presentation
            for name in vehicle.get('clearedParts', []):
                h.check('item' not in before[sql]['parts'][name], 'Formerly cleared furniture slot was refurnished')
            if case.get('requireNonzeroUtilities', False):
                gen=before[sql]['parts']['MELensGenerator']['data']
                water=before[sql]['parts']['MELensWaterTank']['data']
                h.check(gen.get('fuel',0)>0 and water.get('water',0)>0, 'Fixture lacks nonzero saved utilities')
                h.check(gen.get('on') is False, 'Exact conservation requires old baseline generator off; do not rewrite it here')
            h.lua('MELensTest={vehicle=MELensPreservationFixture.vehicle,all={}};return true')
            if h.lua('return getPlayer():getVehicle()~=nil'):
                h.check(h.lua('return getPlayer():getVehicle()==MELensTest.vehicle'), 'Player is in unrelated saved vehicle')
                exit_input()
            load('bed-tests').enter_existing(h,vehicle['script'])
            h.REPORT['inputs'].append({'action':'enter existing saved interior','api':'bed-tests.enter_existing -> native holdKey Interact','sqlId':vehicle['sqlId']})
            h.check(h.lua('return getPlayer():getVehicle():getSqlId()')==vehicle['sqlId'], 'Native entry selected different SQL vehicle')
            exit_input()
            load('bed-tests').enter_existing(h,vehicle['script'])
            h.REPORT['inputs'].append({'action':'re-enter same saved interior','api':'bed-tests.enter_existing -> native holdKey Interact','sqlId':vehicle['sqlId']})
            after_input = h.lua(snapshot)
            h.REPORT.setdefault('inspectionAfterInput', {})[sql] = after_input
            h.check(after_input==before[sql], 'Native re-entry changed saved state')
            h.REPORT['nativeInput']=True
            h.capture('sql-'+sql+'-existing-interior-reentered')
            exit_input()
        h.REPORT.update(world=world,vehicles=before,allExact=True)
        h.lua('saveGame(); return true')
        h.REPORT['copiedWorldSaveRequested'] = True
        h.write_report('passed')
        if a.mode=='baseline':
            a.baseline.write_text(json.dumps(dict(status='passed',world=world,sourceVersion=case['sourceVersion'],
                packageReceipt=receipt,vehicles=before),indent=2)+'\n',encoding='utf-8')
        return 0
    except Exception:
        h.write_report('failed',traceback.format_exc())
        return 1
    finally:
        try:h.lua('MEMCNativeLab.releaseKeys();MELensPreservationFixture=nil;return true')
        except Exception:pass


if __name__=='__main__':
    raise SystemExit(main())
