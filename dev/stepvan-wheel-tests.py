"""Native four-heading wheel-cover review with fixtures removing cargo models.

Keyboard entry uses production input. Clear fittings only for an unobscured view
of the floor and wheel housings; this does not test furniture uninstall input.
"""
import importlib.util
import json
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
    h=load('final-feature-tests');h.configure(run/'stepvan-wheels')
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in session['command'] if x.startswith('-cachedir=')))/'Screenshots'
    try:
        for heading in ('N','E','S','W'):
            h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true''')
            load('bed-tests').enter(h,'Base.StepVan',heading)
            count=h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts;local n=0
for i,s in ipairs(MELens.profileFor(v).spots) do if s.factory then
assert(P.pieceAt(P.spotPart(v,i))=="parcels");n=n+1 end end;return n''')
            h.check(count==6,'step van does not have three cargo slots on each side')
            h.capture('stepvan-six-cargo-'+heading.lower())
            h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
for i in ipairs(MELens.profileFor(v).spots) do local part=P.spotPart(v,i)
part:setInventoryItem(nil);part:getItemContainer():getItems():clear();P.applyPiece(v,part) end
local pr=MELens.profileFor(v);local g=MELens.WalkGrids[pr.walkGrid]
MELens.walkTo(getPlayer(),pr.aisleX or 0,g.z0+#g.rows*g.cell*.45)
ISUIHandler.setVisibleAllUI(false);return true''')
            deadline=time.monotonic()+20
            while h.lua('return MELens.pathing(getPlayer())'):
                h.check(time.monotonic()<deadline,'cleared step van aisle blocked');time.sleep(.1)
            time.sleep(.5);h.capture('stepvan-empty-wheel-housings-'+heading.lower())
            h.REPORT['inputs'].append(dict(action='entry',heading=heading,path='production Interact key'))
            h.REPORT['nativeInput']=True
        h.REPORT['scope']=__doc__;h.REPORT['visualReview']='pending'
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1
    finally:h.lua('ISUIHandler.setVisibleAllUI(true);return true')


if __name__=='__main__':raise SystemExit(main())
