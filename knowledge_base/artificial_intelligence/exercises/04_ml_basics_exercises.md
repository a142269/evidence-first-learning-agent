---
chapter_ref: "04"
chapter_title: "机器学习基础"
kp_refs: [ml_basics, supervised_learning]
bloom_focus: [Apply, Analyze, Evaluate]
total_points: 30
deadline_hint: 本章配套学习时长 8 学时
---

# 机器学习基础 · 章节练习

> **配套**：A3 章节 §04 机器学习基础  
> **配对代码**：`code_examples/01_linear_regression.py`、`code_examples/02_random_forest.py`

---

## 一、选择题（每题 2 分，共 10 分）

### Q1（Understand）
监督学习的核心特征是：

- A. 没有标签数据
- B. 训练数据同时包含特征与标签
- C. 仅依赖奖励信号
- D. 通过无监督聚类发现结构

<details><summary>答案</summary>B</details>

### Q2（Apply）
训练集 99% 准确率、测试集 60% 准确率，最可能的诊断是：

- A. 欠拟合
- B. 过拟合
- C. 数据太少导致偏差
- D. 类别不平衡

<details><summary>答案</summary>B</details>

### Q3（Analyze）
K 折交叉验证的主要目的是：

- A. 增加训练数据量
- B. 减小单次划分的偶然性，得到更稳定的泛化估计
- C. 让模型训练更快
- D. 优化超参数搜索空间

<details><summary>答案</summary>B</details>

### Q4（Apply）
给定 $y = 3x + 2 + \epsilon$，训练 `LinearRegression` 后发现 `model.coef_=3.05`，可能的原因是：

- A. 模型写错
- B. 合理噪声范围内（与真值 3 偏差 < 0.1）
- C. 需要标准化
- D. 应改用 SVM

<details><summary>答案</summary>B</details>

### Q5（Evaluate）
在数据集只有 100 个样本时，下列哪种做法最合适？

- A. 增大神经网络参数量
- B. 用 K 折交叉验证 + 简单模型 + 强正则
- C. 用 99% 训练、1% 测试
- D. 直接用 GPU 训练更大的模型

<details><summary>答案</summary>B</details>

---

## 二、简答题（每题 5 分，共 10 分）

### Q6（Apply）
解释"偏差-方差权衡"，并各举一个欠拟合 / 过拟合的判定方法。

<details><summary>参考答案</summary>

- 偏差（bias）：模型对真实函数的近似能力；高偏差→欠拟合，训练 / 测试误差都高
- 方差（variance）：模型对训练数据波动的敏感度；高方差→过拟合，训练低 / 测试高
- 判定方法：学习曲线（误差随样本量变化）、验证集 vs 训练集差距

</details>

### Q7（Analyze）
为什么随机森林一般比单棵决策树泛化更好？请从"集成"和"多样性"两个角度回答。

<details><summary>参考答案</summary>

- 集成：通过 bagging 平均多棵树，减小单棵树方差
- 多样性：每棵树看不同 bootstrap 样本 + 随机子特征，避免同时犯同样错

</details>

---

## 三、编程题（10 分）

### Q8（Create · 难度 3）
改写 `01_linear_regression.py`：

1. 把 `noise` 从 0.5 调到 2.0
2. 用 `train_test_split` 改为 `random_state=0`
3. 报告新的 R² 与 coefficient，与原文对比

提交：在 PR 中给出 `01_linear_regression_v2.py` 与说明 markdown。

<details><summary>评分要点</summary>

- 代码能跑通（5 分）
- 实验记录 R² / coef 变化（3 分）
- 总结噪声提升对模型的影响（2 分）

</details>

---

> **配套自检**：完成本练习后请在 A3 `ResourcesView` 中查看 §04 章，下方应有"本章练习"入口。
