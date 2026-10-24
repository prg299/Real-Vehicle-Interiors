"""Owned native animal feeding, quiet-time and cold-save checks; setup uses labelled fixtures."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SNAPSHOT = '''local v=MELensTest.vehicle;local A=MELens.Animals;local out={animals={},records=A.records(v,false),sqlId=v:getSqlId(),floor={}}
for _,a in ipairs(A.list(v)) do out.animals[#out.animals+1]={id=a:getAnimalID(),type=a:getAnimalType(),name=a:getCustomName(),health=a:getHealth()} end
table.sort(out.animals,function(a,b) return a.id<b.id end)
local c=MELens.Loose.floorContainer(v);for i=0,c:getItems():size()-1 do local it=c:getItems():get(i);local fc=it:getFluidContainer()
out.floor[#out.floor+1]={id=it:getID(),type=it:getFullType(),water=fc and fc:getAmount() or nil} end
table.sort(out.floor,function(a,b) return a.id<b.id end);return out'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-source', default=os.environ.get('RVI_ANIMALS_VERIFY_SOURCE'))
    args = parser.parse_args()
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h = load('final-feature-tests'); h.configure(run/'animals-lifecycle')
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=', 1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    legacy = (ROOT/'dev/animals/lua/animal_test.lua').read_text('utf-8')

    def fixture(mode):
        return h.lua(legacy.replace('local MODE = "MODE"', 'local MODE = '+json.dumps(mode)))

    def camera():
        h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()-2.5,q);MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')

    def needs(hunger, thirst):
        return h.lua('''local v=MELensTest.vehicle;local a=MELens.Animals.list(v)[1];local r=MELens.Animals.record(v,a)
a:getStats():set(CharacterStat.HUNGER,'''+str(hunger)+''');a:getStats():set(CharacterStat.THIRST,'''+str(thirst)+''');r.u=nil;r.p="idle"
return {hunger=a:getStats():get(CharacterStat.HUNGER),thirst=a:getStats():get(CharacterStat.THIRST)}''')

    def read():
        return h.lua('''local v=MELensTest.vehicle;local a=MELens.Animals.list(v)[1];local r=MELens.Animals.record(v,a)
return {hunger=a:getStats():get(CharacterStat.HUNGER),thirst=a:getStats():get(CharacterStat.THIRST),x=r.x,z=r.z,p=r.p,u=r.u,nextMove=r.nextMove,floor=MELens.Loose.floorContainer(v):getItems():size()}''')

    def clear_floor():
        h.lua('local v=MELensTest.vehicle;MELens.Loose.floorContainer(v):removeAllItems();MELens.Loose.prune(v);return true')

    try:
        h.REPORT['scope'] = __doc__
        h.REPORT['fixtures'] = ['native animal creation and trailer membership', 'empty test cargo room', 'placed food/water',
                                'controlled hunger/thirst and quiet timer', 'world-clock advance', 'saveGame API']
        if args.verify_source:
            expected = json.loads((ROOT/'build/rv'/args.verify_source/'animals-lifecycle/native-feature-tests.json').read_text('utf-8'))
            h.lua('MELensTest={vehicle=assert(getPlayer():getVehicle())};MELensLifecycle={vehicle=MELensTest.vehicle};return true')
            actual = h.lua(SNAPSHOT)
            h.check(actual == expected['savedAnimals'], 'cold save changed animal IDs, positions, names, health, quiet timers or floor stock')
            interior = h.lua(load('interior-lifecycle-tests').SNAPSHOT)
            h.check(interior == expected['savedInterior'], 'cold save changed furniture, loot or utilities')
            camera(); time.sleep(1)
            models = json.loads(h.lua('return MELensDevAnimalModels.snapshot()'))
            active = [m for m in models if m['active']]
            h.check(len(active) == len(actual['animals']) and all(m['tracks'] for m in active), 'cold load lost animal animation')
            h.REPORT['coldReload'] = dict(animals=actual, interiorIdentical=True, activeModels=active)
            h.capture('cold-reloaded-animals')
        else:
            h.lua('MELensTest={all={}};return true')
            load('bed-tests').enter(h, 'Base.87fordF700box', 'N')
            h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts;local pr=MELens.profileFor(v)
for i in ipairs(pr.spots) do local p=P.spotPart(v,i);p:getItemContainer():removeAllItems();p:setInventoryItem(instanceItem(P.EMPTY_ITEM));P.showPiece(p,true,false) end
MELens.walkTo(getPlayer(),pr.exitMarker.x,pr.exitMarker.z);return true''')
            for _ in range(100):
                if not h.lua('return MELens.pathing(getPlayer())'): break
                time.sleep(.1)
            fixture('give:hen')
            h.lua('''local v=MELensTest.vehicle;local p=getPlayer();local a=p:getPrimaryHandItem():getAnimal();v:addAnimalFromHandsInTrailer(a,p)
a:setCustomName("Interior save hen");MELens.Animals.place(v,a,0,-2,0,"idle");return true''')
            camera()
            clear_floor(); before = needs(0,.6); fixture('water'); fixture('minute'); after = read()
            h.check(after['thirst'] < .11 and after['p'] == 'drink', 'water did not relieve thirst')
            h.REPORT['water'] = dict(before=before, after=after, floor=fixture('floor'))
            time.sleep(1); h.capture('hen-drinking-from-placed-dish')
            clear_floor(); before = needs(.6,.6); fixture('food:Base.Corn'); fixture('minute'); after = read()
            h.check(after['hunger'] < before['hunger'] and after['p'] == 'eat', 'thirst without water prevented eating suitable food')
            h.REPORT['foodWithoutWater'] = dict(before=before, after=after, floor=fixture('floor'))
            time.sleep(1); h.capture('hen-eating-placed-corn')
            clear_floor(); before = needs(.6,0); fixture('food:Base.Steak'); fixture('minute'); after = read()
            h.check(abs(after['hunger']-before['hunger']) < .001 and after['p'] != 'eat' and after['floor'] == 1, 'hen ate unsuitable food')
            h.REPORT['dietRejection'] = dict(before=before, after=after)
            clear_floor(); needs(0,0)
            h.lua('''local v=MELensTest.vehicle;local a=MELens.Animals.list(v)[1];local r=MELens.Animals.record(v,a)
r.nextMove=getGameTime():getWorldAgeHours()+20/60;r.u=nil;r.p="idle";return true''')
            before = read()
            for _ in range(12): fixture('minute')
            after = read()
            h.check((before['x'],before['z']) == (after['x'],after['z']), 'same-time updates caused pacing')
            h.lua('local g=getGameTime();g:setTimeOfDay(g:getTimeOfDay()+19/60);return true');time.sleep(.4);fixture('minute')
            after = read()
            h.check((before['x'],before['z']) == (after['x'],after['z']), 'satisfied hen walked during the first 19 quiet minutes')
            h.REPORT['quietControl'] = dict(before=before, after=after, sameTimePasses=12, clockAdvanceMinutes=19)
            # Save a native dog beside the hen, an unfinished drink, and existing
            # furniture/utility/cargo data. Reload must preserve the actual IDs.
            fixture('give:dogmale')
            h.lua('''local v=MELensTest.vehicle;local p=getPlayer();local a=p:getPrimaryHandItem():getAnimal();v:addAnimalFromHandsInTrailer(a,p)
a:setCustomName("Interior save dog");a:getStats():set(CharacterStat.HUNGER,0);a:getStats():set(CharacterStat.THIRST,0)
MELens.Animals.place(v,a,0,-3,0,"lie");return true''')
            needs(0,.6);fixture('water');fixture('minute')
            h.lua('''local v=MELensTest.vehicle;local g=v:getPartById(MELens.Parts.GENERATOR);g:getModData().fuel=5.25;g:getModData().on=false
local w=v:getPartById(MELens.Parts.WATER);w:getModData().water=9.5;w:getModData().tainted=true
local p=MELens.Parts.spotPart(v,1);p:setInventoryItem(instanceItem(MELens.Parts.itemType("box")));MELens.Parts.applyPiece(v,p)
p:getItemContainer():AddItem("Base.Hammer");saveGame();return true''')
            time.sleep(.5)
            h.REPORT['savedAnimals'] = h.lua(SNAPSHOT)
            h.lua('MELensLifecycle={vehicle=MELensTest.vehicle};return true')
            h.REPORT['savedInterior'] = h.lua(load('interior-lifecycle-tests').SNAPSHOT)
            h.REPORT['world'] = h.lua('return getWorld():getWorld()')
            h.capture('saved-hen-and-dog')
        h.REPORT['unverified'] = ['multiplayer', 'Companion Dogs follow input', 'Save/Continue menu input']
        h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1


if __name__ == '__main__': raise SystemExit(main())
