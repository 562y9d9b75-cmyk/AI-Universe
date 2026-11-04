"""Bake / batch static PBR architecture, preserving editable source modules.
Run: blender -b -t 2 -P scripts/optimize_assets.py
Optional args after --: --source assets/headquarters-v2.blend --output frontend/public/assets/headquarters-v2.glb
"""
import argparse, sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(); parser.add_argument('--source',default='assets/headquarters-v2.blend'); parser.add_argument('--output',default='frontend/public/assets/headquarters-v2.glb')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
source,output=ROOT/args.source,ROOT/args.output
if output.name in ('headquarters.glb','workstation.glb'):raise ValueError('Choose a new output name: original published assets are preserved.')
bpy.ops.wm.open_mainfile(filepath=str(source)); bpy.ops.object.select_all(action='DESELECT')
for o in list(bpy.context.scene.objects):
 if o.type in ('MESH','FONT','CURVE'):o.select_set(True)
 else:bpy.data.objects.remove(o,do_unlink=True)
bpy.context.view_layer.objects.active=next(iter(bpy.context.selected_objects)); bpy.ops.object.convert(target='MESH')
groups={}
for o in list(bpy.context.scene.objects):
 if o.type=='MESH':groups.setdefault(o.active_material.name if o.active_material else 'none',[]).append(o)
for name,objects in groups.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]; bpy.ops.object.join(); bpy.context.object.name='Static PBR batch / '+name
bpy.ops.object.select_all(action='SELECT'); output.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',export_apply=False,export_yup=True,export_cameras=False,export_lights=False)
triangles=sum(len(p.vertices)-2 for o in bpy.context.scene.objects if o.type=='MESH' for p in o.data.polygons)
print('Static batches:',len(groups),'/ triangles:',triangles,'/ bytes:',output.stat().st_size)
