# 学习包离线评测 1.0

更新：2026-10-13。该评测独立于旧版 66 条历史基线和新版 76 条普通问答数据集。
已交付 **24 条版本化用例、离线运行采集/故障注入执行器及回放评测器**。24 条均已使用模拟模型通过真实 API/Graph 执行并校验预期契约，没有执行真实模型质量验收，也没有产生新的云端质量指标。

## 用例与固定划分

数据文件：`evals/learning_package_cases_v1.jsonl`。

| 类别 | 总数 | 开发集 | 固定留出集 | 内容 |
|---|---:|---:|---:|---|
| normal | 8 | 4 | 4 | 课程讲解、三道递进练习 |
| evidence_revision | 8 | 4 | 4 | 跨章节、未使用证据、补检索、返工、同来源不同分块 |
| boundary_failure | 8 | 4 | 4 | 空证据、伪造引用、提示注入、待审、格式错误、二次拒绝、写操作、预算耗尽 |

默认只评开发集；显式 `--split holdout` 或 `--split all` 才统计留出集。公开仓库中的固定留出集并非隐藏测试集，不应据其逐例结果反复调整提示词。修改题目、来源、rubric 或划分后报告签名会改变，必须建立新的评测版本记录，不能挪动失败样本提升通过率。

两步计划仍为 Tutor → Practice。受限 ReAct-style 检索决策循环只允许 `search_course` / `finish`，最多 3 次检索，不支持开放式多工具执行或任意 DAG。

## 采集输入与故障条件

回放脚本 `evaluate_learning_package.py` 只读取已有 JSONL，不导入应用配置、不读取 `.env`、不登录、不启动 Docker，也不调用模型。采集脚本 `collect_learning_package.py` 在独立进程中装配无密钥配置、模拟模型和检索，执行现有 V2 API/Graph；不会读取 `.env` 或连接生产服务。
每行格式如下；`result` 保存原始终态 SSE 的 data，`events` 保留实际事件顺序：

```json
{"id":"lp-boundary-001","scenario":"no_evidence","events":["run.started","run.failed"],"result":{"run_id":"EXAMPLE_ONLY","error":"learning_package_no_evidence"}}
```

这个示例只是格式说明，不是已执行的验收结果。成功用例必须保留完整 answer、learning_package、evidence、citations、budget、status。待审用例采集学生收到的 `review.required`，不能把教师查询到的合法草稿当作学生响应。

`scenario=standard` 可以在授权后的真实服务上采集，创建请求必须显式传 `mode=learning_package`，并使用用例中的 question、course_id、require_approval；每例使用独立 session_id，避免会话污染。
其他 scenario 需要可控检索或模型桩，不应只把问题提交给云端并期待它自然触发故障：

| scenario | 必须准备的条件 |
|---|---|
| unused_evidence | 检索额外返回未被最终产物引用的证据 |
| empty_then_evidence | 首轮检索为空，后续检索提供证据 |
| review_once | 首次 Reviewer 拒绝，修订后通过 |
| same_source_chunks | 同一 source 的多个互补 chunk_id 被使用 |
| review_changes_sources | Reviewer 要求修订，最终产物换用证据 |
| repeated_search | 已有证据后再次选择相同查询 |
| no_evidence | 空检索结果后选择 finish |
| fabricated_citation | 注入未知 source_ids |
| invalid_model_output | 注入不满足 Schema 的模型输出 |
| review_twice | 两次 Reviewer 均拒绝 |
| model_budget_exhausted | 注入不足的剩余模型预算 |

评测器检查最终可观测约束，但 scenario 标签和预算计数不能证明故障注入确实执行过。离线执行器 `backend/app/evaluation/package_collection.py` 会记录实际模型桩调用、检索返回的 chunk_id、Reviewer 决定、Practice 收到的上游依赖和反馈，核对脚本消耗及数据库终态。相关回归位于 `tests/a/test_learning_package_collection.py` 与 `tests/a/test_learning_package.py`。这些记录用于审查离线注入是否执行，不是经过认证的云端轨迹；仅修改预测中的 scenario 字段不算故障演练。

## 离线运行采集

在独立终端进程运行，不将采集器导入正在服务的应用。采集器会临时替换进程级依赖，不支持并行采集；每例使用独立 session_id、run_id 和内存 Checkpointer，运行记录写入输出目录内独立 SQLite。

```powershell
# 默认只跑 12 条开发集，必须指定尚不存在的输出目录
python scripts/collect_learning_package.py --output-dir output/package-dev-new

# 显式跑全部 24 条离线契约用例
python scripts/collect_learning_package.py --split all --output-dir output/package-all-new

# 保存的预测可再次独立回放；不允许把 synthetic_asgi 改标为 recorded
python scripts/evaluate_learning_package.py --predictions output/package-all-new/predictions.jsonl --split all --output output/package-all-new/replayed-report.json --enforce-contracts
```

输出目录必须是新路径，已有目录一律拒绝覆盖；`--case-id` 可选定单例，但不能隐式绕过默认开发集划分。没有在线参数、服务 URL 或凭据参数；禁止通过此入口调用付费模型。

| 本地产物 | 内容 |
|---|---|
| predictions.jsonl | 每例完成即追加并 flush；含原始 SSE 帧、终态、注入轨迹、节点审计、collection 检查结果 |
| runs.sqlite3 | 独立 Agent Run、检查点审计和检索日志，不修改项目业务数据库 |
| report.json | 对实际采集结果执行契约评分，固定 synthetic / synthetic_asgi 标记 |
| review-template.jsonl | 空白人工审查格式，不能将测试桩填充内容作为真实模型质量成绩 |

采集器只替换模型、检索、画像、身份解析、检查点后端和数据库连接；路由、权限范围校验、Graph 分支、预算控制、SSE 生命周期与运行持久化仍执行项目代码。身份为合成学生，不证明真实登录有效性。ASGI 在进程内缓冲响应，不测网络流式时延或浏览器表现。
检索桩依据用例来源标注提供模拟片段，模型桩提供明确标注为“离线测试桩”的内容；**既不测试召回相关性，也不测试知识正确性**。collection 任一检查失败会使该例契约失败，CLI 返回 1；初始化、依赖、路径或选例错误返回 2，已写入的逐例预测保留用于排查。

## 运行方法

以下命令从项目根目录执行，不产生模型费用。路径中的 predictions.jsonl 指你已经采集并整理的文件，本仓库不附带伪装成真实结果的默认预测文件。

```powershell
# 仅校验全部用例格式，不执行评测
python scripts/evaluate_learning_package.py --validate-only --split all

# 回放开发集；首次生成空白人工审查表，文件存在则拒绝覆盖
python scripts/evaluate_learning_package.py --predictions output/package/predictions.jsonl --prediction-kind synthetic --output output/package/dev-contracts.json --review-template output/package/dev-review.jsonl --enforce-contracts

# 人工填写审查表后，对同一批已记录输出进行质量复核
python scripts/evaluate_learning_package.py --predictions output/package/recorded-predictions.jsonl --prediction-kind recorded --reviews output/package/recorded-review.jsonl --output output/package/dev-reviewed.json --enforce-contracts --enforce-human-review
```

先对真实记录运行一次带 `--review-template` 的命令，再填写生成的记录，最后才使用第三条复核命令。
`synthetic` 是默认值，表示测试桩/合成预测；`recorded` 仅表示用户声明这些数据来自已保存的运行，不能自动认证它是云端输出，也不会让离线回放变成新的在线验收。报告始终标记 `evaluation_mode=offline_replay`。
固定留出集复核显式添加 `--split holdout`；仅验证数据文件不代表已运行留出集。报告、预测及审查表只存放本地 output/reports，不提交仓库。

## 指标口径

- `contract_pass_rate`：预期行为的契约通过率。成功用例验证两步依赖、讲解、三道题、每项引用、实际引用并集、Reviewer 状态和上限预算；预期失败/待审/拒绝用例则验证相应事件、错误码及受保护内容隔离。正确拒绝也可算契约通过，不能称为“成功生成学习包”。
- `expected_source_coverage`：累积多轮检索 evidence 对标注来源的覆盖比例。它不是有序 Top-5，不与旧版 Recall@5 比较。
- `human_review_coverage`：需要生成学习包的用例中，拥有完整且指纹匹配的人工审查记录的比例。缺失或过期审查不能自动通过。
- `learning_quality_pass_rate`：只有所有预期成功用例均有有效人工审查时才给出；否则为 null。该值要求契约通过且四项人工标准全部通过。它是所回放数据的质量记录，不自动代表在线发布验收。
- `recorded_p50_latency_ms` / `recorded_p95_latency_ms`：仅对 recorded 输入统计其报告耗时。合成输入不报告性能数字。原始 latency_ms 可能包含人工等待，不应改称活动执行耗时；实际 token 用量及费用尚未测量。

报告携带 evaluator_version、所选用例的 dataset_signature、split、prediction_kind、逐例检查结果、分类计数及原始输入。它不能与旧版 66 条或新版 76 条问答报告直接比较；本脚本不提供跨报告基线比较功能。
`--enforce-contracts` 在任意契约失败时退出 1。`--enforce-human-review` 要求 recorded 输入且所有预期成功用例有有效人工审查并全部通过，作为保守的复核门禁，不等同原计划的最终发布门槛。缺失预测计入失败，重复 ID、未知 ID、错误格式和覆盖已有文件返回 2。

## 人工审查标准

审查表包含 case id、prediction_fingerprint、reviewer、notes、用例 rubric，以及四个初始为 null 的判断项：

1. `facts_supported`：讲解与练习解析的事实得到引用证据支持，无严重事实错误。
2. `exercise_answers_correct`：三道题答案和解析正确，必要条件充分。
3. `goal_covered`：满足题目提出的讲解范围和练习要求。
4. `difficulty_progression`：练习有识记、理解或应用的合理递进。

审查人查看原始输出、原文证据及用例 rubric 后填写真实姓名/标识、布尔值和问题记录。fingerprint 绑定题目、rubric、来源和该次完整预测；内容变化后必须重新生成审查表。此绑定可防止误用旧结论，不是审查者身份认证或加密签名。
模型 Reviewer 的 approved 仅检查工作流是否完成审核，不得自动复制成人工评分。固定留出集应按原计划独立盲审。

## 本批验证与下一步

最新定向离线测试：采集器 35 项、评测器 51 项、学习包工作流 27 项，共 113 项通过；使用测试桩、SQLite 和内存 Checkpointer。另执行全部 24 条离线用例并独立回放，24 条均满足预期契约：16 条完成模拟学习包、5 条预期失败、2 条安全拒绝、1 条待审。所有真实内容质量指标仍为 null。
本地产物在 `output/package-collection-20261013/`，不提交仓库。24 条离线契约通过不能称为 24 条真实学习任务质量验收通过，合成留出样例运行也不替代真实模型固定留出集盲审。
后续已另行完成 [7 项真实 PostgreSQL 跨进程检查点恢复测试](../docs/POSTGRES_CHECKPOINT_ACCEPTANCE.md)，覆盖检查点提交后应用进程退出、新进程通过/修改/拒绝审核；模型与检索为桩。仍需完整 API 与数据库一致性验收、经授权的云端采集及人工质量审查。真实云端调用需另行获得用户授权，会产生对话模型与 Embedding 费用。
