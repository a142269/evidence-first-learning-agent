# Changelog

> 本文件是 **v1.0.0-rc1 候选**的 release notes 草案，不是 GA 公告。
> 依据：`docs/RELEASE_DRAFT.md`、`docs/CLAIMS_LEDGER.md`、`docs/TEST_MATRIX.md`。
> 当前仅通过本地/CI 形态的离线测试；**未做独立复核（404 由用户豁免，非复核通过）**，法务/视频/截图/公网未完成。

## [Unreleased — v1.0.0-rc1 候选]

### Added（V2 证据优先学习主线）

- 证据优先学习包：LangGraph 两步计划 + 受限检索循环 + 教师审核中断；部分完成语义、引用分块级来源、SSE、租约与检查点。
- 确认门控长期记忆：`user_memories` + `memory_events`（迁移 `20261023_0012`，可完全回滚）；模型只能 `propose`，`confirm` 需 `student`/`teacher`，partial/failed 七态拒入。
- 跨会话摘要：只读 active 未过期记忆、有界窗口/预算、幂等 sha256、`persisted=false`、明确空态。
- 有界重规划：两类确定性失效信号、最多 1 轮/两版计划、检查点与 `plan.replanned` 审计、超限停止；`PROMPT_VERSION=learning-package-v2.9`。
- 学习包统一 Observation 与交付前规则版 claim-support 校验；失败 fail-closed、不交付/返工。
- Run 队列/Worker：`/enqueue` 创建执行解耦、`/cancel`、租约/心跳/超时、崩溃重领；**at-least-once，不声称 exactly-once**。
- Prompt 注册表：`prompts/` + name/version/sha256/changelog/owner，文件优先 + 内置回退；`verify_registry()` CI 硬门。
- Prompt 回归/离线 A/B harness：固定样例断言、dry-run、预算门禁、脱敏报告；不默认付费调用。
- 声明式 V2 权限矩阵：10 条路由 × 角色 × 课程 × Run 归属 × 工具；CI 未声明即失败。
- 注入红队套件 25 项：用户输入/检索文档/工具参数/部分完成内容；运行期修复 3 个 guard 绕过（NFKC/Cf/`无视`）。
- 配额/限流：请求/token/费用三维滑动窗口、429 + `Retry-After`、生产模板启用、费用 unknown 不当 0。
- Run 级指标 9 个 + `/metrics` 权限边界（401/403/200）+ 告警规则草案 6 条。
- nightly 分批（a/b/integration/misc）+ Celery Linux 显式步骤；孤儿前端测试 17 个正式保留隔离。

### Changed

- 工具目录化 + 运行时 deny-by-default + 统一工具审计；调用行为与错误面保持不变。
- 未请求 Manim 渲染时交付可编辑讲稿脚本（`video_status=script_only`），渲染请求的质量门照旧强制。
- 管理端用量投影修正：浮点延迟保留、`isfinite` 守卫、`estimated` 缺金额补 `reason`；不编造单价。

### Security

- 生产安全边界：`APP_ENV=production` 下 V1 fail-closed、docs/OpenAPI 隐藏、`/metrics` 仅 teacher/admin。
- `run_guard` 注入归一化加固；配额与权限矩阵；红队回归。
- 所有 secret 由 `${VAR:?}` 强制；不得提交/打印 `.env`。

### Known limitations（发布声明必带）

- **独立复核 404：用户豁免，未执行独立复核**；不能称“复核通过/GA/已上线”。
- 法务：NOTICE/许可/GPL-LGPL/素材 provenance 仍待人工审查与签署（见 `docs/DIST_NOTICE_DRAFT.md`、`docs/RELEASE_LICENSE_REVIEW.md`、`docs/ASSETS_PROVENANCE.md`）。
- 素材：pixel-campus/avatars/logo/icon 等 provenance 仍 UNKNOWN；`integrated-map` bundle 无源码，来源落实前不得对外分发。
- Release 材料：演示视频 7 镜头、README 8 张截图仍待人工录制/重截。
- 部署：公网/TLS/域名/备份/PG 恢复/Prometheus 真实抓取未验证（见 `docs/PRODUCTION_RUNBOOK.md`）。
- 真实付费模型 A/B 未做；本版本证据以离线/脚本化为主，除既有 QWEN-102 单臂机器级采集外无新增真人/云评测。
- nightly 的 GitHub remote 回执未验证；本地分批不等于远程绿。

### Evidence baseline

- 全量 `pytest tests/`：**2520 passed / 0 failed / 20 skipped**（Windows + Python 3.12.15，约 1466s；不同环境可能有时长/条件 skip 差异）。
- CI 快清单：**54 文件 / 649 passed / 1 skipped**。
- 详细证据：`docs/CLAIMS_LEDGER.md`、`docs/TEST_MATRIX.md`。
