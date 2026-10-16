---
chapter_id: '15'
slug: decision_trees_ensemble
title: 决策树与集成学习
kp_ids:
- AI_005_02
- AI_005
bloom_focus:
- Apply
- Analyze
prerequisites:
- '13'
estimated_minutes: 55
---

# 15: 决策树与集成学习 · 化繁为简与群体智慧

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 55 分钟
> **前置知识**: 13-监督学习

## 学习目标
1. 解释单棵决策树的节点划分准则（基尼不纯度、信息熵）及其可解释性优势。
2. 阐述为何决策树极易发生过拟合，并掌握相关的剪枝和超参控制手段。
3. 比较 Bagging（如随机森林）与 Boosting（如 XGBoost）两种集成范式在降低方差与偏差上的底层逻辑。
4. 应用 SHAP 值等工具打开集成学习模型的“黑盒”，提供业务可解释性。
5. 结合 A3 个性化学习场景，设计一个使用 XGBoost 进行学生成绩预测和归因反馈的模型。

## 15.1 决策树的直觉与划分
**决策树（Decision Tree）** 是一种模仿人类决策过程的白盒算法。
**直觉**：就像你在玩“20个问题”猜谜游戏。为了最快猜出答案，你会优先问最能排除错误选项的“好问题”（比如“它是活的吗？”而不是“它的名字有几个字母？”）。
决策树通过构建一系列 *if-else* 规则将特征空间切分，最终落在“叶子节点”给出预测。

**三大核心优势**：
- **极强的可解释性**：业务专家能直接读懂生成的规则。
- **无需特征缩放**：对数据的尺度（量纲）完全不敏感，不需要做归一化。
- **开箱即用**：天生支持处理混合类型（数值+类别型），对缺失值有较好容忍。

**节点划分准则**：
每次分裂时，模型都在寻找一个最能“降低混乱度”的切分点。
- **信息熵（Entropy）**：衡量系统的混乱程度，$H = -\sum_k p_k \log_2 p_k$。
- **基尼不纯度（Gini Impurity）**：CART 算法默认使用的准则，计算比对数更快，$G = 1 - \sum_k p_k^2$。

## 15.2 过拟合的魔咒与剪枝
如果任由决策树生长而不加约束，它最终会为训练集里的每一个异常点（甚至噪声）单独开辟一片叶子，达到 100% 的训练准确率，但一上线就彻底崩溃。这被称为**过拟合**。

**控制（剪枝）手段**：
- `max_depth`：限制树的最大深度。
- `min_samples_split`：一个节点至少包含多少个样本，才允许继续分裂。
- `min_samples_leaf`：一个叶子节点至少必须包含多少个样本。

## 15.3 集成学习：为何 1+1>2
因为单棵决策树极其容易过拟合（高方差）且预测不稳定，所以催生了**集成学习（Ensemble Learning）**——“三个臭皮匠，顶个诸葛亮”。

1. **Bagging (装袋法)**：代表作是**随机森林 (Random Forest)**。
   - **思想**：并行训练很多棵独立的深层决策树，最后大家投票（分类）或取平均（回归）。
   - **怎么做到独立？** 利用**自助采样 (Bootstrap)** 让每棵树看不同的数据；每次分裂只允许看**随机的一小部分特征**。
   - **效果**：大幅降低了模型的**方差**，极难过拟合，是“开箱即用”的神器。

2. **Boosting (提升法)**：代表作是 **GBDT、XGBoost、LightGBM**。
   - **思想**：串行训练许多棵较浅的树。第一棵树犯了错，第二棵树就专门盯着第一棵树犯错的地方（残差或负梯度）去拟合，层层递进。
   - **效果**：大幅降低了模型的**偏差**，在各大 Kaggle 表格数据竞赛中常年霸榜。

## 15.4 模型解释：SHAP 值
当几百棵树集成在一起时，模型变成了“黑盒”。如何向用户解释？
**SHAP (SHapley Additive exPlanations)** 基于博弈论，能够量化地解释“到底是因为什么导致了这个预测”。它不仅能告诉你全局哪些特征最重要，还能精确到单条数据：“小明这次预测不及格，主要是因为‘上次作业未交’这个特征拉低了 20 分”。

## 15.5 教育智能体场景案例
在 A3 项目中，我们需要在学生做完阶段测试后，给出**诊断性反馈**。
- **选型**：相比于深度学习黑盒，我们选择 **XGBoost** 作为成绩预测模型，不仅因为它在表格数据（如做题时间、错题历史率、视频观看比）上精度极高。
- **归因机制**：预测完成后，`Evaluator Agent` 在后台调用 SHAP 库分析 XGBoost 的预测结果。
- **反馈闭环**：如果 SHAP 显示“视频跳出率高”是对低分贡献最大的特征，Agent 就会自动向学生发送一条柔性提示：“系统发现你最近跳过了很多讲解视频，建议先把 05 章节的视频补完再做题哦。”

## 15.6 常见误区
- **误区 1：既然 XGBoost 这么强，那就把所有数据都喂给 XGBoost，包括图片和文本。**
  - **为什么错**：树模型天生无法处理图像（CNN 是王者）和高维稀疏的文本（Transformer 擅长）。树模型的主战场是结构化的表格数据（Tabular Data）。
- **误区 2：在训练随机森林时，必须对特征进行归一化（StandardScaler）。**
  - **为什么错**：树模型的每一次分裂都是在对单个特征的值进行大小比较（如 `age < 30`），特征的绝对量级不影响比较结果。归一化不仅多此一举，还会丧失分裂阈值的物理意义（可解释性）。
- **误区 3：增加 Boosting 模型（如 XGBoost）的树的数量，模型只会越来越准。**
  - **为什么错**：与随机森林增加树只是让投票更稳定不同，Boosting 是在不断拟合残差。如果树的数量过多，它最终连噪声也会拟合，引发严重的过拟合。必须使用早期停止（Early Stopping）和控制学习率。

## 15.7 可运行示例：使用随机森林进行分类评估
以下代码演示了如何使用 scikit-learn 训练一个随机森林，并通过调整 `min_samples_leaf` 来控制过拟合。

```python
import numpy as np
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# 1. 构造一个容易过拟合的复杂分类数据集
X, y = make_classification(n_samples=500, n_features=15, n_informative=10, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

# 2. 对照组：不受限制疯长的随机森林 (容易过拟合)
rf_unconstrained = RandomForestClassifier(
    n_estimators=100, 
    max_depth=None,           # 不限制深度
    min_samples_leaf=1,       # 允许叶子节点只有一个样本
    random_state=42
)
rf_unconstrained.fit(X_train, y_train)
acc_train_unc = accuracy_score(y_train, rf_unconstrained.predict(X_train))
acc_test_unc = accuracy_score(y_test, rf_unconstrained.predict(X_test))

# 3. 实验组：添加防过拟合约束的随机森林
rf_constrained = RandomForestClassifier(
    n_estimators=100,
    max_depth=6,              # 限制最大深度
    min_samples_leaf=5,       # 叶子必须有至少 5 个样本支撑
    random_state=42
)
rf_constrained.fit(X_train, y_train)
acc_train_con = accuracy_score(y_train, rf_constrained.predict(X_train))
acc_test_con = accuracy_score(y_test, rf_constrained.predict(X_test))

print("=== 随机森林防过拟合效果 ===")
print("【未受限模型】")
print(f"训练集准确率: {acc_train_unc*100:.1f}% (完全记住了数据)")
print(f"测试集准确率: {acc_test_unc*100:.1f}%")
print("\n【加约束模型】")
print(f"训练集准确率: {acc_train_con*100:.1f}%")
print(f"测试集准确率: {acc_test_con*100:.1f}% (泛化能力更好或持平)")
```

## 15.8 本章小结
1. 单一决策树直观但易过拟合；集成学习通过组合弱学习器，实现了强大的泛化能力。
2. Bagging 核心在于“多子重抽样+并行投票”，有效降低模型方差（如 Random Forest）。
3. Boosting 核心在于“针对前一次错误重点学习”，有效降低模型偏差（如 XGBoost）。
4. 在教育领域的表格特征挖掘中，借助 SHAP 等可解释性工具，集成树模型不仅能输出预测，还能直接驱动 Agent 给学生的诊断反馈。

## 15.11 可运行代码示例

下面用 NumPy 手写决策树最核心的"信息增益"计算，并对一个玩具数据集演示如何选最优划分特征。完整可运行。

```python
'''15 章 · 决策树信息增益计算 — NumPy 自包含'''
import numpy as np

# 玩具数据集：天气 → 是否打球
X = np.array([
    ["晴", "热",  "高", "弱"],
    ["晴", "热",  "高", "强"],
    ["阴", "热",  "高", "弱"],
    ["雨", "温",  "高", "弱"],
    ["雨", "凉爽","正常","弱"],
    ["雨", "凉爽","正常","强"],
    ["阴", "凉爽","正常","强"],
    ["晴", "温",  "高", "弱"],
    ["晴", "凉爽","正常","弱"],
    ["雨", "温",  "正常","弱"],
    ["晴", "温",  "正常","强"],
    ["阴", "温",  "高", "强"],
    ["阴", "热",  "正常","弱"],
    ["雨", "温",  "高", "强"],
])
y = np.array([0,0,1,1,1,0,1,0,1,1,1,1,1,0])  # 1=打球, 0=不打

def entropy(y):
    p = np.bincount(y) / len(y)
    p = p[p > 0]
    return -float((p * np.log2(p)).sum())

def info_gain(y, groups):
    '''y 是父节点 labels，groups 是按特征划分后的若干子集 labels 列表'''
    parent = entropy(y)
    n = len(y)
    child = sum(len(g) / n * entropy(g) for g in groups)
    return parent - child

# 遍历每个特征（列），尝试每种取值划分
for col in range(X.shape[1]):
    print(f"\n特征 {col} ({X[0, col]} 等取值):")
    parent_h = entropy(y)
    print(f"  父节点熵: {parent_h:.3f}")
    for val in np.unique(X[:, col]):
        groups = [y[X[:, col] == v] for v in np.unique(X[:, col])]
        ig = info_gain(y, [y[X[:, col] == v] for v in np.unique(X[:, col])])
        print(f"  划分: {X[0, col]} = {val}  → 信息增益 = {ig:.3f}")

# 实际决策树会选所有特征中信息增益最大的那个作为根节点
print("\n→ 决策树 ID3/C4.5/CART 都基于信息增益（或其变体 Gini）。")
print("→ 集成学习（RF/XGBoost）通过 Bagging/Boosting 把多棵树组合，性能远超单棵。")
```
\n## 15.9 练习思考
1. **理论对比**：请通俗地解释一下“降低方差”和“降低偏差”分别是指什么？为什么说随机森林通常用于降低方差？
2. **场景设计**：假设你要用 LightGBM 来预测学生是否会复购下学期的课程。数据集中有 30% 是数值型（做题时间），70% 是类别型特征（所在省份、选择的难度级别）。在预处理阶段，你该如何处理这些类别特征？
3. **算法特性**：在随机森林构建一棵树的时候，为什么每次节点分裂时不是扫描所有特征，而只扫描随机抽取的 $\sqrt{d}$ 个特征？如果不这么做会怎样？
4. **模型调试**：如果发现训练好的 XGBoost 在验证集上严重过拟合，除了减小树的最大深度（max_depth），你还能调整哪两个关键的超参数？

## 15.10 拓展阅读
- Kaggle 冠军算法巡礼：检索 `XGBoost: A Scalable Tree Boosting System` (Tianqi Chen)
- 可解释 AI 神器：查阅 `SHAP (SHapley Additive exPlanations) Github 官方文档`
- 树模型与深度学习在表格数据上的对抗：检索论文 `Tabular Data: Deep Learning is Not All You Need`
