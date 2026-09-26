"""Re-encode the images embedded in a GLB for the web (python3 + Pillow).

    python3 scripts/modeling/glb_textures.py model.glb [--max 1024] [--rule substr=512 ...]

* colour / data / normal textures -> JPEG (normals at higher quality)
* a baseColor texture on a MASK/BLEND material keeps alpha -> 256-colour PNG
* every image is downscaled to --max px (or the size of the first matching
  --rule, matched against the glTF image name)
Buffer views are re-packed; Draco and accessor data are copied untouched.
"""
import argparse, io, json, struct
from PIL import Image

QUALITY = {'color': 85, 'normal': 90, 'data': 82}


def read_glb(path):
    data = open(path, 'rb').read()
    magic, version, length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67, 'not a GLB'
    off, chunks = 12, []
    while off < length:
        clen, ctype = struct.unpack_from('<II', data, off)
        chunks.append((ctype, data[off + 8: off + 8 + clen]))
        off += 8 + clen
    js = json.loads(chunks[0][1])
    binary = chunks[1][1] if len(chunks) > 1 else b''
    return js, binary


def write_glb(path, js, binary):
    j = json.dumps(js, separators=(',', ':')).encode()
    j += b' ' * (-len(j) % 4)
    binary += b'\0' * (-len(binary) % 4)
    total = 12 + 8 + len(j) + (8 + len(binary) if binary else 0)
    out = struct.pack('<III', 0x46546C67, 2, total) + struct.pack('<II', len(j), 0x4E4F534A) + j
    if binary:
        out += struct.pack('<II', len(binary), 0x004E4942) + binary
    open(path, 'wb').write(out)


def image_roles(js):
    roles = {}
    tex = js.get('textures', [])

    def mark(info, role):
        if info is None:
            return
        src = tex[info['index']].get('source')
        if src is None:  # e.g. EXT_texture_webp only
            return
        # alpha colour wins over plain colour, colour wins over data
        order = ['data', 'normal', 'color', 'color_alpha']
        if src not in roles or order.index(role) > order.index(roles[src]):
            roles[src] = role

    for m in js.get('materials', []):
        pbr = m.get('pbrMetallicRoughness', {})
        alpha = m.get('alphaMode', 'OPAQUE') != 'OPAQUE'
        mark(pbr.get('baseColorTexture'), 'color_alpha' if alpha else 'color')
        mark(pbr.get('metallicRoughnessTexture'), 'data')
        mark(m.get('normalTexture'), 'normal')
        mark(m.get('occlusionTexture'), 'data')
        mark(m.get('emissiveTexture'), 'color')
    return roles


def encode(img, role, limit):
    if max(img.size) > limit:
        s = limit / max(img.size)
        img = img.resize((max(1, round(img.size[0] * s)), max(1, round(img.size[1] * s))), Image.LANCZOS)
    buf = io.BytesIO()
    if role == 'color_alpha' and img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGBA')
        q = img.quantize(colors=256, method=2, dither=0)  # 2 = FASTOCTREE (keeps alpha)
        q.save(buf, 'PNG', optimize=True)
        return buf.getvalue(), 'image/png', img.size
    img = img.convert('RGB')
    img.save(buf, 'JPEG', quality=QUALITY.get(role, 85), optimize=True, progressive=True)
    return buf.getvalue(), 'image/jpeg', img.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('glb')
    ap.add_argument('--max', type=int, default=1024)
    ap.add_argument('--rule', action='append', default=[], help='substr=maxpx, matched on image name')
    a = ap.parse_args()
    rules = [(r.split('=')[0], int(r.split('=')[1])) for r in a.rule]
    js, binary = read_glb(a.glb)
    roles = image_roles(js)
    views = js.get('bufferViews', [])
    replace = {}
    report = []
    for i, im in enumerate(js.get('images', [])):
        if 'bufferView' not in im:
            continue
        bv = views[im['bufferView']]
        raw = binary[bv.get('byteOffset', 0): bv.get('byteOffset', 0) + bv['byteLength']]
        name = im.get('name', f'image{i}')
        limit = next((px for sub, px in rules if sub in name), a.max)
        role = roles.get(i, 'color')
        data, mime, size = encode(Image.open(io.BytesIO(raw)), role, limit)
        replace[im['bufferView']] = data
        im['mimeType'] = mime
        report.append(f'{name}: {role} {size[0]}x{size[1]} {mime.split("/")[1]} {len(raw) // 1024}->{len(data) // 1024} KB')
    out = bytearray()
    for k, bv in enumerate(views):
        chunk = replace.get(k)
        if chunk is None:
            s = bv.get('byteOffset', 0)
            chunk = binary[s: s + bv['byteLength']]
        out += b'\0' * (-len(out) % 4)
        bv['byteOffset'] = len(out)
        bv['byteLength'] = len(chunk)
        out += chunk
    if js.get('buffers'):
        js['buffers'][0]['byteLength'] = len(out)
    write_glb(a.glb, js, bytes(out))
    for line in report:
        print('  ', line)


if __name__ == '__main__':
    main()
