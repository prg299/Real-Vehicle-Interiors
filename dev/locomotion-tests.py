"""Observe native keyboard locomotion and render-time visibility, outside and inside."""
import hashlib,importlib.util,json,os,time,traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    _,h=load('final-interior-tests').load_helpers()
    h.configure(run/'motion');h.SCREENS=run/'home/Zomboid/Screenshots'
    report={'scope':__doc__,'cases':{},'passed':False}
    path=run/'locomotion.json'
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    def sample(label,keys=(),duration=.9):
        codes=[int(h.lua('return getCore():getKey('+json.dumps(name)+')')) for name in keys]
        h.lua('MELensMotionProbe.rows={};MELensMotionProbe.label='+json.dumps(label)+';return true')
        for code in codes:h.lua(f'MEMCNativeLab.holdKey({code},{int(duration*1000)});return true')
        time.sleep(.15)
        h.capture(label+'-a');time.sleep(.15);h.capture(label+'-b')
        time.sleep(max(0,duration-.3));h.lua('MEMCNativeLab.releaseKeys();return true');time.sleep(.4)
        rows=h.lua('local r=MELensMotionProbe.rows;MELensMotionProbe.rows={};return r')
        rows=h._sequence(rows)
        assert rows,'Native sampler failed: '+str(h.lua('return MELensMotionProbe.error'))
        report['cases'][label]={'input':keys,'rows':rows};save()
        if label.startswith('inside-'):
            assert h.lua('return MELens.isStanding(getPlayer())'),'native input unexpectedly left the interior'
        print(label,'frames',len(rows),'alpha',min(row['alpha'] for row in rows),flush=True)
    try:
        package=run/'home/Zomboid/mods/RealVehicleInteriors'
        report['payloadHashes']={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in package.rglob('*') if p.is_file()}
        h.lua('''MELensMotionProbe={rows={},label="setup"}
local T=MELensMotionProbe
 local function collect()
 if #T.rows>=300 then return end
 local p=getPlayer();if not p then return end
 local d=MELens.debugState();local animation=MELensRV.animInfo(p)
 T.rows[#T.rows+1]={t=getTimestampMs(),label=T.label,x=p:getX(),y=p:getY(),alpha=p:getAlpha(0),
 targetAlpha=p:getTargetAlpha(0),pose=d.pose or "",localX=d.x or 0,localZ=d.z or 0,
 moving=p:getVariableBoolean("isMoving"),running=p:isRunning(),sneaking=p:isSneaking(),
 walkSpeed=p:getVariableFloat("WalkSpeed",-1),animation=animation,state=animation:match("state=([^ ]+)"),
 nativeDistance=MELensRV.nativeMovementDistance and MELensRV.nativeMovementDistance(p) or -1,
 animSet=p:GetAnimSetName(),tracks=MELensDevBones.tracks(p)}
end
T.tick=function()
 local ok,err=pcall(collect)
 if not ok then T.error=tostring(err);Events.OnPostRender.Remove(T.tick) end
end
Events.OnPostRender.Add(T.tick);return true''')
        sample('outside-idle',duration=.6)
        sample('outside-walk',('Forward',))
        sample('outside-run',('Forward','Run'))
        load('bed-tests').enter(h,'Base.StepVan','E')
        report['entered']=h.lua('return MELens.isStanding(getPlayer())')
        report['fixture']=h.lua('''local v=MELensTest.vehicle;local q=MELens.profileFor(v);local P=MELens.Parts
local r={removed=0,vehicleId=v:getId(),scope="only this disposable test van; clear floor so feet remain visible"}
for i=1,#q.spots do local part=P.spotPart(v,i)
 if part then if part:getInventoryItem() then r.removed=r.removed+1 end
  local c=part:getItemContainer();if c then c:clear() end
  part:setInventoryItem(nil);P.settle(v,part)
 end
end
return r''')
        time.sleep(1)
        h.lua('MELensMotionProbe.rows={};getCore():setAutoZoom(0,false);return true')
        sample('inside-idle',duration=.6)
        for name,keys in [('walk',('Forward',)),('run',('Backward','Run')),('left',('Left',)),('right',('Right',))]:
            sample('inside-'+name,keys,duration=.65)
        h.lua('Events.OnPostRender.Remove(MELensMotionProbe.tick);return true')
        report['passed']=True;save()
    except Exception as error:
        report['error']=str(error);report['traceback']=traceback.format_exc();save();raise
    finally:
        try:h.lua('MEMCNativeLab.releaseKeys();if MELensMotionProbe then Events.OnPostRender.Remove(MELensMotionProbe.tick) end;return true')
        except Exception:pass

if __name__=='__main__':main()
