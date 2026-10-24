"""Read external binary/ASCII FBX geometry for measurements, without exporting it.

Blender's built-in importer handles binary files. ASCII inputs use a separately
installed ufbx wheel matching Blender's Python (RVI_UFBX_DIR, or .tools/ufbx-blender).
No ufbx or vehicle assets are bundled with the mod.
"""
import os
from pathlib import Path
import sys

import bpy
from mathutils import Matrix


def load(path):
    with open(path, 'rb') as handle:
        binary = handle.read(23).startswith(b'Kaydara FBX Binary')
    if binary:
        bpy.ops.import_scene.fbx(filepath=path)
        return
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, os.environ.get('RVI_UFBX_DIR', str(root / '.tools/ufbx-blender')))
    import ufbx
    axes = ufbx.CoordinateAxes(ufbx.CoordinateAxis.POSITIVE_X, ufbx.CoordinateAxis.POSITIVE_Z,
                               ufbx.CoordinateAxis.NEGATIVE_Y)
    scene = ufbx.load_file(path, target_axes=axes, target_unit_meters=1.0)
    for node in scene.nodes:
        source = node.mesh
        if not source:
            continue
        vertices = [tuple(v) for v in source.vertices]
        indices = list(source.vertex_indices)
        faces = [indices[f.index_begin:f.index_begin + f.num_indices] for f in source.faces if f.num_indices >= 3]
        mesh = bpy.data.meshes.new(node.name)
        mesh.from_pydata(vertices, [], faces)
        obj = bpy.data.objects.new(node.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        m = node.geometry_to_world
        obj.matrix_world = Matrix(((m.c0.x, m.c1.x, m.c2.x, m.c3.x),
                                   (m.c0.y, m.c1.y, m.c2.y, m.c3.y),
                                   (m.c0.z, m.c1.z, m.c2.z, m.c3.z), (0, 0, 0, 1)))
