---
title: "Communication-Efficient Distributed Learning with Knowledge Distillation"
authors: 相关综述与基础工作（整合阅读清单）
year: 2024
url: https://arxiv.org/abs/2402.02150
kp_refs: [AI_006, transformer, multimodal_llm, multi_agent_systems]
summary_zh: 多智能体 / 分布式学习中"知识蒸馏"的综述与典型工程实践。
---

# 多智能体与分布式学习：知识蒸馏导读

> **面向读者**：A3 系统 §11 多智能体章节的进阶阅读

## 三个关键视角

### 1) 模型协同蒸馏（教师-学生框架）

- 把 Multi-Agent 协作看成"分布式教师"，各自维护局部模型，通过周期性 logits 同步缓解通信开销
- 适合资源受限的边缘部署（与 A3 §11 "轻量级本地 tutor" 直接相关）

### 2) 思维链蒸馏（CoT Distillation）

- DeepSeek-R1 风格的"长链思考"可蒸馏到 7B-8B 学生模型
- A3 TutorAgent 的 Step-by-Step 输出可作为蒸馏源

### 3) 共识与冲突解决

- 多 Agent 对同一题输出可能不一致，需引入投票 / 仲裁
- A3 EvaluatorAgent 的 critic + aggregator 模式是落地实践

## 推荐论文清单

| 标题 | 年份 | 关联 A3 模块 |
|------|------|-------------|
| Distilling the Knowledge in a Neural Network (Hinton) | 2015 | TutorAgent prompt 优化 |
| Self-Consistency Improves Chain of Thought Reasoning | 2023 | COVVerifier 思路源头 |
| ReAct: Synergizing Reasoning and Acting in Language Models | 2022 | Agent Tools 调用策略 |
| Model Context Protocol (MCP) | 2024 | AI Agent 生态接入 |

## 阅读策略

- 本科级：先读 Hinton KD 原论文，2 小时
- 进阶：补 ReAct + Self-Consistency，共 4 小时
- 答辩冲刺：重点复述"为什么 Multi-Agent 比单 Agent 更稳"
