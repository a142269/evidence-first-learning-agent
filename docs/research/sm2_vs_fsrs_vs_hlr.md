# SM-2 vs FSRS vs HLR 对照报告

> 日期：2026-06-23  
> 负责人：角色 B  
> 目的：补齐 `T2.5` 的可展示 benchmark Markdown，让 `SM-2 / FSRS / HLR` 不再只停留在代码层。

---

## 1. 实验性质与边界

这份报告基于 `backend/app/services/spaced_repetition/hlr.py::sm2_vs_fsrs_vs_hlr_report(n_items=200)` 的统一对照输出生成。

- 这是 **调度器级 smoke 对照**，不是公共数据集上的 AUC 论文复现。
- 数据来源为脚本内部固定随机种子 `42` 生成的合成复习轨迹。
- 目标是展示三类调度思想的差异、接口可用性与演示价值，而不是宣称最终学术指标。

---

## 2. 实验设置

- 样本规模：`n_items=200`
- 去重后记忆条目数：`50`
- 固定随机种子：`42`
- 输出来源：
  - `SM-2`：`backend/app/services/spaced_repetition/sm2.py`
  - `FSRS-4.5`：`backend/app/services/spaced_repetition/fsrs.py`
  - `HLR`：`backend/app/services/spaced_repetition/hlr.py`

---

## 3. 结果摘要

| 方法 | 关键结果 | 说明 |
|---|---|---|
| SM-2 | `total_items=50`, `due_today=18`, `average_easiness=2.4` | 经典启发式调度，便于解释与落地 |
| FSRS-4.5 | `total=50`, `avg_stability=0.1`, `avg_difficulty=1.0` | 参数化更强，但当前 smoke 输出表现出高难度、短稳定期 |
| HLR | `theta=[0.0252, 0.0357, 0.0414]`, `avg_predicted_recall=0.0254` | 直接建模 half-life，适合做可解释遗忘预测 |

原始说明：

> HLR models half-life directly; SM-2 uses 1-param easiness; FSRS-4.5 uses 17-param memory model.

---

## 4. 差异解读

### 4.1 SM-2

- 优点：规则清晰、工程成本低、易于在演示中解释“为什么推荐今天复习”
- 局限：参数表达能力弱，个体差异适配有限

### 4.2 FSRS-4.5

- 优点：参数更丰富，理论上比 SM-2 更能贴合记忆稳定度变化
- 局限：当前仓库实现主要用于离线对照；若要做强结论，需要真实复习日志和长期在线校准

### 4.3 HLR

- 优点：直接输出与遗忘/记忆半衰期相关的可解释量，适合作为“学习时光机”与未来学情预测的补充证据
- 局限：当前实验仍是合成轨迹 smoke，不应包装为真实课堂 AUC 结论

---

## 5. 适用场景建议

| 方法 | 更适合的场景 |
|---|---|
| SM-2 | 默认复习调度、课程作业提醒、轻量离线演示 |
| FSRS-4.5 | 需要更强参数化调度的个性化复习实验 |
| HLR | 可解释遗忘预测、时光机/预测类展示、研究型答辩说明 |

---

## 6. 一句话结论

在当前仓库阶段，`SM-2` 最适合做稳定默认调度，`FSRS` 适合作为更强参数化基线，`HLR` 最适合承担“可解释预测”展示位；三者已经具备对照叙事，但 **这份报告是 smoke 级证据，不是最终公开数据集结论**。

---

## 7. 复现方式

```bash
D:\Anaconda3\envs\dxtorch\python.exe -c "from backend.app.services.spaced_repetition.hlr import sm2_vs_fsrs_vs_hlr_report; import json; print(json.dumps(sm2_vs_fsrs_vs_hlr_report(n_items=200), ensure_ascii=False, indent=2))"
```
