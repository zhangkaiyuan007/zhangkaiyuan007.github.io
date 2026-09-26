# Southwest Jiaotong University · Xipu New West Gate

Photo-guided architectural model, created in Blender 4.5.14 LTS on 2026-09-23.

## References

Photographer: **Kcx36**. Both originals are licensed **CC BY-SA 4.0**.

- [New west gate, view 01](https://commons.wikimedia.org/wiki/File:西南交大犀浦校区新西门_20230630_01.jpg)
- [New west gate, view 02](https://commons.wikimedia.org/wiki/File:西南交大犀浦校区新西门_20230630_02.jpg)
- [License](https://creativecommons.org/licenses/by-sa/4.0/)

Original files are in `../../references/xipu-west-gate/` and remain unmodified.
Derived assets (embedded in the GLB; `scripts/modeling/prepare_west_gate.py` regenerates the intermediate files under `.tools/west-gate/`): perspective-rectified facade texture, extracted and extruded calligraphy contours, mirrored terracotta surface sample, perspective-rectified monument texture. These adaptations and the resulting model/render images are shared under **CC BY-SA 4.0**, with the above attribution. No endorsement by the photographer or university is implied.

The model is a photo-assisted artistic reconstruction, not a scan or surveyed architectural model. Main gate width is represented as 38 units and height as 12.5 units for proportions; these are estimated. Side and rear surfaces, pavilion depth, landscaping and background buildings are approximations. The two images do not constitute a complete photogrammetry dataset.

Rebuild source: `scripts/modeling/prepare_west_gate.py`, `scripts/modeling/build_west_gate.py`.
Editable Blender scene: written to `artifacts/xipu-west-gate/xipu-west-gate.blend` by the build script (not committed).
Web asset: `xipu-west-gate.glb` (Draco compressed, embedded textures).
