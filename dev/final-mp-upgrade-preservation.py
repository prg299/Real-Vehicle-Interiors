"""Verify old2.0.20 -> candidate preservation of one existing stocked MP camper.

Root owns the guarded server/two-client lifetime. No spawn, repair, inventory
seeding, persistent vehicle markers, server/client launch or save editing. Reads
use the existing MP harness. Both clients exercise real native E entry/reentry.
The parent must run the complete lifetime through the shared test coordinator.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import time
import traceback


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('baseline','verify'))
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--session',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--baseline',required=True,type=Path)
    p.add_argument('--package-receipt',required=True,type=Path)
    p.add_argument('--script',default='Base.Trailer54FlyingCloud22')
    p.add_argument('--restore-standing-source',type=Path,
                   help='Explicit failed read-baseline whose original standing occupants should be restored with native entry')
    a=p.parse_args()
    root=a.root.resolve();artifacts=(root/'build/rv').resolve()
    for path in (a.session,a.output,a.baseline,a.package_receipt):
        assert path.resolve().is_relative_to(artifacts)
    assert a.baseline.suffix=='.json' and a.package_receipt.suffix=='.json'
    metadata=json.loads((a.session/'session.json').read_text('utf-8-sig'))
    assert metadata.get('resumed') and metadata.get('serverJava') is True
    assert metadata.get('inactiveDesktops') and metadata.get('stockClientClasses')
    receipt=json.loads(a.package_receipt.read_text('utf-8-sig'))
    assert len(receipt['packageSha256'])==64
    expected=None
    if a.mode=='baseline':
        assert not a.baseline.exists(),'Never overwrite the old-package baseline'
        assert receipt['version']=='2.0.20'
    else:
        expected=json.loads(a.baseline.read_text('utf-8-sig'))
        assert expected['status']=='passed' and expected['script']==a.script
        assert Path(metadata['resumeFrom']).resolve()==Path(expected['session']).resolve(), 'Candidate must resume the actual closed old-baseline lifetime'

    def load(name):
        spec=importlib.util.spec_from_file_location('upgrade_'+name.replace('-','_'),root/'dev'/(name+'.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

    mp=load('final-mp-interior-tests')
    persistence=load('final-mp-persistence')
    # Reuse its pure comparator without its constructor's no-Java-only gate or
    # its capture method's persisted marker/quiescence fixture writes.
    persistence.SCRIPTS={'camper':a.script}
    compare=object.__new__(persistence.Persistence);compare.tolerances={}
    lab=mp.InteriorLab(a.session,a.output);h=lab.h;compare.h=h
    h.ENDPOINT=h.ENDPOINT.replace('depth=8','depth=16')
    lab.b.ENDPOINT=lab.b.ENDPOINT.replace('depth=8','depth=16')
    h.REPORT.update(scope=__doc__,mode=a.mode,fixtures=['native queued approach to existing entry','MELens.walkTo exit-marker approach'],
                    noInventoryOrVehicleSetup=True,sourceVersion='2.0.20',packageReceipt=receipt,
                    unverified=['Steam transport','Save/Continue menu input','same-world driving','nonzero MP utilities if source values are zero',
                                'Native battery charge changes with ordinary old-release game time; identity/type retained, charge excluded'])

    def server(code):
        return json.loads(lab.server(mp.JSON_ENCODER+'local r=(function() '+code+' end)();return enc(r)'))

    def write():
        (a.output/'upgrade-state.json').write_text(json.dumps(h.REPORT,indent=2)+'\n',encoding='utf-8')

    def equal(before,after,label):
        errors=compare.differences(before,after)
        if errors:h.REPORT.setdefault('differences',{})[label]=errors;write()
        h.check(not errors,label+': '+json.dumps(errors))

    try:
        # Network IDs may change on cold load. Discover the actual persisted SQL
        # authority and map its CURRENT network ID to the two actual clients.
        target=server('''local found;local it=getCell():getVehicles():iterator()
while it:hasNext() do local v=it:next();if v:getScript():getFullName()==SCRIPT then
assert(not found,"More than one requested script; require an explicit qualified target")
found={sqlId=v:getSqlId(),networkId=v:getId(),script=v:getScript():getFullName(),x=v:getX(),y=v:getY(),z=v:getZ()} end end
assert(found and found.sqlId>0,"Existing saved camper SQL identity unavailable; do not spawn")
return found'''.replace('SCRIPT',json.dumps(a.script)))
        if expected:equal(expected['sqlId'],target['sqlId'],'persisted server SQL identity')
        lab.vid=int(target['networkId']);h.REPORT['target']=target
        for side,api in (('A',h),('B',lab.b)):
            h.check(api.lua('return MELensRV.version()')==receipt['version'],side+' Java release mismatch')
        h.check(server('return MELensRV.version()')==receipt['version'],'server Java release mismatch')
        if a.restore_standing_source:
            assert a.mode=='baseline' and a.restore_standing_source.resolve().is_relative_to(artifacts)
            prior=json.loads(a.restore_standing_source.read_text('utf-8-sig'))
            assert prior['target']['sqlId']==target['sqlId']
            h.REPORT['restoreStandingSource']=str(a.restore_standing_source)
            for side,name,api in (('A','MELensAdmin',h),('B','MELensGuest',lab.b)):
                role=prior['first']['server']['players'][name]['role']
                assert role['vehicle']=='camper' and role['standing']
                if not api.lua('return getPlayer():getVehicle()~=nil'):lab.enter_e(side)
        # Adapt only the reusable read projection: transient selection is local,
        # no modData marker is created, copied or required.
        code=persistence.SNAPSHOT.replace('TOKEN','not-persisted-upgrade-selection')
        code=code.replace('it:getUsedDelta()','it:getCurrentUsesFloat()')
        old='local mark=v:getModData()[key]'
        assert code.count(old)==1
        code=code.replace(old,'local mark=selected(v) and {token=token,label="camper"} or nil')
        old='local mark=v and v:getModData()[key]'
        assert code.count(old)==1
        code=code.replace(old,'local mark=selected(v) and {token=token,label="camper"} or nil')
        old='stable.parts[id]={condition=part:getCondition(),installed=installed(part:getInventoryItem()),contents=items(part:getItemContainer())}'
        assert code.count(old)==1
        code=code.replace(old,'''local c=part:getItemContainer();local own=id:find("^MELens") or id:find("^SeatMELens")
local installedItem=installed(part:getInventoryItem());if installedItem and not own then installedItem.condition=nil end
-- Native battery charge can drain while the old game/server clock runs. Its
-- installed identity and item type remain covered; cabin inventory uses do not
-- receive this exception. No battery is refilled or normalized by this test.
if id=="Battery" and installedItem then installedItem.delta=nil end
stable.parts[id]={condition=own and part:getCondition() or false,installed=installedItem,contents=items(c),
capacity=c and not id:find("^Seat") and c:getCapacity() or false,
initialized=part:getModData()[P.INITIALIZED_KEY] or false}''')
        old='r.vehicles[mark.label]={networkId='
        assert code.count(old)==1
        code=code.replace(old,'''stable.factoryLayout=v:getModData().MELensFactoryLayout or false
stable.floorTumbles=floor and floor:getModData().tumbles or false
r.vehicles[mark.label]={networkId=''')
        code=('local function selected(v) return v and v:getId()=='+str(lab.vid)+
              ' and v:getScript():getFullName()=='+json.dumps(a.script)+' end\n')+code

        def snapshot(side):
            if side=='server':
                state=server(code)
            else:state=(h if side=='A' else lab.b).lua(code)
            for v in state.get('vehicles',{}).values():v['payload']['partOrder']=h._sequence(v['payload'].get('partOrder'))
            return state

        def snapshots():return {s:snapshot(s) for s in ('server','A','B')}

        # Lazy-container refresh is observation; no AddItem/transfer is called.
        refresh='local v=getVehicleById('+str(lab.vid)+');assert(v);local n=0;for i=0,v:getPartCount()-1 do local c=v:getPartByIndex(i):getItemContainer();if c then c:requestServerItemsForContainer();n=n+1 end end;return n'
        h.REPORT['containerObservationRequests']={s:api.lua(refresh) for s,api in (('A',h),('B',lab.b))}
        states=lab.wait(snapshots,lambda ss:not compare.replica_differences(ss),'old camper data replicated on server and both clients',timeout=90)
        h.REPORT['first']=states;write()
        authority=states['server'];payload=authority['vehicles']['camper']['payload']
        u=payload['utilities']
        h.check(not authority['vehicles']['camper']['engine'] and not u['generatorOn'] and not u['stoveOn'] and not u['heaterOn'] and u['ovenHeat']<=1.001,
                'Unsupported exact baseline: source is consuming utilities or has hot oven; no state reset is permitted')
        h.REPORT['nonzeroUtilityCoverage']={k:u[k]>0 for k in ('generatorFuel','water','propane')}
        if expected:
            equal(expected['payload'],payload,'candidate cold-load vehicle payload')
            for name in ('MELensAdmin','MELensGuest'):
                equal(expected['players'][name]['inventory'],authority['players'][name]['inventory'],name+' cold-load inventory')
                equal(expected['players'][name]['role'],authority['players'][name]['role'],name+' cold-load membership')
        # Preserve cold-loaded standing membership as well as outside players.
        # Native exit/entry below restore it; no seat injection or forced exit.
        for name in ('MELensAdmin','MELensGuest'):
            role=authority['players'][name]['role']
            h.check(role['vehicle'] is False or (role['vehicle']=='camper' and role['standing']),
                    name+' unsupported saved seated/foreign-vehicle membership')

        def stable_check(label):
            ss=lab.wait(snapshots,lambda x:not compare.replica_differences(x),label+' peer convergence',timeout=45)
            equal(payload,ss['server']['vehicles']['camper']['payload'],label+' unchanged vehicle')
            for name in ('MELensAdmin','MELensGuest'):
                equal(authority['players'][name]['inventory'],ss['server']['players'][name]['inventory'],label+' '+name+' inventory')
            h.REPORT.setdefault('inputCheckpoints',{})[label]=ss;write()
            return ss

        def exit_e(side):
            api=h if side=='A' else lab.b
            api.lua('''local p=getPlayer();assert(p:getVehicle() and p:getVehicle():getId()==VID)
assert(MELens.isStanding(p),"Only actual standing exit is supported")
local m=assert(MELens.profileFor(p:getVehicle()).exitMarker);MELens.walkTo(p,m.x,m.z);return true'''.replace('VID',str(lab.vid)))
            lab.wait(lambda:api.lua('return not MELens.pathing(getPlayer()) and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0'),bool,side+' exit marker approached',timeout=40)
            lab.input(side,key=int(api.lua('return getCore():getKey("Interact")')),milliseconds=350)
            lab.wait(lambda:api.lua('return getPlayer():getVehicle()==nil'),bool,side+' native E exit',timeout=40)

        for side,name in (('A','MELensAdmin'),('B','MELensGuest')):
            if authority['players'][name]['role']['vehicle']=='camper':
                exit_e(side);stable_check(side+'-initial-occupied-exit')
        # One client at a time avoids claiming direct handler or seat injection
        # as input. The existing approach helper queues native pathfinding.
        for side in ('A','B'):
            for cycle in (1,2):
                lab.enter_e(side)
                api=h if side=='A' else lab.b
                lab.wait(lambda:api.lua('return MELens.isStanding(getPlayer()) and not MELens.pathing(getPlayer())'),bool,side+' standing after native E',timeout=40)
                stable_check(side+'-entry-'+str(cycle))
                if cycle==2:lab.capture(side,'upgrade-'+side.lower()+'-existing-camper-reentered')
                exit_e(side);stable_check(side+'-exit-'+str(cycle))
        for side,name in (('A','MELensAdmin'),('B','MELensGuest')):
            if authority['players'][name]['role']['vehicle']=='camper':
                lab.enter_e(side)
                api=h if side=='A' else lab.b
                lab.wait(lambda:api.lua('return MELens.isStanding(getPlayer()) and not MELens.pathing(getPlayer())'),bool,
                         side+' restored saved standing membership',timeout=40)
        final=stable_check('final')
        for name in ('MELensAdmin','MELensGuest'):
            equal(authority['players'][name]['role'],final['server']['players'][name]['role'],name+' final saved membership')
        h.REPORT.update(nativeInput=True,dataPersistenceVerified=True,bothClientsNativeEntryExitReentry=True,
                        physicalSaveMenuInput=False,renderBindingEqualityRequired=False)
        h.write_report('passed');write()
        if a.mode=='baseline':
            a.baseline.parent.mkdir(parents=True,exist_ok=True)
            a.baseline.write_text(json.dumps(dict(status='passed',sourceVersion='2.0.20',session=str(a.session.resolve()),
                script=a.script,sqlId=target['sqlId'],payload=payload,players=authority['players'],packageReceipt=receipt),indent=2)+'\n',encoding='utf-8')
        return 0
    except Exception:
        h.write_report('failed',traceback.format_exc());write();return 1
    finally:
        for api in (h,lab.b):
            try:api.lua('MEMCNativeLab.releaseKeys();return true')
            except Exception:pass


if __name__=='__main__':raise SystemExit(main())
