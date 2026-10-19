# QWEN-101 人工盲评工具包 · 设计稿（只设计，不实现）

> 作者：Qwen（唯一主执行者）· 日期：2026-10-19 · 审阅人：Lead
> 分支：`qwen/wave1-evidence`（基于 `main@64bc815`）· 依据：主计划 [QWEN-101 任务卡](QWEN_AGENT_UPGRADE_MASTER_PLAN_2026-10-19.md#L474)、Lead [REVIEW] 指令第 2 项（`docs/QWEN_LEAD_DIALOGUE.md:329`）
> **本文件不写实现、不产生任何评分值。** 文中每个"现状"都给了 `文件:行`，可逐条复验；证据等级：`offline`。

## 0. 目标与硬边界

| 项 | 内容 |
|---|---|
| 交付物（实现阶段） | `scripts/human_eval/` CLI 五个入口 + `backend/app/evaluation/human_agreement.py` 纯函数 + `docs/HUMAN_EVAL_PROTOCOL.md` + 工具自身的测试 |
| 验收（任务卡原文） | 两位真人可独立完成 20 题；工具输出 kappa 与分歧清单；**不代填评分** |
| 硬边界 | 工具在任何代码路径上都**不产生 `true`/`false`**：生成时 `scores` 恒为 `None`（沿用 `dict.fromkeys(RUBRICS)`，`scripts/prepare_ablation_review.py:59`），导入时只搬运真人填的值，统计时缺值即 `null` 不推测（沿用 `ablation_report.py:96-118` 的 null-if-incomplete） |
| 零成本 | 不接入任何模型 API、不读 `.env`、不产生付费调用 |

## 1. 复用什么（现状事实，不重复造）

| 现有能力 | 位置 | 本设计如何使用 |
|---|---|---|
| 三臂/五指标枚举（唯一真源） | `backend/app/evaluation/ablation_report.py:7-8`（`ARMS`、`RUBRICS`） | 直接 import，**不在工具里另立枚举** |
| 学习包四指标口径 | `backend/app/evaluation/learning_package.py:17`（`HUMAN_CRITERIA`，无 `profile_fit`） | 两套口径分开出报告，禁止混用同一个 κ |
| 盲评包生成 + 证据快照校验 | `scripts/prepare_ablation_review.py:25-62`（`SystemRandom` L49、`blind_id` L53、包/证据双摘要 L57/L61） | 作为 `prepare_packets` 的基线，只加"每评审独立置换"和输入摘要登记 |
| 裁决包（只含分歧项，隐去臂与前两位判断） | `scripts/prepare_ablation_adjudication.py:38-53` | 原样复用其校验语义 |
| 导入合并 + 防篡改（重算摘要、题目一致、评审 id 互斥） | `scripts/merge_ablation_reviews.py:24-30,46-50,71-84` | 作为 `import_reviews` 的校验骨架 |
| 分歧→裁决→resolved 语义 | `ablation_report.py:74-84` | κ 报告的分歧处置**引用**它，不另写一套 |
| 指纹绑定（题+rubric+来源+该次预测） | `learning_package.py:112-116` | 用于"陈旧包导入"检测 |
| 结果 JSON 的诚实字段惯例 | `evals/results/qa-golden-v2-summary.json`（`evaluator_version`、`dataset_signature`、`limitations`）、`learning-package-v1-summary.json`（`human_review_coverage: 0.0`） | 新报告必须有 `evaluation_mode`/`evaluator_version`/输入摘要/`limitations` |
| 既有测试与 CI 位 | `tests/a/test_ablation_review_packets.py:26-28`（fixtures 写法）、`:35`、`:59`（包内无 `arm`）、`:36-42`（篡改→`SystemExit` 且不落文件）；`ci.yml:194` | 新测试沿用同一写法与"包内无 `arm`"断言 |
| 隐私目录约定 | `.gitignore:70`（`output/`） | 人评材料一律落 `output/` |
| 评测层依赖惯例 | `requirements.txt:34-37` 只有 `pandas`/`numpy`/`scikit-learn`（**无 `scipy`**，它只是 scikit-learn 的传递依赖）；`backend/app/evaluation/` 现有模块只用 stdlib（`statistics`/`math`/`hashlib`/`json`） | κ/CI 继续 **stdlib-only**（见 §10 裁决点 4） |

## 2. 代码分层与调用形态

- **数学与校验放 `backend/app/evaluation/human_agreement.py`**：`pyproject.toml:111-116` 的 mypy `exclude` 含 `scripts/`，把 κ/bootstrap 放进 `scripts/` 等于放弃静态检查；`backend/app/evaluation/` 是被 mypy 覆盖、且已有纯函数聚合先例的位置。
- **`scripts/human_eval/` 只做 CLI 薄壳**：`prepare_packets.py`、`validate_packets.py`、`import_reviews.py`、`agreement_report.py`、`export_summary.py`。沿用仓库既有 CLI 惯例：`ROOT = Path(__file__).resolve().parents[2]` + `sys.path.insert`、`main(argv=None) -> int`（便于测试注入）、预写校验用 `parser.error(...)`、运行期失败用 `parser.exit(2, "<固定文案>")` 且**不回显异常原文**（同 `scripts/summarize_ablation.py:40-41`、`scripts/evaluate_learning_package.py:71-75`）、所有写操作用 `Path.open("x")` 拒绝覆盖、stdout 只输出一行机器可读 JSON。
- 子命令不引入 `argparse` sub-parsers（全仓无 `add_parser` 先例，`scripts/manage_access.py:11` 用 `action` 位置参数 + `choices`）；不新增 Makefile 目标或 console entry point（`Makefile` 无脚本类目标、`pyproject.toml` 无 scripts 段）。调用形态统一为 `python -m scripts.human_eval.<mod> ...`。
- `scripts/` 与 `scripts/human_eval/` 都不建 `__init__.py`：`pyproject.toml:143` 的 `pythonpath = ["."]` 已让命名空间导入可用（`tests/a/test_ablation_review_packets.py:7` 即如此）。

## 3. 数据模型（五个对象，字段级）

| 对象 | 字段 | 与现状差异 |
|---|---|---|
| `packet-item`（发给评审人） | `blind_id`、`question`、`evidence`、`package`、`scores{5}`、`notes` | 结构不变；**新增约束**：包内绝不出现 `case_id`/`arm`/`expected_sources`/参考答案（现有测试已断言无 `arm`，`test_ablation_review_packets.py:35`） |
| `packet-manifest`（新增） | `generator_version`、`source_dataset_sha256`、`runs_sha256`、`evidence_index_sha256`、`split`、`item_count`、`permutation_sha256{a,b}`、`created_at` | 现在全仓**没有任何置换或输入的登记**，包不可复现审计；本对象专治此项 |
| `blind-mapping`（私有） | `blind_id`、`case_id`、`arm`、`evidence_sha256`、`package_sha256` | 结构不变；改为**按评审人分列**（`{reviewer, blind_id, case_id, arm, …}`），因为同一 case 在 A/B 包里的 `blind_id` 不再同序 |
| `review-submission`（评审人回填，导入输入） | 与 `packet-item` 同形，`scores` 值 ∈ `true/false/null`，`notes` 可选 | 新增：导入前必须过 `validate_packets`，且 `blind_id` 命名空间必须属于该评审人 |
| `agreement-report`（可发布） | `evaluation_mode="human_agreement_offline"`、`evaluator_version`、输入摘要、`per_metric{κ, po, pe, n, prevalence, bias, κ 95% CI, po 95% CI, status, reason}`、`disagreements[]`、`coverage`、`limitations[]` | 新对象；缺值一律 `null` + `reason`，不隐藏样本量 |

## 4. 盲评流程（六步）与两个必须修掉的现存缺陷

流程：`prepare_packets` → 分发两份**互相不可对齐**的包 → 真人独立填写（工具不参与）→ `validate_packets` → `import_reviews`（合并 + 摘要复核）→ 分歧项 `prepare_adjudication` → 第三位真人裁决 → `agreement_report` → `export_summary`（脱敏发布物）。

- **缺陷 A：A/B 拿到同一顺序。** `scripts/prepare_ablation_review.py:63` 把同一个 `packet` 对象在 `(("reviewer-a.json", packet), ("reviewer-b.json", packet), …)` 里写两次 → 两份材料题序完全相同，存在顺序锚定风险，且两位评审一旦交流就能逐题对号。**本机一手复验**：读 `output/ablation-full-20261017/reviewer-a.json` 与 `reviewer-b.json`，26 个 item 的 `blind_id` 序列**完全相等**（且 26 个 `scores` 值至今全为 `None`，即尚无真人评分）。设计：每评审独立 `random.SystemRandom()` 置换，`blind_id` 加评审前缀（`a-013` / `b-013`），映射表按评审人分列。
- **缺陷 B：置换不可复现、无审计痕迹。** 全仓没有任何 seed/置换登记（`prepare_ablation_review.py:49-50` 用 `SystemRandom`，这是有意为之——不应用固定 seed 去"复现盲评"）。设计：不复现置换，而是登记 `permutation_sha256`（对盲 id 序列做 canonical-JSON 摘要），既能证明"两序不同且生成后未被替换"，又不泄露可反解的信息。
- **不动项**：`blind_id` 在跳过未完成 run 后会跳号（`item-006` 缺失，实测 `output/ablation-full-20261017/blind-mapping.json`）——纯观感问题，改动会破坏现有测试与已生成材料，**本次不修**。

## 5. 导入与校验（错误码，全部"先校验后落盘"）

任一校验失败即 `parser.exit(2, …)` 且**不产出任何文件**（沿用 `test_ablation_review_packets.py:36-42` 的可观察行为：篡改 `evidence_sha256` → `SystemExit` 且 `reviewed-runs.jsonl` 不存在）。

| 错误码 | 触发 | 现有对应 |
|---|---|---|
| `REVIEWER_IDS_INVALID` | 两位 id 为空/相同，或裁决人等于任一位评审 | `merge_ablation_reviews.py:24-30` |
| `PACKET_TAMPERED` | 包内 `package`/`evidence` 重算摘要与 mapping 不符 | `merge_ablation_reviews.py:46-50` |
| `SCORE_TYPE` | 分值不是严格 `bool`/`None`（`"true"`、`0/1`、`0.9` 全拒） | `prepare_ablation_adjudication.py:40-45` |
| `COVERAGE_INCOMPLETE` | A/B 覆盖的 item 集合不同，或存在只一人填了某指标 | `merge_ablation_reviews.py:35-40` 的集合校验，扩到指标级 |
| `STALE_SOURCE` | `runs.jsonl`/`evidence.jsonl` 在包生成后变更 | **新增**：比对 `packet-manifest` 的输入摘要（`learning_package.py:112-116` 的指纹思想） |
| `ANSWER_LEAK` | 包内出现 `case_id`/`arm`/`expected_sources`/参考字段 | **新增**：`validate_packets` 独立步骤，把测试:37 的规则变成运行时防线 |
| `NAMESPACE_MISMATCH` | 把 A 的包当 B 的提交（`blind_id` 前缀不符） | **新增**，配合缺陷 A 的每评审置换 |

`notes` 不强制非空：强制写评语会变成让评审人凑字数，反而降低数据质量；协议里写"建议"，工具不校验。

## 6. 统计口径（写死公式，避免实现时自由发挥）

对每个 rubric 指标 m，取 A/B **双方均为严格 bool** 的 item 集合，`n_m = |集合|`：

- 观察一致率 `po = 一致数 / n_m`。
- 期望一致率 `pe = p_A1·p_B1 + p_A0·p_B0`（`p_X1` = 该评审判 `true` 的比例）。
- Cohen's kappa `κ = (po − pe) / (1 − pe)`。
- **undefined 处理（必须显式）**：`n_m = 0` → `κ=null, po=null, reason="no_common_items"`；`pe == 1` → `κ=null, reason="degenerate_marginals"`（两人都全同值，`po` 照报）。绝不把 undefined 写成 0。
- `po` 的 95% 区间：**Wilson score 区间**，`z=1.96`，纯 `math`。
- `κ` 的 95% 区间：**item 级非参 bootstrap**，`B=2000`、percentile 2.5/97.5、`random.Random(seed)` 且 seed 写进报告（区间可复现；这与盲评置换用 `SystemRandom` 不冲突——前者是数值复现，后者是不可预测分配）。不用 scipy（`requirements.txt` 无该依赖）。
- 附带诊断量 `prevalence`、`bias`、`expected agreement`：当 `po` 高而 `κ` 低时，读者需要知道这是类别失衡（kappa 悖论）而不是"两位评委互相打架"。
- 分歧清单：item×指标粒度、双方均为严格 bool 且不同（对齐 `prepare_ablation_adjudication.py:46-47`）；裁决后的取值**引用** `ablation_report.py:74-84` 的 `resolved_score` 语义，不另写第二套。
- 门禁语义：`review_complete=false` 时，所有质量通过率仍为 `null`（对齐 `ablation_report.py:96-118` 与 `evals/README.md:16`）。
- `profile_fit` 特别条款：任务本身不提供学习者画像（`evals/CLAIM_AND_ABLATION.md:47`），所以该指标 κ 照算，但报告 `limitations` 必须带上"不可据此下结论"。

## 7. fixtures 与测试计划（且绝不泄题）

**原则：仓库里不提交任何真实题面。** 现有留出集在 `evals/ablation_tasks_v1.jsonl`（24 行、12 dev/12 holdout，且被 `tests/a/test_ablation_dataset.py:5-16` 钉死），真实题目文本已经跟踪在库内；但新测试**不得**把 `output/` 里的题面、证据或评分表当作 fixture 提交——fixtures 一律在测试内用 6 个合成 item 现造（`tmp_path` 写 `runs.jsonl`/`evidence.jsonl`/替身 tasks），沿用 `monkeypatch.setattr(<module>, "ROOT", tmp_path)` + `sys.argv` 补丁 + `pytest.raises(SystemExit)`（`test_ablation_review_packets.py:26-28`）。

| 测试 | 关键断言 |
|---|---|
| κ 数值正确性 | 手算例：`n=8`、`po=0.75`、`pe=0.5` → `κ=0.5` |
| degenerate/空集 | 全同值 → `null + reason="degenerate_marginals"`；无共同 item → `no_common_items`；`po` 仍按定义给出 |
| bootstrap 可复现 | 同 seed 两次得同一区间；不同 seed 区间稳定（容差内） |
| Wilson 边界 | `po=1`、`po=0`、`n=0` 不抛异常、区间在 `[0,1]` |
| **不代填** | 生成包后断言每个 `scores` 值 `is None`；且 `human_agreement.py` 无任何写文件/写评分入口（模块级不 import `pathlib` 写路径） |
| 去锚定 | A/B 的 `blind_id` 序列不同；映射可双向还原；两包 `item_count` 相同 |
| 运行时防泄题 | 若手工往包塞 `arm`/`case_id`，`validate_packets` → `ANSWER_LEAK` 且不落文件 |
| 陈旧/篡改 | 改 `evidence_sha256` 或包生成后改 `runs.jsonl` → 对应错误码且不产出文件 |
| 覆盖率不完整 | 一人漏填某指标 → `COVERAGE_INCOMPLETE`，且该指标 `n_m` 相应减少 |

CI 归属：纯 stdlib、毫秒级 → **fast** 层。落地时把新测试文件追加进 `.github/workflows/ci.yml:172-209` 的显式清单（该清单当前 37 文件），并同步 `docs/TEST_MATRIX.md`；**是否加入覆盖率门禁清单（当前 5 文件、`--cov-fail-under=80`）由 Lead 决定**，不在本设计擅自扩。本机验证一律用独立 `--basetemp output/<独立目录>/base`。

## 8. 隐私与不泄题

- 人评材料只写 `output/human-eval-<日期>/`（`.gitignore:70` 唯一相关的被忽略根目录）；发布物只有聚合 JSON/MD + `limitations`，**不含**逐题评语文本、`notes` 原文、真实评审人身份（只留匿名 id）。
- **实测隐患（需要单独整改，不在本任务顺手改）**：`reports/` 并未出现在 `.gitignore`（`grep` 无匹配），而 `scripts/evaluate_learning_package.py:26` 的默认输出恰是 `ROOT/"reports/learning_package_offline_report.json"`，`evals/LEARNING_PACKAGE_EVAL.md:94` 却要求报告/审查表只放本地 `output/reports`。三者相互矛盾，一旦有人按默认路径跑，人工审查材料有被提交的风险。本工具一律 `output/`，并把该矛盾作为 QWEN-103/QWEN-401 的整改候选上报。
- 工具不读取、不复制参考答案（包内本就没有），不做把包上传到任何外部服务的功能。

## 9. 验收对照（"20 题"怎么满足）

现有留出口径实测：12 个 holdout case × 3 臂 = 36 run，实际生成 26 个评分 item（`output/ablation-full-20261017/blind-mapping.json`，本地被忽略；26 个 item 的 `scores` 当前**全部仍是 `None`**，即尚无真人评分——这也印证台账 E7"工具已实现、评分待真人"）。因此：

- 按 **item 计**：26 ≥ 20，工具与流程即可满足验收，无需新增数据。
- 按 **case 计**：只有 12 < 20，必须扩题集 → 属 QWEN-102 / 数据集改动，**不在工具包范围内**。
- 协议文档 `docs/HUMAN_EVAL_PROTOCOL.md` 必须把计量口径写成一句话定死（我倾向前者），否则"完成 20 题"会被两种解读。

## 10. 需要 Lead 裁决（实现前）

1. **落点**：数学放 `backend/app/evaluation/human_agreement.py` + `scripts/human_eval/` 薄 CLI（推荐，理由见 §2），还是全部留在 `scripts/`？
2. **兼容策略**：每评审独立置换会改变现有脚本行为。建议**新包默认开启、旧三脚本原样不动**（不破坏 `tests/a/test_ablation_review_packets.py` 与已生成的历史材料）；如你要直接改造旧脚本，请说明历史 `output/ablation-full-20261017` 材料如何处置。
3. **κ 口径**：逐 rubric 二值 κ（推荐，与现有 `RUBRICS` 一致）还是整包复合标签 κ？
4. **依赖**：bootstrap + Wilson 全 stdlib（推荐，保持 `backend/app/evaluation/` 无第三方依赖）；是否允许引入 `scipy`？我建议不允许——`requirements.txt:34-37` 目前没有它。
5. **"20 题"口径**：item 级（现成 26）还是 case 级（需扩题集）？
6. 覆盖率门禁清单是否纳入新模块（涉及 `ci.yml:218-225` 的 80% 门槛）？

## 11. 明确不做

不代填/不预测评分；不把 `null` 当 `false`；不认证评审身份、不宣称能证明独立性（`evals/CLAIM_AND_ABLATION.md:27` 已如此声明，协议继续声明）；不做 Web UI、不接数据库；不与产品内"教师审核"共用词汇（那是 `docs/ENTERPRISE_AGENT_RAG_UPGRADE.md` 等文档里的另一套语义）；不改 README 的对外数字（归 QWEN-103）。
