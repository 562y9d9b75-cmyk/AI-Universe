"""Original CC0 headquarters v2. Blender 4.x. No downloads or substitute humans.
Run: blender -b -t 2 -P scripts/build_assets.py
Then: blender -b -t 2 -P scripts/optimize_assets.py
The published v1 .blend/.glb assets are preserved. Units: metres, Z-up source.
"""
import bpy, math, random
from pathlib import Path
from mathutils import Vector
random.seed(42)
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)

def mat(name,color,rough=.5,metal=0,texture=None):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
 s=m.node_tree.nodes.get('Principled BSDF'); s.inputs['Base Color'].default_value=(*color,1); s.inputs['Roughness'].default_value=rough; s.inputs['Metallic'].default_value=metal
 if texture:
  image=bpy.data.images.new(name+' original albedo',width=128,height=128); pixels=[]
  for y in range(128):
   for x in range(128):
    grain=(.023*math.sin(y*.7+2*math.sin(x*.04))+.01*math.sin(y*3)) if texture=='wood' else .008*math.sin(x*5)*math.sin(y*5)
    grain+=random.uniform(-.008,.008); pixels.extend((*[max(0,min(1,c+grain)) for c in color],1))
  image.pixels=pixels; image.pack(); t=m.node_tree.nodes.new('ShaderNodeTexImage'); t.image=image; m.node_tree.links.new(t.outputs['Color'],s.inputs['Base Color'])
 return m
oak=mat('01 Natural white oak',(.55,.39,.24),.48,texture='wood'); walnut=mat('02 Smoked walnut',(.24,.135,.078),.43,texture='wood'); stone=mat('03 Honed travertine',(.76,.73,.65),.65,texture='stone'); plaster=mat('04 Mineral plaster',(.88,.865,.81),.85); ivory=mat('05 Ivory powder coat',(.79,.79,.73),.5); bronze=mat('06 Aged bronze',(.23,.18,.115),.3,.65); graphite=mat('07 Graphite steel',(.047,.056,.055),.45,.4); aluminium=mat('08 Brushed aluminium',(.45,.48,.47),.29,.78); linen=mat('09 Oatmeal boucle',(.65,.60,.51),.98,texture='fabric'); olive=mat('10 Moss wool',(.27,.33,.23),.97,texture='fabric'); cognac=mat('11 Cognac leather',(.41,.23,.12),.64); carpet=mat('12 Sand wool rug',(.57,.54,.47),.98,texture='fabric'); terra=mat('13 Terracotta ceramic',(.55,.37,.255),.84); porcelain=mat('14 Warm porcelain',(.91,.89,.83),.24); green=mat('15 Mature leaf',(.095,.20,.085),.58); young=mat('16 Young leaf',(.20,.31,.13),.64); soil=mat('17 Soil and coffee',(.10,.065,.036),.97); screen=mat('18 Screen glass',(.035,.063,.07),.24); paper=mat('19 Paper and linen art',(.84,.82,.74),.92)
books=[mat('Book '+str(i),c,.84) for i,c in enumerate([(.31,.40,.33),(.58,.39,.24),(.19,.25,.28),(.74,.69,.56),(.40,.24,.21)])]
glass=mat('20 Low iron glass',(.63,.76,.71),.15); glass.diffuse_color=(.63,.76,.71,.12); glass.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value=.12
if hasattr(glass,'surface_render_method'): glass.surface_render_method='DITHERED'
diffuser=mat('21 Warm luminaire diffuser',(.95,.85,.65)); s=diffuser.node_tree.nodes.get('Principled BSDF'); s.inputs['Emission Color'].default_value=(1,.84,.58,1); s.inputs['Emission Strength'].default_value=.5

def cube(name,loc,dims,material=oak,bevel=.025):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=dims; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(material)
 if bevel:
  mod=o.modifiers.new('Manufactured edge radius','BEVEL'); mod.width=bevel; mod.segments=3; o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o

def cyl(name,loc,r,depth,material=oak,vertices=24):
 bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=depth,location=loc); o=bpy.context.object; o.name=name; o.data.materials.append(material)
 for p in o.data.polygons:p.use_smooth=True
 return o

def sphere(name,loc,dims,material=linen):
 # Tiny foliage is repeated across the floor; keep its silhouette without dense hidden geometry.
 leaves='leaf' in name.lower()
 bpy.ops.mesh.primitive_uv_sphere_add(segments=12 if leaves else 16,ring_count=6 if leaves else 10,radius=1,location=loc); o=bpy.context.object; o.name=name; o.scale=dims; o.data.materials.append(material)
 for p in o.data.polygons:p.use_smooth=True
 return o

def bar(name,a,b,r=.02,material=graphite):
 o=cyl(name,(Vector(a)+Vector(b))/2,r,(Vector(b)-Vector(a)).length,material,12); o.rotation_euler=(Vector(b)-Vector(a)).to_track_quat('Z','Y').to_euler(); return o

def text(name,content,loc,size,material):
 bpy.ops.object.text_add(location=loc,rotation=(math.pi/2,0,0)); o=bpy.context.object; o.name=name; o.data.body=content; o.data.size=size; o.data.extrude=.0015; o.data.align_x='CENTER'; o.data.materials.append(material)

def mug(x,y,z):
 cyl('Porcelain mug',(x,y,z+.05),.045,.10,porcelain); cyl('Coffee surface',(x,y,z+.102),.037,.003,soil)
 bpy.ops.mesh.primitive_torus_add(major_segments=12,minor_segments=6,location=(x+.052,y,z+.05),major_radius=.03,minor_radius=.008,rotation=(math.pi/2,0,0)); bpy.context.object.data.materials.append(porcelain)

def plant(x,y,size=1,z=0):
 cyl('Ceramic planter',(x,y,z+.25*size),.24*size,.50*size,terra); cyl('Planter topsoil',(x,y,z+.503*size),.21*size,.012,soil)
 for stem in range(3):
  a=stem*2.4; bar('Ficus branch',(x,y,z+.47*size),(x+math.cos(a)*.17*size,y+math.sin(a)*.17*size,z+(1.35+stem*.1)*size),.012*size,walnut)
  for n in range(10):
   a=n*2.4+stem*2.4; h=z+(.69+n*.073)*size; r=(.23+.07*math.sin(n))*size; end=(x+math.cos(a)*r,y+math.sin(a)*r,h)
   bar('Leaf stem',(x,y,h-.1*size),end,.004*size,walnut); o=sphere('Curved broad ficus leaf',end,(.145*size,.064*size,.016*size),green if n%3 else young); o.rotation_euler=(.25,.35*math.sin(a),a)

def rotate_new(before,origin,angle):
 for o in set(bpy.context.scene.objects)-before:
  x,y=o.location.x-origin[0],o.location.y-origin[1]; o.location.x=origin[0]+x*math.cos(angle)-y*math.sin(angle); o.location.y=origin[1]+x*math.sin(angle)+y*math.cos(angle); o.rotation_euler.z+=angle

def chair(x,y,material=olive,angle=0,executive=False):
 before=set(bpy.context.scene.objects); cyl('Chair gas lift',(x,y,.30),.033,.45,aluminium)
 for i in range(5):
  a=i*math.tau/5; xx,yy=x+math.cos(a)*.28,y+math.sin(a)*.28; bar('Five-star chair base',(x,y,.13),(xx,yy,.08),.017); sphere('Rubber castor',(xx,yy,.07),(.035,.035,.045),graphite)
 cube('Upholstered chair seat',(x,y,.50),(.54,.53,.12),material,.07); cube('Lumbar chair back',(x,y-.25,.90),(.52,.09,.72 if executive else .59),material,.085)
 for side in [-1,1]:bar('Chair arm support',(x+side*.29,y-.15,.46),(x+side*.29,y-.1,.70),.015); cube('Padded armrest',(x+side*.29,y,.72),(.055,.28,.04),material,.02)
 rotate_new(before,(x,y),angle)

def desk(x,y,index,executive=False):
 cube('Solid oak desk top',(x,y,.76),(2.40,1.04,.07),walnut if executive else oak,.045)
 for side in [-1,1]:
  for d in [-1,1]:cube('Desk leg',(x+side*1.04,y+d*.39,.36),(.05,.05,.72),graphite,.008)
 cube('Cable tray',(x,y+.32,.65),(1.5,.12,.08),graphite); cube('Felt desk pad',(x,y-.12,.803),(1.1,.43,.008),olive,.025); cube('Monitor base',(x,y+.17,.81),(.35,.22,.025),aluminium); bar('Monitor stand',(x,y+.24,.82),(x,y+.26,1.15),.026,aluminium); cube('Display enclosure',(x,y+.26,1.23),(.82,.047,.47),graphite,.025); cube('Dark display glass',(x,y+.232,1.23),(.78,.007,.42),screen,.007)
 for n in range(5):cube('Neutral document lines',(x-.08,y+.226,1.36-n*.06),(.42-.04*(n%3),.002,.008),paper,.001)
 cube('Keyboard',(x,y-.22,.824),(.46,.16,.024),ivory,.015)
 for row in range(3):
  for col in range(10):cube('Keyboard key',(x-.197+col*.043,y-.269+row*.046,.84),(.032,.032,.005),graphite,.002)
 sphere('Wireless mouse',(x+.39,y-.2,.829),(.042,.065,.024),ivory); cube('Closed notebook',(x-.81,y-.12,.82),(.25,.33,.027),books[index%5],.008); bar('Desk pen',(x-.82,y-.21,.841),(x-.73,y-.04,.841),.005,bronze); mug(x+.87,y+.15,.80); cube('Mobile pedestal',(x+.82,y+.02,.33),(.43,.61,.63),ivory)
 for n in range(3):cube('Drawer reveal',(x+.82,y-.29,.18+n*.18),(.4,.005,.006),graphite,.001); cube('Drawer pull',(x+.82,y-.3,.23+n*.18),(.12,.018,.015),bronze)
 chair(x,y-.91,cognac if executive else olive,executive=executive)

def sofa(x,y,width=2.8,angle=0,material=linen):
 before=set(bpy.context.scene.objects)
 for s in [-1,1]:
  for d in [-1,1]:cyl('Sofa turned foot',(x+s*(width/2-.17),y+d*.32,.12),.035,.24,walnut)
 cube('Upholstered sofa body',(x,y,.37),(width,.98,.38),material,.13); cube('Upholstered sofa back',(x,y+.41,.78),(width,.23,.79),material,.12)
 for s in [-1,1]:cube('Sofa upholstered arm',(x+s*(width/2-.06),y,.66),(.21,1.0,.56),material,.10)
 for n in range(3):cube('Sofa individual cushion',(x+(n-1)*(width-.35)/3,y-.04,.60),((width-.42)/3,.75,.16),material,.08)
 for s in [-1,1]:o=cube('Loose wool pillow',(x+s*(width/2-.5),y+.23,.89),(.42,.18,.40),olive,.08); o.rotation_euler.y=s*.15
 rotate_new(before,(x,y),angle)

def round_table(x,y,r=.6,height=.45):
 cyl('Round oak table top',(x,y,height),r,.065,oak,48); cyl('Round table pedestal',(x,y,height/2),r*.30,height,walnut,32)

def shelf(x,y,width=2.6):
 for s in [-1,1]:cube('Bookcase end panel',(x+s*width/2,y,1.22),(.06,.4,2.44),walnut)
 cube('Bookcase backing',(x,y+.18,1.22),(width,.035,2.44),oak)
 for z in [.1,.66,1.22,1.78,2.34]:cube('Bookcase shelf',(x,y,z),(width,.42,.05),walnut)
 for row in range(4):
  for n in range(14):
   h=random.uniform(.22,.38); cube('Library book',(x-width/2+.13+n*(width-.22)/14,y-.02,.69+row*.56+h/2),(.075,.25,h),random.choice(books),.005)

def glass_wall(x,y,width,angle=0,door=False):
 before=set(bpy.context.scene.objects); cube('Low iron glazed partition',(x,y,1.30),(width,.025,2.60),glass,.002)
 for s in [-1,1]:cube('Bronze glazing mullion',(x+s*width/2,y,1.30),(.035,.045,2.60),bronze,.004)
 for z in [.04,2.58]:cube('Glazing head and sill',(x,y,z),(width,.045,.035),bronze,.004)
 if door:bar('Glass door handle',(x+width*.32,y-.055,.85),(x+width*.32,y-.055,1.3),.012,bronze)
 rotate_new(before,(x,y),angle)

def pendant(x,y,length=2.25,z=2.85):
 for s in [-1,1]:bar('Pendant suspension',(x+s*length*.36,y,3.15),(x+s*length*.36,y,z),.0045)
 cube('Architectural linear pendant',(x,y,z),(length,.09,.07),graphite,.018); cube('Opal warm diffuser',(x,y,z-.039),(length-.07,.065,.012),diffuser,.003)

def artwork(x,y,width=1.3,height=1.0):
 cube('Abstract artwork frame',(x,y,1.65),(width+.08,.06,height+.08),walnut,.015); cube('Original linen art canvas',(x,y-.037,1.65),(width,.012,height),paper,.002); sphere('Abstract terracotta relief',(x-width*.15,y-.05,1.7),(width*.25,.018,height*.31),terra); cube('Abstract olive line',(x+width*.16,y-.068,1.61),(width*.19,.01,height*.57),olive,.02)

# Cutaway architecture leaves the interior visible and continuous circulation open.
cube('Floating foundation',(0,0,-.23),(26.7,20.7,.34),walnut,.08); cube('Continuous travertine slab',(0,0,-.035),(26.2,20.2,.10),stone,.025)
for x in range(-13,14,2):cube('Stone floor joint',(x,0,.017),(.009,20,.002),carpet,0)
for y in range(-10,11,2):cube('Stone floor joint',(0,y,.017),(26,.009,.002),carpet,0)
cube('Rear plaster wall',(0,10,1.55),(26.2,.18,3.1),plaster); cube('West plaster wall',(-13,0,1.55),(.18,20,3.1),plaster); cube('East cutaway parapet',(13,0,.16),(.16,20,.32),stone); cube('Front threshold',(0,-10,.08),(26,.16,.16),stone)
for x in [-11.7,-8.7,-5.7,-2.7,.3,3.3,6.3,9.3,12.0]:
 cube('Panoramic window recess',(x,9.87,1.8),(2.65,.045,2.16),screen,.01); cube('Daylight window pane',(x,9.83,1.8),(2.5,.03,2.04),glass,.002)
 for s in [-1,1]:cube('Window mullion',(x+s*1.30,9.80,1.8),(.035,.055,2.15),bronze,.004)
 cube('Timber window sill',(x,9.72,.69),(2.72,.26,.08),oak)
cube('Rear cove lighting',(0,9.80,3.0),(25.8,.07,.045),diffuser,.01)
for x in [-12.88,12.88]:cube('Oak skirting',(x,0,.10),(.035,20,.16),walnut,.004)

# Reception: stone monolith, original lettering, slatted screen, plants.
cube('Arrival timber platform',(0,-7.5,.035),(6.9,4.3,.04),oak); cube('Reception monolith',(0,-7.05,.56),(3.6,.9,1.10),stone,.16); cube('Reception countertop',(0,-7.05,1.13),(3.74,1,.065),walnut,.05); cube('Reception front inlay',(0,-7.515,.56),(2.45,.02,.54),walnut,.015); text('Reception brand','AI UNIVERSE',(0,-7.533,.55),.19,paper); cube('Reception workstation',(.85,-6.97,1.36),(.61,.05,.37),graphite)
for x in [-3.25,3.25]:plant(x,-7.5,1.15)
for n in range(22):cube('Reception vertical oak fin',(-1.6+n*.15,-5.5,1.25),(.045,.12,2.5),oak,.01)
text('Arrival wayfinding','HEADQUARTERS / 01',(0,-5.58,1.78),.14,graphite); pendant(0,-7,3.3,2.75)

# Six open studio workstations; the other two employees have private offices.
for index,(x,y) in enumerate([(x,y) for y in [0,4] for x in [-4.3,0,4.3]]):desk(x,y,index+1); pendant(x,y+.45); cube('Acoustic desk screen',(x,y+.58,.98),(2.32,.065,.5),olive,.035)
for x in [-2.15,2.15]:
 for y in [0,4]:plant(x,y+.40,.65)
cube('Studio storage wall',(0,6.2,.50),(10.8,.52,1.0),oak,.04)
for x in [-4.6,-3.2,-1.8,-.4,1,2.4,3.8,5.0]:cube('Storage cabinet seam',(x,5.93,.50),(.006,.007,.90),walnut,.001)
plant(-4.6,6.2,.42,1.01); plant(4.6,6.2,.42,1.01); text('Studio sign','STUDIO / COLLABORATE',(0,5.925,.64),.12,graphite)

# Two detailed independent offices, facing the studio through glass.
for index,x in [(0,-9.45),(7,9.45)]:
 cube('Private office timber floor',(x,6.65,.027),(6.2,6.15,.025),oak); cube('Private office rug',(x,6,.05),(4.5,3.1,.025),carpet,.05); glass_wall(x,3.5,6.25,door=True); glass_wall(x+(3.15 if x<0 else -3.15),6.7,6.4,math.pi/2); desk(x,6.7,index,executive=True); chair(x-.8,4.65,linen,math.pi); chair(x+.8,4.65,linen,math.pi); cube('Office credenza',(x,9.3,.48),(3.5,.62,.94),walnut,.04); plant(x+(2.3 if x<0 else -2.3),8.65,1.3)
 for n in range(5):cube('Credenza stacked book',(x-.85,9.25,.98+n*.035),(.3,.24,.03),books[n],.005)
 cyl('Credenza vase',(x+.9,9.25,1.15),.12,.42,terra); pendant(x,6.9,2.5)

# Lounge/library: layered timber, wool, upholstery, books and floor lamp.
cube('Library timber floor',(-9.3,-5.95,.03),(6.8,7.2,.035),oak); cube('Lounge wool rug',(-9.15,-6,.057),(5.6,5.6,.025),carpet,.08); sofa(-9.4,-3.85,3.4); sofa(-11.45,-6.2,2.6,-math.pi/2,olive); round_table(-9.25,-6,.85,.43); round_table(-8,-6.5,.47,.54); mug(-9.4,-5.9,.47); cube('Open design journal',(-9,-6.1,.48),(.38,.31,.02),paper,.006); sofa(-7.05,-8.15,1.25,math.pi*.85,cognac); shelf(-9.35,-2.7,3.6); plant(-12,-8.4,1.3); plant(-6.6,-3.15,1.0); cyl('Floorlamp base',(-11.8,-4.3,.04),.25,.06,bronze); bar('Floorlamp stem',(-11.8,-4.3,.07),(-11.8,-4.3,1.85),.018,bronze); cyl('Linen lampshade',(-11.8,-4.3,1.75),.25,.36,linen,40); cyl('Warm floorlamp diffuser',(-11.8,-4.3,1.57),.22,.015,diffuser); pendant(-9.3,-5.9,2.8,2.95)

# Coffee bar with espresso machine, grinder, sink, worktop and barstools.
cube('Coffee cabinetry',(-11.7,.25,.48),(1.15,4.6,.96),walnut); cube('Coffee worktop',(-11.7,.25,1.0),(1.24,4.7,.085),stone)
for y in [-1.3,-.2,.9,2]:cube('Coffee cabinet handle',(-11.06,y,.71),(.018,.18,.018),bronze)
cube('Commercial espresso machine',(-11.6,.65,1.34),(.77,.83,.57),aluminium,.06); cube('Espresso front panel',(-11.18,.65,1.34),(.025,.73,.40),graphite); cube('Espresso drip tray',(-11.06,.65,1.08),(.30,.73,.04),aluminium)
for y in [.43,.86]:bar('Portafilter',(-11.13,y,1.3),(-10.92,y,1.3),.025,graphite); mug(-11,y,1.10)
cube('Grinder base',(-11.6,1.55,1.24),(.35,.34,.35),graphite); cyl('Bean hopper',(-11.6,1.55,1.57),.13,.28,glass); cyl('Roasted coffee beans',(-11.6,1.55,1.52),.115,.18,soil); cube('Sink rim',(-11.65,-1.15,1.052),(.64,.62,.026),aluminium); cube('Sink interior',(-11.65,-1.15,1.068),(.51,.49,.008),screen); bar('Faucet',(-11.8,-.8,1.04),(-11.8,-.8,1.43),.017,aluminium); bar('Faucet spout',(-11.8,-.8,1.43),(-11.6,-.8,1.43),.017,aluminium)
for n in range(4):mug(-11.6,-1.85+n*.17,1.06)
cube('Coffee island base',(-8.25,.25,.49),(.72,3.2,.98),oak,.05); cube('Coffee island counter',(-8.25,.25,1.02),(1.18,3.5,.075),stone,.045)
for y in [-.9,.25,1.4]:
 cyl('Leather barstool seat',(-7.25,y,.77),.25,.10,cognac,32)
 for n in range(3):
  a=n*math.tau/3; bar('Barstool leg',(-7.25+.19*math.cos(a),y+.19*math.sin(a),.06),(-7.25+.15*math.cos(a),y+.15*math.sin(a),.73),.017,bronze)
 mug(-8.2,y,1.07)
plant(-12.15,2.95,.9); pendant(-8.25,.25,3.2,2.85)

# Glazed meeting suite with eight seats and a presentation wall.
cube('Meeting room carpet',(9.2,-5.65,.036),(6.8,7.2,.035),carpet,.04); glass_wall(5.75,-5.5,7,math.pi/2,door=True); glass_wall(9.3,-1.95,7.1,door=True); cube('Meeting wall panelling',(12.78,-5.6,1.45),(.10,6.5,2.9),walnut); cube('Presentation surround',(12.70,-5.5,1.75),(.06,2.5,1.38),graphite); cube('Presentation dark screen',(12.66,-5.5,1.75),(.015,2.34,1.22),screen)
for n in range(4):cube('Neutral presentation agenda',(12.648,-5.7+n*.2,1.75),(.003,.10,.55),paper)
cube('Conference oak table',(9,-5.5,.78),(1.6,4.5,.095),oak,.16)
for y in [-6.9,-4.1]:cube('Conference table base',(9,y,.38),(.90,.28,.76),walnut,.06)
for y in [-7,-5.5,-4]:chair(7.65,y,linen,-math.pi/2); chair(10.35,y,linen,math.pi/2)
chair(9,-8.35,olive); chair(9,-2.65,olive,math.pi)
for y in [-6.8,-5.3,-3.8]:cube('Conference writing pad',(9,y,.839),(.38,.28,.015),paper,.005); mug(9.4,y,.84)
cube('Conference speakerphone',(9,-5.5,.86),(.22,.22,.06),graphite,.06); cube('Meeting credenza',(11.9,-8.7,.46),(1.6,.6,.92),walnut); cyl('Water carafe',(11.7,-8.7,1.09),.075,.30,glass); plant(11.85,-2.6,1.2); plant(6.6,-8.85,1.1); pendant(9,-5.5,3.6,2.9)

# Quiet reading nook on the window promenade, original abstract wall art.
sofa(-2.1,8.35,1.6,0,olive); sofa(2.1,8.35,1.6,0,linen); round_table(0,8,.52,.48); mug(0,8,.52); plant(-5.5,8.8,1.25); plant(5.5,8.8,1.25)
for y in [-7.6,-4.4,-.2,3,6.5]:
 before=set(bpy.context.scene.objects); artwork(-12.88,y,1.4,1.1); rotate_new(before,(-12.88,y),math.pi/2)

# Source-only inspection camera and lights, never included in the runtime GLB.
scene=bpy.context.scene; bpy.ops.object.camera_add(location=(31,-35,30)); camera=bpy.context.object; camera.name='Inspection camera'; camera.rotation_euler=(Vector((0,0,.8))-camera.location).to_track_quat('-Z','Y').to_euler(); camera.data.type='ORTHO'; camera.data.ortho_scale=37; scene.camera=camera
bpy.ops.object.light_add(type='AREA',location=(-6,-4,16)); bpy.context.object.data.energy=3500; bpy.context.object.data.shape='DISK'; bpy.context.object.data.size=18
bpy.ops.object.light_add(type='SUN',location=(0,0,12)); bpy.context.object.rotation_euler=(.45,-.5,-.35); bpy.context.object.data.energy=2.1
scene.world.color=(.75,.75,.70); scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.render.resolution_x=1600; scene.render.resolution_y=1200; scene.render.resolution_percentage=100; scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(ROOT/'assets/headquarters-v2-preview.png'); scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets/headquarters-v2.blend'))
print('Saved original CC0 v2 source',ROOT/'assets/headquarters-v2.blend')
