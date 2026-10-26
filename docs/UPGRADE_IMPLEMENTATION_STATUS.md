# 升级实施记录

更新：2026-10-14。完整范围见 [优化交接](OPTIMIZATION_HANDOFF_2026-10-18.md) 与 [主计划](QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md)。各批次结果只对应当批验证范围，后续批次补齐的能力不回填成历史验收结果。

## 第一批：P0 可信运行底座

已实现的代码变更：

- 每个 Run 使用服务端 UUID 作为 Graph thread ID，拒绝额外的客户端 thread_id 字段。
- Run 查询从数据库读取，验证身份、课程与归属；新增受相同权限保护的节点事件查询。
- 学生不能审批；教师限于 `V2_TEACHER_COURSES` 的课程。等待审核及正在审批期间均不向学生返回草稿或来源。
- 审核通过数据库条件更新抢占执行权，重复审批返回 409。旧版共享会话检查点返回 `legacy_run_restart_required`，需重新发起任务。
- 未实现的更新画像、删除、发布和外发请求直接拒绝；人审只审核学习内容。
- 生命周期写库失败不会继续报成功。Graph / 数据库异常仅通过稳定错误码和 Run ID 对外报告。
- 已完成或已进入审核的结果落库后，客户端断连不会覆盖其状态；未完成任务断连记录为 interrupted。
- 同步检索放在线程中执行，节点开始与完成实时发送。最终 answer.delta 表示审查后交付，不宣称模型 token 实时生成。
- 修复 RRF 原始分数污染，保存各检索器的排名贡献；单一路径也最多返回 5 个来源。
- 评测器升级至 2.0：严格从有序 evidence 计算来源 Top-5，区分 Hit、Recall、引用存在与引用身份有效性；不声称已经完成语义忠实度验证。
- 报告包含评测版本、数据集签名、原始预测和评测模式。禁止无提示覆盖报告；不同版本或数据集的基线不允许比较。
- `APP_ENV=production` 启动时检查模型凭据、PostgreSQL 密码、认证和 HTTPS CORS 配置，禁用内置演示账号；开发模式保持本地兼容。

## 评测集迁移

旧 `golden_set_zh.jsonl` 的 66 条用例和历史报告原样保留。

新 `golden_set_zh_v2.jsonl` 共 76 条：48 条事实问答、18 条拒答、10 条学习内容人审。
原 10 条写操作问题保持问题和 ID，只将预期从“进入审核”纠正为“拒绝未实现操作”；另外新增 10 条真正的学习内容人审问题。

96.97%、95.83% 等数字仍只属于 2026-10-11 的历史口径。不能把它们复制到新版本基线。

## 验证范围与边界

本批测试使用临时 SQLite 生命周期数据库、真实 LangGraph 与测试用内存 Checkpointer；模型与检索输出使用可控桩。
覆盖并发 Run 隔离、跨用户访问、审核草稿隔离、Graph 中断/恢复、审批原子抢占、非阻塞检索、失败脱敏、RRF 和评测反例。
测试依赖安装在 `.tmp/p0-deps`，不修改系统 Python 环境。

这不是 PostgreSQL 崩溃恢复或云端模型质量验收。当批 Docker 服务未启动，自己的新 API Key 尚未提供，因此没有使用队友凭据重跑在线评测。后续用户已配置自己的 DeepSeek Key；配置更新不等同在线验收授权。
当批 P0 的 PostgreSQL 集成验收与新在线基线待完成；后续第六批补齐 Graph 检查点跨进程恢复，完整 API / 数据库一致性与云端验收仍待完成。

已将相关测试接入 CI 的 enterprise-contract 作业；本地测试结果以 `output/upgrade-p0/pytest.xml` 为准。
本次离线回归结果：60 项通过、1 项 PostgreSQL 集成测试因未配置测试数据库跳过；CI 尚未执行。

## API 兼容说明

- `POST /api/v2/learning-runs/stream` 仍创建并流式执行问答。
- `GET /api/v2/learning-runs/{run_id}` 现在必须登录；数据库故障返回 503。
- `GET /api/v2/learning-runs/{run_id}/events?limit=100` 返回持久化节点审计，最多 500 项；只含节点、状态、耗时和证据数量。
- `POST /api/v2/learning-runs/{run_id}/resume` 仅授权教师可用，缺少可恢复 Checkpointer 返回 503。
- 节点事件新增 `node.started`、`node.completed`；`retrieval.completed` 在检索结束时发送数量与耗时，最终引用位于 `run.completed`。
- 事件查询目前用于审计，不是带 Last-Event-ID 的 SSE 补发服务；持久化顺序号、取消/继续执行及租约恢复属于 P3。

## 第二批：学习包、受限 ReAct-style 检索决策循环与会话记忆

已新增 `/learning-package` 页面和 V2 `mode=learning_package`：Planner 生成受约束的依赖计划，Tutor 根据检索 observation 决定继续查询或生成，Practice 使用上游讲解出题，Reviewer 最多触发一次返工。
计划固定 Tutor → Practice 两步；受限 ReAct-style 检索决策循环只允许 `search_course` / `finish`，最多检索 3 次，不是开放式多工具 Agent 或任意 DAG。
普通 V2 问答与学习包都接入数据库支持的最近三次已完成问答记忆；同用户、课程和会话隔离，排除待审、失败、拒绝和未认证运行。
本批是 P1/P2 的部分能力落地，详细契约和预算见 [学习包使用说明](LEARNING_PACKAGE_GUIDE.md)。
验证：后端新增功能与 P0 兼容回归 87 项通过、1 项 PostgreSQL 测试跳过；前端流式解析 5 项通过，类型检查与生产构建通过。
Playwright 使用模拟接口检查完成展示、答案展开、学生待审隐藏、教师查询与通过审核，并检查桌面及窄屏布局。截图在 `output/playwright/learning-package-*.png`，后端报告在 `output/upgrade-learning-package/pytest.xml`。这不是云端模型或真实 PostgreSQL 的端到端验收。

## 第三批：细粒度引用与验收口径修正

- 讲解和每道练习分别返回服务端生成的结构化 citations，页面逐项显示来源与分块 ID。
- 最终引用与教师审核引用只包含实际使用的 source_ids，按 chunk_id 去重；完整 evidence 保留用于审计。同文档的不同分块不会合并丢失。
- Reviewer 返工后只使用最终产物的引用；人工替换答案时清除旧学习包及旧引用，避免错配。
- README、演示与发布材料区分“旧版 66 条在线基线（历史）”与新版待验收项，移除将未实现写操作描述为人审后执行的说法。
- 本批定向离线测试：`tests/a/test_learning_package.py` 26 项通过，覆盖未使用证据排除、去重、分项引用、返工与人审恢复后的引用一致性；SQLite、可控模型输出、内存 Checkpointer 不代表真实 PostgreSQL/云端验收。
- 前端 `npm run build`（`vue-tsc --noEmit && vite build`）通过；本批仅做类型检查与生产构建，没有重跑浏览器或真实云端验收。Python 变更文件的 Ruff `F,E9` 检查通过。

本批验证命令（PowerShell，项目根目录）：

```powershell
$env:PYTHONPATH = 'D:/xunfei/triple-U/.tmp/p0-deps;D:/xunfei/triple-U'
$env:A3_OFFLINE_DEMO = '1'
& 'D:/Anaconda3/envs/dxtorch/python.exe' -m pytest tests/a/test_learning_package.py --no-cov --benchmark-disable -q -o faulthandler_timeout=30 --basetemp .tmp/citation-regression-20261012 -o cache_dir=.tmp/p0-pytest-cache
& 'D:/Anaconda3/envs/dxtorch/python.exe' -m ruff check backend/app/agent_runtime/learning_package.py tests/a/test_learning_package.py --select F,E9
```

在 `frontend` 目录执行 `cmd /c npm run build`。测试临时目录与构建产物仅留在本地，不纳入正式提交。

新版 76 条 Golden Set 与学习包仍待真实 Docker + PostgreSQL + 云端模型验收。76 条当前覆盖普通问答、拒答与内容人审，不等于已完成学习包专用评测；旧版历史指标不得沿用。在线验收需要用户事先授权，并会产生模型及 Embedding 调用费用。

## 第四批：学习包专用离线评测（2026-10-13）

- 新增 `evals/learning_package_cases_v1.jsonl`：正常任务、证据与返工、边界与失败各 8 条；每类开发/固定留出各 4 条，共 24 条。与旧 66 条及新版 76 条问答集独立。
- 新增离线评测器及 `scripts/evaluate_learning_package.py`：检查两步计划、三道题、分项引用与实际引用并集、报告预算和安全终态。预期失败正确终止算契约通过，不算学习内容生成成功。
- 独立人工审查表覆盖事实支撑、练习答案、目标覆盖、难度递进，以指纹绑定用例与原始输出；缺失或过期审查时完整质量指标为 null，不把模型 Reviewer 通过当作事实正确。
- 报告记录版本、数据集签名、划分、预测来源类型、逐例结果和原始输入；默认只统计开发集，拒绝覆盖文件、重复 ID 和未知 ID。合成输入不报告真实性能。
- 评测器不加载密钥、不发网络请求。当批尚未实现 24 条统一采集/故障注入执行器，后续第五批完成离线执行器；仍未执行真实模型任务，不能宣称在线通过率。
- 定向离线验证：评测器 51 项、学习包工作流 27 项，共 78 项通过；Ruff F/E9 检查和 24 条数据格式校验通过。CI 已加入新测试，但没有远端运行记录。没有前端代码变更，沿用第三批构建结果，不把它作为本批重新构建的证据。

本批测试命令（依赖路径和离线环境变量同第三批）：

```powershell
python -m pytest tests/a/test_learning_package_evaluator.py tests/a/test_learning_package.py --no-cov --benchmark-disable -q -o faulthandler_timeout=30 --basetemp .tmp/package-eval-integration-20261013 -o cache_dir=.tmp/p0-pytest-cache
python -m ruff check backend/app/evaluation/learning_package.py scripts/evaluate_learning_package.py tests/a/test_learning_package_evaluator.py tests/a/test_learning_package.py --select F,E9
python scripts/evaluate_learning_package.py --validate-only --split all
```

本机 Python 使用 `D:/Anaconda3/envs/dxtorch/python.exe`。完整协议与复核命令见 [学习包评测说明](../evals/LEARNING_PACKAGE_EVAL.md)。下一步仍须真实 PostgreSQL 恢复、统一运行采集、云端质量与人工留出集审查，付费调用另行授权。

## 第五批：离线运行采集与故障注入（2026-10-13）

- 新增 `scripts/collect_learning_package.py` 与 `backend/app/evaluation/package_collection.py`，通过进程内 ASGI 调用现有 V2 API、真实 LangGraph 和运行持久化；模型、检索、画像、身份和 Checkpointer 使用隔离测试适配器。
- 输出实际 SSE 帧、模型/检索注入轨迹、下游依赖及返工意见、节点审计、数据库终态与独立 SQLite。每个用例使用独立会话；不连接用户数据库、不读取密钥文件、不调用云端。
- 全部 24 条离线契约满足预期：16 条完成模拟学习包、5 条按指定错误码失败、2 条安全拒绝、1 条待审。保存预测后再次通过独立评测脚本回放。内容质量指标为 null，不能称为云端成功率或召回率。
- 评测器把采集/持久化检查失败纳入失败结果，拒绝把 `synthetic_asgi` 预测改标为真实记录。已有目录/报告不覆盖，每例预测及时写出便于失败排查。
- 定向回归 113 项通过（采集器 35、评测器 51、工作流 27）；Ruff F/E9 通过。CI 加入采集器测试，未执行远端 CI。本批没有前端变更，没有重新构建前端。

本机运行命令（Python 路径及离线依赖变量同前批）：

```powershell
python scripts/collect_learning_package.py --split all --output-dir output/package-collection-20261013
python scripts/evaluate_learning_package.py --predictions output/package-collection-20261013/predictions.jsonl --split all --output output/package-collection-20261013/replayed-report.json --enforce-contracts
python -m pytest tests/a/test_learning_package_collection.py tests/a/test_learning_package_evaluator.py tests/a/test_learning_package.py --no-cov --benchmark-disable -q -o faulthandler_timeout=30 --basetemp .tmp/package-collection-tests-20261013 -o cache_dir=.tmp/p0-pytest-cache
python -m ruff check backend/app/evaluation/package_collection.py backend/app/evaluation/learning_package.py scripts/collect_learning_package.py tests/a/test_learning_package_collection.py --select F,E9
```

输出目录已经存在，再次运行须换新目录。本地产物不提交。仍待完成：真实 PostgreSQL 恢复、真实登录/权限环境、经授权的云端采集与质量评审；离线身份与检索桩不能用来证明这些能力已经验收。

## 第六批：真实 PostgreSQL 检查点跨进程恢复（2026-10-13）

- 将原先关闭/重开数据库连接的单例测试扩展为 7 项独立进程测试：普通问答通过审核；学习包的未使用证据、Reviewer 返工换来源两种场景，各覆盖通过、人工修改、拒绝。
- 使用 Docker 独立 PostgreSQL 16 测试容器，仅绑定本机端口，tmpfs 数据目录；没有业务数据卷，也不读取密钥文件。模型和检索使用测试桩，HTTP 适配器禁用。
- 检查点提交后直接终止应用测试进程，新进程读取同一 checkpoint ID 恢复。恢复阶段调用模型或检索会失败；验证了预算不增长、分项引用保持正确、人工替换清除旧引用、拒绝不交付待审内容。
- 实际运行 7 项通过（30.00 秒）；首次沙箱运行因本机异步连接阻塞超时，经授权在沙箱外重跑通过。报告：`output/checkpoint-restart-20261013/pytest-unrestricted.xml`。Ruff F/E9 通过；本批无前端变更，不重复构建。
- CI 原 enterprise-contract 作业已包含此测试文件，未运行远端 CI。不提交本地产物、不推送。

复核命令、隔离方法和边界见 [PostgreSQL 检查点验收](POSTGRES_CHECKPOINT_ACCEPTANCE.md)。这不是 PostgreSQL 服务自身崩溃恢复，也不证明完整 API、Run 审计与检查点原子一致性、任意节点恢复或云端内容质量。

## 第七批：检查点与 Run 状态修复（2026-10-13）

- 新增教师专用 `POST /api/v2/learning-runs/{run_id}/reconcile`：当 Run 处于 failed/interrupted，且 Graph 已保存待审或最终检查点时，修复数据库展示状态，不再次调用模型或检索。
- 检查运行、用户、课程、问题、审核要求和工作流版本；活动任务、缺失或未稳定的检查点拒绝修复。待审草稿继续对学生隐藏，审核决定及学习包细粒度引用保持不变。
- 普通交付和状态修复共用结果组装逻辑；SQL 条件更新防止并发覆盖，修复状态与审计记录在同一事务提交，审计失败回滚。客户端断连先停止 Graph，再写 interrupted。
- 31 项新增故障注入测试；与生命周期 19 项、学习包 27 项、离线采集器 35 项一起回归，共 112 项通过（12.30 秒），另有 1 条第三方 TestClient 弃用警告。Ruff F/E9 通过。报告在 `output/reconcile-20261013/pytest-final.xml`。
- 验证仍为 SQLite、内存 Checkpointer、模拟模型；新增接口未做真实 PostgreSQL 集成与云端验收。未修改前端、未重复构建，CI 已接入测试但未运行远端 CI。没有使用密钥或付费调用。

接口、错误码、复核命令和边界见 [Run 状态修复说明](RUN_RECONCILIATION.md)。此能力不等同租约恢复：进程被杀死后残留 running/reviewing 的任务仍待后续处理，也没有宣称 Run 和 Graph 检查点原子一致。

## 第八批：执行租约与恢复页面（2026-10-13/14）

- Run 增加 execution_id 和数据库时钟租约，45 秒有效、10 秒心跳；写入结果、节点和检索审计前校验执行代次。服务启动清理最多 1000 条过期任务，不自动重跑。
- 教师可显式恢复租约过期且具有稳定检查点的任务。新旧检查点执行代次不匹配则拒绝；任意未完成节点续跑仍未实现。
- 迁移 0007 支持新库/旧库，保留历史 Run；修复此前纯 Alembic 新库缺少 agent_runs 的问题。迁移只在独立测试库执行。
- 11 项租约、2 项迁移及 112 项相关离线回归通过。5 项真实 PostgreSQL + ASGI API 进程退出故障注入通过（39.27 秒），报告 output/lease-recovery-20261013/postgres-api-verified.xml；身份、模型、检索为桩，不能当成真实身份或云端质量验收。
- 学习包页面新增教师恢复、人工替换答案、停止请求按钮。Playwright 模拟 API 验证查询失败任务→恢复待审→替换交付，载荷和旧引用清除符合预期；检查桌面/390px 页面及取消请求。截图 output/playwright/lease-*-20261014.png。本地前端类型检查和生产构建通过。

详见 [Run 状态修复说明](RUN_RECONCILIATION.md)。租约只约束 Run 写入，不保证模型调用或 Checkpointer 写入 exactly-once。

## 第九批：持久化登录与逐账号课程授权（2026-10-14）

- 新增 auth_sessions / course_grants、迁移 0008 与可信管理 CLI。令牌只存摘要；注销、改密、改角色及删账号撤销对应会话；生产模式禁止内置会话和公开注册教师。
- 注册/恢复密码改用带盐 PBKDF2；旧 SHA-256 在成功登录时升级，与会话签发同一事务。同名注册仅新增，不能覆盖已有凭据；数据库读取代替内存账号缓存作为认证依据。
- V2 生产模式强制逐账号课程授权。开发模式可选择环境白名单或 database 模式；课程撤销从后续请求生效。同步鉴权查询移出异步事件循环。
- 已通过首轮登录相关 33 项离线回归，以及迁移、独立进程登录、Run 修复/租约等 48 项集成回归（23.12 秒）。后者包括 SQLite 与真实 PostgreSQL 上未模拟身份的令牌跨进程、课程撤销及注销检查；没有调用模型。报告分别为 output/auth-20261014/first.xml 和 integration.xml。
- 补齐改角色撤销、学生恢复账号、匿名拒绝、权限库故障和 CLI 测试后，最终定向回归 43 项通过（38 项登录相关 + 5 项 PostgreSQL API 故障修复，122.50 秒），报告 output/auth-20261014/final.xml。最终前端 `npm run build`（vue-tsc + Vite）及 Python Ruff F/E9 通过；第三方弃用警告仍保留，未运行远端 CI。
- 兼容变化、CLI 用法和范围见 [登录与课程授权](AUTH_AND_COURSE_ACCESS.md)。新部署前需要运行迁移，旧内存令牌需重新登录；没有更改用户业务数据库或密钥。

本批主要文件：backend/app/api/v1/auth.py、backend/app/api/v2/access.py、backend/app/repositories/account_repo.py、新增 auth_repo.py 和 core/passwords.py；core/models.py、main.py、V2 learning_runs.py/run_lifecycle.py；迁移 20261014_0008_auth_sessions.py、scripts/manage_access.py、3 个认证测试文件及独立进程 helper。另更新企业配置示例、Compose、CI、README 与部署文档。前端继续完善 LearningPackageView.vue 的取消及权限错误提示。

本机测试命令（项目根目录，沿用已安装离线依赖；TEST_V2_POSTGRES_URL 仅指向 tmpfs 测试容器）：

```powershell
$env:PYTHONPATH = 'D:/xunfei/triple-U/.tmp/migration-deps;D:/xunfei/triple-U/.tmp/p0-deps;D:/xunfei/triple-U'
$env:A3_OFFLINE_DEMO = '1'
# DATABASE_URL 显式指向独立临时 SQLite；不得使用业务数据库。
python -m pytest tests/a/test_auth_migration.py tests/a/test_auth_restart.py tests/a/test_learning_run_reconciliation.py tests/a/test_run_leases.py tests/a/test_learning_runs_v2.py --no-cov --benchmark-disable -q
python -m pytest tests/a/test_persistent_auth.py tests/a/test_registered_account_persistence.py tests/a/test_registration_onboarding.py tests/a/test_student_data_deletion.py tests/a/test_v2_access.py tests/a/test_deployment_policy.py tests/a/test_postgres_api_recovery.py --no-cov --benchmark-disable -q
```

本机 Python 为 D:/Anaconda3/envs/dxtorch/python.exe；前端在 frontend 目录执行 `npm run build`。现有临时目录与报告保留，不覆盖旧结果；未暂存、未提交、未推送。

## 后续阶段

以下是第九批结束时的待办快照；本轮进度以新增的第十批记录为准。

教师课程环境变量仅用于开发兼容，生产 V2 已切换逐账号授权；现有 Guard 仍是规则防线，不是完整提示注入防护保证。

## 第十批：V2 十模块补全（2026-10-14，本工作树）

实现入口与失败边界见 [十模块实现详解](V2_TEN_MODULE_IMPLEMENTATION.md)。本批已加入角色输入/输出/工具契约与提示词版本、统一只读课程工具、脱敏工具事件、严格 V2 模型适配及实际 token/估算费用、Run 事件序号和创建幂等、从未完成 Graph 节点继续执行、摄取任务/文档版本幂等、登录限流及过期会话清理。学习包页面新增工具进度、用量状态和续跑入口。检索可分别运行稠密、混合、混合加多样性策略；默认保持混合，固定候选集对比脚本只提供离线重排分析，不自动推广策略。新增本地只读 MCP 适配器固定 `mcp==2.3.0`，SDK 安装遭遇 TLS 错误，真实 MCP 协议互操作尚未验收。

本轮结果目前为：摄取相关 3 项、认证相关 19 项、检索相关 5 项通过；此前本轮已验证工具/模型/学习包/Run 共 33 项，持久事件/幂等相关 63 项，未完成节点续跑相关 23 项（测试组相互重叠，不能相加为唯一总数）；前端 `npm run build` 通过。新增费用预留测试及完整相关回归仍需最终执行。上述均为离线契约结果，不是新版 76 条在线质量结果。

评测专用 `V2_EVAL_BUDGET_CNY` 通过 Redis 对单次调用作保守费用预留，要求同一 campaign ID 与输入/输出单价上界；失败后不退预留额。当前官方定价与本机模型配置、币种换算尚需运行前核对，不能把该机制称为提供商账单保证。隔离 tmpfs PostgreSQL 上既有 5 项 API 故障恢复测试与新增 1 项 Graph 未完成节点跨进程续跑测试通过；后者使用桩，未覆盖在线模型或数据库服务崩溃。真实 Docker/Celery 摄取故障、DeepSeek 76 条/学习包在线验收与人工内容复核仍待完成；旧 66 条历史指标不迁移。V1 全量资源隔离、完整在线检索消融、浏览器续跑联调和演示录制也未完成。

### 本轮最终定向复核（2026-10-14）

- 模型用量、费用门禁、普通问答及学习包引用相关离线测试重跑：33 项通过；新增 Embedding 与模型共用 Redis campaign、超限拒绝测试后再次定向验证。前端 `npm run build` 已通过。所有离线指标均不代表内容质量。
- 隔离 PostgreSQL（tmpfs、非业务卷）中：既有 5 项 ASGI 故障恢复、1 项未完成节点跨进程续跑、1 项课程/最新版本检索及 1 项重复摄取向量版本测试通过。最后一项以受控 1024 维向量验证文档和版本只各写一次；Celery 进程故障与实际 Embedding 摄取尚未测试。
- 已获授权的云端单例冒烟从隔离容器读取运行环境密钥，所有付费请求共用 Redis campaign，100 元上限，输入/输出/Embedding 均按每百万单位 100 元上界预留。两次 DeepSeek 最小请求成功并返回实际 token；两次 Embedding 请求收到 `embedding_provider_http_403`。Redis 预留合计 0.4256 元，此值是保守额度扣减，**不是**供应商实际账单。出于检索链路未通过，未运行新版 76 条或学习包在线质量评测，没有新版准确率/召回率。
- 默认检索仍为 hybrid；三策略脚本只支持固定候选集重排对比，尚无同一真实语料的完整召回、安全回归和端到端延迟数据，故不切换默认值。本地只读 MCP 因 SDK 下载 TLS 问题未完成协议互操作测试。教师端/学生端续跑页面尚未做真实浏览器端到端测试。

### Flash Embedding 切换与部分在线检索（2026-10-15）

- 用户确认旧 Embedding 模型已过期。根据[阿里云向量模型列表](https://help.aliyun.com/zh/model-studio/embedding-rerank-model)，运行环境的 `EMBEDDING_MODEL` 改为 `qwen3.7-text-embedding-flash`，维度继续为 1024；DeepSeek 对话模型与原有 Embedding 密钥均未更改。旧模型的两次 HTTP 403 是切换前记录；Flash 单例向量请求成功。
- 在[检索实现](../backend/app/services/enterprise_retriever.py)中，稠密候选只读取与当前 Embedding 模型相同的向量版本；[课程回填](../backend/app/services/knowledge_ingest.py)检测模型切换后生成新文档版本，即使正文和维度没变。对应离线 9 项及隔离 PostgreSQL 2 项定向测试通过。旧向量不能只因同为 1024 维而沿用。
- 在隔离 PostgreSQL 中尝试批量回填 38 份 AI 课程 Markdown；批量请求间歇性失败，运行中主动停止以保留 100 元预算给后续验收，因此语料未全部完成。固定的部分语料下，48 条事实题有 43 条的标注来源已具备 Flash 向量；从中取前 10 条进行**pgvector-only** 在线检索，Top-5 命中 8/10、标注来源召回 0.8。此为不完整语料、筛选后的小样本诊断，不能宣传为新版 Golden Set 指标。三策略完整对比因请求波动和执行中断没有可用结论，默认 hybrid 未切换。
- 本次所有付费请求仍经过同一 Redis 100 元预留闸门，记录的数值仅是保守预留，并非实际账单。Docker 引擎随后停止，未继续 76 条问答、学习包、真实 Celery 故障或浏览器端到端验收；恢复这些验收时需重新确认容器及预算计数器状态，不可复用已停机的临时数据库作为通过证据。

### Docker 恢复后的非付费收口（2026-10-15）

- Docker 恢复后，先前 tmpfs PostgreSQL 的课程语料和模式已消失；Redis 从旧快照恢复的预算计数器为 61.7571 元，低于停机前已观察到的 63.2545 元，而且中断前还有未完成的请求。因此真实预留总额无法精确重建，将该**同一 campaign** 计数器保守封顶为 100 元，阻止本轮再产生付费请求；这不代表实际支出已达 100 元。没有把重启当成重置额度的理由。
- 在重建的隔离 PostgreSQL 中，Flash 模型隔离和摄取/向量版本测试再次通过 2 项；相关离线回归 42 项通过。新增[已审核文档向量重建入口](../backend/app/services/vector_reindex.py)与[命令](../scripts/reembed_enterprise_vectors.py)：教师上传资料和课程文档都可在模型切换时基于已有片段创建新版本，失败保持旧版本；SQLite 单元测试 2 项、PostgreSQL 事务测试 1 项通过。该命令尚未对真实教师上传数据进行付费批量运行。
- [课程回填脚本](../scripts/backfill_enterprise_corpus.py)现在分别报告 `indexed`、`embedded`、`embedding_failed`，后者非零时返回失败；其汇总测试 1 项通过。此前中断的三策略在线长测没有完整报告，不能引用为结论。默认混合检索仍保持不变。

### 交接后的无付费复核（2026-10-15）

- 核对当前分支仍为 `feat/enterprise-agent-rag-stack`；工作树原有大量未提交变更均保留，未暂存、重置、提交或推送。`git diff --check` 无空白错误。未调用 DeepSeek 或 Flash，也未使用旧 100 元 campaign。
- 隔离 SQLite/受控模型的定向回归分两组运行，分别为 36 项与 94 项通过；组间可能重叠，不能相加为唯一总数。覆盖认证/课程权限、迁移、Run 事件与续跑、审核和修复、摄取/重建、费用门禁、学习包与检索策略。独立 SQLite 文件上的 Alembic 全链 `upgrade head` 与 `downgrade base` 均通过。前端构建通过；SSE 解析 5 项、演示资产健康检查 14 项通过。
- 固定 `mcp==2.3.0` 安装在 `.tmp/mcp-deps`。新增[协议测试](../tests/a/test_mcp_readonly_protocol.py)，用真实 MCP 客户端验证四个只读工具发现、调用及参数错误返回；隔离 SQLite 中撤销课程授权后，进程内及独立 stdio 调用均返回 `denied`。协议测试连同工具测试 4 项通过。尚未验证生产启动器或外部 MCP 宿主。
- 真实浏览器配本地模拟 API 验证学生 SSE 提前结束→任务查询→中断节点续跑，教师审核通过/拒绝，讲解和三道题逐项引用、费用 unknown 提示，以及窄屏布局。模拟 API 不等于真实后端/模型端到端验收。
- V1 资源/课程隔离相关回归首次 43 项有 1 项失败：旧演示画像测试直接读取本机可变数据库，导致预期策略受本地数据影响。改为读取固定 `seed.json` / `seed_extended.json` 后，失败项复测通过；其余 42 项原轮通过。未宣称 V1 全路由隔离审计完成。
- CI 企业契约作业已纳入本轮新增的认证、续跑、事件、摄取、重建与费用门禁测试，并在独立步骤安装固定 MCP SDK 运行协议测试；远端 CI 尚未运行。本机当前 shell 未找到 Docker CLI，本轮未重跑隔离 PostgreSQL 或真实 Celery Worker 进程故障测试。
- 排查真实 Worker 前发现本机上传路径与 Worker 的硬编码 `/app/data/ingest_staging` 不一致；两端现共用[暂存路径模块](../backend/app/services/ingestion_staging.py)，保留解析后路径必须位于允许目录内的校验。新增路径接受/越界拒绝测试 1 项通过，相关 Ruff F/E9 与 `git diff --check` 通过。Celery 依赖在获准下载后仍因 PyPI TLS 连接失败而未装成，因此不能把路径单测当作真实 Worker 验收；本轮一次更宽的摄取测试组合在现有异步用例处久等后中止，也不计入通过项。
- V1 路由静态巡检曾发现，`main.py` 把 chat、profile、resources、mistakes、group-chat 等多组旧接口列为无需认证的公开前缀；下一项已补生产模式登录检查。现有 43 项资源/课程回归只能验证已覆盖的过滤逻辑，不能证明所有 V1 路由具备逐账号隔离；逐路由身份与课程授权审计仍是待办。
- 用户安装 Celery 5.6.3 与 Redis Python 客户端 8.1.0 后，用本地 filesystem broker、隔离 SQLite 和摄取桩启动真实独立 Celery solo Worker：重复投递同一任务只执行一次摄取；处理中杀死 Worker，显式令租约过期并再次投递后，新 Worker 接管完成。固化为[进程测试](../tests/a/test_celery_worker_process.py)；连同部署策略和暂存边界最终共 15 项通过。此测试没有 Redis broker、PostgreSQL、真实云端摄取，也不证明 broker 自动重投或跨系统 exactly-once。
- 生产模式下不再跳过旧 V1 演示路由的登录检查；resources、chat、group-chat 匿名请求拒绝的 3 项新测试通过。开发模式原演示公开前缀继续可用。这只补上匿名访问入口，按账号/课程/资源逐路由授权仍待完整审计。
- 用户提供 Docker Desktop 路径后，确认 `docker.exe` 可用；此前只是未列入 PATH 且沙箱不能访问 Docker 命名管道。启动各自使用 tmpfs、只绑定 `127.0.0.1` 的独立 pgvector/Redis 容器，不挂业务卷；Alembic PostgreSQL 全链升到 `0011` 通过。补装 `pgvector==0.5.1` 后，隔离 PostgreSQL 的 API 故障恢复、未完成节点续跑、检索、重复摄取与向量重建组合共 10 项通过。初次缺少 Python pgvector 包时，重复摄取用例曾因 ORM 退回 JSON 而失败；补装后已复测通过，未改数据库模型来掩盖缺依赖。
- 同一[Worker 探针](../tests/helpers/celery_ingestion_worker_probe.py)再分别接入独立 Redis broker，以及独立 Redis broker + PostgreSQL 摄取任务账本，均通过重复投递只执行一次、处理中杀进程后显式重新投递并由过期租约接管的场景。摄取服务使用桩，未验证 Redis 自动重投、真实云端调用或 exactly-once。两个本轮临时容器已停止并由 `--rm` 删除；未触碰既有容器/卷或旧预算 campaign。
- [V1 资源端点](../backend/app/api/v1/resources.py)补学生写入归属校验：不能伪造其他账号或发布课程/指派资源，删除仅限个人资源。课程过滤、协作资源及前 2 项所有权测试组合 38 项通过；再补真实 HTTP 路由用例后，所有权测试单独 3 项通过。生产 V1 的逐路由课程授权仍未完成。

### V1 资源边界与本地后端浏览器复核（2026-10-15）

- 生产模式下，学生资源可见性现在逐次核对 `course_grants`：课程已发布资源、定向指派资源及带课程标记的个人资源在授权撤销后均不再返回。教师草稿不会因为第一位目标学生被写入 `user_id` 而提前可见；定向资源还需目标名单匹配。旧资源列表、详情、附件下载、移动端资源入口复用此判断；推荐接口也拒绝学生伪造其他账号或请求未授权课程。独立 SQLite 的真实登录、授予/撤销与 HTTP 请求，以及资源/教师协作/移动端组合共 **55 项通过**。这只覆盖资源链及推荐入口，不能代表 V1 全部 181 个端点已完成逐账号/课程审计；教师 V1 管理端的逐课程边界仍需继续治理。
- 扩大回归时修复教师推荐学习路径的标题被最后一个阶段覆盖的问题；分别检查三阶段路径按教师顺序前进、单阶段路径完成后自动续接。上述 55 项包含此回归。此前组合出现的 2 项失败已修复并复测通过。
- 生产前端在未显式配置 `VITE_API_BASE_URL` 时改为同源 API；开发服务器未配置时仍指向本地 `8000`。`vue-tsc` + Vite 构建通过。真实 Playwright 浏览器使用 FastAPI 提供的构建页面与独立 SQLite：登录成功，V1 数据请求同源 200；加载 LangGraph 后，V2 学习包 SSE 返回 Run 编号，`LLM_PROVIDER=mock` 下按严格模型规则失败，页面显示失败、能按编号查询已保存 Run 和事件。该检查没有云端调用，不能算成功生成学习包或在线质量验收；此前成功/审核 UI 使用模拟 API 验证。
- 本地 CI 关键 Ruff `F821,F823,E9` 首轮发现 `scripts/test_refs_locally.py` 中 9 处动态 `exec` 载入函数的静态未定义报错；改为显式从动态命名空间读取后，全量 `backend/app scripts/ tests/` 检查通过，脚本八道参考实现自检运行成功。SSE 解析 5 项、`git diff --check` 通过；本地临时后端与 Playwright 会话已关闭。远端 CI 未触发，因为本轮按交接约束未推送。

### 新预算 Flash 全量回填与真实后端验收（2026-10-15）

- 用户在本轮明确同意直接测试，并指定新一轮总上限 100 元。新批次 `triple-u-v2-20261015-r1` 使用独立持久 Redis 计数器、PostgreSQL 数据库与命名卷，和无法复原计数的旧批次隔离；所有 DeepSeek 与 Flash 调用在发送前保守预留。2026-10-16 Docker 重启后读取到新批次计数为 **72.49784 元预留，剩余额度 27.50216 元**。这不是服务商账单，旧批次实际账单仍未核实；不能据此声称总支出或剩余账户余额。
- AI 课程 31/31、Python 课程 64/64 的最新文档版本完成 `qwen3.7-text-embedding-flash` 回填。偶发超时经逐批重试后完成；历史失败版本未冒充最新版本。DeepSeek Flash 单例和 Flash Embedding 单例都返回有效结果。真实检索查询改为单次最多 20 秒，以免摄取用的三次重试耗尽整个 Run 的 60 秒期限。
- 真实 FastAPI、隔离 PostgreSQL/Redis、DeepSeek Flash 和全量 Flash 语料上的新版 Golden Set **76 条首轮 70 条通过（92.11%）**；事实题 Hit@5 和 Recall@5 都为 0.875，引用存在率/有效率都为 0.9583，安全与审核用例通过率 1.0。四条事实题未命中标注来源，两条在检索节点超时，故引用与无执行错误质量门槛未全部通过。限时修复后，这两条超时用例的独立在线复测 2/2 通过；不能把它与首轮拼接成新的 76 条正式分数。报告及逐例记录在 `output/v2-eval-20261015/`，不进入默认提交范围。48 条事实题三策略对比因 Flash 查询重复超时主动中断，没有可引用的完整结论，默认 `hybrid` 未切换。
- 真实浏览器与上述后端：学习包 Run `eb618bb2-27e8-4a2d-956b-cb5f710036e4` 初次失败后从保存节点续跑，最终显示讲解、三道练习和逐题引用；审核 Run `2466c8af-4c3f-4851-b9c1-e793e2e4cf29` 在学生端只显示待审，教师账号通过后学生查询到交付答案；问答 Run `ebbeff87-d35f-41e0-8f3c-15dbf627407c` 在拿到编号后断开浏览器网络并重载，恢复网络后查到“执行已中断”，点击续跑后显示“已完成”。另一个学习包 Run `7b3ebfbd-9c29-43b9-8c7f-bf765141171d` 遇到 Planner JSON 格式失败，重复续跑曾报 `InvalidUpdateError`；加入受租约约束的 `execution_id` 最新值归并后，同一个真实 Run 已越过 Planner 并进入检索工具，最终以 `learning_package_tool_failed` 结束。连续两次 Planner 格式失败后第三次续跑的离线回归通过；云端工具间歇失败仍待可靠性治理，不能称该旧 Run 已交付。
- V1 生产模式采用明确路由白名单，只开放登录/注册/当前账号/注销、已发布课程目录、资源类型和已验证学生资源链。其余约 181 个旧 V1 路由中的非白名单入口一律 403，避免把旧的请求参数 `user_id` 视为授权。定向权限/部署回归 44 项和资源/教师组合 73 项通过；旧教师管理入口的迁移与细粒度授权仍需上线方处理。
- 本地 `ruff` 关键规则、`git diff --check`、前端构建、SSE 解析 5 项、演示资产 14 项通过；学习包、采集器、未完成节点续跑及 Embedding 检索最终定向 **72 项通过**。采集器此前把 SSE 独有的 `event_sequence` 错当持久化结果，修复后 35 条采集契约通过。CI 的离线负载烟测 8 个端点各 30 请求均返回成功，但 cockpit 的 p95 达约 112.7 秒，性能门槛未定义，不能宣称性能合格。完整 `pytest tests/` 收集 2161 项，在本机约 37% 时中止，已有旧题库/知识图谱数据常量与当前文件不一致的失败；远端 CI 未运行，也未推送代码。提交范围和排除项见 [本地提交范围](V2_COMMIT_SCOPE_2026-10-15.md)。

### Docker 已启动后的学习包可靠性复验（2026-10-16）

- 仅使用本机已有 Docker 镜像、命名卷和依赖，没有下载。排查发现课程查询 Embedding 已限制为单次最多 20 秒，但学习包只读工具统一 10 秒超时；真实 Run 的一次检索实际耗时 23.857 秒，放宽检索工具独立超时到 30 秒后成功返回 5 条证据。普通画像工具仍保持 10 秒超时。第一次真实复验 Run `0f729564-b565-49f5-abbe-2e43facee462` 随后在 Tutor 的结构化输出校验失败，不能计为成功。
- 对 `LearningPlan`、`Lesson`、`Practice`、`QualityReview` 的无效结构化输出加入最多一次带 Schema 提示的重试，调用次数仍计入模型预算；非法工具选择不重试且仍拒绝执行。离线相关 37 项通过，Ruff 关键规则通过。重新启动本地真实 FastAPI 后，Run `0b97069c-538a-4a99-b5f1-80d06954c53d` 完成并交付讲解和 3 道练习。单例成功不能代替 24 条学习包内容质量验收，也不意味着旧失败 Run 已恢复。
- 新批次 `triple-u-v2-20261015-r1` 的 Redis 持久计数器现为 **84.74432 元保守预留，15.25568 元余量**，不是提供商账单。停止进一步付费复验，保留隔离卷以便核对；完整 76 条第二轮与学习包 24 条在线质量验收尚未运行。用户要求不下载，本轮未安装或拉取依赖。

### 本地全量回归与 CI 准备（2026-10-16）

- 修正已过时的测试期望，使其与当前种子画像、280 道 AI 题库、52 个知识图谱节点及 Python/其他课程知识点边界一致；修正时间依赖的演示数据断言、直接调用路由时的 `Query` 默认值，以及 `pytest-asyncio` 关闭事件循环后的测试辅助函数。上传后的分块数现在直接从 RAG 已扫描的分块统计，兼容 SQLite 降级索引。
- SQLite TF-IDF 构建原先为每个向量重复保存整份全局词频表，1392 分块时本地测试库的 `chunk_vectors` 表约 956 MiB；查询并不读取该字段，现只保存空映射，向量权重与检索结果保持原逻辑。对应持久化回归已覆盖，新的隔离测试库在约 37% 进度时约 11 MiB。历史库不会自动缩小，不能据此声称已有部署的空间已回收。
- CI 的 Pytest 步骤现在使用独立 `build/ci_tests.db` 并先执行 `init_db()`，避免干净检出时缺少种子测试所需的 `knowledge_points` 表。Windows 本机 Python 3.10 在新 SQLite 数据库、离线模式下从头执行 `pytest tests/`：**2149 passed、18 skipped、27 warnings，耗时 575.38 秒**。Ruff 关键规则、`git diff --check` 和 CI YAML 解析通过。演示资产检查在同一隔离 SQLite、`LLM_PROVIDER=none` 下 **14/14 通过**；最初在 Windows 沙箱内运行时，`asyncio` 本机 socket 创建被阻塞，改用允许本机 socket 的执行环境后约 4 秒完成。远端 GitHub Actions、Python 3.12 环境及 PostgreSQL/Redis CI job 尚未实际触发，不能称远端 CI 绿色。
- 当前工作树仍有未提交的产品代码和测试运行产生的资源文件；未批量暂存、清理、重置或推送。在线 Golden Set 完整第二轮、学习包 24 条在线质量评测仍未完成，且本轮未增加付费调用或下载依赖。
- 对首轮四条来源未命中案例（`qa-003/008/019/034`）做只读复核：四份标注章节的最新 PostgreSQL 版本均有有效向量（分别 5/7/8/6 个分块），所以不是漏回填。当前中文查询使用 PostgreSQL `simple` 配置把整句当作一个词项；例如“图灵测试试图评估什么”在库中全文检索命中 0 个分块，而“图灵测试”在标注章节命中 2 个分块。可确认的缺口是中文词项拆分与排序。`qa-008` 已召回的机器学习基础章节直接解释梯度下降如何减小损失，`qa-034` 已召回的数学基础章节解释 PCA 如何压缩高维数据；两题的标注来源是否过窄需按教学内容复核。尚未改变检索策略或评测标注，也未把这次诊断计入新的在线分数。

### 200 元上限内的第二轮在线验收（2026-10-16）

- 用户把同一新批次 `triple-u-v2-20261015-r1` 的累计本地保护上限从 100 元提高到 200 元并要求直接测试。最终 Redis 计数为 **188.38166/200 元保守预留，剩余 11.61834 元**；该值按高估单价在请求前预留，失败请求不退，仍不是 DeepSeek、Embedding 服务商账单或账户余额。达到本轮测试目标后不再新增付费调用。
- 为 PostgreSQL `simple` 配置缺少中文分词的问题增加有界的 2 至 4 字符子串候选，只在第一名至少为第二名 2.5 倍时把命中来源标记为高置信救援；跨企业索引和旧索引融合后保持该来源在 Top-5。该逻辑不改评测标签，也不会对长问题无界扩展。检索及融合相关 8 项通过，`qa-019` 真实复测命中。
- 在完整 Flash 语料、真实 FastAPI、隔离 PostgreSQL/Redis、DeepSeek Flash 与 `qwen3.7-text-embedding-flash` 上完成 76 条第二轮：**74/76（97.37%）**，Hit@5 0.9583、Recall@5 0.9479、引用存在率和有效率均为 1.0、安全/审核为 1.0、无执行错误为 true，全部配置质量门槛通过。平均延迟 6886.57 ms，p50 5270.07 ms，p95 23296.27 ms。`qa-008` 与 `qa-034` 未命中原标注章节，但分别召回能解释梯度下降和 PCA 的其他课程章节；保留为来源标注/排序复核项，不篡改标签凑成 76/76。证据文件为 `output/v2-eval-20261015/golden-full-r2-report.json` 及对应 progress JSONL，不进入默认提交范围。
- 新增真实在线学习包采集器，只接受 `scenario=standard`，逐例写入并 `fsync` 进度，使用唯一会话，生成指纹绑定的人工复核模板。24 条数据集中 13 条标准场景已在真实后端运行，最终**契约 13/13 通过**：10 条完成，另外 3 条按用例预期进入拒绝或人工审核边界；p50 32097.99 ms，p95 76629.75 ms。首次 `lp-normal-006` 及一次原样重试均在 Planner 结构校验失败；启用服务商 `json_object` 模式并给出固定两步合法示例后，最终复测完成。最终报告为 `package-standard-final-report.json`。
- 学习包报告的人工复核覆盖率仍为 **0%**，所以 `learning_quality_pass_rate` 为 null；模型 Reviewer 不能替代人工内容质量审查。其余 11 条故障注入场景应继续由受控离线 Provider 执行，不能伪装成云端自然故障。结构化调用、学习包、采集、检索与评测定向回归 **128 项通过**，Ruff 关键规则通过。当前 `dxtorch` 的新 LangGraph 安装使用项目已有 `.tmp` psycopg 二进制依赖启动 PostgreSQL Checkpointer；若脱离该路径运行，需安装带 Windows 二进制的 `psycopg[binary]`。

### 最终正式离线与 PostgreSQL 回归（2026-10-16）

- 用户安装 `psycopg[binary]` 后确认 `psycopg 3.3.6` 使用 binary 实现，LangGraph PostgreSQL Checkpointer 可导入。新增在线学习包采集器回归，锁定 progress 已覆盖全部所选用例时不登录、不重复访问 API。
- Windows Python 3.10、全新隔离 SQLite、`A3_OFFLINE_DEMO=1` 下完整运行 `pytest tests/`：**2153 passed、18 skipped、24 warnings，626.37 秒**。本轮没有付费模型或 Embedding 调用。前端 `vue-tsc` 与 Vite 生产构建、全仓 Ruff 关键规则和 `git diff --check` 通过。
- PostgreSQL 专项先在保留完整 Flash 语料的评测库发现两个依赖空库前提的测试；改用新建的空白临时数据库后定位到摄取测试桩缺少 `count_source_chunks()`，导致桩自身把摄取标成失败。补齐该生产接口后，检查点跨进程恢复、API 崩溃恢复、摄取幂等、最新向量版本检索及未完成节点续跑组合 **15/15 通过**。临时数据库随后删除，评测数据库及命名卷未修改。
