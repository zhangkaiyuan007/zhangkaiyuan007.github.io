# 犀浦校区新西门

交大站和 `/ride/west-gate/` 对照页共用的模型：`static/ride/models/xipu-west-gate/xipu-west-gate.glb`（约 7.5 MB，Draco，贴图内嵌）。

依据是 Wikimedia Commons 上 Kcx36 的两张新西门照片（CC BY-SA 4.0）。原图与派生贴图的来源、许可记录在同目录的 `SOURCE.md`。两张照片不足以做摄影测量，尺寸、侧背面、附属建筑与植被都是近似重建。

## 重建

```sh
./scripts/modeling/setup.sh                  # Blender 4.5.14，装进 .tools/
python3 scripts/modeling/prepare_west_gate.py
./scripts/blender --background --factory-startup --python scripts/modeling/build_west_gate.py -- --render
```

- `prepare_west_gate.py` 从 `static/ride/references/xipu-west-gate/` 的两张照片生成校正贴图和校名轮廓，写到 `.tools/west-gate/textures/`。
- `build_west_gate.py` 导出 GLB，加 `--render` 时另出 `west-gate-render.png`（对照页有链接）。可编辑场景写到被 Git 忽略的 `artifacts/xipu-west-gate/`。
- Blender 需要在能访问 GPU 的终端里运行（Cycles OptiX）。

流程：
1. 透视校正照片；
2. 按比例建门框与椭圆拱线；
3. 建实体门柱、拱腹、立柱、门岗和校名石；
4. 从照片提取校名轮廓并挤出成凸字；
5. 照片表面 UV 与 PBR 材质；
6. 合并为 5 组，Draco 导出。
