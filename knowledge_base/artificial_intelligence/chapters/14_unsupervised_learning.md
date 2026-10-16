---
chapter_id: '14'
slug: unsupervised_learning
title: 无监督学习
kp_ids:
- AI_016
bloom_focus:
- Understand
- Apply
prerequisites:
- '01'
estimated_minutes: 50
---

# 14: 无监督学习 · 在无序数据中发现隐藏结构

> **Bloom 层级**: Understand → Apply
> **建议学时**: 50 分钟
> **前置知识**: 01-机器学习基础

## 学习目标
1. 区分无监督学习与监督学习的本质差异，并列举其三大核心任务（聚类、降维、密度估计）。
2. 阐述 KMeans、DBSCAN 等主流聚类算法的工作原理、适用边界及优缺点。
3. 比较主成分分析（PCA）与 t-SNE、UMAP 等非线性降维技术在可视化及特征工程中的不同应用。
4. 运用自编码器（Autoencoder）和隔离森林（Isolation Forest）解决数据降维与异常检测问题。
5. 结合 A3 项目场景，设计无监督学习在学生群体分层与异常行为检测中的落地应用。

## 14.1 无监督学习的定义与价值
在现实世界中，获取海量数据是容易的，但为这些数据打上准确标签（Label）却是极其昂贵的。
**定义**：**无监督学习（Unsupervised Learning）** 仅给定特征数据集 $X = \{x_i\}$，而没有任何监督信号（标签 $y$），算法的目标是自主发现数据背后的隐藏结构、分布模式或相似性群体。

**三大核心任务**：
| 任务 | 目标描述 | 代表算法 |
|------|---------|---------|
| **聚类 (Clustering)** | 物以类聚。将相似的样本分到同一个组里。 | KMeans、DBSCAN、高斯混合模型(GMM) |
| **降维 (Dimensionality Reduction)** | 剔除冗余，将高维数据压缩为最具代表性的低维特征。 | PCA、t-SNE、UMAP、自编码器 |
| **密度/异常检测 (Anomaly Detection)** | 学习正常数据的分布，从而把不合群的“怪胎”抓出来。 | Isolation Forest、One-Class SVM |

**教育场景案例**：
在 A3 系统中，我们拥有数以万计的未标注学习行为日志。利用**聚类**，我们可以自动将学生分为“考前突击型”、“稳扎稳打型”等群体；利用**异常检测**，我们可以迅速识别出恶意刷题爬虫或存在作弊嫌疑的异常交互行为。

## 14.2 KMeans：最经典的聚类算法
KMeans 是一种硬聚类算法，它假设数据可以被分为 K 个簇，且每个簇呈现各向同性的球状分布。
**直觉原理**：
1. **初始化**：随机在地图上扔 K 个中心点。
2. **分配 (E 步)**：每个数据点寻找离自己最近的中心点，并加入那个阵营。
3. **更新 (M 步)**：每个阵营重新计算其内部所有点的中心位置，把中心点移过去。
4. **迭代**：重复步骤 2 和 3，直到中心点不再移动为止。

**如何选择 K 值？**
最常用的是“肘部法则（Elbow Method）”：计算不同 K 值下的簇内误差平方和（Inertia），随着 K 增加 Inertia 会下降，下降速度变缓的那个“拐点”往往就是最佳的 K 值。也可以参考轮廓系数（Silhouette Score）。

## 14.3 DBSCAN：基于密度的聚类
KMeans 的最大弱点是必须事先指定 K，且面对非球状（如弯月形）的簇时无能为力。**DBSCAN** 完美解决了这些问题。
**直觉解释**：
想象一片人群。只要一个人周围（半径 $\epsilon$ 内）有不少于特定数量（MinPts）的同伴，他就是“核心点”。所有相邻的核心点及其触手可及的人会连成一片，形成一个巨大的簇。那些孤立在荒野中，周围没有任何人的点，就会被标记为“噪声（异常值）”。
- **优势**：无需指定簇的数量 K；能发现任意形状的簇；天然抗噪。

## 14.4 降维：PCA 与 t-SNE/UMAP
高维数据（如 1024 维的文本向量）不仅存在严重的“维度灾难”，而且人类根本无法可视化。
- **主成分分析 (PCA)**：寻找数据方差最大（分布最散）的方向作为新的坐标轴。它是一种**线性降维**，速度极快，常用于扔进模型前的特征压缩。
- **t-SNE 与 UMAP**：专注于保持数据的局部非线性拓扑结构。它们能把高维空间中距离很近的同类点，在 2D 平面上紧紧挤在一起，形成非常漂亮的可视化星系图。
**注意**：t-SNE 的输出**绝对不能**直接作为特征喂给下游分类器，因为它不保留全局距离比例；如果要做特征降维，首选 PCA 或 Autoencoder。

## 14.5 自编码器 (Autoencoder) 与异常检测
**自编码器** 是一种基于神经网络的无监督学习架构：
它包含一个编码器（把高维输入压缩成低维向量）和一个解码器（试图把低维向量还原回原始输入）。模型的训练目标是让“重构误差”最小。
- **异常检测应用**：正常的数据（如普通学生行为）被大量训练过，自编码器能很好地将其压缩并还原（误差小）。当输入一个前所未见的异常数据时，解码器还原出来的结果会面目全非（重构误差极高）。通过设定误差阈值，就能轻松抓出异常。
- 其他老牌异常检测算法包括：**孤立森林 (Isolation Forest)**，通过随机切分树来隔离数据，越早被孤立出来的点越可能是异常点。

## 14.6 常见误区
- **误区 1：在使用 KMeans 之前，不需要对数据进行归一化/标准化。**
  - **为什么错**：KMeans 极其依赖欧几里得距离计算。如果“收入”特征的量级是百万，而“年龄”特征的量级是几十，未标准化的距离计算将完全被“收入”主导，导致“年龄”特征失效。
- **误区 2：t-SNE 图上距离很远的两个簇，说明它们在真实高维空间里差异极大。**
  - **为什么错**：t-SNE 算法为了突出局部结构，会扭曲全局距离。图上看似遥远的两个簇，可能在高维空间中其实只隔了一层窗户纸。评估全局距离应参考 UMAP 或 PCA。
- **误区 3：可以通过反复调整聚类算法的超参数，直到得到一个与业务“完美贴合”的结果。**
  - **为什么错**：聚类本身就是一种主观的探索性分析（Exploratory Data Analysis）。如果没有引入任何外部标签进行验证，过度迎合某种特定的簇形状很可能是模型对噪声的过拟合（即看到了不存在的规律）。

## 14.7 可运行示例：使用 DBSCAN 进行异常检测与非球形聚类
以下 Python 示例展示了 KMeans 在非凸数据集（如双半月形）上的失败，以及 DBSCAN 如何优雅地解决聚类和噪声识别。

```python
import matplotlib.pyplot as plt
from sklearn.datasets import make_moons
from sklearn.cluster import KMeans, DBSCAN
import numpy as np

# 1. 生成带有少许噪声的“双半月形”数据
X, _ = make_moons(n_samples=300, noise=0.1, random_state=42)
# 手动混入几个离谱的异常点
outliers = np.array([[-1.5, 1.5], [2.5, -1.0], [1.0, 2.0]])
X = np.vstack([X, outliers])

# 2. 对照组：使用 KMeans 聚类 (尝试分为两类)
kmeans = KMeans(n_clusters=2, random_state=42)
y_kmeans = kmeans.fit_predict(X)

# 3. 实验组：使用 DBSCAN (基于密度)
# eps: 邻域半径，min_samples: 成为核心点所需的最少样本
dbscan = DBSCAN(eps=0.2, min_samples=5)
y_dbscan = dbscan.fit_predict(X)

# --- 打印结果摘要 ---
print("=== 无监督学习算法对比 ===")
print("KMeans 结果：粗暴地沿一条直线切分了两个半月，无法识别异常点。")

# DBSCAN 会将噪声点标记为 -1
n_clusters = len(set(y_dbscan)) - (1 if -1 in y_dbscan else 0)
n_noise = list(y_dbscan).count(-1)
print(f"DBSCAN 结果：成功识别出 {n_clusters} 个连续簇，并抓住了 {n_noise} 个异常离群点！")

# 提示：你可以在本地环境使用 plt.scatter 可视化这些标签，
# 会非常直观地看到 DBSCAN 的强大。
```

## 14.8 本章小结
1. 无监督学习在没有标签的情况下，致力于揭示数据的内在分布，是数据探索和特征工程的利器。
2. KMeans 适合规整的球状分群，而 DBSCAN 不仅能处理不规则形状，还天生自带异常检测功能。
3. 降维技术中，PCA 是线性压缩的首选；t-SNE/UMAP 是二维可视化的神器；自编码器则提供了深度学习框架下的解决方案。
4. 在 A3 项目中，无监督技术被隐式地用于构建知识图谱实体聚类和用户隐式画像发现。

## 14.11 可运行代码示例

下面用 NumPy 从零实现 K-Means 聚类，包含 K-Means++ 初始化。零依赖演示"把 200 个点分成 4 簇"的全过程。

```python
'''14 章 · K-Means 聚类实现 (含 K-Means++ 初始化)'''
import numpy as np

np.random.seed(0)

# 1. 生成 4 个高斯簇
centers_true = np.array([[0, 0], [5, 5], [0, 5], [5, 0]])
X = np.vstack([np.random.randn(50, 2) + c for c in centers_true])

# 2. K-Means++ 初始化：第一个随机，后续按距离概率选
def kmeans_pp(X, k, rng):
    idx = [rng.integers(len(X))]
    for _ in range(1, k):
        d2 = np.min([np.sum((X - X[i])**2, axis=1) for i in idx], axis=0)
        probs = d2 / d2.sum()
        idx.append(rng.choice(len(X), p=probs))
    return X[idx]

rng = np.random.default_rng(0)
k = 4
centroids = kmeans_pp(X, k, rng)
print("初始中心 (K-Means++):")
print(np.round(centroids, 2))

# 3. 迭代
for it in range(20):
    # 分配：每个点归到最近中心
    dists = np.stack([np.sum((X - c)**2, axis=1) for c in centroids], axis=1)
    labels = dists.argmin(axis=1)
    # 更新：每簇中心 = 该簇均值
    new_centroids = np.array([X[labels == i].mean(axis=0) if (labels == i).any() else centroids[i]
                              for i in range(k)])
    shift = np.linalg.norm(new_centroids - centroids)
    centroids = new_centroids
    if it % 5 == 0:
        print(f"iter {it:2d}  中心移动={shift:.4f}")
    if shift < 1e-6:
        break

# 4. 评估：簇内 SSE
sse = sum(((X[labels == i] - centroids[i])**2).sum() for i in range(k))
print(f"\nK-Means 收敛: {it+1} 轮，最终簇内 SSE = {sse:.2f}")
print("学到的簇中心:")
print(np.round(centroids, 2))
print("真实中心参考:")
print(centers_true)
```
\n## 14.9 练习思考
1. **聚类特性**：在处理非常庞大的数据集（如 1 亿条用户日志）时，KMeans 往往由于需要全局计算而变得极慢。你能查到有一种名为 `MiniBatchKMeans` 的算法吗？它是如何加速的？
2. **降维选择**：如果我们需要把文本嵌入（Embedding 向量）的维度从 1024 维降到 256 维，然后再喂给支持向量机（SVM）进行分类，你应该选用 PCA 还是 t-SNE？为什么？
3. **异常检测设计**：在 A3 系统的线上考试环境中，你想用“孤立森林（Isolation Forest）”来检测作弊行为，你需要从学生的考试记录中提取哪些特征输入给模型？
4. **算法辨析**：高斯混合模型（GMM）常被称为“软聚类”，它与 KMeans 的“硬聚类”在输出结果的表达上有什么本质区别？这种软分配有何优势？

## 14.10 拓展阅读
- 降维与聚类图解经典：检索 `Visualizing Data using t-SNE`
- 异常检测必读论文：检索 `Isolation Forest` (Liu et al., 2008)
- 聚类评估指标深度解析：查阅 Scikit-learn 的 `Clustering Performance Evaluation` 章节文档。
