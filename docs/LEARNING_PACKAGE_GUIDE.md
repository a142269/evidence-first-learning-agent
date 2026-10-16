# V2 学习包：规划、受限 ReAct-style 检索决策循环与记忆

本批把三项能力接入同一条真实后端链路，并增加页面 `/learning-package`，从「Agent 编排」页面进入。
原有 V1 聊天页面保持原链路。新页面可以选择「课程问答」或「讲解 + 三道练习」，使用登录凭据调用 V2。

## 实际执行流程

1. 校验登录用户与课程权限，读取本用户、本课程、本会话最近三次已完成结果作为上下文。
2. Planner 输出 JSON 任务计划：一个 Tutor 步骤、一个依赖该步骤的 Practice 步骤。验证角色、ID、依赖关系，拒绝循环、未知依赖或未知角色。
3. Tutor 执行受限 ReAct-style 检索决策循环，只能输出 `search_course` 或 `finish`，最多检索 3 次。每次检索结果作为 observation 回到下一次模型决策；可以改写查询再检索。工具课程范围由服务端身份校验结果注入。这不是开放式多工具 Agent。
4. Tutor 依据证据生成讲解；Practice 读取该讲解作为依赖产物，生成三道带答案、解析及来源 ID 的练习。
5. Reviewer 检查目标覆盖、讲解、题目与证据。首次拒绝触发讲解与练习全部返工，第二次拒绝终止并报告失败。
6. 可选教师审核：待审核草稿不会发送给学生，也不会写入可召回的会话记忆。通过后交付结果，拒绝后不交付草稿。

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
| 逻辑模型调用 | 最多 12 次 |
| 累计模型输入 | 最多 100000 字符 |
| 每次模型输出请求上限 | 2048 tokens |
| 学习包流式执行超时 | 180 秒 |

重复查询会停止检索；有证据时继续生成，无证据时失败。无证据、无效输出、未知工具、无效引用或二次质量失败都不会返回成功学习包。
返回的 `budget.output_token_limit` 是累计请求输出上限，不是实际消耗；`model_calls` 是编排层调用数，不统计底层 HTTP 重试。真实 token usage 与费用统计仍待接入。
Reviewer 是一次模型质量检查，不是事实正确性的证明；引用检查验证来源 ID 是否属于检索证据，不冒充语义忠实度评估。

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
返回 SSE 的 node.started / node.completed 是实际节点事件；retrieval.completed 只包含证据数量与耗时。
run.completed 中包含 learning_package（计划、讲解、练习、审核结果和返工次数）、budget、memory_run_ids。
等待人工审核时只向请求者发送 review.required。教师使用任务编号查询草稿，再调用 `/{run_id}/resume` 提交 approved。
教师用 edited_answer 替换答案时，不再交付旧结构化学习包，最终 citations 置空；替换文本没有经过来源映射校验，不能继承旧引用。模型审核结果也不标记为对新文本的验证。

本批工作流版本为 `learning-workflows-v2.2`。旧版待审任务不自动迁移，恢复请求会要求重新发起，避免把旧图状态接入新图。

## 细粒度引用契约

如果模型执行或审核已写入检查点，但 Run 写库失败，授权教师可调用 `POST /api/v2/learning-runs/{run_id}/reconcile` 或使用页面恢复按钮。failed/interrupted 或执行租约已过期的任务可检查修复；有效租约和未完成节点不能抢占。此操作只读取稳定检查点，不重新调用模型；待审仍需审核。页面也支持替换答案及停止本次请求，详见 [Run 状态修复说明](RUN_RECONCILIATION.md)。

- `learning_package.lesson` 和每个 `learning_package.exercises[]` 都保留模型声明的 `source_ids`，并由服务端增加 `citations`。对象格式为 `{"chunk_id": "c1", "source": "chapter.md", "label": "chapter.md", "score": 0}`，元数据来自实际检索证据，不接受模型自行编造。当前学习包证据未保留检索分数，`score: 0` 是缺省值，不代表相关性评分。
- 每个内容单元的引用按其 `source_ids` 首次出现的顺序去重；最终 `run.completed.citations` 按讲解、各题顺序取实际使用来源的并集，以 `chunk_id` 去重。同一文档的不同分块仍分别保留。
- 未被任何内容单元使用的证据不会进入引用列表或服务端生成的参考资料。完整 `evidence` 仍用于检索审计，与“实际引用”分开。
- 页面在讲解下方和每道题下方分别展示来源及分块 ID；审核草稿的文本也逐项标注依据，教师审核列表同样只包含已使用的来源。持久化结果与 SSE 交付遵循相同契约。
- Reviewer 返工后只引用最终产物使用的来源。此校验确认来源身份及映射关系，不证明句子与来源之间的语义蕴含；讲解目前为单个内容单元，尚未拆成逐句引用。

## 验证与尚未完成的内容

自动化用可控模型输出、临时 SQLite 和真实 LangGraph 测试模型决策循环、依赖传递、来源约束、记忆隔离和审核恢复；前端测试拆分 UTF-8、CRLF、提前 EOF 和终止事件。
这些测试验证执行机制，不代表真实模型的学习包质量。本次只做离线验证，不读取或使用 `.env.enterprise` 密钥。
旧版 66 条在线基线（历史）的 64/66、Recall@5 95.83%、引用完整性 100% 不能作为新版成绩。新版 76 条 Golden Set 与学习包待完整 Docker + PostgreSQL + 云端模型验收；76 条当前覆盖普通问答、拒答和内容人审。学习包已另建 [24 条用例、离线采集/故障注入执行器、评测器及人工审查契约](../evals/LEARNING_PACKAGE_EVAL.md)，并通过 24 条模拟模型的预期行为验证。另已完成 [7 项真实 PostgreSQL 跨进程检查点恢复测试](POSTGRES_CHECKPOINT_ACCEPTANCE.md)，验证检查点提交后应用进程退出的审核恢复；模型与检索仍是桩，不等同完整 API 或云端质量验收。在线验收须先取得用户授权，并会产生模型及 Embedding 调用费用。
后续已完成 5 项真实 PostgreSQL API 故障修复（身份/模型/检索为桩），并独立完成 SQLite/PostgreSQL 真实登录跨进程及课程授权撤销验证，见 [登录与课程授权](AUTH_AND_COURSE_ACCESS.md)。这些结果不合并宣称为云端端到端验收。PostgreSQL 服务自身恢复、原生工具协议适配、真实 token 统计、可检索长期经验和任意 DAG 重规划仍是后续工作。
