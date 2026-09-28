# /journey/ · 三维骑行作品集

About 页里的入口卡片（`layouts/shortcodes/journey-portal.html`）通向 `/journey/`。访客沿一条路线骑行，经过武汉江滩、武汉二中、西南交大犀浦西门、Helios、银河通用五个地点；靠近地点按 E 进入第一人称，查看经历、成果和参考照片。

## 操作

- W/S 前进后退，A/D 横移，滚轮也能前进。靠近地点按 E 进入，E、Esc 或关闭按钮返回。
- 右上角菜单：地点跳转（黑场切换）、自动骑行（多机位）、电影画面开关（记在 localStorage）、照片总览、返回 About。
- 手机：按住式方向键，资料面板在屏幕下半部。
- `?station=river|school|campus|helios|galbot`：跳过开场，直接停在该站。

## 代码

| 文件 | 作用 |
| --- | --- |
| `layouts/journey/ride-prototype.html`、`assets/css/ride-prototype.css` | 页面骨架与样式；入口脚本按内容 md5 带版本号 |
| `static/ride/ride-prototype.js` | 加载顺序、状态机（开场、骑行、进入、阅读、返回）、输入、资料面板 |
| `static/ride/stations.js` | 五站的唯一数据源：位置 `at`、文字、成果、参考照片与来源、演示类型 |
| `static/ride/world.js` | 路线 `routeX`、各站场景、街道设施；各站第一人称取景 `stand`/`look`，可选 `fov`、`fit`、`fog`、`aperture`、`narrow` |
| `static/ride/geometry.js` | 共享几何与材质；`surface()` 面层材质（UV 以米为单位）和 `dressSurfaces()` |
| `static/ride/props.js` | 写实道具（行道树、路灯、长椅、花箱、货品）与照片纹理；`instanceTrees()` 实例化行道树并加风摆 |
| `static/ride/gltf.js` | 全页共用的 GLTFLoader 和 Draco 解码器 |
| `static/ride/rider.js` | 写实骑行者，见 [rider.md](rider.md)；加载失败时回退到 `cyclist.js` 的程序化人物 |
| `static/ride/galbot.js` | 按官方 URDF 装配 G1 网格，开放关节句柄 |
| `static/ride/west-gate.js`、`gate-lighting.js` | 犀浦西门模型与灯光，见 [xipu-west-gate.md](xipu-west-gate.md) |
| `static/ride/director.js` | 镜头：跟拍、进入和返回的升降机位、开场航拍、黑场切换、自动骑行六机位 |
| `static/ride/cinema.js`、`atmosphere.js` | 后期（HDR、泛光、景深、调色、暗角、颗粒）；天空、雾、太阳、尘埃 |
| `static/ride/demo-sentry.js`、`demo-drone.js` | Helios 与交大站的交互演示 |
| `static/ride/west-gate/`、`static/ride/references/` | 西门模型对照页、参考照片总览页 |

加载顺序：
1. 入口脚本一执行就开始下载街景道具（行道树、路灯、长椅）、地面贴图和骑行者，同时加载场景模块。
2. 加载页显示已载入的文件数。首帧等这些资源（约 8 MB），但最多等到打开页面后约 6 秒；网络慢时先用程序化的占位模型开场，写实模型到了再替换。
3. 首帧之后按距离依次下载：先是西门（第三站，约 7.5 MB），再是银河通用的 G1 和店内货品（最后一站，约 7 MB）。从 `?station=campus` 进入时，西门算在首帧之内。

## 交互演示

两个都是原理演示，面板里已写明。

- **Helios · 哨兵导航**（`demo-sentry.js`，场地布局见 `world.js` 的 `arenaLayout`）：
  - 建图：模拟 Mid-360 扫描，累积成点云地图。
  - ESDF：对占用栅格做精确欧氏距离变换。
  - 规划：A* 在膨胀栅格上搜索，靠近障碍代价升高，再剪枝、平滑。
  - 跟踪与决策：纯跟踪；状态机在巡逻、前往目标、避障、到达之间切换。
  - 交互：点击场地设目标，可切换图层、打开动态障碍。
  - “NeuPAN 思路”模式：采样 MPC，直接以附近激光点作避障代价。
  - 依据是 26 赛季总结。画面不是实车数据，也不是 neupan_cpp 的输出。
- **交大 · 零样本无人机导航**（`demo-drone.js`）：
  - 检测框：西门模型中真实物体的投影，代替 YOLOE prompt-free 的输出。
  - 拓扑图：DBSCAN（ε = 7 m）在浏览器里实际运行并生成。
  - “Qwen3-0.6B 推理”：按规则生成的文字，不调用模型。
  - 依据是面试记录里的项目描述。

## 素材与许可

每站的参考照片及来源写在 `stations.js`，总览页是 `/ride/references/`。资产来源与许可见 `static/ride/models/*/SOURCE.md` 和 `static/ride/textures/SOURCE.md`：
- 骑行者外套是 CC-BY，需要署名；
- G1 是官方 Apache-2.0 模型；
- 其余道具与贴图为 CC0。

建筑与 Helios 场地是照片指导的程序建模，不是扫描或测绘。

## 预览与重建

- 预览：`./scripts/preview-ride.sh`（Hugo Extended ≥ 0.158），打开 http://127.0.0.1:1313/journey/ 。
- 道具与贴图：`python3 scripts/modeling/fetch_props.py && python3 scripts/modeling/prepare_textures.py && ./scripts/blender --background --factory-startup --python scripts/modeling/prepare_props.py`。
- 骑行者、西门：见各自文档。Blender 4.5 由 `scripts/modeling/setup.sh` 装进被 Git 忽略的 `.tools/`；Blender 工作文件与中间文件写到被忽略的 `.tools/`、`artifacts/`。

## 维护约定

- **站点数据**：站点位置只在 `stations.js` 里改。地面标记、演示启停和 `?station=` 都从这里派生。`world.js` 里 `views` 数组的顺序必须和 `stations` 一致。
- **缓存版本**：静态模块统一带 `?v=cine6`。改任何模块时全局递增，包括 `west-gate/`、`references/` 页面。`props.js` 的资源版本 `props2`、骑行者 `rider3`、西门 `west3` 只在对应资源变化时递增。
- **离路距离**：写实树冠半径 4–6 m，最低的叶片离地约 0.5 m。新增或移动站点、树木时，树冠和建筑离路沿（路中心线 ±2.16 m）至少留 0.3 m。
- **后期兜底**：后期管线会过滤 NaN/Inf，避免个别坏像素被泛光扩散成大片黑块。

## 已知限制

- 手机：贴图显存曾超过 1 GB（G1 的 4096² 贴图约 720 MB），手机浏览器会杀掉标签页并反复重载，表现为白屏闪烁。现在 G1 贴图降到 ≤1024，粗指针设备上模型贴图再缩到 512（西门 1024）、地面 512、阴影 1024；实测模拟手机约 170 MB，桌面约 380 MB。未在真机上测试。
- 后期管线在创建时先探测多重采样半浮点渲染目标，帧缓冲不完整就退回直接渲染。
- 参考照片超过 1600 px 的有展示版（`scripts/modeling/prepare_photos.py`，`stations.js` 的 `DISPLAY`），页面显示展示版，“打开原图”链接原图。
- 首次访问约 18 MB（首帧）加 6 MB（G1，首帧后加载）。
