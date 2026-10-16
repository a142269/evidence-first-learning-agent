---
chapter_id: '13'
slug: supervised_learning
title: 监督学习
kp_ids:
- AI_005
- AI_004
bloom_focus:
- Understand
- Apply
prerequisites:
- '01'
- '02'
estimated_minutes: 55
---

# 13: 监督学习 · 从数据中寻找规律的标尺

> **Bloom 层级**: Understand → Apply
> **建议学时**: 55 分钟
> **前置知识**: 01-机器学习基础、02-数学基础

## 学习目标
1. 明确区分监督学习中的回归与分类两大核心任务。
2. 掌握线性回归、逻辑回归的数学直觉、损失函数及优化方法。
3. 能够针对具体业务场景选择合适的评估指标（如 MSE、F1-Score、ROC-AUC）。
4. 深入理解偏差-方差权衡（Bias-Variance Tradeoff）及其对模型调优的指导意义。
5. 了解在 A3 个性化学习系统中，监督学习如何支持学生成绩预测与偏好分类。

## 13.1 监督学习的定义与直觉
**监督学习（Supervised Learning）** 是机器学习中最成熟、应用最广泛的分支。
**定义**：给定一个包含特征和目标标签的训练集 $D = \{(x_i, y_i)\}_{i=1}^N$，算法的目标是学习到一个映射函数 $f: X \to Y$，使得该函数能够在未见过的新样本上做出准确预测（泛化能力）。
**直觉解释**：就像学生做带有标准答案的练习册。每做完一题（输入 $x$），学生给出自己的答案（预测 $\hat{y}$），然后对照背后的标准答案（标签 $y$），发现错误（计算损失）并改正自己的解题思路（更新模型参数）。

监督学习主要分为两大子任务：
| 子任务 | 输出空间 | 例子 |
|--------|---------|------|
| **回归 (Regression)** | 连续的实数 / 向量 | 房价预测、明天温度预测、学生期末考试具体分数预测 |
| **分类 (Classification)** | 离散的类别 | 垃圾邮件拦截、图像识别、判断学生是否会流失 |

**教育场景案例**：
在 A3 系统中，我们拥有海量的学生历史做题数据。当我们需要预测小明下周的单元测试分数时，这是一个**回归**问题；当我们需要预测小明是否会在一个月后放弃该课程时，这是一个**分类**问题。

## 13.2 线性回归与正则化
线性回归是最基础的回归模型。
**模型公式**：$\hat{y} = w^\top x + b$。它假设输入特征与输出目标之间存在线性关系。
**损失函数**：通常使用均方误差（MSE）。
$$\mathcal{L}(w, b) = \frac{1}{N}\sum_{i=1}^N (w^\top x_i + b - y_i)^2$$

在实际工程中，为了防止模型在训练集上过拟合，我们会在损失函数中加入惩罚项，即**正则化（Regularization）**：
- **L2 正则化（岭回归 Ridge）**：$\mathcal{L} + \lambda \|w\|_2^2$。惩罚过大的权重，使模型更平滑。
- **L1 正则化（Lasso）**：$\mathcal{L} + \lambda \|w\|_1$。倾向于产生稀疏权重（很多权重变为 0），自带特征选择功能。

## 13.3 逻辑回归 (Logistic Regression)
虽然名字里带有“回归”，但它实际上是一个**二分类**算法。
**直觉**：把线性回归的输出（可能是无穷大或负无穷）塞进一个 Sigmoid 函数里，将其强行挤压到 $(0, 1)$ 区间内，从而解释为概率。
$$p(y=1|x) = \sigma(w^\top x + b) = \frac{1}{1 + e^{-(w^\top x + b)}}$$
**损失函数**：对于概率输出，我们使用**二元交叉熵（Log-Loss）**：
$$\mathcal{L} = -\frac{1}{N}\sum_i [y_i \log p_i + (1-y_i)\log(1-p_i)]$$

## 13.4 模型评估指标
评估模型不能只看“感觉”，必须依靠客观指标。
**对于回归任务**：
- **MAE**：平均绝对误差，对离群点（异常值）比较鲁棒。
- **MSE/RMSE**：均方误差/均方根误差，对大误差惩罚极重。

**对于分类任务**：
假设我们要预测学生是否作弊（正类=作弊，负类=正常）。
- **Accuracy (准确率)**：所有预测对的比例。在数据极度不平衡时（如 99% 的人都没作弊）毫无意义，因为全猜“正常”也有 99% 准确率。
- **Precision (精确率)**：$\frac{TP}{TP+FP}$。系统报警说作弊的人里，有多少是真的作弊。
- **Recall (召回率)**：$\frac{TP}{TP+FN}$。真正作弊的人里，系统抓出了多少。
- **F1-Score**：精确率和召回率的调和平均，综合评估模型。
- **ROC-AUC**：衡量模型在所有可能的分类阈值下的综合排序能力，0.5 代表瞎猜，1.0 代表完美。

## 13.5 偏差-方差权衡 (Bias-Variance Tradeoff)
在机器学习中，测试误差可以被数学分解为三部分：偏差、方差和不可避免的噪声。
$$\mathbb{E}[(y - \hat{y})^2] = \text{Bias}^2 + \text{Variance} + \sigma^2$$
- **高偏差（欠拟合）**：模型太简单，连训练集都学不好（比如用一条直线去拟合复杂的波浪曲线）。**对策**：增加模型复杂度、增加特征。
- **高方差（过拟合）**：模型太复杂，死记硬背了训练集里的每一个噪声点，一遇到新数据就歇菜。**对策**：增加数据量、增加正则化（L1/L2）、简化模型。

## 13.6 常见误区
- **误区 1：在类别极度不平衡的数据集上，依然把 Accuracy 当作唯一优化目标。**
  - **为什么错**：如果 100 个学生里只有 1 个不及格，模型只要永远预测“及格”，Accuracy 就是 99%，但这个模型毫无价值。此时必须看 Recall 或 F1。
- **误区 2：在测试集上反复调整超参数。**
  - **为什么错**：测试集只能在项目最后进行一次性评估（One-shot Evaluation）。如果你看着测试集的结果来调参，实际上发生了“数据泄露”，使得测试集变成了验证集，最终模型上线必然翻车。
- **误区 3：所有数据混在一起，直接调用 `train_test_split` 切分，即使是时间序列数据。**
  - **为什么错**：时间序列数据（如预测明天的股票、明天的考试分数）包含了强烈的时序依赖。如果随机切分，就是用未来的数据预测过去（穿越），必须使用 `TimeSeriesSplit` 进行按时间截断。

## 13.7 可运行示例：解决类别不平衡的逻辑回归
以下自包含的 Python 示例展示了在一个严重类别不平衡的数据集上，如何使用 `class_weight="balanced"` 来拯救糟糕的召回率。

```python
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, recall_score, precision_score
from sklearn.model_selection import train_test_split
from sklearn.datasets import make_classification

# 1. 构造极度不平衡的数据集 (95% 负例，5% 正例)
X, y = make_classification(
    n_samples=1000, n_features=20, n_informative=5, 
    weights=[0.95], random_state=42
)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 2. 对照组：普通的逻辑回归
clf_standard = LogisticRegression()
clf_standard.fit(X_train, y_train)
y_pred_std = clf_standard.predict(X_test)

# 3. 实验组：带类别权重平衡的逻辑回归
clf_balanced = LogisticRegression(class_weight="balanced")
clf_balanced.fit(X_train, y_train)
y_pred_bal = clf_balanced.predict(X_test)

# 4. 打印对比结果
def print_metrics(name, y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    rec = recall_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred)
    print(f"[{name}] 准确率: {acc:.3f} | 召回率: {rec:.3f} | 精确率: {prec:.3f}")

print("=== 类别不平衡处理对比 ===")
print_metrics("普通逻辑回归", y_test, y_pred_std)
print_metrics("平衡逻辑回归", y_test, y_pred_bal)

# 输出观察：普通回归准确率很高，但召回率极低（几乎抓不到少数类）；
# 平衡回归牺牲了一点准确率，但大幅提升了少数类的召回率。
```

## 13.8 本章小结
1. 监督学习通过“特征-标签”对训练模型，核心分为回归（连续值）与分类（离散值）两大任务。
2. 线性模型（如线性回归和逻辑回归）虽然简单，但通过正则化和特征工程，在工业界依然占据极高比重。
3. 评估指标的选择决定了模型优化的方向，处理类别不平衡和选择合适的验证策略（交叉验证）是工程落地的关键。
4. 深刻理解偏差与方差的权衡，是每个算法工程师必须具备的直觉。

## 13.11 可运行代码示例

下面用 NumPy 实现线性回归（闭式解）与逻辑回归（梯度下降）两个经典监督学习模型，并对比均方误差与对数损失。

```python
'''13 章 · 线性回归 + 逻辑回归 — NumPy 自包含'''
import numpy as np

np.random.seed(0)

# === 1. 线性回归：闭式解 θ = (XᵀX)⁻¹Xᵀy ===
n, d = 100, 3
X = np.random.randn(n, d)
true_w = np.array([2.0, -1.0, 0.5])
y = X @ true_w + np.random.randn(n) * 0.1   # 加少量噪声
X1 = np.hstack([X, np.ones((n, 1))])        # 加偏置列
w_lr = np.linalg.inv(X1.T @ X1) @ X1.T @ y
print("线性回归学到的权重:", np.round(w_lr, 3))
print("真实权重:            ", np.round(np.append(true_w, 0.0), 3))
pred = X1 @ w_lr
mse = ((pred - y) ** 2).mean()
print(f"训练 MSE: {mse:.5f}\n")

# === 2. 逻辑回归：二分类 + 梯度下降 ===
X = np.random.randn(200, 2)
y = (X[:, 0] + X[:, 1] > 0).astype(int)    # 简单线性可分

def sigmoid(z): return 1.0 / (1.0 + np.exp(-z))
W = np.zeros(2); b = 0.0
lr = 0.1
for epoch in range(200):
    z = X @ W + b
    p = sigmoid(z)
    grad_w = X.T @ (p - y) / len(y)
    grad_b = (p - y).mean()
    W -= lr * grad_w
    b -= lr * grad_b
    if epoch % 50 == 0:
        loss = -(y * np.log(p + 1e-9) + (1-y) * np.log(1-p + 1e-9)).mean()
        print(f"epoch {epoch:3d}  loss={loss:.4f}")

# 评估
acc = ((sigmoid(X @ W + b) >= 0.5).astype(int) == y).mean()
print(f"\n逻辑回归训练准确率: {acc:.3f}")
print("学到的决策边界: y = -", round(W[0]/W[1], 3), "* x1")
```
\n## 13.9 练习思考
1. **指标权衡**：在 A3 系统的“防止学生流失预警”模块中，你认为应优先提升模型的 Precision（精确率）还是 Recall（召回率）？为什么？
2. **算法选择**：如果在预测房价的任务中，发现数据集中包含少量极端昂贵的异常豪宅，你更倾向于选择 MAE 还是 MSE 作为损失函数？
3. **特征工程**：逻辑回归本质上是一个线性分类器。如何通过简单的特征工程（不换模型），让逻辑回归能够解决非线性的环形分布数据？
4. **过拟合诊断**：如果你发现模型在训练集上的误差非常低，但在验证集上的误差很高。请列出三种降低这种过拟合的具体操作。

## 13.10 拓展阅读
- 机器学习基础必读教材：周志华《机器学习》（西瓜书）第三章 线性模型。
- 模型评估与交叉验证指南：查阅 `Scikit-learn` 官方文档中的 `Model Evaluation` 和 `Cross-validation` 章节。
- 深入理解偏差-方差权衡：检索相关的视觉交互演示 `Understanding the Bias-Variance Tradeoff`。
