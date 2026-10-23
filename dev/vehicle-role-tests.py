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
    args = parser.parse_args()
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    assert args.output_name and all(c.isalnum() or c=='-' for c in args.output_name)
    h = load('final-feature-tests'); h.configure(run/args.output_name)
    h.REPORT['scope']='Native factory callbacks and renderer; keyboard entry/exit for body representatives, spawn/heading/seat/camera fixtures for other views'
    beds = load('bed-tests')
    furniture = load('final-furniture-tests')
    interior, tap, _ = furniture.load_helpers()
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    families = json.loads((ROOT/'tools-src/vehicles/coverage.json').read_text())['families']
    names = [f['representative'] for f in families]
    names += ['Base.90fordF350SWAT', 'Base.87fordF700box', 'Base.85chevyStepVanCitrusWave',
              'Base.86fordE150mm', 'Base.Trailer54FlyingCloud22', 'Base.87fordB700school']
    if args.all:
        all_names=h._sequence(h.lua('local rows={};for name in pairs(MELens.Profiles) do rows[#rows+1]=name end;table.sort(rows);return rows'))
        names += sorted(set(all_names) - set(names))
    manifest = h.OUTPUT/'variants.jsonl'
    try:
        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
getGameTime():setTimeOfDay(12);return true''')
        h.REPORT['scenes'] = []
        for number, name in enumerate(names):
            if args.only and name not in args.only:continue
            label = ('v%03d-'%number)+name.split('.',1)[1].lower().replace('_','-')
            print('FACTORY_START '+name, flush=True)
            images = []
            native_input = number < len(families) + 2
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
if piece then expected[i]=piece;assert(pieces[i]==piece,'Missing factory fitting '..i..':'..piece) end end
return {pieces=pieces,expected=expected,containers=containers,models=pr.shell.models,family=pr.walkGrid}''')
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
                    h.lua('MELensMedia.cameraOff();ISUIHandler.setVisibleAllUI(true);return MELensInteriorTest.positionAtExit()')
                    interior.poll(h,lambda s:interior.idle(s),label=label+' exit position')
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
