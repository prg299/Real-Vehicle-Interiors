"""Temporary native height/arch controls; never a shipping-package acceptance ledger."""
import json, os, time
from pathlib import Path
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h=load('final-feature-tests');beds=load('bed-tests');iso=load('shell-isolation-tests')
    h.configure(run/'window-preview')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(v.split('=',1)[1] for v in session['command'] if v.startswith('-cachedir=')))/'Screenshots'
    h.REPORT['scope']='Diagnostic same-pose height and lining-exclusion controls; profile overrides are temporary, not package acceptance'
    def focus(z,zoom=1):
        h.lua(f'''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
local base=v:getWorldPos(0,0,0,q):z();v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+{z},q)
MELensMedia.cameraNativePan(true);MELensMedia.camera(q:x(),q:y(),base+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
        for _ in range(16):
            current=h.lua('return getCore():getZoom(0)')
            if abs(current-zoom)<.01:break
            h.lua('getCore():doZoomScroll(0,'+('1' if current<zoom else '-1')+');return true');time.sleep(.2)
        time.sleep(.4)
    def height():
        h.lua('''local o=PZAPI.ModOptions:getOptions('RealVehicleInteriors');o:getOption('wallHeight'):setValue(3)
o:getOption('cameraWalls'):setValue(false);o:apply();return true''');time.sleep(.4)
    def cleanup():
        h.lua('''local v=MELensTest.vehicle;if getPlayer():getVehicle() then v:exit(getPlayer()) end
v:permanentlyRemove();MELensTest={all={}};MELensMedia.cameraOff();return true''')
    try:
        beds.enter(h,'Base.Trailer87Scamp13','N');height();focus(1.19055)
        h.capture('scamp-high-control');h.capture('scamp-high-unchanged')
        changed=h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);MELensWindowPreview={profile=pr,plane=pr.cutPlanes[3]}
local top=-math.huge;for _,w in ipairs(pr.windowBoxes) do top=math.max(top,w.y[2]) end;top=top+.015
pr.cutPlanes[3]={0,0,-1,pr.mesh.lift-top/pr.mesh.scale};return {top=top,plane=pr.cutPlanes[3]}''')
        h.REPORT['temporaryHighPlane']=changed;height();h.capture('scamp-whole-window-high')
        h.lua('MELensWindowPreview.profile.cutPlanes[3]=MELensWindowPreview.plane;MELensWindowPreview=nil;return true')
        height();h.capture('scamp-high-restored');cleanup()
        beds.enter(h,'Base.87fordB700school','E');height();h.lua(iso.BASELINE)
        aliases=h._sequence(h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);local P=MELens.Parts;local names={}
for _,spot in ipairs(pr.spots) do for _,piece in ipairs(P.piecesFor(spot)) do names[P.modelFile(piece,spot)]=true end end
local out={};for name in pairs(names) do out[#out+1]=name end;return out'''))
        for alias in aliases:h.lua('MELensRV.setKeepPlane('+json.dumps(alias)+',0,0,0,1);return true')
        focus(-2.47,.5);h.capture('bus-arch-control');h.capture('bus-arch-unchanged')
        h.lua('MELensRV.clearClipBoxes();return true');time.sleep(.3);h.capture('bus-arch-unexcluded')
        h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);local m=pr.mesh
for i,w in ipairs(pr.wheelWells) do MELensRV.setClipBox(i-1,-w.x[1]/m.scale,w.z[1]/m.scale,m.lift-w.y[1]/m.scale,
-w.x[2]/m.scale,w.z[2]/m.scale,m.lift-w.y[2]/m.scale) end;return true''')
        time.sleep(.3);h.capture('bus-arch-exclusion-restored');h.lua(iso.RESTORE)
        h.lua('MELensShellIsolation=nil;return true');cleanup();h.write_report('passed')
    finally:
        h.lua('''if MELensWindowPreview then MELensWindowPreview.profile.cutPlanes[3]=MELensWindowPreview.plane;MELensWindowPreview=nil end
if MELensShellIsolation then MELensShellIsolation.restore();MELensShellIsolation=nil end;return true''')
        (run/'request.json').write_text('{"action":"stop"}')

if __name__=='__main__':main()
