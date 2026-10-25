# Triple-U V2 课程学习 Agent：十模块实现详解

更新时间：2026-10-19（QWEN-103 按当前代码复核版本号；上一版 2026-10-15）。本文描述**当前代码**，并将离线契约、真实 PostgreSQL、云端质量分别标注。图中的“Brain / Memory / Planning / Tool / Execution / Observation / Scheduler / Prompt / Guardrail / UI”只是分析框架，不意味着学习 Agent 已拥有代码执行、文件写入、浏览器操作、Tree-of-Thought 或通用自治能力。EchoMind 仅作为角色契约、只读工具、请求轨迹和评测闭环的参考；客服业务与技术栈没有迁移到本项目。

V2 主线为 `POST /api/v2/learning-runs/stream`。服务端从 Bearer Session 解析账号与课程授权，创建独立 Run / thread，加载同用户同课程同会话最近三次**已完成**的回答，执行 LangGraph，保存节点审计与检查点，最后通过 SSE 交付。`mode=answer` 走证据优先问答；`mode=learning_package` 走固定 Tutor → Practice 两步学习包。关键入口：[路由](../backend/app/api/v2/learning_runs.py)、[生命周期](../backend/app/api/v2/run_lifecycle.py)、[基础图](../backend/app/agent_runtime/learning_graph.py)、[学习包图](../backend/app/agent_runtime/learning_package.py)。V1 仍用于旧页面及内置/离线 RAG 兼容；不能将 V1 离线能力算成 V2 在线质量。

## 1. 大模型核心（Brain / LLM）

- **职责及输入输出**：Planner 输出 `LearningPlan`，Tutor 输出 `ToolDecision` / `Lesson`，Practice 输出三道 `Exercise`，Reviewer 输出 `QualityReview`。输入只包括服务端授权的用户目标、有限会话记忆、可信画像摘要与检索证据；输出由 Pydantic 验证，模型文本不能变成任意工具命令。
- **顺序与代码**：[角色契约及 `_ask`](../backend/app/agent_runtime/learning_package.py) → [严格 OpenAI-compatible 模型适配](../backend/app/core/llm_client.py)。V2 的严格适配层在网络/格式错误时返回稳定错误码，不再把失败伪装成 mock 回答。原有媒体与演示调用仍保留旧适配路径。对话模型沿用用户配置的 DeepSeek；RAG Embedding 保持原配置。
- **数据与故障**：每个模型响应尽量记录提供商返回的输入/输出 token；未返回的记为 `usage_unknown_calls`。`budget.cost.status=estimated` 表示用实际 token 和配置单价计算的**估算费用**，`unknown` 表示无法完整估算；请求的 `max_tokens` 只是上限。调用失败、空内容或无效 JSON 不交付学习包。评测环境可开启 [Redis 预留门禁](../backend/app/agent_runtime/eval_cost_guard.py)，配额与单价上界缺失时拒绝付费调用；可能已计费的失败请求不退还预留额。
- **证据与边界**：[模型用量测试](../tests/a/test_v2_model_usage.py)、[评测预算测试](../tests/a/test_v2_eval_cost_guard.py)。隔离容器的两次 DeepSeek 单例冒烟获得实际 token 用量，证明当前密钥/模型的最小请求可用；未评测内容质量，也无法据此确认提供商账单金额。

## 2. 记忆（Memory）

- **职责及输入输出**：短期记忆读取最近三条已完成 Run 的问答；长期学习画像从 `profiles` / BKT 已存记录读取学习偏好与弱项；外置记忆为课程 Markdown、PostgreSQL 文档版本及 pgvector/FTS 片段。画像不由模型推测自动写回。
- **顺序与代码**：[会话记忆](../backend/app/agent_runtime/conversation_memory.py) 以用户、课程、`session_id`、完成状态和创建时间隔离；[画像工具](../backend/app/services/v2_learning_tools.py) 仅返回允许的偏好字段与该课程知识点，普通问答的 [画像摘要](../backend/app/api/v2/learning_runs.py) 也只取有限偏好。检索证据由当前课程授权约束。
- **持久化与故障**：历史 Run 在 `agent_runs`；画像在 `profiles` / `bkt_states`；课程内容在 `knowledge_documents`、`document_versions`、`document_chunks` 与旧 Markdown 索引。记忆查询失败直接报持久化错误；可选画像工具失败可省略个性化，不改变课程事实依据。
- **证据与边界**：[记忆隔离测试](../tests/a/test_conversation_memory_v2.py)、[工具测试](../tests/a/test_v2_learning_tools.py)。这不是长期语义记忆自动学习，也不把未经核实的回答当课程知识。

## 3. 规划（Planning）

- **职责及输入输出**：Planner 把目标约束为一个讲解步骤和一个依赖讲解的练习步骤；Tutor 的受限 ReAct-style 检索决策循环只选 `search_course` / `finish`，最多三次搜索；Reviewer 最多要求一次返工。
- **顺序与代码**：[LearningPlan/ToolDecision 校验](../backend/app/agent_runtime/learning_package.py) 禁止循环、额外节点或未知依赖；Graph 按 `guard → planner → decide ↔ tool → tutor → practice → review → compose` 推进。规划前可读画像、近期错题及先修关系。
- **持久化与故障**：计划、搜索 observation、返工次数和预算随 LangGraph state checkpoint 保存。无证据、重复搜索、超预算或第二次 Reviewer 拒绝终止并给稳定错误码。
- **证据与边界**：[学习包测试](../tests/a/test_learning_package.py)。这是真实依赖链，**不是**任意 DAG、并行多 Agent、Tree-of-Thought 或无限自主规划。

## 4. 工具调用（Tool Use）

- **职责及输入输出**：[统一只读工具入口](../backend/app/services/v2_learning_tools.py) 提供课程证据、学习画像、近期错题、先修关系。Pydantic 拒绝额外参数；工具名、允许角色、权限键、只读/副作用、超时、参数 schema 与截断上限集中在 [单一工具目录](../backend/app/services/tool_catalog.py)，运行时按 `decide_access()` 三层判定、deny-by-default（未知工具/未列角色/未持有权限键一律拒）；身份、课程、Run 由服务端注入，模型只提交查询文本或知识点 ID。
- **顺序与代码**：每次调用重查课程授权，再以超时包装同步读取；返回 `success / no_data / denied / invalid_args / timeout / failed`，每次调用（含拒绝）另写一条统一审计事件（`tool/source/role/run_id/status/decision/reason/权限键/副作用/超时/耗时/参数摘要哈希`），事件不含提示词、参数值或检索文本。[可选本地 MCP 适配器](../backend/app/mcp_readonly.py) 用固定 `mcp==2.3.0` 的 stdio 服务复用工具 broker；可信启动器必须提供身份/课程环境作用域。
- **持久化与故障**：`tool.completed` 关联 Run 事件序号；最终结果包含 `tool_audit`。只读 MCP 是本地受信进程接口，不是对公网开放的鉴权端点。固定 `mcp==2.3.0` 已在项目临时目录安装，并用真实 MCP 客户端完成进程内及独立 stdio 发现/调用；隔离 SQLite 授权撤销后调用返回 `denied`。生产启动器和真实部署仍待验收。
- **证据与边界**：[工具权限测试](../tests/a/test_v2_learning_tools.py)、[MCP 协议测试](../tests/a/test_mcp_readonly_protocol.py)。没有代码执行、文件写入、外部 URL、任意数据库操作或可写 MCP Tool。

## 5. 受控执行（Execution Engine）

- **职责及输入输出**：FastAPI 只执行受控检索与模型请求；教师上传由 Celery 解析、审核、版本化并写入索引。学习 Agent 的“行动”不是宿主机命令。
- **顺序与代码**：[上传 API](../backend/app/api/v1/knowledge_admin.py) → [摄取账本](../backend/app/repositories/ingestion_tasks.py) → [Celery Worker](../backend/app/tasks/ingestion.py) → [摄取服务](../backend/app/services/knowledge_ingest.py)。`Idempotency-Key` 绑定上传者、课程、文件名、内容哈希及审核参数；重复请求复用同一 task/document ID，worker 租约限制重复任务；同内容同状态版本复用，查询只使用最新已索引版本。模型切换时，[向量重建服务](../backend/app/services/vector_reindex.py)及[运维命令](../scripts/reembed_enterprise_vectors.py)读取已审核片段，新版本完整写入后才切换稠密检索；`--dry-run` 不调用云端，付费运行要求同一 Redis 评测预算。
- **持久化与故障**：`ingestion_tasks`、`knowledge_documents`、`document_versions`、`document_chunks`；任务失败保留状态供重试。进程在模型/Embedding 请求与本地提交之间中断仍可能重算或重复计费，不承诺跨系统恰好一次。暂存目录须在共享存储，且 Worker 校验路径边界。
- **证据与边界**：[摄取幂等测试](../tests/a/test_v2_ingestion_idempotency.py)、[暂存路径测试](../tests/a/test_ingestion_staging.py)、[独立 Worker 进程测试](../tests/a/test_celery_worker_process.py)、[向量重建测试](../tests/a/test_vector_reindex.py)、[隔离 PostgreSQL 版本测试](../tests/a/test_v2_ingestion_postgres.py)。上传端和 Worker 共用[暂存路径模块](../backend/app/services/ingestion_staging.py)；路径测试验证本机上传文件可被 Worker 路径规则接受，越界文件被拒绝。独立 Celery Worker 用文件队列、隔离 SQLite 和摄取桩验证重复投递与杀进程后显式重投/过期租约接管；同一探针接入独立 Redis broker 与 PostgreSQL 任务账本后也通过。PostgreSQL 用受控向量验证重复摄取复用同一文档/版本、模型切换生成新版本并保存 pgvector；真实云端摄取、Redis 自动重投、教师资料的真实云端批量重建仍需复核。课程回填汇总单列 `embedded` / `embedding_failed`，失败时退出码非零，避免把仅写入文档解释成向量完整入库。

## 6. 观察与反馈（Observation / Feedback）

- **职责及输入输出**：搜索 observation 含查询及受限片段；Reviewer 检查讲解和三题的证据、答案与难度递进，最多返工一次。每段讲解与每道练习都有模型选择的 `source_ids` 与服务端映射的结构化 `citations`。
- **顺序与代码**：[学习包图](../backend/app/agent_runtime/learning_package.py) 验证引用 ID 属于本轮证据；最终 citations 仅对实际使用的 ID 去重；人工替换内容清空旧包与旧引用。[审计](../backend/app/agent_runtime/run_audit.py) 保存节点与检索事件，Phoenix/OTel 为可观测入口。
- **持久化与故障**：Run 与节点审计保存安全摘要；待审草稿只对教师可见。模型 Reviewer 的通过不等于人工事实核查，也不能当在线正确率。
- **证据与边界**：[细粒度引用测试](../tests/a/test_learning_package.py)、[专用离线评测](../evals/LEARNING_PACKAGE_EVAL.md)。错题回流为现有业务读取，不会在本轮自动写入“模型推测的错题”。

## 7. 状态与调度（Scheduler / State Manager）

- **职责及输入输出**：Graph 管理节点条件边、人工 `interrupt()`、Run 租约、持久化事件序号。`POST /{run_id}/resume` 是教师内容审核；`POST /{run_id}/continue` 是授权用户从未完成节点边界续跑；`POST /{run_id}/reconcile` 是教师只读恢复已稳定结果。
- **顺序与代码**：[基础图](../backend/app/agent_runtime/learning_graph.py)、[检查点](../backend/app/agent_runtime/checkpointing.py)、[租约](../backend/app/agent_runtime/run_leases.py)、[Run API](../backend/app/api/v2/learning_runs.py)。续跑校验 Run/thread/用户/课程/问题/执行代次与版本，用新的租约 `execution_id` 继续同一预算；已提交节点不重跑，在途节点可能重算。`Idempotency-Key` 对同一创建请求返回既有 Run。
- **持久化与故障**：PostgreSQL Checkpointer 与 `agent_runs` / `agent_checkpoints` 是不同事务域；系统不声称它们原子提交。`GET /{run_id}/events?after=` 返回按 `event_sequence` 排序的脱敏事件；SSE 持久事件带 `id`。客户端断线可查状态；不自动重试有副作用调用。
- **证据与边界**：[续跑测试](../tests/a/test_v2_unfinished_resume.py)、[事件/幂等测试](../tests/a/test_v2_event_idempotency.py)、[PostgreSQL 跨进程未完成节点测试](../tests/a/test_v2_unfinished_postgres.py) 与 [既有 PostgreSQL API 故障测试](../tests/a/test_postgres_api_recovery.py)。新增续跑的独立进程 Graph 测试已通过，尚未覆盖数据库服务崩溃或在线模型。

## 8. 提示词工程（Prompting）

- **职责及输入输出**：各角色的 system prompt 明确输入为待分析数据、只返回 JSON Schema，不输出隐藏思维过程；`PROMPT_VERSION=learning-package-v2.9`（自 QWEN-311 起定义于 `backend/app/agent_runtime/prompts.py:22`、`learning_package` re-export；2026-10-25 复核；v2.8→v2.9 因 QWEN-211 重规划追加固定提示词；QWEN-231 后 `learning_package.py:25`、QWEN-311 迁移后定义移入 prompts.py 而版本值不变——迁移字节不变故未 bump）随代码保存，角色主提示词自 QWEN-311 起由 `prompts/` 注册表加载（文件 sha256 校验、缺失/失配回退内置默认），工作流版本 `WORKFLOW_VERSION=learning-workflows-v2.3`（`backend/app/api/v2/run_lifecycle.py:29`）与之分开；结构化请求同时启用服务商 JSON 输出模式。
- **顺序与代码**：[角色提示词及 Pydantic 契约](../backend/app/agent_runtime/learning_package.py) 动态加入问题、有限记忆、画像、计划和证据。输出先长度限制，再 JSON 解析及字段/依赖/来源校验；不能只靠提示词约束权限。
- **持久化与故障**：模型版本、请求上限和 Run state 可追溯；提示词版本当前作为代码常量，尚无独立发布/回滚数据库。无效结构立即失败，不能把自由文本猜成计划。
- **证据与边界**：[学习包契约测试](../tests/a/test_learning_package.py)。未实现跨模型 A/B 提示词实验或自动 prompt 优化。

## 9. 安全与权限（Guardrail / Permission）

- **职责及输入输出**：登录凭据持久化，密码带盐哈希；Session 只存 token 摘要，课程授权由数据库逐账号查询。登录失败按账号摘要 15 分钟窗口限流；过期会话在签发及清理时删除。Graph Guard 在检索前拦截危险请求，工具再次核验授权。
- **顺序与代码**：[认证 API](../backend/app/api/v1/auth.py)、[认证仓储](../backend/app/repositories/auth_repo.py)、[V2 授权](../backend/app/api/v2/access.py)、[安全 Guard](../backend/app/services/safety/run_guard.py)。教师内容审核与普通续跑分别鉴权；模型输出无法触发写入。生产模式禁用内置演示账号与教师公开注册。
- **持久化与故障**：`registered_accounts`、`auth_sessions`、`course_grants`、`login_attempts`。数据库不可用时认证/授权拒绝请求。生产模式旧 V1 演示路由也需要登录；V1 逐账号、逐课程的全量资源隔离仍未完成。
- **证据与边界**：[限流测试](../tests/a/test_v2_auth_throttle.py)、[跨进程认证测试](../tests/a/test_persistent_auth.py)、[授权测试](../tests/a/test_v2_access.py)。规则防护不等于对所有提示注入的数学保证。

## 10. 输出与交互（UI / Response）

- **职责及输入输出**：[学习包页面](../frontend/src/views/LearningPackageView.vue) 展示节点与只读工具进度、讲解及逐题引用、实际使用来源、用量状态、待审状态、任务查询、教师审核和中断节点续跑。SSE 为交付事件，不是模型逐 token 真流。
- **顺序与代码**：[API 封装](../frontend/src/api/learningRuns.ts) 与 [SSE 解析](../frontend/src/api/learningStream.ts)；提交创建、接收进度、读取持久化事件、按权限恢复。服务器只在审核通过后交付 `answer.delta` / `run.completed`。
- **持久化与故障**：UI 根据 Run ID 查询服务器保存的状态；网络断开显示可恢复提示，已保存的部分事件可查询。费用标注为实际 token 与估算费用，缺失用量明示 unknown；不会把请求上限当花费。
- **证据与边界**：前端 `npm run build` 已通过；旧 [SSE 解析测试](../frontend/tests/learningStream.test.mjs) 可回归。2026-10-15 在真实浏览器配本地模拟 API 验证学生断流→查询→续跑、教师通过/拒绝、逐项引用和用量 unknown，并检查窄屏排版；尚未进行真实后端与在线模型的浏览器端到端联调。

## 接口、迁移与验收口径

需要依次执行 `20261014_0009_v2_event_sequence`、`0010_ingestion_tasks`、`0011_login_attempts` 迁移。新增的幂等请求键只作摘要存储；Run 的 `event_sequence` 与工具审计不会包含原始 prompt、模型凭据或完整画像。MCP 为可选依赖，未安装时主 V2 API 不受影响。

验证分层：旧版 66 条在线基线是历史数据；SQLite + 可控模型 + 内存 Checkpointer 仅为离线契约；隔离 PostgreSQL/Docker 已验证部分持久化、续跑和摄取；新版 76 条 Golden Set 和学习包内容质量仍需完整在线采样及人工复核。旧 `qwen3.7-text-embedding` 配置返回 HTTP 403；换成服务商文档中的 `qwen3.7-text-embedding-flash` 后，[隔离冒烟脚本](../scripts/v2_cloud_smoke.py) 的单例 Embedding 成功，DeepSeek 单例亦已成功并返回实际 token。稠密检索按文档版本记录的 Embedding 模型过滤，课程语料在切换模型时生成新版本，避免把同为 1024 维但语义空间不同的向量混用。部分 Flash 语料已写入隔离 PostgreSQL；固定的 10 条可覆盖事实题中 pgvector Top-5 命中 8 条，**不是** 48 条事实题、更不是 76 条集的结果。批量请求有间歇性失败，完整三策略比较中断；默认 hybrid 不变。所有付费调用使用同一 Redis 100 元保守预留上限，预留额不是提供商账单。不能把 V1 降级检索算成新版 pgvector 质量。
