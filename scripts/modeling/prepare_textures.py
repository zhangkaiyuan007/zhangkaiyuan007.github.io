"""Build the ride's PBR texture sets in static/ride/textures/<name>/.

    python3 scripts/modeling/fetch_props.py      # once, outside the network sandbox
    python3 scripts/modeling/prepare_textures.py

Sources are Poly Haven CC0 texture sets cached by fetch_props.py (1k JPEGs).
Only the maps the page uses are written, re-encoded at <= 1024 px: diff.jpg (sRGB albedo),
nor.jpg (OpenGL / +Y normal, which three.js expects) and rough.jpg (linear, single-channel).
"""
from pathlib import Path
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.tools/assets-cache/polyhaven'
OUT = ROOT / 'static/ride/textures'
SIZE = 1024
QUALITY = {'diff': 84, 'nor': 88, 'rough': 78}

# name -> (source id, human label, maps); must match SETS in static/ride/props.js
SETS = {
    'asphalt': ('clean_asphalt', 'road asphalt', ['diff', 'nor', 'rough']),
    'paving': ('concrete_pavers_02', 'riverside / city concrete pavers', ['diff', 'nor', 'rough']),
    'granite': ('granite_tile_03', 'grey flamed-granite slabs for steps and quay tops', ['diff', 'nor', 'rough']),
    'brick': ('red_brick', 'red brick wall', ['diff', 'nor', 'rough']),
    'plaster': ('painted_plaster_wall', 'painted plaster facade', ['diff', 'nor', 'rough']),
    'grass': ('ambientcg:Grass004', 'mown lawn / grass ground', ['diff', 'nor']),
}


def save(img, path, q):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, 'JPEG', quality=q, optimize=True, progressive=True)


ACG = ROOT / '.tools/assets-cache/ambientcg'
ACG_MAPS = {'diff': 'Color', 'nor': 'NormalGL', 'rough': 'Roughness'}


def source_file(pid, short):
    if pid.startswith('ambientcg:'):
        a = pid.split(':')[1]
        f = ACG / a / f'{a}_1K-JPG_{ACG_MAPS[short]}.jpg'
        return f if f.exists() else None
    return next(iter(sorted((CACHE / pid / '1k').glob(short + '.*'))), None)


def source_info(pid):
    if pid.startswith('ambientcg:'):
        a = pid.split(':')[1]
        d = json.loads((ACG / f'{a}.json').read_text())['foundAssets'][0]
        return {'authors': {'ambientCG (Lennart Demes)': 'All'}, 'dimensions': [d['dimensionX'] * 10, d['dimensionY'] * 10],
                'url': f'https://ambientcg.com/view?id={a}'}
    info = json.loads((CACHE / pid / 'info.json').read_text())
    info['url'] = f'https://polyhaven.com/a/{pid}'
    return info


def build_set(name, pid, wanted):
    info = source_info(pid)
    out = OUT / name
    maps = []
    for short in wanted:
        f = source_file(pid, short)
        if f is None:
            continue
        im = Image.open(f)
        mode = 'RGB' if short in ('diff', 'nor') else 'L'
        im = im.convert(mode)
        if max(im.size) > SIZE:
            im = im.resize((SIZE, SIZE * im.size[1] // im.size[0]), Image.LANCZOS)
        save(im, out / f'{short}.jpg', QUALITY[short])
        maps.append(short)
    dims = info.get('dimensions')  # millimetres [w, h]
    return {'source': pid, 'url': info['url'], 'maps': maps,
            'size_m': [round(d / 1000, 3) for d in dims] if dims else None,
            'authors': list(info.get('authors', {}).keys())}


def write_source_md(manifest):
    size = lambda n: sum((OUT / n / f'{m}.jpg').stat().st_size for m in manifest[n]['maps'])
    lines = ['# Ride texture sets: sources and licences', '',
             'Each folder holds `diff.jpg` (sRGB albedo), `nor.jpg` (tangent-space normal, OpenGL / +Y convention as three.js expects),',
             '`rough.jpg` (linear, greyscale). All are 1024 x 1024 JPEG and tile seamlessly.',
             'Loaded by `loadTextureSet(name)` in `static/ride/props.js`, which also sets how many metres one repeat covers.',
             'Rebuild: `python3 scripts/modeling/fetch_props.py && python3 scripts/modeling/prepare_textures.py`.', '',
             '| set | use | source | authors | licence | downloaded | tile (m) | maps | size |',
             '|---|---|---|---|---|---|---|---|---|']
    for name, m in manifest.items():
        src = m['source']
        if src.startswith('ambientcg:'):
            source, lic, dl = f"[ambientCG {src.split(':')[1]}]({m['url']})", 'CC0 1.0', '1K-JPG zip'
        else:
            source, lic, dl = f"[Poly Haven `{src}`]({m['url']})", 'CC0 1.0', '1k JPG'
        tile = 'x'.join(f'{v:g}' for v in m['size_m']) if m['size_m'] else '-'
        lines.append(f"| `{name}` | {m['label']} | {source} | {', '.join(m['authors']) or '-'} | {lic} | {dl} | {tile} | "
                     f"{', '.join(m['maps'])} | {size(name) / 1024:.0f} KB |")
    total = sum(size(n) for n in manifest)
    lines += ['', f'Total: {total / 1e6:.2f} MB.', '',
              'Changes: sources were already 1024 px; every map was re-encoded (diff q84, nor q88, rough q78 greyscale).',
              'The Poly Haven normal maps used are the `nor_gl` (OpenGL) variants; ambientCG `NormalGL` likewise.', '']
    (OUT / 'SOURCE.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    manifest = {}
    for name, (pid, label, wanted) in SETS.items():
        manifest[name] = build_set(name, pid, wanted) | {'label': label}
        print(name, manifest[name])
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    write_source_md(manifest)
