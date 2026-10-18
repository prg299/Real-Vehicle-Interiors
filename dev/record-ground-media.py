"""Record native world-furniture footage inside the already guarded lab game."""
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def lua(code):
    request = urllib.request.Request("http://127.0.0.1:18470/lua?depth=3&sandbox=false", code.encode())
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError(result)
    return result.get("result")


print(lua((ROOT / "dev/lua/furniture-ground-preview.lua").read_text()), flush=True)
for _ in range(25):
    status = lua('return MELensGroundPreview and MELensGroundPreview.status')
    if status == "grid-ready":
        break
    time.sleep(1)
else:
    raise RuntimeError(f"Ground grid not ready: {status}")
print(lua('local p=getPlayer(); local f=MELensGroundPreview.items[1]; '
          'for x=f.x-2,f.x+8 do for y=f.y-2,f.y+6 do local s=getCell():getGridSquare(x,y,f.z); '
          'if s then for i=s:getObjects():size()-1,0,-1 do local o=s:getObjects():get(i); '
          'local sp=o:getSprite(); local n=sp and sp:getName() or ""; '
          'if n:find("^f_") or n:find("^d_") or n:find("^e_") or n:find("^vegetation") '
          'then s:RemoveTileObject(o) end end end end end; '
          'p:setX(f.x+3.5); p:setY(f.y+2.5); p:setZ(f.z); '
          'ISUIHandler.setVisibleAllUI(false); return "clear grid; player centered"'), flush=True)
time.sleep(2)
print(lua('MEMCNativeLab.capture("furniture-ground-fresh.png"); return 1'), flush=True)
print(lua('local p=getPlayer(); ISUIHandler.setVisibleAllUI(false); '
          'MELensGroundMediaItem=p:getInventory():AddItem("Base.MELensRV_Cabinet"); '
          'return {x=p:getX(),y=p:getY(),model=MELensGroundMediaItem:getWorldStaticItem()}'), flush=True)
print(lua('MELensMedia.clip("clip-09-furniture-ground",12); return "recording"'), flush=True)
time.sleep(1)
events = [dict(at=1, result=lua('ISInventoryPaneContextMenu.dropItem(MELensGroundMediaItem,getPlayer():getPlayerNum()); '
                                'return "normal inventory Drop queued"'))]
time.sleep(5)
events.append(dict(at=6, result=lua('local p=getPlayer(); local f=MELensGroundPreview.items[1]; '
                                   'local square=getCell():getGridSquare(f.x+4,f.y+5,f.z); '
                                   'ISTimedActionQueue.add(ISWalkToTimedAction:new(p,square)); return "walk-away queued"')))
time.sleep(7)
print(lua('MEMCNativeLab.capture("furniture-ground-after-drop.png"); '
          'local w=MELensGroundMediaItem:getWorldItem(); '
          'return {worldItem=w~=nil,inInventory=getPlayer():getInventory():contains(MELensGroundMediaItem)}'), flush=True)
manifest_path = ROOT / "build/rv/workshop-20261017-clips/clips.json"
manifest = json.loads(manifest_path.read_text())
manifest = [entry for entry in manifest if entry["name"] != "clip-09-furniture-ground"]
manifest.append(dict(name="clip-09-furniture-ground", events=events,
                     capture="native GL_BACK, 1280x720, bounded 15 FPS, timestamped JPEG 96%",
                     setup="Disposable single-player scene; normal inventory Drop action and production walk timed action",
                     version="2.0.5 world-furniture model bindings", audio=False))
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
