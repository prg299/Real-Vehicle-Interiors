"""Dedicated-server native food aging and real Step Van entry/Dashboard input.

Spawn, fresh food, climate and a bounded world-clock advance are fixtures.
Generator switch, entry and inventory selection use production mouse/keyboard.
"""
import argparse, importlib.util, json, time, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT='Base.85chevyStepVan'
def load(name):
    s=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--verify-source',type=Path);p.add_argument('--finish-source',type=Path)
    args=p.parse_args();d=load('final-mp-interior-tests');lab=d.InteriorLab(args.session,args.output);h=lab.h
    h.REPORT.update(scope=__doc__,inputCoverage=[],fixtures=['spawn/repair/furniture only for initial setup','saved native food reused on restart' if args.verify_source else 'fresh native apples','Dashboard/loot window opening','one bounded game-hour advance','native climate override restored'],lootNativeMouseInput=False,lootUsesProductionTransferAction=False)
    def server(code):return json.loads(lab.server(d.JSON_ENCODER+'local r=(function() '+code+' end)();return enc(r)'))
    def snap():return server('return MELensUtilityProbe.snapshot()')
    def peers():
        code=f'local v=getVehicleById({lab.vid});local g=MELens.Utilities.generatorState(v);local c=MELens.Parts.spotPart(v,4):getItemContainer();return {{on=g.on,fuel=g.fuel,temperature=c:getTemperature(),fridge=c:isFridge(),powered=c:isPowered()}}'
        return {'A':h.lua(code),'B':lab.b.lua(code),'server':snap()}
    def switch(on):
        h.lua('ISUIHandler.setVisibleAllUI(true);MELens.Dashboard.open(getPlayer(),MELensTest.vehicle);local w=MELens.Dashboard.instance;w:setX(30);w:setY(25);return true')
        def control():return h.lua('local w=MELens.Dashboard.instance;for _,c in ipairs(w.controls) do if c.fn==w.onGenerator then return {enabled=c.enabled,x=w:getAbsoluteX()+c.x+c.w/2,y=w:getAbsoluteY()+c.y+c.h/2} end end')
        c=lab.wait(control,lambda c:c and c['enabled'],'native generator button')
        lab.input('A',x=c['x'],y=c['y'])
        result=lab.wait(peers,lambda s:all(v['on']==on and abs(v['temperature']-(.2 if on else 1))<.001 for v in s.values()),'power/temperature on both clients and server')
        title=h.lua('return getText("'+('ContextMenu_Turn_Off' if on else 'ContextMenu_Turn_On')+'")')
        lab.wait(lambda:h.lua('local w=MELens.Dashboard.instance;for _,c in ipairs(w.controls) do if c.fn==w.onGenerator then return c.nativeButton and c.nativeButton.title or (c.button and c.button.text) end end'),lambda value:value==title,'rendered generator control reflects committed state')
        time.sleep(.2)
        h.REPORT.setdefault('switches',[]).append(result);return result
    def finish():
        h.lua('if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end;local page=getPlayerLoot(0);page:setVisible(true);page:refreshBackpacks();return true')
        point=h.lua('local p=getPlayerLoot(0);return {x=p:getAbsoluteX()+80,y=p:getAbsoluteY()+8}')
        lab.input('A',x=point['x'],y=point['y']);time.sleep(.6)
        pin=h.lua('local b=getPlayerLoot(0).pinButton;return b:isVisible() and {x=b:getAbsoluteX()+b:getWidth()/2,y=b:getAbsoluteY()+b:getHeight()/2}')
        if pin:lab.input('A',x=pin['x'],y=pin['y']);time.sleep(.6)
        def fridge_button():return h.lua('local page=getPlayerLoot(0);local c=MELens.Parts.spotPart(MELensTest.vehicle,4):getItemContainer();for _,b in ipairs(page.backpacks) do if b.inventory==c then return {x=b:getAbsoluteX()+b:getWidth()/2,y=b:getAbsoluteY()+b:getHeight()/2} end end')
        button=lab.wait(fridge_button,lambda b:b is not None,'actual fridge inventory button')
        lab.input('A',x=button['x'],y=button['y']);time.sleep(.6)
        def cold_inventory():return h.lua('local c=MELens.Parts.spotPart(MELensTest.vehicle,4):getItemContainer();local page=getPlayerLoot(0);local heats={};for i=0,c:getItems():size()-1 do local item=c:getItems():get(i);if instanceof(item,"Food") then heats[#heats+1]=item:getHeat() end end;return {selected=page.inventoryPane.inventory==c,heats=heats}')
        shown=lab.wait(cold_inventory,lambda s:s['selected'] and h._sequence(s['heats']) and max(h._sequence(s['heats']))<.3,'native cold-food inventory')
        h.REPORT['nativeFridgeInventory']=shown;lab.capture('A','step-van-cold-food-inventory')
        h.REPORT['inputCoverage'].append('native loot title/pin and fridge container selection')
        overlap=server('return MELensUtilityProbe.overlap()');h.check(abs(overlap['after']-overlap['before'])<.005,'overlapping callbacks double bill time');h.REPORT['overlap']=overlap
        rain=server('return MELensUtilityProbe.rain()');h.check(rain['water']==20 and not rain['tainted'],'rain taints potable storage');h.REPORT['rain']=rain
        switch(False);switch(True)
        lab.capture('A','step-van-fridge-running');h.REPORT['saved']=snap();h.REPORT['status']='passed'
    try:
        if args.finish_source:
            previous=json.loads(args.finish_source.read_text());h.REPORT=previous
            h.REPORT.pop('error',None);h.REPORT.pop('traceback',None);h.REPORT['status']='running'
            h.REPORT['continuedFrom']=str(args.finish_source)
            lab.vid=previous['nativeFoodAging']['after']['id'];finish();return
        for api in (h,lab.b):
            api.lua('if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end;ISUIHandler.setVisibleAllUI(false);local p=getPlayer();if p:getVehicle() then MELens.leave(p) end;return true')
        lab.wait(lambda:h.lua('return getPlayer():getVehicle()==nil') and lab.b.lua('return getPlayer():getVehicle()==nil'),bool,'both players outside prior vehicle')
        lab.position_players_at_field()
        if args.verify_source:
            old=json.loads(args.verify_source.read_text());expected=old['saved']
            lab.vid=lab.wait(lambda:int(lab.server('local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next();if v:getSqlId()=='+str(expected['sqlId'])+' then return tostring(v:getId()) end end;return "-1"')),lambda n:n>=0,'saved Step Van')
        else:
            positions=server('local rows={};local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next();rows[#rows+1]={x=v:getX(),y=v:getY()} end;return rows')
            candidates=d.clear_spawn_candidates(h._sequence(positions));h.check(candidates,'no clear spawn point')
            x,y=candidates[0]
            h.lua(f"SendCommandToServer('/addvehicle {SCRIPT} {x},{y},0');return true")
            lab.vid=lab.wait(lambda:int(lab.server('local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next();if v:getScriptName()=="'+SCRIPT+'" then return tostring(v:getId()) end end;return "-1"')),lambda n:n>=0,'Step Van spawn')
            lab.server(f'local v=getVehicleById({lab.vid});v:repair();for i=0,v:getPartCount()-1 do local p=v:getPartByIndex(i);if p:getDoor() then p:getDoor():setLocked(false);v:transmitPartDoor(p) end end;for i in ipairs(MELens.profileFor(v).spots) do local p=MELens.Parts.spotPart(v,i);if p:getItemContainer() then p:getItemContainer():clear() end;p:setInventoryItem(nil);MELens.Parts.applyPiece(v,p);v:transmitPartItem(p) end;local p=MELens.Parts.spotPart(v,4);p:setInventoryItem(instanceItem(MELens.Parts.itemType("fridge")));MELens.Parts.applyPiece(v,p);v:transmitPartItem(p);local g=MELens.Utilities.generatorState(v).part;g:getModData().fuel=18;g:getModData().on=false;g:setCondition(100);MELens.Utilities.transmit(v,g);return "ready"')
        for api in (h,lab.b):lab.wait(lambda api=api:api.lua(f'return getVehicleById({lab.vid})~=nil'),bool,'Step Van peer replication')
        lab.server((ROOT/'dev/lua/utility-refrigeration.lua').read_text()+f';MELensUtilityProbe.bind(getVehicleById({lab.vid}));return "probe ready"')
        h.REPORT['phantomStove']=server('return MELensUtilityProbe.phantomStove()')
        if args.verify_source:
            actual=snap();h.REPORT['restart']={'expected':expected,'actual':actual}
            h.check(actual['sqlId']==expected['sqlId'] and actual['fridgeId']==expected['fridgeId'] and actual['parts']==expected['parts'],'restart changed vehicle/furniture/part identifiers')
            h.check(actual['on']==expected['on'] and actual['water']==expected['water'] and actual['tainted']==expected['tainted'],'restart changed utility state')
            h.check([f['id'] for f in h._sequence(actual['foods'])]==[f['id'] for f in h._sequence(expected['foods'])],'restart changed food identity')
            h.check(abs(actual['fuel']-expected['fuel'])<.08,'restart unexpected fuel debit')
            h.REPORT['restart']={'expected':expected,'actual':actual}
        lab.enter_e('A');h.REPORT['inputCoverage'].append('native Interact entry into KI5 Step Van')
        if snap()['on']:switch(False)
        switch(True);lab.capture('A','step-van-generator-powered')
        before=server('return MELensUtilityProbe.foodControls()')
        h.check(before['powered'] and before['fridge'],'native food does not recognize powered custom fridge')
        unchanged=snap();h.check(abs(unchanged['fuel']-before['fuel'])<.003,'unchanged-input fuel control changed')
        h.REPORT['unchangedControl']={'before':before,'after':unchanged}
        hours=server('return MELensUtilityProbe.advance(1)')
        lab.wait(lambda:snap(),lambda s:s['hours']>=hours,'server clock advance')
        lab.wait(snap,lambda s:before['fuel']-s['fuel'] >= (s['hours']-before['hours'])*before['rate']-.015,'native generator callback accounts advanced interval',timeout=45)
        after=server('return MELensUtilityProbe.ageControls()')
        h.check(before['gridElectricity']==after['gridElectricity'],'food advice changed world power')
        foods=h._sequence(after['foods']);prior={f['id']:f for f in h._sequence(before['foods'])}
        cold=next(f for f in foods if f['id']==before['controlColdId']);warm=next(f for f in foods if f['id']==before['controlWarmId'])
        cd,wd=cold['age']-prior[cold['id']]['age'],warm['age']-prior[warm['id']]['age']
        h.check(wd>.001 and 0<=cd<wd*.5 and cold['heat']<.3,'native powered fridge does not preserve/cool actual food')
        elapsed=after['hours']-before['hours'];used=before['fuel']-after['fuel']
        h.check(abs(used-elapsed*before['rate'])<.015,'native elapsed-time fuel use differs from actual appliance rate')
        h.REPORT['nativeFoodAging']={'before':before,'after':after,'coldAgeDelta':cd,'warmAgeDelta':wd,'fuelUsed':used,'elapsedHours':elapsed}
        finish()
    except BaseException as e:
        h.REPORT.update(status='failed',error=str(e),traceback=traceback.format_exc());raise
    finally:
        h.REPORT['finishedAt']=time.time();(args.output/'native-feature-tests.json').write_text(json.dumps(h.REPORT,indent=2))
if __name__=='__main__':main()
