# 优化状态（2026-10-18）

> 本文件记录 2026-10-18 这轮“先基线核对、再实现部分成功链路”的工作。仓库为 `<repo>`，分支 `main`，本地 `HEAD` 仍为 `9d7fb3e`；本轮所有改动保留在工作区，**未 commit、未 push**。历史交接见 [OPTIMIZATION_HANDOFF_2026-10-18.md](OPTIMIZATION_HANDOFF_2026-10-18.md) 与 [OPTIMIZATION_STATUS_2026-10-17.md](OPTIMIZATION_STATUS_2026-10-17.md)。

## 一、优先事项 1：基线核对结果

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| Git 工作区 | 通过 | 86 个已跟踪变更（27 修改 + 59 删除，删除均为重复素材去重）与 27 个未跟踪条目（33 文件）；未发现意外或危险改动 |
| 敏感数据 | 通过（有限检查） | 候选文件中未发现真实模型密钥、令牌、私钥、真实连接串、`.env` 值、私有课程原文、原始模型响应或学生数据；仅有占位口令与本地绝对路径等卫生项。不是完整历史/全来源安全审计 |
| 素材去重引用 | 通过 | 删除的 `frontend/public/integrated-map/pixel-campus/**` 无任何悬空引用；52 张 PNG 与保留副本字节一致；`test_campus_assets.py` 通过 |
| Ignore 边界 | 通过 | `output/`、`data/artifacts|benchmarks|rag|teacher_uploads` 均被忽略，无已跟踪例外 |
| 静态检查 | 通过 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` 通过；`git diff --check` 无错误 |
| 后端回归 | 通过 | CI 便携 V2 套件 34 文件：**324 passed / 1 skipped**（跳过需一次性 PostgreSQL 的用例）；学习包覆盖率门禁 **90.98%**（`learning_package.py` 93%），高于 80% |
| 前端构建 | 通过 | 使用本机 npm 缓存离线安装 116 个包（`npm ci --offline`，**未联网下载**）后，`vue-tsc --noEmit && vite build` 成功；`frontend/dist` 与 `public` 资源引用一致 |
| 额外生命周期测试 | 通过 | 检查点清理、租约迁移、未完成节点继续执行共 7 项通过 |

详细审计报告：`output/baseline-audit-20261018/report.md`；前端验证日志：`output/frontend-build-20261018/`；测试日志：`output/pytest-baseline-20261018/`。以上 `output/` 内容均被 Git 忽略，未上传。

**已知问题（与本轮改动无关）**：`tests/a/test_run_leases.py::test_heartbeat_failure_cancels_graph_and_prevents_success` 存在时序抖动（5 次隔离重跑中 2 次失败，最终基线运行通过），需要单独修复心跳竞态。

**运行环境说明**：这个 Windows workspace-write 沙箱会拒绝把 pytest 临时目录（`mode=0o700`）列为可读目录，也禁止带管道的子进程；因此测试统一使用 `output/` 下独立的 `--basetemp`，并通过 `output/pytest-baseline-20261018/sandbox_tmpdir_shim.py` 把目录创建模式改为 Windows 默认值（只改环境行为，不改源码/测试断言）。前端构建需要在本机沙箱外执行。这两点都是沙箱限制，不是产品缺陷。

## 二、优先事项 2：`partially_completed` 部分成功链路（本轮已实现）

### 设计原则

- 运行状态区分 `completed`、`partially_completed`、`awaiting_approval`、`rejected`、`failed`、`interrupted`。
- **整体失败保持关闭处理**：没有任何可交付内容时不交付。
- 部分交付必须由 Reviewer **显式**给出分项结论（`lesson_approved` / `practice_approved` / `dropped_exercises`）。省略分项字段时仍按整包结论处理，系统不会从模糊拒绝中推断“部分通过”。
- 只有同时满足以下条件的单元才交付：`source_ids` 属于本次检索证据；对应部分获得 Reviewer 明确通过；按需完成教师审核；结果已持久化并可核验。未交付内容不会因为“部分交付”被标记为已验证。

### 交付规则（实现）

| 场景 | Reviewer 结论 | 结果 |
| --- | --- | --- |
| 练习两次生成失败（无效 JSON/引用无法核对） | `approved=false, lesson_approved=true, practice_approved=false` | 仅交付讲解；`withheld_parts=["practice"]`，reason `practice_unavailable` |
| 练习返工一次后仍被拒 | 同上 | 仅交付讲解；reason `practice_not_approved`；`revisions=1` |
| 个别题目被删除、其余可交付 | `practice_approved=true` + `dropped_exercises=[题号]` | 交付讲解与其余练习；`withheld_exercise_numbers` 记录原始题号（页面显示“原第 N 题”） |
| 讲解未通过 | `lesson_approved=false` | 不交付（练习依赖讲解，不单独交付） |
| Reviewer 通过未生成的产物 | 任意 | 契约冲突，失败关闭（`learning_package_quality_failed`） |
| 失败返工后 Reviewer 又对旧练习给 PASS | 任意 | 旧练习已从状态移除，失败关闭，不会把过期内容当新产物交付 |

### 可靠性保证

- **SSE**：终态事件仍为 `run.completed`，`status=partially_completed`，payload 含 `partial_completion`、只含已交付部分的 `learning_package`、`budget`；`quality.partial_completion=true`。
- **持久化与恢复**：`status`、`result`、`partial_completion` 写入 `agent_runs`；`artifact_count` 为实际交付单元数（0–2），`success_count` 只统计完整 `completed`。GET 查询、`/events` 审计、教师 `/reconcile` 复用同一交付契约；`reconcile` 只读稳定检查点，不重新调用模型，也不能把部分结果升级为 `completed`。
- **教师审核与拒绝**：`require_approval=true` 仍先返回 `review.required`；教师草稿携带 `partial_completion`，通过后为 `partially_completed`，拒绝后为 `rejected` 且不交付草稿；教师替换内容时清除结构学习包与部分标记，按人工内容处理。
- **隔离**：跨用户、跨课程仍按既有授权规则拒绝；`/events` 仅所有者可读；学生看不到待审草稿。
- **不泄漏未审核内容**：被拒收的练习从图状态移除；部分交付结果中的 `learning_package.review.issues` 与 `suggested_query` 清空（仅保留计数标志），避免 Reviewer 转述被拒内容通过 SSE/查询/持久化泄漏。检查点历史可能保留中间产物用于审计，但不通过 API 交付。
- **记忆边界**：会话记忆只召回 `completed` 运行，`partially_completed` 不作为后续上下文（保守处理）。
- **前端**：新增“部分完成（仅交付已审核内容）”状态、部分交付提示、教师审核中的部分交付说明，并明确“审核通过不代表未交付内容已验证”。

### 相关文件

- `backend/app/agent_runtime/learning_package.py`：`QualityReview` 分项契约、练习失败降级、部分交付决策/组合、审核输出脱敏；`PROMPT_VERSION=learning-package-v2.7`
- `backend/app/agent_runtime/learning_graph.py`：审核中断 payload 携带 `partial_completion`
- `backend/app/api/v2/run_lifecycle.py`：`apply_settled_state` 计算部分完成状态；`WORKFLOW_VERSION=learning-workflows-v2.3`
- `backend/app/api/v2/learning_runs.py`：幂等重放覆盖部分完成状态
- `backend/app/agent_runtime/run_audit.py`：终态事件、`artifact_count`、`success_count` 语义
- `backend/app/evaluation/ablation_runner.py`：消融执行器兼容部分交付（不伪造练习产物）
- `frontend/src/views/LearningPackageView.vue`：部分完成展示与审核提示
- `docs/LEARNING_PACKAGE_GUIDE.md`、`docs/RUN_RECONCILIATION.md`：状态、交付、恢复与限制说明
- `.github/workflows/ci.yml`：CI 便携套件与覆盖率门禁加入新测试文件

## 三、验证结果

| 验证 | 结果 |
| --- | --- |
| 新增 `tests/a/test_learning_package_partial.py` | **22 passed**（11 个端到端场景 + 9 个契约参数化 + 2 个修复回归） |
| 本轮最终 CI 便携套件（35 文件，含新测试） | **346 passed / 1 skipped / 0 failed**（51.66 秒） |
| 核心覆盖率门禁 | **92.41%**（`learning_package.py` 94%、`claim_support.py` 83%），≥80% |
| Ruff 关键规则 / `git diff --check` | 通过 |
| 前端构建（含本轮前端改动） | 通过（`vue-tsc --noEmit` + `vite build`） |
| 独立对抗式复核（另一 Agent） | pass-with-findings，**无阻断缺陷**；发现并已修复 4 个非阻断问题（失败返工残留、Reviewer 文本泄漏、题号歧义、`suggested_query` 残留）；复核探针 16 项通过；最终复核确认 R1/D2 关闭 |

复核报告：`output/verify-partial-20261018/report.md`（含修复后复验与“Final confirmation (2026-10-18)”章节）。

**未在本轮验证**：真实模型在 v2.7/v2.8 提示词与部分交付分支上的独立新任务行为；浏览器端到端人工走查；远端 CI 实际结果；Linux 依赖锁。真实 PostgreSQL/Redis 集成已在隔离一次性容器上完成（见下文第四批），但不等于完整生产部署验收。测试通过不等于真实模型质量或事实支撑通过。

## 三之二、第二批：结构化输出稳定性与安全收口（2026-10-18 下午）

### 结构化输出（优先事项 3 的离线分析 + 有界付费复测）

- **诊断**：对 2026-10-17 开发集复测失败的 3 个任务（`ab-006/011/012`）做 13 次调用的有界诊断。6/6 次失败的 Practice 调用与 1 次 Tutor 调用都在**恰好 1024 output tokens** 上限处截断、JSON 未闭合；Planner 无截断。机制是长度截断，不是字段错误或拒答；旧解析器丢弃 `finish_reason`，重试提示也不要求缩短输出，所以重试仍然截断。
- **修复**（`learning-package-v2.8`）：暴露 `finish_reason`；JSON 解析容忍 Markdown 围栏与前后说明文字（仍严格按 Schema 校验）；识别截断后追加固定文案的精简要求，截断场景最多 3 次尝试、普通无效输出仍 2 次，全部计入既有调用/字符预算；消融执行器把“仅讲解、无练习”的降级结果标记为未完成完整任务（`learning_package_incomplete_package`），不再把部分交付计为完整成功。
- **有界付费复测**（单次、冻结证据、无 Reviewer 臂、1024 tokens/调，与历史配置一致）：开发集 **12/12** 完整任务（v2.6 为 9/12、v2.5 为 6/12），44 次模型调用，P50 12.47 s，输出 25,384 tokens；留出集 **12/12**（v2.5 为 7/12），43 次调用，P50 15.10 s，输出 25,286 tokens。两组各出现 6 次截断调用，全部经精简重试恢复。费用状态未知（未配置单价），只记录实际 tokens。
- **局限**：每个任务只运行一次，无方差估计；多个改动捆绑，不能把提升单独归因；留出集此前已被模型执行过，不是全新任务集；完整任务数只说明契约完整，**不证明内容质量**，人工逐 claim/练习评分仍未完成。公开记录见 [evals/results/structured-output-20261018.md](../evals/results/structured-output-20261018.md)。
- 真实模型下的部分交付分支（练习失败/删题）仍未单独验证。

### 安全收口（优先事项 6 的代码部分）

- 独立审计报告：`output/security-audit-20261018/report.md`。本地/离线演示无阻断问题；对任何联网生产发布有两个阻断项：**F1** SPA 静态回退的路径穿越任意文件读取；**F2** 所有随仓库发布的 compose/Dockerfile/示例 env 都未启用 `APP_ENV=production`，导致生产校验与 V1 门禁不生效。
- **已修复 F1**：SPA 回退改为 `resolve()` + 目录包含性校验，越界路径返回 404；新增 `tests/a/test_static_and_ws_safety.py` 覆盖 `../`、反斜杠、嵌套穿越。
- **已修复 F3**：V1 WebSocket `/api/v1/mobile/ws` 在生产模式 fail-closed（HTTP 中间件不覆盖 websocket scope）。
- **已修复 F4/F4b**：Docker `HEALTHCHECK` 与 `docker-compose.yml` 的后端健康检查从 curl 改为镜像内 Python 请求公开的 `/healthz`（HTTP 就绪检查，不再依赖已移除的 curl，也不会因生产模式下状态接口 401 而误判；`frontend.depends_on: service_healthy` 可正常满足）。同步更新 `docs/DOCKER-SMOKE-GUIDE.md` 排障说明。
- **未变更、需部署决策**：F2（企业部署仍默认演示模式）、F5（生产下未认证 `/docs`、`/metrics`）、F8–F10（第三方许可/NOTICE 与素材来源缺失）。发布前必须显式决定“演示模式 vs 生产模式”的边界。
- 独立复核：审计员正在复验 F1/F3/F4，结果将追加到其报告。

### CI / 环境（优先事项 5 的部分）

- 新增 nightly `linux-lockfile` 任务：在 Ubuntu + Python 3.12 上从 `requirements.txt` 生成 Linux 锁、安装并运行学习包核心测试，上传 artifact 供维护者复核后再提交为仓库锁文件；**远端尚未验证**。
- 修复既有心跳时序抖动：`tests/a/test_run_leases.py` 现在等待 Graph 实际进入生成后再让租约失败，10/10 次隔离重跑通过。
- Docker 当时不可用（CLI 无法连接 Linux engine；未自行拉取镜像）。**后续在 2026-10-18 检查时 Docker 已恢复可用**，并完成真实 PostgreSQL/Redis 集成（见下）；未拉取任何镜像，使用本机已有 `pgvector/pgvector:pg16` 与 `redis:7-alpine`。

### 真实 PostgreSQL / Redis 集成（2026-10-18 第四批）

- 使用本机已有镜像启动两个**一次性隔离容器**（仅绑定 `127.0.0.1:15439` / `127.0.0.1:16379`，测试后已删除；未触碰原有 `a3-*` 演示容器、未拉取镜像）。
- 在真实 PostgreSQL 16 + pgvector + Redis 7 上：
  - Alembic **upgrade head → downgrade base → upgrade head** 三步均退出码 0，`vector` 扩展已确认存在；
  - 企业合同测试子集（33 文件，含检查点跨进程恢复、未完成节点继续、PostgreSQL API 恢复、认证/课程授权、租约、检索、入库、Golden Set）**353 passed / 0 failed**（173.62 s）；
  - 新增 `tests/a/test_learning_package_partial_postgres.py` + helper：部分完成学习包在**真实 PostgreSQL 检查点**上跨进程 suspend/resume，教师审核后仍保持 `partially_completed`、仅交付 2 道练习且不重跑模型/检索，**1 passed**（已加入 CI enterprise 合同任务）。
- 这验证了真实数据库与检查点路径，但不等于生产全栈验收：未启动 `docker-compose.production.yml` 全栈，未验证 TLS/反向代理/Phoenix/备份，未在真实部署环境执行迁移窗口。

### 生产边界与部署配方（2026-10-18 第三批）

- **F5 已修复**：生产模式下 `/docs`、`/redoc`、`/openapi.json` 返回 404；根路径 `/metrics`、`/metrics/*` 需要教师/管理员会话（匿名 401、学生 403），开发模式不变。
- **F2 已收紧**：新增独立 `docker-compose.production.yml`（`APP_ENV=production`、`A3_OFFLINE_DEMO=0`、`V2_AUTH_REQUIRED=true`、数据库课程授权、检查点强制；所有密钥用 `${VAR:?}` 强制提供，无默认口令；数据库/Redis/Phoenix 不发布宿主端口；仅前端端口默认回环发布；migrate 先于 backend）与 `.env.production.example` 模板（全部为占位值）。
- `validate_deployment` 加强：数据库口令需 ≥12 字符且不得含 `change-me/changeme/replace/example/placeholder`；模型凭据与 CORS 来源同样拒绝占位标记（含 `REPLACE_WITH`/`your-domain`/`change-me`）；`/docs/`、`/docs/*`（含 `oauth2-redirect`）在 production 下一律 404。模板在启动时会失败关闭（有测试覆盖），填充后的 https 来源可通过。
- 新增 [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)：生产边界、启动命令、通过 `scripts/manage_access` 创建教师/授权课程、验证清单与未验证限制。README 增加链接。
- CI 质量任务新增 Compose 配置解析步骤（demo、demo+enterprise、production 三套）；本地 `docker compose config` 三套均通过（demo/enterprise 需先按文档复制 `.env`/`.env.enterprise`）。
- **仍未验证/未完成**：真实 Docker 引擎启动、迁移往返、真实 PostgreSQL/Redis 集成、TLS/备份/监控、Phoenix 镜像仍为 `latest`（正式部署前应固定）。
- **F8–F10（第三方许可/来源）部分完成**：独立审计生成根目录 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)（机器清单，非法律意见），覆盖 151 个 Python 组件、95 个 Web npm 组件、285 个桌面 npm 组件、126 个受跟踪媒体/打包文件；5 个 UNKNOWN 许可（均未安装的 Python 组件，未猜测）；`docs/03-开源参考与协议.md` 已链接完整清单。**仍需人工补齐**：`frontend/dist` 与桌面包无 LICENSE/NOTICE 文本；`frontend/public/integrated-map` 下的 React 构建无源码/来源；30 个陈旧 React bundle 无来源；125 个媒体文件无来源证明；psycopg 家族/edge-tts 为 LGPL，`imageio-ffmpeg` 捆绑 GPL FFmpeg 7.1，桌面分发前需人工许可审查；`docs/03` 仅覆盖部分直接依赖。

## 四、本轮变更文件

第一批（priorities 1–2）已跟踪修改：`backend/app/agent_runtime/learning_graph.py`、`backend/app/agent_runtime/learning_package.py`、`backend/app/agent_runtime/run_audit.py`、`backend/app/api/v2/learning_runs.py`、`backend/app/api/v2/run_lifecycle.py`、`frontend/src/views/LearningPackageView.vue`、`docs/LEARNING_PACKAGE_GUIDE.md`、`docs/RUN_RECONCILIATION.md`、`README.md`、`.github/workflows/ci.yml`。

第二批新增/修改：`backend/app/core/llm_client.py`、`backend/app/evaluation/ablation_runner.py`、`backend/app/main.py`、`backend/app/api/v1/mobile.py`、`docker/Dockerfile`、`.github/workflows/nightly.yml`、`.github/workflows/ci.yml`、`tests/a/test_run_leases.py`、`README.md`、`docs/LEARNING_PACKAGE_GUIDE.md`、`evals/results/structured-output-20261018.md`（未跟踪）、`tests/a/test_structured_output_robustness.py`（未跟踪）、`tests/a/test_static_and_ws_safety.py`（未跟踪）。

未跟踪新增（累计）：`backend/app/evaluation/ablation_runner.py`、`tests/a/test_learning_package_partial.py`、`tests/a/test_structured_output_robustness.py`、`tests/a/test_static_and_ws_safety.py`、`tests/a/test_learning_package_partial_postgres.py`、`tests/helpers/partial_package_checkpoint_worker.py`、`evals/results/structured-output-20261018.md`、`docs/OPTIMIZATION_STATUS_2026-10-18.md`、`.env.production.example`、`docker-compose.production.yml`、`docs/PRODUCTION_DEPLOYMENT.md`、`THIRD_PARTY_NOTICES.md`（后两项由独立审计生成）。

第三批其他修改：`.gitignore`（允许提交 `.env.production.example`）、`backend/app/core/deployment_policy.py`、`backend/app/main.py`、`tests/a/test_static_and_ws_safety.py`、`tests/a/test_deployment_policy.py`、`README.md`、`docs/03-开源参考与协议.md`（链接完整第三方清单）、`.github/workflows/ci.yml`。

磁盘上的 `frontend/node_modules`、`frontend/dist`、`.coverage`、`htmlcov`、`output/` 均为被忽略的本地产物，未加入提交范围。

## 五、剩余事项（建议下一步）

1. **真实人工评测（优先事项 4）**：两位独立评审完成留出集盲评与逐 claim 审查，必要时第三人裁决；程序不证明人的身份或评分独立性。
2. **真实部署验证（发布门）**：生产 Compose 全栈 `up`/镜像构建、TLS/反向代理、Phoenix、备份与迁移窗口仍需在目标部署环境验证；隔离容器上的 PostgreSQL/Redis 集成与部分完成恢复已完成（见第四批），但不等于生产验收。
3. **远端 CI**：本地工作流已加入新测试、Compose 解析与 Linux 锁任务，但未 commit/push，GitHub Actions 未验证。
4. **Linux 锁文件**：复核 nightly 生成的 artifact 后提交 `requirements.lock.linux.txt`，并验证安装。
5. **真实模型独立任务验证**：在未使用过的新任务上复测 v2.8，并单独验证部分交付分支；如实记录失败、调用数、延迟与可得用量，不虚构账单或人工评分。
6. **交付材料**：第三方 NOTICE 已生成机器清单，仍需补齐许可文本/素材来源、真实演示视频、Release 与部署说明复核。
7. **提交前复核**：按 `output/baseline-audit-20261018/report.md` 的提交前建议，区分三轮改动与此前未提交成果，确认不包含 `output/` 原始资料或任何密钥。

## 六、约束遵守情况

- 未自行下载依赖或 Docker 镜像：前端依赖只从本机 npm 缓存离线安装（`npm ci --offline`），未联网；未执行 `docker pull`/`docker compose up`。真实模型调用使用已授权额度，范围为有界诊断（13 次）与两组各 12 任务复测（44/43 次调用），原始响应只存本地 Git 忽略目录。
- 未上传任何密钥、令牌、连接串、私有课程原文或原始评测资料。
- 未执行 `git reset --hard`、`git clean`、覆盖用户数据或他人的工作区改动。
- 测试使用 `output/<独立目录>` 下的新 `--basetemp` 与隔离 SQLite 文件。
- 本轮未 commit、未 push；工作区仍保留此前未提交成果与两批改动。
