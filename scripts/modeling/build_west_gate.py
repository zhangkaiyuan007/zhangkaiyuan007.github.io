"""Photo-guided reconstruction of SWJTU Xipu new west gate.
Run with Blender 4.5 LTS --background --python this-file -- [--render].
Geometry dimensions are proportional estimates, not surveyed measurements.
"""
import bpy, math, random, json, sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'static/ride/models/xipu-west-gate'; TEX=ROOT/'.tools/west-gate/textures'
ART=ROOT/'artifacts/xipu-west-gate'; ART.mkdir(parents=True,exist_ok=True)
rng=random.Random(77)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
for m in list(bpy.data.materials):bpy.data.materials.remove(m)
parts={}; category='Architecture'
def register(o):parts.setdefault(category,[]).append(o);return o
def rgb(c):
 v=[int(c[i:i+2],16)/255 for i in (0,2,4)]
 return tuple(x/12.92 if x<.04045 else ((x+.055)/1.055)**2.4 for x in v)+(1,)
def mat(name,color,rough=.7,metal=0,texture=None,bump=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=rgb(color);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
 if texture:
  n=m.node_tree.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(TEX/texture),check_existing=True);m.node_tree.links.new(n.outputs['Color'],p.inputs['Base Color'])
 if texture and (TEX/(Path(texture).stem+'-normal.png')).exists():
  n=m.node_tree.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(TEX/(Path(texture).stem+'-normal.png')),check_existing=True);n.image.colorspace_settings.name='Non-Color';norm=m.node_tree.nodes.new('ShaderNodeNormalMap');norm.inputs['Strength'].default_value=.4;m.node_tree.links.new(n.outputs['Color'],norm.inputs['Color']);m.node_tree.links.new(norm.outputs['Normal'],p.inputs['Normal'])
 if bump and not texture:
  noise=m.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=65;noise.inputs['Detail'].default_value=3
  b=m.node_tree.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.35;b.inputs['Distance'].default_value=bump;m.node_tree.links.new(noise.outputs['Fac'],b.inputs['Height']);m.node_tree.links.new(b.outputs['Normal'],p.inputs['Normal'])
 return m
red=mat('Terracotta / physical sides','8b4437',.76,texture='terracotta.jpg',bump=.018)
frontmat=mat('Photographic facade / rectified original','964a3c',.8,texture='facade-reference.jpg')
seam=mat('Recessed terracotta joints','62382f',.9)
white=mat('Ivory arch soffit','d2d2c4',.85,bump=.012)
gold=mat('Raised photographed calligraphy / bronze','b29a50',.32,.65)
stone=mat('Split granite','a8a79d',.88,bump=.10)
stonephoto=mat('Monument original stone and lettering','b8ada0',.86,texture='monument-reference.jpg',bump=.02)
concrete=mat('Concrete kerbs','b6b9b5',.9,bump=.02)
asphalt=mat('Asphalt fine aggregate','51575a',.96,texture='asphalt.jpg',bump=.014)
pavers=mat('Paving blocks','9d9f99',.92,texture='pavers.jpg',bump=.015)
paint=mat('Road marking white','d2d0bc',.95)
metal=mat('Brushed steel','9ea8a9',.3,.8)
black=mat('Dark structural metal','293033',.44,.55)
glass=mat('Tinted pavilion glazing','334d4d',.19,.5)
grass=mat('Lawn mottled ground','486136',.97,texture='grass.jpg',bump=.015)
leaves=[mat('Leaf '+str(i),c,.87) for i,c in enumerate(['263e25','354d2c','42643b','587640','6b844b'])]
bark=mat('Tree bark','655c4c',.98,bump=.055)
cream=mat('Campus light render','c9c9ba',.88,bump=.01)
brick=mat('Campus brick','856458',.85)

def bevel(o,amount=.025,segments=2):
 if amount:
  mod=o.modifiers.new('Edge bevel','BEVEL');mod.width=amount;mod.segments=segments
  mod=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
 return o

def mesh(name,verts,faces,mats,indices=None):
 data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update();o=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(o)
 for m in mats:data.materials.append(m)
 if indices:
  for p,i in zip(data.polygons,indices):p.material_index=i
 return register(o)

def uv_project(o,face_mat=None,mode='tile'):
 uv=o.data.uv_layers.new(name='UVMap') if not o.data.uv_layers else o.data.uv_layers.active
 if face_mat and face_mat.name not in [m.name for m in o.data.materials]:o.data.materials.append(face_mat)
 for p in o.data.polygons:
  isfront=face_mat is not None and p.normal.y<-.99
  if isfront:p.material_index=list(o.data.materials).index(face_mat)
  for li in p.loop_indices:
   v=o.matrix_world@o.data.vertices[o.data.loops[li].vertex_index].co
   if isfront and mode=='facade':uv.data[li].uv=((v.x+19)/38,v.z/12.5)
   elif isfront and mode=='monument':uv.data[li].uv=((v.x+7.5)/15,(v.z-.32)/3.2)
   elif abs(p.normal.z)>.7:uv.data[li].uv=(v.x/3,v.y/3)
   elif abs(p.normal.y)>.7:uv.data[li].uv=(v.x/6,v.z/.9)
   else:uv.data[li].uv=(v.y/6,v.z/.9)

def box(name,loc,dim,material,edge=.025,photo=False):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(material);bpy.context.view_layer.update();register(o);uv_project(o,frontmat if photo else None,'facade' if photo else 'tile');bevel(o,edge);return o

def cylinder(name,a,b,r,material,vertices=12,r2=None):
 a,b=Vector(a),Vector(b);d=b-a
 bpy.ops.mesh.primitive_cone_add(vertices=vertices,radius1=r,radius2=r if r2 is None else r2,depth=d.length,location=(a+b)/2);o=bpy.context.object;o.name=name;o.rotation_quaternion=d.to_track_quat('Z','Y');o.rotation_mode='QUATERNION';o.rotation_quaternion=d.to_track_quat('Z','Y');o.data.materials.append(material)
 for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
 return register(o)

def arch(name,rx1,rz1,rx2,rz2,depth,material,photo=False):
 n=128;v=[]
 for y in [-depth/2,depth/2]:
  for rx,rz in [(rx1,rz1),(rx2,rz2)]:
   for i in range(n+1):a=math.pi*i/n;v.append((rx*math.cos(a),y,rz*math.sin(a)))
 k=n+1;f=[]
 for i in range(n):
  f.extend([(i,i+1,k+i+1,k+i),(2*k+i,3*k+i,3*k+i+1,2*k+i+1),(i,2*k+i,2*k+i+1,i+1),(k+i,k+i+1,3*k+i+1,3*k+i)])
 f.extend([(0,k,3*k,2*k),(n,2*k+n,3*k+n,k+n)])
 o=mesh(name,v,f,[material]);uv_project(o,frontmat if photo else None,'facade' if photo else 'tile');bevel(o,.018,2)
 return o

# Main gate: rectangular frame, red arch, white soffit and fourteen recessed uprights.
for x in [-18.25,18.25]:box('Main jamb',(x,0,6.25),(1.5,3.8,12.5),red,.045,True)
box('Upper inscription beam',(0,0,11.28),(38,3.8,2.44),red,.035,True)
arch('Terracotta arch',18.95,9.05,18.0,8.05,3.72,red)
arch('Ivory inner arch',18.0,8.05,16.35,7.38,3.68,white)
for i in range(14):
 x=-15.5+i*31/13;bottom=9.05*math.sqrt(max(0,1-(x/18.95)**2));height=10.06-bottom
 box('Recessed vertical pier '+str(i),(x,.05,bottom+height/2),(.45,3.22,height+.04),red,.016)
 box('Pier dark reveal '+str(i),(x+.27,-1.61,bottom+height/2),(.065,.09,height),seam,.005)
 # Individual cladding courses make the architecture readable from oblique views.
 for z in [bottom+.19+j*.21 for j in range(max(0,int(height/.21)-1))]:box('Pier mortar joint',(x,-1.565,z),(.452,.016,.014),seam,0)
for z in [.15+i*.23 for i in range(54)]:
 for x in [-18.25,18.25]:box('Jamb horizontal joint',(x,-1.909,z),(1.49,.014,.015),seam,0)
for y in [-1.919,1.919]:
 for z in [10.15+i*.23 for i in range(10)]:box('Beam cladding joint',(0,y,z),(37.9,.012,.014),seam,0)
# Trace contours into actual extruded bronze letter geometry, including counters.
paths=json.loads((TEX/'inscription.json').read_text());curve=bpy.data.curves.new('Photo-traced school name','CURVE');curve.dimensions='2D';curve.fill_mode='BOTH';curve.extrude=.026;curve.bevel_depth=.008;curve.bevel_resolution=2
for path in paths:
 pts=path['points'];s=curve.splines.new('POLY');s.points.add(len(pts)-1)
 for p,(x,z) in zip(s.points,pts):p.co=(x,z,0,1)
 s.use_cyclic_u=True
for side in [-1,1]:
 o=bpy.data.objects.new('Bronze calligraphy '+str(side),curve.copy());bpy.context.collection.objects.link(o);o.rotation_euler=(math.pi/2,0,0 if side==-1 else math.pi);o.location.y=side*1.946;o.data.materials.append(gold);register(o)

category='Pavilions'
def pavilion(x,y,width):
 box('Pavilion roof',(x,y,3.78),(width,6,.65),red,.035)
 box('Pavilion upper coping',(x,y,4.13),(width+.12,6.12,.08),red,.018)
 box('Pavilion soffit',(x,y,3.4),(width-.28,5.65,.09),white,.01)
 for dx in [-width/2+.27,width/2-.27]:
  for dy in [-2.65,2.65]:box('Pavilion corner pier',(x+dx,y+dy,1.75),(.55,.6,3.5),red,.025)
  for z in [.2+i*.22 for i in range(16)]:box('Pavilion pier joint',(x+dx,y-2.96,z),(.55,.015,.013),seam,0)
 for z in [3.58,3.8,4.0]:box('Pavilion roof joint',(x,y-3.01,z),(width,.015,.015),seam,0)
 # Glazed security cabin recessed within the portico.
 box('Security cabin',(x,y+1,1.55),(width*.62,2.9,3.1),glass,.008)
 for dx in [-width*.31,0,width*.31]:box('Glazing mullion',(x+dx,y-.46,1.6),(.065,.08,3.1),metal,.006)
 for z in [.18,1.06,3.12]:box('Glazing transom',(x,y-.46,z),(width*.62,.07,.05),metal,.004)
 for dx in [-width*.29,width*.29]:box('Cabin plinth',(x+dx,y-.44,.32),(.4,.12,.64),black,.01)
 box('Pavilion raised platform',(x,y,.08),(width+1.5,7,.16),concrete,.025)
pavilion(-26,-34,10);pavilion(26,-34,10);pavilion(0,-32,11)
# Turnstiles and lifting barriers, photographed entrance furniture.
for side in [-1,1]:
 for x in [side*20.5,side*23.5,side*26.5,side*29.5]:
  box('Turnstile pedestal',(x,-36.45,.55),(.2,.34,1.1),metal,.03)
  cylinder('Turnstile axle',(x,-36.45,.62),(x+.45,-36.45,.62),.035,metal)
  for a in [0,2.094,4.188]:cylinder('Turnstile arm',(x+.45,-36.45,.62),(x+.45,-36.45+math.sin(a)*.48,.62+math.cos(a)*.48),.025,metal)
 box('Barrier motor',(side*14.6,-36.4,.6),(.44,.5,1.2),metal,.055)
 box('Barrier boom',(side*11.2,-36.4,1.05),(6.4,.09,.1),paint,.01)
 for i in range(5):box('Barrier red band',(side*(8.6+i*1.15),-36.455,1.05),(.45,.012,.1),red,0)

category='Ground'
box('Entrance asphalt',(0,-12,-.15),(76,100,.27),asphalt,.04)
for side in [-1,1]:
 box('Outer sidewalk',(side*28,6,.06),(18,40,.22),pavers,.02)
 for y in [-13+j*.8 for j in range(48)]:box('Individual granite kerb',(side*18.9,y,.15),(.25,.78,.3),concrete,.012)
 # Parallel double lane markings.
 for x in [side*7.6,side*7.85]:box('Lane divider',(x,9,.003),(.09,29,.01),paint,0)
 for y in [-32,-27,-21,-3,4,11,18,25]:box('Broken lane marking',(side*13,y,.005),(.12,2.2,.012),paint,0)
for x in [-34+i*1.38 for i in range(50)]:box('Zebra crossing',(x,8,.01),(.65,4.5,.012),paint,0)
for side in [-1,1]:
 for y in [-20,8]:
  x=side*11
  box('Direction arrow stem',(x,y,.01),(.19,2.5,.015),paint,0)
  o=mesh('Road arrowhead',[(x-.65,y+1,.02),(x+.65,y+1,.02),(x,y+2.1,.02)],[(0,1,2)],[paint])
# Oval planted island and monument.
def ellipse(name,x,y,rx,ry,z,material):
 v=[(x,y,z)]+[(x+rx*math.cos(i*math.tau/96),y+ry*math.sin(i*math.tau/96),z) for i in range(96)]
 return mesh(name,v,[(0,i+1,(i+1)%96+1) for i in range(96)],[material])
ellipse('Central lawn island',0,-39,15,12,.06,grass)
for side in [-1,1]:box('Side planted verge',(side*34,5,.11),(7,42,.08),grass,.06)
# Uneven split-granite slab with photographic front UV, real volume on all sides.
o=box('School name stone',(0,-37,1.92),(15,1.18,3.2),stone,.07);uv_project(o,stonephoto,'monument')
for x in [-5.7,-2.8,0,2.8,5.7]:cylinder('Monument ground uplight',(x,-38.3,.1),(x,-38.3,.24),.13,black,16)

category='Landscape'
leafverts=[];leaffaces=[];leafidx=[]
def leaf_cloud(center,radii,count,size=.18):
 center=Vector(center)
 for _ in range(count):
  d=Vector((rng.gauss(0,1),rng.gauss(0,1),rng.gauss(0,1))).normalized();radius=rng.random()**.27
  p=center+Vector((d.x*radii[0],d.y*radii[1],d.z*radii[2]))*radius
  a=rng.random()*math.tau;u=Vector((math.cos(a),math.sin(a),rng.uniform(-.7,.7))).normalized()*size*rng.uniform(.65,1.35);v=Vector((-u.y,u.x,rng.uniform(-.08,.08))).normalized()*size*.48
  k=len(leafverts);leafverts.extend([p-u,p-v-u*.3,p+v*.15+Vector((0,0,.04)),p+v-u*.3,p+u]);leaffaces.extend([(k,k+1,k+2,k+3),(k+3,k+2,k+4),(k+2,k+1,k+4)]);leafidx.extend([rng.randrange(5)]*3)
def tree(x,y,h):
 cylinder('Tree main trunk',(x,y,.1),(x+.13,y+.06,h*.62),.21,bark,10,.065)
 for j in range(7):
  a=j*2.4+rng.random();z=h*(.38+j*.047);end=(x+math.cos(a)*h*.24,y+math.sin(a)*h*.24,h*(.72+rng.random()*.19))
  cylinder('Tree branch',(x,y,z),end,.072,bark,7,.018)
  leaf_cloud(end,(h*.24,h*.22,h*.21),650,.24)
 # White-painted lower trunks visible in the campus avenue photographs.
 cylinder('Painted lower trunk',(x,y,.12),(x+.025,y+.01,1.05),.216,white,10,.18)
for side in [-1,1]:
 for y in [4,12,20,28]:tree(side*(16.7+rng.random()),y,rng.uniform(8,10))
 for y in [-6,10,24]:tree(side*(32+rng.random()*2),y,rng.uniform(9,11))
for x in [-8.5+i*.7 for i in range(25)]:leaf_cloud((x,-38.5,.52),(.58,.5,.43),80,.10)
for side in [-1,1]:
 for y in range(-1,28,2):leaf_cloud((side*18.1,y,.52),(.58,1.1,.46),75,.11)
le=mesh('Individual leaf blades',leafverts,leaffaces,leaves,leafidx)
# Small grass blades on the island, geometry instead of billboard trees.
v=[];f=[]
for _ in range(6500):
 x=rng.uniform(-15,15);y=rng.uniform(-51,-27)
 if (x/15)**2+((y+39)/12)**2>1 or (abs(x)<7.8 and abs(y+37)<1.1):continue
 h=rng.uniform(.05,.14);w=.017;a=rng.random()*math.tau;k=len(v);v.extend([(x-w*math.cos(a),y-w*math.sin(a),.055),(x+w*math.cos(a),y+w*math.sin(a),.055),(x+.03,y,.055+h)]);f.append((k,k+1,k+2))
mesh('Individual lawn blades',v,f,[leaves[2]])
# Paired streetlights and campus banners.
for side in [-1,1]:
 for y in [-6,15,28]:
  x=side*18.2;cylinder('Streetlight mast',(x,y,0),(x,y,8.2),.085,metal,12,.05)
  for dx in [-.5,.5]:
   cylinder('Streetlight arm',(x,y,8.05),(x+dx,y,8.4),.04,metal,10)
   box('Lamp housing',(x+dx,y,8.4),(.55,.22,.11),metal,.035)
  box('Banner panel',(x+.3,y,4.7),(.48,.035,1.2),red,.008)

category='Context'
for side in [-1,1]:
 x=side*28;y=25
 box('Campus building',(x,y,7),(15,12,14),cream,.04)
 for z in [3,5.8,8.6,11.4]:
  box('Building slab line',(x,y-6.04,z-.8),(15,.12,.18),concrete,.006)
  for dx in [-6,-4,-2,0,2,4,6]:
   box('Campus window',(x+dx,y-6.08,z),(1.25,.05,1.5),glass,.005)
   box('Window mullion',(x+dx,y-6.13,z),(.035,.04,1.5),metal,0)
   box('Window sill',(x+dx,y-6.2,z-.77),(1.4,.24,.09),concrete,.007)
   box('Air conditioner',(x+dx+.66,y-6.32,z-.45),(.42,.38,.4),white,.025)
box('Distant campus tower',(7,35,7),(11,9,14),brick,.04)
for x in [2.5+i*1.2 for i in range(8)]:
 for z in [2+i*1.5 for i in range(8)]:box('Tower glazing',(x,30.47,z),(.8,.05,1.1),glass,.002)

# Daylight studio scene, rendered on the verified local NVIDIA device.
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=64;scene.cycles.use_denoising=True
pref=bpy.context.preferences.addons['cycles'].preferences
try:
 pref.compute_device_type='OPTIX';pref.get_devices()
 for d in pref.devices:d.use=d.type=='OPTIX'
 scene.cycles.device='GPU'
 print('GPU_RENDER_DEVICES',[(d.name,d.type,d.use) for d in pref.devices],flush=True)
except Exception as e:print('GPU setup unavailable:',e);scene.cycles.device='CPU'
world=bpy.data.worlds.new('Soft daylight');scene.world=world;world.use_nodes=True;nodes=world.node_tree.nodes;bg=nodes.get('Background');bg.inputs['Strength'].default_value=.32
sky=nodes.new('ShaderNodeTexSky');sky.sky_type='NISHITA';sky.sun_elevation=math.radians(32);sky.sun_rotation=math.radians(215);sky.air_density=1.2;world.node_tree.links.new(sky.outputs[0],bg.inputs[0]);ambient=nodes.new('ShaderNodeBackground');ambient.inputs['Color'].default_value=(.65,.72,.8,1);ambient.inputs['Strength'].default_value=.65;path=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader');world.node_tree.links.new(path.outputs['Is Camera Ray'],mix.inputs[0]);world.node_tree.links.new(ambient.outputs[0],mix.inputs[1]);world.node_tree.links.new(bg.outputs[0],mix.inputs[2]);world.node_tree.links.new(mix.outputs[0],nodes.get('World Output').inputs['Surface'])
bpy.ops.object.light_add(type='SUN',location=(-30,-40,50));daylight=bpy.context.object;daylight.name='Soft overcast sun';daylight.data.energy=1.5;daylight.data.angle=.25;daylight.rotation_euler=(-daylight.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.light_add(type='AREA',location=(-16,-23,26));light=bpy.context.object;light.name='Large sky fill';light.data.energy=1600;light.data.shape='DISK';light.data.size=25;light.rotation_euler=(Vector((0,0,4))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-62,3.0));camera=bpy.context.object;camera.name='West gate outside';camera.rotation_euler=(Vector((0,-1,5.3))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=34;scene.camera=camera
scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=-.4;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
# Render-only continuation hides the presentation asset boundary.
bpy.ops.mesh.primitive_plane_add(size=1000,location=(0,0,-.29));render_floor=bpy.context.object;render_floor.name='Render-only ground continuation';render_floor.data.materials.append(asphalt);uv_project(render_floor)
# Pack photographic textures so the .blend is portable.
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(ART/'xipu-west-gate.blend'))
# Export a compact scene with one object per logical layer, merging primitives by material.
bpy.ops.object.select_all(action='DESELECT')
export_objects=[]
for name,objects in parts.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join();o=bpy.context.object;o.name=name;export_objects.append(o)
bpy.ops.object.select_all(action='DESELECT')
for o in export_objects:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'xipu-west-gate.glb'),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_materials='EXPORT',export_copyright='Photo-derived textures and model: CC BY-SA 4.0. Reference photography: Kcx36 / Wikimedia Commons. See SOURCE.md.',export_extras=True,export_draco_mesh_compression_enable=True,export_draco_mesh_compression_level=7)
print('MODEL_EXPORT_DONE',sum(len(o.data.polygons) for o in export_objects),'faces',flush=True)
if '--render' in sys.argv:
 scene.render.filepath=str(OUT/'west-gate-render.png');bpy.ops.render.render(write_still=True)
 camera.location=(0,-28,2.2);camera.rotation_euler=(Vector((0,0,5.5))-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.lens=24;scene.render.filepath=str(ART/'arch-render.png');bpy.ops.render.render(write_still=True)
