# Ride props: sources and licences

All models are derived from [Poly Haven](https://polyhaven.com) assets, licensed
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain; attribution not required but given here).
Downloaded as the 1k glTF (1024 px textures) via the Poly Haven API, plus the 1k leaf-alpha / opacity PNGs that the glTF omits.
Rebuild: `python3 scripts/modeling/fetch_props.py` then
`./scripts/blender --background --factory-startup --python scripts/modeling/prepare_props.py`.

Conventions: metres, +Y up, origin at the base centre on the ground, Draco-compressed geometry,
JPEG textures (the leaf atlases are 256-colour PNGs because they need alpha; leaves use alphaMode MASK).

| file | source | authors | triangles | size | dimensions (w x h x d m) |
|---|---|---|---|---|---|
| `street_tree_01.glb` | [Tree Small 02](https://polyhaven.com/a/tree_small_02) (`tree_small_02`) | Rico Cilliers | 8,200 | 0.80 MB | 5.58 x 8.01 x 7.83 |
| `street_tree_02.glb` | [Jacaranda Tree](https://polyhaven.com/a/jacaranda_tree) (`jacaranda_tree`) | Rob Tuytel, Rico Cilliers | 9,800 | 0.93 MB | 9.03 x 9.15 x 7.04 |
| `street_tree_03.glb` | [Island Tree 01](https://polyhaven.com/a/island_tree_01) (`island_tree_01`) | Rob Tuytel, Rico Cilliers | 8,398 | 0.89 MB | 6.87 x 6.73 x 6.56 |
| `street_lamp.glb` | [Street Lamp 01](https://polyhaven.com/a/street_lamp_01) (`street_lamp_01`) | Josh Dean | 4,700 | 0.13 MB | 0.70 x 3.87 x 0.39 |
| `park_bench.glb` | [Modular Street Seating](https://polyhaven.com/a/modular_street_seating) (`modular_street_seating`) | Stuart Attenborrow | 4,879 | 0.40 MB | 2.45 x 0.87 x 0.67 |
| `planter.glb` | [Planter Box 01](https://polyhaven.com/a/planter_box_01) (`planter_box_01`) | James Ray Cock | 3,382 | 0.36 MB | 1.28 x 0.99 x 0.77 |
| `goods_cardboard_box.glb` | [Cardboard Box 01](https://polyhaven.com/a/cardboard_box_01) (`cardboard_box_01`) | Rahul Chaudhary | 1,800 | 0.16 MB | 0.39 x 0.34 x 0.52 |
| `goods_crate.glb` | [Plastic Crate 02](https://polyhaven.com/a/plastic_crate_02) (`plastic_crate_02`) | Fabi_G | 4,400 | 0.19 MB | 0.51 x 0.25 x 0.41 |
| `goods_cans.glb` | [Long Life Food](https://polyhaven.com/a/long_life_food) (`long_life_food`) | Mia Pecina Zorko | 3,600 | 0.17 MB | 0.52 x 0.24 x 0.11 |
| `goods_cleaner.glb` | [All Purpose Cleaner](https://polyhaven.com/a/all_purpose_cleaner) (`all_purpose_cleaner`) | Kuutti Siitonen | 2,400 | 0.09 MB | 0.16 x 0.32 x 0.12 |

Total: 4.11 MB across 10 GLBs.

### street_tree_01.glb

- Source: https://polyhaven.com/a/tree_small_02 (API id `tree_small_02`), by Rico Cilliers; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 4,652,585 as listed by the API).
- Changes: height 7.6 m (scale 1.668); bark 38479->3400 tris; 2400 leaf-cluster cards from a 1024 px 2x2 atlas rendered from the original leaves.
- Bark: trunk + branches thicker than ~1.2 cm kept, collapse-decimated. Leaves: 2x2 leaf-cluster atlas path-traced from the original leaf cards (albedo x softened AO + camera-space normals), cards placed at the original leaf positions with crown-shaped normals.

### street_tree_02.glb

- Source: https://polyhaven.com/a/jacaranda_tree (API id `jacaranda_tree`), by Rob Tuytel, Rico Cilliers; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 312,356 as listed by the API).
- Changes: height 8.8 m (scale 0.452, xy x0.75); bark 234896->4200 tris; 2800 leaf-cluster cards from a 1024 px 2x2 atlas rendered from the original leaves.
- As street_tree_01; horizontal extent scaled x0.75 to fit a street; branches thinner than ~3 cm dropped.

### street_tree_03.glb

- Source: https://polyhaven.com/a/island_tree_01 (API id `island_tree_01`), by Rob Tuytel, Rico Cilliers; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 3,729,692 as listed by the API).
- Changes: height 6.4 m (scale 1.273); bark 41437->3598 tris; 2400 leaf-cluster cards from a 1024 px 2x2 atlas rendered from the original leaves.
- As street_tree_01; flat root/rock skirt at the base removed.

### street_lamp.glb

- Source: https://polyhaven.com/a/street_lamp_01 (API id `street_lamp_01`), by Josh Dean; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 30,610 as listed by the API).
- Changes: decimated from 30.6k tris; glass alpha 0.28 (BLEND); bulb emissive.
- Collapse-decimated; glass made a constant 0.28-alpha BLEND material; bulb given a warm emissive factor.

### park_bench.glb

- Source: https://polyhaven.com/a/modular_street_seating (API id `modular_street_seating`), by Stuart Attenborrow; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 25,156 as listed by the API).
- Changes: assembled back bench from the modular kit; metal parts decimated ~58%.
- Back bench assembled from the kit parts (legs_single, legs_double, seat, seat_back, back supports, arm rests, crossbar); metal parts decimated; metal textures 512 px.

### planter.glb

- Source: https://polyhaven.com/a/planter_box_01 (API id `planter_box_01`), by James Ray Cock; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 8,094 as listed by the API).
- Changes: planter_box_01 scaled x1.4, decimated from 8.1k tris; added soil plane and a 90-card clipped shrub using the street_tree_03 leaf atlas.
- Scaled x1.4 to street-planter size and decimated; dark soil plane and a clipped shrub of leaf cards (street_tree_03 atlas at 512 px) added.

### goods_cardboard_box.glb

- Source: https://polyhaven.com/a/cardboard_box_01 (API id `cardboard_box_01`), by Rahul Chaudhary; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 16,952 as listed by the API).
- Changes: 16952->1800 tris.
- Decimated; textures 512 px.

### goods_crate.glb

- Source: https://polyhaven.com/a/plastic_crate_02 (API id `plastic_crate_02`), by Fabi_G; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 5,840 as listed by the API).
- Changes: 5840->4400 tris; opacity map restored as alpha MASK.
- Decimated; the separate opacity map (dropped by the glTF download) re-attached as alpha MASK; textures 512 px.

### goods_cans.glb

- Source: https://polyhaven.com/a/long_life_food (API id `long_life_food`), by Mia Pecina Zorko; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 4,712 as listed by the API).
- Changes: 4712->3600 tris.
- Four items (milk carton, two cans, sardine tin) joined; decimated; textures 512 px.

### goods_cleaner.glb

- Source: https://polyhaven.com/a/all_purpose_cleaner (API id `all_purpose_cleaner`), by Kuutti Siitonen; licence CC0 1.0.
- Downloaded: 1k glTF (source polycount 4,624 as listed by the API).
- Changes: 4624->2400 tris.
- Decimated; textures 512 px.
