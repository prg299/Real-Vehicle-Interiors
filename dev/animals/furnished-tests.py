"""Native small-animal input and animation samples in an unchanged furnished F700.

The owned parent provides the game lifetime. Carried animals, needs, and short
wandering decisions are labelled fixtures; inventory Drop and pickup use native
mouse events. This does not test breeding or unrestricted animal navigation.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    spec = importlib.util.spec_from_file_location(path.replace('/', '_'), ROOT/'dev'/(path+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume',action='store_true');parser.add_argument('--pose-room',action='store_true');parser.add_argument('--output-name',default='animals-furnished');args=parser.parse_args()
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    interior = load('final-interior-tests'); tap, h = interior.load_helpers()
    furniture = load('final-furniture-tests'); care = load('animals/dog-care-tests')
    h.configure(run/args.output_name)
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(x.split('=', 1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    legacy = (ROOT/'dev/animals/lua/animal_test.lua').read_text('utf-8')

    def wait(code, timeout=40):
        end = time.monotonic()+timeout
        while not h.lua(code):
            h.check(time.monotonic()<end, 'timeout: '+code); time.sleep(.15)

    def fixture(mode):
        return h.lua(legacy.replace('local MODE = "MODE"', 'local MODE = '+json.dumps(mode)))

    def pickup(kind):
        h.lua('local v=MELensTest.vehicle;local a=MELens.Animals.list(v)[1];local r=MELens.Animals.record(v,a);r.nextMove=getGameTime():getWorldAgeHours()+10;return true')
        wait('local v=MELensTest.vehicle;local a=MELens.AnimalsUI.shown(v)[1];local r=a and MELens.Animals.record(v,a.animal);return a and r and (a.x-r.x)^2+(a.z-r.z)^2<.0004 and not a.walking')
        h.lua('getPlayerContextMenu(0):hideAndChildren();ISUIHandler.setVisibleAllUI(true);return true')
        point=h.lua('return MELensDogCare.point()')
        header=h.lua('return MELens.Animals.list(MELensTest.vehicle)[1]:getFullName()')
        label=h.lua('local a=MELens.Animals.list(MELensTest.vehicle)[1];return getText("ContextMenu_PickUpAnimal",a:getFullName())')
        interior.choose(h,tap,point,[header,label],kind+':native-pickup')
        wait('return #MELens.Animals.list(MELensTest.vehicle)==0 and getPlayer():getInventory():getCountTypeRecurse("Animal")==1 and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0')

    def clear_carried():
        h.lua('''local p=getPlayer();local it=p:getPrimaryHandItem();assert(it and instanceof(it,"AnimalInventoryItem"))
p:setPrimaryHandItem(nil);p:setSecondaryHandItem(nil);p:getInventory():Remove(it);return true''')

    try:
        h.REPORT.update(scope=__doc__, fixtures=['carried native animals', 'satisfied needs',
            'expired wandering timers and minute callback; no furniture changes'])
        if args.resume:
            h.lua('MELensTest={vehicle=assert(getPlayer():getVehicle())};return true')
        else:
            h.lua('MELensTest={all={}};return true')
            load('bed-tests').enter(h, 'Base.87fordF700box', 'N')
        if args.pose_room:
            h.REPORT['fixtures'].append('separate empty owned cargo room for unobstructed pose review; furnished input evidence is recorded separately')
            h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do local part=P.spotPart(v,i);part:getItemContainer():removeAllItems();part:setInventoryItem(instanceItem(P.EMPTY_ITEM));P.applyPiece(v,part) end;return true''')
        before = h.lua('''local v=MELensTest.vehicle;local out={}
for i in ipairs(MELens.profileFor(v).spots) do local p=MELens.Parts.spotPart(v,i);local it=p:getInventoryItem()
out[#out+1]={spot=i,id=it and it:getID(),piece=MELens.Parts.pieceAt(p)} end;return out''')
        if not args.pose_room:
            h.check(any(r.get('piece') not in (None, 'none', 'empty') for r in h._sequence(before)), 'furnished fixture is empty')
        h.lua('MELensFeatureTest={vehicle=getPlayer():getVehicle(),snapshot=function() return {queueCount=#ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue} end};return true')
        h.lua(interior.FIXTURE); h.lua(furniture.FIXTURE); h.lua(care.FIXTURE)
        if args.resume and h.lua('return #MELens.Animals.list(MELensTest.vehicle)>0'):
            pickup('resume-existing');clear_carried()
        h.REPORT['furnitureBefore'] = before
        for kind in ('rabdoe', 'lamb', 'piglet', 'cowcalf'):
            result = {'fixture': fixture('give:'+kind)}
            h.REPORT.setdefault('species', {})[kind]=result
            h.check('carrying '+kind in result['fixture'], 'native animal definition missing: '+kind)
            h.lua('MELensInteriorTest.heater=getPlayer():getPrimaryHandItem();MELensInteriorTest.heaterIndex=nil;return true')
            furniture.open_inventory_item_menu(h, interior, tap)
            label = h.lua('return getText("ContextMenu_Drop")')
            state = interior.poll(h, lambda s: tap.menu_option(s, label) is not None, timeout=8, label=kind+' inventory Drop')
            row = tap.menu_option(state, label); h.check(row['enabled'], 'Drop disabled for '+kind)
            tap.native_click(h, row['x'], row['y'], kind+':inventory-drop')
            wait('return #MELens.Animals.list(MELensTest.vehicle)==1 and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0')
            h.lua('local w=getPlayerInventory(0);if w then w:setVisible(false) end;return true')
            if args.pose_room:
                h.lua('local v=MELensTest.vehicle;local A=MELens.Animals;local a=A.list(v)[1];local x,z=A.freePoint(v,MELens.profileFor(v),0,-2.7,tostring(a:getAnimalID()));A.place(v,a,x,z,.785,"idle");return true')
                wait('local v=MELensTest.vehicle;local a=MELens.AnimalsUI.shown(v)[1];local r=a and MELens.Animals.record(v,a.animal);return a and r and (a.x-r.x)^2+(a.z-r.z)^2<.0004 and not a.walking')
            for pose in ('idle', 'eat', 'drink', 'lie'):
                h.lua('''local a=MELens.Animals.list(MELensTest.vehicle)[1];local r=MELens.Animals.record(MELensTest.vehicle,a)
r.p='''+json.dumps(pose)+''';r.u=getGameTime():getWorldAgeHours()+10;r.nextMove=r.u;return true''')
                samples=[]
                for _ in range(8):
                    time.sleep(.15); samples.append(json.loads(h.lua('return MELensDevAnimalModels.snapshot()')))
                tracks={}
                for sample in samples:
                    for model in sample:
                        if model['type']==kind and model.get('active'):
                            for t in model['tracks']:
                                name=t['name'].lower()
                                expected=('eat' in name if pose in ('eat','drink') else
                                    'sit' in name if pose=='lie' and kind in ('lamb','piglet') else 'idle' in name)
                                if expected and t['playing'] and t['weight']>.01: tracks.setdefault(t['name'], []).append(t['time'])
                h.check(any(len(ts)>1 and max(ts)-min(ts)>.01 for ts in tracks.values()), kind+' '+pose+' has no advancing weighted clip')
                result[pose]=samples; h.capture(kind+'-'+pose+'-furnished')
            if not args.pose_room:
                result['wandering'] = h.lua('''local v=MELensTest.vehicle;local A,L=MELens.Animals,MELens.Loose;local a=A.list(v)[1]
local pr=MELens.profileFor(v);local moved,steps=0,{}
for i=1,40 do local r=A.record(v,a);local x,z=r.x,r.z;r.p="idle";r.u=nil;r.nextMove=-1
a:getStats():set(CharacterStat.HUNGER,0);a:getStats():set(CharacterStat.THIRST,0);A.onMinute();r=A.record(v,a)
assert(L.fitsSurface(v,pr,{kind="floor",s=0,y=pr.floorY},r.x,r.z,.1,.1),"animal overlaps furniture or leaves floor")
-- WANDER bounds each target axis, not radial distance. The current sampled
-- point remains eligible, so nearest-floor snapping can at most double the
-- requested diagonal distance. Record actual steps for visual assessment.
local d=(x-r.x)^2+(z-r.z)^2;assert(d<=8*A.WANDER^2+.0001,"oversized animal step")
if d>.0001 then moved=moved+1 end;steps[#steps+1]={x=x,z=z,nextX=r.x,nextZ=r.z} end
return {moved=moved,steps=steps}''')
                h.check(result['wandering']['moved']>0, kind+' never moved in forty decisions')
            # Forty setup decisions run in one tick; let the displayed animal
            # finish interpolating to the final record before aiming the mouse.
            wait('local v=MELensTest.vehicle;local a=MELens.AnimalsUI.shown(v)[1];local r=a and MELens.Animals.record(v,a.animal);return a and r and (a.x-r.x)^2+(a.z-r.z)^2<.0004 and not a.walking')
            h.capture(kind+'-after-furnished-wandering')
            pickup(kind)
            h.REPORT.setdefault('species', {})[kind]=result
            clear_carried()
        after=h.lua('''local v=MELensTest.vehicle;local out={}
for i in ipairs(MELens.profileFor(v).spots) do local p=MELens.Parts.spotPart(v,i);local it=p:getInventoryItem()
out[#out+1]={spot=i,id=it and it:getID(),piece=MELens.Parts.pieceAt(p)} end;return out''')
        h.check(before==after, 'animal interactions changed furniture IDs or pieces')
        h.REPORT['furnitureAfter']=after;h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
