---
chapter_id: '17'
slug: backpropagation
title: 反向传播与优化器
kp_ids:
- AI_006
bloom_focus:
- Analyze
- Apply
prerequisites:
- '02'
- '03'
estimated_minutes: 60

artifacts:
    - type: 'mp3'
      path: 'data/artifacts/mp3/tts_4db511b9ec.mp3'
      title: '反向传播算法语音讲解 (C2)'

---

# 17: 反向传播与优化器 · 神经网络的引擎

> **Bloom 层级**: Analyze → Apply
> **建议学时**: 60 分钟
> **前置知识**: 02-数学基础、03-神经网络基础

## 学习目标
1. 解释反向传播（Backpropagation, BP）为什么比数值微分更适合深度神经网络。
2. 演示如何利用链式法则在计算图（Computational Graph）上计算梯度。
3. 对比分析常见优化器（SGD、Momentum、Adam、AdamW）的原理演进与适用场景。
4. 识别训练中出现的梯度消失与梯度爆炸现象，并掌握缓解策略（如梯度裁剪、合理初始化）。
5. 了解在 A3 项目模型微调或本地小模型训练中，如何设计合理的学习率调度（Learning Rate Scheduler）。

## 17.1 为什么需要反向传播？
深度神经网络动辄包含数百万甚至上千亿个参数。要让网络学习，我们就需要知道：**“当模型预测错误时，每一个参数该负多少责任（梯度）？”**
如果用最暴力的数值微分法（每次拨动一个参数，看损失变化），计算 $N$ 个参数的梯度需要做 $N+1$ 次极其昂贵的前向传播，这是完全不可接受的。
**反向传播（BP）** 算法利用微积分中的**链式法则（Chain Rule）**，只需一次前向传播和一次从后往前的反向传播，就能在 $O(N)$ 的时间复杂度内，一次性求出所有参数的梯度，它是整个深度学习繁荣的基石。

## 17.2 计算图与链式法则
现代深度学习框架（如 PyTorch）不要求你手算微积分，而是会在后台构建一张**计算图（Computational Graph）**。
**直觉**：
想象一条流水线。前向传播就像是组装零件：输入 $x$ 经过加权得到 $z_1$，再经过激活函数得到 $a_1$，最后算出损失 $L$。
反向传播就像是顺藤摸瓜的“追责机制”：损失 $L$ 发现结果不对，先问责最后一层的 $a_1$（偏导数 $\frac{\partial L}{\partial a_1}$），$a_1$ 说这不全怪我，是 $z_1$ 传过来的材料不对（$\frac{\partial a_1}{\partial z_1}$），于是追责力度就乘了起来，一直传达到最底层的参数 $w$。
公式表达即为：
$$\frac{\partial L}{\partial w} = \frac{\partial L}{\partial a_1} \cdot \frac{\partial a_1}{\partial z_1} \cdot \frac{\partial z_1}{\partial w}$$

## 17.3 梯度的两个幽灵：消失与爆炸
在几十上百层的网络中，连乘的链式法则会带来灾难。
- **梯度消失 (Vanishing Gradient)**：如果每层的导数都小于 1（例如 Sigmoid 函数的导数最大才 0.25），连乘 50 次后，底层的梯度将趋近于 0。此时底层的参数根本得不到更新，整个网络退化为浅层网络。
  - *缓解方案*：使用 ReLU 激活函数（正区间导数永远为 1）、引入残差连接（ResNet）。
- **梯度爆炸 (Exploding Gradient)**：如果每层的导数都大于 1，连乘后底层梯度将变为无穷大，导致参数更新时直接飞到天际（NaN）。
  - *缓解方案*：使用**梯度裁剪（Gradient Clipping）**，强制限制梯度的最大长度。

## 17.4 优化器演进：从 SGD 到 AdamW
算出梯度后，如何迈出更新的那一步？这是优化器（Optimizer）的工作。
1. **SGD (随机梯度下降)**：最朴素的走法，沿着当前最陡的下坡迈步。缺点是如果在峡谷地形中，会在两壁之间反复震荡，走不到谷底。
2. **Momentum (动量)**：模拟物理学中的惯性。如果一直朝一个方向走，速度会越来越快；如果方向突变，惯性会抵消震荡。
3. **RMSProp**：自适应学习率。给坡度陡（梯度大）的参数分配较小的步伐，给平缓的参数分配较大的步伐。
4. **Adam (Adaptive Moment Estimation)**：目前深度学习的最常用默认配置。它将 Momentum（一阶动量）和 RMSProp（二阶动量）结合在了一起。
5. **AdamW**：为了解决 Adam 在 L2 正则化上的数学缺陷，它将权重衰减（Weight Decay）单独解耦出来，是目前**训练 Transformer 和大语言模型（LLM）的绝对标配**。

## 17.5 学习率调度 (Learning Rate Scheduler)
在训练初期，我们需要较大的学习率来快速冲出随机初始化的区域；在训练后期，我们需要极小的学习率在谷底精细打磨。
- **Cosine Annealing (余弦退火)**：让学习率按余弦曲线平滑下降。
- **Warmup (预热)**：LLM 训练的必备技巧。刚开始训练时，学习率从 0 线性上升到目标值，防止初始的巨大梯度直接把模型训崩溃，然后再缓慢衰减。

## 17.6 常见误区
- **误区 1：只要用了 Adam，就不用再花心思去调学习率了。**
  - **为什么错**：虽然 Adam 具有自适应机制，但其全局基础学习率 $\eta$ 依然是最重要的超参数。对于不同规模的模型，学习率差一个数量级可能导致模型完全不收敛。
- **误区 2：在 PyTorch 中每个 Batch 训练前，忘记调用 `optimizer.zero_grad()`。**
  - **为什么错**：PyTorch 的梯度是**累加**的（设计用于处理大 Batch 拆分）。如果不清零，当前 Batch 的梯度会和上一个 Batch 的梯度混在一起，导致模型乱走。
- **误区 3：测试集/验证集的推理阶段，也开启计算图。**
  - **为什么错**：反向传播需要保留前向过程中的所有中间激活值（Activation），这极其消耗显存。在推理时必须使用 `with torch.no_grad():` 来关闭它。

## 17.7 可运行示例：手动体验梯度与优化器
以下自包含的 Python 示例使用 PyTorch 演示了一个极其简化的线性回归拟合，直观展示了自动求导（Autograd）和梯度下降（SGD）的威力。

```python
import torch

# 1. 构造一个简单的目标函数: y = 3x + 2，并加入一些噪声
torch.manual_seed(42)
X = torch.randn(100, 1)
y_true = 3 * X + 2 + 0.1 * torch.randn(100, 1)

# 2. 随机初始化权重 w 和偏置 b，并告知 PyTorch 需要追踪它们的梯度
w = torch.randn(1, requires_grad=True)
b = torch.randn(1, requires_grad=True)

# 3. 设置超参数：学习率与迭代次数
learning_rate = 0.1
epochs = 5

print(f"初始状态: w={w.item():.2f}, b={b.item():.2f}")

for epoch in range(epochs):
    # --- 前向传播 ---
    y_pred = X * w + b
    
    # --- 计算损失 (MSE) ---
    loss = torch.mean((y_pred - y_true) ** 2)
    
    # --- 反向传播 ---
    # 这句话会让 PyTorch 自动从 loss 开始运用链式法则往回求导，
    # 并将结果存入 w.grad 和 b.grad 中
    loss.backward()
    
    # --- 优化器更新参数 ---
    # 使用 torch.no_grad() 是因为更新参数这个动作本身不需要被求导追踪
    with torch.no_grad():
        w -= learning_rate * w.grad
        b -= learning_rate * b.grad
        
        # 常见新手坑：更新完参数必须清零梯度，否则下次累加！
        w.grad.zero_()
        b.grad.zero_()
        
    print(f"Epoch {epoch+1} | Loss: {loss.item():.4f} | 拟合结果: w={w.item():.2f}, b={b.item():.2f}")

print("（经过短短 5 次迭代，w 和 b 已经非常逼近真实的 3 和 2）")
```

## 17.8 教育智能体场景案例
在 A3 个性化学习系统中，虽然我们在前端通过 API 调用封装好的大语言模型，但了解优化器是必须的。
**场景**：如果 A3 系统需要基于我们自己课程库的 100 万字语料，对一个本地开源小模型（如 Qwen-1.5B）进行指令微调（SFT），以专门处理编程课程的纠错。
- **实践**：在编写微调脚本时，你必须选择 `AdamW` 作为优化器，同时搭配 `Linear Warmup` 调度策略。如果初期不加 Warmup 约束，由于损失波动极大，极易触发梯度爆炸，导致模型原有的常识灾难性遗忘。

## 17.9 本章小结
1. 反向传播是借助链式法则，在计算图上高效计算参数梯度的核心算法。
2. 深度网络常常受困于梯度消失和梯度爆炸，ReLU、残差连接和梯度裁剪是对症良药。
3. 优化器从 SGD 演进到了带自适应动量的 AdamW，极大地提升了模型的收敛速度和稳定性。
4. 学习率调度（如 Warmup）在训练超大规模神经网络时起到了保驾护航的关键作用。

## 17.12 可运行代码示例

下面用 NumPy 手写两层 MLP 的反向传播：前向 → 计算 loss → 反向逐层求梯度 → 更新参数。零依赖演示 BP 全流程。

```python
'''17 章 · 反向传播手动实现 — 2 层 MLP 解决异或问题'''
import numpy as np

np.random.seed(42)

# 1. 数据：异或
X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float32)
y = np.array([[0], [1], [1], [0]], dtype=np.float32)

# 2. 参数
W1 = np.random.randn(2, 4) * 0.5
b1 = np.zeros(4)
W2 = np.random.randn(4, 1) * 0.5
b2 = np.zeros(1)

def sigmoid(z): return 1.0 / (1.0 + np.exp(-z))
def sigmoid_grad(p): return p * (1 - p)   # p 已经是 sigmoid 输出

lr = 0.5
for epoch in range(5000):
    # ---- 前向 ----
    z1 = X @ W1 + b1
    a1 = sigmoid(z1)
    z2 = a1 @ W2 + b2
    a2 = sigmoid(z2)

    # ---- loss (MSE) ----
    loss = ((a2 - y) ** 2).mean()

    # ---- 反向 ----
    d_a2 = 2 * (a2 - y) / len(y)         # MSE 对输出的梯度
    d_z2 = d_a2 * sigmoid_grad(a2)        # sigmoid 链式
    d_W2 = a1.T @ d_z2
    d_b2 = d_z2.sum(axis=0)

    d_a1 = d_z2 @ W2.T
    d_z1 = d_a1 * sigmoid_grad(a1)
    d_W1 = X.T @ d_z1
    d_b1 = d_z1.sum(axis=0)

    # ---- 更新 ----
    W2 -= lr * d_W2;  b2 -= lr * d_b2
    W1 -= lr * d_W1;  b1 -= lr * d_b1

    if epoch % 1000 == 0:
        print(f"epoch {epoch:4d}  loss={loss:.4f}")

# 4. 推理
pred = sigmoid(sigmoid(X @ W1 + b1) @ W2 + b2)
print("\nXOR 预测:")
for xi, yi, ypi in zip(X, y, pred):
    print(f"  {xi} -> pred={ypi[0]:.3f} (target={yi[0]})")

print("\n→ 关键点: 反向传播本质是链式法则 + 逐层缓存前向激活值。")
print("→ 实际框架 (PyTorch/JAX) 通过 autograd 自动完成求导。")
```
\n## 17.10 练习思考
1. **理论推演**：在使用 Sigmoid 激活函数时，导数的最大值只有 0.25。如果一个 10 层网络没有任何残差连接，最底层的梯度最大可能衰减到原来的多少分之一？
2. **代码排错**：如果你的 PyTorch 模型训练脚本运行时，显存每经过一个 Batch 就增加一点，最终导致 OOM（Out Of Memory），这通常是因为什么基础操作没写好？
3. **架构理解**：在反向传播的过程中，除了需要参数（Weights），往往还需要保留前向传播时的哪些数据（比如 $z$ 或 $a$）？这解释了为什么大模型训练比推理更吃显存。
4. **模型优化**：如果在 A3 系统的微调实验中，你发现训练集 Loss 一直在剧烈上下跳动，迟迟降不下来。请给出三种可能导致此现象的原因及对应的调整方法。

## 17.11 拓展阅读
- 神经网络与反向传播的完美图解教程：阅读 `CS231n 斯坦福课程讲义：Backpropagation`。
- 优化器的深度解析：阅读 Sebastian Ruder 的经典综述 `An overview of gradient descent optimization algorithms`。
- AdamW 的前世今生：检索论文 `Decoupled Weight Decay Regularization` (Ilya Loshchilov)。
