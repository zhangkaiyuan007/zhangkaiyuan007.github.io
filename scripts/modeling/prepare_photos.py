"""Display copies of the large reference photos: the page shows them a few hundred pixels wide, and a 16-megapixel
original costs ~64 MB of memory once decoded (too much on a phone). The originals stay for the "open original" links.

    python3 scripts/modeling/prepare_photos.py

Writes static/ride/references/display/<same path>.jpg for every photo over MAX px; keep DISPLAY in
static/ride/stations.js in sync with the list it prints.
"""
from pathlib import Path
from PIL import Image, ImageOps

REF = Path(__file__).resolve().parents[2] / 'static/ride/references'
MAX = 1600

for p in sorted(REF.rglob('*')):
    if p.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp') or 'display' in p.relative_to(REF).parts:
        continue
    im = ImageOps.exif_transpose(Image.open(p))
    if max(im.size) <= MAX:
        continue
    out = REF / 'display' / p.relative_to(REF).with_suffix('.jpg')
    out.parent.mkdir(parents=True, exist_ok=True)
    im.thumbnail((MAX, MAX), Image.LANCZOS)
    im.convert('RGB').save(out, 'JPEG', quality=84, optimize=True, progressive=True)
    print(f"'{p.relative_to(REF)}'  {p.stat().st_size // 1024} KB -> {out.relative_to(REF)} {im.size[0]}x{im.size[1]} {out.stat().st_size // 1024} KB")
