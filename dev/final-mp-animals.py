"""Owned two-peer animal authority/replication and native world-menu pickup checks."""
import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


READ = '''local v=getVehicleById(VID);local A=MELens.Animals;local r={animals={},floor={},records=A.records(v,false)}
for _,a in ipairs(A.list(v)) do r.animals[#r.animals+1]={id=a:getAnimalID(),type=a:getAnimalType(),name=a:getCustomName(),hunger=a:getStats():get(CharacterStat.HUNGER),thirst=a:getStats():get(CharacterStat.THIRST)} end
table.sort(r.animals,function(a,b) return a.id<b.id end)
local c=MELens.Loose.floorContainer(v);for i=0,c:getItems():size()-1 do local it=c:getItems():get(i);local fc=it:getFluidContainer()
r.floor[#r.floor+1]={id=it:getID(),type=it:getFullType(),water=fc and fc:getAmount() or nil,cdWater=it:getModData().cdWater,cdFood=it:getModData().cdFoodMeals} end
table.sort(r.floor,function(a,b) return a.id<b.id end)
if not isServer() then r.carried=getPlayer():getInventory():getCountTypeRecurse("Animal");r.render=MELensRV.animalsStatus() end
'''

MENUS = '''local root=getPlayerContextMenu(0);local out={};local seen={}
local function visit(m) if not m or seen[m] or not m:isVisible() then return end;seen[m]=true
for i,o in ipairs(m.options or {}) do local y=m:getItemY(i)+m.itemHgt/2
if y>=m:getY() and y<=m:getY()+m:getHeight() then out[#out+1]={name=tostring(o.name),enabled=not o.notAvailable and not o.isDisabled,x=m:getX()+m:getWidth()/2,y=y} end end end
visit(root);if root then for _,m in ipairs(root.instanceMap or {}) do visit(m) end end;return out'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--session',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse-vehicle',type=int)
    args=parser.parse_args();driver=load('final-mp-interior-tests');lab=driver.InteriorLab(args.session,args.output);h=lab.h

    def state(side):
        code=READ.replace('VID',str(lab.vid))
        r=json.loads(lab.server(driver.JSON_ENCODER+code+'return enc(r)')) if side=='server' else (lab.h if side=='A' else lab.b).lua(code+'return r')
        r['animals']=h._sequence(r.get('animals'));r['floor']=h._sequence(r.get('floor'));return r

    def states():return {s:state(s) for s in ('A','B','server')}

    def count(n):
        return lab.wait(states,lambda ss:all(len(s['animals'])==n for s in ss.values()),str(n)+' animals on A/B/server',timeout=45)

    def same_records(ss):
        return ss['A']['records']==ss['B']['records']==ss['server']['records']

    try:
        h.REPORT.update(scope=__doc__,inputCoverage=['native E entry on both peers','native animal world-menu pickup'],
                        fixtures=['admin server spawns world hen','vanilla network pickup action','production Drop handler queues normal server action','placed water and controlled thirst','empty test cargo room'])
        if args.reuse_vehicle:
            lab.vid=args.reuse_vehicle
            for api in (h,lab.b):
                api.lua('''local p=getPlayer();p:setPrimaryHandItem(nil);p:setSecondaryHandItem(nil);local inv=p:getInventory();local items=inv:getItems()
for i=items:size()-1,0,-1 do local it=items:get(i);if instanceof(it,"AnimalInventoryItem") and it:getAnimal():getCustomName()=="MP interior hen" then inv:Remove(it) end end;return true''')
            lab.server('''local ps=getOnlinePlayers();for j=0,ps:size()-1 do local p=ps:get(j);p:setPrimaryHandItem(nil);p:setSecondaryHandItem(nil)
local inv=p:getInventory();local items=inv:getItems();for i=items:size()-1,0,-1 do local it=items:get(i);if instanceof(it,"AnimalInventoryItem") and it:getAnimal():getCustomName()=="MP interior hen" then inv:Remove(it) end end end;return "old synthetic fixture cleared"''')
        else:lab.prepare(allow_server_java=True)
        lab.server('''local v=getVehicleById('''+str(lab.vid)+''');local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do local p=P.spotPart(v,i);local c=p:getItemContainer()
local old={};for j=0,c:getItems():size()-1 do old[#old+1]=c:getItems():get(j) end
for _,it in ipairs(old) do c:Remove(it);sendRemoveItemFromContainer(c,it) end
p:setInventoryItem(instanceItem(P.EMPTY_ITEM));P.applyPiece(v,p);v:transmitPartItem(p) end;return "cleared"''')
        h.lua('MELens.leave(getPlayer());return true')
        lab.wait(lambda:h.lua('return getPlayer():getVehicle()==nil'),bool,'outside for vanilla animal pickup setup')
        animal_id=int(lab.server('''local p;local ps=getOnlinePlayers();for i=0,ps:size()-1 do if ps:get(i):getUsername()=="MELensAdmin" then p=ps:get(i) end end;assert(p)
local breed;for b in pairs(AnimalDefinitions.animals.hen.breeds) do breed=breed or b end
local a=IsoAnimal.new(getCell(),math.floor(p:getX())+1,math.floor(p:getY()),0,"hen",breed);a:setWild(false);a:setCustomName("MP interior hen");a:addToWorld();return a:getAnimalID()'''))
        world_find='''local list=getCell():getAnimals();for i=0,list:size()-1 do local a=list:get(i);if a:getAnimalID()=='''+str(animal_id)+''' then return a end end'''
        lab.wait(lambda:h.lua(world_find),bool,'real world hen replicated before vanilla pickup')
        h.lua('local function find() '+world_find+' end;ISTimedActionQueue.add(ISPickupAnimal:new(getPlayer(),assert(find())));return true')
        lab.wait(lambda:h.lua('return getPlayer():getInventory():getCountTypeRecurse("Animal")==1 and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0'),bool,'vanilla network animal pickup')
        animal_item=int(h.lua('return getPlayer():getInventory():getFirstTypeRecurse("Animal"):getID()'))
        lab.enter_e('A')
        h.lua('''local p=getPlayer();local it=p:getInventory():getItemWithID('''+str(animal_item)+''');assert(it)
p:setPrimaryHandItem(it);p:setSecondaryHandItem(it);sendEquip(p);ISInventoryPaneContextMenu.dropItem(it,0);return true''')
        ss=count(1);h.check(len({s['animals'][0]['id'] for s in ss.values()})==1,'native animal IDs differ across peers')
        ss=lab.wait(states,same_records,'identical animal position records on A/B/server')
        ss=lab.wait(states,lambda ss:ss['A']['carried']==0,'Drop removes the carried animal item')
        h.REPORT['dropAuthority']=ss
        lab.server('local v=getVehicleById('+str(lab.vid)+');local a=MELens.Animals.list(v)[1];MELens.Animals.place(v,a,0,-2,0,"idle");v:transmitModData();return "visibility fixture"')
        for side,api in (('A',h),('B',lab.b)):
            api.lua('''local v=getVehicleById('''+str(lab.vid)+''');local pr=MELens.profileFor(v);local a=MELens.Animals.list(v)[1];local r=MELens.Animals.record(v,a)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();v:getWorldPos(o:x()+r.x,o:y()+pr.floorY,o:z()+r.z,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949);ISUIHandler.setVisibleAllUI(false);return true''')
            time.sleep(.4);lab.capture(side,'mp-hen-inside-'+side.lower())
            samples=[]
            for _ in range(5):
                samples.append(json.loads(api.lua('return MELensDevAnimalModels.snapshot()')));time.sleep(.15)
            times=[t['time'] for sample in samples for m in sample if m['active'] for t in m['tracks'] if t['playing'] and t['weight']>.1]
            h.check(times and max(times)-min(times)>.01,'no advancing animal animation on '+side)
            h.REPORT.setdefault('peerAnimations',{})[side]=samples
        water_id=int(lab.server('''local v=getVehicleById('''+str(lab.vid)+''');local A=MELens.Animals;local a=A.list(v)[1];local r=A.record(v,a)
a:getStats():set(CharacterStat.THIRST,.6);a:getStats():set(CharacterStat.HUNGER,0);r.u=nil;r.p="idle"
local it=MELens.Loose.floorContainer(v):AddItem("Base.WaterDish");it:getFluidContainer():addFluid(Fluid.Water,.25)
MELens.Loose.set(v,it,r.x+.3,MELens.profileFor(v).floorY,r.z,0,0);sendAddItemToContainer(it:getContainer(),it)
A.updateVehicle(v,MELens.profileFor(v));v:transmitModData();return it:getID()'''))
        def water_equal(ss):
            stocks=[[it for it in s['floor'] if it['id']==water_id] for s in ss.values()]
            return same_records(ss) and all(len(it)==1 and it[0].get('water',1)<.001 for it in stocks) and ss['server']['animals'][0]['thirst']<.11
        ss=lab.wait(states,water_equal,'authoritative water consumption and identical stock/pose on both peers')
        h.REPORT['feedingAuthority']=ss
        for side in ('A','B'):lab.capture(side,'mp-hen-drinking-'+side.lower())
        # Point at the actual shown animal and dispatch the real menu clicks.
        point=h.lua('''local v=getVehicleById('''+str(lab.vid)+''');local pr=MELens.profileFor(v);local a=MELens.AnimalsUI.shown(v)[1];assert(a)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z()
for _,height in ipairs({.15,.25,.05,.4}) do v:getWorldPos(o:x()+a.x,o:y()+pr.floorY+height,o:z()+a.z,q)
local sx,sy=ISCoordConversion.ToScreen(q:x(),q:y(),base+(o:y()+pr.floorY+height)/2.44949)
local hit=MELens.Interact.pick(v,pr,sx,sy);if hit and hit.animal==a.animal then return {x=sx/getCore():getZoom(0),y=sy/getCore():getZoom(0),name=MELens.AnimalsUI.nameOf(a.animal)} end end;error("no animal ray hit")''')
        lab.input('A',x=point['x'],y=point['y'],right=True)
        for label in (point['name'],h.lua('return getText("ContextMenu_PickUpAnimalBody")')):
            option=lab.wait(lambda:h._sequence(h.lua(MENUS)),lambda rows:any(r['name']==label for r in rows),'native menu '+label,timeout=10)
            option=next(r for r in option if r['name']==label);h.check(option['enabled'],'animal pickup menu disabled')
            lab.input('A',x=option['x'],y=option['y']);time.sleep(.2)
        ss=count(0)
        ss=lab.wait(states,lambda ss:ss['A']['carried']==1,'pickup creates exactly one carried hen')
        h.REPORT['nativePickup']=ss
        lab.capture('A','mp-animal-picked-up')
        # A bonded dog at the entrance follows its owner through the normal
        # minute pass. No trailer-membership calls are made by this fixture.
        dog_uid=lab.server('''local v=getVehicleById('''+str(lab.vid)+''');local p;local ps=getOnlinePlayers()
for i=0,ps:size()-1 do if ps:get(i):getUsername()=="MELensAdmin" then p=ps:get(i) end end;assert(p)
local pr=MELens.profileFor(v);local o=v:getScript():getModel():getOffset();local d=pr.standing.outside
local q=v:getWorldPos(o:x()+d[1],0,o:z()+d[3],Vector3f.new());local breed
for b in pairs(AnimalDefinitions.animals.dogmale.breeds) do breed=breed or b end
local dog=IsoAnimal.new(getCell(),math.floor(q:x()),math.floor(q:y()),0,"dogmale",breed);dog:addToWorld()
CompanionDogs.makeCompanion(dog,p);CompanionDogs.transmit(dog);CompanionDogs.regInvalidate()
MELens.Animals.onMinute();return CompanionDogs.ensureUid(dog)''')
        ss=count(1);h.REPORT['dogFollowIn']=ss
        bowl_id=int(lab.server('''local v=getVehicleById('''+str(lab.vid)+''');local A=MELens.Animals;local dog=A.list(v)[1];assert(CompanionDogs.isDog(dog))
local r=A.record(v,dog);CompanionDogs.setNeed(dog,"hunger",.6);CompanionDogs.setNeed(dog,"thirst",.6);r.u=nil
local it=MELens.Loose.floorContainer(v):AddItem("Base.CompanionDogsBowl");it:getModData().cdWater=50;it:getModData().cdFoodMeals=50
MELens.Loose.set(v,it,r.x+.3,MELens.profileFor(v).floorY,r.z,0,0);sendAddItemToContainer(it:getContainer(),it)
for i=1,12 do r.u=nil;A.updateVehicle(v,MELens.profileFor(v));if it:getModData().cdWater<50 and it:getModData().cdFoodMeals<50 then break end end
v:transmitModData();return it:getID()'''))
        def bowl_equal(ss):
            bowls=[[it for it in s['floor'] if it['id']==bowl_id] for s in ss.values()]
            return same_records(ss) and all(len(it)==1 and it[0].get('cdWater',50)<50 and it[0].get('cdFood',50)<50 for it in bowls) and bowls[0]==bowls[1]==bowls[2]
        ss=lab.wait(states,bowl_equal,'dog bowl food and water stocks reach both peers')
        h.check(ss['server']['animals'][0]['hunger']<.6 and ss['server']['animals'][0]['thirst']<.6,'dog bowl failed to relieve needs')
        h.REPORT['dogBowl']=ss
        def exit_actor():
            h.lua('local p=getPlayer();local v=p:getVehicle();local pr=MELens.profileFor(v);MELens.walkTo(p,pr.exitMarker.x,pr.exitMarker.z);return true')
            lab.wait(lambda:h.lua('return not MELens.pathing(getPlayer()) and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0'),bool,'owner at exit marker')
            lab.input('A',key=int(h.lua('return getCore():getKey("Interact")')))
            lab.wait(lambda:h.lua('return getPlayer():getVehicle()==nil'),bool,'native owner E exit')
        lab.server('local v=getVehicleById('+str(lab.vid)+');CompanionDogs.setState(MELens.Animals.list(v)[1],CompanionDogs.STATE_STAY);return "stay"')
        exit_actor();lab.server('MELens.Animals.onMinute();return "minute"');h.REPORT['dogStay']=count(1)
        lab.enter_e('A')
        lab.server('local v=getVehicleById('+str(lab.vid)+');CompanionDogs.setState(MELens.Animals.list(v)[1],CompanionDogs.STATE_FOLLOW);return "follow"')
        exit_actor();lab.server('MELens.Animals.onMinute();return "minute"');ss=count(0)
        h.check(all(not s.get('records') for s in ss.values()),'departed dog left a ghost record')
        h.REPORT['dogFollowOut']=ss
        world_dogs=json.loads(lab.server(driver.JSON_ENCODER+'''CompanionDogs.regInvalidate();local out={}
for _,dog in ipairs(CompanionDogs.regCompanions()) do if dog:getVehicle()==nil then out[#out+1]={uid=CompanionDogs.ensureUid(dog),state=CompanionDogs.getState(dog)} end end;return enc(out)'''))
        h.check(sum(str(d['uid'])==dog_uid and d['state']=='follow' for d in h._sequence(world_dogs))==1,'following dog duplicated or lost its identity outside')
        h.REPORT['dogIdentityOutside']=world_dogs;lab.capture('A','mp-following-dog-outside')
        h.REPORT['unverified']=['server restart persistence','mouse inventory Drop in MP','dog command-menu input (state fixture)']
        h.write_report('passed');(args.session/'request.json').write_text('{"action":"stop"}');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
