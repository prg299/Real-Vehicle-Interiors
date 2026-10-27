"""Prepare a labelled stress fixture on the copied old2.0.20 world.

Never call on an original/player save. The parent runs this inside its
guarded old-package lifetime. Existing StepVan SQL6 is observed, never repaired,
removed, repositioned or seeded. Only the newly spawned F350 is modified.
Then run the promoted baseline verifier in this SAME already-running session.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import sys
import time
import traceback


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--copied-world-setup', required=True, action='store_true')
    p.add_argument('--world', default='melens-test-1793063756')
    p.add_argument('--case-output', required=True, type=Path)
    p.add_argument('--baseline', required=True, type=Path)
    p.add_argument('--package-receipt', required=True, type=Path)
    p.add_argument('--with-fridge', action='store_true', help='Add fridge4 and nested bag/marker on the NEW F350 only')
    p.add_argument('--candidate-version', default='2.0.21')
    p.add_argument('--baseline-output-name', default='upgrade-preservation')
    a = p.parse_args()
    root = a.root.resolve()
    artifacts = (root/'build/rv').resolve()
    run = (artifacts/os.environ['RVI_CAPTURE_RUN']).resolve()
    assert run.is_relative_to(artifacts) and run != artifacts
    assert a.world.startswith('melens-test-') and a.world.removeprefix('melens-test-').isdigit()
    for path in (a.case_output, a.baseline, a.package_receipt):
        assert path.suffix == '.json' and path.resolve().is_relative_to(artifacts)
    assert not a.case_output.exists() and not a.baseline.exists(), 'Never rerun/overwrite fixture evidence'
    receipt = json.loads(a.package_receipt.read_text('utf-8-sig'))
    assert receipt['version'] == '2.0.20' and len(receipt['packageSha256']) == 64
    verifier = root/'dev/final-upgrade-preservation.py'
    assert verifier.is_file(), 'Root must review/promote baseline verifier first'

    def load(name):
        spec = importlib.util.spec_from_file_location('old20_'+name.replace('-', '_'), root/'dev'/(name+'.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    h = load('final-feature-tests')
    h.configure(run/'old20-setup')
    h.ENDPOINT = 'http://127.0.0.1:18470/lua?depth=16&sandbox=false'
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    cache = Path(next(v.split('=', 1)[1] for v in session['command'] if v.startswith('-cachedir='))).resolve()
    assert cache.is_relative_to(artifacts), 'Only explicitly copied checkout-owned native profile'
    h.SCREENS = cache/'Screenshots'
    assert not (h.OUTPUT/'prepared.json').exists(), 'Prepared fixture already recorded'
    legacy = load('interior-lifecycle-tests').SNAPSHOT.replace('MELensLifecycle.vehicle', 'MELensOld20Setup.original')
    # Match the promoted inspector's correction: transient native seat capacity
    # can dereference an absent owner during reload. Preserve seat items/IDs;
    # exact cargo/furniture capacities remain in the old shared snapshot.
    legacy, replacements = re.subn(r'local capacity=[^\n]*',
        'local capacity=c and not part:getId():find("^Seat") and c:getCapacity() or nil', legacy)
    assert replacements == 1, 'Shared snapshot capacity contract changed; review before use'
    step_snapshot = '''local r=(function()\n''' + legacy + '''\nend)()
local v=MELensOld20Setup.original;local order={}
for i=0,v:getPartCount()-1 do order[#order+1]=v:getPartByIndex(i):getId() end
local floor=v:getPartById("MELensFloor");local d=floor and floor:getModData() or {}
r.partOrder=order;r.loose=d.loose;r.tumbles=d.tumbles;r.propane=v:getModData().MELensPropane
return r'''

    def wait(code, seconds=40):
        deadline = time.monotonic()+seconds
        while not h.lua(code):
            h.check(time.monotonic()<deadline, 'bounded old20 fixture wait: '+code)
            time.sleep(.15)

    try:
        h.REPORT.update(scope=__doc__,preparedCopiedWorldStressFixture=True,
                        untouchedUserDataClaim=False,setupMutations=['NEW F350 only: spawn/repair/unlock',
                        'NEW F350 only: old-frame loose Bandage on default medlocker7',
                        'NEW F350 only: nonzero quiescent utilities, deliberate cleared legacy base3',
                        'NEW F350 only: optional fridge4 with nested inventory marker', 'saveGame API'],
                        nativeInput=False,world=a.world)
        h.check(h.lua('return getWorld():getWorld()') == a.world, 'Wrong copied source world')
        h.check(h.lua('return MELensRV.version()') == '2.0.20', 'Must run exact OLD2.0.20 bridge')
        # SQL6 is supplied by root's read-only DB discovery, not a network ID.
        h.REPORT['existingVehiclesBefore'] = h.lua('''local out={};local original
local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next()
out[#out+1]={sqlId=v:getSqlId(),networkId=v:getId(),script=v:getScriptName(),x=v:getX(),y=v:getY(),z=v:getZ()}
if v:getSqlId()==6 then assert(v:getScriptName()=="Base.StepVan","SQL6 script mismatch");original=v end
end
assert(original,"Retained StepVan SQL6 must be loaded; do not replace it")
assert(math.abs(original:getX()-10801)<2 and math.abs(original:getY()-10139)<2,"SQL6 differs from discovered source position")
assert(not MELensOld20Setup,"Setup selector already exists; preserve partial evidence")
MELensOld20Setup={original=original};return out''')
        before = h.lua(step_snapshot)
        h.REPORT['untouchedStepVanBefore'] = before
        # No spawn_one.lua, no old vehicle selector, no scene/vegetation removal.
        # The pad must actually be clear rather than silently moving old cars.
        h.REPORT['spawn'] = h.lua('''local x,y=10817,10140
local sq=assert(getCell():getGridSquare(x,y,0),"F350 pad not streamed")
local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next()
assert((v:getX()-x)^2+(v:getY()-y)^2>49,"F350 pad occupied; preserve existing vehicles") end
local script=assert(getScriptManager():getVehicle("Base.90fordF350ambulance"))
local prior=script:neverSpawnKey();script:Load(script:getName(),"{ neverSpawnKey = true, }")
local ok,v=pcall(addVehicleDebug,"Base.90fordF350ambulance",IsoDirections.N,0,sq)
script:Load(script:getName(),"{ neverSpawnKey = "..tostring(prior)..", }")
assert(ok and v,"Old addVehicleDebug failed")
assert(v:getScriptName()=="Base.90fordF350ambulance")
MELensOld20Setup.f350=v
v:getModData().RVIUpgradePreparedStressFixture="old2.0.20-copy-only/F350-shelf-edge"
v:repair()
for i=0,v:getPartCount()-1 do local door=v:getPartByIndex(i):getDoor();if door then door:setLocked(false) end end
return {script=v:getScriptName(),networkId=v:getId(),x=v:getX(),y=v:getY(),z=v:getZ() }''')
        wait('''local v=MELensOld20Setup.f350;local P=MELens.Parts
local a,b=P.spotPart(v,7),P.spotPart(v,8)
return a and b and P.pieceAt(a)=="medlocker" and P.pieceAt(b)=="medlocker" and v:getPartById(P.FLOOR)~=nil''')
        h.REPORT['prepared'] = h.lua('''local v=MELensOld20Setup.f350;local M,P,L=MELens,MELens.Parts,MELens.Loose
local pr=assert(M.profileFor(v));local s7=assert(pr.spots[7]);local s8=assert(pr.spots[8])
assert(s7.wall=="front" and s8.wall=="front" and math.abs(s7.z+.4)<.00001 and math.abs(s8.z+.4)<.00001,"Old profile front-shelf contract missing")
local part7,part8=P.spotPart(v,7),P.spotPart(v,8)
local id7,id8=part7:getInventoryItem():getID(),part8:getInventoryItem():getID()
local floor=assert(v:getPartById(P.FLOOR));local c=assert(floor:getItemContainer())
local item=assert(c:AddItem("Base.Bandage"));local x,y,z=s7.x,pr.floorY+.383,-.46
local cx,cy,cz,cr,cs=L.checked(v,x,y,z,0,7)
assert(cx and cs==7 and math.abs(cy-y)<.00001,"Old edge centre not supported by medlocker7")
assert(L.set(v,item,x,y,z,0,7)==floor,"Old Loose.set failed")
local entry=assert(floor:getModData().loose[tostring(item:getID())]);assert(entry.z==z and entry.s==7)
local g=assert(v:getPartById(P.GENERATOR));g:getModData().fuel=7.25;g:getModData().on=false;g:setCondition(73)
local w=assert(v:getPartById(P.WATER));w:getModData().water=11.5;w:getModData().tainted=true
v:getModData().MELensPropane=.33;v:getModData().MELensLightsOff=true
local clear=assert(P.spotPart(v,3));local old=clear:getInventoryItem();local installedForClear
-- Old released base3 normally starts empty. Make an explicit install/clear
-- stress fixture on this NEW vehicle so initialized=true is intentional.
if not old then
 assert(P.fits(pr.spots[3],"kitchen"),"Base3 cannot hold temporary kitchen")
 old=assert(instanceItem(P.itemType("kitchen")));clear:setInventoryItem(old);P.applyPiece(v,clear);installedForClear=true
end
local removedId=old:getID();local cc=clear:getItemContainer();if cc then cc:clear() end
clear:setInventoryItem(nil);clear:getModData()[P.INITIALIZED_KEY]=true;P.applyPiece(v,clear)
assert(not clear:getInventoryItem() and clear:getModData()[P.INITIALIZED_KEY]==true)
assert(part7:getInventoryItem():getID()==id7 and part8:getInventoryItem():getID()==id8,"Default front-slot identities changed")
return {looseItemId=item:getID(),looseRaw=entry,slot7ItemId=id7,slot8ItemId=id8,
slot7={x=s7.x,z=s7.z,wall=s7.wall},slot8={x=s8.x,z=s8.z,wall=s8.wall},
generator={fuel=g:getModData().fuel,on=g:getModData().on,condition=g:getCondition()},
water={water=w:getModData().water,tainted=w:getModData().tainted},propane=v:getModData().MELensPropane,
clearedPart=clear:getId(),removedSetupItemId=removedId,temporaryPieceInstalledForClear=installedForClear or false}''')
        if a.with_fridge:
            h.REPORT['prepared']['fridge'] = h.lua('''local v=MELensOld20Setup.f350;local P=MELens.Parts;local pr=MELens.profileFor(v)
local part=assert(P.spotPart(v,4));assert(not part:getInventoryItem(),"Retain existing base4 item")
assert(P.fits(pr.spots[4],"fridge"),"Base4 does not fit fridge")
part:setInventoryItem(assert(instanceItem(P.itemType("fridge"))));part:getModData()[P.INITIALIZED_KEY]=true;P.applyPiece(v,part)
local c=assert(part:getItemContainer());local bag=assert(c:AddItem("Base.Bag_DuffelBag"))
assert(instanceof(bag,"InventoryContainer"));local marker=assert(bag:getInventory():AddItem("Base.Screwdriver"))
return {part=part:getId(),installedItemId=part:getInventoryItem():getID(),capacity=c:getCapacity(),bagId=bag:getID(),nestedMarkerId=marker:getID()}''')
        after = h.lua(step_snapshot)
        h.REPORT['untouchedStepVanAfterSetup'] = after
        h.check(after == before, 'Setup changed retained StepVan SQL6 state')
        h.lua('saveGame();return true')
        wait('return MELensOld20Setup.f350:getSqlId()>0')
        identity = h.lua('''local v=MELensOld20Setup.f350;local old=MELensOld20Setup.original
return {f350={sqlId=v:getSqlId(),script=v:getScriptName(),position={x=v:getX(),y=v:getY(),z=v:getZ()}},
original={sqlId=old:getSqlId(),script=old:getScriptName(),position={x=old:getX(),y=old:getY(),z=old:getZ()}}}''')
        h.check(identity['original']['sqlId']==6 and identity['f350']['sqlId']!=6, 'Saved SQL identities invalid')
        identity['original']['clearedParts'] = []
        identity['f350']['clearedParts'] = [h.REPORT['prepared']['clearedPart']]
        case = dict(copyOnly=True,sourceVersion='2.0.20',candidateVersion=a.candidate_version,world=a.world,
                    requireNonzeroUtilities=False,vehicles=[identity['original'],identity['f350']],
                    provenance='SQL6 retained old world; NEW F350 is explicitly prepared stress fixture on copied old2.0.20 world')
        a.case_output.parent.mkdir(parents=True,exist_ok=True)
        a.case_output.write_text(json.dumps(case,indent=2)+'\n',encoding='utf-8')
        h.REPORT.update(savedSqlIdentities=identity,caseOutput=str(a.case_output),copiedWorldSaveRequested=True,
                        beforeAndAfterOriginalStepVanIdentical=True)
        (h.OUTPUT/'prepared.json').write_text(json.dumps(h.REPORT,indent=2)+'\n',encoding='utf-8')
        h.write_report('passed')
    except Exception:
        h.write_report('failed',traceback.format_exc())
        return 1
    # Root's already-reviewed verifier owns its own snapshot report; no changes
    # to that live file and no second game launch. Preserve this setup receipt.
    previous = sys.argv[:]
    try:
        sys.argv = [str(verifier),'--root',str(root),'--case',str(a.case_output),
                    '--mode','baseline','--baseline',str(a.baseline),'--package-receipt',str(a.package_receipt),
                    '--output-name',a.baseline_output_name]
        try:
            runpy.run_path(str(verifier),run_name='__main__')
            code = 0
        except SystemExit as error:
            code = error.code if isinstance(error.code,int) else (0 if error.code is None else 1)
        (run/'old20-setup/baseline-handoff.json').write_text(json.dumps(dict(
            sameNativeSession=True,verifier=str(verifier),exitCode=code,baseline=str(a.baseline)),indent=2)+'\n')
        return code
    finally:
        sys.argv = previous


if __name__=='__main__':
    raise SystemExit(main())
