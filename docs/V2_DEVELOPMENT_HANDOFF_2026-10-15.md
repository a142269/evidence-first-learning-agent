# Triple-U V2 开发交接（2026-10-15）

这份文档供下一个开发窗口直接接手。以当前工作树代码为准；历史阶段记录见 [实施状态](UPGRADE_IMPLEMENTATION_STATUS.md)，各模块的输入、输出、失败路径和代码入口见 [十模块实现详解](V2_TEN_MODULE_IMPLEMENTATION.md)。阅读实施状态时应从末尾最新批次往前看，较早批次的“待办”可能已经完成。

## 1. 项目目标与不可变边界

- 仓库：`D:/xunfei/triple-U`；当前分支：`feat/enterprise-agent-rag-stack`。目标是面向 Agent / 大模型应用开发求职展示的**课程学习 Agent**，不是通用自治 Agent 或 EchoMind 客服系统。
- 参考图的十模块框架：LLM、短期/长期/外置记忆、规划、工具、执行、观察反馈、状态调度、提示词、安全权限、UI。EchoMind 仅供角色契约、工具白名单、请求级轨迹和评测回流参考，未照搬业务或技术栈。
- 保留 DeepSeek 对话模型、用户自己的 RAG Embedding 密钥、PostgreSQL/pgvector、Redis、Celery、LangGraph、Vue。运行环境的 Embedding 模型已由过期的 `qwen3.7-text-embedding` 切换为 `qwen3.7-text-embedding-flash`，维度 1024；密钥值只从运行环境读取。
- 学习包是固定 Tutor → Practice 两步依赖、Reviewer 至多一次返工，以及只允许 `search_course` / `finish`、最多三次搜索的**受限 ReAct-style 检索决策循环**。不得宣传为任意 DAG、并行多 Agent、开放式多工具 Agent、Tree-of-Thought。代码执行、文件写入、浏览器操作和任意外部 URL 均未加入学习 Agent。
- 不推送远端；不覆盖或删除已有未提交改动；不提交 `.env*`、`reports/`、`output/`、`.playwright-cli/`、`cloud-embedding-smoke.md` 或 `data/rag/knowledge_index.json` 的本地大规模改动。尚未进行本轮正式提交。

## 2. 当前系统如何运行

```text
Vue 学习包页面 → V2 FastAPI 登录/课程授权 → 创建 Run 与 SSE
  → LangGraph guard → 检索/受限规划 → Tutor → Practice → Reviewer
  → 证据和逐项引用校验 → 可选教师审核 → 完成事件
                    ↘ PostgreSQL Run/事件/审计 + Graph Checkpointer
课程资料 → 教师上传/审核 → Celery 摄取/版本化 → pgvector + PostgreSQL FTS
```

V2 主入口是 `POST /api/v2/learning-runs/stream`，支持 `mode=answer`（证据优先问答）和 `mode=learning_package`（讲解与三题学习包）。相关 API 还包括查询 Run、教师 `resume` 审核、授权用户 `continue` 未完成节点、按序号读取事件、教师 `reconcile` 稳定检查点。SSE 传运行事件，并非模型逐 token 原生流。V1 旧页面及兼容检索仍存在；V1 的旧基线和降级结果不能充当 V2 pgvector 成绩。

关键代码入口：

| 范围 | 文件 | 当前行为 |
| --- | --- | --- |
| API/生命周期 | `backend/app/api/v2/learning_runs.py`、`backend/app/api/v2/run_lifecycle.py` | 鉴权、创建幂等、SSE、查询、审核、续跑与状态修复 |
| Graph/学习包 | `backend/app/agent_runtime/learning_graph.py`、`learning_package.py` | 状态机、固定两步计划、检索决策、角色交接、Reviewer、引用映射 |
| 模型/用量 | `backend/app/core/llm_client.py`、`backend/app/agent_runtime/usage_meter.py`、`eval_cost_guard.py` | 严格模型错误、实际 token 或 unknown、估算费用、评测费用预留 |
| 记忆/工具 | `backend/app/agent_runtime/conversation_memory.py`、`backend/app/services/v2_learning_tools.py` | 最近三次已完成会话、可信学习画像读取、课程证据/错题/先修关系只读工具 |
| 检索/摄取 | `backend/app/services/enterprise_retriever.py`、`knowledge_ingest.py`、`vector_reindex.py`、`backend/app/tasks/ingestion.py` | pgvector+FTS+RRF；课程/文档版本隔离；上传幂等和模型切换重建 |
| 身份/持久化 | `backend/app/api/v2/access.py`、`backend/app/repositories/auth_repo.py`、`backend/app/agent_runtime/checkpointing.py`、`run_leases.py` | 持久会话、逐账号课程授权、检查点、执行租约 |
| UI | `frontend/src/views/LearningPackageView.vue`、`frontend/src/api/learningRuns.ts`、`learningStream.ts` | 进度、逐项引用、用量状态、审核/恢复入口 |
| 可选 MCP | `backend/app/mcp_readonly.py`、`requirements-mcp.txt` | 本地 stdio 只读适配器，主 V2 图不依赖它 |

实现要点：`lesson` 和每道 `exercise` 都有 `source_ids` 及结构化 `citations`，最终 citations 只对实际使用来源去重。会话窗口记忆按用户/课程/session 隔离；持久学习画像只读取已有可信记录，模型推断不会自动写回。统一工具由服务端注入身份和课程范围，再做角色白名单、参数校验、超时、错误分类与脱敏审计。Graph 从已提交节点边界续跑，复用已完成产物并延续同一 Run 预算；中断时在途云端调用可能重算或计费，**没有 exactly-once 保证**。待审草稿不向学生交付。

## 3. 已实现、实验性与未验收

| 能力 | 状态 | 证据或边界 |
| --- | --- | --- |
| V2 普通问答、学习包、细粒度引用、有限会话记忆、人审 | 已实现 | 离线契约与部分隔离 PostgreSQL 测试；真实内容质量未完成 |
| 只读业务工具、角色权限、Run 事件/用量、持久会话/课程授权 | 已实现 | 定向离线测试；费用是实际 token + 估算金额或 unknown，不是提供商账单 |
| 租约、检查点、未完成节点续跑、创建/摄取幂等 | 已实现 | 隔离 PostgreSQL 跨进程与故障注入覆盖部分路径；不覆盖数据库服务崩溃或恰好一次 |
| Flash Embedding 模型隔离、课程回填及已审核文档重建 | 已实现，真实批量待验收 | 单例 Flash 成功；批量回填遭遇间歇性错误；真实教师上传文档尚未付费重建 |
| 三种检索策略 `dense`、`hybrid`、`hybrid_diverse` | 实验性 | 默认保持 `hybrid`；缺少完整同语料召回/安全/延迟比较 |
| 本地只读 MCP | 本地协议已验收，生产宿主待验收 | 固定 `mcp==2.3.0` 的客户端完成进程内与独立 stdio 发现/调用、授权撤销拒绝；未验证生产启动器 |
| 学习包新续跑 UI | 已构建，模拟 API 浏览器联调通过 | 学生断流→查询→续跑、教师审核及逐题引用已在真实浏览器验证；真实后端端到端待做 |

迁移至少涵盖 `20261013_0007_run_execution_leases.py`、`20261014_0008_auth_sessions.py`、`0009_v2_event_sequence.py`、`0010_ingestion_tasks.py`、`0011_login_attempts.py`。新环境先检查 `alembic/versions/` 和迁移链，再在**隔离数据库**执行；不要把测试命令指向用户业务数据库。

## 4. 质量证据：四种口径必须分开

1. **旧版 66 条历史在线基线**：64/66（96.97%）、Recall@5 95.83%、引用完整性 100%。这只属于旧链路，不能写成新版 76 条或学习包结果。
2. **离线契约**：早期 P0 为 60 passed / 1 skipped，学习包 87 passed / 1 skipped；后来定向回归曾有 42 passed，向量重建/回填 3 passed，最终小范围 sanity 4 passed。测试组重叠，不能相加为唯一总数。24 条学习包用例已通过模拟模型的 API/Graph 采集与回放，其中 12 开发、12 固定留出；内容质量仍为未评测。前端 `npm run build` 已通过。
3. **隔离 PostgreSQL/Docker**：曾有 5 项 ASGI 故障恢复、1 项未完成节点跨进程 Graph 续跑、1 项版本/课程隔离检索、1 项重复摄取向量版本测试通过；Docker 恢复后又重跑 2 项 Flash 版本定向测试。模型与向量在这些测试中受控，并非真实云端/真实 Celery 故障。临时 PostgreSQL/Redis 容器已清理，tmpfs 数据不能复用。
4. **有限云端诊断**：DeepSeek 最小请求两次成功并返回实际 token；旧 Embedding 模型 HTTP 403 后切换 Flash，Flash 单例成功。38 份 AI Markdown 的部分在线回填中请求间歇失败，主动停止。48 条事实题中 43 条的标注来源在部分 Flash 语料中可用；只从中选前 10 条做 pgvector-only Top-5，命中 8/10。**这是筛选后的不完整语料诊断，绝非新版 76 条正式准确率、召回率或三策略结论。** 三策略长测中断，没有完整报告。

用例与脚本：`evals/golden_set_zh_v2.jsonl`（76 条：48 事实、18 拒答、10 审核）、`evals/learning_package_cases_v1.jsonl`（24 条）；`scripts/evaluate_golden_set.py`、`scripts/collect_learning_package.py`、`scripts/evaluate_learning_package.py`、`scripts/compare_v2_retrieval.py`。学习包故障注入场景必须继续用可控环境，不可伪装成云端自然发生。

## 5. 云端费用和密钥交接：下一窗口先停付费调用

原获授权的云端验收硬上限是 **100 元**，campaign 为 `triple-u-v2-20261014`。模型与 Embedding 共同经 Redis 原子预留；所用高估单价只是费用上界，**Redis 预留额不是供应商真实账单**。Docker 中断前看到 63.2545 元预留，重启后旧 Redis 快照只恢复到 61.7571 元，且可能仍有在途请求。为了防止重复消耗，同一 campaign 曾保守写到 100 元；之后用于验收的临时 Redis 容器已清理，因此不能依赖它作为持久账本。

**不要沿用这个 campaign 继续付费验收，也不要把 Docker 重启解释为额度归零。** 下一轮云端测试前，先核对提供商实际账单/调用记录，与用户确认新的费用预算和范围，并使用可靠持久化预算记录与新 campaign。仅在得到新授权后，才做 Flash 全量回填、已审核文档重建、76 条问答与学习包在线质量测试。密钥在 `.env.enterprise` / 运行环境中，不能打印、复制进文档、日志或提交；DeepSeek 和 Embedding 的 key 都无需在交接文档中写明。

## 6. 下一窗口优先完成什么

### P0：先做无付费的收口

1. `git status --short --branch`、`git diff --stat`、`git diff --check`，逐项区分原有改动与新修改；确认当前代码和文档仍在同一分支。工作树很脏，尤其 `data/rag/knowledge_index.json` 有巨量本地差异。不要一键暂存、重置或清理。
2. 在隔离 SQLite/测试 PostgreSQL 上核对最新迁移、认证和课程权限、Run 续跑/审核/事件序号、摄取版本与重建失败保持旧版本。相关文件：`tests/a/test_v2_unfinished_resume.py`、`test_v2_event_idempotency.py`、`test_v2_ingestion_idempotency.py`、`test_vector_reindex.py`、`test_v2_auth_throttle.py` 等。
3. 在网络/依赖允许时安装固定 MCP SDK，使用真实 MCP 客户端验证只读工具发现、调用、课程越权拒绝和错误返回；若 TLS 仍阻断，保留“未验收”状态。
4. 用浏览器联调学生断线/续跑、教师审核/拒绝、逐题引用、用量 unknown 与部分结果；现有前端构建只能证明类型和打包，不等于交互正确。
5. 做真实 Celery Worker 重复任务、进程中断/租约恢复测试；确认无法达到 exactly-once 的边界和重复云端调用的处理。补 V1 资源隔离检查及最小演示/CI 复核。

### P1：重新获得付费预算后再跑完整在线验收

1. 用与当前源码一致的镜像/服务、新建隔离 PostgreSQL/Redis，跑迁移并启用**持久化**的预算记录；明确服务端身份与课程授权。现有 `a3-backend` 镜像可能落后当前源码，不能直接当作新代码验收。
2. 用 Flash 对完整固定课程语料回填；`scripts/backfill_enterprise_corpus.py` 的 `indexed`、`embedded`、`embedding_failed` 分开核对，失败非零须中止/重试。对已审核教师文档先运行 `scripts/reembed_enterprise_vectors.py --dry-run`，确认范围，再在预算内运行付费重建。核查新版本查询只读当前 Embedding 模型且旧版本在失败时仍保留。
3. 单例 DeepSeek + Flash + V2 API 冒烟后，先开发集，再在剩余额度内做新版 76 条及学习包可真实在线运行的标准用例。人工复核讲解/题目/引用；故障用例仍用受控环境。报告逐项标注语料版本、模型、样本数、失败、实际 token、估算成本与提供商账单核对状态。
4. 在**同一完整语料和固定问题集**比较 `dense`、`hybrid`、`hybrid_diverse` 的召回、引用/拒答安全与端到端延迟；先确定可接受延迟门槛，只有质量改善且固定回归无安全退化、延迟未越门槛才考虑更换默认 `hybrid`。
5. 更新 README、演示文档和求职表述，严格区分旧 66 历史基线、离线契约、隔离 PostgreSQL、部分云端诊断、正式新版在线结果与人工学习质量；无结果就写“待验收”。

## 7. 本地命令与资料索引

无云端费用的基本检查（项目根目录；仅在确认本地依赖目录存在后执行）：

```powershell
git status --short --branch
git diff --check
$env:PYTHONPATH = 'D:/xunfei/triple-U/.tmp/migration-deps;D:/xunfei/triple-U/.tmp/p0-deps;D:/xunfei/triple-U'
$env:A3_OFFLINE_DEMO = '1'
& 'D:/Anaconda3/envs/dxtorch/python.exe' -m pytest tests/a/test_learning_package.py tests/a/test_v2_learning_tools.py tests/a/test_v2_model_usage.py tests/a/test_v2_unfinished_resume.py tests/a/test_vector_reindex.py -q -p no:cacheprovider --no-cov --benchmark-disable --basetemp output/handoff-tests-NEW
```

前端在 `frontend/` 运行 `npm run build`。每次测试选全新的 `output/` 子目录以保留旧报告；有些本机临时目录可能不可读，先核查路径。隔离 PostgreSQL 复核说明见 [检查点验收](POSTGRES_CHECKPOINT_ACCEPTANCE.md)，认证配置见 [登录与课程授权](AUTH_AND_COURSE_ACCESS.md)。其他常用文档：[README](../README.md)、[学习包指南](LEARNING_PACKAGE_GUIDE.md)、[企业架构指南](ENTERPRISE_ARCHITECTURE_GUIDE.md)、[学习包评测](../evals/LEARNING_PACKAGE_EVAL.md)、[五分钟演示](DEMO_5_MINUTES.md)。

### 可直接贴给下一个窗口的继续开发请求

> 请从 `D:/xunfei/triple-U/docs/V2_DEVELOPMENT_HANDOFF_2026-10-15.md` 接手 Triple-U V2，先核对当前分支、工作树和最新代码。保护所有未提交改动与本地产物，不推送远端。先完成交接文档 P0 的无付费验收及缺口修复，并保持 README/状态文档与证据一致。原 `triple-u-v2-20261014` 100 元云端评测批次不能续用；任何新的 DeepSeek/Flash 付费批量验收前，先核实实际账单并取得新的费用预算授权。不要读取、展示或提交密钥。

### 本次接手进展（2026-10-15）

无付费定向回归、MCP 客户端协议和模拟 API 浏览器联调已完成，证据与限制见[实施状态末尾](UPGRADE_IMPLEMENTATION_STATUS.md)。MCP 已不再是“SDK 下载阻断、协议未验收”；现在确认的是本地 `mcp==2.3.0` 的进程内与 stdio 协议。浏览器已验证断流、查询续跑、审核和引用 UI，但真实后端端到端仍待做。隔离 PostgreSQL 本轮复测见下文；V1 全路由隔离审计、远端 CI 与新版在线质量仍待完成。原云端 campaign 预算禁令继续有效。

本机继续排查 Celery 时修正了上传端和 Worker 暂存路径不一致：两端现共用 `backend/app/services/ingestion_staging.py`，路径边界单测通过。用户安装 Celery 5.6.3、Redis Python 客户端 8.1.0 及 pgvector 0.5.1。隔离 SQLite + 文件队列中的独立 Worker 回归已固化在 `tests/a/test_celery_worker_process.py`；后来用用户提供的 Docker Desktop CLI（不在 PATH）启动独立 tmpfs PostgreSQL/Redis，完整迁移到 `0011`，10 项 PostgreSQL 回归通过。`tests/helpers/celery_ingestion_worker_probe.py` 在 Redis broker 和 Redis + PostgreSQL 组合下也分别通过重复投递与杀进程后显式重投/过期租约接管。两容器已停止并删除；测试摄取用桩，Redis 自动重投、真实云端摄取与跨系统 exactly-once 仍未验证。生产模式旧 V1 演示路由现要求登录；学生资源写入/删除已补归属限制，原资源组合 38 项及新增 HTTP 路由复测通过，其他 V1 路由的逐账号课程授权仍待审计。

后续无付费复核又补了 V1 学生资源读取的生产课程授权：列表、详情、附件及移动端共用资源可见性判断，推荐入口拒绝账号伪造，教师草稿和非目标学生不可提前读取，SQLite 真实登录与撤销授权用例已覆盖。教师推荐路径标题被阶段名称覆盖的问题也已修复；资源、教师协作、移动端组合 **55 项通过**。前端生产构建默认同源 API，重新构建通过；Playwright 配真实 FastAPI + 隔离 SQLite 验证了登录、V2 SSE 失败后的 Run 编号显示及保存状态查询。该后端显式设 `LLM_PROVIDER=mock`，严格 V2 模型接口按设计失败，因此这不是成功内容生成或云端质量验收。详情见[实施状态最新批次](UPGRADE_IMPLEMENTATION_STATUS.md)。本地测试服务和浏览器已关闭；V1 全路由授权、远端 CI、真实成功链路及新版在线质量仍待验收，旧付费 campaign 禁令不变。

本地 CI 关键 Ruff 全量检查曾被旧参考实现脚本的动态函数名拦住；改成显式命名空间读取后，`backend/app scripts/ tests/` 的 `F821,F823,E9` 通过，参考实现脚本自检运行成功。前端 SSE 解析 5 项及 `git diff --check` 也通过；远端 CI 未运行。

### 本轮继续执行结果（2026-10-15）

用户随后明确将**新批次**预算定为 100 元，并授权直接进行付费测试；此前“先查旧账单再付费”的等待条件已被本轮用户指示覆盖，但旧批次实际账单仍未知。新批次 `triple-u-v2-20261015-r1` 使用新的持久 Redis/pgvector 命名卷和费用计数器；2026-10-16 Docker 重启后读到保守预留 72.49784 元、尚余 27.50216 元，均非供应商账单。不要复用旧批次或把此计数当实际总消费。

最新 Flash 向量覆盖 AI 31/31、Python 64/64 文档。真实后端的 76 条新版 Golden Set 首轮 70 条通过（92.11%）；四条事实题标注来源未进 Top-5，两条检索超时，引用和无执行错误门槛未全过。把交互检索限制为一次最多 20 秒后，超时两题独立复测 2/2 通过；完整第二轮未运行。真实浏览器验证学习包生成、教师待审/批准/学生交付、网络断开后按 Run 编号查询及节点续跑完成。另有旧学习包检查点遇到 Planner 格式失败，重复续跑时的 `InvalidUpdateError` 已由 `execution_id` 归并修复并用离线回归验证，真实 Run 后续仍因云端工具失败而未交付；不能宣称所有失败都可恢复。详见[实施状态最新批次](UPGRADE_IMPLEMENTATION_STATUS.md)。

V1 生产入口现用显式白名单，其余旧接口 403；这带来旧教师管理页在生产不可用的兼容影响。代码仍未暂存、提交或推送；[候选提交范围](V2_COMMIT_SCOPE_2026-10-15.md)明确排除了密钥、浏览器缓存和本地报告。本地关键检查及定向契约通过，但完整测试套件存在旧数据常量断言失败并中止，远端 CI 未运行。原文早期“尚无新版在线评测”“真实后端成功链路待做”等句子为当时的历史状态，以本节为准。

### Docker 启动后的补充复验（2026-10-16）

用户要求不下载，本轮仅用已有 Docker 容器、数据卷和 Python 依赖。学习包工具原统一 10 秒超时，而单次交互 Embedding 允许最多 20 秒；将课程检索工具单独放宽至 30 秒后，真实 Run 中一次 23.857 秒的检索成功返回 5 条证据。该 Run 接着在 Tutor 结构化输出校验失败，因此又对计划、讲解、练习和质量复核的无效 Schema 输出加入最多一次重试，模型调用继续计入预算。相关 37 项离线测试和 Ruff 关键规则通过；重新启动的真实 FastAPI Run `0b97069c-538a-4a99-b5f1-80d06954c53d` 完成讲解与三道练习。此前失败的旧 Run 仍未交付，不能与新 Run 混称恢复。

隔离新批次 `triple-u-v2-20261015-r1` 后续获准把累计硬上限提高到 200 元。最终 Redis 预算保守预留为 **188.38166/200 元，余量 11.61834 元**，不是账单。完整第二轮 76 条已运行，74/76 且全部质量门槛通过；13 条标准学习包在线契约 13/13 通过，人工内容质量复核仍为 0%，其余 11 条故障场景只应在受控离线环境运行。远端 CI 未触发、代码未提交。最新状态以[实施状态末尾](UPGRADE_IMPLEMENTATION_STATUS.md)为准。

### 本地全量回归结果（2026-10-16）

继续修正当前数据与旧测试断言不一致的问题，补齐上传分块统计和 SQLite TF-IDF 向量表的空间问题。全新隔离 SQLite、离线模式、Python 3.10 的完整 `pytest tests/` 从头跑完：**2149 passed、18 skipped，575.38 秒**。Ruff 关键规则、`git diff --check`、CI YAML 解析以及同一隔离数据库上的演示资产检查 **14/14** 通过。CI 的 Pytest 步骤已配置独立数据库并初始化所需表。该结果取代上文“本机完整测试中止”的历史状态；远端 GitHub Actions、Python 3.12 与 PostgreSQL/Redis CI job 仍未运行。没有下载依赖、增加付费调用或推送代码。资源产物及密钥排除范围见[候选提交范围](V2_COMMIT_SCOPE_2026-10-15.md)。

最终安装 `psycopg[binary]` 并加入在线采集器 resume 回归后，完整 SQLite 套件更新为 **2153 passed、18 skipped、24 warnings，626.37 秒**；新建空白临时 PostgreSQL 数据库上的 15 项检查点、进程恢复、摄取、检索和续跑测试全部通过。前端生产构建、Ruff 和差异检查通过。临时数据库与隔离容器在测试后清理/停止，评测卷保留；没有新增付费 API 调用，保护计数仍为 188.38166/200 元。
