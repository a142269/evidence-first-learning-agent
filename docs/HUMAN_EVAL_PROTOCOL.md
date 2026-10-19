# 人工盲评协议（QWEN-101 工具包）

> 适用工具：`scripts/human_eval/`（五个入口）+ `backend/app/evaluation/human_agreement.py`（纯统计与校验）。
> 设计依据：`docs/HUMAN_EVAL_DESIGN_2026-10-19.md` 与 Lead 2026-10-19 的六项裁决（`docs/QWEN_LEAD_DIALOGUE.md` §4）。
> 证据等级：**offline**。本工具不调用任何模型、不读 `.env`、不产生付费调用，也**不代填任何评分**。

## 0. 目的与硬边界

- 目的：让**两位真人**独立盲评同一批学习包，工具负责随机化、防串、校验、κ 一致性与分歧清单，并把统计结果导出为可发布的脱敏摘要。
- 工具在任何代码路径上都不产生 `true`/`false`：生成时 `scores` 五个指标恒为 `null`（`common.py:180`），导入时只搬运真人填的值，统计时缺值即 `null`，**绝不把 `null` 当 `false`，也不把未定义的 κ 写成 0**。
- 工具不认证评审身份、不证明独立性（`evals/CLAIM_AND_ABLATION.md:27` 同口径）；独立性由本协议约束流程，不由代码担保。

## 1. 角色

| 角色 | 数量 | 要求 |
|---|---|---|
| 评审 A / 评审 B | 2 | 互相独立，不得交换题序、答案或进度；使用匿名标识（如 `rev-1`/`rev-2`），不得填真实姓名以外的敏感信息 |
| 第三裁决人 | 0 或 1 | 只在 A/B 有分歧时介入，**必须与两位评审都不同**（`--adjudicator` 与任一评审同名即 `REVIEWER_IDS_INVALID`） |
| 工具操作员 | 1 | 跑命令、保管 `output/` 材料，不参与评分 |

## 2. 前置材料

运行目录必须在 `output/` 下（`OUTPUT_OUTSIDE_PRIVATE_ROOT` 强制），并已存在：

- `runs.jsonl`：`scripts/collect_ablation.py` 产出的三臂运行记录，**该 split 必须全部 `completed`**（否则 `RUNS_INCOMPLETE`）；
- `evidence.jsonl`：逐题冻结的证据快照，自带 `sha256`，工具会双向复核（`EVIDENCE_TAMPERED` / `EVIDENCE_MISSING`）；
- 数据集：`evals/ablation_tasks_v1.jsonl`（`--split {dev,holdout}` 选子集；当前 holdout 12 题 × 3 臂 = 36 run，实际可评 item 数以 manifest 为准）。

## 3. 流程与命令

```bash
# 1) 生成两份盲评包（每评审独立置换、盲 id 命名空间 a-NNN / b-NNN）
python -m scripts.human_eval.prepare_packets --run-dir output/human-eval-2026-10-19 --split holdout

# 2) 生成后自检（只读，永不落文件）
python -m scripts.human_eval.validate_packets --run-dir output/human-eval-2026-10-19

# 3) 真人独立填写（工具不参与）：A 只碰 human-eval-packet-a.json，B 只碰 -b.json
#    每格填 true / false / null，notes 可选。填完再校验一次：
python -m scripts.human_eval.validate_packets --run-dir output/human-eval-2026-10-19 --require-reviewed

# 4) 导入合并（校验通过才写产物；产出分歧裁决包）
python -m scripts.human_eval.import_reviews --run-dir output/human-eval-2026-10-19 \
  --reviewer-a rev-1 --reviewer-b rev-2

# 5) 第三位真人只裁决分歧项，把结果写成 output/<运行目录>/adjudications.json
#    （格式见 §7），然后带裁决重新导入：
python -m scripts.human_eval.import_reviews --run-dir output/human-eval-2026-10-19 \
  --reviewer-a rev-1 --reviewer-b rev-2 --adjudications adjudications.json --adjudicator rev-3

# 6) 计算一致性与分歧（--seed 会写进报告，bootstrap 区间可复现）
python -m scripts.human_eval.agreement_report --run-dir output/human-eval-2026-10-19 --seed 20261019 \
  --replicates 2000

# 7) 导出脱敏发布物
python -m scripts.human_eval.export_summary --run-dir output/human-eval-2026-10-19
```

失败行为统一为：**先校验后落盘**，任一校验不过即 `exit 2` 并打印 `错误码: 固定文案`，**不产出任何文件**（与 `tests/a/test_ablation_review_packets.py:36-42` 的可观察行为一致）。成功时 stdout 只有一行机器可读 JSON。所有写操作使用 `open("x")`，已存在的产物不会被覆盖（`ARTEFACT_EXISTS`）。

## 4. 材料、可见性与产物

| 文件 | 可见性 | 内容 |
|---|---|---|
| `human-eval-packet-a.json` / `-b.json` | 发给对应评审 | `blind_id`、`question`、`evidence`、`package`、`scores{5}`、`notes`；**不含** `case_id`/`arm`/参考答案 |
| `human-eval-manifest.json` | 私有 | 生成器版本、split、item 数、数据集路径、三个输入摘要、每评审 `permutation_sha256` 与 `packet_sha256`、`created_at` |
| `human-eval-mapping.json` | 私有（严禁发给评审） | 按评审分列的 `blind_id → case_id/arm` 与三类摘要 |
| `human-eval-aligned-items.json` | 私有 | 逐 (case, arm) 的 A/B 判断对齐结果 |
| `human-eval-adjudication-packet.json` | 发给裁决人 | **只含分歧项**，隐去臂、case 与前两位判断 |
| `human-eval-reviewed-runs.jsonl` / `-adjudicated-runs.jsonl` | 私有 | 带 `reviews`（可选 `adjudication`）的运行记录 |
| `human-eval-agreement-report.json` | 私有（含 `case_id`/`arm`） | 完整统计报告 |
| `human-eval-summary.json` / `.md` | **可发布** | 脱敏：剔除 `case_id`/`arm`/`notes`/裁决人身份，`reviewer` 一律替换为 `anonymous` |

## 5. 盲评随机化与可审计性

- 两位评审各得一份**独立 `random.SystemRandom()` 置换**的包，`blind_id` 前缀区分命名空间（`a-001…` / `b-001…`）；把 A 的包当 B 的提交会触发 `NAMESPACE_MISMATCH`。
- 若两次置换恰好同序（概率极低但可能发生），`distinct_permutations` 会重排 B 最多 8 次，仍同序则报 `NAMESPACE_MISMATCH`；导入阶段还会再比一次还原后的题序，同序即拒（缺陷 A 的运行时防线）。
- **不固定 seed、不复现置换**（盲评分配必须不可预测）；改为登记 `permutation_sha256`（盲 id 序列的 canonical-JSON 摘要）证明"两序不同且生成后没被替换"，摘要本身不可反解。
- `packet_sha256` 只覆盖 `blind_id`/`question`/`evidence`/`package`（`frozen_packet`），评审填写的 `scores`/`notes` 不参与摘要——否则填完分就"篡改"了。
- 包生成后若 `runs.jsonl`/`evidence.jsonl`/数据集发生任何变更，`STALE_SOURCE` 拒绝导入；必须重新生成包、重新盲评。

## 6. 评分填写规则

- 五个 rubric：`facts_supported`、`exercise_answers_correct`、`goal_covered`、`difficulty_progression`、`profile_fit`（唯一真源 `backend/app/evaluation/ablation_report.py:8`）。
- 每格只允许严格布尔或 `null`：`"true"`、`0/1`、`0.9` 一律 `SCORE_TYPE`；`scores` 键必须与 rubric 完全一致。
- `null` = 未知/不适用，**不是"不达标"**。
- `notes` 不强制非空（强制写评语只会让人凑字数），协议建议：与判断相反或不确定的项写下理由。
- **null 的两条规则**（实现比设计稿更严，见 §14）：
  - *对称* null（同一 item 上 A、B 都在同一批指标上留空）→ 允许，该指标配对样本量 `n_m` 相应减少；
  - *非对称* null（一人填了某指标、另一人留空）→ 导入时 `COVERAGE_INCOMPLETE` 拒绝，因为这类"覆盖不齐"通常意味着漏填或对指标口径理解不同，应当面确认而不是让统计悄悄缩小分母。

## 7. 分歧与裁决

- 分歧清单粒度是 **item × 指标**（双方均为严格布尔且取值不同）。
- `import_reviews` 自动产出 `human-eval-adjudication-packet.json`（只含分歧项，隐去臂与双方判断），第三位真人据此填写：

```json
[{"blind_id": "a-004", "scores": {"facts_supported": true, "exercise_answers_correct": null,
  "goal_covered": true, "difficulty_progression": false, "profile_fit": null}, "notes": "引用可核查"}]
```

- 裁决语义与 `ablation_report.py:74-84` 保持一致（`human_agreement.resolve_judgement`，两处需人工同步）：一致即取共识；不一致**只接受严格布尔裁决**，裁决留空则该指标保持 `null`。
- 裁决只能落在**确有分歧**的 item 上（`ADJUDICATION_REQUIRES_DISPUTE`），同一 item 不可重复裁决，`--adjudications` 必须是运行目录内的本地文件名。
- 只要还有未 resolved 的指标判断，`review_complete=false`，各臂质量通过率一律 `null`（不是 0，也不是失败）。

## 8. 统计口径（公式写死）

对每个指标 m，取 A/B **双方均为严格布尔**的 item 集合，`n = |集合|`；2×2 计数 a=双方 yes、b=A yes/B no、c=A no/B yes、d=双方 no：

- `po = (a+d)/n`
- `pe = p_A1·p_B1 + p_A0·p_B0`（`p_X1` = 该评审判 yes 的比例）
- `κ = (po − pe)/(1 − pe)`
- `prevalence = (2a+b+c)/(2n)`、`bias = |b−c|/n`：`po` 高而 `κ` 低时，用来区分"类别失衡（kappa 悖论）"与"两位评审互相打架"。
- **未定义处理（必须显式）**：`n=0` → `kappa=null, po=null, reason="no_common_items"`；`pe==1`（两人都全同值）→ `kappa=null, reason="degenerate_marginals"`，`po` 照报。`status` ∈ `computed`/`undefined`。
- `po` 的 95% 区间：**Wilson score 区间**，`z=1.96`，`n=0` 时为 `null`（不抛异常，区间始终落在 `[0,1]`）。
- `κ` 的 95% 区间：**item 级非参 bootstrap**，`B=2000`（可 `--replicates` 调整，最小 2）、percentile 2.5/97.5 线性插值、`random.Random(seed)`，seed 与 replicates 都写进报告 `randomness`。退化重采样丢弃而非计 0；若全部退化则区间为 `null`。
- 全程 **stdlib-only**（`math`/`random`/`statistics`/`hashlib`/`json`），不引入 `scipy`。
- `profile_fit` 特别条款：任务集没有学习者画像（`evals/CLAIM_AND_ABLATION.md:47`），该指标 κ **照算但不可据此下结论**；报告的 `limitations` 恒定携带该声明，`reason` 置 `profile_fit_uninterpretable_without_learner_profile`。
- 计量口径声明同样恒定写进 `limitations`：review item 数 ≠ 独立问题数（12 个 case × 3 臂只贡献 26 级 item），不能把 item 计数读作独立题目证据。

## 9. "完成 20 题"的验收口径（Lead 裁决 5）

按 **item 级**计算：一个 (case, arm) 的包内条目 = 一个 review item。

- 历史实测：`output/ablation-full-20261017` 的留出集有 26 个 item（旧脚本跳过未完成 run），≥ 20。
- 新工具更严：`prepare_packets` 要求该 split 三臂**全部完成**（`RUNS_INCOMPLETE`），因此一次完整采集的留出集会给出 12 case × 3 臂 = **36 个 item**，同样 ≥ 20。
- 按 case 级只有 12 < 20，需要扩题集——属 QWEN-102 数据集工作，不在工具包范围。
- **任何汇报都不得把 item 数改口成"独立题目数"**：36 个 item 仍只来自 12 道独立任务，报告的 `limitations` 会恒定携带这一声明。

## 10. 隐私与不泄题

- 人评材料只落 `output/human-eval-<日期>/`（`.gitignore:70`）；**禁止**写入 `reports/`（该目录未被忽略，见 §13 隐患）。
- 发布物只有聚合 JSON/MD + `limitations`：不含逐题评语文本、`notes` 原文、真实评审人身份、`case_id`/`arm`。
- 仓库内不提交任何真实题面、评分表或 `output/` 材料；新测试 fixtures 全部在测试内用合成 item 现造。
- 工具不读取、不复制参考答案（包内本就没有），没有把材料上传到任何外部服务的功能。

## 11. 历史材料处置（2026-10-17 那批）

`output/ablation-full-20261017/` 的 `reviewer-a.json` 与 `reviewer-b.json` **题序完全相同**（缺陷 A），且 26 个 item 的 `scores` 至今全为 `null`（尚无真人评分）。处置原则：

- 只作为历史观察材料保留，**不重算、不并入本报告、不与新包混用**；
- 旧三脚本（`prepare_ablation_review.py` / `merge_ablation_reviews.py` / `prepare_ablation_adjudication.py`）原样不动，既有测试与已生成材料不受影响；
- 若确实需要这批数据的一致性证据，必须用 `prepare_packets` 重新生成两份独立置换的包并**重新盲评**。

## 12. 错误码

| 错误码 | 触发 |
|---|---|
| `REVIEWER_IDS_INVALID` | 两位 id 为空/相同，或裁决人与任一评审同名 |
| `PACKET_TAMPERED` | 包内容/题序/摘要与 manifest 或 mapping 不符；已存在的派生产物与本次重算不一致 |
| `SCORE_TYPE` | 分值不是严格布尔/`null`，或 `scores` 键与 rubric 不一致 |
| `COVERAGE_INCOMPLETE` | 同一 item 上 A/B 留空不对称；或双方一条判断都没填 |
| `STALE_SOURCE` | `runs.jsonl`/`evidence.jsonl`/数据集在包生成后变更 |
| `ANSWER_LEAK` | 包内（任意嵌套层）出现 `arm`/`case_id`/`expected_sources`/`expected_outcome`/`answer`/`answers` |
| `NAMESPACE_MISMATCH` | 盲 id 前缀不符、编号不连续、包不在 mapping 内、A/B 题序相同（张冠李戴） |
| `RUNS_INCOMPLETE` / `RUNS_INVALID` | 该 split 未全部完成；run 重复/缺失、item 覆盖不等于 run 集的两倍 |
| `EVIDENCE_MISSING` / `EVIDENCE_TAMPERED` / `EVIDENCE_DUPLICATE` | 证据快照缺失、自摘要不符、重复 |
| `MANIFEST_INVALID` / `MAPPING_INVALID` / `PACKET_INVALID` / `ARTEFACT_UNREADABLE` | 材料结构不符或读取失败 |
| `ADJUDICATION_INVALID` / `ADJUDICATION_REQUIRES_DISPUTE` / `ADJUDICATION_FILENAME` | 裁决项未知/重复、无分歧却裁决、路径不是本地文件名 |
| `OUTPUT_OUTSIDE_PRIVATE_ROOT` / `RUN_DIR_MISSING` / `ARTEFACT_EXISTS` / `REPORT_INVALID` | 目录越界、运行目录不存在、拒绝覆盖已有产物、报告缺 `evaluation_mode` |

## 13. 工具不能证明的事（必须随报告一起读）

1. 评审身份未认证，独立性是流程约束而非技术证明。
2. `null` 是"未知"，排除在配对计数之外，永不视为否定判断。
3. item 数不是独立题目数；小样本下 κ 与区间宽度都可能毫无意义，`n` 必须与 κ 同屏呈现。
4. `profile_fit` 无学习者画像输入，不可用于任何个性化结论。
5. 学习包四指标口径（`learning_package.py` 的 `HUMAN_CRITERIA`，无 `profile_fit`）与本五指标口径**分开出报告，禁止混用同一个 κ**。
6. 旁证隐患（不在本任务修）：`reports/` 未出现在 `.gitignore`，而 `scripts/evaluate_learning_package.py:26` 的默认输出恰在 `reports/`，与 `evals/LEARNING_PACKAGE_EVAL.md:94`（要求只放 `output/reports`）矛盾；本工具一律写 `output/`。该矛盾作为 QWEN-103/QWEN-401 整改候选上报。

## 14. 与设计稿的偏差（实现期收紧，需 Lead 复核）

| 项 | 设计稿 | 实现 | 原因 |
|---|---|---|---|
| `COVERAGE_INCOMPLETE` | "A/B 覆盖的 item 集合不同，或存在只一人填了某指标"；§6 又写"该指标 `n_m` 相应减少" | 拆成两条：对称留空 → 允许并减少 `n_m`；非对称留空 → 拒绝导入 | 两处表述冲突时取更严格的一条；口径已在 §6 写死，`tests/a/test_human_eval_toolkit.py:210` 与 `:141` 双向钉住 |
| `scripts/human_eval/` 文件数 | "五个入口" | 五个入口 + 一个共享模块 `common.py`（不是入口、无 `main`） | 避免五份重复校验逻辑；`common.py` 与入口同层、同样被测试覆盖 |
| `import_reviews` 幂等 | 未明确 | 派生产物（裁决包、对齐项）内容一致即放行，不同即 `PACKET_TAMPERED`；最终产物（reviewed/adjudicated/report/summary）一律 `open("x")` 拒绝覆盖 | 带裁决重跑是流程必需，但不能允许已有材料被静默改写 |
