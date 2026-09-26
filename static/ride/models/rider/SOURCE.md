# Rider and road bike

Rigged cyclist on an orange road bike, built in Blender 4.5.14 LTS with MPFB 2.0.17 on 2026-09-24.
Rebuild: `scripts/modeling/setup_rider.sh`, then
`./scripts/blender --background --factory-startup --python scripts/modeling/build_rider.py -- [--render]`
(bike geometry in `scripts/modeling/rider_bike.py`).

Web asset: `rider.glb` (Draco compressed, textures embedded: JPEG, plus two small PNGs where alpha is needed for eyebrows and eyelashes). Preview stills: `preview-side.jpg`, `preview-front.jpg`, `preview-closeup.jpg` (Cycles renders of this model).

## Tools

- Blender 4.5.14 LTS (GPL-2.0-or-later), used as a tool.
- [MPFB 2.0.17](https://extensions.blender.org/add-ons/mpfb/) (MakeHuman plugin for Blender), GPL-3.0-or-later, used as a tool; none of its code is in the output. Archive `add-on-mpfb-v2.0.17.zip`, SHA-256 `4f0a879d64a39bf646fbf5f53601ac678855da329d650617dca5737548239a87`.

## Assets used

All MakeHuman assets come from the MakeHuman community [asset packs](https://static.makehumancommunity.org/assets/assetpacks.html). Checksums of the pack archives are pinned in `setup_rider.sh`.

| Part | Asset | Author | Source | License | What was changed |
| --- | --- | --- | --- | --- | --- |
| Body shape, skeleton, skin weights | MakeHuman base mesh `hm08`, modelling targets, `game_engine` skeleton and weights | MakeHuman team (Data Collection AB, Joel Palmius, Jonas Hauquier) | bundled with MPFB 2.0.17 | CC0 1.0 (released 2020; stated in the file headers / weight files) | Macro settings: male, early twenties, East Asian, slim, 175 cm. A few face targets (jaw, chin, lips, brows, neck). Hidden body parts removed. Posed on the bike and re-bound in the riding pose |
| Skin | `young_asian_male` | makehuman_system | MakeHuman system assets pack | CC0 1.0 | Tone adjusted. A buzz cut, a grey crew-neck T-shirt and a roughness map are painted procedurally into the texture |
| Eyes | `high-poly` eyes, `brown` iris texture | makehuman_system | MakeHuman system assets pack | CC0 1.0 | Transparent cornea shell removed |
| Eyebrows, eyelashes | `eyebrow010`, `eyelashes01` | makehuman_system | MakeHuman system assets pack | CC0 1.0 | Tinted near-black, downscaled |
| Shoes | `shoes05` | makehuman_system | MakeHuman system assets pack | CC0 1.0 | Recoloured into plain white sneakers. The dark side stripes of the original texture are removed |
| Trousers | `toigo_wool_pants` (Pants_Wool) | MargaretToigo | pants01 pack, [asset page](http://www.makehumancommunity.org/node/1194) | CC0 1.0 | Recoloured near-black. Fabric pressed onto the saddle. Parts hidden under the jacket removed |
| Jacket | `elvs_hooded_sweat_jacket1` ("Hooded sweat jacket") | **Elvaerwyn** | shirts02 pack, [asset page](http://www.makehumancommunity.org/node/1450) | **CC-BY** (Creative Commons Attribution; the MakeHuman asset FAQ links this option to [CC BY 2.5 SE](https://creativecommons.org/licenses/by/2.5/se/deed.en)) | Recoloured to an orange shell (#e96a2d). A small plain white half-disc (no text or logo) added on the back of the right shoulder. The lowered hood and its drawstrings were removed and replaced by a raised hood built around the head (`add_hood()` in `build_rider.py`), textured with a plain patch of the same jacket texture. Fitted tighter, decimated, skin weights smoothed, folds relaxed in the riding pose |
| Bike | Original procedural model | this repository | `scripts/modeling/rider_bike.py` | Same terms as this repository (MIT) | Built from dimensions only; no third-party meshes, textures, brand names or logos |

**Attribution (CC-BY):** Jacket based on "Hooded sweat jacket" by Elvaerwyn, MakeHuman community asset repository, CC-BY. Recoloured, refitted, and the hood rebuilt in the raised position. The GLB's `asset.copyright` field carries the same credit.

The white shoulder mark is a plain geometric shape. The old procedural rider had brand text there, and it was not reproduced. The character is a generic MakeHuman-based stand-in in the outfit the site owner described. It is not a scan or likeness of a real person.

## Bike dimensions

Typical 54 cm aluminium endurance road frame. Wheelbase 985 mm, chainstays 408 mm, BB drop 70 mm, head angle 73°, seat angle 73.5°, stack 555 mm, fork offset 45 mm. 700x25c tyres (335 mm radius), 170 mm cranks, 50/34 chainrings, 11-28 cassette (the chain runs 50x17), 420 mm drop bar with hoods, 100 mm stem, rim brakes, flat pedals. The saddle height (BB to saddle top along the seat tube, 0.723 m) is solved from the rider's leg length for a 150° knee angle at the bottom of the stroke.
