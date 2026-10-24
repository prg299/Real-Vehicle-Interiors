"""Inventory local vehicle definitions against a read-only Workshop coverage reference.

Only identifiers and resolved vehicle metadata are recorded; no dependency code or
artwork is copied into the mod. Run through run-heavy.mjs. Generated machine paths
stay under build/rv, outside the published repository.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pzscripts', ROOT / 'dev/pzscripts.py')
pz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pz)


def version(path):
    return tuple(int(n) for n in path.name.split('.')) if re.fullmatch(r'\d+(?:\.\d+)*', path.name) else None


def mod_roots(workshop):
    for mods in sorted(workshop.glob('*/mods')):
        for folder in sorted(p for p in mods.iterdir() if p.is_dir()):
            versions = [p for p in folder.iterdir() if p.is_dir() and version(p) and version(p) <= (42, 21)]
            selected = max(versions, key=version) if versions else folder
            scripts = [p for p in (folder / 'common/media/scripts', selected / 'media/scripts') if p.is_dir()]
            if not scripts:
                continue
            descriptors = [selected / 'mod.info', folder / 'common/mod.info', folder / 'mod.info']
            text = next((p.read_text('utf-8-sig', errors='replace') for p in descriptors if p.is_file()), '')
            fields = dict(re.findall(r'(?m)^\s*([\w]+)\s*=\s*(.*?)\s*$', text))
            yield dict(workshop=mods.parent.name, folder=folder, selected=selected,
                       modId=fields.get('id', folder.name), title=fields.get('name', folder.name), scripts=scripts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workshop', type=Path, default=Path('C:/SteamLibrary/steamapps/workshop/content/108600'))
    parser.add_argument('--game', type=Path, default=Path('C:/SteamLibrary/steamapps/common/ProjectZomboid'))
    parser.add_argument('--reference', default='3773972040')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/rv/vehicle-catalogue.json')
    args = parser.parse_args()
    reference = args.workshop / args.reference
    assert reference.is_dir(), 'Referenced Workshop item is not downloaded'
    requested = set()
    for source in reference.glob('mods/*/42/media/lua/server/*ServerDeal.lua'):
        requested.update(re.findall(r'["\'](Base\.[\w]+)["\']', source.read_text('utf-8-sig', errors='replace')))
    game_scripts = args.game / 'media/scripts'
    base_models, base_vehicles, base_templates = pz.load_dirs([str(game_scripts)])
    sources = [dict(workshop=None, folder=args.game, selected=args.game, modId='vanilla', title='Project Zomboid',
                    scripts=[game_scripts])]
    sources.extend(mod_roots(args.workshop))
    loaded = {}
    shared_models, shared_templates = {}, {}
    for source in sources[1:]:
        local = pz.load_dirs([str(p) for p in source['scripts']])
        loaded[str(source['folder'])] = local
        shared_models.update(local[0])
        shared_templates.update(local[2])
    entries = []
    for source in sources:
        if source['modId'] == 'vanilla':
            models, vehicles, templates = base_models, base_vehicles, base_templates
        else:
            local_models, vehicles, local_templates = loaded[str(source['folder'])]
            if not vehicles:
                continue
            models = shared_models | base_models | local_models
            templates = shared_templates | base_templates | local_templates
        for name in sorted(vehicles):
            full = name if '.' in name else 'Base.' + name
            if full not in requested:
                continue
            entry = pz.summary(name, models, vehicles, templates)
            resolved = pz.resolve(vehicles[name], templates)
            entry['wheelGeometry'] = {c.name: dict(offset=pz.vec(c.get('offset')),
                radius=c.get('radius'), width=c.get('width')) for c in resolved.children if c.kind == 'wheel'}
            entry.update(fullName=full, workshop=source['workshop'], modId=source['modId'],
                         title=source['title'], folder=str(source['folder']), selected=str(source['selected']),
                         scriptDirs=[str(p) for p in source['scripts']])
            entries.append(entry)
    result = dict(referenceWorkshop=args.reference, referenceIds=sorted(requested), entries=entries,
                  unresolved=sorted(requested - {entry['fullName'] for entry in entries}))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'{len(requested)} reference IDs; {len(entries)} installed definitions across '
          f'{len({e["modId"] for e in entries})} mod IDs; {len(result["unresolved"])} not installed/resolved')
    by_mod = {}
    for entry in entries:
        by_mod.setdefault(entry['modId'], []).append(entry)
    for mod, values in by_mod.items():
        bodies = sorted({(e.get('model') or {}).get('mesh') or (e.get('model') or {}).get('file') or '?' for e in values})
        print(f'{mod}: {len(values)} vehicles; bodies: {", ".join(bodies[:12])}')
    print('Inventory:', args.output)


if __name__ == '__main__':
    main()
