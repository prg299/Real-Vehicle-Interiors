"""Save/cold-load service fittings without rerolling items or vehicle cargo.

saveGame and actor/vehicle selection are fixtures. This is persistence evidence,
not Save/Continue menu-input or dedicated-server evidence.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import traceback

ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify-source')
    args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN']
    h=load('final-feature-tests');h.configure(run/('service-reload' if args.verify_source else 'service-save'))
    config=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(x.split('=',1)[1] for x in config['command'] if x.startswith('-cachedir=')))/'Screenshots'
    try:
        if args.verify_source:
            expected=json.loads((ROOT/'build/rv'/args.verify_source/'service-save/expected.json').read_text())
            h.lua('''local v=assert(getPlayer():getVehicle());assert(v:getScriptName()=="Base.90fordF350ambulance")
MELensTest={vehicle=v,all={}};return true''')
        else:
            h.lua('''MELensMedia.cameraOff();local p=getPlayer();if p:getVehicle() then p:getVehicle():exit(p) end
ISTimedActionQueue.clear(p);p:setX(10813.5);p:setY(10140.5);p:setLastX(10813.5);p:setLastY(10140.5);return true''')
            load('bed-tests').enter(h,'Base.90fordF350ambulance','N')
            h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts
for i,s in ipairs(MELens.profileFor(v).spots) do if s.default=="medlocker" then
local c=P.spotPart(v,i):getItemContainer();assert(c:AddItem("Base.Screwdriver"));break end end
-- A labelled cleared-slot fixture checks that cold load does not respawn stock.
local spots=MELens.profileFor(v).spots
for i=#spots,1,-1 do if spots[i].factory and spots[i].default=="medlocker" then
local part=P.spotPart(v,i);part:getItemContainer():getItems():clear();part:setInventoryItem(nil);P.applyPiece(v,part);break end end
return true''')
        state=h.lua('''local v=MELensTest.vehicle;local P=MELens.Parts;local rows={}
for index,s in ipairs(MELens.profileFor(v).spots) do if s.factory then
local part=P.spotPart(v,index);local item=part:getInventoryItem()
local c=part:getItemContainer();local cargo={};for i=0,c:getItems():size()-1 do cargo[#cargo+1]=c:getItems():get(i):getID() end
table.sort(cargo);rows[index]={piece=P.pieceOfItem(item),itemId=item and item:getID(),capacity=c:getCapacity(),cargo=cargo,
initialized=part:getModData()[P.INITIALIZED_KEY]} end end
local native={};for i=0,v:getPartCount()-1 do local part=v:getPartByIndex(i);local c=part:getItemContainer()
if c and not part:getId():find("^MELens") then local ids={};for j=0,c:getItems():size()-1 do ids[#ids+1]=c:getItems():get(j):getID() end
table.sort(ids);native[part:getId()]={capacity=c:getCapacity(),items=ids} end end
return {world=getWorld():getWorld(),script=v:getScriptName(),fittings=rows,nativeCargo=native,
factoryLayout=v:getModData().MELensFactoryLayout}''')
        pieces=[row.get('piece') for row in state['fittings'].values()]
        h.check('stretcher' in pieces and 'medbench' in pieces and pieces.count('medlocker')>=2,'medical factory layout incomplete')
        h.check(pieces.count(None)==1,'cleared factory slot was refurnished')
        if args.verify_source:
            h.check(state==expected,'cold load replaced fittings, rerolled medical supplies or changed stock cargo')
            h.REPORT['saveReload']={'expected':expected,'actual':state}
        else:
            (h.OUTPUT/'expected.json').write_text(json.dumps(state,indent=2))
            h.lua('saveGame();return true');h.REPORT['saved']=state
        h.capture('medical-fittings-cold-loaded' if args.verify_source else 'medical-fittings-saved')
        h.REPORT['scope']=__doc__
        h.REPORT['unverified']=['dedicated server','Save/Continue menu input']
        h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
