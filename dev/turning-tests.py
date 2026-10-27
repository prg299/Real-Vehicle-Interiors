"""Compare native body turns outside and inside using actual keyboard events."""
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    _,h=load('final-interior-tests').load_helpers()
    h.configure(run/'turning');h.SCREENS=run/'home/Zomboid/Screenshots'
    report={'scope':__doc__,'cases':{},'passed':False}
    path=run/'turning.json'
    def save():path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    def press(names,duration):
        keys=[int(h.lua('return getCore():getKey('+json.dumps(name)+')')) for name in names]
        h.lua(';'.join(f'MEMCNativeLab.holdKey({k},{int(duration*1000)})' for k in keys)+';return true')
        time.sleep(duration)
        h.lua('MEMCNativeLab.releaseKeys();return true')
    def trial(label,first,second,running=False):
        # Settle the initial heading through normal input; only the reversal is sampled.
        press(first+(['Run'] if running else []),.35)
        time.sleep(.45)
        deadline=time.monotonic()+3
        while True:
            native=json.loads(h.lua('return MELensDevBones.turning(getPlayer())'))
            error=(native['angle']-native['target']+math.pi)%(2*math.pi)-math.pi
            if abs(error)<.04:break
            assert time.monotonic()<deadline,'initial native heading did not settle: '+label
            time.sleep(.1)
        h.lua('RVI_TurnProbe.rows={};RVI_TurnProbe.active=true;return true')
        time.sleep(.2) # unchanged-input control
        press(second+(['Run'] if running else []),.3)
        time.sleep(1.25)
        rows=h._sequence(h.lua('RVI_TurnProbe.active=false;return RVI_TurnProbe.rows'))
        assert rows,'turn probe returned no native render samples'
        report['cases'][label]={'from':first,'to':second,'shift':running,'rows':rows}
        save()
        native=[json.loads(s['turn']) for s in rows]
        wrap=lambda a:(a+math.pi)%(2*math.pi)-math.pi
        expected=math.pi if '180' in label else math.pi/2
        assert abs(abs(wrap(native[-1]['target']-native[0]['target']))-expected)<.02,'target snapped back: '+label
        assert max(abs(wrap(b['angle']-a['angle'])) for a,b in zip(native,native[1:]))<.7,'instant body rotation: '+label
        assert any(s['turning'] for s in native),'native turning state never ran: '+label
        assert abs(wrap(native[-1]['angle']-native[-1]['target']))<.04,'native turn did not finish: '+label
        assert all(s['alpha']==1 and s['targetAlpha']==1 for s in rows),'opacity changed during turn: '+label
        if label.startswith('inside'):assert all(s['standing'] for s in rows),'turn input left the interior: '+label
        h.capture(label)
        print('TURN_RECORDED',label,len(rows),flush=True)
    def group(scope):
        trial(scope+'-90-left',['Forward'],['Left'])
        trial(scope+'-90-right',['Backward'],['Left'])
        trial(scope+'-180',['Forward'],['Backward'])
        trial(scope+'-shift-180',['Forward'],['Backward'],True)
    try:
        # Independent drivers may have left this owned character beside another
        # test vehicle. Return to the known open field before relative spawns;
        # otherwise cumulative comparison travel can place a van inside a house.
        h.lua('local p=getPlayer();p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY());return true')
        time.sleep(.6)
        h.lua('''RVI_TurnProbe={rows={},active=false}
local T=RVI_TurnProbe
T.tick=function()
 if not T.active or #T.rows>=300 then return end
 local ok,err=pcall(function()
 local p=getPlayer();local d=MELens.debugState()
 T.rows[#T.rows+1]={t=getTimestampMs(),turn=MELensDevBones.turning(p),tracks=MELensDevBones.tracks(p),
 animation=MELensRV.animInfo(p),alpha=p:getAlpha(0),targetAlpha=p:getTargetAlpha(0),
 x=d.x,z=d.z,facing=d.facing,standing=MELens.isStanding(p)}
 end)
 if not ok then T.error=tostring(err);Events.OnPostRender.Remove(T.tick) end
end
Events.OnPostRender.Add(T.tick)
ISUIHandler.setVisibleAllUI(false);getCore():setAutoZoom(0,false);return true''')
        group('outside')
        for heading in ('E','W'):
            load('bed-tests').enter(h,'Base.StepVan',heading)
            h.lua('''local v=MELensTest.vehicle;local q=MELens.profileFor(v);local P=MELens.Parts
for i=1,#q.spots do local part=P.spotPart(v,i)
 if part then local c=part:getItemContainer();if c then c:clear() end
 part:setInventoryItem(nil);P.settle(v,part) end
end
ISUIHandler.setVisibleAllUI(false);MELens.walkTo(getPlayer(),0,-.95);return true''')
            end=time.monotonic()+12
            while h.lua('return MELens.pathing(getPlayer())'):
                assert time.monotonic()<end,'native curved approach did not arrive'
                time.sleep(.15)
            time.sleep(.4)
            h.lua(f'MELensMedia.clip("clip-native-turn-{heading.lower()}",14);return true')
            group('inside-'+heading.lower())
            assert h.lua('return MELens.isStanding(getPlayer())'),'turn input left the van'
            h.lua('MELens.leave(getPlayer());return true')
            end=time.monotonic()+15
            while h.lua('return getPlayer():getVehicle()~=nil'):
                assert time.monotonic()<end,'native path/exit did not complete'
                time.sleep(.15)
            time.sleep(.5)
        h.lua('Events.OnPostRender.Remove(RVI_TurnProbe.tick);return true')
        report['passed']=True;save()
    except Exception as error:
        report['error']=str(error);report['traceback']=traceback.format_exc();save();raise
    finally:
        try:h.lua('MEMCNativeLab.releaseKeys();if RVI_TurnProbe then Events.OnPostRender.Remove(RVI_TurnProbe.tick) end;return true')
        except Exception:pass

if __name__=='__main__':main()
