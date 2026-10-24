"""Side-door renderer state fixtures; parent owns the guarded native process."""
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN'];h=load('final-feature-tests');h.configure(run/'side-doors')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    prior=h.lua('local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors");return {height=o:getOption("wallHeight"):getValue(),camera=o:getOption("cameraWalls"):getValue()}')
    def visible(expected,label):
        state=h.lua('''local v=MELensTest.vehicle;local shell=v:getPartById(MELens.Parts.SHELL)
return {side=MELensRV.isPartModelVisible(shell,"MELensShell5"),rear=MELensRV.isPartModelVisible(shell,"MELensShell4")}''')
        h.check(state['side']==expected and state['rear'],label+' door skins disagree with native parts')
        h.REPORT.setdefault('states',[]).append(dict(label=label,**state))
    try:
        for heading in ('E','W'):
            h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
            load('bed-tests').enter(h,'Base.90fordF350ambulance',heading)
            info=h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX, -1.9)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949);ISUIHandler.setVisibleAllUI(false)
local leaf=assert(v:getPartById("DoorRearRight"));assert(leaf:getInventoryItem());MELensTest.sideItem=leaf:getInventoryItem()
return {door=leaf:getId(),item=leaf:getInventoryItem():getFullType(),open=leaf:getDoor():isOpen()}''')
            h.REPORT.setdefault('doors',[]).append(info)
            end=time.monotonic()+25
            while h.lua('return MELens.pathing(getPlayer())'):
                h.check(time.monotonic()<end,'aisle fixture timeout');time.sleep(.1)
            for _ in range(8):
                zoom=h.lua('return getCore():getZoom(0)')
                if abs(zoom-.5)<.02:break
                h.lua(f'getCore():doZoomScroll(0,{1 if zoom<.5 else -1});return true');time.sleep(.15)
            for height in (2,3):
                h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors");o:getOption("wallHeight"):setValue({height})
o:getOption("cameraWalls"):setValue(false);o:apply();return true''')
                time.sleep(.5);visible(True,'closed-'+heading+'-'+str(height));h.capture('side-'+heading.lower()+'-closed-height-'+str(height))
            h.lua('local v=MELensTest.vehicle;local p=v:getPartById("DoorRearRight");p:getDoor():setOpen(true);v:playPartAnim(p,"Opened");return true')
            time.sleep(.5);visible(False,'opened-'+heading);h.capture('side-'+heading.lower()+'-opened-fixture')
            h.lua('MEMCNativeLab.dropInteriorModels(MELensTest.vehicle);return true')
            time.sleep(.8);visible(False,'opened-model-recovery-'+heading)
            h.lua('local v=MELensTest.vehicle;local p=v:getPartById("DoorRearRight");p:getDoor():setOpen(false);v:playPartAnim(p,"Closed");p:setInventoryItem(nil);return true')
            time.sleep(.5);visible(False,'missing-'+heading);h.capture('side-'+heading.lower()+'-missing-fixture')
            h.lua('local v=MELensTest.vehicle;v:getPartById("DoorRearRight"):setInventoryItem(MELensTest.sideItem);return true')
            time.sleep(.4);visible(True,'restored-'+heading);h.capture('side-'+heading.lower()+'-restored')
        h.REPORT['scope']=__doc__;h.REPORT['nativeInput']=True
        h.REPORT['unverified']=['mechanics-menu door removal/open input','dedicated multiplayer']
        h.write_report('passed');return 0
    except Exception:
        h.write_report('failed',traceback.format_exc());raise
    finally:
        h.lua(f'''local o=PZAPI.ModOptions:getOptions("RealVehicleInteriors");o:getOption("wallHeight"):setValue({prior['height']})
o:getOption("cameraWalls"):setValue({str(prior['camera']).lower()});o:apply();return true''')

if __name__=='__main__':raise SystemExit(main())
