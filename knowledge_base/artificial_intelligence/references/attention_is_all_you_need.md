---
title: "Attention Is All You Need"
authors: [Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin]
year: 2017
url: https://arxiv.org/abs/1706.03762
kp_refs: [AI_006_03, transformer, attention_mechanism]
summary_zh: Transformer 原始论文，把自注意力作为序列建模的单一核心机制，奠定了 BERT/GPT 等大模型的基础。
---

# Attention Is All You Need（2017）

> **面向读者**：已学完 §05 Transformer 与注意力机制章节，想了解原始 idea 的同学

## 摘要

本文提出了一种全新的序列 transduction 架构 **Transformer**，完全基于注意力机制，
抛弃了 RNN / CNN 结构。模型在 WMT 2014 英德翻译任务上达到 28.4 BLEU，比此前最佳
（含集成）提升 2.0 BLEU 以上。Transformer 在英法翻译任务上也达到 41.8 BLEU 单模型
SOTA，同时训练时间显著少于 RNN/CNN 基线。

## 关键创新点

1. **Scaled Dot-Product Attention**：
   $$\text{Attention}(Q, K, V) = \text{softmax}\!\left(\frac{QK^{\top}}{\sqrt{d_k}}\right)V$$
   通过 $\sqrt{d_k}$ 缩放防止 softmax 进入饱和区（dot 过大导致梯度消失）。
2. **Multi-Head Attention**：把 $d_{model}$ 切分成 $h$ 头并行做注意力，再 concat 投影，
   让模型在不同子空间学不同关系。
3. **Positional Encoding**：用 $sin/cos$ 函数叠加位置信息（无学习参数），弥补注意力"无序"缺陷。
4. **Encoder-Decoder 结构**：6+6 层，每层包含 Multi-Head Attention + FFN + 残差 + LayerNorm。

## 对 A3 教学的启示

- A3 的 `TutorAgent` 在解释 Transformer 时常被学生问"为什么需要 scaled"，该论文 §3.2.1 给出数学答案
- `Multi-Head Attention` 是 `MultiHeadAttention` 模块源码读懂的必要前提
- 论文在 6.1 节"stop layer normalization"成为后续 LLaMA / GPT-2 等改进的引子

## 推荐阅读顺序

1. §1 Introduction：动机 + 与 CNN/RNN 复杂度对比表
2. §3 Model：Scaled Dot-Product 与 Multi-Head 两个核心公式
3. §4 Why Self-Attention：$O(n^2 d)$ vs $O(n d^2)$ 推导
4. §6 Results & 7 Conclusion

## 中文翻译参考

[知乎高赞解读](https://zhuanlan.zhihu.com/p/48508221) — 可配合 A3 §05 章 5.4 节使用。
