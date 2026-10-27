"""Read native wheel-opening boundary candidates; export numerical sections only.

Run through the guarded Blender lane:
blender -b --factory-startup --python measure_native_boundaries.py -- manifest.json output.json

The manifest lists family, measurement config and shell config. Candidates are
not accepted arch profiles: open boundaries, asymmetric sides or branched joins
need review against the native renderer before a flat-floor spec can use them.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_vehicle_fbx import load

args = sys.argv[sys.argv.index('--')+1:]
manifest = json.loads(Path(args[0]).read_text('utf-8-sig'))
out = Path(args[1])
out.parent.mkdir(parents=True, exist_ok=True)
results = []
loaded = None

for row in sorted(manifest, key=lambda item: (item['measureConfig'], item['family'])):
    cfg = json.loads(Path(row['measureConfig']).read_text('utf-8-sig'))
    shell = json.loads(Path(row['shellConfig']).read_text('utf-8-sig'))
    fbx = cfg['fbx']
    if fbx != loaded:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        load(fbx)
        loaded = fbx
    obj = bpy.data.objects.get(cfg['body'])
    if obj is None:
        meshes = [candidate for candidate in bpy.data.objects if candidate.type == 'MESH']
        assert len(meshes) == 1, (row['family'], 'unresolved native body')
        obj = meshes[0]
    mapping = cfg.get('map', dict(sx=-90, sy=90, sz=90))
    if 'modelScale' in cfg:
        scale = obj.matrix_world.to_scale()
        assert max(scale)-min(scale) < 1e-5, (row['family'], 'nonuniform native scale')
        factor = cfg['modelScale']/scale.z
        mapping = dict(sx=-factor, sy=factor, sz=factor)
    points = []
    for vertex in obj.data.vertices:
        position = obj.matrix_world @ vertex.co
        points.append(tuple(round(value, 7) for value in
                            (position.x*mapping['sx'], position.z*mapping['sy'], position.y*mapping['sz'])))
    # Weld coincident positions numerically so material/UV seams are not
    # mistaken for physical apertures. Retain only true one-face edges.
    edges = Counter()
    edge_faces = defaultdict(list)
    normals = {}
    face_bounds = []
    uv_layer = obj.data.uv_layers[0] if obj.data.uv_layers else None
    up_ranges = defaultdict(list)
    if '--full-edges' in args[2:]:
        obj.data.calc_loop_triangles()
        for tri in obj.data.loop_triangles:
            a,b,c=[points[i] for i in tri.vertices]
            ab=[b[i]-a[i] for i in range(3)];ac=[c[i]-a[i] for i in range(3)]
            cross=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
            length=sum(v*v for v in cross)**.5
            if length>1e-12:up_ranges[tri.polygon_index].append(abs(cross[1])/length)
    for poly in obj.data.polygons:
        ring = [points[index] for index in poly.vertices]
        a,b,c=ring[:3]
        ab=[b[i]-a[i] for i in range(3)];ac=[c[i]-a[i] for i in range(3)]
        normal=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
        length=sum(v*v for v in normal)**.5
        normals[poly.index]=[v/length if length>1e-12 else 0 for v in normal]
        if '--full-edges' in args[2:]:
            native_uv=[(float(uv_layer.data[i].uv.x),1-float(uv_layer.data[i].uv.y))
                       for i in poly.loop_indices] if uv_layer else []
            face_bounds.append(dict(id=poly.index,normal=normals[poly.index],material=poly.material_index,
                normalUpRange=[min(up_ranges[poly.index]),max(up_ranges[poly.index])] if up_ranges[poly.index] else [0,0],
                passengerBounds=[[min(p[i] for p in ring),max(p[i] for p in ring)] for i in range(3)],
                nativeUVBounds=[[min(p[i] for p in native_uv),max(p[i] for p in native_uv)] for i in range(2)] if native_uv else None))
        for a, b in zip(ring, ring[1:]+ring[:1]):
            if a != b:
                edge=tuple(sorted((a,b)))
                edges[edge] += 1
                edge_faces[edge].append(poly.index)
    boundaries = [edge for edge, count in edges.items() if count == 1]
    floor = shell['floorY']
    candidates = []
    for index, well in enumerate(shell.get('wheelWells', [])):
        side = 1 if max(well['x']) > 0 else -1
        inner = min(abs(value) for value in well['x'])
        rear, front = well['z']
        near = [edge for edge in boundaries if all(side*point[0] > inner+.02
                    and rear-.25 <= point[2] <= front+.25
                    and floor-.65 <= point[1] <= floor+.7 for point in edge)]
        graph = defaultdict(set)
        for a, b in near:
            graph[a].add(b)
            graph[b].add(a)
        remaining = {tuple(sorted(edge)) for edge in near}
        paths = []
        while remaining:
            endpoints = sorted(point for point, neighbours in graph.items()
                               if sum(tuple(sorted((point, other))) in remaining for other in neighbours) == 1)
            start = endpoints[0] if endpoints else min(min(edge) for edge in remaining)
            path = [start]
            while True:
                neighbours = sorted(other for other in graph[path[-1]]
                                    if tuple(sorted((path[-1], other))) in remaining)
                if not neighbours:
                    break
                other = neighbours[0]
                remaining.remove(tuple(sorted((path[-1], other))))
                path.append(other)
                if other == start or len(graph[other]) != 2:
                    break
            if len(path) >= 2:
                paths.append(path)
        candidate=dict(well=index, side=side, floor=floor, existingWell=well,
                               edges=len(near), branches=sum(len(value) > 2 for value in graph.values()),
                               paths=paths)
        if '--full-edges' in args[2:]:
            # Closed native wells need actual crease/face ownership; an absent
            # one-face edge is not evidence that the wheel opening is absent.
            candidate['localEdges']=[dict(points=edge,faces=edge_faces[edge],
                normals=[normals[i] for i in edge_faces[edge]]) for edge in edges
                if all(side*p[0]>inner-.10 and rear-.3<=p[2]<=front+.3
                       and floor-.75<=p[1]<=floor+.75 for p in edge)]
        candidates.append(candidate)
    result=dict(family=row['family'], source=fbx, body=obj.name,
                        sourceSha256=hashlib.sha256(Path(fbx).read_bytes()).hexdigest(),
                        nativeBoundaryEdges=len(boundaries), wheelCandidates=candidates,
                        acceptance='unreviewed numeric candidates; no runtime spec change')
    if '--full-edges' in args[2:]:
        result['faces']=face_bounds
        result['nativeUVContract']='Native first UV is (source u,1-source v); only bounds/face identities exported'
    results.append(result)
    out.with_suffix('.partial.json').write_text(json.dumps(results, indent=2)+'\n')
    print('NATIVE_BOUNDARY '+row['family']+' '+str([item['edges'] for item in candidates]), flush=True)

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2)+'\n')
