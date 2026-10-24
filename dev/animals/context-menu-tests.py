"""Real interior right-click, native menu metadata parity, Inspect and Pet input.

The hidden reference invokes the world's actual event on the same animal in the
same Lua tick; it is a builder comparison, not an outside-world mouse-input claim.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]


def load(name,path=None):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),path or ROOT/'dev'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


REFERENCE='''local root=getPlayerContextMenu(0);local p=getPlayer();local a=MELens.Animals.list(p:getVehicle())[1]
local name=CompanionDogs.data(a).name
local function find(menu) for _,o in ipairs(menu.options or {}) do if o.name==name and o.subOption then return menu:getSubMenu(o.subOption) end end end
local function tree(menu)
 local out={};for _,o in ipairs(menu.options or {}) do if not o.isDefaultOption then
 local r={name=tostring(o.name),disabled=o.notAvailable==true or o.isDisabled==true,
 icon=o.iconTexture and tostring(o.iconTexture),tip=o.toolTip and o.toolTip.description}
 if o.subOption then r.children=tree(menu:getSubMenu(o.subOption)) end;out[#out+1]=r end end;return out
end
local actual=assert(find(root),"normal Companion Dogs menu is missing")
local ref=ISContextMenu:getNew(root);triggerEvent("OnClickedAnimalForContext",p:getPlayerNum(),ref,{a},false)
local expected=assert(find(ref),"world event did not produce its reference menu")
return {actual=tree(actual),expected=tree(expected),uid=CompanionDogs.ensureUid(a)}'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-name',default='animal-context');args=parser.parse_args()
    run=ROOT/'build/rv'/os.environ['RVI_CAPTURE_RUN'];h=load('final-feature-tests');h.configure(run/args.output_name)
    session=json.loads((run/'native-session.json').read_text('utf-8-sig'))
    h.SCREENS=Path(next(s.split('=',1)[1] for s in session['command'] if s.startswith('-cachedir=')))/'Screenshots'
    h.ENDPOINT=h.ENDPOINT.replace('depth=8','depth=16')
    interior=load('final-interior-tests');tap,_=interior.load_helpers();animal=load('final-mp-animals')
    care=load('dog_care',ROOT/'dev/animals/dog-care-tests.py')

    def wait(read,predicate=bool,label='native animal context',seconds=40):
        h.REPORT['activeWait']=label;end=time.monotonic()+seconds;value=None
        while time.monotonic()<end:
            value=read()
            if time.monotonic()>=h._input_release and predicate(value):return value
            time.sleep(.12)
        raise AssertionError(label+': '+json.dumps(value,default=str))

    def click_option(title):
        rows=wait(lambda:h._sequence(h.lua(animal.MENUS)),lambda rows:any(r['name']==title for r in rows),'native menu '+title)
        row=next(r for r in rows if r['name']==title);h.check(row['enabled'],'native menu entry disabled: '+title)
        tap.native_click(h,row['x'],row['y'],title)

    def open_dog():
        h.lua('getPlayerContextMenu(0):hideAndChildren();return true')
        point=h.lua('return MELensDogCare.point()');tap.native_click(h,point['x'],point['y'],'interior dog:normal right-click',right=True)
        click_option(h.lua('return CompanionDogs.data(MELens.Animals.list(MELensTest.vehicle)[1]).name'))

    try:
        h.REPORT.update(scope=__doc__,fixtures=['existing disposable bonded companion','noon lighting only','hidden world-builder reference in the same Lua tick'])
        h.lua('MELensTest={vehicle=assert(getPlayer():getVehicle())};ISUIHandler.setVisibleAllUI(true);getGameTime():setTimeOfDay(12);return true')
        h.lua(care.FIXTURE);open_dog();reference=h.lua(REFERENCE)
        h.check(reference['actual']==reference['expected'],'interior names, order, icons, disabled states or tooltips differ from the normal world menu')
        h.REPORT['sameTickWorldMenuReference']=reference;h.capture('normal-world-style-dog-menu-inside')
        click_option(h.lua('return getText("IGUI_PD_Inspect")'))
        wait(lambda:h.lua('local w=ISCDStatusWindow.instanceFor(getPlayer());return w and w:isVisible()'),label='native Inspect stays visible')
        h.capture('normal-dog-inspect-inside');h.lua('ISCDStatusWindow.instanceFor(getPlayer()):close();return true')
        before=h.lua('local a=MELens.Animals.list(MELensTest.vehicle)[1];return {pet=CompanionDogs.data(a).lastPetMin,uid=CompanionDogs.ensureUid(a)}')
        open_dog();click_option(h.lua('return getText("IGUI_PD_Pet")'))
        wait(lambda:h.lua('return getPlayer():getVariableBoolean("petanimal")'),label='native pet animation starts inside')
        h.capture('native-pet-animation-inside')
        after=wait(lambda:h.lua('local a=MELens.Animals.list(MELensTest.vehicle)[1];return {pet=CompanionDogs.data(a).lastPetMin,uid=CompanionDogs.ensureUid(a),queue=#ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue,anim=getPlayer():getVariableBoolean("petanimal"),idle=a:getVariableString("idleAction")}'),
            lambda s:s.get('pet') is not None and s.get('pet')!=before.get('pet') and s['queue']==0 and not s['anim'],label='native pet authority effect and cleanup',seconds=60)
        h.check(after['uid']==before['uid'] and after.get('idle')!='petting','pet changed identity or left the petting animation active')
        h.REPORT['nativePet']={'before':before,'after':after};h.write_report('passed');return 0
    except Exception:
        error=traceback.format_exc();print(error,flush=True);h.write_report('failed',error);return 1


if __name__=='__main__':raise SystemExit(main())
