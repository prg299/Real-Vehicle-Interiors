"""Isolated entry regression profile, including the unmodified More Car Features.

Reuses Motorclub's input/framebuffer adapter and the shared inactive-desktop
launcher. No real saves, enabled-mod lists, Workshop files or OS input are changed.
The baseline is the subscribed package; the candidate is scripts/build.ps1's output.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'C:\SteamLibrary\steamapps\common\ProjectZomboid')
WORKSHOP = GAME.parents[1] / 'workshop/content/108600'
PORT = 18474
STATE = ROOT / 'build/rv/entry-compatibility.json'
DEPS = [('3619862853', 'ZombieBuddy'), ('3171167894', 'damnlib'),
        ('3670064951', 'KI5campers'), ('3110911330', '87fordB700'),
        ('3520758551', 'More Car Features + Spawn Zones Expansion')]


def lua(code):
    request = urllib.request.Request(f'http://127.0.0.1:{PORT}/lua?depth=8',
                                    code.encode(), {'Content-Type': 'text/plain'})
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    if not result.get('ok'):
        raise RuntimeError(result)
    return result


def launch(baseline, adapter_classes=None, package=None):
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/status', timeout=1)
    except OSError:
        pass
    else:
        raise RuntimeError('Entry regression endpoint already occupied')
    label = 'baseline' if baseline else 'candidate'
    run = ROOT / 'build/rv' / ('entry-' + label + '-' + time.strftime('%Y%m%d-%H%M%S'))
    cache = run / 'Zomboid'
    mods = cache / 'mods'
    mods.mkdir(parents=True)
    for item, folder in DEPS:
        shutil.copytree(WORKSHOP / item / 'mods' / folder, mods / folder)
    source = (WORKSHOP / '3811728541/mods/RealVehicleInteriors' if baseline
              else package or ROOT / 'build/rv/package/RealVehicleInteriors')
    shutil.copytree(source, mods / 'RealVehicleInteriors')
    shutil.copytree(ROOT / 'dev/RealVehicleInteriors_Dev', mods / 'RealVehicleInteriors_Dev')
    classes = run / 'classes'
    classes.mkdir()
    adapter = ROOT.parent / 'me-motorclub/tools/java/ClientLab.java'
    sources = list((ROOT / 'dev/java').rglob('*.java'))
    if adapter_classes is None:
        sources.append(adapter)
    jdk = ROOT / '.tools/jdk-25.0.4.1+1/bin'
    subprocess.run([str(jdk / 'javac.exe'), '--release', '25', '-d', str(classes),
                    '-cp', f'{GAME}/projectzomboid.jar;{GAME}/ZombieBuddy.jar',
                    *map(str, sources)], check=True)
    # Reuse a baseline's exact input adapter if another chat is editing its source.
    # Only the adapter classes are reused; the endpoint and shipping mod are rebuilt.
    reused = []
    if adapter_classes is not None:
        reused = list((adapter_classes / 'me/lens/dev').glob('ClientLab*.class'))
        if not reused or not (adapter_classes / 'me/lens/dev/ClientLab.class').is_file():
            raise ValueError('Compiled baseline adapter missing')
        for compiled in reused:
            shutil.copy2(compiled, classes / 'me/lens/dev' / compiled.name)
    devjar = mods / 'RealVehicleInteriors_Dev/42.21/media/java/RealVehicleInteriors_Dev.jar'
    devjar.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(jdk / 'jar.exe'), '--create', '--file', str(devjar),
                    '-C', str(classes), '.'], check=True)
    ids = ['ZombieBuddy', 'damnlib', 'KI5campers', '87fordB700', 'WayMoreCars',
           'RealVehicleInteriors', 'RealVehicleInteriors_Dev']
    (mods / 'default.txt').write_text('VERSION = 1,\nmods\n{\n' + ''.join(
        f' mod = {mod},\n' for mod in ids) + '}\nmaps\n{\n}\n')
    (mods / 'reset-mods-42_00.txt').touch()
    shutil.copy2(Path.home() / 'Zomboid/version.txt', cache / 'version.txt')
    values = dict(line.split('=', 1) for line in (Path.home() / 'Zomboid/options.ini')
                  .read_text().splitlines() if '=' in line)
    values.update(fullScreen='false', borderless='false', width='1280', height='720',
                  focusloss='false', vsync='false', frameRate='60', uiRenderFPS='60')
    (cache / 'options.ini').write_text(''.join(f'{k}={v}\n' for k, v in values.items()))
    (mods / 'RealVehicleInteriors_Dev/common/media/lua/client/AAA_EntryCheck.lua').write_text(
        'UIManager.setShowLuaDebuggerOnError(false)\n'
        'Events.OnMainMenuEnter.Add(function() print("[ENTRY_CHECK] menu ready") end)\n'
        'Events.OnGameStart.Add(function() UIManager.setShowLuaDebuggerOnError(false) '
        'print("[ENTRY_CHECK] world ready") end)\n')
    (run / 'zombie_buddy').mkdir()
    config = json.loads((GAME / 'ProjectZomboid64.json').read_text())
    args = [a for a in config['vmArgs'] if not a.startswith(
        ('-javaagent:', '-agentlib:', '-Duser.home=', '-Dzomboid.steam=',
         '-XX:AOT', '-Xlog:aot='))]
    args += config.get('windows', {}).get('10.0.17134', {}).get('vmArgs', [])
    args += ['-Dzomboid.steam=0', f'-Duser.home={run}', '-Dpzopt.enabled=true',
             '-Dpzopt.aotCache=false', '-Dpzopt.gcMode=stock', '-Dpzopt.updateCheck=false',
             '-Dpzopt.updatePrefetch=false', f'-Dmelens.dev.port={PORT}',
             f'-agentlib:zbNative=policy=allow-all,verbosity=1,config_dir={run}/zombie_buddy',
             '-cp', '.;projectzomboid.jar', config['mainClass'].replace('/', '.'),
             '-nosteam', f'-cachedir={cache}', '-debug']
    configuration = run / 'native-session.json'
    configuration.write_text(json.dumps({'command': [str(GAME / 'jre64/bin/java.exe'), *args],
                                         'cwd': str(GAME)}, indent=2))
    env = dict(os.environ)
    env['PATH'] = str(GAME / 'win64') + ';' + str(GAME) + ';' + env['PATH']
    with (run / 'keeper.log').open('w') as log:
        subprocess.Popen([sys.executable, str(ROOT.parents[1] / 'tools/windows-test-session.py'),
                          str(configuration)], env=env, stdout=log, stderr=log,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    receipt = run / 'native-session-started.json'
    deadline = time.monotonic() + 10
    while not receipt.exists() and time.monotonic() < deadline:
        time.sleep(.1)
    session = json.loads(receipt.read_text())
    manifest = dict(run=str(run), cache=str(cache), port=PORT, label=label, **session,
                    runtime='installed loose classes with PZ Optimization',
                    source={str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in source.rglob('*') if p.is_file()},
                    inputAdapter=str(adapter),
                    inputAdapterSha256=hashlib.sha256(adapter.read_bytes()).hexdigest() if not reused else None,
                    reusedInputAdapter={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in reused})
    STATE.write_text(json.dumps(manifest, indent=2))
    (run / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return {'ok': True, 'run': str(run), 'pid': session['pid']}


def world(load):
    state = json.loads(STATE.read_text())
    log = Path(state['cache']) / 'console.txt'
    before = log.stat().st_size
    if load:
        if not load.startswith('entry-check-') or '/' in load or '\\' in load:
            raise ValueError('Only entry regression saves can be loaded')
        lua('MainScreen.continueLatestSave("Sandbox",' + json.dumps(load) + ');return true')
    else:
        lua((ROOT / 'dev/lua/newgame.lua').read_text().replace('melens-test-', 'entry-check-'))
    deadline = time.monotonic() + 55
    while time.monotonic() < deadline:
        if 'game loading took' in log.read_text(errors='replace')[before:]:
            break
        time.sleep(.5)
    else:
        raise RuntimeError('World did not reach load marker; no concurrent Lua calls sent')
    time.sleep(1)
    lua('MEMCNativeLab.releaseKeys(); MEMCNativeLab.clickToStart(); return true')
    time.sleep(2)
    lua('GameWindow.doRenderEvent(true); return true')
    lua((ROOT / 'dev/lua/setup.lua').read_text())
    return lua('return {world=getWorld():getWorld(),x=getPlayer():getX(),y=getPlayer():getY()}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['launch', 'world', 'lua', 'capture', 'quit'])
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--adapter-classes', type=Path)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--code')
    parser.add_argument('--file', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--load')
    args = parser.parse_args()
    if args.action == 'launch':
        result = launch(args.baseline, args.adapter_classes, args.package)
    elif args.action == 'world':
        result = world(args.load)
    elif args.action == 'quit':
        result = lua('getCore():quitToDesktop(); return "owned test quitting"')
    elif args.action == 'capture':
        spec = importlib.util.spec_from_file_location('motorclub_capture', ROOT.parent / 'me-motorclub/tools/client-lab.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.STATE, module.PORT = STATE, PORT
        result = module.capture_file(args.out)
    else:
        result = lua(args.file.read_text('utf-8-sig') if args.file else args.code)
    if args.out and args.action != 'capture':
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
