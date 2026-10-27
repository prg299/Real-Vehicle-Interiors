"""Check authored model declarations and profile references against real FBX meshes.

Run through Blender with -- --media <common/media> --report <output.json>.
This checks bindings only; native rendering and input require separate review.
"""
import argparse
import json
import re
import sys
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_vehicle_fbx import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--media', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    media = args.media.resolve()
    declarations = []
    for script in sorted((media/'scripts').glob('*.txt')):
        for match in re.finditer(r'model\s+(\w+)\s*\{([^{}]*)\}', script.read_text(), re.S):
            mesh = re.search(r'\bmesh\s*=\s*vehicles/(MELens_\w+)\|(\w+)', match.group(2))
            if mesh:
                declarations.append(dict(model=match.group(1), file=mesh.group(1),
                                         mesh=mesh.group(2), script=script.name))
    assert declarations, 'No authored model declarations found'
    meshes = {}
    for name in sorted({row['file'] for row in declarations}):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        load(str(media/'models_X/vehicles'/(name+'.fbx')))
        meshes[name] = {obj.name: dict(vertices=len(obj.data.vertices), faces=len(obj.data.polygons))
                        for obj in bpy.data.objects if obj.type == 'MESH'}
    missing = []
    for row in declarations:
        actual = meshes[row['file']].get(row['mesh'])
        if actual is None or not actual['vertices'] or not actual['faces']:
            missing.append(dict(**row, actual=actual))
    declared = {row['model'] for row in declarations}
    unknown = []
    profiles = sorted((media/'lua/shared').glob('MELens_Profile*.lua'))
    assert profiles, 'No interior profiles found'
    for profile in profiles:
        for match in re.finditer(r'\bmodels\s*=\s*\{([^{}]*)\}', profile.read_text(), re.S):
            for alias in re.findall(r'"(MELensShell_\w+)"', match.group(1)):
                if alias not in declared:
                    unknown.append(dict(profile=profile.name, model=alias))
    report = dict(scope='Authored mesh binding existence only; no rendering/input proof',
                  declarations=len(declarations), profiles=len(profiles), files=meshes,
                  missingOrEmpty=missing, undeclaredProfileModels=unknown)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in
                     ('declarations', 'profiles', 'missingOrEmpty', 'undeclaredProfileModels')}))
    return 1 if missing or unknown else 0


if __name__ == '__main__':
    raise SystemExit(main())
