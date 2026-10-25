"""Owned SP check of vanilla entry, furniture animation and controls without car mods.

Vehicle spawning, approach positioning and inventory supplies are explicit fixtures.
Entry, furniture menus, getting up, Dashboard and exit use production native input.
"""
import argparse,importlib.util,json,os,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--with-campers',action='store_true');args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    interior,bed=load('final-interior-tests'),load('bed-tests')
    tap,h=interior.load_helpers();h.configure(run/'optional-checks');h.SCREENS=run/'home/Zomboid/Screenshots'
    h.REPORT['scope']=__doc__;h.REPORT['mode']='one optional Camper pack' if args.with_campers else 'ZombieBuddy only'
    def wait(code,condition,label,seconds=35):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            result=h.lua(code)
            if condition(result):return result
            time.sleep(.15)
        raise AssertionError('Timeout '+label+': '+str(result))
    def setup(script):
        bed.enter(h,script,'E')
        h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
        h.REPORT.setdefault('inputCoverage',[]).append('native Interact entry '+script)
    def rest(piece,clip,variable):
        point=h.lua('return MELensInteriorTest.point("'+piece+'")')
        before=interior.choose(h,tap,point,[point['header'],h.lua('return getText("ContextMenu_Rest")')],'rest-'+piece)
        pose=wait('local p=getPlayer();return {standing=MELens.isStanding(p),pose=p:getVariableString("damnPosition"),phase=p:getVariableString("MELensBed"),clip=MELensRV.animationProgress(p,"'+clip+'"),seat=p:getVehicle():getSeat(p)}',
                  lambda s:not s['standing'] and s['pose']==variable and s['clip']>0 and (piece!='stretcher' or s['phase']=='Awake'),'native '+piece+' animation')
        # The production get-up path intentionally ignores movement for 500ms
        # after sitting down. Also let the native seat-switch blend settle.
        time.sleep(1.2)
        settled=h.lua('local p=getPlayer();return {clip=MELensRV.animationProgress(p,"'+clip+'"),alpha=p:getAlpha(0),bones=MEMCNativeLab.animationBones()}')
        pose['settled']=settled
        h.REPORT.setdefault('poses',[]).append(pose)
        h.check(settled['clip']>0 and abs(settled['clip']-pose['clip'])>.001,'chair/bed clip did not advance')
        h.capture('vanilla-'+piece+'-seated')
        key=int(h.lua('return getCore():getKey("Forward")'));h.lua(f'MEMCNativeLab.holdKey({key},180);return true');time.sleep(.7)
        wait('return MELens.isStanding(getPlayer())',bool,'native movement gets up')
        h.REPORT['inputs'].append({'action':'get-up-'+piece,'api':'MEMCNativeLab.holdKey','key':key,'durationMs':180})
        after=interior.read_state(h);h.record('native-'+piece+'-rest-and-get-up',before,after,pose=pose)
    def exit_vehicle():
        h.lua('MELensInteriorTest.positionAtExit();return true')
        wait('return not MELens.pathing(getPlayer())',bool,'exit approach fixture')
        interior.interact_key(h,'native interior exit')
        wait('return getPlayer():getVehicle()==nil',bool,'native exit')
    try:
        mods=h._sequence(h.lua('local a=getActivatedMods();local r={};for i=0,a:size()-1 do r[#r+1]=a:get(i) end;return r'))
        h.REPORT['activeMods']=mods
        expected={'ZombieBuddy','RealVehicleInteriors','RealVehicleInteriors_Dev'}
        if args.with_campers:expected|={'damnlib','KI5campers'}
        h.check(set(mods)==expected,'unexpected active dependencies: '+str(mods))
        availability=h.lua('return {b700=getScriptManager():getVehicle("Base.87fordB700school")~=nil,camper=getScriptManager():getVehicle("Base.Trailer54FlyingCloud22")~=nil,damn=MELens.Parts.hasDamnSeats()}')
        h.check(not availability['b700'] and availability['camper']==args.with_campers and availability['damn']==args.with_campers,'missing packs were implicitly required or enabled')
        h.REPORT['availability']=availability
        setup('Base.VanSeats');h.capture('vanilla-passenger-van-standing')
        rest('medbench','Bob_SatBack_facingLeft' if args.with_campers else 'Bob_SatChair','facingLeft' if args.with_campers else 'MELensSeat')
        point=h.lua('return MELensInteriorTest.point("medbench")')
        before=interior.choose(h,tap,point,[h.lua('return getText("ContextMenu_MELens_Dashboard")')],'core-dashboard')
        after=h.wait_for(lambda s:s.get('dashboard') and bool(s['controls']),label='native Dashboard')
        h.check(h.lua('return MELens.Dashboard.instance.Type')=='MELensVanillaDashboard','core install did not select vanilla UI')
        h.capture('vanilla-core-dashboard');interior.close_dashboard(h,tap);h.record('native-core-dashboard',before,after)
        exit_vehicle();setup('Base.VanAmbulance');h.capture('vanilla-ambulance-standing')
        rest('stretcher','Bob_Awake','MELensBed')
        h.REPORT['savedIdentity']=h.lua('local v=MELensTest.vehicle;local r={sqlId=v:getSqlId(),parts={}};for i=0,v:getPartCount()-1 do local p=v:getPartByIndex(i);r.parts[#r.parts+1]={id=p:getId(),item=p:getInventoryItem() and p:getInventoryItem():getID() or -1} end;return r')
        if args.with_campers:
            exit_vehicle();setup('Base.Trailer54FlyingCloud22');h.capture('optional-camper-standing')
        h.REPORT['passed']=True;h.write_report('passed');print('OPTIONAL_DEPENDENCIES_NATIVE_PASSED',flush=True)
    except BaseException:
        h.REPORT['passed']=False;h.write_report('failed',traceback.format_exc());raise
if __name__=='__main__':main()
