"""Native model-isolation captures; diagnostic fixtures, not final acceptance."""
import argparse,importlib.util,json,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',action='append',help='Exact vehicle script IDs')
    parser.add_argument('--heading',choices=('E','N','S','W'),help='Override the usual diagnostic camera heading')
    parser.add_argument('--output-name',default='cab-seam-diagnosis')
    args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    assert Path(args.output_name).name==args.output_name
    h=load('final-feature-tests');h.configure(run/args.output_name)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    bodies={'Base.90fordF350ambulance':'f350_body','Base.VanRadio':'vehicles/Vehicles_VanRadio',
            'Base.85chevyStepVan':'85stepvan_body','Base.VanAmbulance':'vehicles/Vehicles_VanAmbulance'}
    if args.only:assert not set(args.only)-set(bodies)
    for name,heading in [('Base.90fordF350ambulance','N'),('Base.VanRadio','N'),('Base.85chevyStepVan','W'),('Base.VanAmbulance','N')]:
        if args.only and name not in args.only:continue
        heading=args.heading or heading
        label=name.split('.',1)[1].lower()
        h.lua('MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end;ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true')
        load('bed-tests').enter(h,name,heading)
        h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local P=MELens.Parts
for i in ipairs(pr.spots) do local part=P.spotPart(v,i);if part:getItemContainer() then part:getItemContainer():getItems():clear() end
part:setInventoryItem(nil);P.applyPiece(v,part) end
local g=MELens.WalkGrids[pr.walkGrid];local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensMedia.camera(q:x(),q:y(),v:getZ()+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
        for _ in range(10):
            zoom=h.lua('return getCore():getZoom(0)')
            if abs(zoom-.5)<.02:break
            h.lua(f'getCore():doZoomScroll(0,{1 if zoom<.5 else -1});return true');time.sleep(.2)
        time.sleep(.8);h.capture(label+'-baseline')
        cap=h.lua('''local pr=MELens.profileFor(MELensTest.vehicle)
local cap=pr.shell.models[3];assert(cap:find('bulkhead',1,true))
MELensRV.setKeepPlane(cap,0,0,0,1);return cap''')
        time.sleep(.4);h.capture(label+'-cap-hidden')
        h.lua(f'MELensRV.setKeepPlane({json.dumps(cap)},0,0,0,-1);return true')
        h.lua(f'MELensRV.setKeepPlane("mesh:{bodies[name]}",0,0,0,1);return true')
        time.sleep(.4);h.capture(label+'-body-hidden')
        h.lua(f'MELensRV.setKeepPlane("mesh:{bodies[name]}",0,0,0,-1);MELensRV.setSurvey(true);return true')
        time.sleep(.4)
        survey=h.lua('return MELensRV.surveyInfo()')
        (h.OUTPUT/(label+'-survey.txt')).write_text(survey)
        h.lua('MELensRV.setSurvey(false);return true')
        hidden=h.lua('''local out={};local pr=MELens.profileFor(MELensTest.vehicle)
for name in pairs(pr.hideKI5) do if name:lower():find('interior',1,true) then
MELensRV.setKeepPlane(name,0,0,0,1);out[#out+1]=name end end;return out''')
        time.sleep(.4);h.capture(label+'-native-interiors-hidden')
        h.REPORT.setdefault('isolations',[]).append(dict(vehicle=name,cap=cap,body=bodies[name],hidden=h._sequence(hidden)))
        h.lua('''local pr=MELens.profileFor(MELensTest.vehicle)
for name,rule in pairs(pr.hideKI5) do if name:lower():find('interior',1,true) then
if rule==true then MELensRV.setKeepPlane(name,0,0,0,1)
elseif rule.plane then local p=rule.plane;MELensRV.setKeepPlane(name,p[1],p[2],p[3],p[4]) end end end;return true''')
    h.write_report('passed');return 0
if __name__=='__main__':raise SystemExit(main())
