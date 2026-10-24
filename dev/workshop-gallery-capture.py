"""Gallery captures of the released package. Parent owns the isolated native game."""
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN'];neat=os.environ.get('RVI_GALLERY_NEAT')=='1'
    if not neat:
        command=[sys.executable,str(ROOT/'dev/fleet-gallery.py'),'--output-name','vehicles']
        for label in ['vanilla-cargo-van','vanilla-ambulance','delivery-van','radio-van','econoline','chevy-step-van','armored-truck','ambulance','bus','cargo-truck']:
            command+=['--only',label]
        subprocess.run(command,cwd=ROOT,check=True)
    interior=load('final-interior-tests');tap,h=interior.load_helpers()
    h.configure(run/'dashboard')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
MELensMedia.cameraOff();p:setX(10813.5);p:setY(10140.5);p:setLastX(p:getX());p:setLastY(p:getY());return true''')
    load('bed-tests').enter(h,'Base.Trailer54FlyingCloud22','E')
    h.lua((ROOT/'dev/lua/feature-fixture.lua').read_text());h.lua(interior.FIXTURE)
    h.check(h.lua('return MELens.Dashboard.isNeatActive()')==neat,'actual mod activation differs')
    h.lua('''local v=getPlayer():getVehicle();local P,U=MELens.Parts,MELens.Utilities
local g=v:getPartById(P.GENERATOR);g:getModData().fuel=8.4;g:setCondition(85)
local w=v:getPartById(P.WATER);w:getModData().water=48;w:getModData().tainted=false
U.setSwitch(v,"generator",true);v:getModData().MELensLightsOff=false
return true''')
    interior.close_dashboard(h,tap)
    point=h.lua('return MELensInteriorTest.point("bed")')
    label=h.lua('return getText("ContextMenu_MELens_Dashboard")')
    interior.choose(h,tap,point,[label],'gallery-dashboard-open')
    h.wait_for(lambda s:s.get('dashboard') and len(s['controls'])>=8,timeout=10,label='native dashboard')
    h.lua('''local w=MELens.Dashboard.instance;w:setX(352);w:setY(140);return true''')
    h.lua('''local all=UIManager.getUI();local w=MELens.Dashboard.instance
for i=0,all:size()-1 do local t=all:get(i):getTable()
if t and t~=w and t.setVisible then t:setVisible(false) end end;return true''')
    time.sleep(.7)
    bounds=h.lua('local w=MELens.Dashboard.instance;return {x=w:getX(),y=w:getY(),width=w:getWidth(),height=w:getHeight(),type=w.Type}')
    h.REPORT['bounds']=bounds;h.REPORT['neat']=neat;h.REPORT['nativeInput']=True
    h.REPORT['sourceVersion']=h.lua('return MELensRV.version()')
    h.capture('dashboard-neat' if neat else 'dashboard-vanilla')
    h.write_report('passed');(run/'request.json').write_text('{"action":"stop"}')
    return 0
if __name__=='__main__':raise SystemExit(main())
