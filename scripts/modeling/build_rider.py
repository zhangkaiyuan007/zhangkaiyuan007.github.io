"""Rider + road bike for the ride scene -> static/ride/models/rider/rider.glb

Run from the repo root (after scripts/modeling/setup_rider.sh):
    ./scripts/blender --background --factory-startup --python scripts/modeling/build_rider.py -- [--render]
The script re-launches Blender once with BLENDER_USER_RESOURCES=.tools/rider/blender-user so MPFB and
its asset library resolve inside the git-ignored .tools/ directory. --render adds Cycles preview stills.

Pipeline
  1. Human (MPFB 2 / MakeHuman, CC0 data): male, early twenties, East Asian, slim, calibrated to 175 cm,
     game_engine skeleton. CC0 system assets for skin, eyes, brows, lashes and white sneakers, CC0 wool
     trousers, and a CC-BY hooded jacket recoloured into an orange shell (see SOURCE.md). The jacket's
     lowered hood is cut out and a raised hood is built around the head. Skin under the clothes is deleted
     (ray test). A buzz cut (under the hood), a grey T-shirt and a roughness map are painted into the skin
     texture in UV space.
  2. Bike: rider_bike.py, real dimensions, separately named moving nodes.
  3. Fit: sit-bone contact on the saddle, then saddle height solved for a 150 deg knee at the bottom of the
     stroke. Blender IK puts the ball of the foot over the pedal spindle (with ankling), knees tracking
     their poles, hands on the hoods with the upper spine flexed until the elbows bend to 155 deg.
  4. The riding pose at crank angle 0 becomes the bind pose. The cloth is cleaned there: fold-overs
     relaxed, Taubin-smoothed, trousers culled under the jacket and pressed onto the saddle, and kept
     torso skin tucked behind the jacket.
  5. One crank revolution (48 frames, 2 s) is baked into the glTF clip 'Pedal': bones plus
     Crankset/PedalL/PedalR node rotations, with a subtle pelvis rock.
  6. Export: GLB, Draco, JPEG textures (PNG only where alpha is needed).

Blender frame: +Y forward, +Z up, +X rider's right. glTF: -Z forward, +Y up, +X right.
"""
import os
import sys
import math
import json
import subprocess
import time
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / '.tools' / 'rider'
USER_RES = TOOLS / 'blender-user'

# MPFB and the MakeHuman asset library live in an isolated Blender user directory inside
# .tools/ (see setup_rider.sh). Re-launch Blender once with that directory selected.
if os.environ.get('BLENDER_USER_RESOURCES') != str(USER_RES):
    env = dict(os.environ, BLENDER_USER_RESOURCES=str(USER_RES))
    sys.exit(subprocess.call([bpy.app.binary_path] + sys.argv[1:], env=env))

import bmesh
import addon_utils
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rider_bike as RB

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = ROOT / 'static' / 'ride' / 'models' / 'rider'
WORK = TOOLS / 'work'
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

FRAMES = 48                  # samples per crank revolution
FPS = 24                     # -> clip duration 2.0 s
HEIGHT = 1.75
KNEE_BDC = math.radians(150)  # knee angle (thigh-shank) at bottom dead centre
ELBOW = math.radians(155)     # elbow angle on the hoods: relaxed, never locked straight
TORSO_TILT = math.radians(30)  # pelvis forward tilt
SPINE_FLEX = (math.radians(8), math.radians(8), math.radians(7))
T0 = time.time()


def log(*a):
    print('[rider %6.1fs]' % (time.time() - T0), *a, flush=True)


# ---------------------------------------------------------------- scene ---
def reset_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.armatures, bpy.data.actions):
        for d in list(coll):
            coll.remove(d)
    scn = bpy.context.scene
    scn.render.fps = FPS
    scn.frame_start, scn.frame_end = 0, FRAMES
    scn.frame_set(0)


def update():
    bpy.context.view_layer.update()


def tri_count(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    me = obj.evaluated_get(dg).to_mesh()
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    obj.evaluated_get(dg).to_mesh_clear()
    return n


# --------------------------------------------------------------- images ---
def load_rgba(path, size=None):
    img = bpy.data.images.load(str(path), check_existing=False)
    if size and (img.size[0] != size or img.size[1] != size):
        img.scale(size, size)
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)


def save_image(name, arr, fmt='JPEG', quality=88, colorspace='sRGB'):
    """Write an image to WORK and return a Blender image datablock that references it."""
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=(fmt == 'PNG'))
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    ext = '.jpg' if fmt == 'JPEG' else '.png'
    path = WORK / (name + ext)
    img.filepath_raw = str(path)
    img.file_format = fmt
    scn = bpy.context.scene
    scn.render.image_settings.quality = quality
    img.save(filepath=str(path), quality=quality) if fmt == 'JPEG' else img.save(filepath=str(path))
    bpy.data.images.remove(img)
    out = bpy.data.images.load(str(path))
    out.colorspace_settings.name = colorspace
    return out


def box_blur(a, r):
    """Separable box blur (edge-clamped) on an HxW or HxWxC float array."""
    if r < 1:
        return a
    for axis in (0, 1):
        pad = [(0, 0)] * a.ndim
        pad[axis] = (r + 1, r)
        p = np.pad(a, pad, mode='edge')
        c = np.cumsum(p, axis=axis)
        hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
        lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
        a = (hi - lo) / (2 * r + 1)
    return a


def value_noise(h, w, cells, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((cells + 1, cells + 1)).astype(np.float32)
    ys = np.linspace(0, cells, h, endpoint=False)
    xs = np.linspace(0, cells, w, endpoint=False)
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def rasterize_uv(tris_uv, tris_val, size):
    """Rasterise UV triangles (N,3,2 in 0..1) with per-vertex values (N,3) into a size x size map (max blend)."""
    img = np.zeros((size, size), dtype=np.float32)
    cov = np.zeros((size, size), dtype=bool)
    P = tris_uv * size
    for (a, b, c), (va, vb, vc) in zip(P, tris_val):
        x0, x1 = int(max(0, math.floor(min(a[0], b[0], c[0])))), int(min(size - 1, math.ceil(max(a[0], b[0], c[0]))))
        y0, y1 = int(max(0, math.floor(min(a[1], b[1], c[1])))), int(min(size - 1, math.ceil(max(a[1], b[1], c[1]))))
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        l3 = 1 - l1 - l2
        m = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        v = l1 * va + l2 * vb + l3 * vc
        sub = img[y0:y1 + 1, x0:x1 + 1]
        sub[m] = np.maximum(sub[m], v[m])
        cov[y0:y1 + 1, x0:x1 + 1] |= m
    return img, cov


# ------------------------------------------------------------ materials ---
def principled(name, base=None, tex=None, rough=0.5, metal=0.0, normal=None, normal_strength=1.0,
               alpha_tex=False, ior=1.45, sss=0.0, sss_radius=(1.0, 0.35, 0.2), spec=0.5, rough_tex=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes['Principled BSDF']
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['IOR'].default_value = ior
    p.inputs['Specular IOR Level'].default_value = spec
    if base is not None:
        p.inputs['Base Color'].default_value = tuple(base) + (1.0,) if len(base) == 3 else base
    if tex is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = tex
        nt.links.new(t.outputs['Color'], p.inputs['Base Color'])
        if alpha_tex:
            nt.links.new(t.outputs['Alpha'], p.inputs['Alpha'])
            m.surface_render_method = 'BLENDED'
    if rough_tex is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = rough_tex
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(t.outputs['Color'], sep.inputs['Color'])
        nt.links.new(sep.outputs['Green'], p.inputs['Roughness'])
    if normal is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = normal
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
    if sss:
        p.inputs['Subsurface Weight'].default_value = sss
        p.inputs['Subsurface Radius'].default_value = sss_radius
        p.inputs['Subsurface Scale'].default_value = 0.006
    return m


def set_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def read_mhmat(path):
    d = {}
    for line in Path(path).read_text(errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        k, _, v = line.partition(' ')
        d.setdefault(k, v.strip())
    return d


# ---------------------------------------------------------------- human ---
def mpfb():
    addon_utils.enable('bl_ext.user_default.mpfb', default_set=True, persistent=False)
    from bl_ext.user_default.mpfb.services.humanservice import HumanService
    from bl_ext.user_default.mpfb.services.targetservice import TargetService
    from bl_ext.user_default.mpfb.services.locationservice import LocationService
    from bl_ext.user_default.mpfb.entities.objectproperties import HumanObjectProperties
    return HumanService, TargetService, LocationService, HumanObjectProperties


def evaluated_coords(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    return co @ np.array(obj.matrix_world.to_3x3()).T + np.array(obj.matrix_world.translation)


def build_human():
    HS, TS, LS, HOP = mpfb()
    D = Path(LS.get_user_data())
    macro = TS.get_default_macro_info_dict()
    macro.update(dict(gender=1.0, age=0.47, muscle=0.56, weight=0.42, proportions=0.62, height=0.6))
    macro['race'] = dict(asian=0.9, caucasian=0.1, african=0.0)
    base = HS.create_human(scale=0.1, macro_detail_dict=macro, feet_on_ground=True)
    base.name = 'Body'

    def height_now():
        co = evaluated_coords(base)
        return co[:, 2].max() - co[:, 2].min(), co[:, 2].min()

    lo, hi = 0.3, 1.0
    for _ in range(12):
        mid = (lo + hi) / 2
        HOP.set_value('height', mid, entity_reference=base)
        TS.reapply_macro_details(base)
        h, _ = height_now()
        if h < HEIGHT:
            lo = mid
        else:
            hi = mid
    h, zmin = height_now()
    base.location.z -= zmin
    with bpy.context.temp_override(active_object=base, selected_editable_objects=[base], object=base):
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    log('human height %.3f m (height macro %.3f)' % (h, mid))
    # a little more adult/masculine bone structure than the macro alone gives
    tdir = Path(LS.get_mpfb_data('targets'))
    for rel, wgt in (('chin/chin-width-incr', 0.35), ('chin/chin-bones-incr', 0.3), ('chin/chin-prominent-incr', 0.2),
                     ('head/head-square', 0.25), ('mouth/mouth-lowerlip-volume-decr', 0.3), ('mouth/mouth-upperlip-volume-decr', 0.2),
                     ('eyebrows/eyebrows-trans-down', 0.25), ('neck/neck-scale-horiz-incr', 0.25), ('nose/nose-scale-horiz-incr', 0.15),
                     ('cheek/l-cheek-volume-decr', 0.2), ('cheek/r-cheek-volume-decr', 0.2)):
        TS.load_target(base, str(tdir / (rel + '.target.gz')), weight=wgt)
    h, zmin = height_now()
    base.location.z -= zmin
    with bpy.context.temp_override(active_object=base, selected_editable_objects=[base], object=base):
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    rig = HS.add_builtin_rig(base, 'game_engine')
    rig.name = 'Rider'
    rig.data.name = 'RiderSkeleton'

    def add(rel, typ):
        o = HS.add_mhclo_asset(str(D / rel), base, asset_type=typ, subdiv_levels=0, material_type='NONE')
        for m in list(o.modifiers):
            if m.type == 'SUBSURF':
                o.modifiers.remove(m)
        return o
    parts = dict(
        eyes=add('eyes/high-poly/high-poly.mhclo', 'Eyes'),
        brows=add('eyebrows/eyebrow010/eyebrow010.mhclo', 'Eyebrows'),
        lashes=add('eyelashes/eyelashes01/eyelashes01.mhclo', 'Eyelashes'),
        jacket=add('clothes/elvs_hooded_sweat_jacket1/elvs_hooded_sweat_jacket1.mhclo', 'Clothes'),
        pants=add('clothes/toigo_wool_pants/toigo_wool_pants.mhclo', 'Clothes'),
        shoes=add('clothes/shoes05/shoes05.mhclo', 'Clothes'),
    )
    names = dict(eyes='Eyes', brows='Eyebrows', lashes='Eyelashes', jacket='Jacket', pants='Trousers', shoes='Shoes')
    for k, o in parts.items():
        o.name = names[k]
        o.data.name = names[k]
    return base, rig, parts, D


def finalize_body(base, covers):
    """Apply the macro shape keys, then physically delete helper geometry and the skin hidden under
    the clothes (ray test along the vertex normal against each garment, eroded by one ring so no
    gaps open at cuffs and collars). Head, neck and hands are always kept."""
    with bpy.context.temp_override(active_object=base, object=base, selected_editable_objects=[base]):
        if base.data.shape_keys:
            bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
    me = base.data
    nv = len(me.vertices)
    groups = {g.name: g.index for g in base.vertex_groups}
    body_idx = groups['body']
    keep_groups = {groups[n] for n in groups if n in ('head', 'neck_01') or n.startswith(('hand_', 'index_', 'middle_', 'ring_', 'pinky_', 'thumb_'))}
    del_groups = {i for n, i in groups.items() if n.startswith('Delete.')}
    neck_z = base.parent.data.bones['neck_01'].head_local.z if base.parent else 1.39
    is_body = np.zeros(nv, bool)
    keep = np.zeros(nv, bool)
    pre_del = np.zeros(nv, bool)
    for v in me.vertices:
        wsum = 0.0
        for g in v.groups:
            if g.group == body_idx and g.weight > 0.5:
                is_body[v.index] = True
            if g.group in keep_groups:
                wsum += g.weight
            if g.group in del_groups and g.weight > 0.5:
                pre_del[v.index] = True
        keep[v.index] = wsum > 0.45 or (v.co.z > neck_z - 0.13 and abs(v.co.x) < 0.10 and v.co.y < 0.0) or (v.co.z > neck_z - 0.12 and abs(v.co.x) < 0.21)
    dg = bpy.context.evaluated_depsgraph_get()
    covered = np.zeros(nv, bool)
    for cloth, reach in covers:
        tree = BVHTree.FromObject(cloth, dg)
        for v in me.vertices:
            if not is_body[v.index] or keep[v.index] or covered[v.index]:
                continue
            n = v.normal
            hit = tree.ray_cast(v.co - n * 0.002, n, reach)
            if hit[0] is not None:
                covered[v.index] = True
    # erode by one ring: a vertex is removed only if all of its neighbours are covered too
    edges = np.array([e.vertices[:] for e in me.edges])
    ok = covered.copy()
    bad = ~covered
    ok[edges[:, 0][bad[edges[:, 1]]]] = False
    ok[edges[:, 1][bad[edges[:, 0]]]] = False
    kill = np.where((~is_body) | ok | pre_del)[0]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in kill], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    for m in list(base.modifiers):
        if m.type == 'MASK':
            base.modifiers.remove(m)
    for g in list(base.vertex_groups):
        if g.name.startswith(('Delete.', 'helper-', 'joint-')) or g.name in ('HelperGeometry', 'JointCubes'):
            base.vertex_groups.remove(g)
    log('body after hidden-part removal: %d verts (%d covered by clothes)' % (len(me.vertices), int(ok.sum())))


def tighten(cloth, body, z_from, keep=0.011, factor=0.7, arm_extra=0.18):
    """Pull a loose garment towards the body (rest pose) for a trimmer shell-jacket fit.
    Only above z_from (blended over 12 cm) so the hem keeps its room over the trousers."""
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(body, dg)
    arm = {g.index for g in cloth.vertex_groups if g.name.startswith(('lowerarm', 'hand_'))}
    moved = 0
    for v in cloth.data.vertices:
        loc, nrm, idx, dist = tree.find_nearest(v.co, 0.25)
        if loc is None or dist <= keep:
            continue
        w = min(1.0, max(0.0, (v.co.z - z_from) / 0.12))
        if w <= 0:
            continue
        fa = min(1.0, sum(g.weight for g in v.groups if g.group in arm))
        f = 1 - (1 - (factor - arm_extra * fa)) * w
        d = (v.co - loc)
        v.co = loc + d.normalized() * (keep + (dist - keep) * f)
        moved += 1
    cloth.data.update()
    log('tightened %s: %d verts' % (cloth.name, moved))


def smooth_weights(obj, repeat=5, factor=0.5, max_infl=4):
    """Soften skin-weight transitions of loose cloth (fewer fold-overs at the armpits)."""
    me = obj.data
    rig = obj.parent
    bones = {b.name for b in rig.data.bones}
    groups = [g for g in obj.vertex_groups if g.name in bones]
    gi = {g.index: k for k, g in enumerate(groups)}
    W = np.zeros((len(me.vertices), len(groups)), dtype=np.float64)
    for v in me.vertices:
        for g in v.groups:
            if g.group in gi:
                W[v.index, gi[g.group]] = g.weight
    E = _adjacency(me)
    for _ in range(repeat):
        acc = np.zeros_like(W)
        cnt = np.zeros(len(W))
        np.add.at(acc, E[:, 0], W[E[:, 1]])
        np.add.at(acc, E[:, 1], W[E[:, 0]])
        np.add.at(cnt, E[:, 0], 1)
        np.add.at(cnt, E[:, 1], 1)
        W = W * (1 - factor) + factor * acc / np.maximum(cnt, 1)[:, None]
    order = np.argsort(-W, axis=1)
    cut = np.zeros_like(W, dtype=bool)
    np.put_along_axis(cut, order[:, max_infl:], True, axis=1)
    W[cut] = 0
    W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
    for k, g in enumerate(groups):
        idx = np.nonzero(W[:, k] > 1e-4)[0]
        g.remove(list(range(len(me.vertices))))
        for i in idx:
            g.add([int(i)], float(W[i, k]), 'REPLACE')


# ------------------------------------------------------------------- hood ---
# The asset models its hood lowered onto the back. Those faces are two contiguous vertex-index blocks of the
# MakeHuman garment (checked by rendering them on their own); a raised hood is rebuilt around the head instead.
HOOD_DOWN = ((2270, 3360), (7770, 9780))
HOOD_UV = (0.330, 0.500, 0.080, 0.295)   # a plain-fabric patch of the recoloured jacket texture: u0, u1, v0, v1


def remove_hood_down(jacket, neck_z):
    """Delete the lowered hood and whatever it leaves disconnected (the drawstrings), then relax the new
    neckline along itself so its edge is smooth where the raised hood comes out of it."""
    me = jacket.data
    if len(me.vertices) != 9935:
        raise RuntimeError('unexpected hooded-jacket mesh: re-check HOOD_DOWN')
    inside = lambda i: any(a <= i < b for a, b in HOOD_DOWN)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if 2 * sum(inside(v.index) for v in f.verts) >= len(f.verts)], context='FACES')
    seen, pieces = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, piece = [f], []
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            piece.append(x)
            stack.extend(y for e in x.edges for y in e.link_faces if y not in seen)
        pieces.append(piece)
    pieces.sort(key=len)
    bmesh.ops.delete(bm, geom=[f for p in pieces[:-1] for f in p], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    ring = [v for v in bm.verts if v.is_boundary and v.co.z > neck_z - 0.25]
    nbr = {v: [e.other_vert(v) for e in v.link_edges if e.is_boundary] for v in ring}
    for _ in range(10):
        new = {v: (v.co + sum((u.co for u in nbr[v]), Vector()) / 2) / 2 for v in ring if len(nbr[v]) == 2}
        for v, c in new.items():
            v.co = c
    bm.to_mesh(me)
    bm.free()
    log('removed the lowered hood: jacket %d verts, neckline %d verts' % (len(me.vertices), len(ring)))


def add_hood(base, rig, jacket, eyes, around=72, rows=22, dome=14):
    """A raised hood coming out of the jacket's neckline. Points lie on horizontal rings around an axis
    through the neck and head, a gap outside the outermost skin (ears included). Along each meridian the
    profile is replaced by its concave majorant, so the hood falls straight from the back of the head and the
    ears to the collar instead of hugging the nape. The face opening is an ellipse in (angle, height).
    Weights come from the nearest skin, UVs from a plain patch of the jacket texture. Returns a mesh object."""
    masks = [m for m in base.modifiers if m.type == 'MASK']
    for m in masks:
        m.show_viewport = False
    bco = evaluated_coords(base)
    for m in masks:
        m.show_viewport = True
    update()
    me = base.data
    gi = {g.name: g.index for g in base.vertex_groups}
    wb, wh = np.zeros(len(me.vertices)), np.zeros(len(me.vertices))
    for v in me.vertices:
        for g in v.groups:
            if g.group == gi['body']:
                wb[v.index] = g.weight
            elif g.group == gi['head']:
                wh[v.index] = g.weight
    polys = [p.vertices[:] for p in me.polygons if all(wb[i] > 0.5 for i in p.vertices)]   # skin only, no helpers
    tree = BVHTree.FromPolygons([Vector(c) for c in bco], polys)
    head = bco[(wh > 0.6) & (wb > 0.5)]
    eye_z = float(evaluated_coords(eyes)[:, 2].mean())
    hb, nk = bw(rig, 'head'), bw(rig, 'neck_01')
    chin_z = float(head[head[:, 1] < hb.y - 0.03][:, 2].min())
    cy = float(head[:, 1].min() + head[:, 1].max()) / 2

    def axis(z):
        t = min(max((z - nk.z) / (eye_z - nk.z), 0.0), 1.0)
        return Vector((0.0, nk.y + (cy - nk.y) * t, z))

    # neckline of the jacket (rest pose faces -Y): height and radius as functions of the angle from the front
    jbm = bmesh.new()
    jbm.from_mesh(jacket.data)
    pts = [jacket.matrix_world @ v.co for v in jbm.verts if v.is_boundary and v.co.z > nk.z - 0.25]
    jbm.free()
    ang = np.array([math.atan2(p.x, -(p.y - axis(p.z).y)) for p in pts])
    order = np.argsort(ang)
    ang = ang[order]
    nz = np.array([pts[k].z for k in order])
    nr = np.array([math.hypot(pts[k].x, pts[k].y - axis(pts[k].z).y) for k in order])
    per = lambda a, y: float(np.interp(a, np.r_[ang - 2 * math.pi, ang, ang + 2 * math.pi], np.r_[y, y, y]))
    ss = lambda e0, e1, x: (lambda t: t * t * (3 - 2 * t))(min(max((x - e0) / (e1 - e0), 0.0), 1.0))

    thetas = [math.pi + 2 * math.pi * i / around for i in range(around)]   # column 0 at the back: the UV seam
    C, up = axis(eye_z), Vector((0.0, 0.0, 1.0))

    def outer(o, d):   # distance from o to the outermost skin along direction d (ears included)
        hit = tree.ray_cast(o + d * 0.4, -d, 0.4)
        return 0.4 - hit[3] if hit[0] is not None else 0.0

    # drape rows (tucked, neckline, then up to eye level) on horizontal rings; dome rows on rays from C
    R = np.zeros((rows + 1, around))
    Z = np.zeros((rows + 1, around))
    D = np.zeros((dome - 1, around))
    for i, th in enumerate(thetas):
        a = math.atan2(math.sin(th), math.cos(th))          # angle from the front, as used for the neckline
        d = Vector((math.sin(th), -math.cos(th), 0.0))
        zn, rn = per(a, nz), per(a, nr)
        back = max(0.0, -math.cos(th))
        zs = [zn - 0.03, zn - 0.006] + [zn + (eye_z - zn) * k / (rows - 1) for k in range(1, rows)]
        prof = []
        for jj, z in enumerate(zs):
            skin = outer(axis(z), d)
            if jj == 0:
                r = min(skin + 0.006, rn - 0.008)   # tucked inside the collar
            elif jj == 1:
                r = max(rn + 0.008, skin + 0.006)   # just outside and below the neckline edge, covering the cut
            else:
                r = skin + 0.012 + 0.014 * back * ss(nk.z, eye_z, z)
            prof.append([z, r])
        # the drape is replaced by its concave majorant (upper hull in the (z, r) plane): the hood falls
        # straight from the back of the head and the ears to the collar instead of hugging the nape
        hull = []
        for k in range(1, len(prof)):
            while len(hull) >= 2:
                (z1, r1), (z2, r2), (z3, r3) = prof[hull[-2]], prof[hull[-1]], prof[k]
                if (r2 - r1) * (z3 - z1) - (r3 - r1) * (z2 - z1) <= 0:
                    hull.pop()
                else:
                    break
            hull.append(k)
        hz, hr = [prof[k][0] for k in hull], [prof[k][1] for k in hull]
        for k in range(1, len(prof)):
            prof[k][1] = max(prof[k][1], float(np.interp(prof[k][0], hz, hr)))
        Z[:, i] = [p[0] for p in prof]
        R[:, i] = [p[1] for p in prof]
        for k in range(1, dome):
            phi = math.pi / 2 * k / dome
            dk = d * math.cos(phi) + up * math.sin(phi)
            D[k - 1, i] = outer(C, dk) + 0.012 + 0.014 * back * math.cos(phi) + 0.008 * math.sin(phi)
    for _ in range(3):   # soften bumps around the head (ears) without touching the neckline rows
        R[2:] = 0.25 * np.roll(R[2:], 1, 1) + 0.5 * R[2:] + 0.25 * np.roll(R[2:], -1, 1)
        D[:] = 0.25 * np.roll(D, 1, 1) + 0.5 * D + 0.25 * np.roll(D, -1, 1)
    pts = [[axis(Z[j, i]) + Vector((math.sin(th), -math.cos(th), 0.0)) * R[j, i] for i, th in enumerate(thetas)] for j in range(rows + 1)]
    for k in range(1, dome):
        phi = math.pi / 2 * k / dome
        pts.append([C + (Vector((math.sin(th), -math.cos(th), 0.0)) * math.cos(phi) + up * math.sin(phi)) * D[k - 1, i] for i, th in enumerate(thetas)])
    zp = C.z + outer(C, up) + 0.020
    n_rows = len(pts)

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new(jacket.data.uv_layers.active.name)
    grid = [[bm.verts.new(p) for p in row] for row in pts]
    pole = bm.verts.new(Vector((C.x, C.y, zp)))
    z_hi, z_lo, pa = eye_z + 0.068, chin_z + 0.018, math.radians(64)
    z0, zb = (z_hi + z_lo) / 2, (z_hi - z_lo) / 2
    u0, u1, v0, v1 = HOOD_UV
    U = lambda i: u0 + (u1 - u0) * i / around
    V = lambda j: v0 + (v1 - v0) * j / n_rows
    for j in range(n_rows - 1):
        for i in range(around):
            k = (i + 1) % around
            th = (thetas[i] + thetas[k] + (2 * math.pi if k == 0 else 0)) / 2
            a = math.atan2(math.sin(th), math.cos(th))
            zc = (pts[j][i].z + pts[j + 1][i].z) / 2
            if (a / pa) ** 2 + ((zc - z0) / zb) ** 2 < 1:
                continue
            f = bm.faces.new((grid[j][i], grid[j][k], grid[j + 1][k], grid[j + 1][i]))
            for loop, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                loop[uv].uv = (U(ii), V(jj))
    for i in range(around):
        f = bm.faces.new((grid[-1][i], grid[-1][(i + 1) % around], pole))
        for loop, (ii, jj) in zip(f.loops, ((i, n_rows - 1), (i + 1, n_rows - 1), (i + 0.5, n_rows))):
            loop[uv].uv = (U(ii), V(jj))
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    # smooth the stepped face-opening rim along itself, then turn it in so the edge shows some thickness
    bottom = set(grid[0])
    rim = [v for v in bm.verts if v.is_boundary and v not in bottom]
    nbr = {v: [e.other_vert(v) for e in v.link_edges if e.is_boundary] for v in rim}
    for _ in range(24):   # Taubin along the loop: smooths the steps without shrinking the opening
        for f in (0.5, -0.53):
            new = {v: v.co + (sum((u.co for u in nbr[v]), Vector()) / 2 - v.co) * f for v in rim if len(nbr[v]) == 2}
            for v, c in new.items():
                v.co = c
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    inner = {v: bm.verts.new(v.co - v.normal * 0.005) for v in rim}   # turned-in hem: the edge shows thickness
    for e in [e for e in bm.edges if e.is_boundary and e.verts[0] in inner and e.verts[1] in inner]:
        a, b = e.verts
        src = {l.vert: l[uv].uv.copy() for l in e.link_faces[0].loops}
        f = bm.faces.new((b, a, inner[a], inner[b]))
        for loop, w in zip(f.loops, (b, a, a, b)):
            loop[uv].uv = src[w]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    hme = bpy.data.meshes.new('Hood')
    bm.to_mesh(hme)
    bm.free()
    for p in hme.polygons:
        p.use_smooth = True
    hood = bpy.data.objects.new('Hood', hme)
    bpy.context.scene.collection.objects.link(hood)
    hood.parent = jacket.parent
    hood.matrix_world = jacket.matrix_world.copy()
    # skin weights: average of the nearest skin face's corners, bone groups only
    bones = set(rig.data.bones.keys())
    names = {g.index: g.name for g in base.vertex_groups if g.name in bones}
    vw = [{names[g.group]: g.weight for g in v.groups if g.group in names} for v in me.vertices]
    groups = {}
    for v in hme.vertices:
        _, _, fi, _ = tree.find_nearest(v.co)
        acc = {}
        for vi in polys[fi]:
            for n, w in vw[vi].items():
                acc[n] = acc.get(n, 0.0) + w
        tot = sum(acc.values()) or 1.0
        for n, w in acc.items():
            if n not in groups:
                groups[n] = hood.vertex_groups.new(name=n)
            groups[n].add([v.index], w / tot, 'REPLACE')
    log('hood: %d verts, %d faces, opening z %.3f-%.3f' % (len(hme.vertices), len(hme.polygons), z_lo, z_hi))
    return hood


def cull_covered(obj, cover, reach=0.05):
    """Delete faces of obj hidden under cover (ray along the vertex normal), eroded by one ring."""
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(cover, dg)
    me = obj.data
    covered = np.zeros(len(me.vertices), bool)
    for v in me.vertices:
        hit = tree.ray_cast(v.co + v.normal * 0.001, v.normal, reach)
        covered[v.index] = hit[0] is not None
    E = _adjacency(me)
    ok = covered.copy()
    ok[E[:, 0][~covered[E[:, 1]]]] = False
    ok[E[:, 1][~covered[E[:, 0]]]] = False
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kill = [f for f in bm.faces if all(ok[v.index] for v in f.verts)]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(me)
    bm.free()
    log('culled %d faces of %s hidden under %s' % (len(kill), obj.name, cover.name))


def strip_cornea(eyes, tex_path):
    """MakeHuman eyes carry a cornea shell mapped onto a transparent texel; drop it (opaque export)."""
    a = load_rgba(tex_path)[..., 3]
    h, w = a.shape
    uv = eyes.data.uv_layers.active.data
    bm = bmesh.new()
    bm.from_mesh(eyes.data)
    bm.faces.ensure_lookup_table()
    kill = []
    for p in eyes.data.polygons:
        u = sum(uv[i].uv[0] for i in p.loop_indices) / p.loop_total
        v = sum(uv[i].uv[1] for i in p.loop_indices) / p.loop_total
        if a[min(h - 1, int(v * h)), min(w - 1, int(u * w))] < 0.5:
            kill.append(bm.faces[p.index])
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(eyes.data)
    bm.free()
    log('eyes: removed %d cornea faces' % len(kill))


def taubin(obj, iters=8, lam=0.5, mu=-0.53):
    """Volume-preserving smoothing (Taubin lambda/mu) to take the faceting out of decimated cloth."""
    me = obj.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    E = _adjacency(me)
    bm = bmesh.new()
    bm.from_mesh(me)
    border = np.zeros(len(co), bool)
    for e in bm.edges:
        if e.is_boundary:
            border[e.verts[0].index] = border[e.verts[1].index] = True
    bm.free()
    cnt = np.zeros(len(co))
    np.add.at(cnt, E[:, 0], 1)
    np.add.at(cnt, E[:, 1], 1)
    for _ in range(iters):
        for f in (lam, mu):
            acc = np.zeros_like(co)
            np.add.at(acc, E[:, 0], co[E[:, 1]])
            np.add.at(acc, E[:, 1], co[E[:, 0]])
            delta = acc / np.maximum(cnt, 1)[:, None] - co
            delta[border] *= 0.3
            co = co + f * delta
    me.vertices.foreach_set('co', co.ravel())
    me.update()


def decimate(obj, ratio):
    """Collapse-decimate, protecting open borders (hem, cuffs, hood rim) from getting ragged."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    border = {v.index for e in bm.edges if e.is_boundary for v in e.verts}
    ring = set()
    bm.verts.ensure_lookup_table()
    for i in list(border):
        for e in bm.verts[i].link_edges:
            ring.add(e.other_vert(bm.verts[i]).index)
    bm.free()
    g = obj.vertex_groups.new(name='_keep')
    g.add(sorted(border | ring), 1.0, 'REPLACE')
    d = obj.modifiers.new('Decimate', 'DECIMATE')
    d.ratio = ratio
    d.use_collapse_triangulate = False
    d.vertex_group = '_keep'
    d.invert_vertex_group = True
    d.vertex_group_factor = 50.0
    # the armature modifier must stay last and unapplied
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_move_to_index(modifier='Decimate', index=0)
        bpy.ops.object.modifier_apply(modifier='Decimate')
    obj.vertex_groups.remove(obj.vertex_groups['_keep'])


# ------------------------------------------------------------- textures ---
def skin_texture(base, D, brows):
    """Skin diffuse with a painted buzz cut (short black hair) over the scalp group."""
    mh = read_mhmat(D / 'skins/young_asian_male/young_asian_male.mhmat')
    src = load_rgba(D / 'skins/young_asian_male' / mh['diffuseTexture'])
    size = src.shape[0]
    rgb = src[..., :3].copy()
    # slightly warmer, less pink, a touch less pale: closer to a young East Asian complexion
    lum = rgb.mean(axis=2, keepdims=True)
    rgb = lum + (rgb - lum) * 0.92
    rgb = rgb * np.array([1.0, 0.97, 0.90], dtype=np.float32) * 0.96

    me = base.data
    uv = me.uv_layers.active.data
    scalp = base.vertex_groups['scalp'].index
    w = np.zeros(len(me.vertices), dtype=np.float32)
    for v in me.vertices:
        for g in v.groups:
            if g.group == scalp:
                w[v.index] = g.weight
    # Soften the group into a hairline: a few rounds of neighbour averaging on the mesh graph
    edges = np.array([e.vertices[:] for e in me.edges])
    co = np.array([v.co[:] for v in me.vertices], dtype=np.float32)
    for _ in range(3):
        acc = np.zeros_like(w)
        cnt = np.zeros_like(w)
        np.add.at(acc, edges[:, 0], w[edges[:, 1]])
        np.add.at(acc, edges[:, 1], w[edges[:, 0]])
        np.add.at(cnt, edges[:, 0], 1)
        np.add.at(cnt, edges[:, 1], 1)
        w = 0.5 * w + 0.5 * acc / np.maximum(cnt, 1)
    # keep temples / sideburns short and the nape tapered
    head_z = co[:, 2].max()
    dens = np.clip((w - 0.18) / 0.55, 0, 1)
    dens *= np.clip((co[:, 2] - (head_z - 0.21)) / 0.05, 0, 1)
    # The MakeHuman scalp group stops short of the frontal scalp. Add a geometric hairline: ~6 cm above
    # the brows at the front, just over the ears at the sides, down to the nape at the back.
    gi = {g.name: g.index for g in base.vertex_groups}
    hw = np.zeros(len(me.vertices), dtype=np.float32)
    ear = np.zeros(len(me.vertices), dtype=bool)
    for v in me.vertices:
        for g in v.groups:
            if g.group == gi.get('head'):
                hw[v.index] = g.weight
            if g.group == gi.get('ears') and g.weight > 0.5:
                ear[v.index] = True
    brow_top = max(v.co.z for v in brows.data.vertices)
    ear_top = co[ear, 2].max() if ear.any() else brow_top - 0.01
    nape = base.parent.data.bones['head'].head_local.z - 0.01
    headv = hw > 0.5
    y_face, y_back = co[headv, 1].min(), co[headv, 1].max()
    t = np.clip((co[:, 1] - y_face) / (y_back - y_face), 0, 1)
    def ss(e0, e1, x):
        x = np.clip((x - e0) / (e1 - e0), 0, 1)
        return x * x * (3 - 2 * x)
    z_hair = brow_top + 0.058
    z_hair = z_hair + (ear_top + 0.004 - z_hair) * ss(0.30, 0.52, t)
    z_hair = z_hair + (nape - z_hair) * ss(0.62, 0.92, t)
    geo = np.clip((co[:, 2] - z_hair) / 0.014 + 0.5, 0, 1) * np.clip((hw - 0.3) / 0.3, 0, 1) * (~ear)
    dens = np.maximum(dens, geo)
    tris_uv, tris_val = [], []
    for p in me.polygons:
        vids = list(p.vertices)
        if max(dens[vids]) <= 0.0:
            continue
        luv = [uv[li].uv[:] for li in p.loop_indices]
        for k in range(1, len(vids) - 1):
            tris_uv.append([luv[0], luv[k], luv[k + 1]])
            tris_val.append([dens[vids[0]], dens[vids[k]], dens[vids[k + 1]]])
    dmap, _ = rasterize_uv(np.array(tris_uv, dtype=np.float32), np.array(tris_val, dtype=np.float32), size)
    for _ in range(6):       # grow past the UV island border so seams stay dark
        dmap = np.maximum.reduce([dmap, np.roll(dmap, 1, 0), np.roll(dmap, -1, 0), np.roll(dmap, 1, 1), np.roll(dmap, -1, 1)])
    dmap = box_blur(dmap, 3)
    hh, ww = dmap.shape
    fine = value_noise(hh, ww, 700, 3) * 0.6 + value_noise(hh, ww, 180, 4) * 0.4
    patch = value_noise(hh, ww, 24, 5)
    hair = np.array([0.052, 0.049, 0.047], dtype=np.float32)[None, None, :] * (0.75 + 0.5 * fine[..., None])   # sRGB
    stubble = value_noise(hh, ww, 1400, 9)
    a = np.clip(dmap * (0.84 + 0.12 * patch) * (0.82 + 0.18 * stubble), 0, 0.93)[..., None]
    # scalp showing through very short hair: mix in a darkened skin tone
    scalp_rgb = rgb * 0.5
    rgb = rgb * (1 - a) + (hair * 0.86 + scalp_rgb * 0.14) * a
    # dark crew-neck T-shirt on the torso skin that shows in the jacket's neck opening; the neckline is the
    # 0.5 isoline of a per-vertex mask from the neck bone weights, interpolated in UV space (no stair-steps)
    groups = {g.name: g.index for g in base.vertex_groups}
    neck = {groups[n] for n in ('neck_01', 'head') if n in groups}
    limb = {groups[n] for n in groups if n.startswith(('hand_', 'index_', 'middle_', 'ring_', 'pinky_', 'thumb_', 'lowerarm'))}
    wn = np.zeros(len(me.vertices), dtype=np.float32)
    wl = np.zeros(len(me.vertices), dtype=np.float32)
    for v in me.vertices:
        for g in v.groups:
            if g.group in neck:
                wn[v.index] += g.weight
            elif g.group in limb:
                wl[v.index] += g.weight
    shirt_v = np.clip((0.45 - wn) / 0.12 + 0.5, 0, 1) * np.clip((0.6 - wl) / 0.2, 0, 1)
    tris_uv, tris_val = [], []
    for p in me.polygons:
        vids = list(p.vertices)
        if max(shirt_v[vids]) <= 0.0:
            continue
        luv = [uv[li].uv[:] for li in p.loop_indices]
        for k in range(1, len(vids) - 1):
            tris_uv.append([luv[0], luv[k], luv[k + 1]])
            tris_val.append([shirt_v[vids[0]], shirt_v[vids[k]], shirt_v[vids[k + 1]]])
    smap, _ = rasterize_uv(np.array(tris_uv, dtype=np.float32), np.array(tris_val, dtype=np.float32), size)
    for _ in range(4):
        smap = np.maximum.reduce([smap, np.roll(smap, 1, 0), np.roll(smap, -1, 0), np.roll(smap, 1, 1), np.roll(smap, -1, 1)])
    sa = np.clip((smap - 0.42) / 0.16, 0, 1)
    sa = (sa * sa * (3 - 2 * sa))[..., None]
    knit = value_noise(hh, ww, 900, 7)[..., None]
    shirt_rgb = np.array([0.34, 0.345, 0.36], dtype=np.float32)[None, None, :] * (0.88 + 0.24 * knit)   # heather grey
    rgb = rgb * (1 - sa) + shirt_rgb * sa
    # roughness map (glTF metallic-roughness: G = roughness): matte hair and cotton
    rough = np.full(dmap.shape, 0.52, dtype=np.float32) * (1 - a[..., 0]) + 0.97 * a[..., 0]
    rough = rough * (1 - sa[..., 0]) + 0.92 * sa[..., 0]
    rough = box_blur(rough, 1)
    rmap = np.stack([np.zeros_like(rough), rough, np.zeros_like(rough), np.ones_like(rough)], -1)
    rimg = save_image('rider_skin_rough', rmap[::2, ::2], 'JPEG', 88, colorspace='Non-Color')
    out = np.concatenate([np.clip(rgb, 0, 1), np.ones_like(rgb[..., :1])], axis=2)
    return save_image('rider_skin', out, 'JPEG', 90), rimg


def jacket_texture(jacket, D):
    """Recolour the hooded jacket into an orange hard-shell (#e96a2d) and add a small plain white mark."""
    folder = D / 'clothes/elvs_hooded_sweat_jacket1'
    src = load_rgba(folder / 'hoodietex1.png', 1024)
    rgb = src[..., :3]
    lum = rgb.mean(axis=2)
    blue = np.clip((rgb[..., 2] - rgb[..., 0]) * 4.0, 0, 1)   # navy trims / cords
    detail = np.clip(0.88 + (lum - np.median(lum)) * 2.2, 0.70, 1.12)
    orange = np.array([0xe9 / 255, 0x6a / 255, 0x2d / 255], dtype=np.float32)   # sRGB, like the pixel buffer
    trim = orange * 0.62
    col = orange[None, None, :] * detail[..., None]
    col = col * (1 - blue[..., None]) + trim[None, None, :] * blue[..., None]
    # very light seam/zip lines where the source is brightest
    zipper = np.clip((lum - 0.35) * 3, 0, 1)[..., None]
    col = col * (1 - zipper) + np.array([0.30, 0.30, 0.30])[None, None, :] * zipper
    col = add_shoulder_mark(jacket, col)
    out = np.concatenate([np.clip(col, 0, 1), np.ones_like(col[..., :1])], axis=2)
    tex = save_image('rider_jacket', out, 'JPEG', 88)
    nrm = load_rgba(folder / 'normalshoodie.png', 1024)
    nrm[..., 3] = 1
    ntex = save_image('rider_jacket_normal', nrm, 'JPEG', 90, colorspace='Non-Color')
    return tex, ntex


def add_shoulder_mark(jacket, col):
    """Paint a small plain white half-disc on the back of the right shoulder (no text, no brand art)."""
    me = jacket.data
    uvl = me.uv_layers.active.data
    co = np.array([v.co[:] for v in me.vertices], dtype=np.float32)
    # rest pose: rider faces -Y, rider's right is -X. Target: upper back, right shoulder blade.
    rig = jacket.parent
    zt = rig.data.bones['neck_01'].head_local.z - 0.165
    target = np.array([-0.118, co[:, 1].max(), zt], dtype=np.float32)
    best, bestd = None, 1e9
    for p in me.polygons:
        if p.normal.y < 0.6:
            continue
        c = np.array(p.center[:])
        d = np.linalg.norm((c - target) * np.array([1, 0.2, 1]))
        if d < bestd:
            best, bestd = p, d
    if best is None:
        return col
    # local affine map world(x,z) -> uv using the triangle fan around the chosen face
    li = list(best.loop_indices)
    P = np.array([co[me.loops[i].vertex_index] for i in li])[:, [0, 2]]
    U = np.array([uvl[i].uv[:] for i in li])
    A = np.c_[P - P.mean(0)]
    J, *_ = np.linalg.lstsq(A, U - U.mean(0), rcond=None)   # 2x2: (dx,dz) -> (du,dv)
    c_uv = U.mean(0) + (np.array([target[0], target[2]]) - P.mean(0)) @ J
    h, w = col.shape[:2]
    Jinv = np.linalg.inv(J)
    r = 0.028   # 5.6 cm wide mark
    span = np.abs(np.array([r, r]) @ np.abs(J)).max() * 1.4
    u0, u1 = int((c_uv[0] - span) * w), int((c_uv[0] + span) * w) + 1
    v0, v1 = int((c_uv[1] - span) * h), int((c_uv[1] + span) * h) + 1
    us, vs = np.meshgrid((np.arange(u0, u1) + 0.5) / w, (np.arange(v0, v1) + 0.5) / h)
    d = np.stack([us - c_uv[0], vs - c_uv[1]], -1) @ Jinv    # -> world dx, dz
    dx, dz = d[..., 0], d[..., 1]
    rr = np.sqrt(dx * dx + dz * dz)
    edge = np.clip((r - rr) / 0.002, 0, 1) * np.clip((dz + 0.0) / 0.002, 0, 1)
    white = np.array([0.93, 0.93, 0.91], dtype=np.float32)
    # only paint texels that belong to jacket faces near the target (other UV islands share the box)
    near = [p for p in me.polygons if np.linalg.norm(np.array(p.center[:]) - np.array([target[0], p.center.y, target[2]])) < 0.07 and p.normal.y > 0.3]
    tuv = []
    for p in near:
        luv = [uvl[i].uv[:] for i in p.loop_indices]
        for k in range(1, len(luv) - 1):
            tuv.append([luv[0], luv[k], luv[k + 1]])
    cov, _ = rasterize_uv(np.array(tuv, dtype=np.float32), np.ones((len(tuv), 3), dtype=np.float32), h)
    sub = col[max(v0, 0):v1, max(u0, 0):u1]
    csub = cov[max(v0, 0):v1, max(u0, 0):u1]
    e = edge[(max(v0, 0) - v0):, (max(u0, 0) - u0):][:sub.shape[0], :sub.shape[1]] * csub[:sub.shape[0], :sub.shape[1]]
    e = e[..., None]
    sub[:] = sub * (1 - e) + white * e
    log('shoulder mark at uv', c_uv.round(3))
    return col


def simple_texture(path, size, fn, name, quality=86, alpha=False):
    src = load_rgba(path, size)
    out = fn(src)
    return save_image(name, out, 'PNG' if alpha else 'JPEG', quality)


# ------------------------------------------------------ bind-pose tools ---
def pose_to_rest(rig, meshes):
    """Freeze the current (constraint-driven) pose into the meshes and make it the armature rest pose."""
    ctx = bpy.context
    for o in ctx.view_layer.objects:
        o.select_set(False)
    ctx.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    for pb in rig.pose.bones:
        pb.bone.select = True
    bpy.ops.pose.visual_transform_apply()
    for pb in rig.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    bpy.ops.object.mode_set(mode='OBJECT')
    update()
    for o in meshes:
        mod = next(m for m in o.modifiers if m.type == 'ARMATURE')
        with ctx.temp_override(object=o, active_object=o):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    ctx.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in meshes:
        m = o.modifiers.new('Armature', 'ARMATURE')
        m.object = rig
        m.use_vertex_groups = True
        m.use_deform_preserve_volume = False
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    update()


def _adjacency(me):
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', e)
    return e.reshape(-1, 2)


def relax_folds(obj, rings=3, iters=12, thresh=0.25):
    """Find creases where the skinned cloth folded through itself (neighbouring faces nearly opposite)
    and relax them with umbrella smoothing. Operates on the bind-pose mesh."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    mask = np.zeros(len(bm.verts), bool)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.link_faces[0].normal.dot(e.link_faces[1].normal) < thresh:
            mask[e.verts[0].index] = mask[e.verts[1].index] = True
    bm.free()
    E = _adjacency(me)
    for _ in range(rings):
        grow = mask.copy()
        grow[E[:, 0][mask[E[:, 1]]]] = True
        grow[E[:, 1][mask[E[:, 0]]]] = True
        mask = grow
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    for _ in range(iters):
        acc = np.zeros_like(co)
        cnt = np.zeros(len(co))
        np.add.at(acc, E[:, 0], co[E[:, 1]])
        np.add.at(acc, E[:, 1], co[E[:, 0]])
        np.add.at(cnt, E[:, 0], 1)
        np.add.at(cnt, E[:, 1], 1)
        avg = acc / np.maximum(cnt, 1)[:, None]
        co[mask] = co[mask] * 0.4 + avg[mask] * 0.6
    me.vertices.foreach_set('co', co.ravel())
    me.update()
    log('relaxed %s: %d verts in folds' % (obj.name, int(mask.sum())))


def tuck_under(body, cloth, margin=0.006, depth=0.04):
    """Torso skin kept under the collar must never show through the jacket. Along each vertex normal:
    if the jacket surface lies just behind the vertex (it poked through) or less than margin in front
    of it, slide the vertex back along its own normal to sit margin behind the jacket. Bind pose."""
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(cloth, dg)
    gi = {g.name: g.index for g in body.vertex_groups}
    free = {gi[n] for n in gi if n in ('head', 'neck_01') or n.startswith(('hand_', 'index_', 'middle_', 'ring_', 'pinky_', 'thumb_', 'lowerarm'))}
    n = 0
    for v in body.data.vertices:
        if sum(g.weight for g in v.groups if g.group in free) > 0.3:
            continue
        nv = v.normal.copy()
        back = tree.ray_cast(v.co, -nv, depth)
        if back[0] is not None:
            v.co = back[0] - nv * margin
            n += 1
            continue
        front = tree.ray_cast(v.co, nv, margin)
        if front[0] is not None:
            v.co = v.co - nv * (margin - front[3])
            n += 1
            continue
        # grazing cases: nearest jacket point whose surface faces the same way as the skin
        loc, nrm, idx, dist = tree.find_nearest(v.co, 0.03)
        if loc is not None and nrm.dot(nv) > 0.5 and (v.co - loc).dot(nrm) > -margin:
            v.co = loc - nrm * margin
            n += 1
    body.data.update()
    log('tucked %d body verts under the %s' % (n, cloth.name))


def press_onto_saddle(cloth, rig, top, margin=0.002):
    """Where the trouser fabric sags into the saddle (bind pose), lift it onto the saddle surface."""
    M = rig.matrix_world
    Mi = M.inverted()
    n = 0
    for v in cloth.data.vertices:
        w = M @ v.co
        sz = saddle_surface_z(top, w.x, w.y)
        if sz is not None and w.z < sz + margin and w.z > sz - 0.08:
            w.z = sz + margin
            v.co = Mi @ w
            n += 1
    cloth.data.update()
    log('pressed %d trouser verts onto the saddle' % n)


def pose_reset(rig, remove_constraints=True):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
        if remove_constraints:
            for c in list(pb.constraints):
                pb.constraints.remove(c)
    update()


def mute_constraints(rig, mute):
    for pb in rig.pose.bones:
        for c in pb.constraints:
            c.mute = mute
    update()


def bw(rig, name, tail=False):
    pb = rig.pose.bones[name]
    return rig.matrix_world @ (pb.tail if tail else pb.head)


def rot_world(rig, name, axis, angle, pivot=None):
    pb = rig.pose.bones[name]
    Mw = rig.matrix_world
    M = Mw @ pb.matrix
    p = Vector(pivot) if pivot is not None else M.translation.copy()
    R = Matrix.Translation(p) @ Matrix.Rotation(angle, 4, Vector(axis).normalized()) @ Matrix.Translation(-p)
    pb.matrix = Mw.inverted() @ R @ M
    update()


def move_world(rig, name, delta):
    pb = rig.pose.bones[name]
    Mw = rig.matrix_world
    pb.matrix = Mw.inverted() @ Matrix.Translation(Vector(delta)) @ Mw @ pb.matrix
    update()


def hand_frame(rig, side):
    """Current world frame of a hand: f (wrist->middle knuckle), t (towards thumb side), n (palm normal)."""
    s = side
    wrist = bw(rig, 'hand_' + s)
    f = (bw(rig, 'middle_01_' + s) - wrist).normalized()
    t = (bw(rig, 'index_01_' + s) - bw(rig, 'pinky_01_' + s))
    t = (t - f * t.dot(f)).normalized()
    n = f.cross(t).normalized()
    thumb = bw(rig, 'thumb_03_' + s, tail=True) - wrist
    if thumb.dot(n) < 0:
        n = -n
    return wrist, f, t, n


def curl_fingers(rig, side):
    """Grip curl, applied in the rest pose (local rotations survive later hand orientation)."""
    s = side
    _, f, t, n = hand_frame(rig, s)
    curls = dict(index=(38, 52, 30), middle=(42, 55, 32), ring=(45, 56, 32), pinky=(48, 55, 30))
    for finger, angs in curls.items():
        for k, a in enumerate(angs, start=1):
            name = '%s_%02d_%s' % (finger, k, s)
            d = (bw(rig, name, True) - bw(rig, name)).normalized()
            axis = d.cross(n)
            if axis.length < 1e-6:
                continue
            rot_world(rig, name, axis, math.radians(a))
    # thumb: opposed, wrapping the inside of the hood body
    for k, a in ((1, 22), (2, 18), (3, 20)):
        name = 'thumb_%02d_%s' % (k, s)
        d = (bw(rig, name, True) - bw(rig, name)).normalized()
        rot_world(rig, name, d.cross(n), math.radians(a))


def saddle_surface_z(top, x, y):
    """Top surface height of the saddle model (see rider_bike.build_saddle) at world x,y (nan outside)."""
    L = 0.270
    u = 0.43 - (y - top.y) / L
    if u < 0 or u > 1:
        return None
    w = 0.018 + 0.056 * (1 / (1 + math.exp(-(u - 0.52) * 11))) - 0.006 * max(0, u - 0.93) / 0.07
    if abs(x) > w * 0.98:
        return None
    v = math.asin(max(-1, min(1, x / w))) / (math.pi / 2)
    base = 0.006 * math.sin(math.pi * u) - 0.012 * (1 - u) ** 3 + 0.010 * max(0, u - 0.8)
    z = base - 0.006 * v * v * (0.4 + u) - 0.010 * (1 - math.cos(v * math.pi / 2)) ** 1.5
    return top.z + z


class Rider:
    """Holds rest measurements and drives the seated pose."""

    def __init__(self, rig, body, pants, shoes):
        self.rig, self.body, self.pants, self.shoes = rig, body, pants, shoes
        rig.rotation_mode = 'XYZ'
        rig.rotation_euler = (0, 0, math.pi)          # rest faces -Y; rider faces +Y
        rig.location = (0, 0, 0)
        update()
        pose_reset(rig)
        B = rig.data.bones
        self.thigh = (B['thigh_l'].tail_local - B['thigh_l'].head_local).length
        self.calf = (B['calf_l'].tail_local - B['calf_l'].head_local).length
        self.foot = (B['foot_l'].tail_local - B['foot_l'].head_local).length
        # ankle relative to the ball joint in a flat-foot (standing) frame, world axes
        self.ankle_from_ball = {s: bw(rig, 'foot_' + s) - bw(rig, 'ball_' + s) for s in 'lr'}
        # shoe sole thickness under the ball joint
        co = evaluated_coords(shoes)
        self.sole = {}
        for s in 'lr':
            b = bw(rig, 'ball_' + s)
            near = co[(np.abs(co[:, 0] - b.x) < 0.03) & (np.abs(co[:, 1] - b.y) < 0.02)]
            self.sole[s] = b.z - near[:, 2].min()
        log('leg lengths thigh %.3f calf %.3f foot %.3f, sole under ball %.3f' % (self.thigh, self.calf, self.foot, self.sole['l']))
        # trouser vertices that form the seat (lower buttocks / crotch) in the rest pose
        hip = self.hip_mid()
        pc = evaluated_coords(body)
        pg, bg = body.vertex_groups['pelvis'].index, body.vertex_groups['body'].index
        pw = np.zeros(len(pc))
        for v in body.data.vertices:
            gw = {g.group: g.weight for g in v.groups}
            pw[v.index] = gw.get(pg, 0.0) if gw.get(bg, 0.0) > 0.5 else 0.0
        # buttock/sit-bone skin: behind and below the hip joints, carried by the pelvis (not the thighs)
        self.seat_idx = np.where((pc[:, 1] < hip.y + 0.03) & (pc[:, 2] < hip.z - 0.02) & (pc[:, 2] > hip.z - 0.17)
                                 & (np.abs(pc[:, 0]) < 0.11) & (pw > 0.5))[0]
        log('seat contact vertices', len(self.seat_idx))
        for s in 'lr':
            curl_fingers(rig, s)
        self.finger_pose = {pb.name: pb.rotation_quaternion.copy() for pb in rig.pose.bones if pb.name.split('_')[0] in ('index', 'middle', 'ring', 'pinky', 'thumb')}
        self.targets = {}
        self.reach_flex = 0.0   # extra upper-spine flex that brings the shoulders to the right distance from the hoods

    def hip_mid(self):
        return (bw(self.rig, 'thigh_l') + bw(self.rig, 'thigh_r')) / 2

    def upper_body(self, hip_target):
        rig = self.rig
        mute_constraints(rig, True)
        pose_reset(rig, remove_constraints=False)
        for n, q in self.finger_pose.items():
            rig.pose.bones[n].rotation_quaternion = q
        update()
        fwd = Vector((-1, 0, 0))   # rotation axis: +angle tips the top forward (+Y)
        rot_world(rig, 'pelvis', fwd, TORSO_TILT, pivot=self.hip_mid())
        for name, a in zip(('spine_01', 'spine_02', 'spine_03'), SPINE_FLEX):
            rot_world(rig, name, fwd, a + (self.reach_flex / 2 if name != 'spine_01' else 0.0))
        # shoulders: slightly protracted and relaxed (depressed)
        for s, sx in (('l', -1), ('r', 1)):
            c = 'clavicle_' + s
            rot_world(rig, c, Vector((0, 0, sx)), math.radians(12))
            d = (bw(rig, c, True) - bw(rig, c)).normalized()
            rot_world(rig, c, d.cross(Vector((0, 0, -1))), math.radians(6))
        # head up to look down the road
        rot_world(rig, 'neck_01', fwd, -math.radians(20) - self.reach_flex / 2)   # the eyes stay on the road
        rot_world(rig, 'head', fwd, -math.radians(22) - self.reach_flex / 2)
        # rough pre-pose for the arms so the IK starts close to the solution (elbows bent, out)
        for s, sx in (('l', -1), ('r', 1)):
            ua = 'upperarm_' + s
            d = (bw(rig, ua, True) - bw(rig, ua)).normalized()
            target = Vector((sx * 0.18, 0.62, -0.55)).normalized()
            q = d.rotation_difference(target)
            ax, ang = q.to_axis_angle()
            rot_world(rig, ua, ax, ang)
        move_world(rig, 'pelvis', hip_target - self.hip_mid())
        self.pelvis_matrix = rig.pose.bones['pelvis'].matrix.copy()
        self.hip_offset_x = (bw(rig, 'thigh_r') - self.hip_mid()).x
        mute_constraints(rig, False)

    def fit_reach(self, hip_target, hoods, elbow=ELBOW):
        """Flex the upper spine until the shoulders are as far from the wrist targets as a bent elbow of
        `elbow` allows. Arms locked straight make the elbow IK singular: its bend direction then flips back and
        forth as the pelvis rocks with the pedal stroke."""
        B = self.rig.data.bones
        l1 = (B['lowerarm_l'].head_local - B['upperarm_l'].head_local).length
        l2 = (B['hand_l'].head_local - B['lowerarm_l'].head_local).length
        want = math.sqrt(l1 * l1 + l2 * l2 - 2 * l1 * l2 * math.cos(elbow))

        def reach(flex):
            self.reach_flex = flex
            self.upper_body(hip_target)
            self.set_hand_targets(hoods)
            return sum((bw(self.rig, 'upperarm_' + s) - self.targets['WristTgt_' + s].location).length for s in 'lr') / 2
        lo, hi = 0.0, 0.5
        if reach(lo) > want:
            for _ in range(20):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if reach(mid) > want else (lo, mid)
        self.reach_flex = lo if lo == 0.0 else hi
        log('reach: upper-spine flex %.1f deg for a %.0f deg elbow (straight arm %.3f m, wanted %.3f m)' % (math.degrees(self.reach_flex), math.degrees(elbow), l1 + l2, want))

    def setup_constraints(self, pole_offsets):
        rig = self.rig
        col = bpy.context.scene.collection

        def empty(name):
            e = bpy.data.objects.get(name) or bpy.data.objects.new(name, None)
            if e.name not in col.objects:
                col.objects.link(e)
            e.empty_display_size = 0.03
            self.targets[name] = e
            return e
        for s, sx in (('l', -1), ('r', 1)):
            ank, ball, kp = empty('AnkleTgt_' + s), empty('BallTgt_' + s), empty('KneePole_' + s)
            c = rig.pose.bones['calf_' + s].constraints.new('IK')
            c.target, c.pole_target, c.chain_count = ank, kp, 2
            c.pole_angle = pole_offsets.get('leg', -math.pi / 2)
            c.use_stretch = False
            c.iterations = 800
            f = rig.pose.bones['foot_' + s].constraints.new('DAMPED_TRACK')
            f.target, f.track_axis = ball, 'TRACK_Y'
            wr, ep, hr = empty('WristTgt_' + s), empty('ElbowPole_' + s), empty('HandRot_' + s)
            c = rig.pose.bones['lowerarm_' + s].constraints.new('IK')
            c.target, c.pole_target, c.chain_count = wr, ep, 2
            c.pole_angle = pole_offsets.get('arm_' + s, 0.0)
            c.use_stretch = False
            c.iterations = 800
            cr = rig.pose.bones['hand_' + s].constraints.new('COPY_ROTATION')
            cr.target = hr
            cr.target_space = cr.owner_space = 'WORLD'
        for s in 'lr':
            for b in ('thigh_', 'calf_'):
                rig.pose.bones[b + s].ik_stretch = 0.0
            rig.pose.bones['calf_' + s].lock_ik_y = True
            rig.pose.bones['calf_' + s].lock_ik_z = True
            rig.pose.bones['lowerarm_' + s].lock_ik_y = False

    def set_hand_targets(self, hoods):
        """Wrist position + hand orientation for a hood grip. The desired frame (fingers forward/down,
        palm facing down and inward) is mapped from the hand's rest frame with matching handedness."""
        rig = self.rig
        mute_constraints(rig, True)
        for s, sx in (('l', -1), ('r', 1)):
            grip = hoods[s]
            f_des = Vector((-sx * 0.06, 0.86, -0.50)).normalized()
            n_des = Vector((-sx * 0.78, 0.08, -0.62))
            n_des = (n_des - f_des * n_des.dot(f_des)).normalized()
            wrist, f, t, n = hand_frame(rig, s)
            right_handed = f.cross(t).dot(n) > 0
            t_des = n_des.cross(f_des) if right_handed else f_des.cross(n_des)
            Rc = Matrix((f, t, n)).transposed()
            Rd = Matrix((f_des, t_des, n_des)).transposed()
            R = Rd @ Rc.inverted()
            Mb = rig.matrix_world @ rig.pose.bones['hand_' + s].matrix
            rot = (R @ Mb.to_3x3()).to_quaternion()
            e = self.targets['HandRot_' + s]
            e.rotation_mode = 'QUATERNION'
            e.rotation_quaternion = rot
            # palm contact ~6 cm along the hand and ~2 cm to the palm side of the bone line
            wrist_pos = grip - f_des * 0.068 - n_des * 0.026
            self.targets['WristTgt_' + s].location = wrist_pos
            sh = bw(rig, 'upperarm_' + s)
            self.targets['ElbowPole_' + s].location = (sh + wrist_pos) / 2 + Vector((sx * 0.35, -0.15, -0.25))
        mute_constraints(rig, False)

    def after_rest(self):
        """Re-create the IK rig on top of the new bind pose (riding pose at crank angle 0)."""
        rig = self.rig
        self.setup_constraints({})
        for s, sx in (('l', -1), ('r', 1)):
            e = self.targets['HandRot_' + s]
            e.rotation_mode = 'QUATERNION'
            mute_constraints(rig, True)
            e.rotation_quaternion = (rig.matrix_world @ rig.pose.bones['hand_' + s].matrix).to_quaternion()
            wrist = bw(rig, 'hand_' + s)
            self.targets['WristTgt_' + s].location = wrist
            elbow = bw(rig, 'lowerarm_' + s)
            sh = bw(rig, 'upperarm_' + s)
            mid = (sh + wrist) / 2
            self.targets['ElbowPole_' + s].location = elbow + (elbow - mid).normalized() * 0.4
            mute_constraints(rig, False)
        # knee/elbow positions of the bind pose itself (constraints off), which the IK must reproduce
        mute_constraints(rig, True)
        rest = {b: bw(rig, b) for b in ('calf_l', 'calf_r', 'lowerarm_l', 'lowerarm_r')}
        self.set_leg_targets(0.0)
        mute_constraints(rig, False)
        for key, b in (('leg_l', 'calf_l'), ('leg_r', 'calf_r'), ('arm_l', 'lowerarm_l'), ('arm_r', 'lowerarm_r')):
            err, ang = search_pole(rig, b, lambda: (bw(rig, b) - rest[b]).length, step=math.radians(15))
            log('pole %s: %.1f deg (knee/elbow drift %.2f mm)' % (key, math.degrees(ang), err * 1000))

    def foot_targets(self, phi, s):
        """Ball-of-foot and ankle positions for crank angle phi (0 = right crank up) on side s."""
        sx, ph = (1, phi) if s == 'r' else (-1, phi + math.pi)
        alpha = math.radians(14) - math.radians(9) * math.sin(ph)     # ankling: heel drops on the downstroke
        spindle = RB.BB + Vector((sx * 0.1365, RB.CRANK * math.sin(ph), RB.CRANK * math.cos(ph)))
        R = Matrix.Rotation(-alpha, 3, 'X')
        ball = spindle + R @ Vector((0, 0, 0.0085 + self.sole[s]))   # pedal top + shoe sole under the ball
        return ball, ball + R @ self.ankle_from_ball[s], alpha

    def set_leg_targets(self, phi):
        """Place the IK targets for crank angle phi. Returns the pedal pitch per side."""
        pitch = {}
        for s, sx in (('r', 1), ('l', -1)):
            ball, ankle, alpha = self.foot_targets(phi, s)
            self.targets['BallTgt_' + s].location = ball
            self.targets['AnkleTgt_' + s].location = ankle
            hip = bw(self.rig, 'thigh_' + s)
            self.targets['KneePole_' + s].location = Vector((sx * 0.11, hip.y + 0.9, hip.z + 0.1))
            pitch[s] = alpha
        return pitch

    def ankle_bdc(self):
        return self.foot_targets(math.pi, 'r')[1]

    def seat_gap(self, top):
        """Smallest vertical gap between the seat skin and the saddle top (negative = penetration)."""
        co = evaluated_coords(self.body)[self.seat_idx]
        gaps = []
        for x, y, z in co:
            sz = saddle_surface_z(top, x, y)
            if sz is not None:
                gaps.append(z - sz)
        return min(gaps) if gaps else 1.0


def search_pole(rig, bone, err, lo=-math.pi, hi=math.pi, step=math.radians(10)):
    """Pole angle of the IK constraint on `bone` minimising err(); coarse scan, then two refinements."""
    c = rig.pose.bones[bone].constraints['IK']
    best = None
    while step > math.radians(0.2):
        a = lo
        while a <= hi + 1e-9:
            c.pole_angle = a
            update()
            e = err()
            if best is None or e < best[0]:
                best = (e, a)
            a += step
        lo, hi, step = best[1] - step, best[1] + step, step / 8
    c.pole_angle = best[1]
    update()
    return best


def knee_plane_error(rider, s):
    """How far the knee sits out of the plane through hip, ankle and knee pole (0 = knee tracks the pole).
    A knee pointing away from the pole is rejected outright."""
    rig = rider.rig
    H, K, A = bw(rig, 'thigh_' + s), bw(rig, 'calf_' + s), bw(rig, 'foot_' + s)
    P = rider.targets['KneePole_' + s].location
    n = (A - H).cross(P - H).normalized()
    axis = (A - H).normalized()
    out = K - H - axis * (K - H).dot(axis)
    pole = P - H - axis * (P - H).dot(axis)
    return abs((K - H).dot(n)) + (1.0 if out.dot(pole) <= 0 else 0.0)


def choose_pole_angles(rider):
    """Find IK pole angles that make knees track their poles (forward, over the pedals) and elbows point
    outward/back. The legs use a fine search: an offset of even 20-30 deg swings the knees across the top tube."""
    rig = rider.rig
    best = {}
    def knee_error(s):
        e = 0.0
        for ph in (0.0, math.pi / 2, math.pi):
            rider.set_leg_targets(ph)
            update()
            e += knee_plane_error(rider, s)
        return e
    for s in 'lr':
        e, best['leg_' + s] = search_pole(rig, 'calf_' + s, lambda: knee_error(s))
        log('knee pole %s: %.1f deg, off-plane %.2f mm' % (s, math.degrees(best['leg_' + s]), e * 1000 / 3))
    rider.set_leg_targets(math.pi)
    update()
    for key, bones in (('arm_l', ('lowerarm_l',)), ('arm_r', ('lowerarm_r',))):
        scores = []
        for ang in (-math.pi / 2, 0.0, math.pi / 2, math.pi):
            for b in bones:
                rig.pose.bones[b].constraints['IK'].pole_angle = ang
            update()
            s = key[-1]
            sx = -1 if s == 'l' else 1
            mid = (bw(rig, 'upperarm_' + s) + bw(rig, 'lowerarm_' + s, True)) / 2
            d = bw(rig, 'lowerarm_' + s) - mid
            sc = d.x * sx * 0.6 - d.y * 0.3 - d.z * 0.4
            scores.append((sc, ang))
        best[key] = max(scores)[1]
        for b in bones:
            rig.pose.bones[b].constraints['IK'].pole_angle = best[key]
        update()
    log('pole angles', {k: round(math.degrees(v), 1) for k, v in best.items()})
    return best


# --------------------------------------------------------------- main ---
def main():
    reset_scene()
    base, rig, parts, D = build_human()
    # untouched copy of the skinned body, only used to find where the sit bones meet the saddle
    seat_proxy = base.copy()
    seat_proxy.data = base.data.copy()
    seat_proxy.name = '_SeatProxy'
    for m in list(seat_proxy.modifiers):
        if m.type == 'MASK':
            seat_proxy.modifiers.remove(m)
    bpy.context.scene.collection.objects.link(seat_proxy)
    hip_z = rig.data.bones['thigh_l'].head_local.z
    remove_hood_down(parts['jacket'], rig.data.bones['neck_01'].head_local.z)
    tighten(parts['jacket'], base, z_from=hip_z + 0.16, factor=0.6)
    smooth_weights(parts['jacket'], repeat=6)
    hood = add_hood(base, rig, parts['jacket'], parts['eyes'])   # needs the full skin for its weights
    finalize_body(base, [(parts['jacket'], 0.06), (parts['pants'], 0.05), (parts['shoes'], 0.04)])
    decimate(parts['jacket'], 0.55)
    with bpy.context.temp_override(active_object=parts['jacket'], object=parts['jacket'], selected_editable_objects=[parts['jacket'], hood]):
        bpy.ops.object.join()   # after decimation, so the hood keeps its clean grid
    for o in [base] + list(parts.values()):
        for m in list(o.modifiers):
            if m.type not in ('ARMATURE',):
                with bpy.context.temp_override(object=o, active_object=o):
                    bpy.ops.object.modifier_apply(modifier=m.name)
        for p in o.data.polygons:
            p.use_smooth = True

    # ------------------------------------------------ materials & textures
    log('textures')
    skin_tex, skin_rough = skin_texture(base, D, parts['brows'])
    skin = principled('Skin', tex=skin_tex, rough=0.55, ior=1.4, sss=0.05, spec=0.42, rough_tex=skin_rough)
    set_material(base, skin)
    strip_cornea(parts['eyes'], D / 'eyes/materials/brown_eye.png')
    jt, jn = jacket_texture(parts['jacket'], D)
    set_material(parts['jacket'], principled('Jacket shell', tex=jt, normal=jn, normal_strength=0.55, rough=0.5, spec=0.5))
    pm = read_mhmat(D / 'clothes/toigo_wool_pants/pants_wool.mhmat')
    pt = simple_texture(D / 'clothes/toigo_wool_pants' / pm['diffuseTexture'], 1024,
                        lambda a: np.concatenate([np.clip(0.13 + (a[..., :3].mean(2, keepdims=True) - 0.25) * 0.35, 0.07, 0.22) * np.array([1.0, 1.0, 1.04]), a[..., 3:] * 0 + 1], 2),
                        'rider_trousers')
    set_material(parts['pants'], principled('Trousers', tex=pt, rough=0.82, spec=0.35))

    def whiten(a):
        l = a[..., :3].mean(2, keepdims=True)
        rgb = np.clip(0.74 + (l - 0.5) * 0.28, 0.45, 0.92) * np.array([1.0, 1.0, 0.985])
        return np.concatenate([rgb, np.ones_like(l)], 2)
    st = simple_texture(D / 'clothes/shoes05/shoes05_diffuse.png', 1024, whiten, 'rider_shoes')
    set_material(parts['shoes'], principled('Sneakers', tex=st, rough=0.62, spec=0.4))
    et = simple_texture(D / 'eyes/materials/brown_eye.png', 512, lambda a: np.concatenate([a[..., :3] * 0.8, np.ones_like(a[..., :1])], 2), 'rider_eye')
    set_material(parts['eyes'], principled('Eyes', tex=et, rough=0.12, ior=1.38, spec=0.6))

    def tint(a, c):
        out = a.copy()
        out[..., :3] = np.array(c)[None, None, :] * (0.8 + 0.2 * a[..., :3].mean(2, keepdims=True))
        return out
    bt = simple_texture(D / 'eyebrows/eyebrow010/eyebrow010.png', 256, lambda a: tint(a, (0.07, 0.06, 0.055)), 'rider_brows', alpha=True)
    set_material(parts['brows'], principled('Eyebrows', tex=bt, alpha_tex=True, rough=0.7))
    lt = simple_texture(D / 'eyelashes/eyelashes01/eyelashes01.png', 256, lambda a: tint(a, (0.05, 0.045, 0.04)), 'rider_lashes', alpha=True)
    set_material(parts['lashes'], principled('Eyelashes', tex=lt, alpha_tex=True, rough=0.7))

    # ------------------------------------------------ pose on the bike
    log('posing')
    rider = Rider(rig, seat_proxy, parts['pants'], parts['shoes'])
    hoods = {'l': Vector((-RB.HOOD_GRIP.x, RB.HOOD_GRIP.y, RB.HOOD_GRIP.z)), 'r': RB.HOOD_GRIP.copy()}
    rider.setup_constraints({})
    # 1) seat offset with a nominal saddle, 2) solve saddle height for the knee angle, 3) refine
    h = 0.70
    offset = Vector((0, -0.045, 0.085))
    for it in range(3):
        top = RB.saddle_top(h)
        hip = top + offset
        rider.upper_body(hip)
        rider.set_leg_targets(math.pi)
        rider.set_hand_targets(hoods)
        update()
        if it == 0:
            choose_pole_angles(rider)
        gap = rider.seat_gap(top)
        offset.z -= gap + 0.008          # ~8 mm of soft tissue compressed on the saddle
        a_bdc = rider.ankle_bdc()
        want = math.sqrt(rider.thigh ** 2 + rider.calf ** 2 - 2 * rider.thigh * rider.calf * math.cos(KNEE_BDC))
        lo, hi = 0.55, 0.85
        for _ in range(40):
            mid = (lo + hi) / 2
            hj = RB.saddle_top(mid) + offset + Vector((rider.hip_offset_x, 0, 0))
            if (hj - a_bdc).length < want:
                lo = mid
            else:
                hi = mid
        log('iter %d: seat gap %.4f -> offset %s, saddle height %.3f' % (it, gap, tuple(round(v, 3) for v in offset), mid))
        h = mid
    SADDLE_H = h
    top = RB.saddle_top(SADDLE_H)
    log('saddle height (BB to saddle top along the seat tube) %.3f m' % SADDLE_H)
    hip = top + offset
    rider.fit_reach(hip, hoods)
    rider.upper_body(hip)
    rider.set_hand_targets(hoods)
    rider.set_leg_targets(0.0)
    update()
    bpy.data.objects.remove(seat_proxy, do_unlink=True)

    # ------------------------------------------------ riding pose becomes the bind pose; clean the cloth there
    log('pose -> rest')
    meshes = [base] + list(parts.values())
    pose_to_rest(rig, meshes)
    relax_folds(parts['jacket'], rings=2, iters=6, thresh=-0.3)
    relax_folds(parts['pants'], rings=1, iters=4, thresh=-0.3)
    taubin(parts['jacket'], iters=10)
    cull_covered(parts['pants'], parts['jacket'])
    press_onto_saddle(parts['pants'], rig, top)
    tuck_under(base, parts['jacket'])
    rider.after_rest()

    # ------------------------------------------------ bike
    log('bike')
    M = RB.bike_materials()
    nodes = RB.assemble_bike(M, SADDLE_H)
    update()

    # ------------------------------------------------ bake one crank revolution
    log('baking')
    scn = bpy.context.scene
    crank, pr, pl = nodes['crank'], nodes['pedal_r'], nodes['pedal_l']
    for o in (crank, pr, pl):
        o.rotation_mode = 'XYZ'
    for f in range(FRAMES + 1):
        phi = 2 * math.pi * f / FRAMES
        scn.frame_set(f)
        pitch = rider.set_leg_targets(phi)
        for e in rider.targets.values():
            e.keyframe_insert('location', frame=f)
        for s in 'lr':
            rider.targets['HandRot_' + s].keyframe_insert('rotation_quaternion', frame=f)
        crank.rotation_euler = (-phi, 0, 0)
        crank.keyframe_insert('rotation_euler', frame=f)
        pr.rotation_euler = (phi - pitch['r'], 0, 0)
        pr.keyframe_insert('rotation_euler', frame=f)
        pl.rotation_euler = (phi - pitch['l'], 0, 0)
        pl.keyframe_insert('rotation_euler', frame=f)
        # subtle pelvis rock with the pedal stroke (hands stay on the hoods through the arm IK)
        pb = rig.pose.bones['pelvis']
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        update()
        rot_world(rig, 'pelvis', Vector((0, 1, 0)), 0.014 * math.sin(phi), pivot=rider.hip_mid())
        pb.keyframe_insert('location', frame=f)
        pb.keyframe_insert('rotation_quaternion', frame=f)
    for o in [crank, pr, pl] + list(rider.targets.values()):
        if o.animation_data and o.animation_data.action:
            for fc in o.animation_data.action.fcurves:
                for k in fc.keyframe_points:
                    k.interpolation = 'LINEAR'
    bpy.context.view_layer.objects.active = rig
    for o in bpy.context.view_layer.objects:
        o.select_set(o == rig)
    bpy.ops.object.mode_set(mode='POSE')
    for pb in rig.pose.bones:
        pb.bone.select = True
    bpy.ops.nla.bake(frame_start=0, frame_end=FRAMES, step=1, only_selected=True, visual_keying=True,
                     clear_constraints=True, clear_parents=False, use_current_action=True, clean_curves=False,
                     bake_types={'POSE'})
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.animation_data.action.name = 'Pedal'
    crank.animation_data.action.name = 'PedalCrank'
    pr.animation_data.action.name = 'PedalR'
    pl.animation_data.action.name = 'PedalL'
    for e in list(rider.targets.values()):
        act = e.animation_data.action if e.animation_data else None
        bpy.data.objects.remove(e, do_unlink=True)
        if act:
            bpy.data.actions.remove(act)
    scn.frame_set(0)

    # ------------------------------------------------ checks
    report = {'saddle_height': round(SADDLE_H, 4)}
    foot_err, hand_drift = [], []
    wrist0 = {}
    for f in range(0, FRAMES + 1, 2):
        scn.frame_set(f)
        phi = 2 * math.pi * f / FRAMES
        for s in 'lr':
            ball, _, _ = rider.foot_targets(phi, s)
            foot_err.append((bw(rig, 'ball_' + s) - ball).length)
            w = bw(rig, 'hand_' + s)
            wrist0.setdefault(s, w)
            hand_drift.append((w - wrist0[s]).length)
    report['foot_ik_error_mm'] = round(1000 * max(foot_err), 2)
    report['wrist_drift_mm'] = round(1000 * max(hand_drift), 2)
    scn.frame_set(0)
    log('check', report)

    # ------------------------------------------------ export
    rider_meshes = [base] + list(parts.values())
    for o in rider_meshes:
        log('  tris %-10s %6d' % (o.name, tri_count(o)))
    tri_r = sum(tri_count(o) for o in rider_meshes)
    bike_meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o not in rider_meshes]
    tri_b = sum(tri_count(o) for o in bike_meshes)
    log('triangles rider %d, bike %d' % (tri_r, tri_b))
    report.update(tris_rider=tri_r, tris_bike=tri_b)
    export_glb()
    report['glb_bytes'] = (OUT / 'rider.glb').stat().st_size
    (WORK / 'report.json').write_text(json.dumps(report, indent=1))
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'rider.blend'))
    log('report', report)
    if '--render' in ARGS:
        render_previews()


def export_glb():
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / 'rider.glb'), export_format='GLB', use_selection=False,
        export_apply=False, export_yup=True, export_texcoords=True, export_normals=True,
        export_tangents=False, export_materials='EXPORT', export_image_format='AUTO', export_jpeg_quality=86,
        export_cameras=False, export_lights=False, export_extras=False,
        export_copyright='Rider: MakeHuman/MPFB CC0 assets; jacket "Hooded sweat jacket" by Elvaerwyn (CC-BY), modified. '
                         'Bike: original procedural model. See SOURCE.md.',
        export_skins=True, export_def_bones=False, export_morph=False,
        export_animations=True, export_animation_mode='ACTIVE_ACTIONS', export_nla_strips_merged_animation_name='Pedal',
        export_force_sampling=True, export_frame_range=True, export_optimize_animation_size=False,
        export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
        export_draco_position_quantization=14, export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12, export_draco_generic_quantization=12)
    log('exported', OUT / 'rider.glb')


def render_previews(frame=6):
    """Cycles stills (GPU/OptiX when available): side, three-quarter front, upper-body close-up."""
    scn = bpy.context.scene
    scn.frame_set(frame)
    scn.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for dev in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                scn.cycles.device = 'GPU'
                break
        except TypeError:
            continue
    scn.cycles.samples = 256
    scn.cycles.use_denoising = True
    scn.render.resolution_x, scn.render.resolution_y = 1600, 1000
    scn.render.image_settings.file_format = 'JPEG'
    scn.render.image_settings.quality = 90
    scn.view_settings.view_transform = 'AgX'
    scn.view_settings.look = 'AgX - Punchy'
    scn.view_settings.exposure = -0.9
    world = bpy.data.worlds.new('Sky')
    scn.world = world
    world.use_nodes = True
    nt = world.node_tree
    sky = nt.nodes.new('ShaderNodeTexSky')
    sky.sky_type = 'NISHITA'
    sky.sun_elevation = math.radians(38)
    sky.sun_rotation = math.radians(243)
    sky.air_density = 1.2
    sky.dust_density = 1.5
    nt.links.new(sky.outputs['Color'], nt.nodes['Background'].inputs['Color'])
    nt.nodes['Background'].inputs['Strength'].default_value = 0.22
    sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN'))
    scn.collection.objects.link(sun)
    sun.data.energy = 3.6
    sun.data.angle = math.radians(1.5)
    sun.data.color = (1.0, 0.95, 0.88)
    sun.rotation_euler = (math.radians(42), 0, math.radians(153))   # from the front-right, above
    # asphalt-like ground with a painted edge line
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    ground = bpy.context.object
    gm = bpy.data.materials.new('Road')
    gm.use_nodes = True
    g = gm.node_tree
    bsdf = g.nodes['Principled BSDF']
    noise = g.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 180
    noise.inputs['Detail'].default_value = 8
    ramp = g.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.055, 0.056, 0.058, 1)
    ramp.color_ramp.elements[1].color = (0.13, 0.13, 0.125, 1)
    g.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    g.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bump = g.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.25
    g.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    g.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.9
    ground.data.materials.append(gm)
    line = bpy.data.materials.new('Line')
    line.use_nodes = True
    line.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.75, 0.74, 0.7, 1)
    line.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.7
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-0.95, 0, 0.001))
    ln = bpy.context.object
    ln.scale = (0.12, 40, 1)
    ln.data.materials.append(line)
    cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    scn.collection.objects.link(cam)
    scn.camera = cam
    shots = dict(
        side=((3.9, 0.25, 1.05), (0, 0.02, 0.82), 50, None),
        front=((2.35, 3.0, 1.45), (0.0, 0.1, 0.86), 50, None),
        closeup=((0.82, 1.2, 1.74), (0.0, 0.2, 1.42), 70, 2.8),
    )
    for name, (loc, tgt, lens, fstop) in shots.items():
        cam.location = loc
        cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        cam.data.dof.use_dof = fstop is not None
        if fstop:
            cam.data.dof.focus_distance = (Vector(tgt) - Vector(loc)).length
            cam.data.dof.aperture_fstop = 2.8
        scn.render.filepath = str(OUT / ('preview-%s.jpg' % name))
        bpy.ops.render.render(write_still=True)
        log('rendered', scn.render.filepath)


if __name__ == '__main__':
    main()
