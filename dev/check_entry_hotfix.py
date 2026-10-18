"""Keyboard/mouse acceptance in an already launched entry_compatibility profile.

Load a copy of the recorded baseline save. Position/spawn are fixture setup only;
entry/exit use production input polling and the native mouse event queue.
"""
import importlib.util
import json
import time
from pathlib import Path
import entry_compatibility as lab

ROOT = lab.ROOT
OUT = ROOT / 'reports/entry-error-20261002'


def call(code):
    return lab.lua(code)['result']


def file(name):
    return call((ROOT / 'dev/lua' / name).read_text())


def wait_for(code, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = call(code)
        if value:
            return value
        time.sleep(.25)
    raise AssertionError('Timeout: ' + code)


def key(code, duration=200):
    call(f'MEMCNativeLab.holdKey({code},{duration});return true')
    time.sleep(.4)


def capture(path):
    spec = importlib.util.spec_from_file_location('capture_adapter', ROOT.parent / 'me-motorclub/tools/client-lab.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE, module.PORT = lab.STATE, lab.PORT
    return module.capture_file(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    state = json.loads(lab.STATE.read_text())
    log = Path(state['cache']) / 'console.txt'
    baseline = json.loads((ROOT / 'build/rv/entry-baseline-parts.json').read_text())['result']
    deadline = time.monotonic() + 45
    while '[ENTRY_CHECK] menu ready' not in log.read_text(errors='replace'):
        if time.monotonic() > deadline:
            raise AssertionError('Main menu not ready')
        time.sleep(.5)
    lab.world(baseline['world'])
    initial = file('entry_state.lua')
    for index, part in baseline['parts'].items():
        assert initial['parts'][index] == part, (index, part, initial['parts'][index])
    audit = file('entry_profile_audit.lua')
    print('Saved camper and all profile bindings passed', flush=True)
    key(18)
    wait_for('return getPlayer():getVehicle()==nil')
    fixture = file('entry_fixture.lua')
    time.sleep(1)
    assert call('return MELensEntryTest.entered') == 0
    call('MEMCNativeLab.clickButtonAt(900,360,1);return true')
    time.sleep(.8)
    menu = call('local c=getPlayerContextMenu(0);local r={visible=c:isVisible(),x=c:getX(),h=c.itemHgt,options={}};'
                'for i,o in ipairs(c.options) do r.options[i]={name=o.name,y=c:getItemY(i),disabled=o.notAvailable} end;return r')
    assert menu['visible']
    options = list(menu['options'].values())
    option = next(o for o in options if o['name'] == 'Walk into camper')
    assert not option.get('disabled')
    menu_capture = capture(OUT / 'native-menu.png')
    call(f'MEMCNativeLab.clickAt({int(menu["x"]+70)},{int(option["y"]+menu["h"]/2)});return true')
    wait_for('return getPlayer():getVehicle()~=nil and MELens.isStanding(getPlayer()) and '
             '#ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0')
    mouse = call('return {events=MELensEntryTest,standing=MELens.isStanding(getPlayer())}')
    assert mouse['events']['entered'] == 1 and mouse['events']['lastPart'] == 'SeatMELensCabin'
    key(18)
    wait_for('return getPlayer():getVehicle()==nil')
    file('entry_fixture.lua')
    key(18)
    wait_for('return getPlayer():getVehicle()~=nil and MELens.isStanding(getPlayer()) and '
             '#ISTimedActionQueue.getTimedActionQueue(getPlayer()).queue==0')
    keyboard = call('return {events=MELensEntryTest,standing=MELens.isStanding(getPlayer())}')
    assert keyboard['events']['entered'] == 2 and keyboard['events']['exited'] == 1
    before = call('local p=getPlayer();local x,z=MELens.Parts.characterAt(p:getVehicle(),p);return {x=x,z=z}')
    key(17, 300)
    after = call('local p=getPlayer();local x,z=MELens.Parts.characterAt(p:getVehicle(),p);return {x=x,z=z}')
    assert abs(after['x']-before['x']) + abs(after['z']-before['z']) > .01
    entered_capture = capture(OUT / 'native-inside.png')
    print('Native mouse entry, keyboard entry/exit and walking passed', flush=True)
    marker = log.stat().st_size
    call('getCore():quit();return true')
    deadline = time.monotonic() + 45
    while '[ENTRY_CHECK] menu ready' not in log.read_text(errors='replace')[marker:]:
        if time.monotonic() > deadline:
            raise AssertionError('Save did not return to menu')
        time.sleep(.5)
    lab.world(baseline['world'])
    reloaded = file('entry_state.lua')
    assert reloaded['parts'] == initial['parts']
    reload_capture = capture(OUT / 'native-reloaded.png')
    original_errors = log.read_text(errors='replace').count('PlayerVehicleWeatherEffects.lua:331')
    assert original_errors == 0
    lab.lua('getCore():quitToDesktop();return true')
    exit_file = Path(state['run']) / 'native-session-exit.json'
    deadline = time.monotonic() + 20
    while not exit_file.exists():
        if time.monotonic() > deadline:
            raise AssertionError('Native process did not exit')
        time.sleep(.25)
    exit_status = json.loads(exit_file.read_text())
    result = {'run': state['run'], 'pid': state['pid'], 'initial': initial, 'profiles': audit,
              'fixture': fixture, 'unchangedInputEntered': 0, 'menu': menu, 'mouse': mouse,
              'keyboard': keyboard, 'movement': {'before': before, 'after': after},
              'reloaded': reloaded, 'originalEntryErrors': original_errors, 'exit': exit_status,
              'captures': [menu_capture, entered_capture, reload_capture],
              'inputRoute': 'KeyboardState polling; LWJGL Mouse event queue; production UI and timed actions',
              'desktopSwitched': False}
    (OUT / 'native-result.json').write_text(json.dumps(result, indent=2))
    assert exit_status['exitCode'] == 0, exit_status
    print(json.dumps({'passed': True, 'profiles': len(audit['profiles']), 'bindings': audit['bindings'],
                      'existingPartsPreserved': len(baseline['parts']), 'exitCode': exit_status['exitCode']}))


if __name__ == '__main__':
    main()
