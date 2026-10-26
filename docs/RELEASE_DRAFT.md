# QWEN-402 Release 材料草案（2026-10-25，分支 `qwen/wave4-release`，零模型）

> **草案性质**：版本号/CHANGELOG/演示脚本/截图清单均为**待 Lead 裁定与人工产出的底稿**。
> 视频与截图**未产出**（本卡不伪造媒体文件）；所有"人工产出"条目见 §5 汇总。
> 数字来源：仓库实况（`backend/app/main.py` version、`docs/CLAIMS_LEDGER.md`、`docs/TEST_MATRIX.md`）。

## 1. 版本号建议（待裁定）

| 项 | 现状 | 建议 |
|---|---|---|
| FastAPI app version | `backend/app/main.py` `version="1.0.0"` | 维持 `1.0.0`，发行标记用 **`v1.0.0-rc1`**（release candidate：公网/TLS/独立复核 404 未完成，不称 GA） |
| 仓库内版本锚点 | 无 `CHANGELOG.md`、无 git tag、`frontend/package.json` 版本未核 | 由 Lead 裁定是否引入 tag `v1.0.0-rc1` + 本 CHANGELOG 落地为 `CHANGELOG.md` |

## 2. CHANGELOG 草案（以 main=`b2d4e3c` / 全量 2520/0/20 / 2540 项为准，未虚构）

> 格式建议 Keep a Changelog；日期留空待发行时填写。哈希为台账/对话已记录的真实提交。

```markdown
# Changelog

## [Unreleased — v1.0.0-rc1 候选内容]

### Added（V2 证据优先学习主线）
- 证据优先学习包（LangGraph 两步计划 + 受限检索循环 + 教师审核中断），部分完成语义与引用分块级来源（Wave 0/1，台账 §3-§16）
- 确认门控长期记忆：user_memories + memory_events（迁移 20261023_0012，可完全回滚；模型只能 propose，七态 run 拒入记忆）（QWEN-201，台账 §20）
- 跨会话摘要：只读 active 记忆、有界窗口/预算、幂等 sha256、persisted=false（QWEN-202，台账 §22）
- 有界重规划：确定性失效信号 + 最多 1 轮重规划 + plan.replanned 审计（QWEN-211，PROMPT_VERSION v2.9）（台账 §24-25）
- 学习包统一观察与 claim-support 交付校验（QWEN-231，台账 §29-30）
- Run 队列/Worker：/enqueue、/cancel、租约领取、at-least-once 重领（QWEN-301，台账 §31-32）
- Prompt 注册表：prompts/ 字节不变迁移 + sha256 校验 + CI 硬门（QWEN-311，台账 §33-34）
- 提示词回归 harness 与 A/B 离线对比框架（QWEN-312，台账 §35-36）
- 声明式权限矩阵：全部 V2 路由 × 角色 × 课程 × Run 归属 × 工具，CI 未声明即失败（QWEN-321，台账 §37-38）
- 注入红队套件 25 项（四类注入面 + 泄露金丝雀）（QWEN-322，台账 §39-40）
- 配额/限流：每用户/课程 请求/token/费用 三维滑动窗口，超限 429 quota_exceeded + Retry-After；生产模板默认启用（QWEN-324/324b，台账 §41-42）
- Run 级指标 9 个 + /metrics 权限边界 + 告警规则草案 6 条（QWEN-341/341b，台账 §43-44）
- nightly 分批（a/b/integration/misc）+ celery Linux 显式覆盖步骤（QWEN-343，台账 §45）

### Changed
- 工具目录化 + 运行时 deny-by-default + 统一工具审计（QWEN-221，台账 §27-28）
- 未请求渲染时交付可编辑讲稿脚本（video_status=script_only），渲染请求质量门照旧（QWEN-107 系列）

### Security
- run_guard 注入归一化加固：NFKC 全角折叠、零宽字符剔除、"无视"同义拦截（QWEN-322 运行期修复）
- 生产安全边界：APP_ENV=production 下 V1 fail-closed、docs/OpenAPI 隐藏、/metrics 仅 teacher/admin、secrets 全部 ${VAR:?} 强制（docker-compose.production.yml）

### Known limitations（发布声明必带）
- 公网/TLS/域名/备份未验证（QWEN-403）；**独立复核（404）用户豁免，未执行独立复核，不是“复核通过”**，仍为未关闭 P0
- 素材族 provenance 为 UNKNOWN（QWEN-401）；integrated-map bundle 无源码，不得对外分发；机械清单见 `docs/ASSETS_MANIFEST.md`（121 个 tracked 媒体），人工来源表见 `docs/ASSETS_PROVENANCE.md`
- 新版 Golden Set 在线质量验收未完成；离线契约测试不等价于模型质量评测
```

## 3. 演示视频脚本 + 录制清单（**待人工录制**，本卡零媒体产出）

> 结构沿用 `docs/DEMO_5_MINUTES.md`（5 段 5 分钟）；校正项见 §4。**录制环境要求**：
> 企业 compose 全栈 healthy + 真实在线模型；录屏前确认 `.env*`/密钥/Authorization 头不入镜。

| 镜头 | 时长 | 画面 | 状态 |
|---|---|---|---|
| S1 问题与架构 | 35s | README 架构图 + 仓库首页 | 待人工录制 |
| S2 教师上传异步入库 | 50s | `/teacher/kb` 上传→parsing/queued→indexed | 待人工录制 |
| S3 带来源学习问答 | 60s | 学生端提问→流式回答+引用；学习包页（来源/分块 ID/token/费用） | 待人工录制 |
| S4 安全拒答 + 人工审核 | 50s | 注入拒绝；勾选教师审核→review.required→教师拒绝→学生无草稿 | 待人工录制 |
| S5 可观测 | 50s | Trace（节点耗时/调用顺序/失败）+ （可选）`/metrics` 401/403/200 三态与告警草案展示 | 待人工录制 |
| S6 评测闭环收尾 | 55s | 评测报告页；口径标注（隔离环境 74/76 = 97.37%，2026-10-16；旧 66 条基线为历史） | 待人工录制 |
| S7 可选加分 | — | 配额 429 `quota_exceeded` + Retry-After 现场演示（QWEN-324）；Run 队列 /enqueue→worker 领取（QWEN-301） | 待人工裁定是否纳入 |

**配音/字幕/剪辑**：人工产出；本卡仅提供镜头脚本，无媒体文件。

## 4. `docs/DEMO_5_MINUTES.md` 引用校正表（该文件本卡未改动）

| # | 原文 | 校正 | 依据 |
|---|---|---|---|
| C1 | `cd /d D:\xunfei\triple-U` | 仓库现为 `D:\xunfei\evidence-first-learning-agent`（compose 文件名不变） | 本仓库实况 |
| C2 | 评测收尾只引"旧版 66 条在线基线（历史）" | 补充当前可引用口径：**隔离测试环境在线指标 74/76（97.37%）、事实题 Hit@5 95.83%、引用存在率 100%（2026-10-16）**；仍不得替代真实 Docker+PG+云端验收 | `README.md` 在线指标行 |
| C3 | `D:\Anaconda3\envs\dxtorch\python.exe scripts\evaluate_golden_set.py` | 本机当前评测环境为 `D:\Anaconda3\envs\evidence-agent-py312`（dxtorch 路径待核对是否仍存在） | 本卡环境 |
| C4 | Phoenix `http://localhost:6006` 直开 | 生产 compose 中 phoenix 仅内网（OTLP endpoint）；是否发布端口取决于所用 compose 文件，录制前核对 | `docker-compose.production.yml` |
| C5 | （可选新增）S5 增补 `/metrics` 权限三态镜头 | production 下无 token 401 / 学生 403 / teacher 200 | QWEN-341 交付 |

## 5. README 截图更新清单（**待人工截图**，本卡不放占位图）

| # | 页面/步骤 | 关键元素 | 插入位置 |
|---|---|---|---|
| 1 | 学生端对话（含引用） | 流式回答 + 引用列表（分块级来源） | README 功能段 |
| 2 | 学习包页面 | 讲解+练习、来源与分块 ID、实际 token 与估算/unknown 费用 | README 功能段 |
| 3 | 教师审核流 | `review.required` → 教师草稿审阅/拒绝 → 学生侧不显示草稿 | README 功能段 |
| 4 | 教师知识库 | 上传→版本化分块→索引状态 | README 功能段 |
| 5 | 管理端用量/成本 | `/api/v2/admin/run-usage` 只读投影（teacher/admin） | README 可观测段 |
| 6 | `/metrics` 权限三态 | 401/403/200（脱敏：无 token 值、无内部指标值入镜） | README 可观测段 |
| 7 | 配额 429 | `quota_exceeded` + `Retry-After` 响应 | README 安全/限流段（可选） |
| 8 | 现有 `docs/assets/product-*.png` | **过期需重截**（UI 已迭代） | 覆盖旧图（旧图删除前留档） |

> 截图规范：统一分辨率与浏览器深/浅色模式；任何含用户数据/密钥/token 的区域打码；
> 每张图记入 `docs/ASSETS_PROVENANCE.md`（PROJECT-GENERATED，作者/日期）。

## 6. 发布前置（人工，未完成项汇总）

1. 404 独立复核（用户豁免、未执行；**不是通过**；仍为 P0，发布声明必须保留“未独立复核”）；
2. 401 法务签署（NOTICE/GPL/LGPL/素材）；
3. §3 视频录制与 §5 截图（人工）；
4. 公网/TLS/域名演练（403 Runbook 的"未验证项"清零）；
5. `docs/00-评委30秒导览.md` 项目统计行的测试计数仍停在 324 时代（2529 项），发行前由后续卡按 §43/§44/§45 口径刷新（本卡不改该历史记录）。
