---
title: "模型评估、对齐与可解释性三件套"
authors: []
year: 2024
url: https://scikit-learn.org/stable/model_selection.html
kp_refs: [ml_basics, neural_networks]
summary_zh: 三篇评估 / 对齐 / XAI 经典论文的中文摘要合集
---

# 模型评估、对齐与可解释性三件套

> **面向读者**：即将进入 A3 EvaluatorAgent 设计章节的学生
> **配套章节**：§13 监督学习 / §14 无监督学习
> **KP**：ml_basics / neural_networks
>
> 本合集覆盖 ML 系统落地的「最后三公里」：**怎么知道模型学得好（评估）**、
> **怎么让模型对齐人类意图（对齐）**、**怎么让模型的决策可被理解（可解释性）**。

---

## 论文 1：《Model evaluation, model selection, and algorithm selection in machine learning》— Sebastian Raschka (2018)

### 摘要

本文系统梳理了 ML 项目中"评估模型表现"的完整方法学。从最简单的 train/test split
到 k-fold cross-validation、stratified k-fold、leave-one-out、bootstrap、nested
cross-validation，逐一分析每种方法的适用场景、偏差来源与计算成本。文章重点讨论
了"评估误差与泛化误差的差异"以及"嵌套交叉验证如何避免超参数泄露"，并给出了
scikit-learn 风格的实用 checklist。这是 A3 中 EvaluatorAgent 选择评估策略时
应参考的"白皮书"。

### 核心要点

| 评估方法 | 偏差 | 方差 | 计算成本 | 适用场景 |
|---------|------|------|---------|---------|
| Hold-out | 中 | 中 | 低 | 大数据集 / 一次性实验 |
| k-fold | 低 | 中 | 中 | 中等数据集 |
| Stratified k-fold | 低 | 中 | 中 | 类别不平衡 |
| Leave-one-out | 极低 | 高 | 极高 | 小数据集 |
| Nested CV | 极低 | 低 | 极高 | 超参数选择 |
| Bootstrap | 中 | 中 | 中 | 置信区间估计 |

**关键提醒**：超参数搜索必须在 *外层* CV 的训练折上做 *内层* CV，否则
数据泄露会让泛化误差估计过于乐观。

$$
\text{CV}(k) = \frac{1}{k}\sum_{i=1}^{k} \mathcal{L}(f_{\theta \setminus D_i}(D_i^{\text{test}}))
$$

### 与 A3 系统关联

- **EvaluatorAgent 评估流程**：A3 `EvaluatorAgent` 在评估学生答题表现时，应使用
  *stratified k-fold*（按 KP 类别分层）而非简单随机划分，否则容易把某一类学生
  的答题模式误判为"模型缺陷"。
- **Pedagogical Safety**：本文反复强调"评估指标必须可复现"，对应 A3 的
  `PedagogicalSafety` 守卫 —— 任何评估结论必须附带 fold_id + 数据集 hash，
  防止学生得到前后不一致的反馈。

---

## 论文 2：《Training language models to follow instructions》— Ouyang et al. (InstructGPT, 2022)

### 摘要

OpenAI 团队提出 RLHF（Reinforcement Learning from Human Feedback）三阶段流程，
把 GPT-3 从"补全 prompt 的工具"改造为"听从指令的助手"：

1. **SFT**（Supervised Fine-Tuning）：人工写高质量 (prompt, response) 对，微调 base model；
2. **RM**（Reward Model）：人工对模型多个输出排序，训练一个 reward model 预测人类偏好；
3. **PPO**（Proximal Policy Optimization）：用 RM 作为奖励信号继续微调 SFT 模型。

论文展示了 RLHF 在 Truthfulness、Toxicity、Helpfulness 三个维度的显著提升（约
+10pp），并坦承局限：RM 会"被 hack"、对长回答有偏好、对少数群体回应质量不稳定等。

### 核心要点

**RLHF 三阶段损失**：

$$
\mathcal{L}_{\text{RM}} = -\log \sigma\!\left(r_\phi(x, y_w) - r_\phi(x, y_l)\right)
$$

其中 $y_w$ 是 preferred response，$y_l$ 是 dispreferred response。

$$
\mathcal{L}_{\text{PPO}} = \mathbb{E}\!\left[r_\phi(x, y) - \beta \cdot \text{KL}(\pi_\theta \| \pi_{\text{SFT}})\right]
$$

KL 项防止模型偏离 SFT 太远（即"reward hacking"）。

### 与 A3 系统关联

- **A3 的对齐机制**：A3 的 TutorAgent 在给学生讲解时，也面临"输出对齐学生
  偏好 vs 教学目标"的二元张力；本文 §4 提供的 reward model + KL 约束思路
  可直接迁移到 A3 的多目标 RLHF 实验中。
- **Pedagogical Safety 守门**：InstructGPT 文中明确指出"harmful output 必须
  主动拒绝"，这与 A3 `PedagogicalSafety` 在 TutorAgent 输出侧强制注入 safety
  prefix 的设计一脉相承。
- **Claim Ledger 的必要性**：InstructGPT 的奖励模型会因数据偏差放大不公平；
  A3 通过 Claim Ledger 强制每条断言带证据，是教学场景下"无 RM 但仍可对齐"
  的工程折中。

---

## 论文 3：《Attention Is Not Explanation》— Jain & Wallace (NAACL 2019)

### 摘要

这篇论文挑战了 NLP 社区对 attention weights 的"误用"：研究者常把 attention
权重当作"模型在做决策时关注了哪部分输入"的解释，但作者通过对抗扰动实验
证明：

1. **Attention weights 可以被完全替换**：把 attention 分布替换为随机分布或
   uniform 分布后，模型预测几乎不变；
2. **不同的 attention 分布可以给出同样的输出**：通过对抗优化找到一组显著不同
   的 attention weights，但产生相同预测；
3. **Attention 不满足"解释"的最低要求**：因果性（causal）、忠实性（faithful）。

结论不是说 attention 没用，而是说 **不能直接把 attention 当成可解释性工具**，
要区分 *attention as mechanism* 与 *attention as explanation*。

### 核心要点

**可解释性四大标准**（作者综合文献给出）：

| 标准 | 含义 | Attention 是否满足 |
|------|------|-------------------|
| Plausibility | 看起来合理 | 满足 |
| Fidelity | 解释与模型决策一致 | **不满足** |
| Completeness | 解释覆盖全部决策依据 | 部分 |
| Causal | 改变解释会改变预测 | **不满足** |

### 与 A3 系统关联

- **A3 的 Attention 可视化需重新设计**：A3 在 TutorAgent 给出 Transformer
  解释时，目前直接渲染 attention map 作为"模型关注点"。本文提示我们：
  应当**同时给出对抗扰动对照**（同一输入 → 不同 attention → 同样预测），
  才能避免误导学生。
- **EvaluatorAgent 的可解释性输出**：A3 `EvaluatorAgent` 给学生返回错题归因时，
  不应直接报"attention 权重告诉你原因是 X"，而应给出更可靠的 SHAP / LIME
  特征归因（参考 Ribeiro et al. 2016《Why Should I Trust You》）。
- **教学诚信**：本文提醒所有 AI 教师 agent —— **"看起来合理的解释"不等于
  "正确的解释"**。A3 的 Claim Ledger 强制引用源文献，正是为了杜绝
  "可解释性幻觉"。

---

## 三件套的整体启示

| 主题 | 核心论文 | A3 对应模块 |
|------|---------|-------------|
| 评估 | Raschka 2018 | EvaluatorAgent + CV 流程 |
| 对齐 | Ouyang 2022 | RLHF + PedagogicalSafety |
| 可解释性 | Jain & Wallace 2019 | Claim Ledger + SHAP 归因 |

**A3 教师提示词**：当学生进入模型部署章节时，TutorAgent 应一次性推荐三件套，
让学生意识到「能跑 ≠ 能用 ≠ 能解释 ≠ 对齐人类」。

## 推荐片段

- Raschka：§3 Cross-Validation、§6 Bootstrap Confidence Intervals
- Ouyang：§3 Method（RLHF 三阶段）、§5 Limitations
- Jain & Wallace：§4 Adversarial Attention 实验

> **教学小贴士**：把这三件套作为 A3 §14 章的"扩展阅读清单"布置给学生，
> 配合 §14 章节习题，能让 ML 通识课的学生对"落地"有完整概念。