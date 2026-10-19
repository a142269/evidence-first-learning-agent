# Qwen 接手主线：Agent 十模块完备性评估与优化主计划

> 编写：项目指挥（Lead） · 日期：2026-10-19 · 基线：`main@1ba64fa`（工作区干净，远端 CI run #19 全绿）
> 执行者：Qwen（本项目唯一主执行者）
> **协作通道**：`docs/QWEN_LEAD_DIALOGUE.md`（Lead 与 Qwen 直接对话，append-only；Qwen 在此汇报/提问）
> 必读：`docs/OPTIMIZATION_HANDOFF_2026-10-18.md`、`docs/OPTIMIZATION_STATUS_2026-10-18.md`、
> `docs/V2_TEN_MODULE_IMPLEMENTATION.md`、`README.md`（定位与“不宣称”边界）
>
> 本文分两部分：**A. 十模块完备性评估**、**B. 可直接执行的优化计划与 Qwen 工作规范**。
> 评估结论只基于当前代码、测试与已归档证据；没有证据的能力一律标为“未验证”，不替项目拔高。

---

## 0. 一页结论

**十模块是否完善？**

- **“模块是否齐全”**：齐。图片中的 10 个模块在项目里都有对应实现或明确映射，V2 学习包是一条真实的受控 Agent 链路，不是聊天壳子。
- **“是否达到图片所描述的通用完整 Agent”**：没有，而且**不应**按那个标准硬补。项目定位是**课程学习 Agent**，刻意收缩了通用自治能力（无浏览器/Shell/任意文件写入/通用代码执行/Tree-of-Thought/无限自主规划）。
- **按“课程学习 Agent 产品”标准**：主线可用度约 **7.5/10**；短板不在“少模块”，而在：
  1. **证据可信度**：缺真实人工盲评、缺独立新任务真模型验证（项目核心卖点是 evidence-first，这是最大风险）；
  2. **模块深度不均衡**：Memory/Planning/Prompting 是受限子集，Tool/Execution 是只读/领域执行，Scheduler 无 DAG/无独立 Run 队列；
  3. **工程化与发布**：CI 只覆盖部分测试文件、可观测性无看板告警、许可/素材来源未闭环、演示与 Release 未完成。

**最高优先级不是加功能，而是把“已实现能力”变成“可核实能力”**：

1. 人工盲评工具包 + 协议（人完成评分，Qwen 只做工具）；
2. 新任务真模型验证（需用户授权付费）；
3. 声明台账（claims ledger）：逐条核对 README/docs 的每个数字和“已实现”措辞；
4. 主线模块补强：Memory 写入策略、Planning 失败/重规划语义、统一 Tool 权限矩阵、提示词注册表、Run 队列；
5. 发布闭环：全量测试分层、可观测性、许可、演示、Release。

> 一句话给 Qwen：**不要把这个项目改造成通用 Agent；要把它做成“证据可核查、边界可解释、演示可复现”的课程学习 Agent。**

---

# A. 十模块完备性评估

## 1. 评估口径

### 1.1 图片中的十模块

| # | 模块 | 图片要点 | 在本项目中的对应物 |
|---|---|---|---|
| 1 | Brain / LLM | 思考、推理、决策、输出下一步/工具/回答 | Planner/Tutor/Practice/Reviewer 角色 + LLM 适配层 |
| 2 | Memory | 短期上下文、长期历史/偏好/知识库、外置向量库 | 最近 3 条完成 Run、学习画像、课程 RAG |
| 3 | Planning | 理解需求、拆任务、定顺序、失败重试/调整 | V2 两步计划 + 受限 ReAct 检索 + 一次返工 |
| 4 | Tool Use | 搜索、代码执行、文件读写、API、浏览器；Function Calling/MCP | V2 只读工具白名单；V1 工具注册表；只读 MCP 适配器 |
| 5 | Execution Engine | 跑代码、读写文件、调 API、操作 DB、启动命令 | 知识摄取执行器（Celery/索引）；沙箱/多媒体生成（V1） |
| 6 | Observation / Feedback | 获取结果、判断成功、回传模型继续思考 | 检索 observation、Reviewer、引用/审计、反思子系统 |
| 7 | Scheduler / State | 多步流程、循环控制、防死循环、多 Agent 调度 | LangGraph、检查点、租约、幂等、续跑/恢复；V1 优先级调度 |
| 8 | Prompting | 系统提示、角色、输出格式、动态拼接 | 各角色 system prompt + Pydantic JSON 契约 + 版本常量 |
| 9 | Guardrail / Permission | 限制能力、禁危险操作、文件白名单、API 权限 | 认证/课程/运行授权、V1 路由白名单、工具角色白名单、安全 Guard |
| 10 | UI / Response | 最终回答、格式化、流式、前端交互 | Vue 前端 23 个视图 + SSE 事件 + 结构化引用展示 |

### 1.2 成熟度分级

| 等级 | 含义 |
|---|---|
| **A（生产可用）** | 主路径完整，有自动化测试与真实依赖验证，边界写入文档，CI 覆盖 |
| **B（可用但有明确边界）** | 功能真实存在且受控，但覆盖/深度/验证不足，或只服务主链路的子集 |
| **C（原型/实验）** | 有代码/测试，但不进入主路径，或依赖未验证的外部条件 |
| **D（缺失）** | 没有实现，或只有文档设想 |

### 1.3 证据分级（所有进度更新必须标注）

| 标记 | 含义 |
|---|---|
| `offline` | SQLite/内存检查点/可控模型，仅证明契约 |
| `pg` | 真实 PostgreSQL/Redis、隔离容器/跨进程 |
| `cloud` | 真实模型单次/小额调用（须用户授权，费用未知则写 unknown） |
| `human` | 真实人类评分/审核（AI 不可代填） |
| `prod` | 目标部署环境验证（当前仅本机生产栈，非公网） |

## 2. 十模块逐项评估

### 总览表

| # | 模块 | 当前等级 | 一句话判断 | 目标等级 |
|---|---|---|---|---|
| 1 | Brain | **A-** | 结构化输出与故障语义扎实；缺模型路由/成本预算/配额 | A |
| 2 | Memory | **B** | 只有短期记忆 + 只读画像 + 外置 RAG，无长期语义记忆 | B+ |
| 3 | Planning | **B** | 受限两步计划 + 一次返工；无 DAG/动态重规划；V1 `depends_on` 未执行 | B+（主线）/不追求通用 |
| 4 | Tool Use | **B+** | 只读工具白名单 + MCP 只读；V1 工具有 sandbox 但不统一 | A- |
| 5 | Execution | **C+** | 有摄取执行器与 V1 沙箱/多媒体，但不是通用执行引擎 | B（受控） |
| 6 | Observation | **B+** | 检索观察 + Reviewer + 引用审计；缺统一观察 schema/反思进主链 | A- |
| 7 | Scheduler | **A-** | 检查点/租约/幂等/续跑强；无 DAG，无独立 Run 队列 | A |
| 8 | Prompting | **B** | 角色 prompt + JSON 契约 + 版本常量；无注册表/A-B/回归门禁 | B+ |
| 9 | Guardrail | **A-** | 权限边界强；缺统一权限矩阵/注入红队/配额/输出审核 | A |
| 10 | UI / Response | **B+** | SSE + 学习包页 + 引用展示；缺真实 E2E、可访问性、演示材料 | A- |

> 说明：这是**产品视角**的成熟度，不是“通用 Agent 能力分”。若按图片的通用标准，Tool/Execution/Planning 会显著更低，这是有意为之。

### 2.1 大模型核心（Brain / LLM）——A-

**现状与证据**

- 角色契约与学习包链路：`backend/app/agent_runtime/learning_package.py`（Planner/Tutor/Practice/Reviewer，Pydantic 校验）。
- 严格 OpenAI-compatible 适配：`backend/app/core/llm_client.py`（`achat_strict_with_usage`，返回 `finish_reason`；失败不伪装成 mock）。
- 结构化输出鲁棒性：`_extract_json_object`/截断重试/紧凑重试（v2.8），测试 `tests/a/test_structured_output_robustness.py`。
- 用量与预算：`usage_meter.py`、`eval_cost_guard.py`；测试 `test_v2_model_usage.py`、`test_v2_eval_cost_guard.py`。
- 真模型证据：`evals/results/structured-output-20261018.md`（dev 12/12、holdout 12/12，单次运行，局限已写明）。

**关键差距**

- P1：没有多模型路由/降级策略（主模型失败时是否切换、切换是否可审计、成本是否可控），只有单一配置。
- P1：没有默认的**每用户/每 Run token 配额与预算**；`eval_cost_guard` 只用于评测，生产主路径可无限调用。
- P2：没有原生 Function Calling 的端到端使用（结构化 JSON 是自实现协议）；对支持 tools 的供应商未利用。
- P2：缺少模型输出质量回归集（schema 之外的内容质量）。

**目标态（验收）**

- 配置化路由：主/备模型、超时、最大重试、降级原因写入审计；测试覆盖“主失败→备成功/两者失败”。
- 生产配额：每用户每日 token/费用上限，超限返回 429 与稳定错误码；测试；指标可观测。
- 文档明确：当前费用 `unknown` 时不得显示为 0。

### 2.2 记忆（Memory）——B

**现状与证据**

- 短期记忆：最近 3 条**已完成** Run（`conversation_memory.py`），测试 `test_conversation_memory_v2.py`。
- 长期画像：只读 `profiles`/BKT 记录（`v2_learning_tools.py`）、画像摘要（`api/v2/learning_runs.py`）。
- 外置记忆：课程 Markdown/PostgreSQL 文档版本/pgvector+FTS（`enterprise_retriever.py` 等）。
- 边界：明确“不是长期语义记忆自动学习，不把未核实回答写回课程知识”。

**关键差距**

- P1：没有**长期学习记忆的写入策略**（哪些事实可写、来源、置信度、TTL、审计、撤销）；当前画像不由模型自动写回，这是安全优点，但也导致跨会话“记住学习者”的能力弱。
- P1：没有**跨会话摘要/合并**（consolidation）；只有最近 3 条，超出即丢，长周期学习体验断档。
- P2：没有学习者可查看/删除记忆的 API/UI（隐私与可控性）。
- P2：部分完成 Run 明确不进入记忆（策略正确），但缺少文档化与测试固化（需显式测试“partial 不写记忆”）。
- P2：无记忆质量评估（摘要是否忠实、是否引入错误）。

**目标态**

- 记忆分层：短期（会话）→ 中期（完成 Run 摘要，带来源/时间/课程）→ 长期（学习者确认的偏好/目标，带 TTL）。
- 写入只允许“规则提取 + 学习者确认/教师审核”，模型只能提议，不能直接写。
- API：`GET/DELETE /api/v2/memory`（仅本人/同课程），审计；测试。
- 摘要任务有 token 预算、失败回退、幂等；partial/failed Run 永不入记忆（测试）。

### 2.3 规划（Planning）——B（主线受控，不追求通用）

**现状与证据**

- `LearningPlan` 强制一个讲解 + 一个依赖讲解的练习；禁止循环/未知依赖；Tutor 只允许 `search_course`/`finish`，最多三次检索；Reviewer 最多返工一次（`learning_package.py`）。
- V1 调度器：按优先级分组并行，`depends_on` 是兼容字段但**不执行**（`orchestrator.py` 注释与 README 已写明）。
- 失败语义：无证据、重复搜索、超预算、二次拒绝都有稳定错误码；部分完成状态已实现。

**关键差距**

- P1：没有**一次真正的重规划**（replan）：检索失败/工具失败后只能固定重试策略，不能在有界预算内换查询/换步骤；用户无法看到“为什么换策略”。
- P1：V1 `depends_on` 未实现——要么实现真 DAG（带失败传播），要么删字段与相关表述，不能继续“字段存在但不生效”。
- P2：没有可选 DAG/Plan-and-Execute 的**研究开关**；若做，必须默认关闭、可回滚、有失败语义测试。
- P2：没有多 Agent 协作规划（分工/仲裁/handoff），V1 的“多智能体”是角色并行，不是协作协议。

**目标态**

- 主线保持受限规划（这是优势，不要改坏）；新增“有界重规划”语义：最多 N 次、每次记录原因、预算内、结果可审计。
- V1：二选一——实现 DAG（节点/依赖/失败传播/超时）或删除 `depends_on` 字段与所有“DAG”表述；Qwen 必须选一个并在文档写清楚。
- 可选 DAG 研究开关默认 off；开启时同样不能突破预算/权限。

### 2.4 工具调用（Tool Use）——B+

**现状与证据**

- V2 只读工具：`v2_learning_tools.py`，`ROLE_TOOLS` 角色白名单（Planner/Tutor），服务端注入身份/课程/Run，Pydantic 拒绝额外参数；返回 `success/no_data/denied/invalid_args/timeout/failed`；工具审计关联 Run。
- V1 工具注册表：`services/agent_tools/registry.py`，含 lookup/KG/execute_code/search_resources/generate_learning_materials，带 trace；但主要被 `resource_generator_agent.py` 使用，未统一到 V2。
- MCP：`mcp_readonly.py` 只读 stdio 适配器（固定 scope 环境变量）；测试 `test_mcp_readonly_protocol.py`；需安装 `requirements-mcp.txt`。
- 安全：`tests/regression/test_sandbox_security_p0.py` 等。

**关键差距**

- P1：**两套工具/权限体系**（V1 registry vs V2 broker），没有统一注册、统一权限矩阵、统一超时/配额/审计 schema；新增工具容易只接到一边。
- P1：没有工具级配额（每 Run 调用次数/耗时/输出大小），只有笼统的检索次数限制。
- P1：MCP 只有只读 4 个工具，且依赖本地可信启动器；没有真实部署运行记录。
- P2：没有外部搜索/浏览器（这是有意的，不建议加）；没有可写工具（同样不建议默认加）。
- P2：工具结果没有统一“可重试/不可重试/证据强度”分类，影响观察与重规划。

**目标态**

- 单一 `ToolRegistry` 接口 + 角色/课程/Run 权限矩阵 + 超时/配额/输出截断 + 统一审计；V1/V2 各自适配层，不破坏线上契约。
- MCP：保持只读；若未来加写工具，必须独立进程、显式 allowlist、人工授权、审计；默认关闭。
- 工具调用指标：次数、成功率、P95 延迟、超时率、每工具错误分类。

### 2.5 执行引擎（Execution Engine）——C+（领域执行器，不是通用引擎）

**现状与证据**

- 知识摄取执行：`api/v1/knowledge_admin.py` → `ingestion_tasks` → Celery `tasks/ingestion.py` → `knowledge_ingest.py`；幂等键、租约、版本化、pgvector 重建；测试 `test_v2_ingestion_idempotency.py`、`test_celery_worker_process.py`、`test_vector_reindex.py`。
- V1 沙箱/多媒体：`services/multimodal/code_sandbox.py`（AST+RestrictedPython）、mermaid、pptx、tts、video、manim、OCR；测试在 `tests/regression/`、`tests/b/`。
- 学习 Agent 本身不执行宿主机命令；这是安全设计。

**关键差距**

- P1：没有“执行”与“观察”的统一抽象：摄取任务有状态，但 Agent 工具调用没有同一套任务/重试/取消语义。
- P2：可选“练习代码执行”能力（学习者提交代码→沙箱运行→结果反馈）尚未接入 V2；若做必须隔离、无网络、限时/限内存、默认关闭，并有逃逸测试。
- P2：执行器缺少资源配额（CPU/内存/磁盘/时长）与并发上限的统一配置。

**目标态**

- 保持“学习 Agent 不直接执行宿主命令”；把摄取/沙箱/多媒体抽象成受控执行任务（状态、重试、取消、审计）。
- 若产品需要练习代码执行：独立沙箱服务 + 白名单语言 + 资源限制 + 逃逸/DoS 测试 + 教师开关；否则明确不做。

### 2.6 观察与反馈（Observation / Feedback）——B+

**现状与证据**

- 检索 observation、Reviewer 分项结论、逐段/逐题 `source_ids` 与结构化 citations（`learning_package.py`）。
- 审计：`run_audit.py`（节点、工具、artifact_count、success_count）；Phoenix/OTel 可选（`core/observability.py`）。
- 反思子系统：`agents/reflection/`（reflector/rubric/strategies），V1 chat pipeline 使用；V2 主链未接入。
- 测试：`test_learning_package.py`、`test_learning_package_partial.py`、`test_claim_support.py`。

**关键差距**

- P1：观察结果没有统一 schema（工具状态、错误类、是否可重试、证据强度），导致重规划/反思只能写死。
- P1：V2 没有“有界反思”步骤：Reviewer 只做一次返工，缺少对“引用是否真的支持结论”的二次校验（claim_support 在评测侧，未进主链）。
- P2：没有用户反馈闭环（点赞/纠错/举报）进入评测与记忆（不能直接当 ground truth）。
- P2：没有观察质量指标（证据覆盖率、引用支持率、失败分类分布）。

**目标态**

- 统一 `Observation` 结构；V2 增加最多一次“claim-support 二次校验”（可用规则/评测模型，默认不额外付费或可配置）；测试“校验失败→不交付/返工”。
- 用户反馈只作为“待评估信号”，不自动改知识；有审计与隐私说明。

### 2.7 状态与调度（Scheduler / State Manager）——A-

**现状与证据**

- LangGraph + PostgreSQL checkpointer（`learning_graph.py`、`checkpointing.py`）。
- 租约/防并发：`run_leases.py`；幂等：`run_lifecycle.py`、`api/v2/learning_runs.py`；续跑/恢复/教师 reconcile；事件序号与 SSE `id`。
- 测试：`test_checkpoint_lifecycle.py`、`test_v2_unfinished_resume.py`、`test_v2_event_idempotency.py`、`test_postgres_api_recovery.py`、`test_run_leases.py`。
- 局限已写明：无 DAG、无分布式 Run 队列、不承诺跨系统恰好一次。

**关键差距**

- P1：**没有独立 Run 执行队列/Worker**：长任务仍在 Web 进程内跑，扩缩容、隔离故障、限流都受限；崩溃恢复靠租约/续跑，但没有统一“任务领取-心跳-完成”模型。
- P1：没有 DAG/依赖调度（同 2.3）；多 Agent 协作只是顺序/并行调用，没有 handoff 协议。
- P2：缺少调度指标（排队时长、执行时长、租约冲突、恢复次数）与告警。
- P2：Celery 用于摄取，但 Agent Run 的可靠性语义与摄取不一致，文档需统一。

**目标态**

- Run 队列：创建 Run 返回可查询 ID；Worker 租约领取、心跳、取消、超时；崩溃后租约过期可重领；测试跨进程/杀进程恢复；**不声称 exactly-once**。
- 调度指标与看板；与现有 SSE/恢复接口兼容。
- DAG/多 Agent 作为独立可选项，不混入主线。

### 2.8 提示词工程（Prompting）——B

**现状与证据**

- 各角色 system prompt + Pydantic 契约 + 动态拼接问题/记忆/画像/证据（`learning_package.py`）。
- `PROMPT_VERSION=learning-package-v2.8`；各 Agent `prompt_version` 类属性（`agents/base.py`）。
- 重试/截断指导（`_TRUNCATION_GUIDANCE`）；契约测试与结构化输出测试。
- 边界：无跨模型 A/B、无自动 prompt 优化、无独立发布/回滚。

**关键差距**

- P1：没有**提示词注册表**（文件化、版本号、hash、加载器、环境覆盖、回滚），版本只在代码常量里。
- P1：没有**提示词回归门禁**：改 prompt 后，除现有契约测试外没有固定输入/期望行为的回归集；A/B 也没有受控脚本。
- P2：提示注入防护缺少系统性红队集（检索文档、用户输入、工具参数、部分完成内容）。
- P2：提示词与模型/供应商的兼容矩阵没有文档化。

**目标态**

- `prompts/` 目录 + registry（name/version/hash/owner/changelog），核心 prompt 迁移；加载失败回退明确。
- 回归测试：固定样例的 schema/关键行为断言；A/B 脚本默认 dry-run/预算门禁；结果只进脱敏报告。
- 注入红队集（≥20 例）进 CI。

### 2.9 安全与权限（Guardrail / Permission）——A-

**现状与证据**

- 认证/会话/课程授权：`api/v1/auth.py`、`repositories/auth_repo.py`、`api/v2/access.py`；V2 逐 Run 校验用户/课程/问题/代次。
- V1 生产路由白名单（`test_v1_production_access.py`）；生产模式禁演示账号/公开注册；`/docs`、`/metrics` 边界；WebSocket 生产 fail-closed（`api/v1/mobile.py`）。
- 安全 Guard：`services/safety/run_guard.py`、`content_filter.py`、`adversarial_leakage.py`、`consistency_checker.py`；知识防幻觉 `knowledge_guard.py`。
- 部署策略：`core/deployment_policy.py`（口令/占位符/CORS 失败关闭）；Docker healthcheck；gitleaks + dependency scan（CI）。
- 测试：`test_deployment_policy.py`、`test_static_and_ws_safety.py`、`test_v2_access.py`、`test_v2_auth_throttle.py`、安全专项测试。

**关键差距**

- P1：权限逻辑分散在路由/服务/工具三层，没有**单一权限矩阵**（角色×路由×工具×课程×Run×字段）与统一测试；新增入口容易漏。
- P1：没有**模型调用配额/速率限制**（登录有限流，聊天/学习包没有每用户限额）。
- P1：没有系统化 prompt-injection/越权红队套件（有零散测试）。
- P2：输出审核只有规则/内容过滤，缺少分级处置（拒绝/降级/人工审核）与指标。
- P2：审计覆盖不完整（V1 部分路由无统一审计）；日志脱敏有测试但缺少全局策略文档。
- P2：依赖漏洞扫描只覆盖 Python，前端/桌面依赖没有同等门禁（前端有 audit？需确认并补齐）。

**目标态**

- 单一 `PermissionMatrix` + 启动自检（所有路由必须在矩阵中声明）；测试覆盖矩阵。
- 每用户/每课程配额与 429；指标。
- 注入红队集进 CI；输出分级处置；审计事件统一 schema。
- SBOM/依赖扫描覆盖 Python + npm；许可清单同步。

### 2.10 输出与交互（UI / Response）——B+

**现状与证据**

- 23 个 Vue 视图（含 `LearningPackageView.vue`、教师端、仪表盘、证据页、图谱等）；27 个 API 模块。
- SSE 事件（非逐 token 真流）、结构化引用、用量/待审/续跑/教师审核 UI。
- 构建：`npm run build` 在 CI 通过；前端测试 `frontend/tests/`（含 `learningStream.test.mjs`）。

**关键差距**

- P1：没有真实浏览器 E2E（前端 + 后端 + 可控模型）覆盖“学习包 happy path / partial / 教师审核 / 续跑”；现有验证是本地模拟 API。
- P1：23 个视图造成主线聚焦不足；V1/实验页面缺少清楚的功能开关/标注，演示时容易迷路。
- P2：可访问性（键盘/对比度/屏幕阅读器）与窄屏体验未系统审计。
- P2：没有演示视频/截图自动生成/Release 材料；README 截图可能过期。
- P2：错误态/未知费用/降级提示的一致性缺少组件级测试。

**目标态**

- Playwright E2E（headless，CI 可选 job）覆盖 4 条主路径；测试产出截图/视频 artifact。
- 主线导航聚焦：V2 学习包为默认入口；V1/实验功能打标签或开关；演示路径 5 分钟内可达。
- 可访问性清单与修复 Top 问题；错误态组件测试。

---

## 3. 横向能力评估

| 维度 | 现状 | 风险/差距 | 优先级 |
|---|---|---|---|
| 证据与评测 | 有 ablation/claim_support/结构化输出；**无人工盲评、无独立新任务真模型** | 核心“evidence-first”卖点缺人类证据；数字容易被误读 | **P0** |
| 成本与用量 | 有 token 记录/估算；`unknown` 会明示；评测有 Redis 预算门禁 | 生产无默认预算/配额；费用常 unknown；无成本看板 | P1 |
| 测试与 CI | 189 个测试文件；CI 只跑约 38（quality）+ 约 30（enterprise）；`tests/b`/integration/regression 未全进 CI | 回归漏洞；全量套件耗时/稳定性未知；覆盖率只对 2 个模块 ≥80% | P1 |
| 可观测性 | OTel/Phoenix 可选；审计事件；`/metrics` 权限边界 | 无看板/告警；无 Run/队列/工具指标聚合；trace 与 SSE 关联不完整 | P1 |
| 安全/合规 | 认证/授权/网关/密钥扫描/生产门禁较强 | 权限矩阵分散、注入红队不足、配额缺失、npm SBOM 缺失 | P1 |
| 产品聚焦 | V2 主线清晰，README 已声明 V1/实验边界 | 23 视图、V1 大量旧能力，演示/维护成本高 | P1 |
| 许可/素材 | `THIRD_PARTY_NOTICES.md` 机器清单 | dist NOTICE、integrated-map 源码、125 媒体来源、GPL/LGPL 人工审查 | P1 |
| 发布 | 本地生产栈验收、Linux 锁、CI 绿 | 无公网部署/TLS/备份/监控；无 Release/演示视频；nightly 未手动跑 | P1 |

---

## 4. 决策：补什么、不补什么

### 4.1 必须补（与产品价值和证据可信度直接相关）

1. 人工盲评工具 + 独立新任务真模型验证（P0）。
2. 声明台账 + 文档一致性（P0）。
3. Memory 写入策略/跨会话摘要（P1）。
4. Planning 有界重规划 + V1 `depends_on` 决策（P1）。
5. 统一 Tool 注册/权限矩阵/配额 + MCP 硬化（P1）。
6. 观察/反思统一 schema + claim-support 进主链（P1）。
7. Run 队列/Worker + 调度指标（P1）。
8. Prompt 注册表 + 回归门禁 + 注入红队（P1）。
9. 权限矩阵/配额/输出审核（P1）。
10. E2E、可观测性看板、全量测试分层、发布材料（P1）。

### 4.2 可选/研究（默认关闭、可回滚、单独评测）

- 可选 DAG / Plan-and-Execute 研究模式（不替代主线）。
- 练习代码执行（沙箱、无网络、资源限制、教师开关）。
- 可写 MCP 工具（独立进程、显式 allowlist、人工授权）。
- 多 Agent 协作 handoff 协议（仅当 V1 保留时）。

### 4.3 明确不做（防止过度设计和安全风险）

- 不把 V2 改成通用浏览器/Shell/任意文件读写 Agent（与学习场景无关，攻击面大）。
- 不追求 Tree-of-Thought/无限自主循环；预算/步数/可审计优先。
- 不重写 V1；V1 只做“冻结/标注/必要 DAG 修复”，资源优先 V2。
- 不引入 AutoGen/CrewAI 等重框架替换 LangGraph，除非有明确收益与对比评测。
- 不在没有用户授权时跑付费模型；不把单次运行说成泛化结论；不伪造人工评分。
- 不弱化生产安全门禁来“让演示更顺”。

---

# B. Qwen 优化主计划

## 5. Qwen 执行规范（硬约束）

### 5.1 角色与范围

- 你是**唯一主执行者**；可以直接改代码、加测试、跑测试、提交/推送。
- 优先主线 V2；V1 只做范围明确的小修（DAG 决策、权限/安全、文档一致性）。
- 每个阶段开始前先读：本计划 → `OPTIMIZATION_HANDOFF_2026-10-18.md` → `OPTIMIZATION_STATUS_2026-10-18.md` → `V2_TEN_MODULE_IMPLEMENTATION.md`。
- 每周/每波结束更新 `docs/OPTIMIZATION_STATUS_<date>.md`（只写已验证结果）。

### 5.2 不可违反的规则

1. **不伪造证据**：没有跑过的测试不写“通过”；没有人类评分不写“已人工验证”；费用未知写 `unknown`，不写 0。
2. **不泄露密钥/私有数据**：不提交 `.env`、Key、token、连接串、原始评测输出；提交前自检 + CI gitleaks。
3. **不破坏用户数据**：不执行 `git reset --hard`、`git clean`；不覆盖他人工作区；迁移必须可回滚/有备份说明。
4. **测试隔离**：统一使用新的 `--basetemp output/<独立目录>/base`、隔离 SQLite 文件、一次性容器；不污染主数据库。
5. **付费模型调用**：先向用户申请授权并记录调用数/token/延迟；评测预算门禁开启；失败重试也要记录。
6. **不扩权**：默认只读工具；新增写工具必须独立进程 + allowlist + 人工授权 + 审计，默认关闭。
7. **不做“看似完成”**：文档、README、PR 描述、提交信息都必须与代码/证据一致；不确定就标“未验证”。
8. **Windows 沙箱注意**：pytest `tmp_path` 可能权限受限，必要时用 `PYTHONPATH=output/pytest-...` + `-p sandbox_tmpdir_shim`；不要把沙箱问题误判为代码 bug。

### 5.3 工作流（每个任务固定执行）

1. **读**：任务相关文件 + 现有测试 + 文档；确认边界与已完成项（避免重做）。
2. **设计**：写下最小改动、契约变化、失败语义、回滚方式；涉及 API/DB 先写迁移与兼容方案。
3. **测**：先补回归测试（失败）→ 实现 → 通过；必要时加集成/跨进程测试。
4. **验**：跑目标测试 + 受影响模块 + CI 等价检查（ruff/mypy/build/compose config）。
5. **写**：更新文档/README/状态文档；标注证据等级（offline/pg/cloud/human/prod）。
6. **提交**：小步提交，提交信息写“做了什么 + 证据”；推送前 `git status` 干净、无敏感文件。
7. **报告**：按模板汇报（见 5.5），包含改动、测试命令与结果、未验证项、风险。

### 5.4 Definition of Done（每个任务必须全部满足）

- [ ] 代码实现符合任务目标，未扩大范围。
- [ ] 新增/修改行为有自动化测试；关键失败路径有测试。
- [ ] 相关旧测试不回归；CI 等价检查通过（ruff、mypy 目标集、前端构建、compose config）。
- [ ] 迁移可回滚（如有 DB 变更），文档写明。
- [ ] 安全边界未被削弱；无密钥/隐私数据进入提交。
- [ ] 文档更新：行为、限制、证据等级、未验证项。
- [ ] 提交信息 + 状态文档一致；无“未验证却写通过”的措辞。

### 5.5 汇报模板（每次交付）

```text
[TASK QWEN-xxx] 标题
结论：完成 / 部分完成 / 阻塞（原因）
改动：文件列表（关键 3-8 个）
测试：命令 + passed/failed/skipped（含环境：SQLite/PG/容器）
证据等级：offline / pg / cloud / human / prod（说明）
未验证/风险：...
下一步：...
用量：模型调用数/输入输出 token（若适用；未知写 unknown）
```

### 5.6 常用命令

```powershell
# 目标测试（Windows 沙箱）
$env:PYTHONPATH="output\pytest-baseline-20261018"; $env:DATABASE_URL="sqlite:///./output/<dir>/dev.db"
$env:A3_OFFLINE_DEMO="true"
python -m pytest tests/a/test_xxx.py --basetemp output/<dir>/base -o addopts= `
  -p no:cacheprovider -p sandbox_tmpdir_shim --benchmark-disable -q

# 静态检查
python -m ruff check --select=F821,F823,E9 backend/app scripts/ tests/
python -m mypy --config-file mypy.ini

# 前端
cd frontend; npm ci; npm run build

# Compose 配置（不启动）
docker compose -f docker-compose.yml config > $null
docker compose --env-file .env.production -f docker-compose.production.yml config > $null

# 推送前自检
git status --short; git diff --check; git diff --stat
```

### 5.7 分支与提交

- 每个 Wave 一个分支：`qwen/wave0-baseline`、`qwen/wave1-evidence`、`qwen/wave2-memory-planning`、`qwen/wave3-scale`、`qwen/wave4-release`。
- 小步提交；提交信息格式：`<area>: <what> (<evidence>)`，例如 `agent/memory: add confirmed-memory writes and audit (tests: 8 passed)`。
- 每 Wave 结束合并到 `main` 前：本地 CI 等价检查 + 远端 CI 绿；不通过不合并。

---

## 6. 分波次任务计划

> 估时为“人类工程师等效人日”，Qwen 可并行/加速；优先级：P0 必做、P1 应做、P2 可选。
> 依赖关系按 ID 标注；同一 Wave 内可并行，但涉及同一文件/模块的任务需串行。

### Wave 0：基线与治理（第 1 周，约 3-4 人日）

| ID | 任务 | 优先级 | 依赖 | 估时 | 验收 |
|---|---|---|---|---|---|
| QWEN-000 | 基线复跑与冻结：跑 `tests/a` 核心、CI 等价检查、前端构建；记录 passed/skipped/failed、耗时；更新状态文档 | P0 | — | 1d | `output/qwen-baseline-2026-10-19/` 有日志；状态文档只写实测 |
| QWEN-001 | 声明台账 `docs/CLAIMS_LEDGER.md`：逐条列出 README/docs/演示稿中的数字与“已实现”表述，状态=有证据/需复跑/愿景；删除或降级无证据表述 | P0 | — | 1.5d | 台账覆盖全部对外数字；README 修改后 CI 绿 |
| QWEN-002 | 测试分层映射：把 189 个测试文件映射到 fast/nightly/manual，说明为何某些不进 CI；产出 `docs/TEST_MATRIX.md` | P1 | — | 1d | 矩阵可执行；nightly 计划列出 |
| QWEN-003 | 依赖/许可基线：Python/npm 漏洞扫描、SBOM 草案、许可清单差异；只做清单不做法务结论 | P1 | — | 1d | `output/qwen-baseline/` + 文档更新 |

**Wave 0 出口**：对“项目现在到底有什么证据”有一张可信清单；没有未经验证的数字留在 README/演示稿。

### Wave 1：证据与可信度（第 2-3 周，约 8-10 人日，最高优先）

| ID | 任务 | 优先级 | 依赖 | 估时 | 验收 |
|---|---|---|---|---|---|
| QWEN-101 | 人工盲评工具包：`scripts/human_eval/`（生成随机化评分包/导入评分/计算一致性与置信区间/导出报告）；协议 `docs/HUMAN_EVAL_PROTOCOL.md`；测试工具本身 | **P0** | QWEN-001 | 3d | 两位评审可独立完成 20 题；工具输出 kappa/分歧；**不代填评分** |
| QWEN-102 | 独立新任务真模型验证：设计 12 个未用过的课程任务（3 课程×4），用**用户原有 DeepSeek API** 跑 v2.8 与基线；检索走 **SQLite + legacy RAG 回退**（无 cloud embedding，不调用 embedding API）；调用上限：1 次冒烟 + 12×1（每任务重试≤2，总≤37）；记录调用/token/延迟/费用（未知写 unknown）；脱敏报告 | **P0** | 已授权（2026-10-19，本地 `.env`；不新增/不上传密钥） | 2d | `evals/results/independent-2026-10-*.md`；局限写明；原始数据只在 gitignore 目录 |
| QWEN-103 | 证据等级与文档一致性：给 README/核心文档的每条能力加证据等级；删除/修正 `V2_TEN_MODULE_IMPLEMENTATION.md` 中与代码不符处 | **P0** | QWEN-001 | 2d | 文档与代码一致；CI 绿 |
| QWEN-104 | 成本/用量可见性：统一每个 Run 的 usage/cost 摘要（含 unknown 语义），加管理端查询与测试；不做账单承诺 | P1 | QWEN-000 | 2d | 接口/测试；文档说明估算口径 |
| QWEN-105 | PG/Redis 独立复跑：用一次性容器重跑企业合同+部分完成恢复，生成可复现报告 | P1 | QWEN-000 | 1d | 报告含命令、版本、passed；容器清理 |

**Wave 1 出口**：项目拥有“可被别人复核的证据包”；人工评分的**执行**仍需真人，Qwen 只交付工具与流程。

### Wave 2：主线模块深度（第 3-5 周，约 15-18 人日）

| ID | 任务 | 优先级 | 依赖 | 估时 | 验收 |
|---|---|---|---|---|---|
| QWEN-201 | Memory schema + 写入策略：`user_memories`（类型/来源/置信度/TTL/审计），仅“规则提取 + 用户确认/教师审核”写入；模型只能提议 | P1 | QWEN-103 | 3d | 迁移+回滚；写入/拒绝/撤销测试；partial 不入记忆测试 |
| QWEN-202 | 跨会话摘要/consolidation：对完成 Run 生成有界摘要（token 预算、幂等、失败回退），替代固定 3 条窗口的可配置版本 | P1 | QWEN-201 | 3d | 摘要忠实性测试（固定样例）；token 预算；不被 partial 污染 |
| QWEN-203 | 学习者记忆 API/UI：查看/删除本人记忆；审计；前端最小页面 | P2 | QWEN-201 | 3d | 权限测试；UI 构建；文档 |
| QWEN-211 | Planning 有界重规划：工具失败/无证据时，最多 1 次换查询/换策略；记录原因与预算；不突破步数 | P1 | QWEN-103 | 3d | 失败路径测试；审计事件；文档 |
| QWEN-212 | V1 `depends_on` 决策：实现真 DAG（依赖/失败传播/超时）或删除字段与所有 DAG 表述；二选一 | P1 | QWEN-001 | 2d | 若实现：DAG 测试；若删除：grep 无残留 + 文档更新 |
| QWEN-221 | 统一 ToolRegistry + 权限矩阵：合并 V1 registry/V2 broker 接口；角色×课程×Run×工具×参数校验；超时/配额/截断；统一审计 | P1 | QWEN-103 | 5d | 迁移现有工具；矩阵测试；V2 回归全绿；新增工具只接一处 |
| QWEN-222 | MCP 硬化：scope 仅来自可信启动器；只读；协议/超时/权限测试；部署文档；不放公网 | P1 | QWEN-221 | 3d | 协议测试扩展；无 scope 拒绝；文档 |
| QWEN-231 | 观察/反思进主链：统一 Observation schema（状态/错误类/可重试/证据强度）；V2 最多一次 claim-support 二次校验，失败不交付/返工 | P1 | QWEN-221 | 3d | 失败路径测试；引用支持验证；不额外付费时可用规则版 |
| QWEN-232 | 用户反馈采集：点赞/纠错/举报进入待评估队列，不当 ground truth；隐私说明 | P2 | QWEN-231 | 2d | API+存储+审计；测试 |

**Wave 2 出口**：Memory/Planning/Tool/Observation 从“能用”升级为“有策略、可审计、可测试”；主线不被通用化拖垮。

### Wave 3：工程化与体验（第 5-7 周，约 18-22 人日）

| ID | 任务 | 优先级 | 依赖 | 估时 | 验收 |
|---|---|---|---|---|---|
| QWEN-301 | Run 队列/Worker：Run 创建与执行解耦；租约领取/心跳/取消/超时；崩溃可重领；API 兼容 | P1 | QWEN-211 | 5d | 跨进程测试；杀进程恢复；不声称 exactly-once；文档 |
| QWEN-302 | 多 Agent 协作协议（可选）：typed handoff artifact、supervisor 路由；只用于 V1 研究开关 | P2 | QWEN-212 | 5d | 协议测试；默认关闭；文档标注实验 |
| QWEN-311 | Prompt 注册表：`prompts/` + registry（name/version/hash/changelog）；核心 prompt 迁移；加载回退 | P1 | QWEN-103 | 3d | 单测；版本可追溯；无硬编码散落 |
| QWEN-312 | Prompt 回归/AB harness：固定样例行为断言；A/B 脚本带预算门禁/dry-run；脱敏报告 | P1 | QWEN-311 | 3d | 回归测试进 CI；A/B 默认 dry-run |
| QWEN-321 | 权限矩阵统一：路由×角色×课程×Run×工具；启动自检“未声明路由拒绝启动”（或 CI 检查） | P1 | QWEN-221 | 3d | 矩阵测试；无遗漏路由；文档 |
| QWEN-322 | 注入红队套件：≥20 例（用户输入/检索文档/工具参数/部分完成内容），期望拒绝/安全降级；进 CI | P1 | QWEN-321 | 3d | 全部用例通过；新增回归 |
| QWEN-323 | 输出审核与分级处置：规则+内容过滤；拒绝/降级/人工审核三级；指标 | P2 | QWEN-322 | 3d | 分级测试；审计 |
| QWEN-324 | 配额与速率限制：每用户/课程 token/费用/请求限额；429 语义；指标 | P1 | QWEN-104 | 3d | 429 测试；配置化；文档 |
| QWEN-331 | Playwright E2E：学习包 happy path、partial、教师审核、续跑；headless；CI 可选 job | P2 | QWEN-103 | 5d | 4 条路径视频/截图 artifact；稳定重跑 |
| QWEN-332 | 可访问性/响应式：键盘/对比度/窄屏 Top 问题清单与修复 | P2 | — | 2d | 清单+修复；构建通过 |
| QWEN-333 | UI 聚焦与 legacy 标注：V2 默认入口；V1/实验页面开关/标签；演示路径 | P2 | — | 2d | 导航/开关；文档 |
| QWEN-341 | 指标与告警：Run 成功率/延迟/错误/工具/队列/成本指标；Prometheus+告警规则草案 | P1 | QWEN-301 | 3d | `/metrics` 指标测试；告警 YAML；文档 |
| QWEN-342 | trace/日志关联：run_id/execution_id/trace_id 贯穿 SSE/工具/审计 | P2 | QWEN-341 | 2d | 关联测试；排障文档 |
| QWEN-343 | 测试分层进 nightly：把 `tests/b`/integration/regression 分批加入 nightly；fast CI 保持 <20min；**新增（QWEN-121 收口）**：验证 Linux nightly 真跑到 `tests/a/test_celery_worker_process.py`（Windows 侧已条件 skip），并给 `frontend/tests/_orphaned/` 17 个孤儿测试给出结论（恢复源码则移回，否则正式处置） | P1 | QWEN-002 | 3d | nightly 绿；耗时记录；明确 skip 原因；孤儿测试有处置结论 |

**Wave 3 出口**：可扩缩容、可观测、可测试的工程底座；安全边界有红队与矩阵。

### Wave 4：发布（第 7-8 周，约 8-10 人日）

| ID | 任务 | 优先级 | 依赖 | 估时 | 验收 |
|---|---|---|---|---|---|
| QWEN-401 | 许可/素材闭环：准备 dist NOTICE、integrated-map 来源、125 媒体清单、GPL/LGPL 审查包；**新增（QWEN-121 收口）**：给出 `frontend/integrated-map-src` 来源结论——取得可提交源码则把 `frontend/tests/_orphaned/` 16 个依赖它的测试移回 `frontend/tests/`，否则正式删除并同步文档（`docs/TripleU平台全功能思维导图.md` L550/L1231、`docs/10-学术与工程创新对照表.md` L490-491）；法务结论由人签署 | P1 | QWEN-003 | 3d | 清单/文件齐全；文档标注"待人工审查"；孤儿测试有来源结论 |
| QWEN-402 | Release 材料：版本号/CHANGELOG、演示视频脚本与录制清单、5 分钟演示路径、README 截图更新 | P1 | QWEN-333 | 3d | Release 草稿；视频/截图 artifact |
| QWEN-403 | 生产 Runbook：TLS/域名/备份/迁移窗口/监控模板；本机演练记录；不宣称公网已验证 | P1 | QWEN-341 | 3d | Runbook + 演练日志；未验证项清单 |
| QWEN-404 | 独立复核：请未参与开发的 agent/人按文档复跑关键证据；记录差异与修正 | **P0** | 全部 | 2d | 复核报告；差异关闭或标注 |

**Wave 4 出口**：可发布、可复核、可演示；所有对外声明有证据或明确标注“未验证”。

---

## 7. 验收指标（KPI / 质量门）

| 维度 | 指标 | 目标 |
|---|---|---|
| 证据 | 人工盲评 | 2 位独立评审 × 20 题；报告真实 kappa/分歧，不设“必过”造假门槛 |
| 证据 | 新任务真模型 | ≥12 个未用任务；报告成功率、调用/token/延迟；费用未知写 unknown |
| 证据 | 声明台账 | 100% 对外数字有证据或标注“愿景/未验证” |
| 质量 | CI | 主线 CI 绿；新增测试覆盖失败路径 |
| 质量 | 覆盖率 | 核心模块（learning_package/claim_support）≥80%，扩展核心（memory/tools/scheduler）≥70% |
| 可靠性 | Run 队列 | 崩溃/租约过期可恢复；失败有稳定错误码；不声称 exactly-once |
| 安全 | 门禁 | gitleaks/dependency scan 绿；注入红队 ≥20 例通过；权限矩阵自检通过 |
| 观测 | 指标 | 成功率/延迟/错误/工具/队列/成本可查；告警草案 |
| 发布 | 文档 | README/演示稿与代码一致；未验证项显式标注 |
| 体验 | E2E | 4 条主路径可重复通过（headless） |

---

## 8. 风险与回滚

| 风险 | 影响 | 缓解 |
|---|---|---|
| 为“对齐十模块”过度扩张 | 安全面/维护成本上升 | 本计划 4.3 明确不做；一切新能力默认关闭/可回滚 |
| 付费模型评测消耗 | 费用不可控 | 用户授权 + Redis 预算门禁 + 调用上限；记录 unknown |
| 人类评审不可用 | 证据缺口长期存在 | Qwen 交付工具/流程；状态文档明确“等待人工”，不代填 |
| DB 迁移/调度改动 | 数据/恢复风险 | 可回滚迁移 + 备份说明 + PG 跨进程测试；feature flag |
| V1/V2 双线维护 | 分心/回归 | V1 冻结，只做 DAG 决策与安全修复；V2 优先 |
| Windows/Linux 差异 | 测试假失败 | CI Linux + 本机隔离测试；平台相关断言显式分支 |
| CI 时间变长 | 反馈慢 | fast/nightly 分层；E2E 独立 job；并行化 |

**回滚原则**：新功能默认 feature flag（`V2_*` 环境变量）；DB 迁移必须有 downgrade 或数据备份；不删除旧接口直到新接口稳定一个 Wave；文档先标“实验”，验证后再升级等级。

---

## 9. Qwen 第一周行动清单（照做）

**Day 1**
1. 读 5 份文档（本计划 + 3 份 handoff/status + 十模块说明），列出“已完成勿重做”清单。
2. 跑基线：`tests/a` 核心子集 + ruff + 前端构建；记录到 `output/qwen-baseline-2026-10-19/`。
3. 建分支 `qwen/wave0-baseline`；创建 `docs/CLAIMS_LEDGER.md` 草稿。

**Day 2**
4. 完成 QWEN-001（声明台账），修正 README 中无证据/过期数字；CI 绿后提交。
5. 完成 QWEN-002（测试分层矩阵）。

**Day 3**
6. 完成 QWEN-003（依赖/许可/SBOM 基线）。
7. 写 Wave 1 细化设计（人工评分包字段、盲评流程、kappa 计算），提交设计文档。

**Day 4-5**
8. 实现 QWEN-101 工具包 + 测试（不代填评分）。
9. 按已授权范围执行 QWEN-102：先用 `[PLAN]` 记录题集与预算，再调用（上限见 §3 第 4 条）；费用未知写 `unknown`，不打印/提交密钥。
10. 周报：基线数字、台账完成度、下一步风险。

---

## 附录 A：十模块 ↔ 代码/测试映射

| 模块 | 核心代码 | 主要测试 |
|---|---|---|
| Brain | `backend/app/agent_runtime/learning_package.py`、`backend/app/core/llm_client.py` | `tests/a/test_learning_package.py`、`test_structured_output_robustness.py`、`test_v2_model_usage.py` |
| Memory | `conversation_memory.py`、`services/v2_learning_tools.py`、`api/v2/learning_runs.py` | `test_conversation_memory_v2.py`、`test_v2_learning_tools.py` |
| Planning | `learning_package.py`（LearningPlan）、`learning_graph.py`、`agents/orchestrator.py` | `test_learning_package.py`、`test_learning_package_partial.py` |
| Tool | `services/v2_learning_tools.py`、`services/agent_tools/registry.py`、`mcp_readonly.py` | `test_v2_learning_tools.py`、`test_mcp_readonly_protocol.py` |
| Execution | `services/knowledge_ingest.py`、`tasks/ingestion.py`、`services/multimodal/code_sandbox.py` | `test_v2_ingestion_idempotency.py`、`test_celery_worker_process.py`、`test_sandbox_security_p0.py` |
| Observation | `run_audit.py`、`learning_package.py`（citations）、`agents/reflection/` | `test_learning_package.py`、`test_claim_support.py` |
| Scheduler | `learning_graph.py`、`checkpointing.py`、`run_leases.py`、`api/v2/learning_runs.py` | `test_v2_unfinished_resume.py`、`test_v2_event_idempotency.py`、`test_run_leases.py` |
| Prompting | `learning_package.py`（prompts）、`agents/base.py`（prompt_version） | `test_learning_package.py`、`test_learning_package_retry_guidance.py` |
| Guardrail | `services/safety/*`、`core/deployment_policy.py`、`api/v2/access.py`、`api/v1/auth.py` | `test_v2_access.py`、`test_static_and_ws_safety.py`、`test_deployment_policy.py` |
| UI | `frontend/src/views/LearningPackageView.vue`、`api/learningRuns.ts`、`api/learningStream.ts` | `frontend/tests/learningStream.test.mjs`、`npm run build` |

## 附录 B：已完成、不要重做

- `partially_completed` 部分成功链路、逐项 Reviewer 结论、未审核内容不交付（测试 22 项）。
- 结构化输出 v2.8：finish_reason、围栏/散文容错、截断感知重试（测试 9 项）。
- claim_support 与 ablation 固定证据实验（`evals/results/`）。
- 生产边界：docs/metrics 404/401、V1 路由白名单、WS fail-closed、部署策略失败关闭、生产 Compose 配方。
- CI：dockerized gitleaks（只输出路径/规则）、pytest 失败注解、Compose 解析、Linux 锁安装、nightly 锁任务。
- 安全修复：SPA 路径穿越、健康检查、日志脱敏、许可清单。
- 测试：189 个测试文件；企业合同 353 passed、部分完成 PG 恢复、66 项 Linux 锁测试。
- 不要重复实现；如需改动，先读测试和文档。

## 附录 C：证据与免责

- 本评估基于 2026-10-19 当前 `main` 与已有归档；未在本计划中新增模型调用或人工评分。
- “等级”是工程判断，不是认证；人工评分、公网生产、法务结论均需真人签署。
- 任何进度更新必须标注证据等级；未验证内容不得写成已验证。
