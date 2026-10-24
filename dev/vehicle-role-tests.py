"""Native factory layouts, loot provenance and intact cab partitions at four headings.

Spawn/heading/seat/camera are capture fixtures. One keyboard entry and exit per
body family uses the production Interact path. No player save is loaded.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--only', action='append', help='Exact script ID for focused retakes')
    parser.add_argument('--output-name', default='factory-layouts')
    parser.add_argument('--limit', type=int, help='Review the first N selected vehicles before continuing')
    parser.add_argument('--resume', action='store_true', help='Continue a reviewed pass in the same owned process')
    parser.add_argument('--native-selected', action='store_true', help='Use production Interact entry/exit for every selected vehicle')
    args = parser.parse_args()
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    assert args.output_name and all(c.isalnum() or c=='-' for c in args.output_name)
    h = load('final-feature-tests'); h.configure(run/args.output_name)
    h.REPORT['scope']='Native factory callbacks and renderer; keyboard entry/exit at measured outside points for every selected vehicle when --native-selected, otherwise body representatives; spawn/heading/seat/camera fixtures for other views'
    beds = load('bed-tests')
    furniture = load('final-furniture-tests')
    interior, tap, _ = furniture.load_helpers()
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    families = json.loads((ROOT/'tools-src/vehicles/coverage.json').read_text())['families']
    names = [f['representative'] for f in families]
    names += ['Base.90fordF350SWAT', 'Base.87fordF700box', 'Base.85chevyStepVanCitrusWave',
              'Base.86fordE150mm', 'Base.Trailer54FlyingCloud22', 'Base.87fordB700school',
              'Base.85chevyStepVanSWAT','Base.StepVan_LouisvilleSWAT']
    if args.all:
        all_names=h._sequence(h.lua('local rows={};for name in pairs(MELens.Profiles) do rows[#rows+1]=name end;table.sort(rows);return rows'))
        names += sorted(set(all_names) - set(names))
    manifest = h.OUTPUT/'variants.jsonl'
    completed = set()
    if args.resume and manifest.exists():
        prior_rows=[json.loads(line) for line in manifest.read_text().splitlines()]
        assert all(len(row['images'])==4 and all(Path(file).is_file() for file in row['images']) for row in prior_rows),'resume has incomplete capture rows'
        completed = {row['name'] for row in prior_rows}
        assert len(completed)==len(prior_rows),'duplicate completed variants'
        previous = json.loads((h.OUTPUT/'native-feature-tests.json').read_text())
        assert previous['status'] in ('passed','failed'), 'resume requires a stopped review phase'
        if previous['status']=='failed':
            archived=h.OUTPUT/('failed-attempt-'+datetime.now(timezone.utc).strftime('%H%M%S')+'.json')
            archived.write_text(json.dumps(previous,indent=2)+'\n')
            h.REPORT['resumedFailure']={'report':str(archived),'completedVariants':len(completed)}
        for field in ('scenes','cases','captures','inputs','nativeInput'):
            if field in previous:h.REPORT[field]=previous[field]
    try:
        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
getGameTime():setTimeOfDay(12);return true''')
        h.REPORT.setdefault('scenes', [])
        selected = 0
        for number, name in enumerate(names):
            if args.only and name not in args.only:continue
            if name in completed:continue
            if args.limit is not None and selected>=args.limit:break
            selected+=1
            label = ('v%03d-'%number)+name.split('.',1)[1].lower().replace('_','-')
            print('FACTORY_START '+name, flush=True)
            images = []
            native_input = args.native_selected or number < len(families) + 2
            for heading in ('E','N','S','W'):
                h.lua('''MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true)
local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true''')
                if heading == 'E' and native_input:
                    beds.enter(h, name, heading)
                    h.REPORT['nativeInput'] = True
                    h.REPORT['inputs'].append(dict(vehicle=name, action='enter', path='production Interact key'))
                else:
                    spawn=(ROOT/'dev/lua/spawn_one.lua').read_text().replace('NAME',name)
                    spawn=spawn.replace('tonumber("7")','tonumber("-4")').replace('local HEADING = "E"',f'local HEADING = "{heading}"')
                    h.lua(spawn); time.sleep(.35)
                    h.lua('local v=MELensTest.vehicle;assert(v:enter(MELens.cabinSeat(v),getPlayer()));return true')
                    deadline=time.monotonic()+15
                    while not h.lua('return MELens.isStanding(getPlayer())'):
                        assert time.monotonic()<deadline, 'standing fixture timeout'
                        time.sleep(.1)
                state=h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts;local pr=MELens.profileFor(v)
local pieces=P.standing(v,pr);local containers={};for i=0,v:getPartCount()-1 do
local part=v:getPartByIndex(i);local c=part:getItemContainer();if c then
containers[#containers+1]={part=part:getId(),type=c:getType(),items=c:getItems():size(),capacity=c:getCapacity()} end end
local expected={};for i,s in ipairs(pr.spots) do local piece=P.factoryPiece(v,i,s)
if piece then expected[i]=piece;assert(pieces[i]==piece,'Missing factory fitting '..i..':'..piece)
if s.factory then local c=P.spotPart(v,i):getItemContainer();local kit=P.kit(piece)
assert(c:getCapacity()==kit.capacity,'Wrong factory capacity');assert(c:getCapacityWeight()<=c:getCapacity()+.001,'Overfilled factory cargo')
local use=pr.factoryUse or {};local stock=(use.stock or {})[piece] or {}
if kit.capacity>0 and (#stock>0 or (use.loot or {})[piece]) then
assert(c:getItems():size()>0,'Empty factory supplies '..i..':'..piece) end end end end
if pr.shell.entryModel then
P.syncShellDoors(v,pr);local leaf=v:getPartById(pr.shell.entryDoor)
local closed=leaf:getInventoryItem()~=nil and not leaf:getDoor():isOpen()
assert(P.shellDoorStates[v]==closed,'Rear door lining state is stale') end
return {pieces=pieces,expected=expected,containers=containers,role=pr.factoryRole,models=pr.shell.models,family=pr.walkGrid}''')
                if heading == 'E':
                    scene = state
                    h.record(label+'-factory-layout',{},state,scope='native create callbacks; untouched factory cargo')
                h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
local z=g.z0+#g.rows*g.cell*.45;MELens.walkTo(getPlayer(),pr.aisleX or 0,z)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
                deadline=time.monotonic()+20
                while h.lua('return #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue~=0 or MELens.pathing(getPlayer())'):
                    assert time.monotonic()<deadline, 'aisle positioning did not finish'
                    time.sleep(.1)
                length=h.lua('local pr=MELens.profileFor(MELensTest.vehicle);local g=MELens.WalkGrids[pr.walkGrid];return #g.rows*g.cell')
                target=1.25 if length>4 else .75
                for _ in range(10):
                    zoom=h.lua('return getCore():getZoom(0)')
                    if abs(zoom-target)<.02:break
                    h.lua(f'getCore():doZoomScroll(0,{1 if zoom<target else -1});return true');time.sleep(.2)
                time.sleep(.5)
                assert not h.lua('return MELensRV.shaderError()'), 'native cutaway shader error'
                images.append(h.capture(label+'-'+heading.lower()))
                if heading == 'E' and native_input:
                    h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
                    marker=h.lua('MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return MELensInteriorTest.positionAtExit()')
                    interior.poll(h,lambda s:interior.idle(s) and s['interior']['standing']
                                  and abs(s['interior']['debug'].get('x',999)-marker['x'])<=marker['halfX']
                                  and abs(s['interior']['debug'].get('z',999)-marker['z'])<=marker['halfZ'],label=label+' reachable exit position')
                    interior.interact_key(h,label+'-exit')
                    interior.poll(h,lambda s:not s['interior']['inside'],label=label+' outside')
                    h.REPORT['inputs'].append(dict(vehicle=name,action='exit',path='production Interact key'))
                else:
                    h.lua('MELensMedia.cameraOff();MELensTest.vehicle:exit(getPlayer());return true')
            row=dict(number=number,name=name,images=images,family=scene['family'],factory=scene,
                     nativeEntryExit=native_input,visualReview='pending')
            with manifest.open('a',encoding='utf-8') as out:out.write(json.dumps(row)+'\n')
            h.REPORT['scenes'].append(row)
            h.write_report('running');print('FACTORY_PASS '+name,flush=True)
        h.REPORT['unverified']=['dedicated server','driving; extra headings use fixtures','human acceptance']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True)
        try:h.capture('failure')
        except Exception:pass
        h.write_report('failed',error);return 1
    finally:
        h.lua('MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return true')


if __name__=='__main__':raise SystemExit(main())
