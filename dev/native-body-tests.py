"""Vanilla plain and KI5 curved native interior matrices.

Entry/exit use the production Interact key. Spawn/position, wall options, door
and window removal are labelled renderer fixtures, not mechanics-menu proof.
Family matrices and every-variant furnished captures are separate ledgers.
"""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT/'dev'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def catalogue():
    """Supported source specs only; disabled cargo trailers never become cases."""
    families = []
    sys.path.insert(0, str(ROOT/'tools-src/vehicles'))
    from factory_layouts import role_for
    resolved = {row['fullName']: row for row in json.loads((ROOT/'build/rv/vehicle-catalogue.json').read_text())['entries']}

    def aliases(scripts, fallback):
        sources = [resolved.get(name, fallback) for name in scripts]
        return dict(bodyAliases=sorted({source['model']['file'] for source in sources}),
                    tyreAliases=sorted({model['file'] for source in sources for part in source['parts']
                                        if part['id'].startswith('Tire') for model in part['models']}),
                    tyreModels=[dict(part=part, model=model) for part, model in sorted({
                        (part['id'], model['id']) for source in sources for part in source['parts']
                        if part['id'].startswith('Tire') for model in part['models']})])
    for path in sorted((ROOT/'tools-src/vehicles/specs').glob('*.json')):
        spec = json.loads(path.read_text())
        if spec.get('disabled'):
            continue
        measure = json.loads((ROOT/'build/rv/floorplans'/spec['measure']).read_text())
        source_file, source_key = spec['scripts']
        source = json.loads((ROOT/'build/rv/floorplans'/source_file).read_text())[source_key]
        native_scripts = [name for name in spec['vehicles'] if spec.get('nativeBodyWalls') is True
                          or (spec.get('nativeBodyWallsRole') is not None
                              and role_for(name, spec['key']) == spec['nativeBodyWallsRole'])]
        families.append(dict(family=spec['key'], title=spec['title'], scripts=spec['vehicles'],
                             representative=measure['name'], bounds=measure['body'],
                             nativeWallScripts=native_scripts,
                             plainFinish=spec.get('nativePlainFinish') is True,
                             **aliases(spec['vehicles'], source)))
    measure = json.loads((ROOT/'build/rv/floorplans/measure_FlyingCloud22.json').read_text())
    source = json.loads((ROOT/'build/rv/floorplans/campers.json').read_text())['Trailer54FlyingCloud22']
    families.append(dict(family='FlyingCloud22', title='Flying Cloud 22', scripts=['Base.Trailer54FlyingCloud22'],
                         representative='Base.Trailer54FlyingCloud22', bounds=measure['body'],
                         nativeWallScripts=['Base.Trailer54FlyingCloud22'], plainFinish=False,
                         **aliases(['Base.Trailer54FlyingCloud22'], source)))
    assert len(families) == 19 and sum(len(row['scripts']) for row in families) == 203
    for row in families:
        assert row['representative'] in row['scripts'], row
    return families


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family', action='append', help='Repeat exact supported family key')
    parser.add_argument('--only', action='append', help='Repeat exact script ID')
    parser.add_argument('--variants', action='store_true', help='Four furnished views of every selected script')
    parser.add_argument('--photos-only', action='store_true', help='Four furnished photographs per variant with Interact entry/exit; omit extra diagnostic states')
    parser.add_argument('--empty-photos', action='store_true', help='Add draw-only empty floor views/details and a restored frame to photography mode')
    parser.add_argument('--door-photo-part', help='Photography fixture: closed/open/restored views of one exact native door part')
    parser.add_argument('--detail-height', type=int, choices=(1, 2, 3), default=1,
                        help='Physical wall height in close front/rear detail frames')
    parser.add_argument('--native-camera', action='store_true', help='Frame photographs through the native 2D/3D camera pan contract')
    parser.add_argument('--paint-hsv', help='Vanilla photography fixture only: fixed native hue,saturation,value in [0,1]')
    parser.add_argument('--reuse-ledger', action='append', type=Path, default=[], help='Skip valid furnished headings already captured from this frozen payload')
    parser.add_argument('--ki5-only', action='store_true', help='Select all supported KI5 families; exclude vanilla')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--headings', default='E,N,S,W')
    parser.add_argument('--output-name', default='native-body')
    parser.add_argument('--fallback', action='store_true', help='Expect older Java with authored lining')
    parser.add_argument('--isolate', action='store_true', help='Fixed-camera body/support/tyre ownership controls')
    parser.add_argument('--isolate-height', type=int, choices=(1, 2, 3), default=1)
    parser.add_argument('--isolate-only', action='append', choices=('body','support','arch','tyres'), help='Limit empty ownership controls to selected roles')
    parser.add_argument('--isolate-alias', action='append', help='Additional exact native model alias ownership control')
    parser.add_argument('--material-controls', action='store_true', help='Native finish/normal/texture/mask diagnostics')
    parser.add_argument('--draw-survey', action='store_true', help='Record actual native draw classes, wheel roles and body-space bounds once per pose')
    parser.add_argument('--loose-controls', action='store_true', help='Paused loose-item draw hide/restore attribution, preserving inventory')
    parser.add_argument('--require-wheel-mask', action='store_true', help='Require actual masked wheel draws between reviewed frames in each pose')
    parser.add_argument('--surface-coordinates', action='store_true', help='Record first UV and body-position pixel diagnostics; requires the diagnostic bridge')
    parser.add_argument('--surface-bitplanes', action='store_true', help='Pause the pose and record binary surface coordinates through game colour processing')
    parser.add_argument('--surface-height', type=int, choices=(1,2,3), default=1,
                        help='Wall height for paused coordinate diagnostics; default Low')
    parser.add_argument('--empty-controls', action='store_true', help='Hide furniture draws temporarily to expose structural joins')
    parser.add_argument('--empty-opening-controls', action='store_true',
                        help='Hide furniture draws during the door/window fixture matrix to expose covered panes')
    parser.add_argument('--opening-part', action='append', default=[],
                        help='Limit opening fixtures to exact live door/window part IDs; retain the full recorded contract')
    parser.add_argument('--opening-cut-y', type=float,
                        help='Temporary diagnostic High cut in passenger metres, restored before normal detail/outside views')
    parser.add_argument('--panel-input', action='store_true', help='Open the utility-panel world menu and Dashboard with native mouse input')
    parser.add_argument('--alias-controls', action='append', default=[], help='Paused keep-plane hide/restore controls; comma-separated exact model aliases per group')
    parser.add_argument('--alias-wall-height', type=int, choices=(1, 2, 3), default=1,
                        help='Retain the reported wall height during paused alias attribution')
    parser.add_argument('--alias-camera-walls', action=argparse.BooleanOptionalAction, default=True,
                        help='Retain camera-side lowering during paused alias attribution')
    parser.add_argument('--keep-open', action='store_true', help='Use the parent bounded review window after success')
    parser.add_argument('--project-points', type=Path, help='Diagnostic measured model-space points to project beside original frame records')
    args = parser.parse_args()
    assert not args.surface_coordinates or args.material_controls, 'Surface coordinates require material controls'
    assert not args.surface_bitplanes or args.surface_coordinates, 'Surface bitplanes require surface coordinates'
    assert args.surface_height == 1 or args.surface_bitplanes, 'Diagnostic surface height requires bitplanes'
    assert not args.loose_controls or (args.variants and not args.photos_only), 'Loose attribution requires diagnostic variants'
    alias_groups = [dict(aliases=group.split(','), plane=[0,0,0,1]) for group in args.alias_controls]
    assert all(alias and all(c.isalnum() or c in '_:.' for c in alias)
               for group in alias_groups for alias in group['aliases']), 'Invalid model alias'
    if args.photos_only:
        args.variants = True
        assert not (args.isolate or args.material_controls or args.empty_controls or args.empty_opening_controls or alias_groups), 'Photography and diagnostic matrices are separate modes'
    assert not args.empty_photos or args.photos_only, 'Empty photographs require photography mode'
    assert not args.door_photo_part or (args.photos_only and args.door_photo_part.isalnum()), 'Door photographs require photography mode and an exact part ID'
    if args.paint_hsv is not None:
        args.paint_hsv = [float(value) for value in args.paint_hsv.split(',')]
        assert args.photos_only and len(args.paint_hsv) == 3 and all(math.isfinite(value) and 0 <= value <= 1 for value in args.paint_hsv), 'Paint fixture requires photography and three finite native HSV values'
    assert not (args.variants and args.empty_opening_controls), 'Empty opening controls require the full state matrix'
    assert not (args.variants and (args.opening_part or args.opening_cut_y is not None)), 'Focused openings require matrix mode'
    assert all(part and part.isalnum() for part in args.opening_part), 'Invalid opening part ID'
    assert args.opening_cut_y is None or (math.isfinite(args.opening_cut_y) and args.opening_part), 'Diagnostic cut requires finite height and focused parts'
    projected_points = json.loads(args.project_points.read_text()) if args.project_points else {}
    assert Path(args.output_name).name == args.output_name
    headings = args.headings.split(',')
    assert headings and all(value in ('E', 'N', 'S', 'W') for value in headings)
    families = catalogue()
    if args.ki5_only:
        families = [row for row in families if not row['plainFinish']]
    if args.family:
        assert set(args.family) <= {row['family'] for row in families}
        families = [row for row in families if row['family'] in args.family]
    cases = [dict(row, script=name) for row in families
             for name in (row['scripts'] if args.variants else [row['representative']])]
    if args.only:
        # Exact variant overrides also work in matrix mode.
        family_for = {name: row for row in families for name in row['scripts']}
        assert set(args.only) <= family_for.keys()
        cases = [dict(family_for[name], script=name) for name in args.only]
    cases = cases[args.start:args.start+args.limit if args.limit else None]
    assert cases, 'No selected supported cases'
    run = ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h = load('final-feature-tests')
    h.configure(run/args.output_name)
    session = json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS = Path(next(value.split('=', 1)[1] for value in session['command']
                         if value.startswith('-cachedir=')))/'Screenshots'
    snapshot = load('interior-lifecycle-tests').SNAPSHOT
    beds = load('bed-tests')
    ledger = h.OUTPUT/'frames.jsonl'
    h.REPORT.update(scope=__doc__, selected=cases, nativeInput=False,
                    fixtures=['spawn/repair/unlock', 'outside position', 'wall options',
                              'door open/missing and window missing/broken/open', 'camera and zoom'],
                    unverified=['mechanics-menu door/window input', 'dedicated multiplayer',
                                'performance', 'human acceptance', 'visual acceptance pending original-frame review'])
    package = ROOT/'build/rv/package/RealVehicleInteriors'
    payload = {path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(package.rglob('*')) if path.is_file()}
    payload_id = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    (h.OUTPUT/'capture-package.json').write_text(json.dumps(dict(
        sha256=payload_id, files=payload, source=str(package)), indent=2)+'\n')
    h.REPORT['capturePackageSha256'] = payload_id
    reused = set()
    for prior in args.reuse_ledger:
        for line in prior.read_text().splitlines():
            frame = json.loads(line)
            if frame['state'] != 'furnished-high':
                continue
            assert frame['capturePackageSha256'] == payload_id and frame['native'] and not frame['plain']
            assert 'nativePan=true' in frame['framingReceipt']['camera'] and Path(frame['image']).is_file()
            reused.add((frame['script'], frame['heading']))
    h.REPORT['reusedHeadings'] = sorted(reused)

    def wait(code, label, seconds=40):
        deadline = time.monotonic()+seconds
        while not h.lua(code):
            h.check(time.monotonic() < deadline, label)
            time.sleep(.15)

    def snap():
        return h.lua(snapshot)

    def options(height, near=False):
        h.lua(f'''local o=PZAPI.ModOptions:getOptions('RealVehicleInteriors')
o:getOption('wallHeight'):setValue({height});o:getOption('cameraWalls'):setValue({str(near).lower()})
o:apply();return true''')
        time.sleep(.35)

    def hide_furniture_draws():
        isolation = load('shell-isolation-tests')
        h.lua(isolation.BASELINE)
        aliases = h._sequence(h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);local P=MELens.Parts
local names={};for _,spot in ipairs(pr.spots) do for _,piece in ipairs(P.piecesFor(spot)) do
names[P.modelFile(piece,spot)]=true end end
local out={};for name in pairs(names) do out[#out+1]=name end;return out'''))
        for alias in aliases:
            h.lua('MELensRV.setKeepPlane('+json.dumps(alias)+',0,0,0,1);return true')
        return isolation, aliases

    @contextmanager
    def opening_furniture(row, heading):
        if not args.empty_opening_controls:
            yield
            return
        _, aliases = hide_furniture_draws()
        h.REPORT.setdefault('emptyOpeningControls', []).append(dict(
            script=row['script'], heading=heading, hiddenAliases=aliases,
            note='Draw-only fixture; installed items, inventories and native loose contents retained'))
        try:
            yield
        finally:
            h.lua('MELensShellIsolation.restore();MELensShellIsolation=nil;return true')

    @contextmanager
    def opening_cut(row, heading):
        if args.opening_cut_y is None:
            yield
            return
        receipt = h.lua('''local pr=MELens.profileFor(MELensTest.vehicle);local planes=pr.nativeCutPlanes or pr.cutPlanes;local old=planes[3]
local y='''+repr(args.opening_cut_y)+''';local m=pr.mesh
assert(old[1]==0 and old[2]==0 and old[3]==-1,'Diagnostic cut requires horizontal High plane')
assert(pr.nativeWallMaterial and y>pr.floorY+.2 and y<pr.floorY+pr.nativeWallMaterial.height-.01,'Diagnostic cut outside living compartment')
MELensBodyAudit.openingCut={planes=planes,plane=old};planes[3]={0,0,-1,m.lift-y/m.scale}
return {originalPlane=old,diagnosticPlane=planes[3],originalPassengerY=(m.lift-old[4])*m.scale,diagnosticPassengerY=y}''')
        h.REPORT.setdefault('openingCutFixtures', []).append(dict(script=row['script'], heading=heading,
            **receipt, scope='Temporary framing diagnostic; no production profile or saved state change'))
        try:
            options(3)
            yield
        finally:
            h.check(h.lua('''local b=MELensBodyAudit.openingCut
b.planes[3]=b.plane;local restored=b.planes[3]==b.plane
MELensBodyAudit.openingCut=nil;return restored'''), 'Diagnostic opening cut did not restore original plane')
            options(3)

    def camera(row):
        bounds = row['bounds']
        centre = [(a+b)/2 for a, b in zip(bounds['min'], bounds['max'])]
        h.lua(f'''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z()
v:getWorldPos(o:x()+{centre[0]},o:y()+pr.floorY,o:z()+{centre[2]},q)
MELensBodyAudit.focus(q:x(),q:y(),base+(o:y()+pr.floorY)/2.44949)
ISUIHandler.setVisibleAllUI(false);return true''')
        time.sleep(.3)
        for _ in range(14):
            if h.lua('return getCore():getZoom(0)') <= .51:
                break
            h.lua('getCore():doZoomScroll(0,-1);return true')
            time.sleep(.25)
        # Fit the native measured body in the viewport, including the cab/hitch.
        # The bounds receipt makes cropped/unreviewable cases detectable.
        for _ in range(14):
            receipt = h.lua('''MELensMedia.frameCamera();local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local b='''+json.dumps(bounds).replace('"min":', 'min=').replace('"max":', 'max=').replace('[', '{').replace(']', '}')+'''
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z();local loX,loY=1e9,1e9;local hiX,hiY=-1e9,-1e9
local zoom=getCore():getZoom(0)
for _,x in ipairs({b.min[1],b.max[1]}) do for _,y in ipairs({pr.floorY,b.max[2]}) do
for _,z in ipairs({b.min[3],b.max[3]}) do
v:getWorldPos(o:x()+x,o:y()+y,o:z()+z,q)
local sx,sy=ISCoordConversion.ToScreen(q:x(),q:y(),base+(o:y()+y)/2.44949)
sx=sx/zoom;sy=sy/zoom;loX=math.min(loX,sx);hiX=math.max(hiX,sx);loY=math.min(loY,sy);hiY=math.max(hiY,sy)
end end end
return {left=loX,right=hiX,top=loY,bottom=hiY,zoom=zoom,width=getCore():getScreenWidth(),height=getCore():getScreenHeight()}''')
            outside = receipt['left'] < 50 or receipt['top'] < 40 or receipt['right'] > receipt['width']-50 or receipt['bottom'] > receipt['height']-40
            if not outside:
                break
            previous = receipt['zoom']
            h.lua('getCore():doZoomScroll(0,1);return true')
            time.sleep(.25)
            h.check(h.lua('return getCore():getZoom(0)') != previous, 'Cannot fit native body in camera')
        h.check(not outside, 'Native body remains outside capture viewport')
        return receipt

    def detail_photos(row, heading, prefix, framing):
        options(args.detail_height, True)
        for _ in range(14):
            if h.lua('return getCore():getZoom(0)') <= .51:
                break
            h.lua('getCore():doZoomScroll(0,-1);return true')
            time.sleep(.25)
        for fraction, name in ((.3, 'rear'), (.7, 'front')):
            h.lua(f'''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local g=MELens.WalkGrids[pr.walkGrid];local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell*{fraction},q)
MELensBodyAudit.focus(q:x(),q:y(),base+(o:y()+pr.floorY)/2.44949);return true''')
            time.sleep(.3)
            collect(row, heading, prefix+name, framing=framing)

    def panel_input(row, heading):
        tap = load('final-water-tests')
        h.lua('ISUIHandler.setVisibleAllUI(true);return true')
        point = h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local p=MELens.Parts.panelFor(v,pr)
assert(p,'missing utility panel');local o=v:getScript():getModel():getOffset();local q=Vector3f.new()
local base=v:getWorldPos(0,0,0,q):z();v:getWorldPos(o:x()+p.x,o:y()+p.y,o:z()+p.z,q)
local sx,sy=ISCoordConversion.ToScreen(q:x(),q:y(),base+(o:y()+p.y)/2.44949)
local hit=MELens.Interact.pick(v,pr,sx,sy);assert(hit and hit.kind=='panel','rendered utility panel is not pickable')
local s=pr.shell;local part=v:getPartById(MELens.Parts.SHELL)
if pr.nativePanel and MELensRV.isPartModelVisible then local native=p==pr.nativePanel
assert(MELensRV.isPartModelVisible(part,'MELensShell'..s.nativePanelModel)==native,'native plate visibility disagrees with anchor')
assert(MELensRV.isPartModelVisible(part,'MELensShell'..s.legacyPanelModel)==not native,'legacy plate visibility disagrees with anchor') end
local zoom=getCore():getZoom(0);return {x=sx/zoom,y=sy/zoom,anchor=p,native=p==pr.nativePanel,
header=getText('IGUI_MELens_UtilityPanel'),action=getText('ContextMenu_MELens_Dashboard')}''')
        has_native_panel = h.lua('return MELens.profileFor(MELensTest.vehicle).nativePanel~=nil')
        h.check(point['native'] == (has_native_panel and not args.fallback), 'Panel input selected the wrong native/fallback anchor')
        query = '''local p=getPlayer();local root=getPlayerContextMenu(p:getPlayerNum());local seen={};local menus={}
local function add(m)
 if not m or seen[m] or not m:isVisible() then return end;seen[m]=true;local options={}
 for i,o in ipairs(m.options or {}) do local y=m:getItemY(i)+m.itemHgt/2
  if y>=m:getY() and y<=m:getY()+m:getHeight() then options[#options+1]={name=tostring(o.name),
   enabled=not o.notAvailable and not o.isDisabled,x=m:getX()+m:getWidth()/2,y=y} end
 end;menus[#menus+1]={options=options}
end;add(root);if root then for _,m in ipairs(root.instanceMap or {}) do add(m) end end
local d=MELens.Dashboard.instance;local visible=d and d:isVisible();local close
if visible and d.closeBox then close={x=d:getX()+d.closeBox.x+d.closeBox.w/2,y=d:getY()+d.closeBox.y+d.closeBox.h/2} end
return {menus=menus,dashboard=visible or false,close=close,pathing=MELens.pathing(p),
dashboardVehicleMatches=visible and d.vehicle==MELensTest.vehicle or false,
dashboardVehicleSql=visible and d.vehicle and d.vehicle:getSqlId() or nil,
queueCount=#ISTimedActionQueue.getTimedActionQueue(p).queue}'''

        def state():
            value = h.lua(query)
            value['menus'] = h._sequence(value.get('menus'))
            for menu in value['menus']:
                menu['options'] = h._sequence(menu.get('options'))
            return value

        def until(predicate, label):
            deadline = time.monotonic()+30
            while True:
                value = state()
                if time.monotonic() >= h._input_release and predicate(value):
                    return value
                h.check(time.monotonic()<deadline, 'Panel input timeout: '+label+' '+str(value))
                time.sleep(.1)

        try:
            tap.native_click(h, point['x'], point['y'], 'panel:world-menu', right=True)
            for label in (point['header'], point['action']):
                value = until(lambda s: tap.menu_option(s,label) is not None, label)
                option = tap.menu_option(value,label)
                h.check(option['enabled'], 'Utility panel option disabled: '+label)
                tap.native_click(h, option['x'], option['y'], 'panel:'+label)
            opened = until(lambda s: s['dashboard'] and s['dashboardVehicleMatches']
                           and not s['pathing'] and s['queueCount']==0, 'Dashboard bound to current vehicle')
            h.check(opened.get('close'), 'Dashboard close control missing')
            h.capture((row['script'].split('.',1)[1]+'-'+heading+'-panel-dashboard').lower())
            tap.native_click(h, opened['close']['x'], opened['close']['y'], 'panel:close-dashboard')
            until(lambda s: not s['dashboard'] and not s['pathing'] and s['queueCount']==0, 'Dashboard closed without underlying movement')
            h.REPORT.setdefault('panelInput', []).append(dict(script=row['script'],heading=heading,point=point,
                nativeMouse=True,handlersInvokedDirectly=False,openedAndClosed=True,
                authorityReceipt=dict(dashboardVisible=True,vehicleMatches=True,vehicleSql=opened['dashboardVehicleSql'])))
        finally:
            h.lua('ISUIHandler.setVisibleAllUI(false);return true')

    def collect(row, heading, state, framing='whole-body'):
        label = (row['script'].split('.', 1)[1]+'-'+heading+'-'+state).lower()
        h.lua('MELensMedia.frameCamera();return true')
        time.sleep(.2)
        framing_receipt = h.lua('''local t=MELensBodyAudit.cameraTarget;local zoom=getCore():getZoom(0)
local x,y=ISCoordConversion.ToScreen(t.x,t.y,t.z)
return {target=t,screenX=x/zoom,screenY=y/zoom,width=getCore():getScreenWidth(),height=getCore():getScreenHeight(),zoom=zoom,
camera=MELensMedia.cameraInfo and MELensMedia.cameraInfo() or 'unavailable'}''')
        h.check(abs(framing_receipt['screenX']-framing_receipt['width']/2) < 2
                and abs(framing_receipt['screenY']-framing_receipt['height']/2) < 2,
                'Capture camera did not settle on the requested physical target: '+str(framing_receipt))
        status = h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local p=getPlayer();local localPose=Vector3f.new();v:getPassengerLocalPos(v:getSeat(p),localPose)
return {script=v:getScriptName(),name=getText('IGUI_VehicleName'..(v:getScript():getCarModelName() or v:getScript():getName())),
paintHSV={v:getColorHue(),v:getColorSaturation(),v:getColorValue()},paintFixture=MELensBodyAudit.paintFixture,
avatar={world={x=p:getX(),y=p:getY(),z=p:getZ()},passenger={x=localPose:x(),y=localPose:y(),z=localPose:z()},floorY=pr.floorY},
sql=v:getSqlId(),native=MELensRV.nativeBodyWallsActive and MELensRV.nativeBodyWallsActive() or false,
flat=MELensRV.flatWheelArchActive and MELensRV.flatWheelArchActive() or false,profileNative=pr.nativeBodyWalls==true,
profileArch=pr.nativeWheelArch~=nil,
archTrim=MELensRV.nativeArchTrimActive and MELensRV.nativeArchTrimActive() or false,profileArchTrim=pr.nativeArchTrimModels~=nil,
stockWell=MELensRV.nativeWheelWellTrimActive and MELensRV.nativeWheelWellTrimActive() or false,profileStockWell=pr.nativeWheelWellTrim~=nil,
wheelInfo=MELensRV.flatWheelArchInfo and MELensRV.flatWheelArchInfo() or 'unavailable',
plain=MELensRV.bodyLiningPlainActive and MELensRV.bodyLiningPlainActive() or false,profilePlain=pr.nativePlainFinish==true,
material=MELensRV.bodyLiningMaterialActive and MELensRV.bodyLiningMaterialActive() or false,profileMaterial=pr.nativeWallMaterial,
stockMetal=MELensRV.bodyLiningStockMetalActive and MELensRV.bodyLiningStockMetalActive() or false,profileStockMetal=pr.nativeStockMetal~=nil,
bodyTrim=MELensRV.nativeBodyTrimActive and MELensRV.nativeBodyTrimActive() or false,profileBodyTrim=pr.nativeBodyTrim~=nil,
partition=MELensRV.nativeCabPartitionActive and MELensRV.nativeCabPartitionActive() or false,profilePartition=pr.nativeCabPartition==true,
roofCuts=MELensRV.nativeRoofCutsActive and MELensRV.nativeRoofCutsActive() or false,profileRoofCuts=pr.nativeRoofCuts~=nil,
profileSurfaceCuts=pr.nativeSurfaceCuts~=nil,
nearFaceCount=MELensRV.nativeNearFaceCount and MELensRV.nativeNearFaceCount() or 0,profileNearFaceCount=#(pr.nativeNearFaces or {}),
culling=MELensRV.nativeBodyWallsInfo and MELensRV.nativeBodyWallsInfo() or 'unavailable',
shaderError=MELensRV.shaderError(),shell=pr.shell.models,spots=#pr.spots,walkGrid=pr.walkGrid}''')
        status['wallOptions'] = h.lua('''local o=PZAPI.ModOptions:getOptions('RealVehicleInteriors')
local choice=o:getOption('wallHeight'):getValue();local pr=MELens.profileFor(MELensTest.vehicle)
local native=MELensRV.setNativeBodyWalls and pr.nativeBodyWalls and
 (not pr.nativeRoofCuts or (MELensRV.setNativeRoofCut and MELensRV.clearNativeRoofCuts))
return {height=choice,cameraWalls=o:getOption('cameraWalls'):getValue(),profilePlane=(native and pr.nativeCutPlanes or pr.cutPlanes)[choice],legacyPlane=pr.cutPlanes[choice],diagnosticOpeningCut=MELensBodyAudit.openingCut~=nil}''')
        h.check(status['script'] == row['script'], 'Wrong native vehicle captured')
        native_profile = row['script'] in row['nativeWallScripts']
        expected_native = native_profile and not args.fallback
        h.check(status['profileNative'] == native_profile, 'Loaded profile differs from wall policy')
        h.check(status['profilePlain'] == row['plainFinish'], 'Loaded profile differs from finish policy')
        h.check(status['plain'] == (row['plainFinish'] and not args.fallback), 'Plain finish leaked across vehicle policies')
        h.check(status['native'] == expected_native, 'Vanilla/KI5 native-wall scope mismatch')
        h.check(status['material'] == (bool(status.get('profileMaterial')) and not args.fallback),
                'Curved wall material did not match the loaded profile')
        h.check(status['partition'] == (status['profilePartition'] and not args.fallback),
                'Measured native cab partition did not match the loaded profile')
        h.check(status['roofCuts'] == ((status['profileRoofCuts'] or status['profileSurfaceCuts']) and not args.fallback),
                'Shared native roof/surface cuts did not match the loaded profile')
        h.check(status['nearFaceCount'] == (status['profileNearFaceCount'] if expected_native else 0),
                'Source-qualified side-edge classifications did not match the loaded profile')
        h.check(status['bodyTrim'] == (status['profileBodyTrim'] and not args.fallback),
                'Measured hitch trim did not match the loaded profile')
        h.check(status['flat'] == (expected_native and status['profileArch']),
                'Flat-floor arch mode differs from the loaded profile')
        h.check(status['archTrim'] == (expected_native and status['profileArch'] and status['profileArchTrim']),
                'Rear fitting trim differs from the loaded profile')
        h.check(status['stockWell'] == (expected_native and status['profileStockWell']),
                'Embedded stock wheel-well trim differs from the loaded profile')
        h.check(not status.get('shaderError'), 'Cutaway shader failed: '+str(status.get('shaderError')))
        if args.require_wheel_mask and expected_native and status['profileArch']:
            wheel_draws = dict(pair.split('=', 1) for pair in status['wheelInfo'].split(';'))
            current = int(wheel_draws['wheels'])
            key = row['script']+'-'+heading
            previous = h.REPORT.setdefault('wheelMaskPrevious', {}).get(key)
            if previous is not None:
                h.check(current > previous, 'No actual wheel-mask draw between frames: '+key)
            h.REPORT['wheelMaskPrevious'][key] = current
            if status['profileArchTrim']:
                fitting_draws = int(wheel_draws['fittings'])
                previous_fittings = h.REPORT.setdefault('fittingMaskPrevious', {}).get(key)
                if previous_fittings is not None:
                    h.check(fitting_draws > previous_fittings, 'No rear fitting-mask draw between frames: '+key)
                h.REPORT['fittingMaskPrevious'][key] = fitting_draws
        elif args.require_wheel_mask:
            h.REPORT.setdefault('wheelMaskNotRequired', {})[row['script']+'-'+heading] = dict(
                profileArch=status['profileArch'],native=expected_native,
                reason='No measured arch mask configured; ordinary raised floor/native wheel draws retained')
        if expected_native:
            counts = {key: int(value) for key, value in (pair.split('=', 1) for pair in status['culling'].split(';'))}
            h.check(counts['draws'] > 0 and counts['stateErrors'] == 0, 'Two-sided native draw inactive or leaked state')
        survey_key = row['script']+'-'+heading
        if args.draw_survey and survey_key not in h.REPORT.get('drawSurveys', {}):
            h.lua('MELensRV.setSurvey(true);return true')
            try:
                time.sleep(.25)
                h.REPORT.setdefault('drawSurveys', {})[survey_key] = h.lua('return MELensRV.surveyInfo()')
            finally:
                h.lua('MELensRV.setSurvey(false);return true')
        path = h.capture(label)
        pose = h.lua('''local v=MELensTest.vehicle;local a,b=Vector3f.new(),Vector3f.new()
v:getWorldPos(0,0,0,a);v:getWorldPos(0,0,1,b)
return {x=a:x(),y=a:y(),z=a:z(),forwardX=b:x()-a:x(),forwardY=b:y()-a:y(),angles={v:getAngleX(),v:getAngleY(),v:getAngleZ()}}''')
        return_bindings = h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
local shell=v:getPartById('MELensShell');local out={windows={},wheels={}}
for _,trim in ipairs(pr.shell.windowReturns or {}) do
out.windows[#out.windows+1]={model=trim.model,part=trim.part,parent=trim.parent,
visible=MELensRV.isPartModelVisible(shell,'MELensShell'..trim.model)} end
for _,field in ipairs({'wheelCoversModel','wheelFloorModel','wheelWallModel'}) do
local index=pr.shell[field];if index then out.wheels[#out.wheels+1]={field=field,model=index,
name=pr.shell.models[index],visible=MELensRV.isPartModelVisible(shell,'MELensShell'..index)} end end;return out''')
        record = dict(family=row['family'], familyTitle=row['title'], heading=heading, state=state, framing=framing,
                      framingReceipt=framing_receipt, pose=pose, image=path, capturePackageSha256=payload_id, **status)
        record['windowReturnBindings'] = h._sequence(return_bindings.get('windows'))
        record['wheelBindings'] = h._sequence(return_bindings.get('wheels'))
        if row['script'] in projected_points:
            lua_points = '{'+','.join('{name='+json.dumps(point['name'])+',x='+str(point['x'])
                                      +',y='+str(point['y'])+',z='+str(point['z'])+'}'
                                      for point in projected_points[row['script']])+'}'
            record['projectedPoints'] = h.lua('''local out={};local v=MELensTest.vehicle
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local zoom=getCore():getZoom(0);local base=v:getWorldPos(0,0,0,q):z()
for _,p in ipairs('''+lua_points+''') do v:getWorldPos(o:x()+p.x,o:y()+p.y,o:z()+p.z,q)
local x,y=ISCoordConversion.ToScreen(q:x(),q:y(),base+(o:y()+p.y)/2.44949)
out[#out+1]={name=p.name,screenX=x/zoom,screenY=y/zoom} end;return out''')
        with ledger.open('a', encoding='utf-8') as output:
            output.write(json.dumps(record)+'\n')
        h.REPORT.setdefault('frames', []).append(record)

    def doors(opened, only=None):
        selected = [only] if isinstance(only, str) else only
        predicate = (' and ('+' or '.join('id=='+json.dumps(part) for part in selected)+')') if selected else ''
        h.lua('''local v=MELensTest.vehicle;for _,id in ipairs(MELensBodyAudit.doors) do
local part=v:getPartById(id);local opened='''+str(opened).lower()+predicate+'''
part:getDoor():setOpen(opened);v:playPartAnim(part,opened and 'Opened' or 'Closed')
assert(part:getDoor():isOpen()==opened,'Door fixture did not retain requested state: '..id) end;return true''')
        time.sleep(.4)

    def reenter():
        # Use the same real approach as initial entry so the native nearby-part
        # cache observes movement; teleporting alone can retain the exit cache.
        beds.enter_existing(h)
        key = int(h.lua('return getCore():getKey("Interact")'))
        wait('return getPlayer():getVehicle()==MELensTest.vehicle and MELens.isStanding(getPlayer()) and #ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0', 'Native re-entry timed out')
        h.REPORT['inputs'].append(dict(action='reenter', key=key, api='MEMCNativeLab.holdKey'))

    def enter_case(row, heading, px, py):
        h.lua(f'''local p=getPlayer();assert(not p:getVehicle());MELensMedia.cameraOff()
p:setX({px});p:setY({py});p:setLastX(p:getX());p:setLastY(p:getY());getGameTime():setTimeOfDay(12);return true''')
        h.check(h.lua('''local old=MELensTest.vehicle
return not old or not MELensBodyAudit.preserved[old:getSqlId()]'''), 'Spawn would remove a preserved fixture')
        beds.enter(h, row['script'], heading)
        h.check(h.lua('return getPlayer():getVehicle()==MELensTest.vehicle'), 'Interact entered a different vehicle')
        if args.paint_hsv is not None:
            h.check(row['plainFinish'], 'Fixed native paint fixture is vanilla-only')
            hue,saturation,value=args.paint_hsv
            paint=h.lua(f'''local v=MELensTest.vehicle;v:setColorHSV({hue},{saturation},{value})
MELensBodyAudit.paintFixture={{kind='native HSV render fixture; not paint-menu input',requested={{{hue},{saturation},{value}}}}}
return {{v:getColorHue(),v:getColorSaturation(),v:getColorValue()}}''')
            h.check(all(abs(actual-wanted)<.00001 for actual,wanted in zip(h._sequence(paint),args.paint_hsv)), 'Native colour fixture did not retain requested HSV')
            time.sleep(.3)
        else:
            h.lua('MELensBodyAudit.paintFixture=nil;return true')
        h.REPORT['inputs'].append(dict(action='enter', script=row['script'], heading=heading,
                                      binding='Interact', api='MEMCNativeLab.holdKey'))
        h.REPORT['nativeInput'] = True
        contract = h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v)
MELensLifecycle={vehicle=v};MELensBodyAudit.doors={};local windows={};local renderParts={};local components={}
for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i);local id=part:getId()
if id=='E150Divider' then local item=part:getInventoryItem()
components[#components+1]={part=id,item=item and item:getID(),uninstalled=part:isInventoryItemUninstalled(),
model='E150Div',modelVisible=MELensRV.isPartModelVisible(part,'E150Div')} end
if part:getDoor() and (id:sub(1,4)=='Door' or id=='TrunkDoor')
and (id==pr.standing.door or (id~='DoorFrontLeft' and id~='DoorFrontRight')) then
local models=part:getScriptPart():getModelCount();local types=part:getItemType()
local physical=models>0 or (types and not types:isEmpty()) or id==pr.standing.door
if physical then MELensBodyAudit.doors[#MELensBodyAudit.doors+1]=id end
renderParts[#renderParts+1]={part=id,kind=physical and 'door' or 'entry-hook',models=models} end
local glazing=(id:sub(1,6)=='Window' or id:sub(1,10)=='Windshield') and not id:lower():find('armor',1,true)
if (part:getWindow() or (glazing and part:getScriptPart():getModelCount()>0))
and (pr.kind=='camper' or (id~='WindowFrontLeft' and id~='WindowFrontRight' and id~='Windshield')) then
windows[#windows+1]=id;renderParts[#renderParts+1]={part=id,kind=part:getWindow() and 'window' or 'fixed-window',models=part:getScriptPart():getModelCount()} end end
local g=MELens.WalkGrids[pr.walkGrid];MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell/2)
return {doors=MELensBodyAudit.doors,windows=windows,renderParts=renderParts,components=components}''')
        h.REPORT.setdefault('partContracts', []).append(dict(
            script=row['script'], heading=heading,
            source='live resolved vehicle script part models',
            components=h._sequence(contract.get('components')),
            parts=[dict(part, renderPath='separate native models' if part['models']
                        else 'native passenger-entry hook; no independent leaf' if part['kind']=='entry-hook'
                        else 'embedded body mask; no separate animated leaf' if row['plainFinish']
                        else 'native logical opening; inspect source animation')
                   for part in h._sequence(contract.get('renderParts'))]))
        wait('return not MELens.pathing(getPlayer())', 'Aisle walk timed out')
        doors(False)
        return contract, snap()

    def exit_case(row, heading):
        h.lua('''local p=getPlayer();local marker=MELens.profileFor(MELensTest.vehicle).exitMarker
MELens.walkTo(p,marker.x,marker.z);return true''')
        wait('return not MELens.pathing(getPlayer())', 'Exit approach timed out')
        key = int(h.lua('return getCore():getKey("Interact")'))
        h.lua(f'MEMCNativeLab.holdKey({key},200);return true')
        wait('return not getPlayer():getVehicle()', 'Native exit timed out')
        h.REPORT['inputs'].append(dict(action='exit', script=row['script'], heading=heading,
                                      key=key, api='MEMCNativeLab.holdKey'))
        h.check(h.lua('''return not (MELensRV.nativeBodyWallsActive and MELensRV.nativeBodyWallsActive())
and not (MELensRV.flatWheelArchActive and MELensRV.flatWheelArchActive())'''), 'Render feature leaked after exit')

    try:
        h.lua('MELensMedia.cameraOff();MELensMedia.cameraNativePan('+str(args.native_camera).lower()+');return true')
        h.REPORT['cameraMode'] = 'native deferred pan' if args.native_camera else 'legacy direct offsets'
        available = h._sequence(h.lua('''local out={};for name,pr in pairs(MELens.Profiles) do
out[#out+1]={script=name,available=ScriptManager.instance:getVehicle(name)~=nil,walkGrid=pr.walkGrid}
end;return out'''))
        (h.OUTPUT/'inventory.json').write_text(json.dumps(available, indent=2))
        h.check(len(available) == 203, 'Loaded supported inventory differs from source')
        missing = [row['script'] for row in available if not row['available']]
        h.REPORT['missingScripts'] = missing
        h.check(not missing, 'Optional dependency missing from native audit: '+str(missing))
        # Preserve every pre-existing loaded vehicle. The shared spawn helper
        # is allowed to remove only the preceding fixture created by this run.
        h.lua('''local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);MELensTest={all={}};MELensBodyAudit={preserved={},locations={},doors={}}
local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next()
if MELens.profileFor(v) then local sql=v:getSqlId();MELensBodyAudit.preserved[sql]=v
MELensBodyAudit.locations[tostring(sql)]={x=v:getX(),y=v:getY(),z=v:getZ()} end end;MELensMedia.cameraOff();return true''')
        h.lua('''MELensBodyAudit.focus=function(x,y,z)
MELensBodyAudit.cameraTarget={x=x,y=y,z=z};MELensMedia.camera(x,y,z);MELensMedia.frameCamera()
end;return true''')
        h.lua('MELensBodyAudit.snapshot=function(vehicle) '+snapshot.replace('local v=MELensLifecycle.vehicle', 'local v=vehicle')+' end;return true')
        preserved = h.lua('''local out={};for sql,v in pairs(MELensBodyAudit.preserved) do
out[tostring(sql)]=MELensBodyAudit.snapshot(v) end;return out''') or {}
        h.REPORT['preservedBefore'] = preserved
        preserved_locations = h.lua('return MELensBodyAudit.locations') or {}
        h.REPORT['preservedLocations'] = preserved_locations
        h.REPORT['world'] = h.lua('return getWorld():getWorld()')
        pad = h.lua('''local survey={};local chosen;local pads={}
local p=getPlayer();local cx=math.floor(p:getX()/10)*10;local cy=math.floor(p:getY()/10)*10
local offsets={0};for d=5,60,5 do offsets[#offsets+1]=d;offsets[#offsets+1]=-d end
for _,d in ipairs(offsets) do for _,e in ipairs(offsets) do
pads[#pads+1]={cx+d,cy+e} end end
for _,pad in ipairs(pads) do
local missing,blocked=0,0
for x=pad[1]-9,pad[1]+9 do for y=pad[2]-9,pad[2]+9 do local sq=getCell():getGridSquare(x,y,0)
if not sq then missing=missing+1 else for i=1,sq:getObjects():size()-1 do
local s=sq:getObjects():get(i):getSprite();local n=s and s:getName() or '?'
if not n:find('^vegetation_') and not n:find('^e_') and not n:find('^f_bushes') and not n:find('^blends_grassoverlays_')
and not n:find('^d_plants') and not n:find('^d_generic') and not n:find('^boulders') then blocked=blocked+1 end end end end end
local it=getCell():getVehicles():iterator();while it:hasNext() do local v=it:next()
if math.abs(v:getX()-pad[1])<9 and math.abs(v:getY()-pad[2])<9 then blocked=blocked+1 end end
survey[#survey+1]={x=pad[1],y=pad[2],missing=missing,blocked=blocked}
if missing==0 and blocked==0 then chosen={x=pad[1],y=pad[2]};break end end
return {chosen=chosen,survey=survey}''')
        h.REPORT['pad'] = pad
        h.check(pad.get('chosen'), 'No clear loaded fleet audit pad; see retained square survey')
        px, py = pad['chosen']['x']+4.5, pad['chosen']['y']+.5
        stopped = False
        for row in cases:
            if (run/'stop-capture.json').exists():
                stopped = True
                break
            case_headings = [heading for heading in headings if (row['script'], heading) not in reused]
            if not case_headings:
                continue
            h.REPORT['activeScript'] = row['script']
            print('BODY_START '+row['family']+' '+row['script'], flush=True)
            for heading in case_headings:
                contract, before = enter_case(row, heading, px, py)
                opening_contract = dict(contract)
                if args.opening_part:
                    requested = set(args.opening_part)
                    actual = {part for kind in ('doors', 'windows') for part in h._sequence(contract.get(kind))}
                    h.check(requested <= actual, 'Focused opening part absent from live contract: '+str(requested-actual))
                    for kind in ('doors', 'windows'):
                        opening_contract[kind] = [part for part in h._sequence(contract.get(kind)) if part in requested]
                    h.REPORT.setdefault('focusedOpeningParts', []).append(dict(script=row['script'],heading=heading,parts=args.opening_part))
                options(3)
                framing = camera(row)
                h.REPORT.setdefault('framing', []).append(dict(script=row['script'], heading=heading, **framing))
                if args.photos_only or (args.variants and args.native_camera):
                    # Photograph the normal playable cutaway: retain far-wall
                    # detail while dropping the wall nearest the camera.
                    options(3, True)
                if args.variants:
                    collect(row, heading, 'furnished-high')
                else:
                    for height in (1, 2, 3):
                        options(height)
                        collect(row, heading, 'closed-height-'+str(height))
                    options(2, True)
                    collect(row, heading, 'camera-cut')
                    with opening_furniture(row, heading), opening_cut(row, heading):
                        options(3)
                        selected_doors = h._sequence(opening_contract.get('doors'))
                        for door in selected_doors:
                            doors(True, door)
                            collect(row, heading, door+'-open')
                        if selected_doors or not args.opening_part:
                            if args.opening_part:
                                doors(True, selected_doors)
                            else:
                                doors(True)
                            collect(row, heading, 'all-open')
                        doors(False)
                        collect(row, heading, 'closed-restored')
                        for kind in ('doors', 'windows'):
                            for part in h._sequence(opening_contract.get(kind)):
                                h.lua('''local part=MELensTest.vehicle:getPartById('''+json.dumps(part)+''')
    MELensBodyAudit.removed=part:getInventoryItem();part:setInventoryItem(nil);return true''')
                                time.sleep(.4)
                                collect(row, heading, part+'-missing')
                                h.lua('''MELensTest.vehicle:getPartById('''+json.dumps(part)+'''):setInventoryItem(MELensBodyAudit.removed)
    MELensBodyAudit.removed=nil;return true''')
                                time.sleep(.4)
                                collect(row, heading, part+'-restored')
                                if kind == 'windows':
                                    damageable = h.lua('''local p=MELensTest.vehicle:getPartById('''+json.dumps(part)+''');local w=p:getWindow();local item=p:getInventoryItem()
    MELensBodyAudit.windowBefore={item=item,condition=p:getCondition(),itemCondition=item and item:getCondition(),opened=w and w:isOpen(),delta=w and w:getOpenDelta()}
    if w then w:setOpen(false);w:damage(w:getHealth());assert(w:isDestroyed() and not p:getInventoryItem(),'native pane damage did not remove destroyed glass') end
    return w~=nil''')
                                    time.sleep(.3)
                                    collect(row, heading, part+('-broken' if damageable else '-fixed-installed-control'))
                                    h.lua('''local p=MELensTest.vehicle:getPartById('''+json.dumps(part)+''');local b=MELensBodyAudit.windowBefore
    p:setInventoryItem(b.item);p:setCondition(b.condition);local item=p:getInventoryItem();if item and b.itemCondition then item:setCondition(b.itemCondition) end
    local w=p:getWindow();if w then w:setOpen(b.opened);w:setOpenDelta(b.delta) end
    assert(not p:getWindow() or not p:getWindow():isDestroyed(),'pane repair did not restore native window');return true''')
                                    time.sleep(.3)
                                    collect(row, heading, part+'-repaired')
                                    openable=h.lua('local w=MELensTest.vehicle:getPartById('+json.dumps(part)+'):getWindow();return w and w:isOpenable() or false')
                                    if openable:
                                        h.lua('''local w=MELensTest.vehicle:getPartById('''+json.dumps(part)+'''):getWindow()
    w:setOpen(true);w:setOpenDelta(1);assert(w:isOpen());return true''')
                                        time.sleep(.3)
                                        collect(row, heading, part+'-open')
                                        h.lua('''local w=MELensTest.vehicle:getPartById('''+json.dumps(part)+'''):getWindow();local b=MELensBodyAudit.windowBefore
    w:setOpen(b.opened);w:setOpenDelta(b.delta);return true''')
                                        time.sleep(.3)
                                        collect(row, heading, part+'-closed-restored')
                                    h.lua('MELensBodyAudit.windowBefore=nil;return true')
                if args.panel_input:
                    panel_input(row, heading)
                    camera(row)
                if args.photos_only:
                    if args.door_photo_part:
                        h.check(args.door_photo_part in h._sequence(contract.get('doors')), 'Door photography part absent from live native contract')
                        for leaf_pose in ('closed-control', 'open', 'closed-restored'):
                            doors(leaf_pose == 'open', args.door_photo_part)
                            camera(row)
                            collect(row, heading, 'leaf-'+args.door_photo_part+'-'+leaf_pose,
                                    framing='whole body; native door pose fixture, not mechanics-menu input')
                    if args.empty_photos:
                        _, aliases = hide_furniture_draws()
                        try:
                            collect(row, heading, 'empty-high', framing='whole body; furniture draws hidden only')
                            detail_photos(row, heading, 'empty-detail-',
                                          'empty interior detail; native loose contents remain; whole body may crop')
                        finally:
                            h.lua('MELensShellIsolation.restore();MELensShellIsolation=nil;return true')
                        time.sleep(.3)
                        collect(row, heading, 'furniture-restored', framing='front detail after restoring all keep planes; whole body may crop')
                        h.REPORT.setdefault('emptyControls', []).append(dict(script=row['script'], heading=heading,
                            hiddenAliases=aliases, note='Photography draw-only floor review; installed state unchanged'))
                    h.check(snap() == before, 'Photography changed inventory, utilities or installed item IDs')
                    exit_case(row, heading)
                    h.check(snap() == before, 'Photography entry/exit changed committed vehicle state')
                    continue
                if args.isolate:
                    options(args.isolate_height)
                    h.lua('''local v=MELensTest.vehicle;local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
local o=v:getScript():getModel():getOffset();local q=Vector3f.new();local base=v:getWorldPos(0,0,0,q):z()
v:getWorldPos(o:x(),o:y()+pr.floorY,o:z()+g.z0+#g.rows*g.cell/2,q)
MELensBodyAudit.focus(q:x(),q:y(),base+(o:y()+pr.floorY)/2.44949);return true''')
                    for _ in range(14):
                        if h.lua('return getCore():getZoom(0)') <= .51:
                            break
                        h.lua('getCore():doZoomScroll(0,-1);return true')
                        time.sleep(.25)
                    time.sleep(.3)
                    isolation, isolation_furniture = hide_furniture_draws()
                    h.REPORT.setdefault('isolationBaselines', []).append(h.lua('return {planes=MELensShellIsolation.planes,hiddenFurniture=true}'))
                    controls = [('body', 'body'), ('support', 'support'), ('arch', 'arch-wall'), ('tyres', 'tyres')]
                    if args.isolate_only:
                        controls = [control for control in controls if control[0] in args.isolate_only]
                    controls += [('alias', alias) for alias in (args.isolate_alias or [])]
                    for field, suffix in controls:
                        if field in ('support', 'arch'):
                            token = '_support' if field == 'support' else '_wheel_wall'
                            aliases = h._sequence(h.lua('''local out={};for _,model in ipairs(MELens.profileFor(MELensTest.vehicle).shell.models) do
if model:find('''+json.dumps(token)+''',1,true) then out[#out+1]=model end end;return out'''))
                        elif field == 'alias':
                            aliases = [suffix]
                        else:
                            aliases = row['bodyAliases' if field == 'body' else 'tyreAliases']
                        if not aliases:
                            continue
                        collect(row, heading, 'isolate-control-'+suffix, framing='fixed cabin isolation; whole body may crop')
                        if field == 'tyres':
                            # Unmodified road-wheel draws bypass the cutaway
                            # shader. Hide actual model bindings instead of
                            # pretending a keep plane can affect that path.
                            h.lua('MELensBodyAudit.hiddenModels={};MELensBodyAudit.hiddenModelKeys={};return true')
                            for model in row['tyreModels']:
                                h.lua('''local v=MELensTest.vehicle;local pattern='''+json.dumps(model['part'])+'''
for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i);local partId=part:getId()
if partId==pattern or (pattern:sub(-1)=='*' and partId:sub(1,#pattern-1)==pattern:sub(1,-2)) then
local id='''+json.dumps(model['model'])+''';local key=partId..':'..id
if not MELensBodyAudit.hiddenModelKeys[key] then
MELensBodyAudit.hiddenModelKeys[key]=true;local visible=MELensRV.isPartModelVisible(part,id)
MELensBodyAudit.hiddenModels[#MELensBodyAudit.hiddenModels+1]={part=part,model=id,visible=visible}
if visible then part:setModelVisible(id,false) end end end end;return true''')
                        else:
                            for alias in aliases:
                                h.lua('MELensRV.setKeepPlane('+json.dumps(alias)+',0,0,0,1);return true')
                        time.sleep(.4)
                        if field == 'tyres':
                            hidden = h.lua('''local count=0;for _,row in ipairs(MELensBodyAudit.hiddenModels) do
if row.visible then count=count+1 end
assert(not MELensRV.isPartModelVisible(row.part,row.model),'wheel visibility fixture was reset') end;return count''')
                            h.check(hidden > 0, 'Tyre isolation hid no live native bindings')
                            h.REPORT.setdefault('tyreIsolation', []).append(dict(script=row['script'], heading=heading, hiddenBindings=hidden))
                        collect(row, heading, 'isolate-hidden-'+suffix, framing='fixed cabin isolation; whole body may crop')
                        if field == 'tyres':
                            h.lua('''for _,row in ipairs(MELensBodyAudit.hiddenModels) do
if row.visible then row.part:setModelVisible(row.model,true) end
assert(MELensRV.isPartModelVisible(row.part,row.model)==row.visible,'wheel model restoration changed a binding')
end;MELensBodyAudit.hiddenModels=nil;MELensBodyAudit.hiddenModelKeys=nil;return true''')
                        # Reapply the entire source map; do not replace a real
                        # prior clipping plane with an arbitrary neutral value.
                        h.lua(isolation.RESTORE)
                        for alias in isolation_furniture:
                            h.lua('MELensRV.setKeepPlane('+json.dumps(alias)+',0,0,0,1);return true')
                        time.sleep(.3)
                        collect(row, heading, 'isolate-restored-'+suffix, framing='fixed cabin isolation; whole body may crop')
                    h.lua('MELensShellIsolation.restore();MELensShellIsolation=nil;return true')
                if args.empty_controls:
                    isolation, aliases = hide_furniture_draws()
                    camera(row)
                    for height in (1, 2, 3):
                        options(height)
                        collect(row, heading, 'empty-height-'+str(height))
                    options(2, True)
                    collect(row, heading, 'empty-camera-cut')
                    detail_photos(row, heading, 'empty-detail-',
                                  'empty interior detail; native loose contents remain; whole body may crop')
                    h.lua('MELensShellIsolation.restore();MELensShellIsolation=nil;return true')
                    time.sleep(.3)
                    collect(row, heading, 'furniture-restored', framing='front detail after restoring all keep planes; whole body may crop')
                    h.REPORT.setdefault('emptyControls', []).append(dict(script=row['script'], heading=heading,
                        hiddenAliases=aliases, note='Furniture draws hidden only; installed item IDs, containers and native loose contents unchanged'))
                # Overlapping cabin details make joins/furniture clearance
                # reviewable even when the whole bus/camper needs a wide view.
                detail_photos(row, heading, 'interior-detail-', 'interior detail; whole body may crop')
                if args.loose_controls:
                    _, hidden_furniture = hide_furniture_draws()
                    options(3, True)
                    pose_query = '''local v=MELensTest.vehicle;return {clock=getGameTime():getWorldAgeHours(),x=v:getX(),y=v:getY(),z=v:getZ(),angles={v:getAngleX(),v:getAngleY(),v:getAngleZ()}}'''
                    h.lua('setGameSpeed(0);return true')
                    loose_pose = h.lua(pose_query)
                    h.lua('MELensBodyAudit.looseTick=MELens.LooseView.onTick;return true')
                    try:
                        collect(row, heading, 'loose-control', framing='paused empty furniture; retained native loose contents')
                        h.lua('MELens.LooseView.onTick=function() end;MELensRV.clearLoose();return true')
                        collect(row, heading, 'loose-hidden', framing='paused draw-only loose contents hidden; inventories unchanged')
                    finally:
                        h.lua('MELens.LooseView.onTick=MELensBodyAudit.looseTick;MELensBodyAudit.looseTick=nil;MELens.LooseView.refresh();MELens.LooseView.onTick();return true')
                    collect(row, heading, 'loose-restored', framing='paused exact loose item draws restored')
                    h.check(h.lua(pose_query)==loose_pose, 'Loose attribution changed tick or vehicle pose')
                    h.REPORT.setdefault('looseControls',[]).append(dict(script=row['script'],heading=heading,pose=loose_pose,inventoryPreserved=True))
                    h.lua('MELensShellIsolation.restore();MELensShellIsolation=nil;setGameSpeed(1);return true')
                if alias_groups:
                    # Keep bindings/transforms alive. Removing/recreating part
                    # models while paused leaves native transforms uninitialized.
                    # The existing keep-plane map restores without that mutation.
                    _, hidden_furniture = hide_furniture_draws()
                    options(args.alias_wall_height, args.alias_camera_walls)
                    pose_query = '''local v=MELensTest.vehicle;return {clock=getGameTime():getWorldAgeHours(),
x=v:getX(),y=v:getY(),z=v:getZ(),angles={v:getAngleX(),v:getAngleY(),v:getAngleZ()}}'''
                    try:
                        h.lua('setGameSpeed(0);return true')
                        alias_pose = h.lua(pose_query)
                        for index, control in enumerate(alias_groups, 1):
                            aliases, plane = control['aliases'], control['plane']
                            suffix = f'alias-model-{index:02d}'
                            collect(row, heading, suffix+'-control', framing='paused front detail; furniture draws hidden')
                            try:
                                for alias in aliases:
                                    h.lua('MELensRV.setKeepPlane('+json.dumps(alias)+','+','.join(str(v) for v in plane)+');return true')
                                time.sleep(.3)
                                collect(row, heading, suffix+'-hidden', framing='paused front detail; exact model aliases clipped')
                                h.check(h.lua(pose_query) == alias_pose, 'Alias control changed simulation tick or pose')
                                h.REPORT.setdefault('aliasControls', []).append(dict(script=row['script'], heading=heading,
                                    group=index, aliases=aliases, plane=plane, pose=alias_pose,
                                    wallHeight=args.alias_wall_height, cameraWalls=args.alias_camera_walls))
                            finally:
                                h.lua('MELensShellIsolation.restore();return true')
                                for alias in hidden_furniture:
                                    h.lua('MELensRV.setKeepPlane('+json.dumps(alias)+',0,0,0,1);return true')
                            collect(row, heading, suffix+'-restored', framing='paused front detail; captured keep-plane map restored')
                            h.check(h.lua(pose_query) == alias_pose, 'Alias restoration changed simulation tick or pose')
                    finally:
                        h.lua('MELensShellIsolation.restore();MELensShellIsolation=nil;setGameSpeed(1);return true')
                if args.material_controls:
                    options(3)
                    bit_isolation = None
                    bit_pose = None
                    pose_query = '''local v=MELensTest.vehicle;return {clock=getGameTime():getWorldAgeHours(),
x=v:getX(),y=v:getY(),z=v:getZ(),angles={v:getAngleX(),v:getAngleY(),v:getAngleZ()}}'''
                    if args.surface_bitplanes:
                        bit_isolation, bit_aliases = hide_furniture_draws()
                        options(args.surface_height, True)
                        h.REPORT['surfaceBitplaneHiddenFurniture'] = bit_aliases
                    modes = [(0, 'finish'), (1, 'normals'), (2, 'source-rgb'),
                             (3, 'part-mask'), (4, 'paint-alpha')]
                    if args.surface_coordinates:
                        h.check(h.lua('return MELensRV.bodyLiningDebugMode~=nil'), 'Bridge lacks surface-coordinate diagnostics')
                        modes += [(5, 'first-uv'), (6, 'body-position')]
                        h.REPORT['surfaceCoordinateEncoding'] = dict(
                            scope='UV/position diagnostics include selected native body/door pixels outside ordinary lining scope; floor-relative height clamps below the floor',
                            firstUV='R=U; G=V; B=0; each clamped0..1',
                            bodyPosition='passengerX=2*R-1; front=8*G-4; heightAboveRoomFloor=2*B, metres',
                            precision='Binary planes encode 8bits: X~0.00784m; front~0.03137m; height~0.00784m',
                            limits='Float colours are affected by game postprocessing; use binary planes on opaque pixels and avoid antialiased edges')
                        if args.surface_bitplanes:
                            modes += [(7+i, 'uv-bit-'+str(i)) for i in range(8)]
                            modes += [(15+i, 'position-bit-'+str(i)) for i in range(8)]
                    modes.append((0, 'restored'))
                    try:
                        if args.surface_bitplanes:
                            h.lua('setGameSpeed(0);return true')
                            bit_pose = h.lua(pose_query)
                            h.REPORT['surfaceBitplanePose'] = bit_pose
                        for mode, name in modes:
                            h.lua(f'MELensRV.setBodyLiningDebugMode({mode});return true')
                            if args.surface_coordinates:
                                h.check(h.lua('return MELensRV.bodyLiningDebugMode()') == mode, 'Requested surface diagnostic mode did not activate')
                            time.sleep(.3)
                            collect(row, heading, 'material-'+name, framing='fixed front detail material diagnostic; whole body may crop')
                            if bit_pose is not None:
                                h.check(h.lua(pose_query) == bit_pose, 'Surface bitplanes did not retain identical tick and vehicle pose')
                    finally:
                        h.lua('MELensRV.setBodyLiningDebugMode(0);setGameSpeed(1);return true')
                        if bit_isolation is not None:
                            h.lua('MELensShellIsolation.restore();MELensShellIsolation=nil;return true')
                    h.REPORT.setdefault('materialControls', []).append(dict(script=row['script'], heading=heading,
                        note='Normals RGB: inward class, upward class, reverse GL winding; part masks and alpha are source data'))
                h.check(snap() == before, 'Renderer fixtures changed inventory, utilities or installed item IDs')
                exit_case(row, heading)
                camera(row)
                h.capture((row['script'].split('.', 1)[1]+'-'+heading+'-outside').lower())
                reenter()
                camera(row)
                collect(row, heading, 'reentered')
                h.check(snap() == before, 'Entry/exit changed committed vehicle state')
                h.lua('MELensTest.vehicle:exit(getPlayer());return true')  # next-case setup only
            if args.variants and len(headings) > 1:
                views = [frame for frame in h.REPORT['frames'] if frame['script'] == row['script'] and frame['state'] == 'furnished-high']
                for i, left in enumerate(views):
                    for right in views[i+1:]:
                        a, b = left['pose'], right['pose']
                        dot = (a['forwardX']*b['forwardX']+a['forwardY']*b['forwardY']) / (
                            (a['forwardX']**2+a['forwardY']**2)*(b['forwardX']**2+b['forwardY']**2))**.5
                        h.check(dot < .95, 'Distinct headings produced repeated physical vehicle poses')
            print('BODY_DONE '+row['family']+' '+row['script'], flush=True)
            h.REPORT.setdefault('completedScripts', []).append(row['script'])
            (h.OUTPUT/'native-progress.json').write_text(json.dumps(h.REPORT, indent=2)+'\n')
        h.lua('''local v=MELensTest.vehicle;assert(not MELensBodyAudit.preserved[v:getSqlId()])
v:permanentlyRemove();MELensTest={all={}};MELensMedia.cameraOff();return true''')
        # Reacquire the saved identity after ordinary world streaming; never
        # substitute a new fixture or accept a missing/changed inventory.
        protection = load('vehicle-preservation')
        after = {sql: protection.verify(h, expected, preserved_locations.get(sql), snapshot)
                 for sql, expected in preserved.items()}
        h.check(after == preserved, 'Fleet audit changed a pre-existing saved fixture')
        h.REPORT['preservedAfterIdentical'] = True
        h.write_report('stopped' if stopped else 'passed')
        if not args.keep_open:
            (run/'request.json').write_text('{"action":"stop"}')
        return 0
    except Exception:
        h.write_report('failed', traceback.format_exc())
        raise


if __name__ == '__main__':
    raise SystemExit(main())
