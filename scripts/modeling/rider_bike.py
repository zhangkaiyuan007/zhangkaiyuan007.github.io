"""Procedural road bike for the ride scene (imported by build_rider.py).

Blender frame: +Y forward, +Z up, +X is the rider's right (drive side).
Units are metres. Origin is on the ground, midway between the tyre contact points.
Geometry follows a typical 54 cm aluminium endurance road frame: 985 mm wheelbase,
408 mm chainstays, 70 mm BB drop, 73 deg head / 73.5 deg seat angles, 700x25c tyres,
170 mm cranks, 50/34 chainrings, 11-28 cassette, 420 mm drop bar, 100 mm stem.
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

# ---------------------------------------------------------------- geometry ---
WHEEL_R = 0.335          # tyre outer radius (622 mm bead seat + 25c tyre)
RIM_R = 0.311            # bead seat radius
WHEELBASE = 0.985
CHAINSTAY = 0.408
BB_DROP = 0.070
HTA = math.radians(73.0)
STA = math.radians(73.5)
RAKE = 0.045
STACK = 0.555
CRANK = 0.170

R_AXLE = Vector((0, -WHEELBASE / 2, WHEEL_R))
F_AXLE = Vector((0, WHEELBASE / 2, WHEEL_R))
BB = Vector((0, R_AXLE.y + math.sqrt(CHAINSTAY ** 2 - BB_DROP ** 2), WHEEL_R - BB_DROP))
HT_DOWN = Vector((0, math.cos(HTA), -math.sin(HTA)))       # steering axis, pointing down
HT_UP = -HT_DOWN
ST_UP = Vector((0, -math.cos(STA), math.sin(STA)))          # seat tube axis, pointing up
_rake_dir = Vector((0, math.sin(HTA), math.cos(HTA)))       # perpendicular to the axis, forward
_axis_p0 = F_AXLE - RAKE * _rake_dir                        # steering axis at axle height
HT_TOP = _axis_p0 + HT_UP * ((BB.z + STACK - _axis_p0.z) / HT_UP.z)
HT_BOT = HT_TOP + HT_DOWN * 0.150
STEM_CLAMP = HT_TOP + HT_UP * 0.058                        # 15 mm headset cap + 25 mm spacers + half stem
_stem_dir = Vector((0, math.cos(math.radians(11)), math.sin(math.radians(11))))
BAR_CLAMP = STEM_CLAMP + _stem_dir * 0.100
BAR_HALF_WIDTH = 0.205
HOOD_GRIP = Vector((BAR_HALF_WIDTH - 0.004, BAR_CLAMP.y + 0.086, BAR_CLAMP.z + 0.022))   # palm contact on the hood


def saddle_top(height):
    """Saddle clamp top point for a given BB-to-saddle-top distance along the seat tube."""
    return BB + ST_UP * height


# -------------------------------------------------------------- materials ---
def srgb(hexstr):
    v = [int(hexstr[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x < 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v) + (1.0,)


def make_material(name, color, rough=0.5, metal=0.0, coat=0.0, coat_rough=0.08):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = srgb(color) if isinstance(color, str) else color
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if coat:
        p.inputs['Coat Weight'].default_value = coat
        p.inputs['Coat Roughness'].default_value = coat_rough
    return m


def bike_materials():
    return dict(
        paint=make_material('Bike paint orange', 'e96a2d', 0.32, 0.0, coat=0.7, coat_rough=0.06),
        black=make_material('Bike black matte', '1c1d1f', 0.55, 0.0),
        gloss=make_material('Bike black gloss', '141516', 0.22, 0.0, coat=0.4),
        alu=make_material('Bike aluminium', 'b8bcc0', 0.28, 1.0),
        dark_alu=make_material('Bike anodised grey', '4a4e53', 0.35, 1.0),
        steel=make_material('Bike chain steel', '6d7075', 0.38, 1.0),
        spoke=make_material('Bike spokes', 'c9ccd0', 0.25, 1.0),
        tread=make_material('Tyre tread', '17181a', 0.82, 0.0),
        wall=make_material('Tyre sidewall', '2a2a2b', 0.62, 0.0),
        tape=make_material('Bar tape', '1a1b1c', 0.75, 0.0),
        saddle=make_material('Saddle cover', '161718', 0.45, 0.0),
        rubber=make_material('Hood rubber', '202122', 0.68, 0.0),
        track=make_material('Rim brake track', '8e9398', 0.42, 1.0),
    )


# ------------------------------------------------------------ mesh helpers ---
_OBJS = []


def new_mesh(name, verts, faces, mat, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(mat)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    _OBJS.append(o)
    return o


def _frames(pts, up=None):
    """Parallel-transport frames along a polyline."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tangents = []
    for i in range(n):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    ref = Vector(up) if up is not None else Vector((0, 0, 1))
    if abs(ref.dot(tangents[0])) > 0.95:
        ref = Vector((1, 0, 0)) if abs(tangents[0].x) < 0.9 else Vector((0, 1, 0))
    nrm = (ref - tangents[0] * ref.dot(tangents[0])).normalized()
    out = []
    for i, t in enumerate(tangents):
        if i > 0:
            q = tangents[i - 1].rotation_difference(t)
            nrm = (q @ nrm)
            nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm, t.cross(nrm)))
    return pts, out


def sweep(name, pts, radii, mat, seg=12, caps=True, up=None, smooth=True, twist=0.0):
    """Tube along pts. radii: float, list of floats, or list of (r_normal, r_binormal)."""
    pts, frames = _frames(pts, up)
    n = len(pts)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    verts, faces = [], []
    for i, (p, (t, nm, bn)) in enumerate(zip(pts, frames)):
        r = radii[i]
        ra, rb = (r, r) if not isinstance(r, (list, tuple)) else r
        for k in range(seg):
            a = 2 * math.pi * k / seg + twist
            verts.append(p + nm * (math.cos(a) * ra) + bn * (math.sin(a) * rb))
    for i in range(n - 1):
        for k in range(seg):
            a, b = i * seg + k, i * seg + (k + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    if caps:
        faces.append(tuple(reversed(range(seg))))
        faces.append(tuple(range((n - 1) * seg, n * seg)))
    return new_mesh(name, verts, faces, mat, smooth)


def lathe(name, profile, mat, seg=32, center=(0, 0, 0), axis='X', close=False, smooth=True):
    """Revolve a (radius, axial) profile about an axis through center."""
    c = Vector(center)
    verts, faces = [], []
    m = len(profile)
    for k in range(seg):
        a = 2 * math.pi * k / seg
        ca, sa = math.cos(a), math.sin(a)
        for r, x in profile:
            if axis == 'X':
                v = Vector((x, r * ca, r * sa))
            elif axis == 'Z':
                v = Vector((r * ca, r * sa, x))
            else:
                v = Vector((r * ca, x, r * sa))
            verts.append(c + v)
    rng = m if close else m - 1
    for k in range(seg):
        k2 = (k + 1) % seg
        for j in range(rng):
            j2 = (j + 1) % m
            faces.append((k * m + j, k * m + j2, k2 * m + j2, k2 * m + j))
    return new_mesh(name, verts, faces, mat, smooth)


def extrude(name, outline, depth, mat, origin=(0, 0, 0), u=(0, 1, 0), v=(0, 0, 1), smooth=False):
    """Extrude a 2D outline (in the u/v plane) symmetric about the plane, along u x v."""
    o, U, V = Vector(origin), Vector(u).normalized(), Vector(v).normalized()
    W = U.cross(V).normalized()
    n = len(outline)
    verts = [o + U * x + V * y - W * depth / 2 for x, y in outline] + \
            [o + U * x + V * y + W * depth / 2 for x, y in outline]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    ob = new_mesh(name, verts, faces, mat, smooth)
    return ob


def box(name, center, size, mat, rot=None):
    c = Vector(center)
    sx, sy, sz = [s / 2 for s in size]
    corners = [Vector((x, y, z)) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    if rot is not None:
        corners = [rot @ p for p in corners]
    verts = [c + p for p in corners]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return new_mesh(name, verts, faces, mat, False)


def catmull(points, per=6):
    pts = [Vector(p) for p in points]
    out = []
    for i in range(len(pts) - 1):
        p0, p1 = pts[max(i - 1, 0)], pts[i]
        p2, p3 = pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        for s in range(per):
            t = s / per
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def join(objs, name):
    objs = [o for o in objs if o is not None]
    ctx = bpy.context
    for o in ctx.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    ctx.view_layer.objects.active = objs[0]
    with ctx.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
        bpy.ops.object.join()
    ob = objs[0]
    ob.name = name
    ob.data.name = name
    for o in objs[1:]:
        if o in _OBJS:
            _OBJS.remove(o)
    return ob


def remesh_blend(obj, voxel=0.0016, smooth_iter=6, ratio=0.02, target=None):
    """Voxel-remesh a union of tubes so that joints read as welded/moulded, then decimate."""
    m = obj.modifiers.new('Remesh', 'REMESH')
    m.mode = 'VOXEL'
    m.voxel_size = voxel
    m.adaptivity = 0.0
    m.use_smooth_shade = True
    s = obj.modifiers.new('Fillet', 'CORRECTIVE_SMOOTH')
    s.iterations = smooth_iter
    s.smooth_type = 'LENGTH_WEIGHTED'
    s.use_only_smooth = True
    s.factor = 0.5
    ctx = bpy.context
    ctx.view_layer.objects.active = obj
    with ctx.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier='Remesh')
        bpy.ops.object.modifier_apply(modifier='Fillet')
    faces = len(obj.data.polygons)
    if target:
        ratio = min(1.0, target / (faces * 2))
    d = obj.modifiers.new('Decimate', 'DECIMATE')
    d.ratio = ratio
    d.use_collapse_triangulate = True
    with ctx.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier='Decimate')
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj


def sprocket_outline(teeth, pitch=0.0127, pts_per_tooth=4):
    """Chainring / cog outline: round roller seats, short flat-topped teeth."""
    rp = pitch / (2 * math.sin(math.pi / teeth))
    out = []
    for i in range(teeth):
        base = 2 * math.pi * i / teeth
        for k in range(pts_per_tooth):
            f = k / pts_per_tooth
            d = min(f, 1 - f)                      # 0 at the roller seat, 0.5 at the tooth tip
            s = max(0.0, min(1.0, (d - 0.10) / 0.28))
            s = s * s * (3 - 2 * s)
            r = rp - 0.0036 + 0.0064 * s
            a = base + 2 * math.pi * f / teeth
            out.append((r * math.cos(a), r * math.sin(a)))
    return out, rp


def gear_ring(name, teeth, x, inner_r, mat, thick=0.0018, pts=4, back=True, center=(0, 0, 0)):
    """Toothed ring in the YZ plane at lateral position x. Front face (+x), tooth rim, optional back face."""
    outline, rp = sprocket_outline(teeth, pts_per_tooth=pts)
    cy, cz = center[1], center[2]
    m = len(outline)
    verts, faces = [], []
    for sgn in (-1, 1):
        for (py, pz) in outline:
            verts.append((x + sgn * thick / 2, cy + py, cz + pz))
        for (py, pz) in outline:
            a = math.atan2(pz, py)
            verts.append((x + sgn * thick / 2, cy + inner_r * math.cos(a), cz + inner_r * math.sin(a)))
    for k in range(m):
        k2 = (k + 1) % m
        faces.append((2 * m + k, 3 * m + k, 3 * m + k2, 2 * m + k2))   # +x face
        faces.append((k, 2 * m + k, 2 * m + k2, k2))                   # tooth rim
        if back:
            faces.append((k, k2, m + k2, m + k))                       # -x face
    return new_mesh(name, verts, faces, mat, smooth=False), rp


# ------------------------------------------------------------------ parts ---
def build_frame(M):
    parts = []
    # Tube centre-line key points
    tt_front = HT_TOP + HT_DOWN * 0.028
    st_top = BB + ST_UP * 0.500
    tt_rear = BB + ST_UP * 0.470
    dt_front = HT_BOT + HT_UP * 0.030
    seat_cluster = BB + ST_UP * 0.455
    drop_r = Vector((0.0655, R_AXLE.y, R_AXLE.z))
    drop_l = Vector((-0.0655, R_AXLE.y, R_AXLE.z))

    parts.append(sweep('HeadTube', [HT_TOP + HT_UP * 0.004, HT_BOT + HT_DOWN * 0.006],
                       [0.0235, 0.0285], M['paint'], seg=28))
    tt = catmull([tt_front, tt_front.lerp(tt_rear, 0.5) + Vector((0, 0, 0.004)), tt_rear], 8)
    parts.append(sweep('TopTube', tt, [(0.019 - 0.004 * i / (len(tt) - 1), 0.0165 - 0.002 * i / (len(tt) - 1)) for i in range(len(tt))],
                       M['paint'], seg=20, up=(1, 0, 0)))
    dt_end = BB + Vector((0, 0.012, 0.018))
    dt = catmull([dt_front, dt_front.lerp(dt_end, 0.5), dt_end], 8)
    parts.append(sweep('DownTube', dt, [(0.0245 - 0.004 * i / (len(dt) - 1), 0.0215 - 0.002 * i / (len(dt) - 1)) for i in range(len(dt))],
                       M['paint'], seg=22, up=(1, 0, 0)))
    parts.append(sweep('SeatTube', [BB + ST_UP * -0.01, BB + ST_UP * 0.12, st_top],
                       [0.0205, 0.0175, 0.0162], M['paint'], seg=20))
    parts.append(sweep('BBShell', [BB + Vector((-0.036, 0, 0)), BB + Vector((0.036, 0, 0))], 0.0215, M['paint'], seg=22))
    for side, drop in ((1, drop_r), (-1, drop_l)):
        cs_start = BB + Vector((side * 0.030, -0.018, 0.0))
        cs = catmull([cs_start, cs_start.lerp(drop, 0.35) + Vector((side * 0.018, 0, -0.004)),
                      cs_start.lerp(drop, 0.75) + Vector((side * 0.012, 0, 0.0)), drop + Vector((0, 0.012, 0.004))], 6)
        parts.append(sweep('Chainstay', cs, [(0.0115 - 0.004 * i / (len(cs) - 1), 0.0095 - 0.0035 * i / (len(cs) - 1)) for i in range(len(cs))],
                           M['paint'], seg=14, up=(1, 0, 0)))
        ss_start = seat_cluster + Vector((side * 0.017, -0.012, 0.0))
        ss = catmull([ss_start, ss_start.lerp(drop, 0.45) + Vector((side * 0.012, 0, 0.0)), drop + Vector((0, 0.004, 0.013))], 8)
        parts.append(sweep('Seatstay', ss, [0.0085 - 0.002 * i / (len(ss) - 1) for i in range(len(ss))], M['paint'], seg=12))
        # dropout plate
        parts.append(extrude('Dropout', [(-0.012, -0.004), (0.02, -0.008), (0.024, 0.016), (0.0, 0.022), (-0.014, 0.012)],
                             0.006, M['paint'], origin=drop, u=(0, 1, 0), v=(0, 0, 1)))
    # seat-stay brake bridge
    bridge_c = seat_cluster.lerp(R_AXLE, 0.30)
    parts.append(sweep('BrakeBridge', [bridge_c + Vector((-0.024, 0, 0)), bridge_c + Vector((0.024, 0, 0))], 0.0055, M['paint'], seg=10))
    frame = join(parts, 'FrameTubes')
    remesh_blend(frame, voxel=0.0014, smooth_iter=8, target=6000)
    frame.data.materials.clear()
    frame.data.materials.append(M['paint'])
    return frame, dict(st_top=st_top, bridge=bridge_c, seat_cluster=seat_cluster)


def build_fork(M):
    """Fork, in world coordinates."""
    parts = []
    crown = HT_BOT + HT_DOWN * 0.012
    parts.append(sweep('Steerer', [HT_TOP + HT_UP * 0.05, crown], 0.0145, M['paint'], seg=14))
    for side in (1, -1):
        top = crown + Vector((side * 0.038, 0.004, -0.012))
        drop = F_AXLE + Vector((side * 0.051, 0, 0.004))
        mid = top.lerp(drop, 0.5) + _rake_dir * 0.006
        blade = catmull([crown + Vector((side * 0.012, 0.0, 0.0)), top, mid, drop], 6)
        parts.append(sweep('ForkBlade', blade, [(0.019 - 0.009 * i / (len(blade) - 1), 0.0135 - 0.005 * i / (len(blade) - 1)) for i in range(len(blade))],
                           M['paint'], seg=16, up=(1, 0, 0)))
        parts.append(extrude('ForkTip', [(-0.012, -0.006), (0.012, -0.006), (0.013, 0.012), (-0.01, 0.016)], 0.007, M['paint'],
                             origin=F_AXLE + Vector((side * 0.051, 0, 0)), u=(0, 1, 0), v=(0, 0, 1)))
    parts.append(sweep('Crown', [crown + Vector((-0.045, 0.002, -0.008)), crown + Vector((0, 0.004, 0.0)), crown + Vector((0.045, 0.002, -0.008))],
                       [(0.013, 0.02), (0.016, 0.024), (0.013, 0.02)], M['paint'], seg=16, up=(0, 0, 1)))
    fork = join(parts, 'ForkBody')
    remesh_blend(fork, voxel=0.0013, smooth_iter=6, target=2300)
    return fork


def build_cockpit(M):
    """Headset, stem, handlebar, hoods, levers and cable housing (world coordinates)."""
    parts = []
    # headset cap, spacers, stem steerer clamp
    parts.append(lathe('HeadsetTop', [(0.0, 0.0), (0.0245, 0.0), (0.0245, 0.006), (0.021, 0.012), (0.0, 0.012)],
                       M['black'], 28, HT_TOP + HT_UP * 0.002, 'Z', smooth=False))
    for i in range(2):
        parts.append(lathe('Spacer', [(0.0165, 0.0), (0.0175, 0.0), (0.0175, 0.0095), (0.0165, 0.0095)], M['gloss'], 24,
                           HT_TOP + HT_UP * (0.014 + 0.0105 * i), 'Z', close=True, smooth=False))
    for p in parts[-3:]:
        _orient_to_axis(p, HT_TOP, HT_UP)
    stem_base = STEM_CLAMP
    clamp = sweep('StemClamp', [stem_base + HT_DOWN * 0.021, stem_base + HT_UP * 0.021], 0.0185, M['black'], seg=20)
    parts.append(clamp)
    parts.append(lathe('TopCap', [(0.0, 0.0), (0.0175, 0.0), (0.016, 0.004), (0.0, 0.0045)], M['black'], 20,
                       stem_base + HT_UP * 0.021, 'Z', smooth=True))
    _orient_to_axis(parts[-1], stem_base + HT_UP * 0.021, HT_UP)
    ext = [stem_base + _stem_dir * 0.01, stem_base + _stem_dir * 0.05, BAR_CLAMP - _stem_dir * 0.012]
    parts.append(sweep('StemBody', ext, [(0.0175, 0.0145), (0.0155, 0.013), (0.0165, 0.0135)], M['black'], seg=18, up=(0, 0, 1)))
    parts.append(sweep('BarClampBody', [BAR_CLAMP + Vector((-0.021, 0, 0)), BAR_CLAMP + Vector((0.021, 0, 0))], 0.0195, M['black'], seg=22))
    parts.append(sweep('Faceplate', [BAR_CLAMP + Vector((-0.02, 0.0, 0)), BAR_CLAMP + Vector((0.02, 0.0, 0))],
                       [(0.0205, 0.0205)] * 2, M['gloss'], seg=22, caps=True))
    bar_black, bar_tape, hoods = [], [], []
    for side in (1, -1):
        s = side
        c = BAR_CLAMP
        path = [c + Vector((s * x, y, z)) for x, y, z in [
            (0.0, 0.0, 0.0), (0.05, 0.0, 0.0), (0.12, 0.0, 0.0), (0.165, 0.004, 0.0), (0.192, 0.024, 0.0),
            (0.203, 0.055, -0.002), (0.206, 0.080, -0.012), (0.207, 0.093, -0.038), (0.207, 0.087, -0.072),
            (0.207, 0.064, -0.105), (0.207, 0.030, -0.124), (0.207, -0.010, -0.128), (0.207, -0.060, -0.125), (0.207, -0.085, -0.122)]]
        dense = catmull(path, 3)
        # centre (bare) and taped parts
        k = next(i for i, p in enumerate(dense) if abs(p.x - c.x) > 0.075)
        bare = dense[:k + 1]
        r_bare = [0.0159 if abs(p.x - c.x) < 0.035 else 0.0159 - (abs(p.x - c.x) - 0.035) * 0.1 for p in bare]
        bar_black.append(sweep('BarTop', bare, r_bare, M['black'], seg=12, caps=False, up=(0, 0, 1)))
        taped = dense[k:]
        bar_tape.append(sweep('BarTape', taped, 0.0138, M['tape'], seg=11, up=(0, 0, 1)))
        # bar-end plug
        bar_black.append(lathe('BarPlug', [(0.0, 0.0), (0.0135, 0.0), (0.0138, 0.003), (0.0, 0.004)], M['gloss'], 12,
                               dense[-1], 'Y', smooth=False))
        _orient_to_axis(bar_black[-1], dense[-1], (dense[-1] - dense[-2]).normalized())
        # hood (lever body): clamps on the forward bend, top continues the bar tops, horn in front
        hc = c + Vector((s * 0.207, 0.0, 0.0))
        hp = [hc + Vector((0, y, z)) for y, z in [(0.058, -0.006), (0.075, -0.001), (0.095, 0.004), (0.114, 0.010),
                                                   (0.127, 0.017), (0.134, 0.021), (0.138, 0.012), (0.134, -0.004)]]
        hp = catmull(hp, 3)
        rr = []
        for i in range(len(hp)):
            f = i / (len(hp) - 1)
            lat = 0.0125 + 0.002 * math.sin(math.pi * min(1.0, f * 1.3))
            ver = 0.0165 + 0.0035 * math.sin(math.pi * min(1.0, f * 1.25))
            if f > 0.72:
                k2 = (f - 0.72) / 0.28
                lat *= 1 - 0.55 * k2
                ver *= 1 - 0.65 * k2
            rr.append((lat, ver))
        hoods.append(sweep('Hood', hp, rr, M['rubber'], seg=12, up=(1, 0, 0)))
        # lever blade in front of the drop curve
        lp = [hc + Vector((s * 0.001, y, z)) for y, z in [(0.133, -0.006), (0.131, -0.036), (0.121, -0.068), (0.105, -0.097), (0.090, -0.118), (0.084, -0.128)]]
        lp = catmull(lp, 3)
        hoods.append(sweep('Lever', lp, [(0.0045, 0.0068 - 0.0018 * i / (len(lp) - 1)) for i in range(len(lp))], M['dark_alu'], seg=8, up=(1, 0, 0)))
    # cable housing loops from under the bar tape (next to the stem) to the frame ports and front caliper
    housing = []
    caliper_top = HT_BOT + HT_DOWN * 0.018 + _rake_dir * 0.036 + Vector((0.012, 0, 0.012))
    C = BAR_CLAMP
    rel = lambda p: C + Vector(p)
    for side in (1, -1):   # rear brake (right) / shift (left): forward loop, back into the head-tube port
        port = HT_TOP + HT_DOWN * 0.06 + Vector((side * 0.021, 0.004, 0.0))
        pr = port - C
        pts = [rel((side * 0.046, -0.004, -0.013)), rel((side * 0.052, 0.035, -0.036)), rel((side * 0.043, 0.058, -0.08)),
               rel((side * 0.03, 0.02, pr.z + 0.035)), port + HT_UP * 0.012, port]
        housing.append(sweep('Housing', catmull(pts, 5), 0.0024, M['gloss'], seg=6))
    pts = [rel((-0.04, -0.004, -0.013)), rel((-0.05, 0.045, -0.045)), rel((-0.035, 0.075, -0.115)),
           rel((-0.008, 0.035, (caliper_top - C).z + 0.04)), caliper_top + Vector((0, 0.004, 0.012)), caliper_top]
    housing.append(sweep('Housing', catmull(pts, 5), 0.0024, M['gloss'], seg=6))
    return parts + bar_black, bar_tape, hoods, housing


def _orient_to_axis(obj, pivot, axis):
    """Rotate object vertices built along +Z (about pivot) so that +Z becomes axis."""
    q = Vector((0, 0, 1)).rotation_difference(Vector(axis))
    R = q.to_matrix().to_4x4()
    T = Matrix.Translation(Vector(pivot))
    obj.data.transform(T @ R @ T.inverted())


def build_caliper(M, pivot, facing, name):
    """Dual-pivot rim brake: pivot = mounting bolt, facing = unit vector away from the frame (Y)."""
    parts = []
    f = facing
    for s in (1, -1):
        outline = [(s * 0.004, 0.006), (s * 0.028, -0.002), (s * 0.034, -0.030), (s * 0.030, -0.050), (s * 0.024, -0.050),
                   (s * 0.024, -0.030), (s * 0.018, -0.008), (s * 0.0, -0.004)]
        if s < 0:
            outline = list(reversed(outline))
        parts.append(extrude(name + 'Arm', outline, 0.007, M['alu'], origin=pivot + f * (0.010 + 0.006 * (s > 0)),
                             u=(1, 0, 0), v=(0, 0, 1)))
        pad = pivot + Vector((s * 0.019, 0, -0.048)) + f * 0.004
        parts.append(box(name + 'Pad', pad, (0.008, 0.038, 0.009), M['black']))
    parts.append(sweep(name + 'Bolt', [pivot - f * 0.01, pivot + f * 0.028], 0.0042, M['alu'], seg=10))
    return parts


def build_wheel(M, name, rear=False):
    """Wheel centred at origin, axle along X (local coordinates)."""
    parts = []
    # rim: black semi-aero profile with machined silver brake track
    rim_prof = [(0.284, 0.0), (0.2875, 0.0055), (0.2955, 0.0095), (0.3005, 0.0108), (0.3108, 0.0108), (0.3125, 0.0098),
                (0.3125, 0.0086), (0.3100, 0.0082), (0.3100, -0.0082), (0.3125, -0.0086), (0.3125, -0.0098), (0.3108, -0.0108),
                (0.3005, -0.0108), (0.2955, -0.0095), (0.2875, -0.0055)]
    parts.append(lathe(name + 'Rim', rim_prof[:4] + rim_prof[-3:] + [rim_prof[0]], M['gloss'], 56, close=False, smooth=True))
    parts.append(lathe(name + 'BrakeTrackR', [(0.3005, 0.0109), (0.3108, 0.0109)], M['track'], 56, smooth=True))
    parts.append(lathe(name + 'BrakeTrackL', [(0.3108, -0.0109), (0.3005, -0.0109)], M['track'], 56, smooth=True))
    parts.append(lathe(name + 'RimTop', [(0.3108, 0.0109), (0.3125, 0.0098), (0.3125, -0.0098), (0.3108, -0.0109)], M['gloss'], 56))
    # tyre: tread cap + sidewalls with a slightly different finish
    tw, tc = 0.0126, RIM_R + 0.0118
    def pt(a):
        # a measured from the outward radial direction; x lateral
        return (tc + tw * math.cos(a), tw * math.sin(a) * 0.96)
    wall_r = [pt(a) for a in (math.radians(155), math.radians(118), math.radians(84), math.radians(55))]
    tread = [pt(a) for a in (math.radians(55), math.radians(27), 0.0, math.radians(-27), math.radians(-55))]
    wall_l = [pt(a) for a in (math.radians(-55), math.radians(-84), math.radians(-118), math.radians(-155))]
    parts.append(lathe(name + 'TyreWallR', wall_r, M['wall'], 56))
    parts.append(lathe(name + 'Tread', tread, M['tread'], 56))
    parts.append(lathe(name + 'TyreWallL', wall_l, M['wall'], 56))
    # hub
    if rear:
        hub = [(0.005, -0.066), (0.0125, -0.066), (0.0125, -0.040), (0.024, -0.038), (0.024, -0.034), (0.013, -0.031),
               (0.0115, 0.0), (0.013, 0.012), (0.024, 0.015), (0.024, 0.019), (0.016, 0.021), (0.016, 0.062), (0.005, 0.066)]
        flanges = (-0.036, 0.017)
    else:
        hub = [(0.005, -0.051), (0.012, -0.051), (0.012, -0.036), (0.021, -0.034), (0.021, -0.030), (0.011, -0.027),
               (0.0095, 0.0), (0.011, 0.027), (0.021, 0.030), (0.021, 0.034), (0.012, 0.036), (0.012, 0.051), (0.005, 0.051)]
        flanges = (-0.032, 0.032)
    parts.append(lathe(name + 'Hub', hub, M['dark_alu'], 24))
    # quick-release skewer: nut on drive side, lever on the left
    ol = hub[0][1]
    parts.append(lathe(name + 'QRNut', [(0.0, 0.0), (0.009, 0.0), (0.0095, 0.008), (0.0, 0.009)], M['alu'], 16, (hub[-1][1] + 0.003, 0, 0), 'X'))
    parts.append(lathe(name + 'QRCam', [(0.0, 0.0), (0.0105, 0.0), (0.0105, -0.010), (0.0, -0.011)], M['alu'], 16, (ol - 0.003, 0, 0), 'X'))
    lever = catmull([Vector((ol - 0.012, 0, 0)), Vector((ol - 0.016, 0.02, -0.004)), Vector((ol - 0.018, 0.045, -0.006)), Vector((ol - 0.017, 0.062, -0.004))], 4)
    parts.append(sweep(name + 'QRLever', lever, [(0.004, 0.0065)] * len(lever), M['alu'], seg=8, up=(1, 0, 0)))
    # spokes
    n = 24 if rear else 20
    spokes = []
    for i in range(n):
        a = 2 * math.pi * i / n
        side = 1 if i % 2 == 0 else -1
        fx = flanges[1] if side > 0 else flanges[0]
        cross = (math.radians(30) if (i // 2) % 2 == 0 else -math.radians(30)) if rear else 0.0
        hub_pt = Vector((fx, 0.0205 * math.cos(a + cross), 0.0205 * math.sin(a + cross)))
        rim_pt = Vector((side * 0.0015, 0.2855 * math.cos(a), 0.2855 * math.sin(a)))
        spokes.append(sweep(name + 'Spoke', [hub_pt, rim_pt], 0.0011, M['spoke'], seg=4, caps=False))
        # nipple
        nip_a = rim_pt + (rim_pt - hub_pt).normalized() * -0.004
        spokes.append(sweep(name + 'Nipple', [nip_a, rim_pt + (rim_pt - hub_pt).normalized() * 0.001], 0.0022, M['alu'], seg=5, caps=False))
    parts += spokes
    # valve
    va = math.radians(-90 + 360 / n / 2)
    vdir = Vector((0, math.cos(va), math.sin(va)))
    parts.append(sweep(name + 'Valve', [vdir * 0.296, vdir * 0.268], 0.0028, M['alu'], seg=8))
    if rear:
        parts += build_cassette(M)
    return parts


CASSETTE = (11, 12, 13, 14, 15, 17, 19, 21, 23, 25, 28)
CHAIN_COG = 17
CHAIN_RING = 50


def cog_x(teeth):
    i = CASSETTE.index(teeth)
    return 0.058 - i * 0.0039


def build_cassette(M):
    parts = []
    for i, t in enumerate(CASSETTE):
        x = cog_x(t)
        _, rp = sprocket_outline(t)
        inner_r = 0.0185 if t < 15 else rp * 0.66
        mat = M['alu'] if t <= 12 else M['steel']
        o, _ = gear_ring('Cog%d' % t, t, x, inner_r, mat, thick=0.0018, pts=3, back=(t == CASSETTE[-1]))
        parts.append(o)
        if t >= 15:   # carrier spider visible between the larger cogs
            for k in range(5):
                a = 2 * math.pi * k / 5 + 0.3 * i
                d = Vector((0, math.cos(a), math.sin(a)))
                parts.append(sweep('CogSpider', [Vector((x - 0.0008, 0, 0)) + d * 0.018, Vector((x - 0.0008, 0, 0)) + d * (inner_r + 0.001)],
                                   [(0.0009, 0.004)] * 2, mat, seg=4, up=(1, 0, 0)))
    parts.append(lathe('CassetteBody', [(0.018, 0.018), (0.0185, 0.018), (0.0185, 0.060), (0.018, 0.060)], M['dark_alu'], 16, close=True))
    parts.append(lathe('Lockring', [(0.012, 0.0595), (0.0165, 0.0595), (0.0165, 0.0635), (0.012, 0.0635)], M['alu'], 16, close=True, smooth=False))
    return parts


def build_crankset(M):
    """Crankset centred on BB at local origin, crank angle 0 = right arm up. Returns (crank_parts, pedal_parts_R, pedal_parts_L)."""
    parts = []
    parts.append(sweep('Spindle', [Vector((-0.07, 0, 0)), Vector((0.07, 0, 0))], 0.012, M['dark_alu'], seg=16))
    for s in (1, -1):
        x0 = s * 0.070
        up = 1 if s > 0 else -1   # right arm points up at angle 0, left arm down
        L = CRANK
        outline = [(-0.0175, 0.0), (-0.016, 0.03), (-0.0115, 0.11), (-0.0112, L - 0.004), (-0.0082, L + 0.0085),
                   (0.0, L + 0.0125), (0.0082, L + 0.0085), (0.0112, L - 0.004), (0.0115, 0.11), (0.016, 0.03),
                   (0.0175, 0.0), (0.012, -0.015), (0.0, -0.02), (-0.012, -0.015)]
        outline = [(y, z * up) for y, z in outline]
        if up < 0:
            outline = list(reversed(outline))
        arm = extrude('CrankArm', outline, 0.014, M['black'], origin=(x0 + s * 0.002, 0, 0), u=(0, 1, 0), v=(0, 0, 1), smooth=False)
        bev = arm.modifiers.new('Bevel', 'BEVEL')
        bev.width = 0.003
        bev.segments = 2
        bev.limit_method = 'ANGLE'
        _apply_mods(arm)
        for p in arm.data.polygons:
            p.use_smooth = True
        parts.append(arm)
        parts.append(lathe('CrankBolt', [(0.0, 0.0), (0.011, 0.0), (0.011, 0.003), (0.0, 0.003)], M['alu'], 16, (x0 + s * 0.009, 0, 0), 'X', smooth=False))
    # spider (4 arms) + chainrings
    spider = []
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = Vector((0, math.cos(a), math.sin(a)))
        spider.append(sweep('Spider', [Vector((0.058, 0, 0)) + d * 0.012, Vector((0.054, 0, 0)) + d * 0.078],
                            [(0.0045, 0.009), (0.004, 0.0065)], M['black'], seg=8, up=(1, 0, 0)))
        spider.append(sweep('RingBolt', [Vector((0.044, 0, 0)) + d * 0.0775, Vector((0.056, 0, 0)) + d * 0.0775], 0.0038, M['alu'], seg=8))
    parts += spider
    for teeth, x, inner in ((CHAIN_RING, 0.0515, 0.080), (34, 0.0455, 0.056)):
        o, _ = gear_ring('Chainring%d' % teeth, teeth, x, inner, M['dark_alu'] if teeth == CHAIN_RING else M['alu'], thick=0.0024, pts=3)
        parts.append(o)
        # ring body between teeth band and bolt circle
        parts.append(lathe('RingBody%d' % teeth, [(inner, x + 0.0011), (inner - 0.008, x + 0.0011), (inner - 0.008, x - 0.0011), (inner, x - 0.0011)],
                           M['dark_alu'] if teeth == CHAIN_RING else M['alu'], 32, close=True, smooth=False))
    return parts


def build_pedal(M, side):
    """Flat platform pedal centred on its spindle axis at local origin; side=+1 right, -1 left."""
    parts = []
    parts.append(sweep('PedalAxle', [Vector((side * 0.0, 0, 0)), Vector((side * 0.066, 0, 0))], 0.0065, M['alu'], seg=12))
    cx = side * 0.058
    w, l, h = 0.095, 0.100, 0.016
    # platform as rounded-rectangle ring (concave body) plus cross bar
    outline = []
    for k in range(20):
        a = 2 * math.pi * k / 20
        c, s_ = math.cos(a), math.sin(a)
        outline.append((l / 2 * math.copysign(abs(c) ** 0.35, c), h / 2 * math.copysign(abs(s_) ** 0.6, s_)))
    for dx in (-w / 2 + 0.005, w / 2 - 0.005):
        parts.append(extrude('PedalSide', outline, 0.010, M['black'], origin=(cx + dx, 0, 0), u=(0, 1, 0), v=(0, 0, 1), smooth=True))
    for dy in (-l / 2 + 0.004, l / 2 - 0.004):
        parts.append(box('PedalEdge', (cx, dy, 0), (w, 0.008, h * 0.9), M['black']))
    parts.append(box('PedalBody', (cx, 0, 0), (w * 0.9, 0.022, 0.012), M['black']))
    # traction pins
    for dx in (-0.038, -0.013, 0.013, 0.038):
        for dy in (-0.047, 0.047):
            for dz in (-1, 1):
                parts.append(sweep('Pin', [Vector((cx + dx, dy, dz * h * 0.45)), Vector((cx + dx, dy, dz * (h * 0.45 + 0.004)))], 0.0012, M['alu'], seg=4, caps=False))
    return parts


def _apply_mods(obj):
    ctx = bpy.context
    with ctx.temp_override(object=obj, active_object=obj):
        for m in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)


def chain_path():
    """Chain centre-line (world): big ring top -> 17T cog -> derailleur pulleys (S-bend) -> ring bottom."""
    ring_r = 0.0127 / (2 * math.sin(math.pi / CHAIN_RING))
    cog_r = 0.0127 / (2 * math.sin(math.pi / CHAIN_COG))
    jr = 0.0127 / (2 * math.sin(math.pi / 11))
    ring_c = Vector((0, BB.y, BB.z))
    cog_c = Vector((0, R_AXLE.y, R_AXLE.z))
    up_p = cog_c + Vector((0, -0.004, -0.062))       # guide pulley centre
    lo_p = cog_c + Vector((0, 0.024, -0.128))        # tension pulley centre

    def arc(c, r, a0, a1, n):
        return [c + Vector((0, r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), r * math.sin(math.radians(a0 + (a1 - a0) * i / n))))
                for i in range(n + 1)]
    pts = []
    pts += arc(ring_c, ring_r, -98, 92, 40)          # front: bottom -> front -> top
    pts += arc(cog_c, cog_r, 92, 262, 14)             # rear cog: top -> back -> bottom
    pts += arc(up_p, jr, 130, -20, 9)                 # guide pulley: over the top, down its front
    pts += arc(lo_p, jr, 175, 272, 7)                 # tension pulley: back -> bottom
    pts.append(pts[0])
    out = []
    for p in pts:
        f = max(0.0, min(1.0, (BB.y - p.y) / (BB.y - R_AXLE.y)))
        out.append(Vector((0.0515 + (cog_x(CHAIN_COG) - 0.0515) * f, p.y, p.z)))
    return out, up_p, lo_p, jr


def build_chain_and_derailleurs(M):
    pts, up_p, lo_p, jr = chain_path()
    seg_len = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seg_len)
    n = int(round(total / 0.0127))
    n -= n % 2
    samples = []
    acc, j = 0.0, 0
    for i in range(n):
        d = i * total / n
        while j < len(seg_len) - 1 and acc + seg_len[j] < d:
            acc += seg_len[j]
            j += 1
        t = (d - acc) / seg_len[j] if seg_len[j] else 0
        samples.append(pts[j].lerp(pts[j + 1], t))
    samples.append(samples[0])
    # figure-8 side plates (flat, double sided), alternating inner/outer
    verts, faces = [], []
    shape = [(-0.0036, 0.0), (-0.0012, 0.0037), (0.00635, 0.0027), (0.0139, 0.0037), (0.0163, 0.0),
             (0.0139, -0.0037), (0.00635, -0.0027), (-0.0012, -0.0037)]
    for i in range(n):
        a, b = samples[i], samples[i + 1]
        dn = (b - a).normalized()
        nz = Vector((1, 0, 0)).cross(dn).normalized()
        outer = i % 2 == 0
        k = 1.12 if outer else 1.0
        for side in (-1, 1):
            xo = Vector((side * (0.0041 if outer else 0.0029), 0, 0))
            base = len(verts)
            for (u, v) in shape:
                verts.append(a + xo + dn * u + nz * v * k)
            faces.append(tuple(range(base, base + len(shape))))
    parts = [new_mesh('ChainPlates', verts, faces, M['steel'], smooth=False)]
    parts.append(sweep('ChainRollers', samples, 0.0034, M['steel'], seg=4, caps=False, up=(1, 0, 0), twist=math.pi / 4))
    x = cog_x(CHAIN_COG)
    # rear derailleur: jockey wheels, slim cage plates, parallelogram body, knuckles
    for c in (up_p, lo_p):
        o, _ = gear_ring('Jockey', 11, x, 0.006, M['black'], thick=0.0026, pts=3, center=c)
        parts.append(o)
        parts.append(sweep('JockeyBolt', [Vector((x - 0.009, c.y, c.z)), Vector((x + 0.009, c.y, c.z))], 0.0045, M['alu'], seg=10))
    uy, uz = (lo_p.y - up_p.y), (lo_p.z - up_p.z)
    L = math.hypot(uy, uz)
    uy, uz = uy / L, uz / L
    ny, nz_ = -uz, uy
    for sgn, mat, r1, r2 in ((1, M['dark_alu'], 0.0115, 0.0125), (-1, M['black'], 0.0095, 0.0105)):
        outline = []
        for k in range(9):
            t = math.pi * k / 8
            outline.append((up_p.y + r1 * (math.cos(t) * ny - math.sin(t) * uy), up_p.z + r1 * (math.cos(t) * nz_ - math.sin(t) * uz)))
        for k in range(9):
            t = math.pi * k / 8
            outline.append((lo_p.y + r2 * (-math.cos(t) * ny + math.sin(t) * uy), lo_p.z + r2 * (-math.cos(t) * nz_ + math.sin(t) * uz)))
        parts.append(extrude('RDCage', outline, 0.0018, mat, origin=(x + sgn * 0.0068, 0, 0), u=(0, 1, 0), v=(0, 0, 1), smooth=False))
    knuckle = Vector((0.074, R_AXLE.y + 0.006, R_AXLE.z - 0.022))
    p_knuckle = Vector((x + 0.014, up_p.y - 0.004, up_p.z + 0.014))
    body = catmull([Vector((0.068, R_AXLE.y + 0.004, R_AXLE.z - 0.006)), knuckle, knuckle.lerp(p_knuckle, 0.5) + Vector((0.006, -0.016, 0.0)), p_knuckle], 4)
    parts.append(sweep('RDBody', body, [(0.0075, 0.0105)] * len(body), M['dark_alu'], seg=10, up=(1, 0, 0)))
    parts.append(sweep('RDPlate', [knuckle.lerp(p_knuckle, 0.3) + Vector((0.009, -0.008, 0)), knuckle.lerp(p_knuckle, 0.7) + Vector((0.01, -0.012, 0))],
                       [(0.003, 0.013)] * 2, M['black'], seg=8, up=(1, 0, 0)))
    parts.append(sweep('RDKnuckle', [p_knuckle + Vector((-0.012, 0, 0)), p_knuckle + Vector((0.004, 0, 0))], 0.008, M['black'], seg=10))
    parts.append(sweep('RDHanger', [Vector((0.0655, R_AXLE.y + 0.002, R_AXLE.z - 0.004)), knuckle + Vector((-0.004, 0, 0.004))], 0.0055, M['black'], seg=8))
    # front derailleur: clamp band on the seat tube + curved cage above the big ring
    ring_r = 0.0127 / (2 * math.sin(math.pi / CHAIN_RING))
    fd_c = BB + ST_UP * 0.158
    band = lathe('FDClamp', [(0.0178, -0.007), (0.0196, -0.007), (0.0196, 0.007), (0.0178, 0.007)], M['dark_alu'], 16, (0, 0, 0), 'Z', close=True)
    _orient_to_axis(band, Vector((0, 0, 0)), ST_UP)
    band.data.transform(Matrix.Translation(fd_c))
    parts.append(band)
    for sgn, h in ((1, 0.020), (-1, 0.014)):
        arc_o = []
        for k in range(8):
            a = math.radians(62 + 58 * k / 7)
            arc_o.append(((ring_r + 0.004) * math.cos(a), (ring_r + 0.004) * math.sin(a)))
        for k in range(8):
            a = math.radians(120 - 58 * k / 7)
            arc_o.append(((ring_r + 0.004 + h) * math.cos(a), (ring_r + 0.004 + h) * math.sin(a)))
        parts.append(extrude('FDCage', arc_o, 0.0016, M['dark_alu'], origin=(0.0515 + sgn * 0.0055, BB.y, BB.z), u=(0, 1, 0), v=(0, 0, 1)))
    cage_top = Vector((0.057, BB.y + (ring_r + 0.022) * math.cos(math.radians(95)), BB.z + (ring_r + 0.022) * math.sin(math.radians(95))))
    parts.append(sweep('FDBody', [fd_c + Vector((0.017, 0.006, 0.0)), cage_top + Vector((-0.004, 0.004, 0.008)), cage_top + Vector((0.004, 0.0, 0.0))],
                       [(0.006, 0.008), (0.006, 0.007), (0.005, 0.006)], M['dark_alu'], seg=8, up=(1, 0, 0)))
    return parts


def build_saddle(M, top):
    """Saddle + rails + seatpost head; 'top' is the saddle top above the clamp."""
    parts = []
    L = 0.270
    nu, nv = 30, 14
    verts, faces = [], []
    def width(u):   # u: 0 = nose, 1 = tail
        return 0.018 + 0.056 * (1 / (1 + math.exp(-(u - 0.52) * 11))) - 0.006 * max(0, u - 0.93) / 0.07
    def height(u, v):  # v in -1..1 across
        base = 0.006 * math.sin(math.pi * u) - 0.012 * (1 - u) ** 3 + 0.010 * max(0, u - 0.8)
        return base - 0.006 * v * v * (0.4 + u)
    rows = []
    for i in range(nu + 1):
        u = i / nu
        y = L * (0.43 - u)            # nose at +y, tail at -y (clamp near the middle)
        w = width(u)
        row = []
        for j in range(nv + 1):
            v = -1 + 2 * j / nv
            x = w * math.sin(v * math.pi / 2)
            z = height(u, v) - 0.010 * (1 - math.cos(v * math.pi / 2)) ** 1.5
            row.append(Vector((x, y, z)))
        rows.append(row)
    # top surface
    for i in range(nu + 1):
        for j in range(nv + 1):
            verts.append(rows[i][j])
    # bottom (shell) surface
    for i in range(nu + 1):
        for j in range(nv + 1):
            p = rows[i][j]
            verts.append(Vector((p.x * 0.9, p.y * 0.97, p.z - 0.018 + 0.004 * abs(p.x) / 0.07)))
    off = (nu + 1) * (nv + 1)
    idx = lambda i, j: i * (nv + 1) + j
    for i in range(nu):
        for j in range(nv):
            faces.append((idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)))
            faces.append((off + idx(i, j), off + idx(i, j + 1), off + idx(i + 1, j + 1), off + idx(i + 1, j)))
    for i in range(nu):
        for j in (0, nv):
            a, b = idx(i, j), idx(i + 1, j)
            faces.append((a, off + a, off + b, b) if j == 0 else (a, b, off + b, off + a))
    for j in range(nv):
        for i in (0, nu):
            a, b = idx(i, j), idx(i, j + 1)
            faces.append((a, b, off + b, off + a) if i == 0 else (a, off + a, off + b, b))
    sad = new_mesh('SaddleShell', [top + v for v in verts], faces, M['saddle'], smooth=True)
    parts.append(sad)
    # rails
    for s in (1, -1):
        rail = catmull([top + Vector((s * 0.012, 0.10, -0.012)), top + Vector((s * 0.022, 0.05, -0.030)),
                        top + Vector((s * 0.024, -0.03, -0.032)), top + Vector((s * 0.03, -0.085, -0.022)),
                        top + Vector((s * 0.034, -0.105, -0.012))], 4)
        parts.append(sweep('Rail', rail, 0.0035, M['alu'], seg=6))
    # seatpost head clamp
    parts.append(box('PostClamp', top + Vector((0, 0.0, -0.036)), (0.058, 0.04, 0.012), M['black']))
    return parts


def build_bike(M, saddle_height=0.70):
    """Return dict of node name -> (world-space parts list, pivot/transform info)."""
    frame, info = build_frame(M)
    parts_frame = [frame]
    s_top = saddle_top(saddle_height)
    post_top = s_top + Vector((0, 0.0, -0.040))
    post_bottom = BB + ST_UP * 0.32
    parts_frame.append(sweep('Seatpost', [post_bottom, post_top], 0.0136, M['black'], seg=16))
    parts_frame.append(lathe('SeatClamp', [(0.0168, -0.009), (0.0192, -0.009), (0.0192, 0.009), (0.0168, 0.009)], M['black'], 20, (0, 0, 0), 'Z', close=True))
    _orient_to_axis(parts_frame[-1], Vector((0, 0, 0)), ST_UP)
    parts_frame[-1].data.transform(Matrix.Translation(info['st_top'] + ST_UP * 0.004))
    parts_frame += build_saddle(M, s_top)
    parts_frame += build_chain_and_derailleurs(M)
    bridge = info['bridge']
    parts_frame += build_caliper(M, bridge + Vector((0, -0.010, 0.0)), Vector((0, -1, 0)), 'RearBrake')
    # bottle cage
    cage_base = BB + (HT_BOT - BB) * 0.22 + Vector((0, 0, 0.026))
    dtd = (HT_BOT - BB).normalized()
    for s in (1, -1):
        rail = catmull([cage_base + Vector((s * 0.02, 0, 0)), cage_base + dtd * 0.06 + Vector((s * 0.034, 0, 0.03)),
                        cage_base + dtd * 0.13 + Vector((s * 0.03, 0, 0.034)), cage_base + dtd * 0.16 + Vector((s * 0.012, 0, 0.012))], 4)
        parts_frame.append(sweep('Cage', rail, 0.0028, M['black'], seg=6))

    fork = build_fork(M)
    cockpit, tape, hoods, housing = build_cockpit(M)
    front_caliper = build_caliper(M, HT_BOT + HT_DOWN * 0.018 + _rake_dir * 0.028, _rake_dir, 'FrontBrake')
    fork_parts = [fork] + cockpit + tape + hoods + housing + front_caliper

    front = build_wheel(M, 'Front', rear=False)
    rear = build_wheel(M, 'Rear', rear=True)
    crank = build_crankset(M)
    pedal_r = build_pedal(M, 1)
    pedal_l = build_pedal(M, -1)
    return dict(frame=parts_frame, fork=fork_parts, front=front, rear=rear, crank=crank, pedal_r=pedal_r, pedal_l=pedal_l)


def assemble_bike(M, saddle_height=0.70, parent=None):
    """Build and organise the bike into named nodes. Returns dict of nodes."""
    groups = build_bike(M, saddle_height)
    col = bpy.context.scene.collection

    def empty(name, matrix, par):
        e = bpy.data.objects.new(name, None)
        e.empty_display_size = 0.05
        col.objects.link(e)
        e.parent = par
        e.matrix_parent_inverse = Matrix.Identity(4)
        e.matrix_basis = matrix
        return e

    def bind(parts, name, node, world_to_local):
        ob = join(parts, name)
        ob.data.transform(world_to_local)
        ob.parent = node
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_basis = Matrix.Identity(4)
        return ob

    bike = empty('Bike', Matrix.Identity(4), parent)
    bind(groups['frame'], 'FrameMesh', bike, Matrix.Identity(4))

    # steering: SteerAxis local +Z along the head tube axis (up), origin at the head tube centre
    ht_mid = (HT_TOP + HT_BOT) / 2
    q = Vector((0, 0, 1)).rotation_difference(HT_UP)
    steer_m = Matrix.Translation(ht_mid) @ q.to_matrix().to_4x4()
    steer = empty('SteerAxis', steer_m, bike)
    fork = empty('Fork', Matrix.Identity(4), steer)
    inv = steer_m.inverted()
    bind(groups['fork'], 'ForkMesh', fork, inv)
    fa_local = inv @ F_AXLE
    # FrontWheel: X axis stays the world axle axis. Local rotation = inverse of steer tilt.
    fw_m = Matrix.Translation(fa_local) @ q.inverted().to_matrix().to_4x4()
    fwheel = empty('FrontWheel', fw_m, fork)
    bind(groups['front'], 'FrontWheelMesh', fwheel, Matrix.Identity(4))
    for name, side in (('HoodL', -1), ('HoodR', 1)):
        p = Vector((side * HOOD_GRIP.x, HOOD_GRIP.y, HOOD_GRIP.z))
        empty(name, Matrix.Translation(inv @ p) @ q.inverted().to_matrix().to_4x4(), fork)

    rwheel = empty('RearWheel', Matrix.Translation(R_AXLE), bike)
    bind(groups['rear'], 'RearWheelMesh', rwheel, Matrix.Identity(4))

    crank = empty('Crankset', Matrix.Translation(BB), bike)
    bind(groups['crank'], 'CranksetMesh', crank, Matrix.Identity(4))
    pr = empty('PedalR', Matrix.Translation(Vector((0.0785, 0, CRANK))), crank)
    bind(groups['pedal_r'], 'PedalRMesh', pr, Matrix.Identity(4))
    pl = empty('PedalL', Matrix.Translation(Vector((-0.0785, 0, -CRANK))), crank)
    bind(groups['pedal_l'], 'PedalLMesh', pl, Matrix.Identity(4))
    return dict(bike=bike, steer=steer, fork=fork, front=fwheel, rear=rwheel, crank=crank, pedal_r=pr, pedal_l=pl)
