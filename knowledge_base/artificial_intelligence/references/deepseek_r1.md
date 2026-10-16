---
title: "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning"
authors: [DeepSeek-AI]
year: 2025
url: https://arxiv.org/abs/2501.12948
kp_refs: [AI_006_03, transformer, ai_agent]
summary_zh: DeepSeek-R1 用纯 RL 训练推理能力，提出"aha moment"涌现与可读推理蒸馏范式。
---

# DeepSeek-R1（2025）

> **面向读者**：对大模型推理 / RLHF 感兴趣，想看 OpenAI o1 之后代表路线的同学

## 摘要

DeepSeek-R1-Zero 跳过 SFT，直接对基础模型施加 GRPO + 规则奖励（accuracy + format），
观察到模型自发"长链思考"行为，并在 AIME / MATH 上逼近 OpenAI-o1。R1 进一步通过 SFT
冷启动 + 多阶段 RL + 蒸馏得到更稳健、可读的推理模型。

## 核心要点

| 维度 | R1-Zero | R1 |
|------|---------|----|
| 训练数据 | 纯 RL，无 SFT 冷启动 | 少量冷启动 SFT + RL + 蒸馏 |
| 奖励模型 | 规则型（accuracy + format） | 规则型 + 偏好型（后期） |
| 推理能力 | 自发涌现"aha moment" | 更可读、更稳定 |
| 可蒸馏 | 是（→ Qwen/LLaMA） | 是 |

## 与 A3 系统关联

- `TutorAgent` 在 Socratic 策略中（§06 P1-4）借鉴了"self-reflection"机制 → 类比 R1 的 RL 反思
- `EvaluatorAgent` 的 quality_score 可以参考 R1 蒸馏 logits score
- `KnowledgeIndex.coverage_report` 可暴露给 RL 训练 pipeline 做 curriculum

## 推荐片段

- §2 Approach：GRPO 公式与 rule-based reward 设计
- §3.2 R1-Zero 训练曲线（重点观察"aha moment"涌现点）
- §4 Distillation：把推理能力迁移到小模型

## 中文解读

[机器之心报道](https://www.jiqizhixin.com/articles/deepseek-r1) — 适合答辩演示引用。
