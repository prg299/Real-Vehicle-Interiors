"""Measure glazing planes for parametric lining returns, without exporting meshes.

Guarded Blender usage: -- manifest.json output.json
Each manifest row names family, measureConfig, scripts and vehicle. The output
contains fitted planes and rounded-rectangle dimensions, not dependency faces.
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_vehicle_fbx import load

args = sys.argv[sys.argv.index('--') + 1:]
rows = json.loads(Path(args[0]).read_text('utf-8-sig'))
result = {'schema': 1, 'description': 'Fitted glazing planes for parametric lining returns; no source mesh or UV data', 'families': {}}
for row in rows:
    cfg = json.loads(Path(row['measureConfig']).read_text('utf-8-sig'))
    script = json.loads(Path(row['scripts']).read_text('utf-8-sig'))[row['vehicle']]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    load(cfg['fbx'])
    mapping = cfg.get('map', dict(sx=-90, sy=90, sz=90))
    if 'modelScale' in cfg:
        obj = bpy.data.objects[cfg['body']]
        factor = cfg['modelScale'] / obj.matrix_world.to_scale().z
        mapping = dict(sx=-factor, sy=factor, sz=factor)
    panes = []
    for part in script['parts']:
        if not (part['id'].startswith('Window') or part['id'].startswith('Windshield')) or '*' in part['id']:
            continue
        if part['id'] in row.get('excludeParts', []):
            continue
        for model in part.get('models', []):
            mesh = model.get('mesh', '').split('|')[-1]
            obj = bpy.data.objects.get(mesh)
            if obj is None:
                continue
            values = []
            for vertex in obj.data.vertices:
                p = obj.matrix_world @ vertex.co
                values.append([p.x * mapping['sx'], p.z * mapping['sy'], p.y * mapping['sz']])
            points = np.unique(np.round(values, 7), axis=0)
            if len(points) < 4:
                continue
            centre = points.mean(axis=0)
            _, _, axes = np.linalg.svd(points-centre, full_matrices=False)
            inward = axes[-1]
            if np.dot(inward, [-centre[0], 0, row.get('centreZ', 0)-centre[2]]) < 0:
                inward = -inward
            up = np.array([0., 1., 0.]) - inward*inward[1]
            up /= np.linalg.norm(up)
            across = np.cross(up, inward)
            u, v, depth = ((points-centre) @ axis for axis in (across, up, inward))
            width, height = np.ptp(u), np.ptp(v)
            assert width > .15 and height > .15 and np.ptp(depth) < .15, (row['family'], part['id'], 'glazing plane')
            origin = centre + across*(u.min()+u.max())/2 + up*(v.min()+v.max())/2 + inward*depth.max()
            # Fit corner radius from diagonal support rather than copying the
            # native pane's vertices. Clamp only within practical trim sizes.
            diagonal = max(abs(u)/width*2 + abs(v)/height*2)
            radius = min(width, height)*max(.025, min(.16, (2-diagonal)/1.171572875))
            panes.append(dict(part=part['id'], parent=part.get('parent'), mesh=mesh,
                origin=origin.round(7).tolist(), across=across.round(7).tolist(), up=up.round(7).tolist(),
                inward=inward.round(7).tolist(), width=round(float(width), 7), height=round(float(height), 7),
                radius=round(float(radius), 7), border=.042, depth=.035, gasket=.010))
    assert panes, (row['family'], 'no measured glazing')
    result['families'][row['family']] = dict(source=cfg['fbx'], sourceSha256=hashlib.sha256(Path(cfg['fbx']).read_bytes()).hexdigest(), panes=panes)
    print(row['family'], len(panes), 'fitted window returns', flush=True)
Path(args[1]).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
