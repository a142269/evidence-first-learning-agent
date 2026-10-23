# 评测调用量/Token/延迟/成本 只读汇总 (QWEN-109)

- 生成脚本: `scripts/report_eval_cost.py` (只读, 不 import os, 不读取 .env)
- 命令: `python scripts/report_eval_cost.py --scan-root output --out output/qwen109-2026-10-22/eval-cost-report.md`
- 证据等级: offline (对本机已有评测产物的只读再汇总, 无模型调用)
- 记账口径: 直接调用产品代码 `backend/app/services/run_usage.py` 的 `summarize_run_usage` + `aggregate_run_usage`, 脚本不自己另写一套成本/用量判定
- 成本口径: 逐条照抄记录里的 `result.budget.cost`; 不套用任何单价, `unknown` 原样输出, 绝不写成 0; 无 estimated 记录时金额一律显示为未记录
- 字段来源: `model_calls`/token/cost/usage_status 全部走产品投影; `latency_ms` 是唯一例外, 按原始 `result.latency_ms` 读 (原因见下一行与第 2 节); `input_chars` 取 budget
- 与产品投影的偏差: latency_ms 有 127 条被投影判为未记录, model_calls 有 0 条 (2026-10-22 已交付实测; 该投影已由 QWEN-104b 修复为接受非负 int/float, 同一条命令复跑此计数为 127→0, 本报告统计数字不改)
- 跨副本一致性: model_calls 不一致 0 条, latency_ms 不一致 0 条 (record / result / budget 三处副本互相校验)
- 记录总数 127 条, 来源 8 个, 无法解析的行 0 行

## 1. 数据来源与样本量

只统计真实评测产物; pytest 的 basetemp 夹具按路径组件 `test_*` 识别并整份排除。

| 来源标签 | 路径 | 记录数 | 臂 | 模型 | completed |
| --- | --- | --- | --- | --- | --- |
| ablation-full-20261017/runs | `output/ablation-full-20261017/runs.jsonl` | 72 | fullx24, singlex24, without_reviewerx24 | deepseek-flashx72 | Falsex23, Truex49 |
| ablation-smoke-20261017/runs | `output/ablation-smoke-20261017/runs.jsonl` | 3 | fullx1, singlex1, without_reviewerx1 | deepseek-flashx3 | Falsex1, Truex2 |
| ablation-smoke-budget-20261017/runs | `output/ablation-smoke-budget-20261017/runs.jsonl` | 3 | fullx1, singlex1, without_reviewerx1 | deepseek-flashx3 | Falsex1, Truex2 |
| qwen102-main/runs | `output/qwen102-main/runs.jsonl` | 12 | fullx12 | deepseek-flashx12 | Truex12 |
| qwen102-smoke/runs | `output/qwen102-smoke/runs.jsonl` | 1 | fullx1 | deepseek-flashx1 | Truex1 |
| retry-development-20261017 | `output/retry-development-20261017.jsonl` | 12 | 未标注x12 | 未标注x12 | Falsex3, Truex9 |
| stability-20261018/dev-retest-20261018 | `output/stability-20261018/dev-retest-20261018.jsonl` | 12 | 未标注x12 | 未标注x12 | Truex12 |
| stability-20261018/holdout-retest-20261018 | `output/stability-20261018/holdout-retest-20261018.jsonl` | 12 | 未标注x12 | 未标注x12 | Truex12 |

- 扫描根 `output` 下含 `result.budget` 的 `.jsonl` 共 130 份
- 计入 8 份 / 127 条记录 (本次汇总选用 8 份 / 127 条)
- 排除 pytest 夹具 122 份 / 304 条记录

被排除的夹具按 `output` 下第一层目录归并, 数字为记录数:

| 目录 | 被排除记录数 |
| --- | --- |
| pytest-baseline-20261018/... | 8 |
| pytest-final-20261018/... | 16 |
| pytest-final2-20261018/... | 8 |
| pytest-final3-20261018/... | 8 |
| pytest-final4-20261018/... | 8 |
| pytest-postgres-20261018/... | 2 |
| qwen-baseline-2026-10-19/... | 24 |
| qwen-wave1-2026-10-19/... | 26 |
| qwen103-2026-10-19/... | 10 |
| qwen103-lead-full/... | 10 |
| qwen104-2026-10-22/... | 30 |
| qwen105-2026-10-22/... | 6 |
| qwen106-2026-10-21/... | 38 |
| qwen106-lead-full/... | 10 |
| qwen107-2026-10-22/... | 40 |
| qwen107b-2026-10-22/... | 20 |
| qwen107c-2026-10-22/... | 20 |
| qwen108-2026-10-22/... | 20 |

## 2. 未知项与缺失样本 (单列计数, 不补 0)

| 项 | 计数 | 说明 |
| --- | --- | --- |
| budget 有记录 | 127/127 | run_usage 的 budget_recorded |
| cost_status=unknown | 127 | 运行时未配置 `V2_LLM_*_CNY_PER_MILLION` 单价 (usage_meter.py:29-37) |
| cost_status=estimated | 0 | 有单价时的估算成本 |
| cost.reason=cost_not_recorded | 1 | 记录里根本没有 cost 对象 |
| cost.reason=no_cost_amount_recorded | 126 | 有 cost 对象但没有金额 |
| cost.reason=cost_status_invalid | 0 | status 不在产品允许集 (estimated/unknown) |
| 无 estimated 成本的记录 | 127 | 成本维度只能报 unknown |
| estimated 金额合计 | 金额未记录 (无 estimated 记录) | 不套用单价, 无估算即不显示金额 |
| 顶层 cost_cny 有值 | 0 | 收集器写入的顶层成本字段 |
| 无 token 数据的记录 | 1 | 两侧 token 都无值, 不参与 token 求和 |
| usage_status=measured | 126 | 两侧 token 都有值 |
| usage_status=partial | 0 | 有 usage_unknown_calls |
| usage_status=unknown | 1 | 两侧 token 都无值 |
| usage_unknown_calls 合计 | 0 | provider 没回 usage 的调用数 |
| actual_input_tokens 缺失 | 1 | 输入 token 无值 |
| actual_output_tokens 缺失 | 1 | 输出 token 无值 |
| model_calls 缺失 | 0 | 调用数无值 |
| latency_ms 缺失 | 0 | 延迟无值 |
| latency_ms 被产品投影判为未记录 | 127 | 2026-10-22 实测: `run_usage.py` 的 `_count` 只接受非负整数, 小数 latency 全被丢弃; 本报告按原始值读, 偏差单列 (只登记, 本卡不改产品代码)。**该说明已过期**: QWEN-104b 把 `reported_latency_ms` 改走接受非负 int/float 的 `_number`, 复跑此计数为 127→0; QWEN-104c 再给 `_number`/`_amount` 加 `math.isfinite`。本行数字与全篇统计保持已交付口径, 不回改 |
| model_calls 被产品投影判为未记录 | 0 | 同一规则; 实测 0 条, 说明调用数都记成了整数 |
| arm 未标注 | 36 | 重跑/复测产物没有写臂标签 |
| config.model 未标注 | 36 | 重跑/复测产物没有写模型名 |
| completed 未标注 | 0 | record.completed 与 result.completed 都缺失 |
| result.error 有值 | 28 | 运行本身失败的记录, token 可能不完整 |

- `unknown` 的含义是**未记录**, 不是 0 元; 本报告不套用任何单价, 也不给折算金额。
- 产品聚合器自带的口径说明: Token and cost totals cover only runs with a recorded measurement; unknown entries are counted separately and never treated as zero.

## 3. 每臂汇总

| 来源 | 臂 | 样本 | completed | 调用数合计 | 输入 token 合计 | 输出 token 合计 | input_chars 合计 | latency_ms 中位数 [min~max] | 成本 | usage 状态 | 无 token 数据 | 缺失 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ablation-full-20261017/runs | full | 24 | Falsex11, Truex13 | 119 (24/24 条有值) | 389382 (24/24 条有值) | 72926 (24/24 条有值) | 806251 (24/24 条有值) | 21411.53 [11319.05~40332.14] (24/24) | cost_status: unknownx24; 金额未记录 (无 estimated 记录); 无 estimated 成本 24 条 | measuredx24 | 0 | 无 |
| ablation-full-20261017/runs | single | 24 | Falsex1, Truex23 | 24 (24/24 条有值) | 76613 (23/24 条有值) | 23866 (23/24 条有值) | 176340 (24/24 条有值) | 5803.27 [2302.41~8542.39] (24/24) | cost_status: unknownx24; 金额未记录 (无 estimated 记录); 无 estimated 成本 24 条 | measuredx23, unknownx1 | 1 | actual_input_tokens 缺 1, actual_output_tokens 缺 1 |
| ablation-full-20261017/runs | without_reviewer | 24 | Falsex11, Truex13 | 86 (24/24 条有值) | 234392 (24/24 条有值) | 57479 (24/24 条有值) | 492306 (24/24 条有值) | 15912.39 [10608.59~25447.86] (24/24) | cost_status: unknownx24; 金额未记录 (无 estimated 记录); 无 estimated 成本 24 条 | measuredx24 | 0 | 无 |
| ablation-smoke-20261017/runs | full | 1 | Falsex1 | 6 (1/1 条有值) | 22800 (1/1 条有值) | 3128 (1/1 条有值) | 47432 (1/1 条有值) | 27184.71 [27184.71~27184.71] (1/1) | cost_status: unknownx1; 金额未记录 (无 estimated 记录); 无 estimated 成本 1 条 | measuredx1 | 0 | 无 |
| ablation-smoke-20261017/runs | single | 1 | Truex1 | 1 (1/1 条有值) | 3715 (1/1 条有值) | 878 (1/1 条有值) | 8141 (1/1 条有值) | 5122.47 [5122.47~5122.47] (1/1) | cost_status: unknownx1; 金额未记录 (无 estimated 记录); 无 estimated 成本 1 条 | measuredx1 | 0 | 无 |
| ablation-smoke-20261017/runs | without_reviewer | 1 | Truex1 | 3 (1/1 条有值) | 8060 (1/1 条有值) | 1997 (1/1 条有值) | 17098 (1/1 条有值) | 15035.12 [15035.12~15035.12] (1/1) | cost_status: unknownx1; 金额未记录 (无 estimated 记录); 无 estimated 成本 1 条 | measuredx1 | 0 | 无 |
| ablation-smoke-budget-20261017/runs | full | 1 | Falsex1 | 5 (1/1 条有值) | 15612 (1/1 条有值) | 3214 (1/1 条有值) | 32951 (1/1 条有值) | 25727.03 [25727.03~25727.03] (1/1) | cost_status: unknownx1; 金额未记录 (无 estimated 记录); 无 estimated 成本 1 条 | measuredx1 | 0 | 无 |
| ablation-smoke-budget-20261017/runs | single | 1 | Truex1 | 1 (1/1 条有值) | 3715 (1/1 条有值) | 954 (1/1 条有值) | 8141 (1/1 条有值) | 5464.27 [5464.27~5464.27] (1/1) | cost_status: unknownx1; 金额未记录 (无 estimated 记录); 无 estimated 成本 1 条 | measuredx1 | 0 | 无 |
| ablation-smoke-budget-20261017/runs | without_reviewer | 1 | Truex1 | 3 (1/1 条有值) | 8381 (1/1 条有值) | 1692 (1/1 条有值) | 17622 (1/1 条有值) | 12378.32 [12378.32~12378.32] (1/1) | cost_status: unknownx1; 金额未记录 (无 estimated 记录); 无 estimated 成本 1 条 | measuredx1 | 0 | 无 |
| qwen102-main/runs | full | 12 | Truex12 | 60 (12/12 条有值) | 192781 (12/12 条有值) | 29101 (12/12 条有值) | 422348 (12/12 条有值) | 14367.08 [8990.81~26326.87] (12/12) | cost_status: unknownx12; 金额未记录 (无 estimated 记录); 无 estimated 成本 12 条 | measuredx12 | 0 | 无 |
| qwen102-smoke/runs | full | 1 | Truex1 | 5 (1/1 条有值) | 12922 (1/1 条有值) | 2602 (1/1 条有值) | 29147 (1/1 条有值) | 16732.46 [16732.46~16732.46] (1/1) | cost_status: unknownx1; 金额未记录 (无 estimated 记录); 无 estimated 成本 1 条 | measuredx1 | 0 | 无 |
| retry-development-20261017 | 未标注 | 12 | Falsex3, Truex9 | 42 (12/12 条有值) | 115790 (12/12 条有值) | 27524 (12/12 条有值) | 239474 (12/12 条有值) | 11533.34 [9194.96~20719.87] (12/12) | cost_status: unknownx12; 金额未记录 (无 estimated 记录); 无 estimated 成本 12 条 | measuredx12 | 0 | 无 |
| stability-20261018/dev-retest-20261018 | 未标注 | 12 | Truex12 | 44 (12/12 条有值) | 121383 (12/12 条有值) | 25384 (12/12 条有值) | 251917 (12/12 条有值) | 12473.52 [8433.91~20615.60] (12/12) | cost_status: unknownx12; 金额未记录 (无 estimated 记录); 无 estimated 成本 12 条 | measuredx12 | 0 | 无 |
| stability-20261018/holdout-retest-20261018 | 未标注 | 12 | Truex12 | 43 (12/12 条有值) | 116292 (12/12 条有值) | 25286 (12/12 条有值) | 247924 (12/12 条有值) | 15104.90 [8504.14~17587.74] (12/12) | cost_status: unknownx12; 金额未记录 (无 estimated 记录); 无 estimated 成本 12 条 | measuredx12 | 0 | 无 |

## 4. 每题明细

单条记录直接取产品投影结果; `未记录` 表示原始记录里没有该字段, 不是 0。

| 来源 | 臂 | 题号 | 调用数 | 输入 token | 输出 token | input_chars | latency_ms | cost_status | usage_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ablation-full-20261017/runs | full | ab-001 | 4 | 12375 | 2804 | 26058 | 20624.82 | unknown | measured |
| ablation-full-20261017/runs | full | ab-002 | 5 | 17010 | 2509 | 34167 | 19312.93 | unknown | measured |
| ablation-full-20261017/runs | full | ab-003 | 5 | 16608 | 2998 | 33952 | 26199.62 | unknown | measured |
| ablation-full-20261017/runs | full | ab-004 | 8 | 33648 | 5942 | 64403 | 40332.14 | unknown | measured |
| ablation-full-20261017/runs | full | ab-005 | 4 | 13506 | 1596 | 27557 | 13214.34 | unknown | measured |
| ablation-full-20261017/runs | full | ab-006 | 4 | 13912 | 3056 | 27524 | 21743.62 | unknown | measured |
| ablation-full-20261017/runs | full | ab-007 | 7 | 27764 | 4301 | 58307 | 32103.94 | unknown | measured |
| ablation-full-20261017/runs | full | ab-008 | 4 | 8203 | 1672 | 18487 | 14796.19 | unknown | measured |
| ablation-full-20261017/runs | full | ab-009 | 6 | 22224 | 2881 | 47322 | 27544.69 | unknown | measured |
| ablation-full-20261017/runs | full | ab-010 | 5 | 8312 | 3302 | 19094 | 25678.05 | unknown | measured |
| ablation-full-20261017/runs | full | ab-011 | 4 | 9791 | 2824 | 20779 | 18687.21 | unknown | measured |
| ablation-full-20261017/runs | full | ab-012 | 7 | 28794 | 5247 | 56505 | 35351.53 | unknown | measured |
| ablation-full-20261017/runs | full | ab-013 | 5 | 17307 | 3209 | 37290 | 27126.81 | unknown | measured |
| ablation-full-20261017/runs | full | ab-014 | 4 | 13001 | 1183 | 27578 | 11319.05 | unknown | measured |
| ablation-full-20261017/runs | full | ab-015 | 5 | 16736 | 2705 | 34802 | 23025.16 | unknown | measured |
| ablation-full-20261017/runs | full | ab-016 | 4 | 6623 | 3122 | 14463 | 19359.07 | unknown | measured |
| ablation-full-20261017/runs | full | ab-017 | 4 | 13397 | 2972 | 26901 | 19506.13 | unknown | measured |
| ablation-full-20261017/runs | full | ab-018 | 5 | 10053 | 2794 | 24167 | 23161.16 | unknown | measured |
| ablation-full-20261017/runs | full | ab-019 | 5 | 15184 | 3364 | 31759 | 21079.43 | unknown | measured |
| ablation-full-20261017/runs | full | ab-020 | 4 | 14384 | 2045 | 29388 | 13235.88 | unknown | measured |
| ablation-full-20261017/runs | full | ab-021 | 4 | 11655 | 3077 | 25877 | 18485.28 | unknown | measured |
| ablation-full-20261017/runs | full | ab-022 | 6 | 24889 | 3874 | 50228 | 23051.68 | unknown | measured |
| ablation-full-20261017/runs | full | ab-023 | 6 | 21927 | 3808 | 44887 | 23568.41 | unknown | measured |
| ablation-full-20261017/runs | full | ab-024 | 4 | 12079 | 1641 | 24756 | 14586.92 | unknown | measured |
| ablation-full-20261017/runs | single | ab-001 | 1 | 3715 | 816 | 8141 | 4927.26 | unknown | measured |
| ablation-full-20261017/runs | single | ab-002 | 1 | 3682 | 950 | 7753 | 5859.86 | unknown | measured |
| ablation-full-20261017/runs | single | ab-003 | 1 | 3283 | 1075 | 7180 | 6321.47 | unknown | measured |
| ablation-full-20261017/runs | single | ab-004 | 1 | 3851 | 1354 | 7890 | 8542.39 | unknown | measured |
| ablation-full-20261017/runs | single | ab-005 | 1 | 3822 | 739 | 8237 | 5141.84 | unknown | measured |
| ablation-full-20261017/runs | single | ab-006 | 1 | 4064 | 1052 | 8469 | 5746.69 | unknown | measured |
| ablation-full-20261017/runs | single | ab-007 | 1 | 3633 | 1316 | 8094 | 6926.64 | unknown | measured |
| ablation-full-20261017/runs | single | ab-008 | 1 | 2007 | 970 | 5073 | 5423.29 | unknown | measured |
| ablation-full-20261017/runs | single | ab-009 | 1 | 3617 | 853 | 8191 | 5368.64 | unknown | measured |
| ablation-full-20261017/runs | single | ab-010 | 1 | 1468 | 854 | 3784 | 5102.61 | unknown | measured |
| ablation-full-20261017/runs | single | ab-011 | 1 | 2845 | 936 | 6400 | 4894.27 | unknown | measured |
| ablation-full-20261017/runs | single | ab-012 | 1 | 4042 | 1198 | 8429 | 6161.02 | unknown | measured |
| ablation-full-20261017/runs | single | ab-013 | 1 | 3609 | 1246 | 8366 | 7058.13 | unknown | measured |
| ablation-full-20261017/runs | single | ab-014 | 1 | 3829 | 906 | 8467 | 4833.46 | unknown | measured |
| ablation-full-20261017/runs | single | ab-015 | 1 | 3537 | 938 | 7798 | 6183.75 | unknown | measured |
| ablation-full-20261017/runs | single | ab-016 | 1 | 1592 | 1062 | 4001 | 6656.78 | unknown | measured |
| ablation-full-20261017/runs | single | ab-017 | 1 | 3945 | 1108 | 8308 | 6963.25 | unknown | measured |
| ablation-full-20261017/runs | single | ab-018 | 1 | 1818 | 924 | 4849 | 5503.04 | unknown | measured |
| ablation-full-20261017/runs | single | ab-019 | 1 | 未记录 | 未记录 | 6843 | 2302.41 | unknown | unknown |
| ablation-full-20261017/runs | single | ab-020 | 1 | 3839 | 1364 | 8286 | 7197.86 | unknown | measured |
| ablation-full-20261017/runs | single | ab-021 | 1 | 3299 | 1270 | 7745 | 6098.79 | unknown | measured |
| ablation-full-20261017/runs | single | ab-022 | 1 | 3897 | 759 | 8450 | 3951.28 | unknown | measured |
| ablation-full-20261017/runs | single | ab-023 | 1 | 3892 | 1465 | 8392 | 6463.07 | unknown | measured |
| ablation-full-20261017/runs | single | ab-024 | 1 | 3327 | 711 | 7194 | 4835.40 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-001 | 3 | 8092 | 1698 | 17111 | 14620.21 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-002 | 3 | 8153 | 1498 | 16566 | 11418.88 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-003 | 4 | 11771 | 3148 | 24130 | 22567.70 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-004 | 4 | 13017 | 2919 | 25507 | 20376.83 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-005 | 3 | 8516 | 1407 | 17534 | 12714.94 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-006 | 5 | 17682 | 3748 | 35081 | 25447.86 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-007 | 3 | 8071 | 1849 | 17375 | 17426.02 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-008 | 3 | 4646 | 1268 | 10885 | 10608.59 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-009 | 4 | 12493 | 3013 | 26971 | 22055.76 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-010 | 4 | 5235 | 3086 | 12155 | 22784.14 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-011 | 4 | 9720 | 2784 | 20719 | 19818.67 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-012 | 4 | 13701 | 2981 | 27270 | 19736.39 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-013 | 4 | 11577 | 2771 | 25532 | 22055.56 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-014 | 3 | 8289 | 1432 | 17646 | 10620.08 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-015 | 3 | 7782 | 1678 | 16470 | 14648.11 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-016 | 3 | 4048 | 1881 | 9180 | 13161.69 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-017 | 3 | 7841 | 2207 | 15994 | 15764.91 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-018 | 3 | 4436 | 1845 | 10959 | 14101.54 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-019 | 3 | 7073 | 2034 | 15015 | 13425.54 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-020 | 5 | 16544 | 3602 | 34187 | 24540.31 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-021 | 4 | 11763 | 3138 | 26020 | 18251.38 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-022 | 4 | 13030 | 2853 | 26986 | 15496.26 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-023 | 4 | 13595 | 3166 | 27788 | 16059.87 | unknown | measured |
| ablation-full-20261017/runs | without_reviewer | ab-024 | 3 | 7317 | 1473 | 15225 | 13109.88 | unknown | measured |
| ablation-smoke-20261017/runs | full | ab-001 | 6 | 22800 | 3128 | 47432 | 27184.71 | unknown | measured |
| ablation-smoke-20261017/runs | single | ab-001 | 1 | 3715 | 878 | 8141 | 5122.47 | unknown | measured |
| ablation-smoke-20261017/runs | without_reviewer | ab-001 | 3 | 8060 | 1997 | 17098 | 15035.12 | unknown | measured |
| ablation-smoke-budget-20261017/runs | full | ab-001 | 5 | 15612 | 3214 | 32951 | 25727.03 | unknown | measured |
| ablation-smoke-budget-20261017/runs | single | ab-001 | 1 | 3715 | 954 | 8141 | 5464.27 | unknown | measured |
| ablation-smoke-budget-20261017/runs | without_reviewer | ab-001 | 3 | 8381 | 1692 | 17622 | 12378.32 | unknown | measured |
| qwen102-main/runs | full | it-001 | 5 | 13248 | 2662 | 29617 | 17458.69 | unknown | measured |
| qwen102-main/runs | full | it-002 | 4 | 13420 | 1733 | 30169 | 10983.71 | unknown | measured |
| qwen102-main/runs | full | it-003 | 5 | 17349 | 2055 | 37322 | 13176.98 | unknown | measured |
| qwen102-main/runs | full | it-004 | 4 | 13091 | 1631 | 28959 | 10396.90 | unknown | measured |
| qwen102-main/runs | full | it-005 | 8 | 23657 | 4393 | 48281 | 26326.87 | unknown | measured |
| qwen102-main/runs | full | it-006 | 5 | 18343 | 2523 | 39568 | 14989.63 | unknown | measured |
| qwen102-main/runs | full | it-007 | 6 | 17693 | 3134 | 39144 | 16352.42 | unknown | measured |
| qwen102-main/runs | full | it-008 | 5 | 17727 | 2341 | 38551 | 13744.53 | unknown | measured |
| qwen102-main/runs | full | it-009 | 5 | 13381 | 2688 | 28185 | 16621.81 | unknown | measured |
| qwen102-main/runs | full | it-010 | 4 | 12961 | 1435 | 30145 | 8993.20 | unknown | measured |
| qwen102-main/runs | full | it-011 | 4 | 13582 | 1580 | 30395 | 8990.81 | unknown | measured |
| qwen102-main/runs | full | it-012 | 5 | 18329 | 2926 | 42012 | 15676.48 | unknown | measured |
| qwen102-smoke/runs | full | it-001 | 5 | 12922 | 2602 | 29147 | 16732.46 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-001 | 3 | 8128 | 1713 | 17167 | 10927.50 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-002 | 3 | 8115 | 1491 | 16488 | 9194.96 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-003 | 3 | 7362 | 1850 | 15334 | 11579.03 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-004 | 5 | 17043 | 3931 | 33274 | 20719.87 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-005 | 4 | 12777 | 2702 | 26362 | 14958.32 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-006 | 4 | 14020 | 3102 | 27808 | 16463.90 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-007 | 3 | 8061 | 1854 | 17282 | 10111.50 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-008 | 3 | 4821 | 1622 | 11144 | 9923.08 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-009 | 3 | 7908 | 1512 | 17235 | 10009.51 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-010 | 3 | 3841 | 1848 | 8977 | 11487.65 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-011 | 4 | 10195 | 3020 | 21385 | 16346.28 | unknown | measured |
| retry-development-20261017 | 未标注 | ab-012 | 4 | 13519 | 2879 | 27018 | 15103.65 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-001 | 4 | 12248 | 2269 | 25829 | 14491.39 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-002 | 4 | 11529 | 1962 | 23330 | 13187.95 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-003 | 3 | 7278 | 1687 | 15203 | 10943.99 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-004 | 4 | 13171 | 2458 | 25829 | 13665.73 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-005 | 3 | 8324 | 1506 | 17306 | 9578.03 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-006 | 5 | 16695 | 3113 | 33633 | 19785.18 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-007 | 3 | 7938 | 1567 | 17132 | 9745 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-008 | 3 | 4692 | 1362 | 10965 | 8433.91 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-009 | 3 | 7913 | 1513 | 17260 | 10281.84 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-010 | 3 | 3904 | 1836 | 9086 | 11759.09 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-011 | 4 | 10014 | 2568 | 21197 | 15533.78 | unknown | measured |
| stability-20261018/dev-retest-20261018 | 未标注 | ab-012 | 5 | 17677 | 3543 | 35147 | 20615.60 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-013 | 4 | 11002 | 2167 | 24640 | 15035.65 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-014 | 3 | 8553 | 1682 | 18080 | 10265.19 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-015 | 3 | 7778 | 1681 | 16486 | 10397.73 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-016 | 3 | 4017 | 1813 | 9105 | 10773.36 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-017 | 4 | 12697 | 2769 | 25568 | 17587.74 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-018 | 3 | 4198 | 1274 | 10474 | 8504.14 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-019 | 4 | 10746 | 2408 | 22792 | 15268.01 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-020 | 4 | 11725 | 2241 | 24483 | 15790.94 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-021 | 4 | 11755 | 2653 | 26145 | 15389.49 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-022 | 4 | 12900 | 2291 | 26945 | 15174.15 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-023 | 4 | 13381 | 2647 | 27548 | 16017.57 | unknown | measured |
| stability-20261018/holdout-retest-20261018 | 未标注 | ab-024 | 3 | 7540 | 1660 | 15658 | 12557.03 | unknown | measured |

## 5. 跨来源合计与口径警告

| 维度 | 值 |
| --- | --- |
| 记录总数 | 127 |
| 调用数合计 | 442 (127/127 条有值) |
| 输入 token 合计 | 1321838 (126/127 条有值) |
| 输出 token 合计 | 276031 (126/127 条有值) |
| input_chars 合计 | 2797092 (127/127 条有值) |
| latency_ms 中位数 [min~max] | 14101.54 [2302.41~40332.14] (127/127) |
| 成本 | cost_status: unknownx127; 金额未记录 (无 estimated 记录); 无 estimated 成本 127 条 |
| usage 状态 | measuredx126, unknownx1 |
| 无 token 数据 | 1 |
| 缺失 | actual_input_tokens 缺 1, actual_output_tokens 缺 1 |

- 合计是**记录求和**, 不是去重题数: 有 25 个题号出现在多个来源 (例如 ab-001, ab-002, ab-003, ab-004), 同一题在不同轮次被重复计入。
- 各来源的 `dataset_sha256` 并不相同 (重跑/复测产物甚至没有写该字段), 因此跨来源合计只能当作调用量上界, 不能当作一次评测的结果。
- 数据集/证据摘要存在于原始记录中, 本报告按脱敏要求不复现其取值。
