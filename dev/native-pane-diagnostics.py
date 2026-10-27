"""Finite same-pose native pane ownership controls; never acceptance evidence."""
import importlib.util
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h, beds, iso = load('final-feature-tests'), load('bed-tests'), load('shell-isolation-tests')
    h.configure(run/'pane-diagnostics')
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(v.split('=', 1)[1] for v in session['command'] if v.startswith('-cachedir=')))/'Screenshots'
    h.REPORT['scope'] = 'Temporary same-pose pane/model/finish ownership fixtures; no package acceptance'
    try:
        for script, heading, body in [('Base.Trailer87Scamp13', 'N', 'scamp13_body'),
                                      ('Base.87fordB700school', 'E', 'b700_body')]:
            beds.enter(h, script, heading)
            key = script.split('.')[1].lower()
            h.lua('''local o=PZAPI.ModOptions:getOptions('RealVehicleInteriors')
o:getOption('wallHeight'):setValue(3);o:getOption('cameraWalls'):setValue(false);o:apply()
local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.cameraNativePan(true);MELensMedia.camera(q:x(),q:y(),base+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);MELensPaneDiagnostic={parts={}}
for i=0,v:getPartCount()-1 do local p=v:getPartByIndex(i);local id=p:getId()
if (p:getWindow() or id:sub(1,6)=='Window' or id:sub(1,10)=='Windshield') and not id:lower():find('armor',1,true) then
 local w=p:getWindow();MELensPaneDiagnostic.parts[#MELensPaneDiagnostic.parts+1]={part=p,item=p:getInventoryItem(),
 condition=p:getCondition(),open=w and w:isOpen(),delta=w and w:getOpenDelta()}
end end
MELensRV.setSurvey(true);return true''')
            time.sleep(.6)
            h.REPORT.setdefault('surveys', {})[script] = h.lua('return MELensRV.surveyInfo()')
            h.lua('MELensRV.setSurvey(false);return true')
            h.capture(key+'-intact')
            for mode, title in [(2, 'source'), (3, 'mask'), (4, 'alpha')]:
                h.lua(f'MELensRV.setBodyLiningDebugMode({mode});return true')
                time.sleep(.3)
                h.capture(key+'-'+title)
            h.lua('MELensRV.setBodyLiningDebugMode(0);return true')
            h.lua('''for _,b in ipairs(MELensPaneDiagnostic.parts) do local p=b.part;local s=p:getScriptPart()
for j=0,s:getModelCount()-1 do p:setModelVisible(s:getModel(j):getId(),false) end end;return true''')
            time.sleep(.4)
            h.capture(key+'-pane-models-hidden')
            h.lua('''for _,b in ipairs(MELensPaneDiagnostic.parts) do local p=b.part;local s=p:getScriptPart()
for j=0,s:getModelCount()-1 do p:setModelVisible(s:getModel(j):getId(),true) end end;return true''')
            h.lua(iso.BASELINE)
            h.lua('MELensRV.setKeepPlane('+json.dumps('mesh:'+body)+',0,0,0,1);return true')
            time.sleep(.3)
            h.capture(key+'-root-body-hidden')
            h.lua(iso.RESTORE)
            h.lua('MELensShellIsolation=nil;return true')
            h.REPORT.setdefault('damageStates', {})[script] = h.lua('''local out={}
for _,b in ipairs(MELensPaneDiagnostic.parts) do local p=b.part;local w=p:getWindow()
if w then w:setOpen(false);w:damage(w:getHealth());assert(w:isDestroyed()) else p:setCondition(0) end
out[#out+1]={id=p:getId(),condition=p:getCondition(),item=p:getInventoryItem()~=nil,destroyed=w and w:isDestroyed()}
end;return out''')
            time.sleep(.4)
            h.capture(key+'-native-damage')
            h.lua('''for _,b in ipairs(MELensPaneDiagnostic.parts) do local p=b.part
p:setInventoryItem(b.item);p:setCondition(b.condition);local w=p:getWindow()
if w then w:setOpen(b.open);w:setOpenDelta(b.delta) end end;return true''')
            time.sleep(.4)
            h.capture(key+'-repaired')
            h.lua('''for _,b in ipairs(MELensPaneDiagnostic.parts) do local w=b.part:getWindow()
if w and w:isOpenable() then w:setOpen(true);w:setOpenDelta(1) end end;return true''')
            time.sleep(.4)
            h.capture(key+'-fully-open')
            h.lua('''for _,b in ipairs(MELensPaneDiagnostic.parts) do local w=b.part:getWindow()
if w then w:setOpen(b.open);w:setOpenDelta(b.delta) end end
local v=MELensTest.vehicle;v:exit(getPlayer());v:permanentlyRemove()
MELensPaneDiagnostic=nil;MELensTest={all={}};MELensMedia.cameraOff();return true''')
        h.write_report('passed')
    finally:
        try:
            h.lua('MELensRV.setSurvey(false);MELensRV.setBodyLiningDebugMode(0);if MELensShellIsolation then MELensShellIsolation.restore();MELensShellIsolation=nil end;return true')
        finally:
            (run/'request.json').write_text('{"action":"stop"}')


if __name__ == '__main__':
    main()
