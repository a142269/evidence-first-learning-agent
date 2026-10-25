# QWEN-401 许可/素材闭环复核（2026-10-25，分支 `qwen/wave4-release`，零模型）

> 单一事实源仍是 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)（2026-10-18 机器盘点）。
> 本文档是该盘点在本日的**复核记录 + 401 交付物索引**：媒体清单逐族状态、GPL/LGPL 审查包、
> integrated-map 来源结论。所有法务结论均为**待人工审查**，不写"已合规/已签署"。

## 1. 媒体清单复核（2026-10-25 实测 `git ls-files` 计数）

盘点基线：126 个 tracked 媒体/文档文件、125 个无来源文件；本日复核各族计数如下
（与盘点一致，无新增/减少）：

| 族 | 今日 tracked 计数 | 来源/许可证状态 | 待确认项（→人工） |
|---|---|---|---|
| pixel-campus 像素素材 | 51 PNG（`frontend/public/pixel-campus/`） | **UNKNOWN — 无 provenance 文件**，PNG 元数据被剥离 | 出处/作者/工具/授权；补 `docs/ASSETS_PROVENANCE.md` 条目 |
| 头像（web） | 16（`frontend/public/avatars/`） | **UNKNOWN — 无 provenance** | 同上；另 `frontend/src/assets` 8 个（6 个与 avatars 字节同源） |
| React 子应用 bundle | 2（`frontend/public/integrated-map/assets/`）+ 6 头像副本 = 8 | **THIRD-PARTY BUILD，仓库无源码**（见 §3） | 恢复 `integrated-map-src` 或停止分发该 bundle |
| 旧 React 产物 | 30（`frontend/public/assets/`，4.97 MB） | **无来源构建产物，当前 index.html 不引用** | 删除或文档化（inventory §6.3；本卡未动，待产品裁定） |
| 项目 logo / 桌面图标 | 1（`frontend/public/logo.png`）+ `electron/assets/icon.ico` 1 | **UNKNOWN — 派生关系未记录** | 设计源文件与授权 |
| docs 产品截图 + hero | 4（`docs/assets/`） | PROJECT-GENERATED（本项目 UI 截图/手写 SVG） | 补作者/日期记录即可 |
| AI 生成架构图 | 3（`docs/TripleU-*.png`） | AI-GENERATED，服务/模型未记录 | 生成服务条款；图中出现真实厂商 logo 的商标授权 |
| 移动端头像/favicon | 7（`mobile/public/`） | UNKNOWN — 头像与 web 同族副本、favicon 派生自 logo | 同 avatar/logo |
| Android 启动图标/splash | 26（`mobile/android/.../res/`） | UNKNOWN — 生成图标 | 同 logo |
| PPTX 模板 | 1（`data/pptx_templates/`） | UNKNOWN — 模板出处未记录 | 模板内主题/字体第三方条款 |
| 生成产物（不入 git，随桌面包） | `data/artifacts/**` 119 个 | 管线生成；per-file renderer 记录不全 | TTS/渲染服务条款归属 |
| 第三方数据集 | `data/benchmarks/assist2009.zip`（本地存在，**不入 git**） | USTC EduData 镜像（CMU open 条款记录于 dataset_spec） | 再分发许可文本；保持不入发行物 |
| KaTeX 字体 | 59（`frontend/dist/assets/`，构建产物） | katex MIT 包内 | 字体衍生条款核实 |

**复核结论**：素材侧无一族已落实可再分发授权；此前 QWEN-103 已提交 pixel-campus 去重
（`frontend/public/integrated-map/pixel-campus` 现 0 tracked/0 on-disk），无"已删未提交"残留。
**逐族 provenance 表（`docs/ASSETS_PROVENANCE.md`）仍是发布前必须补齐的人工产出**（见 §4）。

## 2. GPL/LGPL 审查包（供法务；事实陈列，非意见）

### 2.1 组件与链接方式

| 组件 | 版本 | 许可证（按声明） | 进入发行物的方式 | 义务触发点 |
|---|---|---|---|---|
| `psycopg` / `psycopg-binary` / `psycopg-pool` | 3.3.6 / 3.3.6 / 3.3.3 | **LGPL-3.0-only** | `requirements.lock.txt` 锁定；PyInstaller `backend.spec` 打包后端时被收集 | 静态打包是否构成"库 + 独立作品"的界定（ LGPL §4/§6 如何满足：随附 license 文本、允许替换库、提供源或书面 offer） |
| `edge-tts` | 7.3.1 | **LGPL-3.0**（classifier） | `requirements.txt` 直依赖；`backend.spec` collects `edge_tts` | 同上 |
| FFmpeg 可执行文件（`ffmpeg-win-x86_64-v7.1.exe`，87.6 MB） | 7.1 essentials | **GPLv3 构建**（`--enable-gpl --enable-version3`，gyan.dev build） | `imageio-ffmpeg`（BSD 声明）首次使用时落盘；是否真的进了桌面安装包**未核实**（本机无 `dist/` 构建） | 若随包：GPL 合规 = 随附 GPL-3.0 文本 + 对应源码或书面 offer；GPL 传染范围评估 |
| `jszip` | 3.10.1 | (MIT **OR** GPL-3.0-or-later) | Electron 根闭包运行时 | 双许可可选 MIT——法务确认选择即可 |
| 无 **GPL-2.0/纯 GPL** Python/npm 运行时依赖 | — | — | — | 盘点范围内未发现；UNKNOWN 5 包中 4 个（chromadb 默认 Apache-2.0、mcp MIT、passlib BSD、python-jose MIT——**这些是公开常识而非本机证据，仍以法务核实为准**） |

### 2.2 待法务确认清单（401 交付，供签署）

1. PyInstaller 单目录/单文件打包下 LGPL"可替换库"义务的满足方式（改 `--onedir`？附源包？排除并要求用户自装？）；
2. GPL FFmpeg：随包发行 vs 改用非 GPL 构建（如 LGPL 构建/ essentials 非 GPL 版）vs 运行时用户自备——三选一的裁定与材料；
3. `edge-tts` 调用 Microsoft 在线服务：服务条款对商用/再分发的约束（叠加于 LGPL 之上）；
4. NOTICE 文本定稿与三处发行物落位（见 [DIST_NOTICE_DRAFT.md](DIST_NOTICE_DRAFT.md) §1/§4）；
5. 素材族授权（§1 全部 UNKNOWN 族）；
6. 在线服务（讯飞/OpenAI 兼容端点）输出内容再分发边界。

## 3. integrated-map 来源结论（按 §3-109 Lead 裁定落地）

**事实（2026-10-25 复测）**：`git ls-files frontend/integrated-map-src` = **0**；仓库根无
`.gitmodules`；`frontend/src/views/CockpitView.vue` 未提交；`frontend/public/integrated-map/assets/`
为 2 个无 license banner 的 minified 文件（React/react-dom/marked/lucide 字符串），git 历史
亦无 `integrated-map-src`。

**结论**：**无源码可恢复**。

**处置（终局，沿用 QWEN-343 结论并经 Lead §3-109 裁定确认）**：

- `frontend/tests/_orphaned/` 的 **17 个测试保留**：不删除、不恢复运行、不进 CI；
- 本卡**未删除任何测试、未改动任何 CI 使其运行**（`ci.yml`/`nightly.yml` 本卡零改动）；
- 结论已同步写入发布材料：本节 + [frontend/tests/_orphaned/README.md](../frontend/tests/_orphaned/README.md)
  "QWEN-343 正式处置结论"节 + [RELEASE_DRAFT.md](RELEASE_DRAFT.md) 的发布前置项；
- `frontend/public/integrated-map/` bundle 在来源落实前**不得对外分发**（inventory §6.2），
  处置选项（恢复源码重建 / 移除产物）归产品裁定，本卡不执行删除。

## 4. 401 人工产出清单（汇总）

| # | 产出 | 责任 | 输入 |
|---|---|---|---|
| 1 | NOTICE 定稿（法务签署） | 法务 | DIST_NOTICE_DRAFT.md + THIRD_PARTY_NOTICES.md |
| 2 | `docs/ASSETS_PROVENANCE.md` 逐族来源表 | 产品/设计 | 本文档 §1 表 |
| 3 | GPL/LGPL 义务裁定（含 FFmpeg 三选一） | 法务 | 本文档 §2 |
| 4 | integrated-map bundle 处置裁定 | 产品 | 本文档 §3 |
| 5 | assist2009 数据集再分发条款确认 | 法务 | `docs/datasets/dataset_spec.md` |
| 6 | 在线服务条款确认（讯飞/Edge-TTS/OpenAI 端点） | 法务/商务 | inventory §0 scope 说明 |
