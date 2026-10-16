---
chapter_id: '03'
slug: neural_network_basics
title: 神经网络基础
kp_ids:
- AI_006
bloom_focus:
- Understand
- Apply
prerequisites:
- '01'
- '02'
estimated_minutes: 50
---

# 03: 神经网络基础 · 深度学习的基石

> **Bloom 层级**: Understand → Apply
> **建议学时**: 50 分钟
> **前置知识**: 01-机器学习基础、02-数学基础

## 学习目标
1. 掌握人工神经元的基本结构（输入、权重、偏置、激活函数）。
2. 理解多层前馈网络（MLP）的架构以及万能逼近定理的直觉。
3. 阐述反向传播算法（BP）中前向传播与反向求梯度的流程。
4. 比较常见激活函数（Sigmoid, ReLU, GELU）的优缺点。
5. 了解如何在 A3 个性化学习系统中通过神经网络模型预测学生的掌握度。

## 3.1 神经元与感知机
神经网络的基本计算单元是 **神经元（neuron）**，其结构来源于对生物大脑神经元的抽象建模。

**定义与直觉**：
想象你要决定今天是否去跑步。你会考虑几个因素（输入）：天气好坏（$x_1$）、时间是否充足（$x_2$）、身体疲劳度（$x_3$）。不同的人对这些因素的重视程度不同，这就是**权重（Weights, $w$）**。此外，你可能本身就是一个非常自律的人，即使条件很差也想去跑，这种基础倾向就是**偏置（Bias, $b$）**。
一个人工神经元的计算过程为：
1. **加权求和**：$z = \sum_i w_i x_i + b$
2. **激活函数**：$a = \sigma(z)$（决定最终是否输出信号）

**感知机（Perceptron）**：
感知机是最早的单层神经元模型，它是一个线性分类器：
$$\hat{y} = \begin{cases} 1, & w^\top x + b > 0 \\ 0, & \text{otherwise} \end{cases}$$
**局限**：感知机无法解决“线性不可分”问题（如 XOR 异或问题），这一致命缺陷曾导致了 AI 的第一次寒冬。

## 3.2 多层前馈网络（MLP）
为了解决线性不可分的问题，研究者引入了隐藏层。
**多层感知机（MLP）** 通过堆叠多个隐藏层，并使用非线性激活函数，能够拟合任意复杂的非线性函数（这就是著名的“万能逼近定理”）。
- **输入层**：接收原始数据特征。
- **隐藏层**：逐层提取更高阶的抽象特征。
- **输出层**：给出最终的预测（如分类概率）。

**教育场景案例**：
在 A3 项目中，Profile Agent 需要预测一个学生在下一次测试中的及格概率。输入层的特征可以是学生的历史做题时间、视频观看完成率、过去得分等。隐藏层会对这些特征进行非线性组合，输出层最终吐出一个 0 到 1 之间的概率。

## 3.3 反向传播算法（BP）
**直觉解释**：
想象一个盲人下山。他不知道整个山体（损失函数）的地形，只能用脚试探当前位置的坡度（计算梯度），然后向着最陡峭的下坡方向迈出一步（更新权重）。
反向传播算法（Back-Propagation）的核心是利用**链式法则**在计算图上高效地求取梯度。

**三大步骤**：
1. **前向传播 (Forward)**：输入数据，逐层计算激活值，直到输出层得到预测结果。
2. **计算损失 (Loss)**：对比预测结果与真实标签，计算误差（如交叉熵损失 $\mathcal{L}$）。
3. **反向求导与更新 (Backward & Update)**：从输出层倒推，逐层计算损失对每个权重 $w$ 的偏导数 $\frac{\partial \mathcal{L}}{\partial w}$。然后使用梯度下降法更新权重：$w \leftarrow w - \eta \frac{\partial \mathcal{L}}{\partial w}$，其中 $\eta$ 为学习率。

## 3.4 常见激活函数对比
如果没有激活函数，再深的神经网络也等价于一层线性变换。
- **Sigmoid**：$1/(1+e^{-x})$。优点是输出在 (0,1) 之间，适合做概率；缺点是容易导致“梯度消失”（两端太平缓）。
- **ReLU**：$\max(0,x)$。计算极快，有效缓解梯度消失，是深度学习默认的首选；缺点是输入为负时神经元会“死亡”（Dying ReLU）。
- **GELU**：基于高斯误差的平滑激活，目前在 Transformer 和大语言模型（LLM）中广泛使用。

## 3.5 常见误区
- **误区 1：神经网络层数越深，模型的预测效果一定越好。**
  - **为什么错**：层数过深会导致梯度消失或梯度爆炸，同时容易引发过拟合。在没有残差连接的情况下，极深的 MLP 根本无法训练。
- **误区 2：在训练开始前，可以把所有权重 $w$ 初始化为 0。**
  - **为什么错**：如果所有权重都是 0，所有隐藏层神经元在前向和反向传播时将得到完全相同的更新（对称性失效），网络将无法学习到任何有效特征。必须使用随机初始化。
- **误区 3：学习率设置得越大，模型收敛越快。**
  - **为什么错**：过大的学习率会导致模型在谷底反复震荡，甚至损失函数发散飙升；必须配合学习率衰减策略或使用 Adam 优化器。

## 3.6 可运行示例：纯 NumPy 实现单层感知机
以下代码展示了不使用 PyTorch 时，如何用基础库训练一个感知机来解决逻辑与（AND）问题。

```python
import numpy as np

class SimplePerceptron:
    def __init__(self, input_dim, lr=0.1):
        # 随机初始化权重和偏置
        self.w = np.random.randn(input_dim)
        self.b = np.random.randn(1)
        self.lr = lr
        
    def activate(self, x):
        # 阶跃激活函数
        return 1 if x >= 0 else 0
        
    def predict(self, x):
        z = np.dot(x, self.w) + self.b
        return self.activate(z)
        
    def train(self, X, Y, epochs=10):
        for epoch in range(epochs):
            total_error = 0
            for x, y_true in zip(X, Y):
                y_pred = self.predict(x)
                error = y_true - y_pred
                if error != 0:
                    # 权重更新规则
                    self.w += self.lr * error * x
                    self.b += self.lr * error
                total_error += abs(error)
            print(f"Epoch {epoch+1}, Errors: {total_error}")
            if total_error == 0:
                print("已完全拟合！")
                break

if __name__ == "__main__":
    # AND 门的数据集
    X = np.array([[0,0], [0,1], [1,0], [1,1]])
    Y = np.array([0, 0, 0, 1])
    
    model = SimplePerceptron(input_dim=2)
    model.train(X, Y, epochs=15)
    
    print("\n测试结果:")
    for x in X:
        print(f"输入: {x} -> 预测: {model.predict(x)}")
```

## 3.7 本章小结
1. 神经元通过加权求和与非线性激活函数对信息进行处理。
2. 多层感知机（MLP）利用隐藏层打破了线性分类的局限。
3. 反向传播算法结合链式法则和梯度下降，构成了神经网络的训练基石。
4. 在 A3 这样的教育智能体中，基础神经网络常被用于后台数据的轻量级预测（如学生流失预警、知识点掌握度预测）。

## 3.8 练习思考
1. 请数学推导一下，为什么两个只有线性激活函数的全连接层，可以等价合并为一个单层线性网络？
2. 在 A3 系统中，如果用 MLP 来预测某学生做对下一道题的概率，但发现训练集准确率 95%，测试集准确率只有 50%。这属于什么现象？应采用哪两种方法缓解？
3. (编程挑战) 请尝试修改本章的代码示例，使其能够拟合 XOR（异或）数据集。你会发现感知机失败了，你能尝试用 PyTorch 的 `nn.Module` 写一个 2 层 MLP 来解决它吗？

## 3.9 拓展阅读
- 神经网络入门经典可视化教程：检索关键词 `3Blue1Brown Neural Networks`
- 激活函数演进与对比：检索 `A comprehensive survey of activation functions in deep learning`
- PyTorch 官方教程：`Deep Learning with PyTorch: A 60 Minute Blitz`
