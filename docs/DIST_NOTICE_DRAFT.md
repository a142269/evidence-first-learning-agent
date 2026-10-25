# dist NOTICE 草案（DRAFT — 待人工法务审查，未签署）

> **状态：草案（QWEN-401，2026-10-25，分支 `qwen/wave4-release`）。本文件是随发行物分发的
> NOTICE 的**文案底稿**，不是法务意见，不构成"已合规/已签署"的主张；任何一条在人工法务
> 审查通过前都不得视为定稿。数据来源：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
> （2026-10-18 机器盘点）与本日复核（见 [RELEASE_LICENSE_REVIEW.md](RELEASE_LICENSE_REVIEW.md)）。

## 1. 用途与产出位置（待定，按打包惯例补齐）

| 发行物 | NOTICE 产出位置（建议） | 现状 |
|---|---|---|
| Web 前端 `frontend/dist` | `frontend/dist/NOTICE.txt`（Vite 构建后复制或 public 注入） | **缺失**（inventory G1：dist 内 0 个 LICENSE/NOTICE） |
| 桌面安装包（Electron NSIS） | 安装目录 `NOTICE.txt` + `electron-builder.yml` `extraResources` | **缺失**（同 G1） |
| PyInstaller 后端（`backend.spec`） | `datas` 加入 `NOTICE.txt`（+ 依赖 license 文本目录） | **缺失**（同 G1） |
| 源码发行 | 仓库根 `LICENSE`（MIT，已存在）+ 本 NOTICE | LICENSE 已有，NOTICE 为本草案 |

> 生成方式建议（供法务审查时参考，未实现脚本）：从 `THIRD_PARTY_NOTICES.md` 的表格 +
> 本机 `dist-info`/`node_modules` 的 license 文本（Python 144/146、前端 105/115 有本地文本）
> 机械拼接；**不得手抄依赖清单**，以免与实际锁文件漂移。

## 2. 本项目声明（MIT）

```
Triple-U / 智学领航（evidence-first-learning-agent）
Copyright (c) 2026 智学领航 contributors
以仓库根 LICENSE（MIT）分发；本 NOTICE 为第三方组件声明，不改变项目许可。
```

## 3. 第三方组件声明（摘要 — 全量清单以 THIRD_PARTY_NOTICES.md 为单一事实源）

**嵌入分发（打包产物内）的组件族**（逐包名称/版本/许可证全文随最终 NOTICE 生成，本草案只列族级摘要）：

| 组件族 | 数量 | 许可证（按声明） | 备注 |
|---|---|---|---|
| Python 运行时（requirements.lock.txt 145 锁定） | 121 运行时 + 24 仅开发 | MIT / BSD / Apache-2.0 / MPL-2.0 / PSF / LGPL-3.0（4 包）等 | 5 个声明未安装组件 UNKNOWN（chromadb/mcp/passlib/python-jose/sentence-transformers，均不入运行时） |
| Web 前端 npm 运行时闭包 | 65 | MIT / ISC / Apache-2.0 / BSD / 0BSD | 0 个 UNKNOWN；KaTeX 字体 59 文件随构建（MIT 包内，字体衍生条款**未核实**） |
| Electron 桌面（根 package-lock） | 19 运行时 + 266 仅开发 | MIT / ISC / BlueOak / (MIT OR GPL-3.0-or-later)（jszip，可选 MIT） | Electron 运行时（MIT）自带 Chromium 等组件通知，由 electron-builder 打包 |
| 随后端打包的 FFmpeg 可执行文件 | 1 | **GPLv3 构建**（`--enable-gpl --enable-version3`） | 经 `imageio-ffmpeg` 落盘；与该 Python 包的 BSD 声明**不一致**，见 LICENSE_REVIEW §3 |

**随包但来源未证实的素材**：pixel-campus 像素素材（51 PNG）、头像（16）、logo/图标、
React 子应用 minified bundle（无源码）——逐族状态见 LICENSE_REVIEW §2；**在素材来源落实前
不得对外分发**（inventory §6.2 同结论）。

## 4. 待人工法务审查项（签署前必须逐条关闭）

1. NOTICE 最终文本与三处发行物落位（§1 表）是否齐全、随构建自动复制；
2. LGPL 组件（`psycopg`/`psycopg-binary`/`psycopg-pool`/`edge-tts`）被 PyInstaller 静态收集后的义务履行方式（license 文本 + source offer 或改用其他构建）；
3. GPL FFmpeg 二进制是否随包发行；若发行，GPL 合规材料；
4. `integrated-map` React bundle 无源码、无 license banner——恢复源码或停止分发该产物；
5. 素材族（pixel-campus/avatars/logo/图标/AI 架构图）来源与使用授权记录（现为 UNKNOWN）；
6. KaTeX 字体衍生自 Computer Modern 的附加条款核实；
7. 在线服务条款（讯飞 Spark/Embedding/imagev3/TTS、Edge-TTS、OpenAI 兼容端点）对"输出可否再分发"的约束——inventory 明示不在盘点范围，需人工确认；
8. `assist2009.zip` 数据集（本地存在、不入 git）再分发条款；
9. 生成式产物（TTS 音频/pptx/mermaid 图/LLM 文本）的版权归属与商用边界。

**在以上各项有书面结论前，本 NOTICE 保持 DRAFT 状态；"已合规/已签署"字样禁止出现。**
