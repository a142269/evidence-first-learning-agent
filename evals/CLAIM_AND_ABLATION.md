# 证据复核与多 Agent 对照计划

## 逐条事实的双人复核

`scripts/evaluate_claim_support.py` 只汇总人工判断，不调用模型，也不读取密钥。逐条拆分输出中的事实陈述；两位评审独立阅读原始输出和对应证据，分别标注支持性、严重事实错误和每条引用的相关性。评审应记录匿名标识，不要把账户、密钥或课程私有材料提交到仓库。

输入 JSON 示例（仅示范格式，数值不是实验结果）：

```json
{
  "evidence_ids": ["chunk-12"],
  "claims": [{
    "claim": "RRF 根据不同检索结果的倒数排名融合结果。",
    "source_ids": ["chunk-12"],
    "reviews": [
      {"reviewer": "reviewer-a", "supported": true, "severe_error": false, "citation_relevance": {"chunk-12": true}},
      {"reviewer": "reviewer-b", "supported": true, "severe_error": false, "citation_relevance": {"chunk-12": true}}
    ]
  }]
}
```

```bash
python scripts/evaluate_claim_support.py output/claim-reviews.json --output output/claim-summary.json
```

每条 claim 必须有两位不同评审；结果不一致或缺少评分时，支持率、引用精确率、未支持条数和严重错误数为 `null`。存在分歧时保留两份原始记录，由第三位独立评审在该 claim 中填写 `adjudication`，格式与单条 review 相同。仅在已有两条不同评审且存在分歧时接受裁决；裁决用于最终指标，原始分歧仍计入 `disagreement_count`。程序不认证身份、不证明独立性，也不能验证 claim 拆分是否完整；这些由评测流程保证。

例如，若两名评审对某条 claim 有分歧，在该 claim 的 JSON 对象中另加：

```json
"adjudication": {"reviewer": "reviewer-c", "supported": true, "severe_error": false, "citation_relevance": {"chunk-12": true}}
```

- `citation_validity`：所引用 ID 存在于证据集合的比例。
- `citation_coverage`：带有至少一个引用的 claim 比例，不要求该引用有效或相关。
- `citation_precision`：全部引用中，ID 存在且最终判断为相关的比例。
- `claim_support_rate`：最终判断为被证据支持的 claim 占全部 claim 的比例。
- `unsupported_claim_count`、`severe_error_count`：最终判断的数量。没有引用时引用精确率为 `null`。

这是离线评测工具，不改变在线生成结果，也不会将 `faithfulness_checked` 标为真。支持性并不由引用存在或文本相似度自动推断。

## 固定证据对照实验

`scripts/collect_ablation.py` 在离线评测环境调用真实模型：先冻结各题检索证据，再运行单 Agent、无 Reviewer 多角色、带 Reviewer 多角色三个方案。三组均限定最多请求 8192 个输出 token；单 Agent 一次请求，多角色最多八次、每次 1024。模型输入、角色提示和单次额度不同，因而这是受控的方案比较，并非完全等同线上端到端流程：没有身份工具、人工审批或动态补充检索。向量检索不可用时，使用现有检索器的回退结果；请核实其实际内容。检索失败计入各组失败。输出含原始课程材料，必须保存在被忽略的 `output/` 下，禁止直接上传。

采集可通过同一命令增加 `--resume` 继续；校验数据集、模型、运行器和证据指纹，已记录结果不重跑。中断发生在模型调用与落盘之间时无法保证不重复计费。`scripts/prepare_ablation_review.py --run-dir output/<运行目录>` 为完成的留出集生成两份盲评材料及单独映射；生成前逐条校验证据快照和运行记录中的摘要，发现不匹配时拒绝生成。评分必须由两名不同的人独立完成，程序不能证明独立性。当前任务没有提供学习者画像，不能据此得出画像适配结论。

评审分别填写 `reviewer-a.json` 和 `reviewer-b.json` 的 `scores`，每个判断使用 true、false 或 null（未知／不适用），并可在 notes 记录原因。完成后执行 `python scripts/merge_ablation_reviews.py --run-dir output/<运行目录> --reviewer-a <匿名标识1> --reviewer-b <匿名标识2>`，再对生成的 `reviewed-runs.jsonl` 汇总。两份原始盲评及分歧予以保留；不同意见需要另行裁决，不能当作一致。空评分不会自动推测。

填写两份评分后，执行 `python scripts/prepare_ablation_adjudication.py --run-dir output/<运行目录>`，生成 `adjudication-packet.json`，仅包含有分歧的盲评条目、分歧指标、证据和空评分，不显示方案名称或前两位评审的判断。第三位独立评审在其中填写五项 `scores`，未知填 null。执行同一合并命令并增加 `--adjudications adjudication-packet.json --adjudicator <第三人匿名标识>`，生成新的 `adjudicated-runs.jsonl`，再用汇总脚本读取该文件。程序只用裁决解决两位评审都已评分但意见不同的指标；缺失评分不能由裁决补造。`review_disagreement_count` 保留每组出现过分歧的任务数。

比较单 Agent、Planner＋Tutor＋Practice（无 Reviewer）和完整工作流；固定模型版本、知识库快照、任务、评分标准、最大 token/费用与超时。预先记录任务顺序、运行次数、参数、运行失败、实际 token、每次请求单价及价格日期。缺失用量或账单数据记录为 unknown，不能当作零成本。对照组要真正执行不同流程，不能通过修改标签模拟。

现有 `learning_package_cases_v1.jsonl` 的 24 条包含预期拒绝、待审和需要模型或检索桩的故障场景；它不是 24 条可直接提交给真实模型的普通生成题。`ablation_tasks_v1.jsonl` 提供另行拟定的 24 条学习任务（开发集和留出集各 12 条）；这是未经人工审核及预跑的数据集，不能视为已有实验结果。安全和故障测试仍单独执行。固定 12 条留出任务由至少两名评审独立盲评，记录分歧并裁决；评估事实支撑、练习正确性、目标覆盖、难度递进和画像适配。

报告应按组列出任务成功率、质量通过率、事实支撑率、练习答案正确率、目标覆盖率、Reviewer 修订成功率、平均模型调用数、P50/P95 延迟、单任务费用和无效工具调用数，并注明分母和缺失项。无 Reviewer 的修订成功率应标记不适用，不能计为零。公开报告必须先脱敏并核对模型密钥；未经实际实验和人工评分不得填写结果或推断优劣。

`scripts/summarize_ablation.py` 可汇总已有记录。输入 JSONL 每行包括 `case_id`、`arm`（`single`、`without_reviewer`、`full`）、`completed`、`evidence_sha256`、`config`（`model`、`knowledge_snapshot`、`max_output_tokens`、`max_cost_cny`）、`latency_ms`、`model_calls`、`cost_cny`、`invalid_tool_calls`、`reviews`。未知数值用 null；每位 review 含 `reviewer` 和五个字段 `facts_supported`、`exercise_answers_correct`、`goal_covered`、`difficulty_progression`、`profile_fit`，各值为布尔值或 null。每组缺案例、对应评分缺失或分歧未裁决时，相关指标为 null；失败案例计入任务和质量的分母。Reviewer 修订成功率以 Reviewer 首次拒绝的运行数为分母；没有拒绝案例时为 null。本汇总器不验证评审独立性，也不计算逐 claim 支撑率。

```bash
python scripts/summarize_ablation.py --split holdout --runs output/ablation-runs.jsonl --output output/ablation-summary.json
```
