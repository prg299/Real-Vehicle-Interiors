"""Bounded native performance probes; fixture setup is separate from native Interact entry.

Run as a workshop-capture driver inside the performance test admission guard.
Frame timing and component CPU time are distinct metrics. The dense rack fixture
uses real native InventoryItems/VehicleParts and the production Kahlua/render paths.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline-ref', help='Existing Git revision for the released shelf control')
    parser.add_argument('--animal-types', default='hen', help='Native registered animal definitions, comma separated')
    args=parser.parse_args()
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    interior, bed = load('final-interior-tests'), load('bed-tests')
    _, h = interior.load_helpers()
    h.configure(run/'performance-checks')
    h.SCREENS = run/'home/Zomboid/Screenshots'
    report = {'scope': __doc__, 'frames': {}, 'components': {}}
    target = run/'performance.json'

    def save():
        target.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def frames(label, seconds=12):
        h.lua('MEMCNativeLab.measure(100000);return true')
        time.sleep(seconds)
        row = json.loads(h.lua('return MEMCNativeLab.measurement()'))
        report['frames'][label] = row
        save()
        print(label, row, flush=True)

    try:
        report['mods'] = h.lua('local r={};local a=getActivatedMods();for i=0,a:size()-1 do r[#r+1]=a:get(i) end;return r')
        report['version'] = h.lua('return MELens.VERSION')
        package=run/'home/Zomboid/mods/RealVehicleInteriors'
        report['payloadHashes']={str(path.relative_to(package)):hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(package.rglob('*')) if path.is_file()}
        time.sleep(8)
        frames('outside')
        bed.enter(h, 'Base.StepVan', 'E')
        # Replace only the owned disposable van's fitout. Do not modify authored
        # profiles, container authority, saved IDs, or another user's world.
        report['fixture'] = h.lua('''local v=MELensTest.vehicle;local q=MELens.profileFor(v);local P=MELens.Parts
local r={script=v:getScript():getFullName(),racks=0,items=0,slots=#q.spots}
for i=1,#q.spots do local part=P.spotPart(v,i)
 if part then part:setInventoryItem(instanceItem(P.itemType("shelf")));P.settle(v,part)
  local c=part:getItemContainer();assert(c,"rack container missing");c:clear();c:setExplored(true)
  for n=1,48 do assert(c:AddItem(n%2==0 and "Base.CannedCorn" or "Base.Bandage"));r.items=r.items+1 end
  r.racks=r.racks+1
 end
end
MELensPerf={vehicle=v,profile=q};MELens.LooseView.refresh();return r''')
        time.sleep(8)
        h.capture('dense-racks')
        frames('dense-racks-64')
        # Avoid changing the player's sandbox configuration outside this profile.
        old_limit = h.lua('return MELens.itemLimit()')
        report['configuredItemLimit'] = old_limit
        report['components']['shelves'] = h.lua('''local t=MELensPerf;local times={};local count,pending
for i=1,7 do local before=getTimestampMs();local rows,p=MELens.LooseView.shelfItems(t.vehicle,t.profile,64)
 times[i]=getTimestampMs()-before;count=#rows;pending=p end
return {ms=times,displayed=count,pending=pending}''')
        # Record samples from the actual game threads, including Lua stacks and
        # allocations. JFR is diagnostic only; no runtime flags are shipped.
        native = json.loads((run/'native-session-started.json').read_text(encoding='utf-8-sig'))
        jcmd = Path(os.environ['RVI_JCMD'])
        recording = run/'dense-racks.jfr'
        result = subprocess.run([str(jcmd), str(native['pid']), 'JFR.start', 'name=rvi-performance',
                                 'settings=profile', 'duration=25s', 'filename='+str(recording)],
                                capture_output=True, text=True, timeout=20)
        report['jfr'] = {'exitCode': result.returncode, 'output': result.stdout+result.stderr}
        save()
        frames('dense-racks-jfr', 27)
        report['loose'] = h.lua('return MELensRV.looseStatus()')
        # Re-run the released shelf implementation in this same world, with the
        # same live items/camera/Java. This isolates shelf CPU from scene variance.
        current = ROOT/'mod/RealVehicleInteriors/common/media/lua/client/MELens_LooseView.lua'
        if args.baseline_ref:
            source_path='mod/RealVehicleInteriors/common/media/lua/client/MELens_LooseView.lua'
            baseline=subprocess.run(['git','show',args.baseline_ref+':'+source_path],cwd=ROOT,
                                    check=True,capture_output=True,text=True,encoding='utf-8').stdout
            report['controlRef']=args.baseline_ref
            for label, source in [('released-shelves-control', baseline), ('fixed-shelves-repeat', current.read_text(encoding='utf-8'))]:
                report.setdefault('controlSources',{})[label]=hashlib.sha256(source.encode('utf-8')).hexdigest()
                h.lua(source+'\nMELens.LooseView.reset();return true')
                time.sleep(4)
                frames(label, 8)
            original = h.lua('MELensPerf.oldItemLimit=MELens.itemLimit;MELens.itemLimit=function() return 16 end;MELens.LooseView.refresh();return true')
            time.sleep(3)
            frames('fixed-shelves-limit16', 8)
            h.lua('MELens.itemLimit=MELensPerf.oldItemLimit;MELens.LooseView.refresh();return true')
        report['components']['cold-shelves'] = h.lua('''local t=MELensPerf;local times={}
for i=1,5 do MELens.LooseView.refresh();local start=getTimestampMs()
 MELens.LooseView.shelfItems(t.vehicle,t.profile,64);times[i]=getTimestampMs()-start end
return times''')
        report['inventory'] = h.lua('''local t=MELensPerf;local V=MELens.LooseView
local rows=V.shelfItems(t.vehicle,t.profile,64);local row=assert(rows[1]);local item=row.item
local container=item:getContainer();local id=item:getID();local count=container:getItems():size()
container:Remove(item);getPlayer():getInventory():AddItem(item)
rows=V.shelfItems(t.vehicle,t.profile,64)
for _,shown in ipairs(rows) do assert(shown.e.id~=id,"transferred item still drawn") end
getPlayer():getInventory():Remove(item);container:AddItem(item)
rows=V.shelfItems(t.vehicle,t.profile,64);local found=false
for _,shown in ipairs(rows) do if shown.e.id==id then found=true end end
assert(found and item:getID()==id and container:getItems():size()==count,"native transfer changed identity/count")
return {itemId=id,count=count,removedDisplay=true,returnedDisplay=found}''')
        # Native phobia acceptance uses ordinary player updates, including near
        # cap and beta-blocker cases. Generalize only the disposable vehicle check.
        phobia = (ROOT/'dev/lua/native-phobia-check.lua').read_text(encoding='utf-8')
        phobia = phobia.replace('vehicle:getScript():getFullName() == "Base.87fordF700box"',
                                'vehicle:getScript():getFullName() == "Base.StepVan"')
        h.lua(phobia)
        deadline = time.monotonic()+45
        while True:
            result = h.lua('return MELens.MELensNativePhobiaTest')
            if result['status'] != 'running':
                report['phobia'] = result
                assert result['status'] == 'passed', result
                break
            assert time.monotonic() < deadline, 'native phobia checks timed out'
            time.sleep(.3)
        # Exercise actual native AnimatedModels, then retire each animal. Rendering
        # must keep advancing after each previous model's queued states drain.
        h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
for i=1,#MELens.profileFor(v).spots do local part=P.spotPart(v,i)
part:getItemContainer():removeAllItems();part:setInventoryItem(instanceItem(P.EMPTY_ITEM));P.showPiece(part,true,false) end
MELens.LooseView.refresh();return true''')
        report['animals'] = []
        kinds=args.animal_types.split(',')
        assert all(kind.replace('_','').isalnum() for kind in kinds), 'invalid native animal type'
        for cycle in range(4):
            kind=kinds[cycle%len(kinds)]
            h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local breed;local kind="'''+kind+'''"
for key in pairs(AnimalDefinitions.animals[kind].breeds) do breed=breed or key end
local a=IsoAnimal.new(getCell(),math.floor(p:getX()),math.floor(p:getY()),0,kind,breed)
a:setWild(false);local item=instanceItem("Base.Animal");item:setAnimal(a)
a:removeFromWorld();a:removeFromSquare();a:setSquare(nil)
p:getInventory():AddItem(item);p:setPrimaryHandItem(item);p:setSecondaryHandItem(item)
v:addAnimalFromHandsInTrailer(a,p);MELens.Animals.place(v,a,0,-1,0,"idle")
a:getStats():set(CharacterStat.HUNGER,0);a:getStats():set(CharacterStat.THIRST,0);return true''')
            time.sleep(2)
            first = json.loads(h.lua('return MELensDevAnimalModels.snapshot()'))
            time.sleep(.5)
            second = json.loads(h.lua('return MELensDevAnimalModels.snapshot()'))
            status = h.lua('return MELensRV.animalsStatus()')
            report['animals'].append({'cycle': cycle, 'first': first, 'second': second, 'status': status})
            assert 'disabled=false' in status and 'cached=1 ' in status, status
            assert first and second, 'animal model did not render'
            advancing = any(a['name'] == b['name'] and a['weight'] > .2 and b['weight'] > .2
                            and abs(a['time']-b['time']) > .001
                            for a in first[0]['tracks'] for b in second[0]['tracks'])
            assert advancing, 'animal animation did not advance after model retirement'
            if cycle == 0:
                h.capture('animal-model-before-retirement')
            h.lua('MELensTest.vehicle:getAnimals():clear();return true')
            time.sleep(1)
            empty = h.lua('return MELensRV.animalsStatus()')
            report['animals'][-1]['retiredStatus'] = empty
            assert 'cached=0 ' in empty and 'retiring=0 ' in empty, empty
        h.lua('local t=MELensPerf;MELens.walkTo(getPlayer(),t.profile.exitMarker.x,t.profile.exitMarker.z);return true')
        deadline=time.monotonic()+20
        while h.lua('return MELens.pathing(getPlayer())'):
            assert time.monotonic()<deadline, 'exit approach timed out'
            time.sleep(.15)
        key=int(h.lua('return getCore():getKey("Interact")'))
        h.lua(f'MEMCNativeLab.holdKey({key},200);return true')
        deadline=time.monotonic()+20
        while h.lua('return getPlayer():getVehicle()~=nil'):
            assert time.monotonic()<deadline, 'native Interact exit timed out'
            time.sleep(.15)
        report['outsidePhobia']=json.loads(h.lua('return MELensRV.phobiaInfo(getPlayer())'))
        assert report['outsidePhobia']=={}, 'interior phobia scope survived native exit'
        report['passed'] = True
    except BaseException:
        report['passed'] = False
        report['error'] = traceback.format_exc()
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
