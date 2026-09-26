# Ride texture sets: sources and licences

Each folder holds `diff.jpg` (sRGB albedo), `nor.jpg` (tangent-space normal, OpenGL / +Y convention as three.js expects),
`rough.jpg` (linear, greyscale). All are 1024 x 1024 JPEG and tile seamlessly.
Loaded by `loadTextureSet(name)` in `static/ride/props.js`, which also sets how many metres one repeat covers.
Rebuild: `python3 scripts/modeling/fetch_props.py && python3 scripts/modeling/prepare_textures.py`.

| set | use | source | authors | licence | downloaded | tile (m) | maps | size |
|---|---|---|---|---|---|---|---|---|
| `asphalt` | road asphalt | [Poly Haven `clean_asphalt`](https://polyhaven.com/a/clean_asphalt) | Dimitrios Savva | CC0 1.0 | 1k JPG | 2.1x2.1 | diff, nor, rough | 443 KB |
| `paving` | riverside / city concrete pavers | [Poly Haven `concrete_pavers_02`](https://polyhaven.com/a/concrete_pavers_02) | Amal Kumar | CC0 1.0 | 1k JPG | 2x2 | diff, nor, rough | 329 KB |
| `granite` | grey flamed-granite slabs for steps and quay tops | [Poly Haven `granite_tile_03`](https://polyhaven.com/a/granite_tile_03) | Charlotte Baglioni | CC0 1.0 | 1k JPG | 1.802x1.802 | diff, nor, rough | 530 KB |
| `brick` | red brick wall | [Poly Haven `red_brick`](https://polyhaven.com/a/red_brick) | Rob Tuytel | CC0 1.0 | 1k JPG | 1.4x1.4 | diff, nor, rough | 504 KB |
| `plaster` | painted plaster facade | [Poly Haven `painted_plaster_wall`](https://polyhaven.com/a/painted_plaster_wall) | Amal Kumar | CC0 1.0 | 1k JPG | 2x2 | diff, nor, rough | 409 KB |
| `grass` | mown lawn / grass ground | [ambientCG Grass004](https://ambientcg.com/view?id=Grass004) | ambientCG (Lennart Demes) | CC0 1.0 | 1K-JPG zip | 1.4x1.4 | diff, nor | 768 KB |

Total: 3.05 MB.

Changes: sources were already 1024 px; every map was re-encoded (diff q84, nor q88, rough q78 greyscale).
The Poly Haven normal maps used are the `nor_gl` (OpenGL) variants; ambientCG `NormalGL` likewise.
