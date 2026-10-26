# 素材来源与授权状态（ASSETS_PROVENANCE）

> 状态：**模板/人工产出待补（401）**。本文件不是法务结论，不构成“已合规/已授权”。
> 机械清单：`docs/ASSETS_MANIFEST.md`（当前 `git ls-files` 实测 **121** 个 tracked 媒体文件，含 SHA256）。
> 2026-10-26 复核发现：`RELEASE_LICENSE_REVIEW.md` 旧记“126 tracked / 125 无来源”与当前实测 121 不一致，
> 差异待人工逐族复核；**本文件不沿用旧数字**。

## 1. 分族汇总（按 `docs/ASSETS_MANIFEST.md` 机械分类）

| 族 | 数量 | 路径 | 当前状态 | 发布前需人工补 |
|---|---:|---|---|---|
| pixel-campus 像素素材 | 51 | `frontend/public/pixel-campus/` | **UNKNOWN**（PNG 元数据被剥离） | 出处/作者/工具/授权/日期 |
| avatars（web+mobile） | 22 | `frontend/public/avatars/`、`mobile/public/avatars/` | **UNKNOWN**（无 provenance） | 出处/授权；与 `frontend/src/assets` 6 个同源文件的关系 |
| integrated-map bundle | 6 | `frontend/public/integrated-map/assets/` | **THIRD-PARTY BUILD，无源码** | 恢复源码或停止对外分发该 bundle |
| mobile 其他素材 | 27 | `mobile/`（图标/启动图等） | **UNKNOWN** | 设计源文件/授权 |
| frontend/src assets | 8 | `frontend/src/assets/` | **UNKNOWN** | 与 avatars 同源关系、授权 |
| docs 产品截图/hero | 4 | `docs/assets/` | **PROJECT-GENERATED** | 作者/日期/截图环境记录 |
| 项目 logo | 2 | `frontend/public/logo.png`、`data/logo.png` | **UNKNOWN** | 设计源文件/授权 |
| Electron 图标 | 1 | `electron/assets/icon.ico` | **UNKNOWN** | 派生关系/授权 |
| **合计** | **121** | — | — | — |

## 2. 事实边界

- 以上“UNKNOWN”表示**没有可核验的授权记录**，不是“无版权”也不是“已授权”。
- `docs/assets/` 4 个文件是项目自有 UI 截图/手写 SVG，可由作者补日期与截图环境后标为自有；仍建议登记。
- `integrated-map/assets/` 6 个是第三方构建产物，仓库无 `integrated-map-src`、无 `.gitmodules`、无 `CockpitView.vue`；**来源落实前不得对外分发**。
- 旧 `frontend/public/assets/`（30 个旧 React 产物）当前 **不在** `git ls-files` 媒体清单内；如发布包含，需单独处置。
- 构建产物 `frontend/dist/assets/` 的 KaTeX 字体不在 tracked 清单内；随包分发时需法务确认字体衍生条款。

## 3. 与发布文档的关系

- `RELEASE_LICENSE_REVIEW.md` 负责 GPL/LGPL 审查包与待法务项；
- 本文件负责**逐族来源事实**与“待人工”清单；
- `docs/RELEASE_DRAFT.md` 的 Known limitations 必须保留“素材 provenance 待人工”；
- 在人工补齐并签署前，release 只能是 `v1.0.0-rc1` 候选，不得称 GA。

## 4. 人工补齐方式

逐族在 `docs/ASSETS_MANIFEST.md` 对应行备注：

```
来源: <设计稿/生成工具/第三方包/作者>
授权: <具体许可证/书面许可/自有>
日期: <YYYY-MM-DD>
证据: <链接/合同/设计文件路径>
```

不要用“看起来是 AI 生成”“网上找的”之类不可核验描述替代授权记录。
