"""Same-pose, paused-clock controls for the isolated capture camera."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-', '_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--headings',default='E')
    parser.add_argument('--output-name',default='depth-controls')
    parser.add_argument('--keep-open',action='store_true')
    args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h=load('final-feature-tests');h.configure(run/args.output_name)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    try:
        h.lua('''MELensMedia.cameraOff();MELensMedia.cameraNativePan(false);local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
        load('bed-tests').enter(h,'Base.86fordE150','E')
        h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell/2);return true''')
        deadline=time.monotonic()+30
        while h.lua('return MELens.pathing(getPlayer())'):
            h.check(time.monotonic()<deadline,'aisle walk timeout');time.sleep(.2)
        h.lua('''local o=PZAPI.ModOptions:getOptions('RealVehicleInteriors')
o:getOption('wallHeight'):setValue(3);o:getOption('cameraWalls'):setValue(false);o:apply()
ISUIHandler.setVisibleAllUI(false);getGameTime():setTimeOfDay(12);return true''')
        time.sleep(.5)
        h.lua('setGameSpeed(0);return true')
        pose="""local v=MELensTest.vehicle;local p=Vector3f.new();v:getWorldPos(0,0,0,p)
return {clock=getGameTime():getWorldAgeHours(),x=v:getX(),y=v:getY(),z=v:getZ(),
origin={p:x(),p:y(),p:z()},angles={v:getAngleX(),v:getAngleY(),v:getAngleZ()}}"""
        before=h.lua(pose)
        h.REPORT['sameTickPose']=before
        parts=h.lua('''local v=MELensTest.vehicle;local out={};for i=0,v:getPartCount()-1 do local p=v:getPartByIndex(i)
if p:getId():find('Tire') then local item=p:getInventoryItem();out[#out+1]={id=p:getId(),item=item and item:getFullType(),condition=p:getCondition(),models=p:getScriptPart():getModelCount()} end end
return {tyres=out,native=MELensRV.nativeBodyWallsActive(),flat=MELensRV.flatWheelArchActive(),shader=MELensRV.shaderError()}''')
        h.REPORT['parts']=parts
        def render_state():
            return h.lua('''return {native=MELensRV.nativeBodyWallsActive(),flat=MELensRV.flatWheelArchActive(),shader=MELensRV.shaderError(),camera=MELensMedia.cameraInfo()}''')
        h.REPORT['stages']={}
        time.sleep(.5);h.capture('stock-camera-native-walls')
        h.REPORT['stages']['stockNative']=render_state()
        h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
local base=v:getWorldPos(0,0,0,q):z();local g=MELens.WalkGrids[pr.walkGrid]
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensDepthTarget={x=q:x(),y=q:y(),z=base+(o:y()+pr.floorY)/2.44949}
MELensMedia.camera(q:x(),q:y(),MELensDepthTarget.z);MELensMedia.frameCamera();return true''')
        time.sleep(.5);h.capture('fixed-camera-native-walls')
        h.REPORT['stages']['fixedNative']=render_state()
        time.sleep(.3);h.capture('fixed-camera-unchanged-control')
        h.REPORT['camera']=h.lua('return MELensMedia.cameraInfo()')
        h.check(h.lua(pose)==before,'camera control changed paused tick or physical pose')
        h.lua('MELensMedia.cameraNativePan(true);MELensMedia.frameCamera();return true')
        time.sleep(.5);h.capture('native-pan-camera-native-walls')
        h.REPORT['stages']['nativePan']=render_state()
        time.sleep(.3);h.capture('native-pan-camera-unchanged-control')
        h.check(h.lua(pose)==before,'native pan changed paused tick or physical pose')
        h.lua('MELensMedia.cameraNativePan(false);MELensMedia.frameCamera();return true')
        h.lua('MELensRV.clearCutaway();return true')
        time.sleep(.5);h.capture('fixed-camera-without-cutaway')
        h.REPORT['stages']['fixedOriginal']=render_state()
        h.check(not h.REPORT['stages']['fixedOriginal']['native'],'cutaway reset did not stay disabled during paused fixture')
        h.check(h.lua(pose)==before,'cutaway control changed paused tick or physical pose')
        h.lua('MELensMedia.cameraOff();return true')
        time.sleep(.5);h.capture('stock-camera-without-cutaway')
        h.REPORT['stages']['stockOriginal']=render_state()
        h.check(h.lua(pose)==before,'stock control changed paused tick or physical pose')
        h.REPORT['nativeInput']=True
        h.REPORT['scope']=__doc__;h.write_report('passed');return 0
    except Exception:
        h.write_report('failed',traceback.format_exc());raise
    finally:
        try:h.lua('setGameSpeed(1);MELensMedia.cameraOff();return true')
        finally:
            if not args.keep_open:(run/'request.json').write_text('{"action":"stop"}')

if __name__=='__main__':raise SystemExit(main())
