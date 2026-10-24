"""Real inventory/world mouse animal actions, followed by labelled animation fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    interior=load('final-interior-tests');tap,h=interior.load_helpers();h.configure(run/'animals-input')
    furniture=load('final-furniture-tests')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    legacy=(ROOT/'dev/animals/lua/animal_test.lua').read_text('utf-8')
    def fixture(mode):return h.lua(legacy.replace('local MODE = "MODE"','local MODE = '+json.dumps(mode)))
    def wait(code,timeout=40):
        end=time.monotonic()+timeout
        while not h.lua(code):
            h.check(time.monotonic()<end,'timeout: '+code);time.sleep(.15)
    def models():return json.loads(h.lua('return MELensDevAnimalModels.snapshot()'))
    def pose(label,kind,offset=0):
        h.lua('''local v=MELensTest.vehicle;local A=MELens.Animals
for _,animal in ipairs(A.list(v)) do local r=A.record(v,animal)
r.p='''+json.dumps(kind)+''';r.u=getGameTime():getWorldAgeHours()+10;r.nextMove=r.u
r.x=r.x+'''+str(offset)+''';r.f=0 end;return true''')
        samples=[]
        for index in range(16):
            time.sleep(.12);samples.append(models())
            if index in (5,15):h.capture(label+'-'+str(index))
        h.REPORT.setdefault('animationSamples',{})[label]=samples
        for kind in ('hen','dogmale'):
            tracks={}
            for sample in samples:
                for model in sample:
                    if model['type']==kind and model.get('active'):
                        for track in model['tracks']:
                            name=track['name'].lower()
                            expected=(label=='idle' and 'idle' in name
                                or label=='walking' and model['state']=='walk' and 'walk' in name
                                or label=='eating' and 'eat' in name
                                or label=='drinking' and ('eat' in name if kind=='hen' else 'drink' in name)
                                or label=='resting' and any(word in name for word in ('sat','lying','rest')))
                            if expected and track['playing'] and track['weight']>.01:
                                tracks.setdefault(track['name'],[]).append(track['time'])
            advanced=any(len(times)>1 and max(times)-min(times)>.01 for times in tracks.values())
            if not advanced:h.REPORT.setdefault('animationFailures',[]).append(label+': '+kind+' has no advancing weighted clip')
        return samples
    try:
        h.REPORT['scope']=__doc__
        h.lua('MELensTest={all={}};return true')
        load('bed-tests').enter(h,'Base.Trailer54FlyingCloud22','N')
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text('utf-8'));h.lua(interior.FIXTURE);h.lua(furniture.FIXTURE)
        fixture('give:hen')
        h.lua('''MELensInteriorTest.heater=getPlayer():getPrimaryHandItem();MELensInteriorTest.heaterIndex=nil
MELensAnimalTest={hen=MELensInteriorTest.heater:getAnimal(),itemId=MELensInteriorTest.heater:getID()};return true''')
        furniture.open_inventory_item_menu(h,interior,tap)
        drop=h.lua('return getText("ContextMenu_Drop")')
        state=interior.poll(h,lambda s:tap.menu_option(s,drop) is not None,timeout=8,label='actual animal inventory Drop')
        option=tap.menu_option(state,drop);h.check(option['enabled'],'animal Drop disabled inside')
        tap.native_click(h,option['x'],option['y'],'animal:inventory-drop')
        wait('return #MELens.Animals.list(MELensTest.vehicle)==1 and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0')
        h.REPORT['mouseDrop']=True;h.capture('native-inventory-drop')
        h.lua('''function MELensAnimalTest.point()
local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local a=MELens.AnimalsUI.shown(v)[1];assert(a)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z()
for _,height in ipairs({.15,.25,.05,.4}) do
v:getWorldPos(o:x()+a.x,o:y()+pr.floorY+height,o:z()+a.z,q)
local sx,sy=ISCoordConversion.ToScreen(q:x(),q:y(),base+(o:y()+pr.floorY+height)/2.44949)
local hit=MELens.Interact.pick(v,pr,sx,sy)
if hit and hit.animal==a.animal then return {x=sx/getCore():getZoom(0),y=sy/getCore():getZoom(0),header=MELens.AnimalsUI.nameOf(a.animal)} end end
error("no pickable animal point") end;return true''')
        point=h.lua('return MELensAnimalTest.point()')
        interior.choose(h,tap,point,[point['header'],h.lua('return getText("ContextMenu_PickUpAnimalBody")')],'animal:pickup')
        wait('return #MELens.Animals.list(MELensTest.vehicle)==0 and getPlayer():getInventory():getCountTypeRecurse("Animal")==1 and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0')
        h.REPORT['mousePickup']=True;h.REPORT['pickupState']=fixture('state');h.capture('native-world-pickup')

        # Separate rendering fixtures: clear a test-owned truck so model visibility
        # and animation progress can be reviewed without furniture/actor occlusion.
        h.lua('''local p=getPlayer();p:getVehicle():exit(p);MELensMedia.cameraOff()
p:setPrimaryHandItem(nil);p:setSecondaryHandItem(nil)
local inv=p:getInventory();local items=inv:getItems();for i=items:size()-1,0,-1 do if instanceof(items:get(i),"AnimalInventoryItem") then inv:Remove(items:get(i)) end end
return true''')
        load('bed-tests').enter(h,'Base.87fordF700box','N')
        h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts;local pr=MELens.profileFor(v)
for i in ipairs(pr.spots) do local part=P.spotPart(v,i);part:getItemContainer():removeAllItems()
part:setInventoryItem(instanceItem(P.EMPTY_ITEM));P.showPiece(part,true,false) end
MELens.walkTo(getPlayer(),pr.exitMarker.x,pr.exitMarker.z)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local g=MELens.WalkGrids[pr.walkGrid]
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
        wait('return not MELens.pathing(getPlayer())')
        for kind,x,z in [('hen',0,-2.0),('dogmale',0,-3.0)]:
            fixture('give:'+kind)
            h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local a=p:getPrimaryHandItem():getAnimal()
v:addAnimalFromHandsInTrailer(a,p);MELens.Animals.place(v,a,'''+str(x)+','+str(z)+''',0,"idle")
a:getStats():set(CharacterStat.HUNGER,0);a:getStats():set(CharacterStat.THIRST,0);return true''')
        for _ in range(8):
            zoom=h.lua('return getCore():getZoom(0)')
            if abs(zoom-.5)<.02:break
            h.lua('getCore():doZoomScroll(0,'+str(1 if zoom<.5 else -1)+');return true');time.sleep(.15)
        pose('idle','idle')
        pose('walking','idle',.6)
        pose('eating','eat')
        pose('drinking','drink')
        pose('resting','lie')
        h.REPORT['renderStatus']=h.lua('return MELensRV.animalsStatus()')
        h.check(not h.REPORT.get('animationFailures'),str(h.REPORT.get('animationFailures')))
        h.REPORT['nativeInput']=True
        h.REPORT['unverified']=['multiplayer','save/reload','autonomous feeding','furniture routing','visual acceptance until frames reviewed']
        h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1

if __name__=='__main__':raise SystemExit(main())
