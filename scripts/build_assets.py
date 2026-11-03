"""Blender 4.x: original CC0 modular headquarters. Run: blender -b -t 2 -P scripts/build_assets.py
No external assets, downloads, or paid services. Units are meters; Z-up source.
"""
import bpy,math,random
from pathlib import Path
from mathutils import Vector
random.seed(21)
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'frontend/public/assets';OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)

def mat(name,color,rough=.5,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
 return m
wood=mat('Natural oak / longitudinal grain',(.49,.31,.16),.42)
# A small generated albedo image exports to glTF as an embedded PBR texture.
img=bpy.data.images.new('Original oak albedo',width=256,height=256)
pixels=[]
for y in range(256):
 for x in range(256):
  grain=.025*math.sin(y*.44+2*math.sin(x*.018))+.015*math.sin(y*2.1)+random.random()*.015
  pixels.extend((.5+grain,.34+grain,.21+grain,1))
img.pixels=pixels;img.pack();tex=wood.node_tree.nodes.new('ShaderNodeTexImage');tex.image=img;wood.node_tree.links.new(tex.outputs['Color'],wood.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
stone=mat('Warm limestone',(.72,.71,.66),.55);cream=mat('Ivory plaster',(.85,.84,.78),.8);black=mat('Graphite powder coated steel',(.055,.065,.067),.4,.5);metal=mat('Brushed aluminium',(.42,.45,.46),.28,.8);fabric=mat('Olive linen',(.29,.36,.27),.94);beige=mat('Oat bouclé',(.64,.59,.49),.95);leaves=mat('Ficus leaf',(.13,.25,.12),.57);leaflight=mat('Young leaves',(.26,.36,.15),.6);soil=mat('Potting soil',(.12,.08,.045),1);terra=mat('Matte ceramic',(.61,.45,.33),.8);white=mat('Porcelain',(.87,.86,.79),.25);screen=mat('Monitor dark glass',(.045,.085,.09),.2);bookm=[mat('Book cover '+str(i),c,.85) for i,c in enumerate([(.4,.49,.39),(.69,.52,.36),(.23,.31,.35),(.79,.75,.63),(.52,.34,.28)])]
glass=mat('Low iron architectural glass',(.67,.81,.76),.12)
glass.diffuse_color=(.67,.81,.76,.17)
bs=glass.node_tree.nodes.get('Principled BSDF');bs.inputs['Alpha'].default_value=.17
if hasattr(glass,'surface_render_method'):glass.surface_render_method='DITHERED'
light=mat('Warm luminous diffuser',(.98,.89,.7),.5);bs=light.node_tree.nodes.get('Principled BSDF');bs.inputs['Emission Color'].default_value=(1,.87,.62,1);bs.inputs['Emission Strength'].default_value=.4

def cube(name,loc,scale,material,bevel=.025):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material)
 if bevel:
  mod=o.modifiers.new('Soft manufactured edges','BEVEL');mod.width=bevel;mod.segments=2
  o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o

def cyl(name,loc,r,depth,material,vertices=20):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc);o=bpy.context.object;o.name=name;o.data.materials.append(material)
 for p in o.data.polygons:p.use_smooth=True
 return o

def sphere(name,loc,scale,material):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(material)
 for p in o.data.polygons:p.use_smooth=True
 return o

def bar(name,a,b,r,material):
 mid=(Vector(a)+Vector(b))/2;o=cyl(name,mid,r,(Vector(a)-Vector(b)).length,material,12);o.rotation_euler=(Vector(b)-Vector(a)).to_track_quat('Z','Y').to_euler();return o

def mug(x,y,z):
 cyl('Coffee / ceramic mug',(x,y,z+.05),.045,.1,white)
 cyl('Coffee surface',(x,y,z+.103),.035,.003,soil)
 bpy.ops.mesh.primitive_torus_add(major_segments=12,minor_segments=6,location=(x+.052,y,z+.05),major_radius=.03,minor_radius=.008,rotation=(math.pi/2,0,0));bpy.context.object.data.materials.append(white)

def plant(x,y,size=1):
 cyl('Planter',(x,y,.26*size),.24*size,.52*size,terra)
 cyl('Soil',(x,y,.525*size),.205*size,.015,soil)
 bar('Ficus trunk',(x,y,.5*size),(x+.06,y,1.5*size),.024*size,wood)
 for i in range(11):
  angle=i*2.4;z=(.9+i*.065)*size;r=(.28 if i<7 else .2)*size
  end=(x+math.cos(angle)*r,y+math.sin(angle)*r,z)
  bar('Plant branch',(x,y,z-.15*size),end,.008*size,wood)
  o=sphere('Ficus leaf',end,(.15*size,.075*size,.028*size),leaves if i%2 else leaflight);o.rotation_euler=(.3*math.sin(angle),.35,angle)

def chair(x,y,material=fabric):
 cyl('Chair base pillar',(x,y,.3),.035,.5,metal)
 for i in range(5):
  a=i*math.tau/5;xx=x+math.cos(a)*.28;yy=y+math.sin(a)*.28
  bar('Five star base',(x,y,.12),(xx,yy,.08),.017,black);sphere('Caster',(xx,yy,.07),(.035,.035,.045),black)
 cube('Seat cushion',(x,y,.49),(.54,.5,.11),material,.07)
 back=cube('Ergonomic backrest',(x,y-.24,.86),(.5,.075,.62),material,.08);back.rotation_euler.x=-.1
 for sign in [-1,1]:
  bar('Arm support',(x+sign*.29,y-.12,.45),(x+sign*.29,y-.1,.69),.018,black)
  cube('Arm rest',(x+sign*.29,y-.01,.71),(.06,.3,.045),black,.018)

def desk(x,y,i):
 cube('Oak worktop '+str(i),(x,y,.76),(2.35,1.1,.075),wood,.035)
 for a in [-1,1]:
  for b in [-1,1]:cube('Desk frame',(x+a*1.04,y+b*.43,.36),(.05,.05,.72),black,.008)
 cube('Cable tray',(x,y+.34,.66),(1.5,.12,.08),black)
 cube('Desk mat',(x,y-.12,.806),(1.0,.45,.009),beige,.018)
 cube('Monitor foot',(x,y+.2,.81),(.33,.22,.018),metal)
 bar('Monitor stand',(x,y+.27,.82),(x,y+.3,1.12),.025,metal)
 cube('Monitor housing',(x,y+.29,1.2),(.75,.055,.44),black,.024)
 cube('Monitor panel',(x,y+.255,1.2),(.71,.005,.4),screen,.008)
 # A subtle UI on the screen, no fake task completion display.
 for n in range(4):cube('Screen document line',(x-.1,y+.249,1.31-n*.065),(.32+n*.04,.003,.009),leaflight,.001)
 cube('Keyboard',(x,y-.22,.825),(.45,.16,.025),metal,.015)
 for row in range(3):
  for col in range(10):cube('Keyboard key',(x-.197+col*.043,y-.272+row*.047,.842),(.032,.033,.006),black,.002)
 sphere('Mouse',(x+.37,y-.22,.83),(.045,.067,.022),black)
 cube('Notebook',(x-.78,y-.14,.82),(.25,.32,.025),bookm[i%5],.01)
 bar('Pen',(x-.78,y-.2,.845),(x-.7,y-.05,.845),.005,black)
 mug(x+.85,y+.2,.81)
 cube('Desk pedestal',(x+.83,y+.05,.35),(.44,.64,.64),cream)
 for j in range(3):
  cube('Drawer shadow gap',(x+.83,y-.275,.19+j*.19),(.39,.006,.006),black,.001)
  cube('Drawer handle',(x+.83,y-.29,.25+j*.19),(.1,.018,.018),metal,.005)
 chair(x,y-.92)

def sofa(x,y):
 for a in [-1,1]:
  for b in [-1,1]:cube('Sofa leg',(x+a*1.12,y+b*.38,.12),(.06,.06,.24),wood)
 cube('Sofa body',(x,y,.35),(2.7,.95,.38),beige,.12)
 cube('Sofa back',(x,y+.42,.78),(2.7,.2,.8),beige,.1)
 for sign in [-1,1]:cube('Sofa arm',(x+sign*1.3,y,.66),(.18,.95,.54),beige,.08)
 for i in range(3):cube('Sofa seat',(x+(i-1)*.8,y-.04,.57),(.78,.77,.15),beige,.07)
 for i in [-1,1]:
  o=cube('Olive linen pillow',(x+i*.8,y+.24,.86),(.42,.16,.39),fabric,.07);o.rotation_euler.y=i*.17

def shelf(x,y):
 for sign in [-1,1]:cube('Bookcase upright',(x+sign*1.2,y,1.15),(.07,.37,2.3),wood)
 for z in [.12,.62,1.12,1.62,2.12]:cube('Bookcase shelf',(x,y,z),(2.5,.37,.045),wood)
 for j in range(4):
  for i in range(12):
   h=random.uniform(.2,.35);cube('Book',(x-1.05+i*.11,y-.03,.645+j*.5+h/2),(.07,.22,h),random.choice(bookm),.004)

# Modular room shell. No roof: usable orbit view of a complete headquarters floor.
cube('Foundation',(0,0,-.18),(24.4,16.4,.3),cream,.06)
for x in range(-12,12):
 for y in range(-8,8):cube('Limestone tile',(x+.5,y+.5,-.015),(.992,.992,.06),stone,.003)
cube('Rear wall',(0,8,1.35),(24,.16,2.7),cream)
cube('Left wall',(-12,0,1.35),(.16,16,2.7),cream)
cube('Right low perimeter',(12,0,.35),(.16,16,.7),cream)
for x in range(-11,12,2):
 cube('Window mullion',(x,7.88,1.55),(.045,.08,2.25),black,.004)
 cube('Rear glazing',(x+.98,7.9,1.55),(1.9,.03,2.2),glass,.002)
for x in range(-11,12):cube('Baseboard',(x+.5,7.87,.12),(.99,.035,.12),wood,.003)
# Reception
cube('Reception oak plinth',(-1,-6,.54),(3.3,.8,1.08),wood,.04)
cube('Reception limestone top',(-1,-6,1.1),(3.4,.86,.065),stone)
cube('Reception desktop',(0,-5.9,1.35),(.65,.055,.4),black)
plant(-4,-6,1.1);plant(2,-6,1.3)
# Open studio: eight furnished workstations.
for i,(x,y) in enumerate([(x,y) for y in [0,4] for x in [-5,-1,3,7]]):desk(x,y,i)
# Pendant lighting
for y in [1.2,5.2]:
 for x in [-5,-1,3,7]:
  for off in [-.8,.8]:bar('Pendant suspension',(x+off,y,2.95),(x+off,y,2.5),.006,black)
  cube('Linear pendant',(x,y,2.47),(2.1,.09,.07),black,.016)
  cube('Pendant diffuser',(x,y,2.427),(2.02,.07,.01),light,.002)
# Lounge, library, plants
for x in range(-11,-5):
 for y in range(-6,-1):cube('Oak lounge floor',(x+.5,y+.5,.028),(.99,.99,.02),wood,.002)
cube('Woven lounge rug',(-8.3,-3.6,.055),(5.1,3.7,.025),fabric,.03)
sofa(-8.3,-2.3)
cyl('Round coffee table',(-8.3,-4.2,.47),.72,.07,wood,48)
for a in [0,2.1,4.2]:bar('Coffee table leg',(-8.3+math.cos(a)*.4,-4.2+math.sin(a)*.4,.06),(-8.3+math.cos(a)*.4,-4.2+math.sin(a)*.4,.44),.025,black)
mug(-8.5,-4.2,.51);cube('Magazine',(-8.0,-4.2,.53),(.3,.4,.02),bookm[3],.008)
shelf(-10.2,-.8);plant(-11,-5.9,1.2);plant(-5.6,-2.4,.9)
# Coffee bar: commercial machine, grinder, sink, mugs and supplies.
cube('Coffee bar cabinetry',(-10,5,.48),(2.0,3.2,.96),wood)
cube('Stone coffee counter',(-10,5,1.0),(2.12,3.3,.08),stone)
cube('Espresso machine',(-10,5.55,1.3),(.7,.65,.5),metal,.045)
cube('Coffee machine front',(-10,5.2,1.3),(.62,.03,.35),black,.015)
for x in [-10.18,-9.83]:
 cyl('Group head',(x,5.1,1.26),.06,.07,metal)
 bar('Portafilter handle',(x,5.1,1.26),(x,4.96,1.26),.025,black)
 mug(x,5.05,1.04)
cube('Espresso drip tray',(-10,5.04,1.07),(.64,.22,.035),metal,.008)
cyl('Grinder hopper',(-10.62,5.5,1.55),.12,.28,glass);cyl('Coffee beans',(-10.62,5.5,1.5),.105,.18,soil)
cube('Grinder base',(-10.62,5.5,1.24),(.3,.35,.35),black)
cube('Sink bowl',(-10,4.2,1.045),(.65,.5,.025),metal)
bar('Faucet',(-10,4.48,1.06),(-10,4.48,1.4),.018,metal);bar('Faucet spout',(-10,4.48,1.4),(-10,4.3,1.4),.018,metal)
for i in range(4):mug(-9.4,4.2+i*.2,1.05)
plant(-11.1,7.1,.9)
# Glass meeting room and whiteboard.
for x in [5.4,11.6]:
 cube('Meeting glass wall',(x,-4.3,1.1),(.025,4.2,2.2),glass,.002)
 for y in [-6.4,-4.3,-2.2]:cube('Meeting glass frame',(x,y,1.1),(.035,.035,2.2),black,.002)
cube('Conference table',(8.5,-4.3,.76),(4.1,1.25,.09),wood,.05)
for x in [7.2,9.8]:cube('Conference table base',(x,-4.3,.36),(.08,.8,.72),black)
for x in [7,8.5,10]:chair(x,-5.35,beige)
for x in [7,8.5,10]:
 start=set(bpy.context.scene.objects);chair(x,-3.2,beige)
 # Face chairs on opposite side toward the table.
 for o in set(bpy.context.scene.objects)-start:
  o.location.x=2*x-o.location.x;o.location.y=2*(-3.2)-o.location.y;o.rotation_euler.z+=math.pi
cube('Whiteboard',(11.5,-4.4,1.55),(.05,2.5,1.15),white,.015)
for y in [-5.1,-4.6,-4.1]:cube('Whiteboard marker lines',(11.46,y,1.6),(.006,.26,.015),fabric,.003)
# Private director office in the rear-left corner, plus corridor details.
cube('Private office partition',(-7.2,5.8,1.1),(.025,3.8,2.2),glass,.002)
for y in [4,6,7.7]:cube('Private office frame',(-7.2,y,1.1),(.04,.04,2.2),black,.002)
cube('Private credenza',(-8.6,7.3,.6),(2.0,.6,1.2),wood)
plant(10.8,6.9,1.5);plant(3,7.1,1.1);plant(-5.6,7.1,1)
# Artwork: original abstract layered composition.
for y in [-5,0,4]:
 cube('Artwork frame',(-11.88,y,1.65),(.05,1.35,1.05),wood,.015)
 cube('Artwork linen',(-11.84,y,1.65),(.01,1.22,.92),beige,.001)
 sphere('Artwork relief',(-11.82,y+.15,1.7),(.015,.35,.28),fabric)
# Books, boxes, lamps and baskets add useful material variety.
for x in [-3,1,5,9]:
 cyl('Ceiling downlight',(x,7.7,2.5),.1,.035,light)
# Export a complete GLB and source blend, plus reusable furniture modules.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/headquarters.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT/'headquarters.glb'),export_format='GLB',export_apply=True,export_yup=True,export_cameras=False,export_lights=False)
# Reusable desk module: normalized coordinates, same PBR assets.
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.context.scene.objects:
 if -6.3<o.location.x<-3.7 and -1.5<o.location.y<.7:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'workstation.glb'),use_selection=True,export_format='GLB',export_apply=True)
print('Exported',OUT)
