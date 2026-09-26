"""Build web-ready ride props (Draco GLB) from cached Poly Haven CC0 sources.

    python3 scripts/modeling/fetch_props.py            # once, needs network
    ./scripts/blender --background --factory-startup \
        --python scripts/modeling/prepare_props.py [-- name ...]

Writes static/ride/models/props/<name>.glb and SOURCE.md.  Names:
street_tree_01..03, street_lamp, park_bench, planter,
goods_cardboard_box, goods_crate, goods_cans, goods_cleaner.

Conventions: metres, +Y up in glTF (Blender +Z), origin at the base centre on
the ground.  Trees are rebuilt as a decimated bark mesh plus leaf-cluster
cards: clusters of the original leaves are path-traced (Cycles, white
ambient light -> albedo x occlusion, and a camera-space normal pass) into a
2x2 atlas, then cards are scattered where the original leaves are, with
normals pointing out of the crown.  Textures are re-encoded afterwards by
glb_textures.py (JPEG; the leaf atlas is a 256-colour PNG because it needs
alpha).
"""
import bpy, json, math, os, subprocess, sys, time
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.tools/assets-cache/polyhaven'
WORK = ROOT / '.tools/assets-cache/work'
OUT = ROOT / 'static/ride/models/props'
STATS = WORK / 'stats.json'
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)


def log(*a):
    print('[props]', *a, flush=True)


# ---------------------------------------------------------------- basics
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_asset(pid):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(next((CACHE / pid / '1k').glob('*.gltf'))))
    return [o for o in bpy.data.objects if o not in before]


def tex_path(pid, part):
    return str(next((CACHE / pid / '1k' / 'textures').glob(f'{pid}_{part}_1k.*')))


def tri_count(objs):
    n = 0
    for o in objs:
        if o.type != 'MESH':
            continue
        lt = np.empty(len(o.data.polygons), np.int32)
        o.data.polygons.foreach_get('loop_total', lt)
        n += int((lt - 2).sum())
    return n


def activate(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def join(objs, name):
    ms = [o for o in objs if o.type == 'MESH']
    others = [o.name for o in objs if o.type != 'MESH']
    for o in ms:  # bake parent chains into the mesh before joining
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    bpy.ops.object.select_all(action='DESELECT')
    for o in ms:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = o.data.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for n in others:
        if n in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[n])
    return o


def clear_custom_normals(o):
    activate(o)
    if o.data.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()


def decimate(o, target):
    n = tri_count([o])
    if n <= target:
        return n
    clear_custom_normals(o)
    m = o.modifiers.new('dec', 'DECIMATE')
    m.decimate_type = 'COLLAPSE'
    m.ratio = target / n
    m.use_collapse_triangulate = True
    activate(o)
    bpy.ops.object.modifier_apply(modifier=m.name)
    return tri_count([o])


def smooth(o, angle=None):
    activate(o)
    if angle is None:
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))


def ground(o, scale=1.0, xy_center=None):
    """Scale, then move so the base centre sits on the origin (Blender Z up)."""
    if scale != 1.0:
        o.data.transform(Matrix.Scale(scale, 4))
    co = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(0), co.max(0)
    c = (lo + hi) / 2 if xy_center is None else np.array([*xy_center, 0])
    o.data.transform(Matrix.Translation((-float(c[0]), -float(c[1]), -float(lo[2]))))
    o.data.update()
    return (hi - lo).tolist()


def dims(objs):
    lo = np.full(3, 1e9); hi = np.full(3, -1e9)
    for o in objs:
        for v in o.bound_box:
            w = np.array(o.matrix_world @ Vector(v))
            lo = np.minimum(lo, w); hi = np.maximum(hi, w)
    return (hi - lo).round(3).tolist()


def export(objs, name, max_tex=1024, rules=(), note=''):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    path = OUT / f'{name}.glb'
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', use_selection=True, export_apply=True,
        export_yup=True, export_image_format='AUTO', export_materials='EXPORT',
        export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
        export_draco_position_quantization=14, export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12, export_cameras=False, export_lights=False,
        export_animations=False, export_extras=False, export_tangents=False,
        export_copyright='CC0 1.0 - derived from Poly Haven assets, see SOURCE.md')
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
    cmd = ['python3', str(ROOT / 'scripts/modeling/glb_textures.py'), str(path), '--max', str(max_tex)]
    for r in rules:
        cmd += ['--rule', r]
    subprocess.run(cmd, check=True, env=env)
    stats = json.loads(STATS.read_text()) if STATS.exists() else {}
    stats[name] = {'tris': tri_count(objs), 'bytes': path.stat().st_size, 'size_m': dims(objs), 'note': note}
    STATS.write_text(json.dumps(stats, indent=1))
    log(f'{name}.glb', stats[name])


# ---------------------------------------------------------------- materials
def principled(name, color=None, normal=None, rough=0.9, alpha=None, alpha_clip=True, normal_strength=1.0,
               metallic=0.0, color_img=None, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Specular IOR Level'].default_value = spec
    tex = None
    if color or color_img:
        tex = nt.nodes.new('ShaderNodeTexImage')
        tex.image = color_img or bpy.data.images.load(color, check_existing=True)
        nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    if normal:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(normal, check_existing=True)
        t.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.inputs['Strength'].default_value = normal_strength
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if alpha == 'tex' and tex is not None:
        src = tex.outputs['Alpha']
    elif isinstance(alpha, str) and alpha != 'tex':
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(alpha, check_existing=True)
        t.image.colorspace_settings.name = 'Non-Color'
        src = t.outputs['Color']
    else:
        src = None
    if src is not None:
        if alpha_clip:  # exporter maps Math:Round -> alphaMode MASK, cutoff 0.5
            r = nt.nodes.new('ShaderNodeMath')
            r.operation = 'ROUND'
            nt.links.new(src, r.inputs[0])
            src = r.outputs[0]
        nt.links.new(src, b.inputs['Alpha'])
    return m


def bsdf(m):
    return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


# ---------------------------------------------------------------- mesh arrays
def arrays(o):
    me = o.data
    nv, nf, nl = len(me.vertices), len(me.polygons), len(me.loops)
    A = {}
    A['co'] = np.empty(nv * 3, np.float32); me.vertices.foreach_get('co', A['co']); A['co'] = A['co'].reshape(-1, 3)
    A['lv'] = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', A['lv'])
    A['ls'] = np.empty(nf, np.int32); me.polygons.foreach_get('loop_start', A['ls'])
    A['lt'] = np.empty(nf, np.int32); me.polygons.foreach_get('loop_total', A['lt'])
    A['mi'] = np.empty(nf, np.int32); me.polygons.foreach_get('material_index', A['mi'])
    A['area'] = np.empty(nf, np.float32); me.polygons.foreach_get('area', A['area'])
    A['ctr'] = np.empty(nf * 3, np.float32); me.polygons.foreach_get('center', A['ctr']); A['ctr'] = A['ctr'].reshape(-1, 3)
    A['uv'] = np.empty(nl * 2, np.float32); me.uv_layers[0].data.foreach_get('uv', A['uv']); A['uv'] = A['uv'].reshape(-1, 2)
    return A


def face_components(A):
    """Connected-component label per face (min-label propagation + pointer jumping)."""
    nf, nv = len(A['ls']), len(A['co'])
    fol = np.repeat(np.arange(nf), A['lt'])
    lv = A['lv'].astype(np.int64)
    lab = np.arange(nv)
    for _ in range(500):
        fmin = np.full(nf, nv); np.minimum.at(fmin, fol, lab[lv])
        new = lab.copy(); np.minimum.at(new, lv, fmin[fol])
        new = new[new]; new = new[new]
        if np.array_equal(new, lab):
            break
        lab = new
    return fmin


def submesh(name, A, faces, mats, mat_of_face=None):
    faces = np.asarray(faces)
    tots = A['lt'][faces]; starts = A['ls'][faces]
    loops = np.repeat(starts - np.concatenate([[0], np.cumsum(tots)[:-1]]), tots) + np.arange(tots.sum())
    lv = A['lv'][loops]
    used, inv = np.unique(lv, return_inverse=True)
    polys = np.split(inv, np.cumsum(tots)[:-1])
    me = bpy.data.meshes.new(name)
    me.from_pydata(A['co'][used].tolist(), [], [p.tolist() for p in polys])
    me.uv_layers.new(name='UVMap').data.foreach_set('uv', A['uv'][loops].ravel())
    for m in mats:
        me.materials.append(m)
    if mat_of_face is not None:
        me.polygons.foreach_set('material_index', np.asarray(mat_of_face, np.int32))
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


# ---------------------------------------------------------------- leaf atlas
def setup_cycles(res):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for kind in ('OPTIX', 'CUDA'):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                gpus = [d for d in prefs.devices if d.type == kind]
                if gpus:
                    for d in prefs.devices:
                        d.use = d.type == kind
                    sc.cycles.device = 'GPU'
                    break
            except TypeError:
                continue
    except Exception as e:  # CPU fallback is fine, just slower
        log('GPU setup failed, using CPU', e)
    sc.cycles.samples = 96
    sc.cycles.use_denoising = False
    sc.cycles.transparent_max_bounces = 256
    sc.cycles.max_bounces = 6
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.filter_size = 1.2
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.image_settings.color_depth = '8'
    w = bpy.data.worlds.new('white')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (1, 1, 1, 1)
    bg.inputs['Strength'].default_value = 1.0
    sc.world = w
    vl = sc.view_layers[0]
    vl.use_pass_normal = True
    vl.use_pass_diffuse_color = True
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')
    comp = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(rl.outputs['Image'], comp.inputs['Image'])
    fo = nt.nodes.new('CompositorNodeOutputFile')
    fo.format.file_format = 'OPEN_EXR'
    fo.format.color_mode = 'RGBA'
    fo.format.color_depth = '32'
    fo.file_slots[0].path = 'normal_'
    fo.file_slots.new('combined_')
    fo.file_slots.new('albedo_')
    nt.links.new(rl.outputs['Normal'], fo.inputs[0])
    nt.links.new(rl.outputs['Image'], fo.inputs[1])
    nt.links.new(rl.outputs['DiffCol'], fo.inputs[2])
    return fo


def load_pixels(path):
    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)  # rows bottom-up, same as Blender UV v


def dilate(rgb, mask, iters=24):
    rgb = rgb.copy(); m = mask.astype(np.float32)
    for _ in range(iters):
        acc = np.zeros_like(rgb); w = np.zeros_like(m)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            acc += np.roll(np.roll(rgb * m[..., None], dy, 0), dx, 1)
            w += np.roll(np.roll(m, dy, 0), dx, 1)
        new = (w > 0) & (m == 0)
        if not new.any():
            break
        rgb[new] = acc[new] / w[new][:, None]
        m[new] = 1
    fill = rgb[mask].mean(0) if mask.any() else np.array([0.5, 0.5, 1.0])
    rgb[m == 0] = fill
    return rgb


def look_basis(d):
    """Camera basis looking along -d (d points from subject to camera), world-up aligned."""
    z = d / np.linalg.norm(d)
    up = np.array([0, 0, 1.0])
    x = np.cross(up, z)
    if np.linalg.norm(x) < 1e-3:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return x, y, z


def render_tiles(name, leafA, leaf_comp, comp_ctr, twigA, twig_faces, seeds, dirs, radius, render_mats, tile_res=512):
    """Path-trace one leaf cluster per seed; returns atlas paths and per-tile world extents."""
    fo = setup_cycles(tile_res)
    tdir = WORK / name / 'tiles'
    tdir.mkdir(parents=True, exist_ok=True)
    fo.base_path = str(tdir)
    cam_data = bpy.data.cameras.new('tilecam'); cam_data.type = 'ORTHO'; cam_data.clip_end = 200
    cam = bpy.data.objects.new('tilecam', cam_data); bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    comp_of_face = leaf_comp
    tiles = []
    for t, (p, d) in enumerate(zip(seeds, dirs)):
        dist = np.linalg.norm(comp_ctr[1] - p, axis=1)
        near = np.where(dist < radius * (0.7 + 0.3 * np.random.default_rng(t).random(len(dist))))[0]
        keep = np.isin(comp_of_face, comp_ctr[0][near])
        objs = [submesh(f'tile{t}_leaves', leafA, np.where(keep)[0], [render_mats[0]])]
        tf = twig_faces[np.linalg.norm(twigA['ctr'][twig_faces] - p, axis=1) < radius * 0.9]
        if len(tf):
            objs.append(submesh(f'tile{t}_twigs', twigA, tf, [render_mats[1]]))
        x, y, z = look_basis(d)
        vs = []
        for o in objs:
            c = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get('co', c)
            vs.append(c.reshape(-1, 3))
        vs = np.concatenate(vs) - p
        u, w = vs @ x, vs @ y
        cu, cw = (u.max() + u.min()) / 2, (w.max() + w.min()) / 2
        ext = max(u.max() - u.min(), w.max() - w.min()) * 1.1  # transparent gutter for mipmaps
        cam_data.ortho_scale = ext
        cam.matrix_world = Matrix(np.array([[*x, 0], [*y, 0], [*z, 0], [0, 0, 0, 1]]).T.tolist())
        cam.location = Vector(p + x * cu + y * cw + z * 30)
        bpy.context.scene.frame_current = 1
        bpy.ops.render.render(write_still=False)
        for k in ('normal', 'combined', 'albedo'):
            (tdir / f'{k}_0001.exr').replace(tdir / f'{k}_{t}.exr')
        comb = load_pixels(tdir / f'combined_{t}.exr')
        alb = load_pixels(tdir / f'albedo_{t}.exr')[..., :3]
        nw = load_pixels(tdir / f'normal_{t}.exr')[..., :3]
        # colour = albedo x softened occlusion (white-sky render / albedo), straight alpha, sRGB
        a_ = np.clip(comb[..., 3], 0, 1)
        occ = np.clip(comb[..., :3].sum(-1) / np.maximum(alb.sum(-1), 1e-5), 0, 1)
        lin = alb / np.maximum(a_, 0.02)[..., None] * (0.5 + 0.5 * occ)[..., None]
        lin = np.clip(lin, 0, 1)
        srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)
        col = np.concatenate([srgb, a_[..., None]], -1)
        # world -> camera space (tangent space of a card facing the camera, OpenGL +Y)
        nc = np.stack([nw @ x, nw @ y, nw @ z], -1)
        nc[nc[..., 2] < 0] *= -1
        nc /= np.maximum(np.linalg.norm(nc, axis=-1, keepdims=True), 1e-6)
        mask = col[..., 3] > 0.5
        rgb = dilate(col[..., :3], col[..., 3] > 0.02)
        nrm = dilate(nc * 0.5 + 0.5, mask)
        tiles.append({'rgb': rgb, 'a': col[..., 3], 'nrm': nrm, 'ext': float(ext),
                      'coverage': float(mask.mean())})
        for o in objs:
            bpy.data.meshes.remove(o.data)
        log(f'  tile {t}: {len(near)} leaf clusters, {len(tf)} twig faces, ext {ext:.2f} m, coverage {mask.mean():.2f}')
    # 2x2 atlas, bottom-up rows like Blender pixels
    n = tile_res
    col = np.zeros((2 * n, 2 * n, 4), np.float32)
    nor = np.zeros((2 * n, 2 * n, 4), np.float32); nor[..., 3] = 1
    for t, tl in enumerate(tiles):
        r0, c0 = (t // 2) * n, (t % 2) * n
        col[r0:r0 + n, c0:c0 + n, :3] = tl['rgb']
        col[r0:r0 + n, c0:c0 + n, 3] = np.clip(tl['a'] * 1.15, 0, 1)  # keeps coverage in mips
        nor[r0:r0 + n, c0:c0 + n, :3] = tl['nrm']
    paths = []
    for label, arr, alpha in (('leaves_atlas', col, True), ('leaves_atlas_nor', nor, False)):
        img = bpy.data.images.new(f'{name}_{label}', 2 * n, 2 * n, alpha=alpha)
        if not alpha:
            img.colorspace_settings.name = 'Non-Color'
        img.pixels.foreach_set(arr.ravel())
        path = WORK / name / f'{label}.png'
        img.filepath_raw = str(path)
        img.file_format = 'PNG'
        img.save()
        paths.append(path)
    bpy.data.objects.remove(cam)
    return paths, tiles


# ---------------------------------------------------------------- trees
def build_tree(name, pid, height, xy=1.0, cards=2600, bark_tris=3600, branch_rmin=0.02, trunk_rmin=0.01,
               cell_k=1.0, size_k=1.0, radius_k=1.5, seed=1):
    t0 = time.time()
    reset()
    src = join(import_asset(pid), 'src')
    co = np.empty(len(src.data.vertices) * 3, np.float32); src.data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    s = height / (co[:, 2].max() - co[:, 2].min())
    src.data.transform(Matrix.Diagonal((s * xy, s * xy, s, 1)))
    A = arrays(src)
    names = [m.name for m in src.data.materials]
    leaf_i = [i for i, n in enumerate(names) if 'leaves' in n]
    branch_i = [i for i, n in enumerate(names) if 'branch' in n]
    trunk_i = [i for i in range(len(names)) if i not in leaf_i + branch_i]
    log(name, 'materials', names, 'scale', round(s, 3))
    # base centre = trunk vertices near the ground
    trunk_faces = np.where(np.isin(A['mi'], trunk_i))[0]
    z0 = A['ctr'][:, 2].min()
    low = trunk_faces[A['ctr'][trunk_faces, 2] < z0 + 0.4]
    base = np.average(A['ctr'][low, :2], axis=0, weights=A['area'][low])
    A['co'][:, :2] -= base; A['ctr'][:, :2] -= base
    A['co'][:, 2] -= z0; A['ctr'][:, 2] -= z0

    comp = face_components(A)
    # per-component stats
    uc, inv = np.unique(comp, return_inverse=True)
    carea = np.bincount(inv, weights=A['area'])
    cctr = np.stack([np.bincount(inv, weights=A['ctr'][:, k] * A['area']) for k in range(3)], 1) / np.maximum(carea, 1e-12)[:, None]
    lo = np.full((len(uc), 3), 1e9); hi = np.full((len(uc), 3), -1e9)
    for k in range(3):
        np.minimum.at(lo[:, k], inv, A['ctr'][:, k]); np.maximum.at(hi[:, k], inv, A['ctr'][:, k])
    cext = (hi - lo).max(1)
    crad = carea / (2 * np.pi * np.maximum(cext, 1e-3))
    cmat = np.zeros(len(uc), np.int32); cmat[inv] = A['mi']

    # ---- bark: trunk + thick branches, decimated
    flat_ground = ((hi[:, 2] - lo[:, 2]) < 0.2) & (hi[:, 2] < 0.25)  # root skirts / rock bases from the scans
    keep_c = ((np.isin(cmat, trunk_i) & (crad >= trunk_rmin)) | (np.isin(cmat, branch_i) & (crad >= branch_rmin))) & ~flat_ground
    bark_faces = np.where(keep_c[inv] & ~np.isin(A['mi'], leaf_i))[0]
    bark_mat = principled('bark', tex_path(pid, 'diff' if pid != 'jacaranda_tree' else 'trunk_diff'),
                          tex_path(pid, 'nor_gl' if pid != 'jacaranda_tree' else 'trunk_nor_gl'), rough=0.92, spec=0.3)
    br_part = 'branch' if pid == 'tree_small_02' else 'branches'
    branch_mat = principled('branches', tex_path(pid, f'{br_part}_diff'), tex_path(pid, f'{br_part}_nor_gl'), rough=0.9, spec=0.3)
    mof = np.where(np.isin(A['mi'][bark_faces], branch_i), 1, 0)
    bark = submesh(f'{name}_bark', A, bark_faces, [bark_mat, branch_mat], mof)
    n_before = tri_count([bark])
    decimate(bark, bark_tris)
    smooth(bark)
    log(f'  bark: {keep_c.sum()} parts, {n_before} -> {tri_count([bark])} tris')

    # ---- leaf clusters
    leaf_c = np.where(np.isin(cmat, leaf_i))[0]
    P, W = cctr[leaf_c], carea[leaf_c]
    O = np.average(P, axis=0, weights=W)
    R = np.array([np.percentile(np.abs(P[:, k] - O[k]), 92) for k in range(3)]) + 0.05
    rng = np.random.default_rng(seed)
    # choose grid size so the occupied-cell count gives roughly `cards` cards
    def cells_for(g):
        key = np.floor(P / g).astype(np.int64)
        ukey, kinv = np.unique(key, axis=0, return_inverse=True)
        kinv = kinv.ravel()
        a = np.bincount(kinv, weights=W)
        ctr = np.stack([np.bincount(kinv, weights=P[:, k] * W) for k in range(3)], 1) / a[:, None]
        ok = a >= 0.12 * a.mean()
        return ctr[ok], a[ok]
    g = 0.5
    for _ in range(30):
        ctr, a = cells_for(g)
        target = cards / 1.35
        if abs(len(ctr) - target) < 0.04 * target:
            break
        g *= (len(ctr) / target) ** (1 / 2.4)
    g *= cell_k
    ctr, a = cells_for(g)
    log(f'  leaves: {len(leaf_c)} leaf parts, area {W.sum():.1f} m2, crown centre {O.round(2)}, radii {R.round(2)}, cell {g:.3f} m, {len(ctr)} cells')

    def radial(p):
        v = (p - O) / R ** 2
        v = v + np.array([0, 0, 0.8 / R[2]])  # lean crown normals skyward so undersides still see sky light
        return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)

    # atlas seeds: dense cells on the outside of the crown, spread apart
    shell = np.linalg.norm((ctr - O) / R, axis=1)
    cand = np.where((a >= np.percentile(a, 60)) & (shell > 0.55) & (shell < 1.1))[0]
    if len(cand) < 8:
        cand = np.argsort(-a)[:max(8, len(a) // 4)]
    seeds = [cand[rng.integers(len(cand))]]
    while len(seeds) < 4:
        dmin = np.min([np.linalg.norm(ctr[cand] - ctr[s_], axis=1) for s_ in seeds], axis=0)
        seeds.append(cand[int(np.argmax(dmin * (0.6 + 0.4 * rng.random(len(cand)))))])
    seed_p = ctr[seeds]
    seed_d = radial(seed_p) * np.array([1, 1, 0.35]) + rng.normal(0, 0.15, (4, 3))
    render_mats = (
        principled('render_leaves', tex_path(pid, 'leaves_diff'), tex_path(pid, 'leaves_nor_gl'), rough=1.0,
                   alpha=tex_path(pid, 'leaves_alpha'), alpha_clip=False, spec=0.0),
        principled('render_twigs', tex_path(pid, f'{br_part}_diff'), rough=1.0, spec=0.0))
    twig_faces = np.where(np.isin(A['mi'], branch_i))[0]
    src.hide_render = True
    bark.hide_render = True
    leaf_faces_mask = np.isin(A['mi'], leaf_i)
    comp_face = np.where(leaf_faces_mask, comp, -1)
    atlas, tiles = render_tiles(name, A, comp_face, (uc[leaf_c], P), A, twig_faces, seed_p, seed_d,
                                radius_k * g, render_mats)

    # ---- card placement
    n_extra = max(0, cards - len(ctr))
    extra = np.argsort(-a)[:n_extra]
    sites = np.concatenate([ctr, ctr[extra] + rng.normal(0, g * 0.25, (len(extra), 3))])
    nc = len(sites)
    rad = radial(sites)
    rnd = rng.normal(size=(nc, 3)); rnd /= np.linalg.norm(rnd, axis=1, keepdims=True)
    nrm = rad * 1.0 + rnd * 1.1
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    tile_id = rng.integers(0, 4, nc)
    size = np.array([tiles[t]['ext'] for t in tile_id]) * size_k * rng.uniform(0.85, 1.12, nc)
    verts, faces, uvs = [], [], []
    inset = 1.5 / 1024
    for i in range(nc):
        n = nrm[i]
        up = np.array([0, 0, 1.0]) - n[2] * n
        if np.linalg.norm(up) < 0.2:
            up = np.cross(n, rnd[(i + 1) % nc])
        up /= np.linalg.norm(up)
        ang = rng.normal(0, 0.45)
        right = np.cross(up, n)
        up, right = up * math.cos(ang) + right * math.sin(ang), right * math.cos(ang) - up * math.sin(ang)
        h = size[i] / 2
        b = len(verts)
        for cx, cy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append(sites[i] + right * cx * h + up * cy * h)
        faces.append((b, b + 1, b + 2, b + 3))
        t = tile_id[i]
        u0, v0 = (t % 2) * 0.5, (t // 2) * 0.5
        flip = rng.random() < 0.5
        for cx, cy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            cu = -cx if flip else cx
            uvs.append((u0 + inset + (cu * 0.5 + 0.5) * (0.5 - 2 * inset), v0 + inset + (cy * 0.5 + 0.5) * (0.5 - 2 * inset)))
    verts = np.array(verts)
    me = bpy.data.meshes.new(f'{name}_leaves')
    me.from_pydata(verts.tolist(), [], faces)
    me.uv_layers.new(name='UVMap').data.foreach_set('uv', np.array(uvs, np.float32).ravel())
    atlas_img = bpy.data.images.load(str(atlas[0]))
    leaves_mat = principled('leaves', color_img=atlas_img, normal=str(atlas[1]), rough=0.72, alpha='tex',
                            normal_strength=0.8, spec=0.35)
    me.materials.append(leaves_mat)
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    me.update()
    vn = radial(verts)
    me.normals_split_custom_set_from_vertices(vn.tolist())
    leaves = bpy.data.objects.new(f'{name}_leaves', me)
    bpy.context.scene.collection.objects.link(leaves)
    bpy.data.objects.remove(src)
    note = (f'height {height} m (scale {s:.3f}{", xy x" + str(xy) if xy != 1 else ""}); bark {n_before}->{tri_count([bark])} tris; '
            f'{nc} leaf-cluster cards from a 1024 px 2x2 atlas rendered from the original leaves')
    export([bark, leaves], name, rules=('branch=512', 'nor_gl=512', 'leaves_atlas_nor=512'), note=note)
    log(f'  {name} done in {time.time() - t0:.0f}s')
    return atlas


# ---------------------------------------------------------------- props
def build_lamp():
    reset()
    o = join(import_asset('street_lamp_01'), 'street_lamp')
    decimate(o, 4700)
    smooth(o, 40)
    ground(o)
    for m in o.data.materials:
        b = bsdf(m)
        if m.name.endswith('_glass'):
            for l in list(b.inputs['Alpha'].links):
                m.node_tree.links.remove(l)
            b.inputs['Alpha'].default_value = 0.28
            b.inputs['Roughness'].default_value = 0.08
        if m.name.endswith('_bulb'):
            b.inputs['Emission Color'].default_value = (1.0, 0.82, 0.55, 1)
            b.inputs['Emission Strength'].default_value = 1.0
    export([o], 'street_lamp', note='decimated from 30.6k tris; glass alpha 0.28 (BLEND); bulb emissive')


def build_bench():
    reset()
    objs = import_asset('modular_street_seating')
    parts = {'legs_single', 'legs_double', 'seat', 'seat_back', 'back_support_r', 'back_support_l',
             'arm_rest_01', 'arm_rest_02', 'crossbar'}
    for x in objs:
        if x.type == 'MESH' and x.name.split('.')[0] not in parts:
            bpy.data.objects.remove(x)
    objs = [x for x in bpy.data.objects if x.type == 'MESH']
    for x in objs:
        if tri_count([x]) > 1000:
            decimate(x, int(tri_count([x]) * 0.42))
    o = join(objs, 'park_bench')
    smooth(o, 40)
    ground(o)
    # merge the duplicated armrest material
    mats = o.data.materials
    for i, m in enumerate(mats):
        if m.name.endswith('.001'):
            base = bpy.data.materials.get(m.name[:-4])
            if base:
                mats[i] = base
    export([o], 'park_bench', rules=('armrests=512', 'supports=512', 'connectors=512'), note='assembled back bench from the modular kit; metal parts decimated ~58%')


def build_planter(atlas):
    reset()
    o = join(import_asset('planter_box_01'), 'planter')
    decimate(o, 3200)
    smooth(o, 40)
    d = ground(o, scale=1.4)
    # soil surface just below the rim
    L, Wd, H = d
    soil_mat = principled('soil', rough=0.95)
    bsdf(soil_mat).inputs['Base Color'].default_value = (0.09, 0.065, 0.045, 1)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, H - 0.07))
    soil = bpy.context.object
    soil.scale = (L - 0.12, Wd - 0.12, 1)
    bpy.ops.object.transform_apply(location=True, scale=True)
    soil.data.materials.append(soil_mat)
    # a low clipped shrub from leaf-cluster cards (atlas of street_tree_03)
    rng = np.random.default_rng(7)
    verts, faces, uvs, nrms = [], [], [], []
    O = np.array([0, 0, H + 0.08]); Rr = np.array([L * 0.42, Wd * 0.38, 0.16])
    for i in range(90):
        while True:
            p = rng.uniform(-1, 1, 3)
            if np.linalg.norm(p) < 1:
                break
        p = O + p * Rr * np.array([1, 1, 0.8])
        n = rng.normal(size=3); n /= np.linalg.norm(n)
        up = np.cross(n, [1, 0, 0]); up /= np.linalg.norm(up); right = np.cross(up, n)
        h = rng.uniform(0.13, 0.19)
        b = len(verts)
        t = rng.integers(4); u0, v0 = (t % 2) * 0.5, (t // 2) * 0.5
        for cx, cy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            q = p + right * cx * h + up * cy * h
            q[2] = max(q[2], H - 0.05)
            verts.append(q)
            uvs.append((u0 + 0.002 + (cx * 0.5 + 0.5) * 0.496, v0 + 0.002 + (cy * 0.5 + 0.5) * 0.496))
            v = (q - O) / Rr ** 2 + np.array([0, 0, 2.0]); nrms.append(v / np.linalg.norm(v))
        faces.append((b, b + 1, b + 2, b + 3))
    me = bpy.data.meshes.new('planter_shrub')
    me.from_pydata(np.array(verts).tolist(), [], faces)
    me.uv_layers.new(name='UVMap').data.foreach_set('uv', np.array(uvs, np.float32).ravel())
    img = bpy.data.images.load(str(atlas[0]))
    me.materials.append(principled('leaves', color_img=img, normal=str(atlas[1]), rough=0.72, alpha='tex', normal_strength=0.8, spec=0.35))
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    me.update()
    me.normals_split_custom_set_from_vertices(nrms)
    shrub = bpy.data.objects.new('planter_shrub', me)
    bpy.context.scene.collection.objects.link(shrub)
    export([o, soil, shrub], 'planter', rules=('leaves_atlas=512',),
           note='planter_box_01 scaled x1.4, decimated from 8.1k tris; added soil plane and a 90-card clipped shrub using the street_tree_03 leaf atlas')


def build_simple(name, pid, target, scale=1.0, max_tex=1024, note='', alpha_png=None, rotate_z=0.0):
    reset()
    o = join(import_asset(pid), name)
    n0 = tri_count([o])
    if rotate_z:
        o.data.transform(Matrix.Rotation(math.radians(rotate_z), 4, 'Z'))
    decimate(o, target)
    smooth(o, 40)
    ground(o, scale=scale)
    if alpha_png:  # glTF download drops the opacity map; rebuild alpha as a MASK
        for m in o.data.materials:
            b = bsdf(m)
            t = m.node_tree.nodes.new('ShaderNodeTexImage')
            t.image = bpy.data.images.load(alpha_png)
            t.image.colorspace_settings.name = 'Non-Color'
            r = m.node_tree.nodes.new('ShaderNodeMath'); r.operation = 'ROUND'
            m.node_tree.links.new(t.outputs['Color'], r.inputs[0])
            m.node_tree.links.new(r.outputs[0], b.inputs['Alpha'])
    export([o], name, max_tex=max_tex, note=f'{n0}->{tri_count([o])} tris; {note}'.strip('; '))


TREES = {
    # name: (pid, height m, kwargs)
    'street_tree_01': ('tree_small_02', 7.6, dict(xy=1.0, cards=2400, bark_tris=3400, branch_rmin=0.012, seed=3)),
    'street_tree_02': ('jacaranda_tree', 8.8, dict(xy=0.75, cards=2800, bark_tris=4200, branch_rmin=0.03, seed=5)),
    'street_tree_03': ('island_tree_01', 6.4, dict(xy=1.0, cards=2400, bark_tris=3600, branch_rmin=0.012, seed=7)),
}


SOURCES = {  # output name -> (Poly Haven id, what was done beyond the stats note)
    'street_tree_01': ('tree_small_02', 'Bark: trunk + branches thicker than ~1.2 cm kept, collapse-decimated. Leaves: 2x2 leaf-cluster atlas path-traced from the original leaf cards (albedo x softened AO + camera-space normals), cards placed at the original leaf positions with crown-shaped normals.'),
    'street_tree_02': ('jacaranda_tree', 'As street_tree_01; horizontal extent scaled x0.75 to fit a street; branches thinner than ~3 cm dropped.'),
    'street_tree_03': ('island_tree_01', 'As street_tree_01; flat root/rock skirt at the base removed.'),
    'street_lamp': ('street_lamp_01', 'Collapse-decimated; glass made a constant 0.28-alpha BLEND material; bulb given a warm emissive factor.'),
    'park_bench': ('modular_street_seating', 'Back bench assembled from the kit parts (legs_single, legs_double, seat, seat_back, back supports, arm rests, crossbar); metal parts decimated; metal textures 512 px.'),
    'planter': ('planter_box_01', 'Scaled x1.4 to street-planter size and decimated; dark soil plane and a clipped shrub of leaf cards (street_tree_03 atlas at 512 px) added.'),
    'goods_cardboard_box': ('cardboard_box_01', 'Decimated; textures 512 px.'),
    'goods_crate': ('plastic_crate_02', 'Decimated; the separate opacity map (dropped by the glTF download) re-attached as alpha MASK; textures 512 px.'),
    'goods_cans': ('long_life_food', 'Four items (milk carton, two cans, sardine tin) joined; decimated; textures 512 px.'),
    'goods_cleaner': ('all_purpose_cleaner', 'Decimated; textures 512 px.'),
}


def write_source_md():
    stats = json.loads(STATS.read_text()) if STATS.exists() else {}
    lines = ['# Ride props: sources and licences', '',
             'All models are derived from [Poly Haven](https://polyhaven.com) assets, licensed',
             '[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain; attribution not required but given here).',
             'Downloaded as the 1k glTF (1024 px textures) via the Poly Haven API, plus the 1k leaf-alpha / opacity PNGs that the glTF omits.',
             'Rebuild: `python3 scripts/modeling/fetch_props.py` then',
             '`./scripts/blender --background --factory-startup --python scripts/modeling/prepare_props.py`.',
             '',
             'Conventions: metres, +Y up, origin at the base centre on the ground, Draco-compressed geometry,',
             'JPEG textures (the leaf atlases are 256-colour PNGs because they need alpha; leaves use alphaMode MASK).', '',
             '| file | source | authors | triangles | size | dimensions (w x h x d m) |',
             '|---|---|---|---|---|---|']
    details = []
    for name, (pid, what) in SOURCES.items():
        if name not in stats:
            continue
        st = stats[name]
        info = json.loads((CACHE / pid / 'info.json').read_text())
        authors = ', '.join(info.get('authors', {}).keys())
        w, d, h = st['size_m']
        lines.append(f"| `{name}.glb` | [{info.get('name', pid)}](https://polyhaven.com/a/{pid}) (`{pid}`) | {authors} | "
                     f"{st['tris']:,} | {st['bytes'] / 1e6:.2f} MB | {w:.2f} x {h:.2f} x {d:.2f} |")
        details += [f'### {name}.glb', '',
                    f'- Source: https://polyhaven.com/a/{pid} (API id `{pid}`), by {authors}; licence CC0 1.0.',
                    f"- Downloaded: 1k glTF (source polycount {info.get('polycount', '?'):,} as listed by the API).",
                    f"- Changes: {st['note']}.", f'- {what}', '']
    total = sum(v['bytes'] for k, v in stats.items() if k in SOURCES)
    lines += ['', f'Total: {total / 1e6:.2f} MB across {sum(k in stats for k in SOURCES)} GLBs.', ''] + details
    (OUT / 'SOURCE.md').write_text('\n'.join(lines))
    log('wrote SOURCE.md', f'{total / 1e6:.2f} MB total')


def main(which):
    atlas3 = None
    for name, (pid, h, kw) in TREES.items():
        if not which or name in which or 'trees' in which:
            a = build_tree(name, pid, h, **kw)
            if name == 'street_tree_03':
                atlas3 = a
    if not which or 'street_lamp' in which:
        build_lamp()
    if not which or 'park_bench' in which:
        build_bench()
    if not which or 'planter' in which:
        atlas3 = atlas3 or [WORK / 'street_tree_03' / 'leaves_atlas.png', WORK / 'street_tree_03' / 'leaves_atlas_nor.png']
        build_planter(atlas3)
    if not which or 'goods' in which or 'goods_cardboard_box' in which:
        build_simple('goods_cardboard_box', 'cardboard_box_01', 1800, max_tex=512)
    if not which or 'goods' in which or 'goods_crate' in which:
        build_simple('goods_crate', 'plastic_crate_02', 4400, max_tex=512,
                     alpha_png=tex_path('plastic_crate_02', 'opacity'), note='opacity map restored as alpha MASK')
    if not which or 'goods' in which or 'goods_cans' in which:
        build_simple('goods_cans', 'long_life_food', 3600, max_tex=512)
    if not which or 'goods' in which or 'goods_cleaner' in which:
        build_simple('goods_cleaner', 'all_purpose_cleaner', 2400, max_tex=512)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    main(set(argv))
    write_source_md()
    log('ALL DONE')
