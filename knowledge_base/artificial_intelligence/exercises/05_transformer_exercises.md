---
chapter_ref: "05"
chapter_title: "Transformer 与注意力机制"
kp_refs: [transformer, attention_mechanism]
bloom_focus: [Apply, Analyze, Evaluate]
total_points: 30
deadline_hint: 本章配套学习时长 5 学时
---

# Transformer 与注意力机制 · 章节练习

> **配套**：A3 章节 §05 Transformer 与注意力机制  
> **配对代码**：`code_examples/05_transformer_toy.py`

---

## 一、选择题（每题 2 分，共 10 分）

### Q1（Apply）
在 Scaled Dot-Product Attention 中，缩放因子 $\sqrt{d_k}$ 的主要作用是：

- A. 减少显存占用
- B. 防止 softmax 进入饱和区，缓解梯度消失
- C. 让 K 与 V 维度对齐
- D. 提高序列长度

<details><summary>答案</summary>B。详见 Vaswani et al. 2017 §3.2.1。</details>

### Q2（Analyze）
Multi-Head Attention 把 $d_{model}$ 切分成 $h$ 头并行计算，主要目的是：

- A. 减少参数量
- B. 让不同子空间学不同关系（位置 / 语法 / 语义等）
- C. 替代位置编码
- D. 让训练更快（与 batch size 无关）

<details><summary>答案</summary>B。</details>

### Q3（Evaluate）
判断：在 NLP 任务中，Transformer 已经全面替代 RNN / LSTM，因此 RNN 没有学习价值。

- A. 正确
- B. 错误——RNN/LSTM 在流式 / 长序列场景仍有工程优势
- C. 正确——只在教学价值上有意义
- D. 错误——Transformer 不需要位置编码

<details><summary>答案</summary>B。</details>

---

## 二、简答题（每题 5 分，共 10 分）

### Q4（Apply）
请写出 Scaled Dot-Product Attention 的公式，并解释 $\sqrt{d_k}$ 缩放的数学动机。

<details><summary>参考答案要点</summary>

$$\text{Attention}(Q, K, V) = \text{softmax}\!\left(\frac{QK^{\top}}{\sqrt{d_k}}\right)V$$

当 $d_k$ 较大时，dot product 量级增长，使 softmax 接近 one-hot，梯度消失；缩放后将方差归一到 1。
</details>

### Q5（Analyze）
比较 Self-Attention 与 RNN 在处理长度为 $n$ 的序列时的复杂度，并解释为什么长序列训练 Transformer 更慢。

<details><summary>参考答案</summary>

| | Self-Attention | RNN |
|---|---|---|
| 每层计算 | $O(n^2 d)$ | $O(n d^2)$ |
| 顺序依赖 | 无 | 有 |
| 长序列瓶颈 | $n^2$ | $d^2$（与 n 无关）|

Transformer 在 $n \gg d$ 时训练较慢，因 attention 矩阵是 $n^2$ 增长；FlashAttention / 稀疏 attention 是常见优化方向。
</details>

---

## 三、编程题（10 分）

### Q6（Create · 难度 5）
基于 `code_examples/05_transformer_toy.py`，完成下面扩展：

1. 在 attention 输出后加一层 `LayerNorm`，观察 loss 收敛速度
2. 把 Multi-Head 头数从 4 调到 8，记录 loss 曲线并写 markdown 总结

**提交要求**：
- 在 `data/artifacts/pptx/` 下提交截图或 CLI 输出 markdown
- 在 `MistakesView` 上能看到练习记录

<details><summary>评分要点</summary>

- 代码可运行（5 分）
- 实验记录完整（3 分）
- 总结有理有据（2 分）
</details>

---

> **配套自检**：完成本练习后请在 A3 `ResourcesView` 中查看 §05 章，下方应有"本章练习"入口。
