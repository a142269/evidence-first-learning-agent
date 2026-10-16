# SAKT Knowledge Tracing Benchmark

> B 角色 / 2026-06-23 / full 5-fold 实测版

## 1. 目标

在 ASSISTments-2009 上对 SAKT 做完整 5-fold next-step knowledge tracing benchmark，并和同口径的 Naive / BKT / DINA / DKT 做真实对照。

## 2. 实验设置

| 项目 | 值 |
|------|----|
| 数据集 | ASSISTments-2009 |
| 学生数 | 3694 |
| 技能数 | 111 |
| 交互数 | 336663 |
| 评估协议 | student-wise 5-fold CV |
| 任务定义 | next-step KT |
| SAKT 配置 | `embed_dim=128, num_heads=8, num_layers=1, max_epochs=30, batch_size=64` |
| DKT 配置 | `hidden_dim=128, n_layers=2, max_epochs=50, batch_size=64` |

## 3. 复现实测命令

```powershell
cd D:\xunfei\triple-U

$env:TEMP='D:\xunfei\triple-U\.tmp'
$env:TMP='D:\xunfei\triple-U\.tmp'

D:\Anaconda3\envs\dxtorch\python.exe scripts/benchmark_cognitive_models.py --models sakt --folds 5 --out reports
D:\Anaconda3\envs\dxtorch\python.exe scripts/benchmark_cognitive_models.py --models dkt --folds 5 --out reports
```

关联产物：

- `reports/benchmark_20260623_201019.json`
- `reports/benchmark_20260623_201019.md`
- `reports/benchmark_20260623_201927.json`
- `reports/benchmark_20260623_201927.md`
- `reports/benchmark_20260620_210118.json`（同脚本、同 5-fold、Naive/BKT/DINA 历史实测）

## 4. 五模型真实对照

| 模型 | 实测 AUC | 实测 RMSE | 实测 Accuracy | 说明 |
|------|----------|-----------|----------------|------|
| Naive | 0.5955 ± 0.0025 | 0.4939 ± 0.0056 | 0.6548 ± 0.0094 | 5-fold full |
| BKT | 0.6666 ± 0.0067 | 0.4625 ± 0.0032 | 0.6627 ± 0.0081 | 5-fold full |
| DINA | 0.6958 ± 0.0103 | 0.4541 ± 0.0009 | 0.7051 ± 0.0032 | 5-fold full |
| DKT | 0.8021 ± 0.0056 | 0.4073 ± 0.0020 | 0.7568 ± 0.0020 | 2026-06-23 重跑 |
| **SAKT** | **0.8381 ± 0.0121** | **0.3752 ± 0.0092** | **0.8325 ± 0.0128** | 2026-06-23 重跑 |

结论：

- SAKT 在当前仓库这套 ASSISTments-2009 口径下，是五模型里最优的 AUC / RMSE / Accuracy。
- SAKT 相比 DKT 的优势不是“预期”，而是这次 full 5-fold 真跑出来的结果：
  - AUC: `0.8381 - 0.8021 = +0.0360`
  - RMSE: `0.3752 - 0.4073 = -0.0321`
  - Accuracy: `0.8325 - 0.7568 = +0.0757`

## 5. SAKT fold 级结果

| Fold | AUC | RMSE | Accuracy | 训练时间(s) | 测试样本数 |
|------|-----|------|----------|-------------|-----------|
| 1 | 0.8443 | 0.3718 | 0.8294 | 38.95 | 66988 |
| 2 | 0.8577 | 0.3633 | 0.8457 | 35.01 | 65755 |
| 3 | 0.8217 | 0.3834 | 0.8211 | 35.17 | 61667 |
| 4 | 0.8345 | 0.3882 | 0.8173 | 35.02 | 73443 |
| 5 | 0.8321 | 0.3693 | 0.8488 | 35.31 | 68810 |

汇总：

- mean AUC: `0.8381`
- std AUC: `0.0121`
- overall AUC on all test samples: `0.8378`
- total wall time: `232.00s`

## 6. DKT fold 级补充

| Fold | AUC | RMSE | Accuracy | 训练时间(s) |
|------|-----|------|----------|-------------|
| 1 | 0.8072 | 0.4041 | 0.7597 | 60.30 |
| 2 | 0.8054 | 0.4075 | 0.7570 | 61.89 |
| 3 | 0.7913 | 0.4094 | 0.7547 | 79.43 |
| 4 | 0.8026 | 0.4091 | 0.7546 | 87.76 |
| 5 | 0.8041 | 0.4063 | 0.7582 | 107.09 |

## 7. 答辩可直接使用的话术

30 秒版本：

> 我们不是只把 SAKT 接进来了，而是按 ASSISTments-2009 的 student-wise 5-fold 全量跑了真实 benchmark。结果是：Naive 0.5955，BKT 0.6666，DINA 0.6958，DKT 0.8021，而 SAKT 达到 0.8381，是当前仓库五模型里最好的。也就是说，自注意力知识追踪在我们这套真实数据和评测口径下，不是“预期更强”，而是已经实测更强。

解释性版本：

> SAKT 相比 DKT 的优势不仅在于 Transformer 并行训练，更在于它对稀疏长序列的建模更稳。我们这次 full 5-fold 的实测结果也支持这一点：SAKT 的 AUC 比 DKT 高 0.036，RMSE 更低，Accuracy 更高。

## 8. 注意事项

- 这份文档已经从 smoke 结果切换为 full 5-fold 实测结果。
- `Naive / BKT / DINA` 复用了同脚本、同协议的历史 full benchmark 产物；`DKT / SAKT` 于 2026-06-23 在当前环境重新跑出。
- 如果后续再次重跑，优先以 `reports/benchmark_*.json` 为准，不要手抄旧的预期值。
