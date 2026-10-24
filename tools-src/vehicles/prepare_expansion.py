"""Prepare measured body families from the local catalogue; dependencies stay external."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/rv/floorplans'
FAMILIES = [
    ('VanillaVan', 'Van', 'Franklin Valuline cargo van', 'DoorRear'),
    ('VanillaPassengerVan', 'VanSeats', 'Franklin Valuline passenger van', 'DoorRear'),
    ('VanillaAmbulance', 'VanAmbulance', 'Vanilla ambulance', 'DoorRear'),
    ('VanillaRadioVan', 'VanRadio', 'Vanilla radio van', 'DoorRear'),
    ('VanillaStepVan', 'StepVan', 'Chevalier step van', 'DoorRear'),
    ('E150Short', '86fordE150', 'Ford E150 short van', 'TrunkDoor'),
    ('E150Long', '86fordE150long', 'Ford E150 long van', 'TrunkDoor'),
    ('E150Windows', '86fordE150longW', 'Ford E150 passenger van', 'TrunkDoor'),
    ('ChevyStepVan', '85chevyStepVan', 'Chevrolet step van', 'TrunkDoor'),
    ('F700Bank', '87fordF700bank', 'F700 armored bank truck', 'TrunkDoor'),
    ('F700Swat', '87fordF700swat', 'F700 SWAT truck', 'TrunkDoor'),
    ('F350Ambulance', '90fordF350ambulance', 'Ford F350 ambulance', 'DoorRear'),
]
INTERIORS = {
    'E150Short': ['e150_interior_common', 'e150_interior_slide'],
    'E150Long': ['e150_interior_common', 'e150_interior_long'],
    'E150Windows': ['e150_interior_common', 'e150_interior_long_win'],
    'ChevyStepVan': ['85stepvan_interior'],
    'F700Bank': ['b700_interior_bank'], 'F700Swat': ['b700_interior_swat'],
    'F350Ambulance': ['f350_interior'],
}


def cab_parts(base):
    """Resolve normal door/panel skins sharing the representative body's FBX.

    Some bodies omit these separate faces entirely. Only their numerical
    sections supplement the cap; accessories and other body variants do not.
    Offsets are in passenger space, as in the opening-geometry exporter.
    """
    body_file = base['model']['mesh'].partition('|')[0]
    scale = base['model']['scale']
    found = {}
    for part in base['parts']:
        for model in part.get('models', []):
            file, _, node = (model.get('mesh') or '').partition('|')
            if file != body_file or not node:
                continue
            tags = ' '.join((part['id'], model.get('file') or '', node)).lower()
            if any(word in tags for word in ('armor', 'armour', 'mirror', 'interior')):
                continue
            door = part['id'].startswith('Door') or part['id'] == 'TrunkDoor'
            panel = 'body' in node.lower() and 'panel' in node.lower()
            if not (door or panel):
                continue
            if any(abs(v) > .001 for v in (model.get('rotate') or [])):
                raise ValueError(f"Unresolved rotated cab skin: {base['name']} {node}")
            offset = tuple(v * scale for v in (model.get('offset') or [0, 0, 0]))
            found[(node, offset)] = dict(mesh=node, offset=offset)
    return [found[key] for key in sorted(found)]


def main():
    entries = json.loads((ROOT / 'build/rv/vehicle-catalogue.json').read_text())['entries']
    # Original camper specs use the same resolved catalogue contract. Keep their
    # numerical/script metadata available without restoring a historical lab file.
    camper_source = next((entry for entry in entries if entry['modId'] == 'KI5campers'), None)
    if camper_source:
        # The external reference list omits Airflyte/Astrodome. Resolve every
        # original camper spec from the installed scripts, rather than using
        # that coverage filter as a complete native script inventory.
        module_spec = importlib.util.spec_from_file_location('pzscripts', ROOT/'dev/pzscripts.py')
        pz = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(pz)
        dirs = list(dict.fromkeys(directory for entry in entries for directory in entry['scriptDirs']))
        models, vehicles, templates = pz.load_dirs(dirs)
        names = {'Trailer54FlyingCloud22'}
        for path in (ROOT/'tools-src/vehicles/specs').glob('*.json'):
            vehicle_spec = json.loads(path.read_text('utf-8-sig'))
            if vehicle_spec.get('scripts', [None])[0] == 'campers.json':
                names.add(vehicle_spec['scripts'][1])
                names.update(name.removeprefix('Base.') for name in vehicle_spec['vehicles'])
        campers = {name: pz.summary(name, models, vehicles, templates) for name in sorted(names)}
        assert all('error' not in value and value.get('model') for value in campers.values()), campers
        (OUT / 'campers.json').write_text(json.dumps(campers, indent=2))
    rows = []
    for key, name, title, door in FAMILIES:
        base = next(e for e in entries if e['name'] == name)
        model = base['model']
        variants = [e for e in entries if e.get('model') and all(
            e['model'].get(field) == model.get(field) for field in ('mesh', 'scale', 'meshScale'))]
        mesh, _, node = model['mesh'].partition('|')
        roots = [Path(base['selected']), Path(base['folder']) / 'common', Path(base['folder'])]
        fbx = next((r / 'media/models_X' / (mesh + '.fbx') for r in roots
                    if (r / 'media/models_X' / (mesh + '.fbx')).is_file()), None)
        assert fbx, (key, mesh)
        info_file = OUT / f'fleet_{key}.json'
        info_file.write_text(json.dumps({base['name']: base}, indent=2))
        front = min(p['inside']['offset'][2] * model['scale'] for p in base['passengers']
                    if p['id'] in ('FrontLeft', 'FrontRight') and p.get('inside')) - .42
        row = dict(key=key, name=base['fullName'], title=title, body=node or Path(mesh).name,
                   fbx=str(fbx), interior=INTERIORS.get(key, []), prefix=[''], sampleZ=[-100, front],
                   cabParts=cab_parts(base), cabSectionZ=round(front - .04, 3),
                   modelScale=model['scale'] * model['meshScale'], fitEnvelope=True,
                   out=str(OUT / f'measure_{key}.json'), entryDoor=door,
                   scripts=[info_file.name, base['name']],
                   vehicles=sorted({e['fullName'] for e in variants}),
                   dependencies=sorted({(e['workshop'], e['modId']) for e in variants if e['workshop']}))
        rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'fleet-measures.json').write_text(json.dumps(rows, indent=2))
    for r in rows:
        print(f'{r["key"]}: {len(r["vehicles"])} variants; {r["body"]}; {r["entryDoor"]}')
    print('New body-family definitions:', sum(len(r['vehicles']) for r in rows))


if __name__ == '__main__':
    main()
