"""Record reusable silent gameplay clips in the existing owned guarded media session."""
from pathlib import Path
import json
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'build/rv/workshop-20261017-clips'
manifest = []


def lua(code):
    req = urllib.request.Request('http://127.0.0.1:18470/lua?depth=3&sandbox=false', code.encode())
    with urllib.request.urlopen(req, timeout=15) as reply:
        result = json.load(reply)
    if not result.get('ok'):
        raise RuntimeError(result)
    return result.get('result')


def script(name, replacements=None):
    code = (ROOT / 'dev/lua' / name).read_text()
    for old, new in (replacements or {}).items():
        code = code.replace(old, new)
    return lua(code)


def clip(name, events, seconds=8):
    print('RECORDING', name, flush=True)
    lua(f'MELensMedia.clip("{name}",{seconds}); return 1')
    start = time.monotonic()
    results = []
    for at, action in events:
        time.sleep(max(0, at - (time.monotonic() - start)))
        results.append(dict(at=at, result=action()))
    time.sleep(max(0, seconds + 1 - (time.monotonic() - start)))
    manifest.append(dict(name=name, events=results, capture='native GL_BACK, 1280x720, bounded 15 FPS, timestamped JPEG 96%',
                         setup='Disposable single-player scene; scripted production mod actions', audio=False))
    (RUN / 'clips.json').write_text(json.dumps(manifest, indent=2))


def walk(fraction):
    return lua('local p=getPlayer(); local v=p:getVehicle(); local q=MELens.profileFor(v); '
               'local g=MELens.WalkGrids[q.walkGrid]; '
               f'MELens.walkTo(p,q.aisleX or 0,g.z0 + #g.rows*g.cell*{fraction}); return "walking"')


def wait(code, expected=True, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if lua(code) == expected:
            return
        time.sleep(.4)
    raise TimeoutError('Scene action did not complete')


if '--cargo-only' in sys.argv:
    manifest.extend(json.loads((RUN / 'clips.json').read_text()))
    lua('getCore():doZoomScroll(0,1); local p=getPlayer(); if p:getVehicle() then MELens.leave(p) end; return 1')
    wait('return getPlayer():getVehicle()==nil')
    for label, vehicle in [('05b-bus-walkthrough','Base.87fordB700school'),
                           ('06b-truck-cargo','Base.87fordF700box')]:
        result = script('spawn_one.lua', {'NAME': vehicle, 'tonumber("7")': 'tonumber("-2")'})
        if not str(result).startswith(vehicle + ' id='):
            raise RuntimeError('Spawn rejected: ' + str(result))
        time.sleep(2)
        print(result, flush=True)
        print(script('walkin.lua'), flush=True)
        wait('return MELens.isStanding(getPlayer())')
        time.sleep(2)
        clip('clip-' + label, [(1, lambda: walk(.75)), (4.5, lambda: walk(.3))])
        lua(f'MEMCNativeLab.capture("clip-{label}-still.png"); return 1')
        if 'truck' in label:
            print(script('box_pick.lua', {'"MODE"': '"empty"'}), flush=True)
            clip('clip-07b-pick-up-boxes', [
                (1, lambda: script('box_pick.lua', {'"MODE"': '"next"'})),
                (4.5, lambda: script('box_pick.lua', {'"MODE"': '"next"'})),
            ])
        lua('MELens.leave(getPlayer()); return 1')
        wait('return getPlayer():getVehicle()==nil')
    print('CARGO_TAKES_RECORDED', flush=True)
    sys.exit(0)


lua('ISUIHandler.setVisibleAllUI(false); if MELens.Dashboard.instance then MELens.Dashboard.instance:close() end; '
    'getCore():setAutoZoom(0,false); getCore():setFramerate(30); getCore():doZoomScroll(0,1); '
    'MELens.leave(getPlayer()); return 1')
time.sleep(4)
clip('clip-01-camper-entry', [(1.2, lambda: script('walkin.lua'))])
clip('clip-02-walk-around', [(1, lambda: walk(.8)), (4.5, lambda: walk(.2))])
lua('local p=getPlayer(); local v=p:getVehicle(); local q=MELens.profileFor(v); '
    'local item=p:getInventory():AddItem("Base.Hammer"); MELens.LooseUI.start(p,{item}); '
    'local surface; for _,s in ipairs(MELens.Loose.surfaces(v,q)) do if s.kind~="floor" then surface=s; break end end; '
    'local o=v:getScript():getModel():getOffset(); local w=v:getWorldPos(o:x()+(surface.x0+surface.x1)/2, '
    'o:y()+surface.y,o:z()+(surface.z0+surface.z1)/2,Vector3f.new()); '
    'local b=v:getWorldPos(0,0,0,Vector3f.new()):z(); '
    'local sx,sy=ISCoordConversion.ToScreen(w:x(),w:y(),b+(o:y()+surface.y)/2.44949); '
    'MELens.LooseUI.testMouse={x=sx,y=sy}; return 1')
clip('clip-08-place-and-rotate', [
    (2, lambda: lua('MELens.LooseUI.active.yaw=45; return "rotated"')),
    (4, lambda: lua('local m=MELens.LooseUI.active; local h=m.hover; if h and h.valid then m:commit(); return "placed" end; return "invalid preview"')),
])
lua('if MELens.LooseUI.active then MELens.LooseUI.active:stop() end; MELens.LooseUI.testMouse=nil; return 1')
script('loose_fill.lua')
lua('local U=MELens.Utilities; local v=getPlayer():getVehicle(); local g=U.generatorState(v); '
    'g.part:getModData().fuel=12; U.setPropane(v,1.5,true); '
    'ISUIHandler.setVisibleAllUI(false); MELens.Dashboard.open(getPlayer(),v); '
    'local w=MELens.Dashboard.instance; w:setX(30); w:setY(120); w:setVisible(true); return 1')
clip('clip-03-interior-manager', [
    (1, lambda: lua('MELens.Dashboard.instance:onGenerator(); return "generator queued"')),
    (3, lambda: lua('MELens.Dashboard.instance:onHeater(); return "heater queued"')),
    (5, lambda: lua('MELens.Dashboard.instance:onStove(); return "stove queued"')),
])
lua('MEMCNativeLab.capture("manager-clean.png"); return 1')
time.sleep(1)
lua('MELens.Dashboard.instance:close(); return 1')
clip('clip-04-furnished-camper', [(1, lambda: walk(.65)), (4.5, lambda: walk(.3))])
lua('MEMCNativeLab.capture("camper-furnished.png"); return 1')
lua('MELens.leave(getPlayer()); return 1')
time.sleep(3)
for name, vehicle in [('clip-05-bus-walkthrough','Base.87fordB700school'),
                      ('clip-06-truck-cargo','Base.87fordF700box')]:
    result = script('spawn_one.lua', {'NAME': vehicle, 'tonumber("7")': 'tonumber("-2")'})
    print(result, flush=True)
    time.sleep(2)
    print(script('walkin.lua'), flush=True)
    time.sleep(5)
    clip(name, [(1, lambda: walk(.8)), (4.5, lambda: walk(.25))])
    lua(f'MEMCNativeLab.capture("{name}-still.png"); return 1')
    if 'truck' in name:
        print(script('box_pick.lua', {'"MODE"': '"empty"'}), flush=True)
        clip('clip-07-pick-up-boxes', [
            (1, lambda: script('box_pick.lua', {'"MODE"': '"next"'})),
            (4.5, lambda: script('box_pick.lua', {'"MODE"': '"next"'})),
        ])
    lua('MELens.leave(getPlayer()); return 1')
    time.sleep(3)
print('CLIPS_RECORDED', len(manifest), flush=True)
