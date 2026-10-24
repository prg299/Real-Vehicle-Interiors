"""Native Companion Dogs care, interior commands, carry-out, Bring and streaming checks."""
import argparse
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


FIXTURE='''MELensDogCare=MELensDogCare or {}
function MELensDogCare.snapshot()
 local T=MELensDogCare;local v=MELensTest.vehicle;local A=MELens.Animals;local animals={}
 for _,a in ipairs(A.list(v)) do local d=CompanionDogs.data(a)
 animals[#animals+1]={id=a:getAnimalID(),onlineId=a:getOnlineID(),uid=d.uid,token=d.companionToken,state=CompanionDogs.getState(a),
 hunger=CompanionDogs.getHunger(a),thirst=a:getThirst(),health=a:getHealth(),upkeep=d.lastUpkeepMin,record=A.record(v,a),owner=d.ownerKey} end
 local bowls={};local c=MELens.Loose.floorContainer(v);for i=0,c:getItems():size()-1 do local it=c:getItems():get(i)
 if A.isDogsBowl(it) then local d=it:getModData();bowls[#bowls+1]={id=it:getID(),food=d.cdFoodMeals or 0,water=d.cdWater or 0} end end
 table.sort(bowls,function(a,b) return a.id<b.id end)
 return {animals=animals,bowls=bowls,worldHours=getGameTime():getWorldAgeHours(),carried=getPlayer():getInventory():getCountTypeRecurse("Animal"),
 inside=getPlayer():getVehicle()==v,sqlId=v:getSqlId(),loaded=getCell():getVehicles():contains(v)}
end
function MELensDogCare.point()
 local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local a=MELens.AnimalsUI.shown(v)[1];assert(a,"no shown dog")
 local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z()
 for _,height in ipairs({.25,.15,.4,.6,.05}) do v:getWorldPos(o:x()+a.x,o:y()+pr.floorY+height,o:z()+a.z,q)
 local sx,sy=ISCoordConversion.ToScreen(q:x(),q:y(),base+(o:y()+pr.floorY+height)/2.44949)
 local hit=MELens.Interact.pick(v,pr,sx,sy);if hit and hit.animal==a.animal then
 return {x=sx/getCore():getZoom(0),y=sy/getCore():getZoom(0),name=MELens.AnimalsUI.nameOf(a.animal)} end end
 error("no animal ray hit")
end
return true'''

BUTTONS='''local out={};local seen={}
local function visit(w) if not w or seen[w] or not w:isVisible() then return end;seen[w]=true
 if w.title then out[#out+1]={title=tostring(w.title),type=tostring(w.Type),x=w:getAbsoluteX()+w:getWidth()/2,y=w:getAbsoluteY()+w:getHeight()/2,enabled=w.enable~=false} end
 for _,child in pairs(w.children or {}) do if type(child)=="table" then visit(child) end end end
local list=UIManager.getUI();for i=0,list:size()-1 do local w=list:get(i);local l=w and w:getTable();if l then visit(l) end end;return out'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify-source');parser.add_argument('--finish-care-source');parser.add_argument('--after-bring',action='store_true');parser.add_argument('--bowl-only',action='store_true');parser.add_argument('--bring-only',action='store_true');parser.add_argument('--resume',action='store_true');parser.add_argument('--output-name',default='dog-care');args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN'];h=load('final-feature-tests');h.configure(run/args.output_name)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    interior=load('final-interior-tests');tap,_=interior.load_helpers();menus=load('final-mp-animals').MENUS

    def wait(read,predicate=bool,label='expected animal state',timeout=40):
        h.REPORT['activeWait']=label;end=time.monotonic()+timeout;latest=None
        while time.monotonic()<end:
            latest=read()
            if time.monotonic()>=h._input_release and predicate(latest):return latest
            time.sleep(.15)
        raise AssertionError(label+': '+json.dumps(latest,default=str))

    def snap():
        s=h.lua('return MELensDogCare.snapshot()')
        for k in ('animals','bowls'):s[k]=h._sequence(s[k])
        return s

    def idle():wait(lambda:h.lua('return not MELens.pathing(getPlayer()) and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0'))

    def resume_overlay():
        point=h.lua('''local m=MainScreen and MainScreen.instance;local r=m and m.returnOption
if r and r:isReallyVisible() then return {x=r:getAbsoluteX()+r:getWidth()/2,y=r:getAbsoluteY()+r:getHeight()/2} end''')
        if point:
            tap.native_click(h,point['x'],point['y'],'resume after Escape menu');time.sleep(.65)

    def close_menus():
        resume_overlay()
        for _ in range(4):
            if not h._sequence(h.lua(menus)):return
            h.lua('MEMCNativeLab.holdKey(1,180);return true')
            h.REPORT['inputs'].append(dict(action='dismiss context menu',api='MEMCNativeLab.holdKey',key=1))
            time.sleep(.65)
            resume_overlay()
        h.check(not h._sequence(h.lua(menus)),'native Escape did not dismiss context menus')

    def dog_menu(label):
        idle();close_menus();point=h.lua('return MELensDogCare.point()')
        tap.native_click(h,point['x'],point['y'],'dog:world-menu',right=True)
        for name in (point['name'],label):
            rows=wait(lambda:h._sequence(h.lua(menus)),lambda rows:any(r['name']==name for r in rows),'menu '+name,timeout=8)
            row=next(r for r in rows if r['name']==name);h.check(row['enabled'],'disabled menu '+name)
            tap.native_click(h,row['x'],row['y'],'dog:'+name);time.sleep(.2)

    def dog_state(state):
        # Ordinary Companion Dogs obedience can refuse an order. Retry the real
        # input after its two-second lock, never write the tested state directly.
        for attempt in range(5):
            if snap()['animals'][0]['state']==state:return
            dog_menu(h.lua('return getText('+json.dumps('IGUI_PD_Stay' if state=='stay' else 'IGUI_PD_Follow')+')'))
            time.sleep(2.2)
            if snap()['animals'][0]['state']==state:return
            h.REPORT.setdefault('obedienceRefusals',[]).append(dict(state=state,attempt=attempt+1))
        raise AssertionError('Companion Dogs refused five native '+state+' orders')

    def exit_native():
        h.lua('local v=MELensTest.vehicle;local pr=MELens.profileFor(v);MELens.walkTo(getPlayer(),pr.exitMarker.x,pr.exitMarker.z);return true');idle()
        key=int(h.lua('return getCore():getKey("Interact")'));h.lua(f'MEMCNativeLab.holdKey({key},180);return true')
        h.REPORT['inputs'].append(dict(action='owner exits interior',api='MEMCNativeLab.holdKey',key=key))
        wait(lambda:h.lua('return getPlayer():getVehicle()==nil'),label='real Interact exit')

    def enter_native():
        h.lua('''local v=MELensTest.vehicle;local p=getPlayer();local q=Vector3f.new();v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"outside"),q)
p:setX(q:x());p:setY(q:y());p:setLastX(q:x());p:setLastY(q:y())
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q);p:faceLocation(q:x(),q:y());ISUIHandler.setVisibleAllUI(true);return true''');time.sleep(.5)
        # Refresh the native nearby-vehicle cache after the streaming fixture.
        approach=h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local q=Vector3f.new()
v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"inside"),q)
local dx,dy=q:x()-p:getX(),q:y()-p:getY();local sx,sy=dx-dy,dx+dy
return getCore():getKey(math.abs(sx)>math.abs(sy) and (sx>0 and "Right" or "Left") or (sy>0 and "Backward" or "Forward"))''')
        h.lua(f'MEMCNativeLab.holdKey({int(approach)},150);return true');time.sleep(.65)
        h.lua('''local v=MELensTest.vehicle;local p=getPlayer();local q=Vector3f.new();v:getPassengerPositionWorldPos(v:getPassengerPosition(MELens.cabinSeat(v),"outside"),q)
p:setX(q:x());p:setY(q:y());p:setLastX(q:x());p:setLastY(q:y());return true''');time.sleep(.5)
        key=int(h.lua('return getCore():getKey("Interact")'));h.lua(f'MEMCNativeLab.holdKey({key},180);return true')
        h.REPORT['inputs'].append(dict(action='owner enters interior',api='MEMCNativeLab.holdKey',key=key))
        try:wait(lambda:h.lua('return MELens.isStanding(getPlayer())'));idle()
        except Exception:
            h.REPORT['failedEntry']=h.lua('''local p=getPlayer();local v=MELensTest.vehicle;local part=v:getUseablePart(p)
return {x=p:getX(),y=p:getY(),z=p:getZ(),vehicleX=v:getX(),vehicleY=v:getY(),seat=p:getVehicle() and p:getVehicle():getSeat(p),
part=part and part:getId(),near=MELens.nearWayIn(p,v,MELens.profileFor(v)),debug=MELens.debugState()}''')
            h.capture('failed-native-reentry');raise

    def carried():
        return h.lua('''local it=getPlayer():getInventory():getFirstTypeRecurse("Animal");local a=it and it:getAnimal()
return {count=getPlayer():getInventory():getCountTypeRecurse("Animal"),item=it and it:getID(),uid=a and CompanionDogs.ensureUid(a),state=a and CompanionDogs.getState(a)}''')

    def inventory_menu(item_id):
        furniture=load('final-furniture-tests')
        h.lua('MELensInteriorTest.heater=getPlayer():getInventory():getItemWithID('+str(item_id)+');MELensInteriorTest.heaterIndex=nil;return true')
        furniture.open_inventory_item_menu(h,interior,tap)

    def menu_click(label):
        rows=wait(lambda:h._sequence(h.lua(menus)),lambda rows:any(r['name']==label for r in rows),'menu '+label,timeout=8)
        row=next(r for r in rows if r['name']==label);h.check(row['enabled'],'disabled menu '+label)
        tap.native_click(h,row['x'],row['y'],label);time.sleep(.2)

    def saved_state():
        return h.lua('''local v=MELensTest.vehicle;local a=assert(MELens.Animals.list(v)[1]);local d=CompanionDogs.data(a)
local bowls={};local c=MELens.Loose.floorContainer(v);for i=0,c:getItems():size()-1 do local b=c:getItems():get(i)
if MELens.Animals.isDogsBowl(b) then local m=b:getModData();bowls[#bowls+1]={id=b:getID(),food=m.cdFoodMeals or 0,water=m.cdWater or 0} end end
table.sort(bowls,function(x,y) return x.id<y.id end)
return {animalId=a:getAnimalID(),uid=d.uid,token=d.companionToken,owner=d.ownerKey,name=d.name,state=CompanionDogs.getState(a),sqlId=v:getSqlId(),bowls=bowls}''')

    def command_cases():
        h.lua('local w=ISCDStatusWindow.instanceFor(getPlayer());if w then w:close() end;return true')
        close_menus()
        if not snap()['inside']:enter_native()
        wait(snap,lambda s:len(s['animals'])==1,'recalled dog follows owner back inside',timeout=60)
        uid=snap()['animals'][0]['uid']
        h.check(h.lua('return CompanionDogs.isOwnedBy(MELens.Animals.list(MELensTest.vehicle)[1],getPlayer())'),
                'command fixture must start with the players own companion')
        # A foreign ownership fixture must disable pickup and dog commands. A
        # real click on the disabled row cannot take the dog or move the player.
        h.lua('''local a=MELens.Animals.list(MELensTest.vehicle)[1];local d=CompanionDogs.data(a)
MELensDogCare.owner={key=d.ownerKey,name=d.ownerName};d.ownerKey="rvi_other_owner";d.ownerName="Other owner";return true''')
        point=h.lua('return MELensDogCare.point()');tap.native_click(h,point['x'],point['y'],'foreign dog:world-menu',right=True)
        menu_click(point['name']);rows=wait(lambda:h._sequence(h.lua(menus)),label='foreign dog submenu')
        label=h.lua('return getText("ContextMenu_PickUpAnimalBody")');row=next(r for r in rows if r['name']==label)
        h.check(not row['enabled'],'another owner can pick up the dog')
        before=h.lua('local x,z=MELens.Parts.characterAt(MELensTest.vehicle,getPlayer());return {x=x,z=z}')
        tap.native_click(h,row['x'],row['y'],'foreign dog:rejected pickup');time.sleep(.7)
        h.check(snap()['carried']==0 and snap()['animals'][0]['uid']==uid,'rejected foreign pickup changes animal ownership')
        after=h.lua('local x,z=MELens.Parts.characterAt(MELensTest.vehicle,getPlayer());return {x=x,z=z,path=MELens.pathing(getPlayer())}')
        h.check(before['x']==after['x'] and before['z']==after['z'] and not after['path'],'disabled dog menu click moves the underlying scene')
        h.REPORT['foreignOwnerPickupRejected']=True;h.capture('native-foreign-dog-pickup-disabled')
        h.lua('''local d=CompanionDogs.data(MELens.Animals.list(MELensTest.vehicle)[1]);local o=MELensDogCare.owner
d.ownerKey=o.key;d.ownerName=o.name;CompanionDogs.regInvalidate();return true''');close_menus()
        # Native Follow/Stay commands, followed by real exit, test the complete
        # interaction instead of fixture state changes used by the older MP run.
        dog_state('stay');dog_state('follow')
        wait(snap,lambda s:s['animals'][0]['state']=='follow');exit_native()
        wait(snap,lambda s:len(s['animals'])==0,'native Follow takes dog outside',timeout=60)
        enter_native();wait(snap,lambda s:len(s['animals'])==1,'native Follow brings dog inside again',timeout=60)
        h.REPORT['nativeFollowRoundTrip']=snap()
        dog_state('stay')
        h.lua('''local a=MELens.Animals.list(MELensTest.vehicle)[1];CompanionDogs.setNeed(a,"hunger",0);CompanionDogs.setNeed(a,"thirst",0)
local r=MELens.Animals.record(MELensTest.vehicle,a);r.u=nil;return true''')
        before=wait(snap,lambda s:s['animals'][0].get('upkeep') is not None,'initial loaded care clock')
        h.lua('local g=getGameTime();g:setTimeOfDay(g:getTimeOfDay()+40/60);return true')
        after=wait(snap,lambda s:s['animals'][0].get('upkeep',0)>before['animals'][0]['upkeep']+30,
            'Stay spans an expired voluntary movement timer')
        origin,settled=before['animals'][0]['record'],after['animals'][0]['record']
        h.check(origin['x']==settled['x'] and origin['z']==settled['z'],'Stay dog wandered without needing food or water')
        h.REPORT['nativeStayFortyMinutes']={'before':before,'after':after}
        dog_menu(h.lua('return getText("ContextMenu_PickUpAnimalBody")'))
        c=wait(carried,lambda c:c['count']==1,'native Pick up produces carried dog')
        h.check(c['uid']==uid and len(snap()['animals'])==0,'pickup changed or duplicated dog identity')
        h.capture('native-dog-carried-inside');exit_native()
        h.check(carried()['uid']==uid,'exit lost the carried dog');h.REPORT['carryOutside']=carried();h.capture('native-dog-carried-outside')
        enter_native()
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text('utf-8'));h.lua(interior.FIXTURE);h.lua(load('final-furniture-tests').FIXTURE)
        inventory_menu(c['item']);menu_click(h.lua('return getText("ContextMenu_Drop")'))
        s=wait(snap,lambda s:len(s['animals'])==1 and s['carried']==0,'native inventory Drop returns carried dog to interior')
        h.check(s['animals'][0]['uid']==uid and s['animals'][0]['state']=='stay','drop changed companion identity or Stay command')
        h.REPORT['nativeCarryRoundTrip']=s;h.capture('native-dog-dropped-back-inside')
        return bowl_cases()

    def bowl_cases():
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text('utf-8'));h.lua(interior.FIXTURE);h.lua(load('final-furniture-tests').FIXTURE)
        # Exercise the familiar CD Place bowl inventory option with CD's normal
        # stocked-bowl representation. New CD bowls whitelist cosmetic fluids;
        # ordinary Water cannot be poured into them (legacy bowls can accept it).
        bowl=h.lua('''local v=MELensTest.vehicle;local c=MELens.Loose.floorContainer(v);local items=c:getItems()
for i=items:size()-1,0,-1 do if MELens.Animals.isDogsBowl(items:get(i)) then c:Remove(items:get(i)) end end;MELens.Loose.prune(v)
local inv=getPlayer():getInventory();items=inv:getItems();for i=items:size()-1,0,-1 do if MELens.Animals.isDogsBowl(items:get(i)) then inv:Remove(items:get(i)) end end
local b=inv:AddItem("Base.CompanionDogsBowl");b:getModData().cdWater=100;CompanionDogs.refreshDishModel(b,true);return b:getID()''')
        h.REPORT['nativeBowlId']=bowl
        inventory_menu(bowl);menu_click(h.lua('return getText("IGUI_PD_PlaceDish")'))
        wait(lambda:h.lua('return MELens.LooseUI.active~=nil'),label='CD Place bowl starts interior cursor')
        point=wait(lambda:h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local b=getPlayer():getInventory():getItemWithID('''+str(bowl)+''');local UI=MELens.LooseUI
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z();local zoom=getCore():getZoom(0)
for _,p in ipairs(MELens.Loose.floorPoints(v,pr)) do v:getWorldPos(o:x()+p[1],o:y()+pr.floorY,o:z()+p[2],q)
local sx,sy=ISCoordConversion.ToScreen(q:x(),q:y(),base+(o:y()+pr.floorY)/2.44949);local hover=UI.hoverFor(v,pr,b,0,sx,sy)
local px,py=sx/zoom,sy/zoom
if hover and hover.valid and hover.surface.s==0 and px>400 and px<1200 and py>250 and py<650 then return {x=px,y=py} end end'''),label='valid native bowl placement point')
        tap.native_click(h,point['x'],point['y'],'CD bowl:place interior preview')
        wait(lambda:h.lua('return MELens.LooseUI.active==nil and MELens.Loose.floorContainer(MELensTest.vehicle):getItemWithID('+str(bowl)+')~=nil'),label='native bowl placement commits')
        h.lua('local v=MELensTest.vehicle;local a=MELens.Animals.list(v)[1];CompanionDogs.setNeed(a,"thirst",.6);MELens.Animals.record(v,a).u=nil;return true')
        s=wait(snap,lambda s:s['animals'][0]['thirst']<.4 and any(0<b['water']<100 for b in s['bowls']),'dog drinks stocked interior bowl',timeout=60)
        h.REPORT['nativeBowlPlacementAndWater']=s;h.capture('native-bowl-water-consumed')
        h.lua('saveGame();return true');h.REPORT['savedCompanion']=saved_state();h.REPORT['world']=h.lua('return getWorld():getWorld()')
        h.REPORT['nativeInput']=True;h.write_report('passed');return 0

    def bring_case():
        h.lua('ISUIHandler.setVisibleAllUI(true);ISCDStatusWindow.OpenKennelOnly(getPlayer(),"kennel");return true')
        point=wait(lambda:h.lua('''local w=ISCDStatusWindow.instanceFor(getPlayer());local k=w and w.kennelView
local row=k and k.rowPanels and k.rowPanels[1];if row and row:isVisible() then return {x=row:getAbsoluteX()+row:getWidth()/2,y=row:getAbsoluteY()+row:getHeight()/2} end'''),label='native kennel dog row')
        tap.native_click(h,point['x'],point['y'],'dog:select kennel row')
        title=h.lua('return getText("IGUI_PD_CmdFetch")')
        rows=wait(lambda:h._sequence(h.lua(BUTTONS)),lambda rows:any(b['title']==title and b['enabled'] for b in rows),'enabled native Bring button')
        button=next(b for b in rows if b['title']==title and b['enabled']);tap.native_click(h,button['x'],button['y'],'dog:Bring from interior')
        time.sleep(.7)
        rows=h._sequence(h.lua(BUTTONS));yes=h.lua('return getText("UI_Yes")')
        confirm=next((b for b in rows if b['title']==yes and b['enabled']),None)
        if confirm:tap.native_click(h,confirm['x'],confirm['y'],'dog:Bring confirmation')
        wait(snap,lambda s:len(s['animals'])==0,'Bring takes dog from interior to outside owner')
        h.REPORT['bringOutside']=h.lua('''CompanionDogs.regInvalidate();local out={};for _,a in ipairs(CompanionDogs.regCompanions()) do if CompanionDogs.ensureUid(a)==MELensDogCare.uid then out[#out+1]={uid=CompanionDogs.ensureUid(a),vehicle=a:getVehicle()~=nil,distance=a:DistTo(getPlayer():getX(),getPlayer():getY())} end end;return out''')
        h.check(len(h._sequence(h.REPORT['bringOutside']))==1,'Bring duplicated or lost dog');h.capture('native-bring-dog-outside')
        wait(lambda:h.lua('local count=0;for _ in pairs(MELens.Animals.records(MELensTest.vehicle,false) or {}) do count=count+1 end;return count'),lambda n:n==0,'Bring clears interior occupancy record',timeout=60)
        h.REPORT['bringRecordPruned']=True

    def complete_care(start):
        target=start['worldHours']+24
        if snap()['worldHours']<target:
            h.lua('UIManager.getSpeedControls():ButtonClicked("Wait");return true')
            try:
                wait(lambda:h.lua('return getGameTime():getTrueMultiplier()>1'),label='native accelerated clock',timeout=5)
                wait(snap,lambda s:s['worldHours']>=target,'one simulated day of loaded care',timeout=210)
            finally:h.lua('UIManager.getSpeedControls():ButtonClicked("Play");return true')
        s=snap()
        h.check(len(s['animals'])==1 and s['animals'][0]['health']>=.99,'dog lost health during supplied loaded care')
        h.check(s['animals'][0].get('upkeep',0)>start['animals'][0].get('upkeep',0)+1400,'interior dog care clock did not run across one day')
        # At the default .3/day hunger rate and .5 trigger, a .1-fed dog does not
        # need its second meal within 24 h. Water (.6/day) must be consumed again.
        h.check(sum(b['water'] for b in s['bowls'])<sum(b['water'] for b in start['bowls']),'ongoing loaded care never consumed another drink')
        h.REPORT['loadedDay']=dict(before=start,after=s)
        h.lua('''local v=MELensTest.vehicle;local p=getPlayer();MELensDogCare.anchor={x=v:getX(),y=v:getY()};p:setX(v:getX()+400);p:setY(v:getY());p:setLastX(p:getX());p:setLastY(p:getY());return true''')
        wait(lambda:h.lua('return not getCell():getVehicles():contains(MELensTest.vehicle)'),label='actual vehicle chunk unload')
        h.lua('local g=getGameTime();g:setTimeOfDay(g:getTimeOfDay()+12);return true');time.sleep(.6)
        h.lua('local p=getPlayer();local a=MELensDogCare.anchor;p:setX(a.x+5);p:setY(a.y);p:setLastX(p:getX());p:setLastY(p:getY());return true')
        wait(lambda:h.lua('''local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next();if v:getModData().RVICareTest=="care-20261024" then MELensTest.vehicle=v;return true end end;return false'''),label='vehicle returns from actual streaming')
        s=snap();h.check(len(s['animals'])==1 and s['animals'][0]['uid']==start['animals'][0]['uid'],'streaming lost or duplicated dog identity')
        h.check(s['animals'][0]['health']>=.99,'unloaded time harmed the staying dog');h.REPORT['unloadedTwelveHours']=s
        bring_case();h.write_report('passed');return 0

    try:
        h.REPORT.update(scope=__doc__,fixtures=['bonded dog at real entrance','two separate stocked bowls','world-clock/time-speed controls','400-tile streaming relocation'])
        h.lua('UIManager.getSpeedControls():ButtonClicked("Play");return true')
        resume_overlay()
        if args.verify_source:
            expected=json.loads((ROOT/args.verify_source).read_text('utf-8'))
            h.lua('MELensTest={vehicle=assert(getPlayer():getVehicle())};return true');h.lua(FIXTURE)
            actual=saved_state();h.check(actual==expected['savedCompanion'],'cold reload changed bonded dog identity, ownership, Stay or bowl stocks')
            h.REPORT['coldReload']=actual;h.capture('cold-reloaded-companion-and-bowl');h.write_report('passed')
            (run/'request.json').write_text('{"action":"stop"}');return 0
        if args.after_bring:
            h.lua('MELensTest=MELensTest or {};MELensTest.vehicle=MELensTest.vehicle or assert(getPlayer():getVehicle());return true')
            h.lua(FIXTURE);return command_cases()
        if args.bowl_only:
            h.lua('MELensTest={vehicle=assert(getPlayer():getVehicle())};return true');h.lua(FIXTURE);return bowl_cases()
        if args.bring_only:
            h.lua(FIXTURE);bring_case();h.write_report('passed');return 0
        if args.finish_care_source:
            previous=json.loads((run/args.finish_care_source/'native-feature-tests.json').read_text('utf-8'))
            h.REPORT['reusedCareEvidence']=args.finish_care_source
            h.REPORT['unattendedLoadedFeeding']=previous['unattendedLoadedFeeding']
            h.lua(FIXTURE);return complete_care(previous['unattendedLoadedFeeding']['after'])
        if not args.resume:
            h.lua('MELensTest={all={}};return true');load('bed-tests').enter(h,'Base.87fordF700box','N')
        h.lua(FIXTURE)
        if args.resume and not h.lua('return getPlayer():getVehicle()~=nil'):enter_native()
        if not args.resume:h.lua('''local v=MELensTest.vehicle;local p=getPlayer();v:getModData().RVICareTest="care-20261024"
local P=MELens.Parts;local pr=MELens.profileFor(v)
for i in ipairs(pr.spots) do local part=P.spotPart(v,i);part:getItemContainer():removeAllItems();part:setInventoryItem(instanceItem(P.EMPTY_ITEM));P.applyPiece(v,part) end
local o=v:getScript():getModel():getOffset();local d=pr.standing.outside;local q=v:getWorldPos(o:x()+d[1],0,o:z()+d[3],Vector3f.new())
local a=assert(CompanionDogs.spawnDog(math.floor(q:x()),math.floor(q:y()),0,"dogmale"));CompanionDogs.makeCompanion(a,p)
CompanionDogs.data(a).trust=100;CompanionDogs.data(a).name="Interior care dog";a:setCustomName("Interior care dog")
MELensDogCare.uid=CompanionDogs.ensureUid(a);return true''')
        s=wait(snap,lambda s:len(s['animals'])==1,'dog follows in through normal minute event',timeout=60);h.REPORT['followIn']=s
        h.lua('MELensDogCare.uid=MELens.Animals.list(MELensTest.vehicle)[1]:getModData().CompanionDogs.uid;return true')
        h.lua('local v=MELensTest.vehicle;MELens.walkTo(getPlayer(),0,-2);return true');idle()
        dog_state('stay')
        s=wait(snap,lambda s:s['animals'][0]['state']=='stay','real Stay command');h.REPORT['stayMenu']=s;h.capture('native-dog-stay')
        dog_menu(h.lua('return getText("IGUI_PD_Inspect")'))
        wait(lambda:h.lua('local w=ISCDStatusWindow.instanceFor(getPlayer());return w and w:isVisible() and w.animal~=nil'))
        h.capture('native-dog-inspect');h.lua('ISCDStatusWindow.instanceFor(getPlayer()):close();return true')
        h.lua('''local v=MELensTest.vehicle;local A=MELens.Animals;local a=A.list(v)[1];local r=A.record(v,a);local c=MELens.Loose.floorContainer(v)
local items=c:getItems();for i=items:size()-1,0,-1 do if A.isDogsBowl(items:get(i)) then c:Remove(items:get(i)) end end;MELens.Loose.prune(v)
for _,kind in ipairs({"food","water"}) do local b=c:AddItem("Base.CompanionDogsBowl");local d=b:getModData()
if kind=="food" then d.cdFoodMeals=100 else d.cdWater=100 end;CompanionDogs.refreshDishModel(b,true)
local x,z=A.freePoint(v,MELens.profileFor(v),r.x+(kind=="food" and .3 or -.3),r.z,"none")
MELens.Loose.set(v,b,x,MELens.profileFor(v).floorY,z,0,0) end
CompanionDogs.setNeed(a,"hunger",.6);CompanionDogs.setNeed(a,"thirst",.6);r.u=nil;return true''')
        before=snap();exit_native()
        trigger=h.lua('return MELens.Animals.trigger(MELens.Animals.list(MELensTest.vehicle)[1])')
        s=wait(snap,lambda s:s['animals'][0]['hunger']<trigger and s['animals'][0]['thirst']<trigger and sum(b['food'] for b in s['bowls'])<100 and sum(b['water'] for b in s['bowls'])<100,'staying dog eats and drinks without owner inside',timeout=60)
        h.REPORT['unattendedLoadedFeeding']=dict(before=before,after=s)
        return complete_care(snap())
    except Exception:
        # Restore setup-only ownership even if a native input assertion fails.
        try:h.lua('''local T=MELensDogCare;local v=MELensTest and MELensTest.vehicle
local a=v and MELens.Animals.list(v)[1];if a and T and T.owner then local d=CompanionDogs.data(a)
d.ownerKey=T.owner.key;d.ownerName=T.owner.name;CompanionDogs.regInvalidate();T.owner=nil end;return true''')
        except Exception:pass
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
