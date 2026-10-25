# V2 学习包：规划、受限 ReAct-style 检索决策循环与记忆

本批把三项能力接入同一条真实后端链路，并增加页面 `/learning-package`，从「Agent 编排」页面进入。
原有 V1 聊天页面保持原链路。新页面可以选择「课程问答」或「讲解 + 三道练习」，使用登录凭据调用 V2。

## 实际执行流程

1. 校验登录用户与课程权限，读取本用户、本课程、本会话最近三次已完成结果作为上下文。
2. Planner 输出 JSON 任务计划：一个 Tutor 步骤、一个依赖该步骤的 Practice 步骤。验证角色、ID、依赖关系，拒绝循环、未知依赖或未知角色。
3. Tutor 执行受限 ReAct-style 检索决策循环，只能输出 `search_course` 或 `finish`，最多检索 3 次。每次检索结果作为 observation 回到下一次模型决策；可以改写查询再检索。工具课程范围由服务端身份校验结果注入。这不是开放式多工具 Agent。
4. Tutor 依据证据生成讲解；Practice 读取该讲解作为依赖产物，生成三道带答案、解析及来源 ID 的练习。
5. Reviewer 检查目标覆盖、讲解、题目与证据，并给出分项结论 `lesson_approved` / `practice_approved`。整包通过时交付讲解与三道练习；首次拒绝按问题选择返工：练习问题只重做练习；讲解问题重做讲解及依赖练习；证据不足时在原有预算内补充课程检索，再重做讲解与练习。第二次拒绝通常终止并报告失败；重复查询或检索预算耗尽时，补证据返工会失败关闭。Reviewer 可以显式给出部分交付结论（讲解可交付而练习不可交付），或删除个别判定错误的题目后交付其余内容，见「部分成功」一节。
6. 可选教师审核：待审核草稿不会发送给学生，也不会写入可召回的会话记忆。通过后交付结果，拒绝后不交付草稿。部分交付的学习包同样先经过教师审核，审核草稿带 `partial_completion`，审核通过不改变未交付内容的未验证状态。

学习计划是有约束的两步骤计划，不是任意 Agent DAG。返工属于有限修订，不宣称实现开放式全自动重规划。
工具决策使用 JSON Schema 校验的模型输出，不依赖模型提供商原生 Function Calling，也不执行模型输出的代码或 URL。

## 记忆边界

- 会话记忆读取 `agent_runs` 数据库，按已认证用户、课程、session_id 和 completed 状态过滤；只有标记为来自已认证请求的运行可被召回。
- 最多三组问答，每条消息最多 2000 字符，总计最多 12000 字符。是窗口记忆，没有声称具备摘要压缩、向量记忆或经验自学习。
- 新请求固定记忆快照，各 Run 仍使用独立 thread_id；不会共享正在执行的 Graph 状态。
- 图或服务进程重新创建后可重新从数据库读取已完成历史。查询同一 session_id 的其他用户不会得到这份历史。
- 学生画像仍复用已有持久化画像，本流程只读取，不自动将模型猜测写成永久画像。
- 省略 session_id 时服务端生成独立会话编号，并通过 run.started 返回；调用方后续需复用这个编号。
- 页面「开启新会话」切换会话范围，不删除数据库中的历史记录。

## 执行预算与错误

| 限制 | 当前值 |
|---|---:|
| 课程检索次数 | 最多 3 次 |
| Reviewer 触发返工 | 最多 1 次 |
| 计划重规划轮数 | 最多 1 次（基线常量） |
| 单运行内计划版本 | 最多 2 版（基线常量） |
| 逻辑模型调用 | 最多 12 次 |
| 累计模型输入 | 最多 100000 字符 |
| 每次模型输出请求上限 | 2048 tokens |
| 结构化输出重试 | 普通无效输出最多 2 次尝试；长度截断最多 3 次尝试（计入模型调用总预算） |
| 学习包流式执行超时 | 180 秒 |

重复查询会停止检索；有证据时继续生成，无证据时失败。无证据、无效输出、未知工具、无效引用或二次质量失败都不会返回成功学习包。

**有界重规划**：一次课程检索失败（含超时），或模型重复使用已经检索过的提问仍未取得任何证据，都会把当前计划判为失效，Planner 最多重规划 **1 次**（`MAX_REPLAN_ROUNDS=1`，单运行内计划版本上限 `MAX_REPLAN_DEPTH=2`；两者是本批的基线常量，最终阈值属产品裁定）。重规划沿用已缓存的学习上下文，不再重复读取画像、错题与前置知识；失效那一刻的触发原因与计数（轮次、计划版本、`model_calls`、`tool_calls`、`input_chars`、检索次数、证据数）写入检查点状态 `plan_invalidations`，并额外发出一个 `plan.replanned` 审计事件——事件只含原因标识与计数，不含提示词、模型文本或检索内容，也不进入交付结果或教师审核草稿。已计费但失败的检索仍记入 `searches`，所以重规划后的计划不可能把同一个提问再跑一遍。检索预算耗尽、无证据直接结束、以及工具被拒绝授权（`denied`/`invalid_args`）都**不是**计划失效，不会换来第二次 Planner 调用。超过上限时运行**停止**并沿用底层原因的既有错误码（例如 `learning_package_tool_failed`），不新增用户可见错误码；已消耗的轮次保存在检查点里，崩溃后用 `/{run_id}/continue` 恢复只会重放失败节点并再次停止，不会发放新的一轮，也不会追加模型调用。
返回的 `budget.output_token_limit` 是累计请求输出上限，不是实际消耗；`model_calls` 是编排层调用数，不统计底层 HTTP 重试。真实 token usage 与费用统计仍待接入。
Reviewer 是一次模型质量检查，不是事实正确性的证明；引用检查验证来源 ID 是否属于检索证据，不冒充语义忠实度评估。

结构化输出解析会容忍 Markdown 围栏和 JSON 前后的说明文字，但仍按 Schema 严格校验。2026-10-18 的诊断确认，开发集此前的结构化输出失败是**输出长度截断**（`finish_reason=length` 或 JSON 未闭合，落在每次调用的输出 token 上限），不是字段错误或拒答：失败样本的 Practice 调用 6/6 次恰好停在上限。现在的处理是识别截断后追加一次固定文案的精简要求（不回显模型输出），最多 3 次尝试；仍失败则关闭式失败。实验器为公平比较采用 1024 tokens/调，生产默认为 2048 tokens/调；该重试只提高格式完成率，不证明内容质量。

## 部分成功（partially_completed）

运行状态区分 `completed`、`partially_completed`、`awaiting_approval`、`rejected`、`failed`、`interrupted`。**整体失败仍然关闭处理**：没有任何可交付内容时不交付。部分交付只在“一部分已独立审核通过、另一部分不可交付”时发生，并且必须由 Reviewer 显式给出分项结论；省略分项字段时仍按整包结论处理，系统不会从模糊拒绝中推断“部分通过”。

| 场景 | Reviewer 输出（关键字段） | 交付结果 |
|---|---|---|
| 练习连续两次无法生成（无效 JSON 或引用无法核对） | `approved=false, lesson_approved=true, practice_approved=false` | 仅讲解；`withheld_parts=["practice"]`，reason `practice_unavailable` |
| 练习返工一次后仍被拒绝 | `approved=false, lesson_approved=true, practice_approved=false` | 仅讲解；reason `practice_not_approved` |
| 个别题目被判定不可交付，其余可交付 | `practice_approved=true`、`dropped_exercises=[题号]`，`approved` 表示余下内容是否全部可交付 | 删除对应题号后交付讲解与其余练习；`withheld_exercise_numbers` 记录原始题号（页面标注为“原第 N 题”），reason `exercise_not_approved` |
| 讲解未通过 | `lesson_approved=false` | 不交付任何内容；练习依赖讲解，即使练习通过也不单独交付 |
| Reviewer 对未生成的产物给出通过 | 任意 | 视为契约冲突，失败关闭（`learning_package_quality_failed`） |

交付前的强制校验与边界：

- **证据**：每个交付单元（讲解、每道保留的练习）的 `source_ids` 必须属于本次检索证据；被删除或被拒绝的内容不会进入 SSE、持久化结果或教师审核草稿。
- **审核**：被交付的讲解或练习必须带有 Reviewer 的显式通过结论。`quality.reviewer_passed` 表示 Reviewer 是否通过“本次交付的内容”：练习被整体拒收的部分交付为 false；仅删除个别题目的部分交付在 Reviewer 通过余下内容时为 true。无论哪种情况都会带 `quality.partial_completion=true` 与 `quality.delivered_parts`，不会把部分结果报告成完整计划全部通过。Reviewer 的原始 `issues`/`suggested_query` 可能引用被拒收的题目文本，因此部分交付只把它们保留在内部审核状态，交付结果中的 `learning_package.review.issues` 清空、`suggested_query` 置空，并记录 `withheld_issue_count`/`withheld_suggested_query`。
- **教师审核与授权**：`require_approval=true` 时仍先返回 `review.required`；教师草稿（`result.approval`）携带 `partial_completion`，通过后状态为 `partially_completed`，拒绝后为 `rejected` 且不交付草稿。学生看不到草稿；跨用户、跨课程访问仍按既有授权规则拒绝。
- **SSE 与持久化**：终态事件仍为 `run.completed`，其 `status` 为 `partially_completed`，payload 包含 `partial_completion`、只含已交付部分的 `learning_package` 和 `budget`。同一份结果写入 `agent_runs`：`artifact_count` 为实际交付的讲解/练习单元数（0–2），`success_count` 只统计完整 `completed`，部分完成记为 0。GET 查询、`/events` 审计、断线后 `reconcile` 都复用该交付契约；`reconcile` 只读稳定检查点，不重新调用模型，也不能把部分结果升级为 `completed`。
- **检查点历史**：被拒收的中间产物可能保留在 LangGraph 的检查点历史中用于审计，但不会通过 API 交付，也不会写入 `agent_runs` 结果；需要更强删除保证的部署应另行制定检查点清理策略。
- **记忆边界**：会话记忆只召回 `completed` 运行；`partially_completed` 不作为后续问题的历史上下文（保守处理）。
- **页面**：显示“部分完成”，并明确说明未交付内容不会因为部分交付而被视为已验证。
- 这些测试验证执行与交付契约，不构成真实模型质量或事实支撑评测。

## API 示例

向 `POST /api/v2/learning-runs/stream` 发送以下 JSON，并使用已有登录服务取得的 Bearer token：

```json
{
  "message": "解释 RAG 的检索、生成与引用，并给我三道由浅入深的练习",
  "course_id": "artificial_intelligence",
  "session_id": "my-learning-session",
  "mode": "learning_package",
  "require_approval": false
}
```

省略 mode 或传 `answer` 使用普通问答，也能读取同一范围的会话历史。
返回 SSE 的 node.started / node.completed 是实际节点事件；retrieval.completed 只包含证据数量与耗时。observation.recorded 是 QWEN-231 新增的统一观察事件（状态 / 错误类 / 是否可重试 / 证据强度 / 引用支持度 / 有界计数），只做审计，不替代既有节点事件或错误码。
run.completed 中包含 learning_package（计划、讲解、练习、审核结果和返工次数）、budget、memory_run_ids；部分交付时另含 partial_completion，且 learning_package 只包含已交付内容。quality 中新增 claim_support（规则版交付前校验结果）与 delivery_observations（本次运行的观察投影）。
等待人工审核时只向请求者发送 review.required。教师使用任务编号查询草稿，再调用 `/{run_id}/resume` 提交 approved。
教师用 edited_answer 替换答案时，不再交付旧结构化学习包，最终 citations 置空；替换文本没有经过来源映射校验，不能继承旧引用。模型审核结果也不标记为对新文本的验证。替换部分交付草稿时同样清除 `partial_completion`，按人工替换内容处理。

## 队列执行（QWEN-301）

`POST /api/v2/learning-runs/enqueue` 与执行解耦：只持久化一个 `status="queued"` 的 Run（请求体与 `/stream` 相同），返回 `{run_id, status, session_id, workflow_version}`，**不**在请求内执行。后续由队列 Worker（`backend/app/agent_runtime/run_worker.py`）领取执行，走与 `/stream` 相同的图、租约心跳（`run_leases`）、超时（answer 60s / learning_package 180s）与交付契约；结果仍通过 `GET /api/v2/learning-runs/{run_id}` 查询，队列专属审计事件为 `run.queued` / `run.claimed` / `run.cancelled` / `run.queue_exhausted`（落在 `agent_checkpoints`，`GET /{run_id}/events` 可读）。

`POST /api/v2/learning-runs/{run_id}/cancel` 可取消队列来源且处于 `queued` / `running` 的 Run（409：`run_not_cancellable` / `run_not_queued`）；运行中取消会轮换执行租约，使原 Worker 的后续写入被拒绝，取消结果不被覆盖。

崩溃恢复语义是 **at-least-once**：Worker 进程死亡后其租约过期，任何 Worker 的领取扫描都会重领并重新执行（`MAX_ATTEMPTS=2`，超限判 `failed("run_queue_attempts_exhausted")`）；死亡执行的新写入被轮换后的 execution 租约隔离。**不声称 exactly-once**。`/stream` 同步端点保留原语义不变；`/resume`、`/continue`、`/reconcile` 对队列来源的 Run 同样适用、行为不变。

## 提示词注册表（QWEN-311）

Planner / Tutor（含检索决策）/ Practice / Reviewer 的主提示词与共用 system 框架不再写死在函数里：仓库根 `prompts/` 下每条一个 UTF-8 文本文件，`backend/app/agent_runtime/prompts.py` 的注册表为每条记录 name、version（`PROMPT_VERSION=learning-package-v2.9`，定义在该文件、`learning_package` re-export）、内容 sha256（对换行归一后的文本计算，检出形态 CRLF/LF 不敏感）、owner、description 与 changelog；`list_prompts()` 可列出全部条目做追溯，`verify_registry()` 给出每条的文件状态（ok/missing/mismatch）。

加载路径是"文件优先、内置回退"：文件存在且 sha256 与注册表一致才使用文件内容；文件缺失或被改动（哈希失配）时回退到与文件字节相同的内置默认，`render` 的返回值带 `source`（file/builtin）与 `version` 标识；未注册的 name 抛稳定错误 `prompt_not_registered`。QWEN-311 只是迁移、所有提示词文本字节不变，故 **未 bump `PROMPT_VERSION`**；后续修改任一提示词必须同步更新文件、内置默认、注册表哈希与 changelog，并按既有规则评估是否 bump。

QWEN-312 落地 Lead 的失配策略：**运行时回退保留，但每次回退记一条 warning 日志（只有 name 与 missing/mismatch 原因，绝不含提示词文本），`verify_registry()` 进入 CI `quality` job 作为硬门（任何 missing/mismatch 即失败）**；同卡交付回归 harness（`tests/a/test_prompt_regression.py`：聚合完整性 + 固定样例结构断言）与 A/B harness（`scripts/ab_prompts.py`：默认 dry-run、预算门禁、脱敏报告；`--execute` 仅 offline 脚本化对比，候选文本经 `prompts.apply_overrides` 进程内注入，生产恒为空）。

本批工作流版本为 `learning-workflows-v2.3`，提示词版本为 `learning-package-v2.9`（v2.9：重规划向 Planner 追加固定失效指令，属提示词变更；上一版 v2.8 是 QWEN-102 云端采集与本批契约评测所用版本）。旧版待审任务不自动迁移，恢复请求会要求重新发起，避免把旧图状态接入新图。

## V2 权限矩阵（QWEN-321）

`backend/app/api/v2/permission_matrix.py` 把全部 10 条 V2 路由（learning-runs 8 + admin 2）声明在一处：每条 `RoutePolicy` 记 method+path、允许角色（demo/student/teacher/admin）、认证要求（required/optional）、课程范围、Run 归属（creator / owner_or_reviewer / reviewer_only / none）与执行面可触达的工具 permission key（直接引用 `tool_catalog` 的 v2 工具键，不另造第二份工具真相）。

这是**声明层而非新执行路径**：运行时鉴权（`resolve_v2_principal` / `authorize_run_owner` / `authorize_reviewer` / 工具 deny-by-default）行为不变，已声明路由保持既有语义。`verify_route_policies(app)` 从 OpenAPI schema 枚举实际服务的 V2 路由与矩阵对比——**未声明路由、幽灵声明、非法字段（未知角色/auth/归属/越目录工具）都算问题**；该检查在 CI `quality` job 作为硬门步骤 `V2 permission matrix coverage`（非空即失败），防止新路由未经权限评审就上线。不改变任何既有授权行为：只有"未声明"才会被 CI 拒绝。

## 配额与速率限制（QWEN-324）

`backend/app/services/quota.py` 为 `/stream` 与 `/enqueue` 的**新 Run 创建**提供三道滑动窗口：每用户每分钟请求数（默认 60）、每用户×课程每小时 token（默认 500000，结算时从 `result.budget` 累计）、每用户每天可计量费用 CNY（默认 5.0，只有 `cost.status=="estimated"` 的有限金额累计）。超限返回稳定 **429 `quota_exceeded`** 带 `Retry-After`；只挡创建——`/resume`、`/continue`、读面与管理面不受限，未超限用户行为零改变。基线常量可经 `QUOTA_*` 环境变量覆盖；**启用为 opt-in**（与权限矩阵运行时检查同一精神）：`QUOTA_ENABLED=true` 显式开启才生效，默认所有面行为零改变；QWEN-324b 起 `.env.production.example`/`.env.enterprise.example` 与 production compose 默认启用，配额禁用时启动日志打一行 warning（无敏感信息）。窗口按条目过期连续滑动；provider 未返回的费用记为 unknown run——**unknown 不当 0 也不当免费**：窗口含 unknown 时费用维度暂缓判定（运行侧另有 eval_cost_guard 预留门禁兜底）。存储为进程内滑动窗口（线程安全、零迁移），多进程部署下为每进程口径，跨进程一致性归 341 观测面；`quota.snapshot()` 提供只读占用视图。demo（未认证）模式的配额键取自请求体，不构成安全边界。

## 细粒度引用契约

检索前的确定性 Guard（`backend/app/services/safety/run_guard.py`）按短语类别拦截 prompt 注入、数据外泄、越权写入与危险操作，命中即走 `safe_decline` 安全降级（零模型/零工具调用）。QWEN-322 红队套件（`tests/a/test_prompt_injection_redteam.py`，25 项）覆盖用户输入/检索文档/工具参数/部分完成内容四类注入面，并推动一处最小加固：`decide` 归一化现在先做 NFKC 折叠（全角拉丁还原为半角）并剔除 Unicode 格式字符（零宽空格/连接符、BOM、软连字符——防止关键词被隐形字符切分绕过），prompt_injection 类 pattern 补"无视"同义词。注入式检索文档仍是数据：受 2000 字截断约束、只能被引用而不能新增工具或改写 `source_ids`（伪造引用 fail-closed）。

如果模型执行或审核已写入检查点，但 Run 写库失败，授权教师可调用 `POST /api/v2/learning-runs/{run_id}/reconcile` 或使用页面恢复按钮。failed/interrupted 或执行租约已过期的任务可检查修复；有效租约和未完成节点不能抢占。此操作只读取稳定检查点，不重新调用模型；待审仍需审核。页面也支持替换答案及停止本次请求，详见 [Run 状态修复说明](RUN_RECONCILIATION.md)。

- `learning_package.lesson` 和每个 `learning_package.exercises[]` 都保留模型声明的 `source_ids`，并由服务端增加 `citations`。对象格式为 `{"chunk_id": "c1", "source": "chapter.md", "label": "chapter.md", "score": 0}`，元数据来自实际检索证据，不接受模型自行编造。当前学习包证据未保留检索分数，`score: 0` 是缺省值，不代表相关性评分。
- 每个内容单元的引用按其 `source_ids` 首次出现的顺序去重；最终 `run.completed.citations` 按讲解、各题顺序取实际使用来源的并集，以 `chunk_id` 去重。同一文档的不同分块仍分别保留。
- 未被任何内容单元使用的证据不会进入引用列表或服务端生成的参考资料。完整 `evidence` 仍用于检索审计，与“实际引用”分开。
- 页面在讲解下方和每道题下方分别展示来源及分块 ID；审核草稿的文本也逐项标注依据，教师审核列表同样只包含已使用的来源。持久化结果与 SSE 交付遵循相同契约。
- Reviewer 返工后只引用最终产物使用的来源。此校验确认来源身份及映射关系，不证明句子与来源之间的语义蕴含；讲解目前为单个内容单元，尚未拆成逐句引用。
- 交付前另有一次**规则版** claim-support 二次校验（`claim_check` 节点，规则实现见 `backend/app/evaluation/claim_support.py`）：逐内容单元检查引用 ID 是否指向本次检索证据，并在证据文本足够长（≥40 字符）时用字符二元组重叠判断是否存在词面支持；不支持则按既有稳定错误码失败（`learning_package_invalid_citation` / `learning_package_quality_failed`），不调用额外模型、不新增重试循环。该检查是启发式下界，不证明语义蕴含，也不替代人工审核。

## 验证与尚未完成的内容

自动化用可控模型输出、临时 SQLite 和真实 LangGraph 测试模型决策循环、依赖传递、来源约束、记忆隔离和审核恢复；前端测试拆分 UTF-8、CRLF、提前 EOF 和终止事件。
这些测试验证执行机制，不代表真实模型的学习包质量。本次只做离线验证，不读取或使用 `.env.enterprise` 密钥。
旧版 66 条在线基线（历史）的 64/66、Recall@5 95.83%、引用完整性 100% 不能作为新版成绩。新版 76 条 Golden Set 与学习包待完整 Docker + PostgreSQL + 云端模型验收；76 条当前覆盖普通问答、拒答和内容人审。学习包已另建 [24 条用例、离线采集/故障注入执行器、评测器及人工审查契约](../evals/LEARNING_PACKAGE_EVAL.md)，并通过 24 条模拟模型的预期行为验证。另已完成 [7 项真实 PostgreSQL 跨进程检查点恢复测试](POSTGRES_CHECKPOINT_ACCEPTANCE.md)，验证检查点提交后应用进程退出的审核恢复；模型与检索仍是桩，不等同完整 API 或云端质量验收。在线验收须先取得用户授权，并会产生模型及 Embedding 调用费用。
后续已完成 5 项真实 PostgreSQL API 故障修复（身份/模型/检索为桩），并独立完成 SQLite/PostgreSQL 真实登录跨进程及课程授权撤销验证，见 [登录与课程授权](AUTH_AND_COURSE_ACCESS.md)。这些结果不合并宣称为云端端到端验收。
2026-10-18 另在一次性隔离容器（本机已有 PostgreSQL 16 + pgvector、Redis 7 镜像，未拉取）上验证：Alembic `upgrade head → downgrade base → upgrade head` 通过，企业合同测试子集 353 passed；新增真实 PostgreSQL 跨进程测试验证部分完成学习包在教师审核后仍保持 `partially_completed`、仅交付 2 道练习且恢复时不重跑模型/检索（`tests/a/test_learning_package_partial_postgres.py`）。这不等于生产全栈、TLS、Phoenix 或云端质量验收。PostgreSQL 服务自身恢复、原生工具协议适配、真实 token 统计、可检索长期经验和任意 DAG 重规划仍是后续工作。
