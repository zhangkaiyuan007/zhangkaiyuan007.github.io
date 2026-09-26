"""Download the Poly Haven (CC0) sources for the ride props and texture sets.

Run with plain python3 outside any network sandbox:
    python3 scripts/modeling/fetch_props.py
Everything lands in the git-ignored .tools/assets-cache/polyhaven/<id>/ and is
skipped when already present, so re-running is cheap.  Processing happens in
prepare_props.py (Blender) and prepare_textures.py (python3 + Pillow/NumPy).
"""
from pathlib import Path
import json, sys, urllib.request

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '.tools/assets-cache/polyhaven'

# Models: glTF at 1k (textures are 1024 px; the trees' leaf atlas is re-rendered anyway).
MODELS = [
    'jacaranda_tree', 'tree_small_02', 'island_tree_01',
    'street_lamp_01', 'modular_street_seating', 'planter_box_01',
    'cardboard_box_01', 'plastic_crate_02',
    'long_life_food', 'all_purpose_cleaner',
]
# Texture sets: output name -> Poly Haven id.
TEXTURES = {
    'asphalt': 'clean_asphalt',
    'paving': 'concrete_pavers_02',
    'granite': 'granite_tile_03',
    'brick': 'red_brick',
    'plaster': 'painted_plaster_wall',
}
TEX_MAPS = {'Diffuse': 'diff', 'nor_gl': 'nor', 'Rough': 'rough'}
# ambientCG (CC0) fills the one gap Poly Haven has: a green, mown lawn.
AMBIENTCG = ['Grass004']
ACG_CACHE = ROOT / '.tools/assets-cache/ambientcg'
UA = {'User-Agent': 'zhangkaiyuan007.github.io asset prep (personal portfolio)'}


def get(url, dest=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    if dest:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return data


def fetch_info(asset_id):
    d = CACHE / asset_id
    d.mkdir(parents=True, exist_ok=True)
    info, files = d / 'info.json', d / 'files.json'
    if not info.exists():
        get(f'https://api.polyhaven.com/info/{asset_id}', info)
    if not files.exists():
        get(f'https://api.polyhaven.com/files/{asset_id}', files)
    return json.loads(info.read_text()), json.loads(files.read_text())


def fetch_model(asset_id, res='1k'):
    _, files = fetch_info(asset_id)
    entry = files['gltf'][res]['gltf']
    out = CACHE / asset_id / res
    todo = [(entry['url'], out / Path(entry['url']).name)]
    todo += [(v['url'], out / rel) for rel, v in entry.get('include', {}).items()]
    for url, dest in todo:
        if dest.exists() and dest.stat().st_size > 0:
            continue
        print('  get', dest.relative_to(CACHE)); sys.stdout.flush()
        get(url, dest)


def fetch_extra_maps(asset_id, res='1k'):
    """Maps the glTF download leaves out (Poly Haven's glTF drops leaf alpha)."""
    _, files = fetch_info(asset_id)
    for key in files:
        if 'alpha' not in key.lower() and key.lower() not in ('opacity',):
            continue
        e = files[key][res]
        e = e.get('png') or e.get('jpg')
        dest = CACHE / asset_id / res / 'textures' / Path(e['url']).name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        print('  get', dest.relative_to(CACHE)); sys.stdout.flush()
        get(e['url'], dest)


def fetch_texture(asset_id, res='1k'):
    _, files = fetch_info(asset_id)
    out = CACHE / asset_id / res
    for key, short in TEX_MAPS.items():
        if key not in files:
            continue
        e = files[key][res]
        e = e.get('jpg') or e.get('png')
        dest = out / f'{short}{Path(e["url"]).suffix}'
        if dest.exists() and dest.stat().st_size > 0:
            continue
        print('  get', dest.relative_to(CACHE)); sys.stdout.flush()
        get(e['url'], dest)


def fetch_ambientcg(asset_id, res='1K-JPG'):
    import zipfile
    d = ACG_CACHE / asset_id
    if not (d / f'{asset_id}_{res}_Color.jpg').exists():
        z = ACG_CACHE / f'{asset_id}.zip'
        print('  get', z.name); sys.stdout.flush()
        get(f'https://ambientcg.com/get?file={asset_id}_{res}.zip', z)
        zipfile.ZipFile(z).extractall(d)
    info = ACG_CACHE / f'{asset_id}.json'
    if not info.exists():
        get(f'https://ambientcg.com/api/v2/full_json?id={asset_id}&include=dimensionsData,tagData', info)


if __name__ == '__main__':
    only = set(sys.argv[1:])
    for m in MODELS:
        if not only or m in only:
            print('model', m); fetch_model(m); fetch_extra_maps(m)
    for name, t in TEXTURES.items():
        if not only or t in only or name in only:
            print('texture', name, '<-', t); fetch_texture(t)
    for t in AMBIENTCG:
        if not only or t in only:
            print('ambientCG', t); fetch_ambientcg(t)
    print('done')
