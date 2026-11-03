"""Merge static draw calls by PBR material; editable modular .blend is preserved."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/headquarters.blend'))
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.convert(target='MESH')
groups={}
for o in list(bpy.context.scene.objects):
 if o.type=='MESH':groups.setdefault(o.active_material.name if o.active_material else 'none',[]).append(o)
for name,objects in groups.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
 bpy.ops.object.join();bpy.context.object.name='Static batch / '+name
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(ROOT/'frontend/public/assets/headquarters.glb'),export_format='GLB',export_apply=False)
print('Static batches:',len(groups))
