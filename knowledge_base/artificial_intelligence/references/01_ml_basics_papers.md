---
title: "A Few Useful Things to Know About Machine Learning"
authors: [Pedro Domingos]
year: 2012
url: https://cacm.acm.org/research/a-few-useful-things-to-know-about-machine-learning/
kp_refs: [ml_basics, decision_trees]
summary_zh: 经典 ML 实践指南：数据 vs 算法、数据集大小、特征工程、过拟合、泛化等 12 条工程师必读经验。
---

# A Few Useful Things to Know About Machine Learning（2012）

> **面向读者**：刚开始用 scikit-learn 做作业 / 比赛 / 教学 demo 的同学
> **配套章节**：§01 机器学习基础 / §15 决策树（部分观点适用于所有监督学习）

## 摘要

Pedro Domingos 在 *Communications of the ACM* 上发表的这篇综述，是 ML 工程实践领域
被引用最广的"非技术"文章之一。它不展开公式，而是把过去三十年 ML 实践中沉淀下来的
**12 条经验**系统整理成文：learning = representation + evaluation + optimization，
以及 "data alone is not enough"、"intricate models = overfitting danger"、"more data
beats a cleverer algorithm"、"ensembles are the winningest"、"simple models win more
than they should" 等等。

文章主线是「**机器学习项目成功 90% 取决于数据与特征工程，而不是模型选型**」。这条
结论与 A3 系统里 EvaluatorAgent 对学生学习数据的诊断结论高度一致。

## 核心要点

| # | 经验 | 与 A3 / 教学对应 |
|---|------|-----------------|
| 1 | Learning = Representation + Evaluation + Optimization | A3 的 TutorAgent 三段式 |
| 2 | It's generalization that counts | Bloom「应用」层级以上 |
| 3 | Data alone is not enough | 必须有先验 / 特征 / 模型族 |
| 4 | Intuition fails in high dimensions | 维度灾难演示 |
| 5 | Theoretical guarantees are not what they seem | 期望 vs 现实差距 |
| 6 | Feature engineering is the key | A3 数据预处理模块 |
| 7 | More data beats a cleverer algorithm | data augmentation 策略 |
| 8 | Learn many models, not just one | 集成学习（RF / Boosting） |
| 9 | Simplicity does not imply accuracy | Occam's razor 误区 |
| 10 | Representable does not imply learnable | 模型容量 ≠ 可学 |
| 11 | Correlation does not imply causation | 因果 vs 相关 |
| 12 | Beware the intrinsic limits of ML | 安全 / 公平 / 鲁棒 |

**关键公式（学习本体三件套）**：

$$
\text{Machine Learning} = \text{Representation} + \text{Evaluation} + \text{Optimization}
$$

其中 Representation 对应模型族（如决策树、SVM、神经网络），Evaluation 对应损失函数
（0-1 loss、logloss、hinge loss），Optimization 对应求解算法（梯度下降、SGD、
贪心分裂等）。

## 与 A3 系统关联

- **EvaluatorAgent**：文中第 8 条「Learn many models, not just one」直接对应
  A3 的 `EvaluatorAgent` 同时跑 RF / SVM / MLP / 朴素贝叶斯并投票给出诊断结论，
  而非依赖单一模型。`scripts/relabel_bloom_6x3.py` 中也用到了集成的思想。
- **Pedagogical Safety**：第 12 条「固有局限」对应 A3 的 `PedagogicalSafety` 守卫：
  当学生追问"模型一定能答对"时，A3 必须主动声明 ML 的不确定性与边界。
- **Claim Ledger**：第 3 条「数据非万能」要求教师 agent 在回答中**附带引用**，
  这与 A3 的 `Claim Ledger`（每次断言带可追溯证据）机制一致。
- **TutorAgent 个性化**：第 6 条「特征工程」指引 TutorAgent 在分析学生错题时，
  把"错因"编码为可计算的特征，而不是停留在自然语言描述。

## 推荐片段

1. **§1 Introduction** —— 三段式总览，5 分钟读完
2. **§2 Learning = Representation + Evaluation + Optimization** —— 必读
3. **§5 Intuition Fails in High Dimensions** —— 配合 A3 §01 章节的维度灾难 demo
4. **§8 More Data Beats a Cleverer Algorithm** —— 推荐在数据增强章节引用
5. **§10 Representable Does Not Imply Learnable** —— 与神经网络学习理论章节呼应

## 中文翻译参考

- 社区译文：https://www.csdn.net/article/2015-01-13/2813518
- 配合 A3 §01 章 "Why ML works" 阅读效果最佳。

> **教学小贴士**：建议让 A3 TutorAgent 在学生首次接触决策树章节时引用本文，作为
> 「为什么我们要先学 ML 通论再学具体算法」的论证。