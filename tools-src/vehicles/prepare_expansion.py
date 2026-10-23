"""Prepare measured body families from the local catalogue; dependencies stay external."""
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


def main():
    entries = json.loads((ROOT / 'build/rv/vehicle-catalogue.json').read_text())['entries']
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
