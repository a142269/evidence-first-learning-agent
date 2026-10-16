# SM-2 vs FSRS-4.5 vs HLR

> B 角色 / 2026-06-24 / 真实可复验证据版

## 1. 本轮结论先说

这三套间隔重复算法在仓库里都已经有可运行实现。到 2026-06-24 为止，我们已经拿到了两类**真实可复现**数字：

1. 基于真实学生序列间隔的 **proxy MAE**。
2. 基于真实学生后续作答结果的 **模拟遗忘率 / 校准结果**。

但我们依然**不能**诚实宣称“day-level MAE 已实测”，因为当前仓库和 ASSISTments 数据口径仍然不支持按“真实天数”对齐。

所以这份文档做三件事：

1. 给出当前代码真正跑得出的 smoke 证据。
2. 给出当前已经补齐的 proxy MAE / 模拟遗忘率真实数字。
3. 明确写清楚哪些指标依然不能写成 day-level 实测，以及为什么不能假装已经实测。

## 2. 真实运行命令

```powershell
cd D:\xunfei\triple-U

D:\Anaconda3\envs\dxtorch\python.exe -c "
from backend.app.services.spaced_repetition.fsrs import sm2_vs_fsrs_benchmark
import json
print(json.dumps(sm2_vs_fsrs_benchmark(200), ensure_ascii=False, indent=2, default=str))
"

D:\Anaconda3\envs\dxtorch\python.exe -c "
from backend.app.services.spaced_repetition.hlr import sm2_vs_fsrs_vs_hlr_report
import json
print(json.dumps(sm2_vs_fsrs_vs_hlr_report(200), ensure_ascii=False, indent=2, default=str))
"
```

## 3. 当前真实可复现输出

### 3.1 SM-2 / FSRS smoke

`sm2_vs_fsrs_benchmark(200)` 实际输出：

| 算法 | 当前真实输出 |
|------|-------------|
| SM-2 | `total_items=50`, `due_today=18`, `average_easiness=2.41` |
| FSRS-4.5 | `total=50`, `avg_stability=0.10`, `avg_difficulty=1.00` |

### 3.2 三方 smoke

`sm2_vs_fsrs_vs_hlr_report(200)` 实际输出：

| 算法 | 当前真实输出 |
|------|-------------|
| SM-2 | `total_items=50`, `due_today=18`, `average_easiness=2.40` |
| FSRS-4.5 | `total=50`, `avg_stability=0.10`, `avg_difficulty=1.00` |
| HLR | `theta=[0.0252, 0.0357, 0.0414]`, `avg_predicted_recall=0.0254` |

这些数字是**真实执行结果**，但它们代表的是“函数级 smoke 可运行证据”，不是“ASSISTments 上 day-level scheduling benchmark”。

## 4. 当前可报告指标与边界

| 指标 | SM-2 | FSRS-4.5 | HLR |
|------|------|----------|-----|
| proxy MAE（真实序列间隔） | 46.4033 | 11.6602 | — |
| 模拟遗忘率 | 0.3622 | 0.2745 | — |
| day-level MAE（真实天数） | 不可计算 | 不可计算 | 不可计算 |
| 原因说明 | 缺绝对复习时间戳，只能对齐 order-gap proxy | 同左 | 除时间戳外还缺论文口径 per-lexeme 特征 |

## 5. 为什么不能把“预期值”继续写成实测

### 5.1 ASSISTments 原始表没有合适的复习时间戳

当前数据里我们能稳定拿到的字段包括：

- `order_id`
- `ms_first_response`
- `overlap_time`
- `opportunity`

但没有适合直接定义“下一次复习发生在多少天后”的 learner-level revisit day timestamp。  
这意味着我们不能诚实地给出“MAE（天）”。

### 5.2 当前仓库没有 day-level scheduler-eval harness

已有实现能做的是：

- SM-2: 更新 `easiness / interval / repetitions`
- FSRS-4.5: 更新 `stability / difficulty`
- HLR: 拟合 `theta` 并预测 recall probability

现在仓库里已经有一条 **proxy benchmark** 流水线，把“真实学生复习轨迹”映射成：

1. 预测下一次复习间隔
2. 对齐真实下一次 `order_id` 间隔
3. 计算 proxy MAE / forgetting-rate

### 5.3 HLR 还受论文特征依赖限制

HLR 原论文依赖的是接近 Duolingo 的特征工程口径，比如 per-lexeme / user-background / item-feature 组合。  
本仓库的 `HLRModel` 已经能训练、能输出参数，但还不是一套论文口径的完整 end-to-end benchmark。

## 6. 真实数据模拟实测（2026-06-24）

### 6.1 实测设置

| 项目 | 值 |
|------|----|
| 数据集 | ASSISTments-2009 |
| 采样 | 1000 学生 / 5000 per-student-skill 复习序列（≥3 次交互） |
| 指标 | proxy MAE / 预测间隔分布 / 校准（按间隔分箱的正确率）/ 模拟遗忘率 / 算法间分歧 |
| 脚本 | `scripts/benchmark_spaced_repetition.py --students 1000` |
| 产物 | `reports/spaced_repetition_benchmark_20260624_104358.json` |

### 6.2 SM-2 实测结果

| 指标 | 值 |
|------|----|
| 预测数 | 47405 |
| **proxy MAE（真实序列间隔）** | **46.4033** |
| 预测间隔 mean (天) | 41.71 |
| 预测间隔 std | 98.95 |
| 整体实际正确率 | 0.7205 |
| **模拟遗忘率** | **0.3622** |

校准（按预测间隔分箱）：

| 分箱 | 平均预测间隔(天) | 实际正确率 | 样本数 |
|------|-----------------|-----------|--------|
| 短间隔 (<33%) | 1.00 | 0.6378 | 15801 |
| 中间隔 (33-66%) | 2.97 | 0.7020 | 15801 |
| 长间隔 (>66%) | 121.16 | 0.8216 | 15803 |

校准合理：SM-2 预测"需尽快复习"的 item 实际正确率 0.64，预测"可长期不复习"的 item 实际正确率 0.82，单调递增。

### 6.3 FSRS-4.5 实测结果

| 指标 | 值 |
|------|----|
| 预测数 | 47405 |
| **proxy MAE（真实序列间隔）** | **11.6602** |
| 预测间隔 mean (天) | 0.32 |
| 预测间隔 std | 0.79 |
| 整体实际正确率 | 0.7205 |
| **模拟遗忘率** | **0.2745** |

FSRS 在 ASSISTments 上预测间隔极短（mean 0.32 天），因为 ASSISTments 较高答错率会频繁触发 stability 重置。proxy MAE 和模拟遗忘率都低于 SM-2。

### 6.4 HLR 实测结果（有限）

| 指标 | 值 |
|------|----|
| 训练样本 | 1600 |
| 测试样本 | 400 |
| theta | [0.0103, 0.0116, 0.0147] |
| 平均预测保持率 | 0.0830 |

HLR 训练在 interaction-count 代理特征上（非 day-level），per-lexeme 特征因 ASSISTments 缺失无法使用。

### 6.5 算法间分歧

| 指标 | 值 |
|------|----|
| SM-2 平均预测间隔 | 41.71 天 |
| FSRS 平均预测间隔 | 0.32 天 |
| 平均分歧 | 41.39 天 |

两算法在相同真实数据上的调度策略差异显著：SM-2 倾向长间隔（easiness 累积），FSRS 倾向短间隔（stability 重置保守）。

### 6.6 数据限制说明

ASSISTments-2009 skill builder 数据集**不包含 day-level 复习时间戳**。数据集有 `order_id`（序列序号）和 `ms_first_response`（响应延迟）但没有绝对时间戳。因此：

- **真正的 day-level MAE 无法计算**（没有"真实下次复习发生在多少天后"的 ground truth）
- 本报告新增的 **proxy MAE**，是把算法预测间隔与真实 `order_id` 间隔做对齐后的代理误差
- 本报告的"模拟遗忘率"是短间隔组实际错误率的代理指标
- "算法间分歧"衡量两种算法在相同数据上的调度分歧，不是与真实复习间隔的 MAE

## 7. 答辩建议话术

实测版：

> 我们把 SM-2、FSRS-4.5 和 HLR 三条路线都集成进来了，并在 ASSISTments-2009 真实学生数据上跑了模拟 benchmark。现在能给出的真实数字包括：SM-2 的 proxy MAE 是 46.40、模拟遗忘率是 0.36；FSRS 的 proxy MAE 是 11.66、模拟遗忘率是 0.27；HLR 因 ASSISTments 缺少 per-lexeme 特征只能跑有限训练。校准结果也显示 SM-2 的预测间隔与实际正确率单调相关。但 ASSISTments 数据集不包含 day-level 复习时间戳，所以真正的 day-level MAE 依然无法计算，我们没有用估计值冒充实测。

## 8. 后续如果要把这项补成真正实测

最短路径是新增一个专门的 spaced-repetition benchmark 脚本，至少补齐：

1. learner-item 复习事件抽取（已完成）
2. 可解释的 revisit 时间定义
3. 预测间隔与真实下次 revisit 的对齐
4. MAE / calibration / forgetting-rate 统一评估（calibration 和 forgetting-rate 已完成）

当前状态：**真实数据模拟实测已完成**（proxy MAE + 校准 + 遗忘率 + 算法间分歧），day-level MAE 因数据限制无法计算。
