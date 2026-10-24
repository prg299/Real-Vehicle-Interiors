"""Two-peer native dog ownership, carry/drop, commands, care, Bring and restart."""
import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--verify-source',type=Path)
    args=p.parse_args();driver=load('final-mp-interior-tests');lab=driver.InteriorLab(args.session,args.output);h=lab.h
    animal=load('final-mp-animals')
    spec=importlib.util.spec_from_file_location('dog_care',ROOT/'dev/animals/dog-care-tests.py');care=importlib.util.module_from_spec(spec);spec.loader.exec_module(care)

    def read(side):
        code=animal.READ.replace('VID',str(lab.vid))+'''
for _,a in ipairs(MELens.Animals.list(v)) do local d=CompanionDogs.data(a)
for _,row in ipairs(r.animals) do if row.id==a:getAnimalID() then
row.uid=d.uid;row.token=d.companionToken;row.owner=d.ownerKey;row.state=CompanionDogs.getState(a)
row.upkeep=d.lastUpkeepMin;row.health=a:getHealth();row.hunger=CompanionDogs.getHunger(a) end end end
r.sqlId=v:getSqlId();r.hours=getGameTime():getWorldAgeHours()
'''
        r=json.loads(lab.server(driver.JSON_ENCODER+code+'return enc(r)')) if side=='server' else (h if side=='A' else lab.b).lua(code+'return r')
        for key in ('animals','floor'):r[key]=h._sequence(r.get(key))
        return r

    def all_states():return {side:read(side) for side in ('A','B','server')}
    def count(n):return lab.wait(all_states,lambda ss:all(len(s['animals'])==n for s in ss.values()),str(n)+' dogs on server and both peers',timeout=60)

    def menu(label,side='A',enabled=True):
        api=h if side=='A' else lab.b
        # Setup cleanup only; actions under test still use native mouse input.
        api.lua('local m=getPlayerContextMenu(0);if m then m:hideAndChildren() end;return true')
        point=api.lua('return MELensDogCare.point()');lab.input(side,x=point['x'],y=point['y'],right=True)
        for title in (point['name'],label):
            rows=lab.wait(lambda:h._sequence(api.lua(animal.MENUS)),lambda rr:any(r['name']==title for r in rr),'native dog menu '+title,timeout=10)
            r=next(r for r in rows if r['name']==title)
            h.check(r['enabled']==(enabled if title==label else True),'unexpected command availability '+title)
            lab.input(side,x=r['x'],y=r['y']);time.sleep(.2)

    def set_state(state):
        for attempt in range(5):
            if read('server')['animals'][0]['state']==state:return
            menu(h.lua('return getText('+json.dumps('IGUI_PD_Stay' if state=='stay' else 'IGUI_PD_Follow')+')'));time.sleep(2.2)
        h.check(read('server')['animals'][0]['state']==state,'five native dog commands refused')

    def exit_owner():
        h.lua('local p=getPlayer();local pr=MELens.profileFor(p:getVehicle());MELens.walkTo(p,pr.exitMarker.x,pr.exitMarker.z);return true')
        lab.wait(lambda:h.lua('return not MELens.pathing(getPlayer()) and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0'),bool,'owner at exit')
        lab.input('A',key=int(h.lua('return getCore():getKey("Interact")')))
        lab.wait(lambda:h.lua('return getPlayer():getVehicle()==nil'),bool,'native owner Interact exit')

    def carry_case():
        before=count(1);uid=before['server']['animals'][0]['uid']
        # The guest stays a real non-owner; no ownership fixture is needed in MP.
        lab.b.lua('MELensTest={vehicle=getVehicleById('+str(lab.vid)+')};ISUIHandler.setVisibleAllUI(true);return true')
        lab.b.lua(care.FIXTURE)
        position=lambda:lab.b.lua('local x,z=MELens.Parts.characterAt(MELensTest.vehicle,getPlayer());return {x=x,z=z,path=MELens.pathing(getPlayer())}')
        origin=position()
        lab.b.lua('local m=getPlayerContextMenu(0);if m then m:hideAndChildren() end;return true')
        point=lab.b.lua('return MELensDogCare.point()');lab.input('B',x=point['x'],y=point['y'],right=True)
        time.sleep(.6)
        rows=h._sequence(lab.b.lua(animal.MENUS));title=lab.b.lua('return getText("IGUI_PD_Carry")')
        h.check(not any(r['name']==title and r['enabled'] for r in rows),'normal dog menu exposes guest Carry')
        after=count(1)
        settled=position()
        h.check(after['server']['animals'][0]['uid']==uid and after['B']['carried']==0
                and not settled['path'] and abs(settled['x']-origin['x'])<1e-4 and abs(settled['z']-origin['z'])<1e-4,
                'guest pickup click changed the dog or underlying player movement')
        h.REPORT['guestPickupRejected']=after;lab.capture('B','mp-non-owner-pickup-disabled')
        lab.b.lua('getPlayerContextMenu(0):hideAndChildren();return true')

        def carried():
            return h.lua('local it=getPlayer():getInventory():getFirstTypeRecurse("Animal");local a=it and it:getAnimal();return {count=getPlayer():getInventory():getCountTypeRecurse("Animal"),id=it and it:getID(),uid=a and CompanionDogs.ensureUid(a)}')

        menu(h.lua('return getText("IGUI_PD_Carry")'))
        item=lab.wait(carried,lambda s:s['count']==1,'native owner pickup creates one carried dog')
        h.check(item['uid']==uid,'pickup changed companion UID');h.REPORT['nativePickup']=count(0)
        exit_owner();h.check(carried()['uid']==uid,'native exit lost carried dog')
        h.REPORT['carryOutside']=carried();lab.capture('A','mp-owner-carries-dog-outside')
        lab.enter_e('A');h.check(carried()['uid']==uid,'native re-entry lost carried dog')

        interior=load('final-interior-tests');tap,_=interior.load_helpers();furniture=load('final-furniture-tests')
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text('utf-8'));h.lua(interior.FIXTURE);h.lua(furniture.FIXTURE)
        h.lua('MELensInteriorTest.heater=getPlayer():getInventory():getItemWithID('+str(item['id'])+');MELensInteriorTest.heaterIndex=nil;return true')
        furniture.open_inventory_item_menu(h,interior,tap)
        title=h.lua('return getText("ContextMenu_Drop")')
        rows=lab.wait(lambda:h._sequence(h.lua(animal.MENUS)),lambda rr:any(r['name']==title for r in rr),'native inventory Drop option')
        row=next(r for r in rows if r['name']==title);h.check(row['enabled'],'inventory Drop is disabled')
        lab.input('A',x=row['x'],y=row['y'])
        after=lab.wait(all_states,lambda ss:all(len(s['animals'])==1 and s['animals'][0]['uid']==uid
            and s['animals'][0]['state']=='stay' for s in ss.values()),'inventory Drop preserves identity and Stay on both peers')
        lab.wait(carried,lambda s:s['count']==0,'inventory Drop removes carried item')
        h.REPORT['nativeCarryRoundTrip']=after;lab.capture('A','mp-native-inventory-drop-dog')
        h.lua('local w=getPlayerInventory(0);if w then w:setVisible(false) end;return true')

    try:
        h.REPORT.update(scope=__doc__,fixtures=['bonded world dog at real entrance','empty owned cargo room','separate stocked bowls','controlled needs and 10-minute server-clock advance'])
        if args.verify_source:
            previous=json.loads(args.verify_source.read_text('utf-8'));expected=previous['savedCompanion']
            # A reconnect may place players outside their saved vehicle. Resolve
            # the existing vehicle by persistent SQL ID and use real Interact
            # input to re-enter; never spawn a replacement for the restart check.
            find='local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next();if v:getSqlId()=='+str(expected['sqlId'])+' then return v:getId() end end;return -1'
            lab.vid=lab.wait(lambda:int(lab.server(find)),lambda value:value>=0,'saved vehicle loads after dedicated-server restart')
            for side,api in (('A',h),('B',lab.b)):
                lab.wait(lambda:api.lua('return getVehicleById('+str(lab.vid)+')~=nil'),bool,'saved vehicle replicated on '+side)
                if not api.lua('return getPlayer():getVehicle()~=nil'):lab.enter_e(side)
            ss=count(1);a=ss['server']['animals'][0]
            h.check(all(a[k]==expected[k] for k in ('id','uid','token','owner','state')) and ss['server']['sqlId']==expected['sqlId'],'server restart changed dog identity, owner or Stay')
            h.check(ss['server']['floor']==previous['savedFloor'],'server restart changed interior food/water stocks')
            h.REPORT['restart']=ss
            lab.server('local g=getGameTime();g:setTimeOfDay(g:getTimeOfDay()+(CompanionDogs.KENNEL_RECALL_COOLDOWN_MIN+1)/60);return "existing recall cooldown elapsed"')
        else:
            lab.prepare(allow_server_java=True)
            lab.server('''local v=getVehicleById('''+str(lab.vid)+''');local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do local part=P.spotPart(v,i);local c=part:getItemContainer();local old={}
for j=0,c:getItems():size()-1 do old[#old+1]=c:getItems():get(j) end;for _,it in ipairs(old) do c:Remove(it);sendRemoveItemFromContainer(c,it) end
part:setInventoryItem(instanceItem(P.EMPTY_ITEM));P.applyPiece(v,part);v:transmitPartItem(part) end
local owner;local ps=getOnlinePlayers();for i=0,ps:size()-1 do if ps:get(i):getUsername()=="MELensAdmin" then owner=ps:get(i) end end
local pr=MELens.profileFor(v);local o=v:getScript():getModel():getOffset();local d=pr.standing.outside;local q=v:getWorldPos(o:x()+d[1],0,o:z()+d[3],Vector3f.new())
local a=assert(CompanionDogs.spawnDog(math.floor(q:x()),math.floor(q:y()),0,"dogmale"));CompanionDogs.makeCompanion(a,owner)
CompanionDogs.data(a).trust=100;CompanionDogs.data(a).name="MP care dog";a:setCustomName("MP care dog");CompanionDogs.transmit(a);CompanionDogs.regInvalidate();return "bonded"''')
            h.REPORT['followIn']=count(1)
        h.lua('MELensTest={vehicle=getVehicleById('+str(lab.vid)+')};ISUIHandler.setVisibleAllUI(true);return true');h.lua(care.FIXTURE)
        if not h.lua('local a=MELens.Animals.list(MELensTest.vehicle)[1];return CompanionDogs.data(a).companionToken==CompanionDogs.playerData(getPlayer()).token'):
            menu(h.lua('local a=MELens.Animals.list(MELensTest.vehicle)[1];return getText("IGUI_PD_Select",CompanionDogs.data(a).name)'))
            lab.wait(lambda:h.lua('local a=MELens.Animals.list(MELensTest.vehicle)[1];return CompanionDogs.data(a).companionToken==CompanionDogs.playerData(getPlayer()).token'),bool,'native selected companion after loading')
            h.REPORT['nativeCompanionSelection']=True
        set_state('stay');h.REPORT['nativeStay']=all_states()
        menu(h.lua('return getText("IGUI_PD_Inspect")'))
        lab.wait(lambda:h.lua('local w=ISCDStatusWindow.instanceFor(getPlayer());return w and w:isVisible()'),bool,'native interior Inspect remains open')
        lab.capture('A','mp-native-interior-inspect');h.lua('ISCDStatusWindow.instanceFor(getPlayer()):close();return true')
        h.REPORT['petCooldownFixture']=lab.server('local a=MELens.Animals.list(getVehicleById('+str(lab.vid)+'))[1];local last=CompanionDogs.data(a).lastPetMin;local wait=last and last+CompanionDogs.petCooldownMin()+1-CompanionDogs.worldMinutes() or 0;if wait>0 then getGameTime():setTimeOfDay(getGameTime():getTimeOfDay()+wait/60) end;return wait')
        prior_pet=lab.server('local a=MELens.Animals.list(getVehicleById('+str(lab.vid)+'))[1];return CompanionDogs.data(a).lastPetMin or -1')
        menu(h.lua('return getText("IGUI_PD_Pet")'))
        lab.wait(lambda:h.lua('return getPlayer():getVariableBoolean("petanimal")'),bool,'native dedicated-server pet animation starts')
        samples=[]
        for _ in range(4):
            samples.append(json.loads(h.lua('return MELensDevBones.tracks(getPlayer())')));time.sleep(.2)
        lab.capture('A','mp-native-pet-pose')
        pet_tracks={}
        for sample in samples:
            for track in sample:
                if 'pet' in track['name'].lower() and track['blend']>.1:pet_tracks.setdefault(track['name'],[]).append(track['time'])
        h.check(any(len(times)>1 and max(times)-min(times)>.01 for times in pet_tracks.values()),'dedicated-server pet action has no advancing weighted player clip')
        lab.wait(lambda:lab.server('local a=MELens.Animals.list(getVehicleById('+str(lab.vid)+'))[1];return CompanionDogs.data(a).lastPetMin or -1'),lambda value:value!=prior_pet,'dedicated server accepts the native pet effect')
        lab.wait(lambda:h.lua('return not getPlayer():getVariableBoolean("petanimal") and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0'),bool,'native pet action cleans up')
        h.REPORT['nativePet']={'before':prior_pet,'playerTracks':samples}
        before=lab.wait(all_states,lambda ss:ss['server']['animals'][0].get('upkeep') is not None,
            'first loaded Companion Dogs upkeep pass')
        lab.server('local g=getGameTime();g:setTimeOfDay(g:getTimeOfDay()+40/60);return "forty minute Stay control"')
        lab.wait(lambda:read('server'),lambda s:s['hours']>before['server']['hours']+.6
            and s['animals'][0]['upkeep']>before['server']['animals'][0]['upkeep']+30,'Stay spans an expired wandering timer')
        after=all_states()
        for side in ('A','B','server'):
            prior=next(iter(before[side]['records'].values()));current=next(iter(after[side]['records'].values()))
            h.check(current['x']==prior['x'] and current['z']==prior['z'],'Stay dog voluntarily wandered on '+side)
        h.REPORT['nativeStayFortyMinutes']={'before':before,'after':after}
        carry_case()
        lab.server('''local v=getVehicleById('''+str(lab.vid)+''');local A=MELens.Animals;local a=A.list(v)[1];local r=A.record(v,a)
for _,kind in ipairs({"food","water"}) do local b=MELens.Loose.floorContainer(v):AddItem("Base.CompanionDogsBowl");b:getModData()[kind=="food" and "cdFoodMeals" or "cdWater"]=100
CompanionDogs.refreshDishModel(b,true);local x,z=A.freePoint(v,MELens.profileFor(v),r.x+(kind=="food" and .3 or -.3),r.z,"none")
MELens.Loose.set(v,b,x,MELens.profileFor(v).floorY,z,0,0);sendAddItemToContainer(b:getContainer(),b) end
CompanionDogs.setNeed(a,"hunger",.6);CompanionDogs.setNeed(a,"thirst",.6);r.u=nil;return "supplies"''')
        exit_owner()
        ss=lab.wait(all_states,lambda ss:ss['server']['animals'][0]['hunger']<.5 and ss['server']['animals'][0]['thirst']<.5 and
            ss['A']['floor']==ss['B']['floor']==ss['server']['floor'],'authoritative unattended feeding and identical stocks',timeout=65)
        h.REPORT['unattendedCare']=ss;start=ss['server']['animals'][0]['upkeep']
        lab.server('local g=getGameTime();g:setTimeOfDay(g:getTimeOfDay()+10/60);return "ten minutes"')
        lab.wait(lambda:read('server'),lambda s:s['animals'][0]['upkeep']>start+8,'loaded interior upkeep advances on dedicated server')
        # Actual kennel row, Bring, and confirmation input while owner is outside.
        uid=read('server')['animals'][0]['uid'];h.lua('ISCDStatusWindow.OpenKennelOnly(getPlayer(),"kennel");return true')
        pt=lab.wait(lambda:h.lua('local w=ISCDStatusWindow.instanceFor(getPlayer());local r=w and w.kennelView.rowPanels[1];if r then return {x=r:getAbsoluteX()+r:getWidth()/2,y=r:getAbsoluteY()+r:getHeight()/2} end'),bool,'native kennel row')
        lab.input('A',x=pt['x'],y=pt['y'])
        for title in (h.lua('return getText("IGUI_PD_CmdFetch")'),h.lua('return getText("UI_Yes")')):
            rows=lab.wait(lambda:h._sequence(h.lua(care.BUTTONS)),lambda rr:any(r['title']==title and r['enabled'] for r in rr),'native '+title)
            r=next(r for r in rows if r['title']==title and r['enabled']);lab.input('A',x=r['x'],y=r['y'])
        ss=count(0);h.REPORT['bringOutside']=ss
        lab.wait(all_states,lambda ss:all(not s.get('records') for s in ss.values()),'Bring clears occupancy on both peers')
        dogs=json.loads(lab.server(driver.JSON_ENCODER+'''CompanionDogs.regInvalidate();local out={};for _,a in ipairs(CompanionDogs.regCompanions()) do out[#out+1]={uid=CompanionDogs.ensureUid(a),vehicle=a:getVehicle()~=nil} end;return enc(out)'''))
        h.check(sum(d['uid']==uid for d in h._sequence(dogs))==1,'Bring lost or duplicated the world dog');h.REPORT['outsideIdentity']=dogs
        lab.capture('A','mp-native-bring-outside');h.lua('ISCDStatusWindow.instanceFor(getPlayer()):close();return true')
        lab.enter_e('A');count(1);set_state('stay');ss=all_states();a=ss['server']['animals'][0]
        h.REPORT['savedCompanion']={**{k:a[k] for k in ('id','uid','token','owner','state')},'sqlId':ss['server']['sqlId']}
        h.REPORT['savedFloor']=ss['server']['floor']
        h.REPORT['nativeInput']=True;h.write_report('passed');(args.session/'request.json').write_text('{"action":"stop"}');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
