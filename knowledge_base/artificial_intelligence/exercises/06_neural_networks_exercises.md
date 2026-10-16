---
chapter_ref: "06"
chapter_title: "神经网络与深度学习"
kp_refs: [neural_networks, backpropagation, cnn]
bloom_focus: [Apply, Analyze, Create]
total_points: 30
deadline_hint: 本章配套学习时长 12 学时
---

# 神经网络与深度学习 · 章节练习

> **配套**：A3 章节 §06 神经网络与深度学习  
> **配对代码**：`code_examples/03_mlp_mnist.py`、`code_examples/04_cnn_cifar10.py`

---

## 一、选择题（每题 2 分，共 10 分）

### Q1（Remember）
反向传播算法的核心数学工具是：

- A. 牛顿迭代法
- B. 链式法则
- C. 主成分分析
- D. 卷积定理

<details><summary>答案</summary>B</details>

### Q2（Understand）
Batch Normalization 的主要作用是：

- A. 把激活值归一到 0 均值 1 方差，从而缓解梯度消失 / 爆炸
- B. 减少网络参数量
- C. 让训练集更大
- D. 替代 Dropout

<details><summary>答案</summary>A</details>

### Q3（Apply）
CNN 用卷积层替代全连接层最主要的好处是：

- A. 减少参数 + 局部连接 + 平移不变性
- B. 让训练变慢
- C. 强化过拟合
- D. 让图片变大

<details><summary>答案</summary>A</details>

### Q4（Analyze）
LeNet-5 / AlexNet / VGG / ResNet 的共同点是：

- A. 都用 RNN
- B. 都是 CNN 风格但深度与 shortcut 机制逐步演化
- C. 都是无监督模型
- D. 都依赖强化学习

<details><summary>答案</summary>B</details>

### Q5（Evaluate）
"越深的网络效果越好，所以应该无限堆叠" 这一观点的局限是：

- A. 不耗显存
- B. 退化 / 梯度消失 / 算力爆炸，需残差连接
- C. 永远最佳
- D. 不需要归一化

<details><summary>答案</summary>B</details>

---

## 二、简答题（每题 5 分，共 10 分）

### Q6（Apply）
写出反向传播在 MLP 单层 `y = Wx + b, σ = ReLU, ℓ = CE(y, t)` 上的关键梯度推导步骤。

<details><summary>参考答案</summary>

$$\frac{\partial \ell}{\partial W} = \frac{\partial \ell}{\partial y}\frac{\partial y}{\partial W} = (\sigma - t)\, x^{\top}$$

其中 $\sigma = \text{softmax}(y)$，$\frac{\partial \ell}{\partial y}$ 是 CE 对 logits 的梯度；ReLU 单元上的 mask 在反向时直接相乘。
</details>

### Q7（Analyze）
为什么 ResNet 的残差连接让训练更深网络成为可能？从梯度视角说明。

<details><summary>参考答案</summary>

残差块输出 $H(x) = F(x) + x$，反向传播时 $\frac{\partial L}{\partial x}$ 多一条 $1$ 直通通道，避免深层网络梯度消失；这也使非常深的网络（如 152 层）仍可训练。
</details>

---

## 三、编程题（10 分）

### Q8（Create · 难度 4）
基于 `04_cnn_cifar10.py`，完成如下扩展：

1. 加一层 `BatchNorm2d` 在两个 conv 后
2. 把 batch_size 调到 256
3. 跑 30 个 batch，记录 loss 曲线与 test acc

提交：在 PR 中附 `04_cnn_cifar10_v2.py` 与截图。

<details><summary>评分要点</summary>

- 代码可跑（5 分）
- BN 引入后的稳定性证据（3 分）
- 总结对收敛速度 / 最终 acc 的影响（2 分）

</details>

---

> **配套自检**：完成本练习后请在 A3 `ResourcesView` 中查看 §06 章，下方应有"本章练习"入口。
