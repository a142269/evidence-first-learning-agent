#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
教师端知识图谱数据补全脚本（v1 · 0711）

依据：
    开发日志/交给其他大模型-学生端知识图谱数据补全任务.md

执行内容：
    一. 课程知识点元数据补全（50/50 KP）
        - description: 40-100 字中文
        - metadata.bloom_level: 6 选 1
        - metadata.difficulty:  basic/intermediate/advanced
        - metadata.chapter, learning_objectives, keywords,
          typical_tasks, common_misconceptions, estimated_minutes
    二. KP 关系补全到 100-130（无自环，weight 0.4-1.0）
        - 5 类关系：prerequisite / part_of / related_to / applies_to / extends
    三. BKT 学习证据：50/50 KP × 8-20 名演示学生
        - 4 高 + 10 稳定 + 6 风险 = 20 学生分层
    四. 错题与学习活动
        - 错题 error_type 限定 6 种（禁 unknown）
        - 评估 30 天分布，不同日全相同
    五. 画像与资源
        - ProfileRecord.profile_data 存原生对象/数组（非 JSON 字符串）
        - ResourceRecord 标题用中文可读命名

幂等与安全：
    - 所有演示记录使用稳定 ID（前缀 kg_demo_v1_）
    - 事务失败回滚
    - 不删除已有真实数据
    - 不覆盖已有非空课程说明 / Bloom 层级 / 人工标注
    - --dry-run 仅打印计划；--apply 才落库
    - 仅处理 demo-student-1 ~ demo-student-20
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from backend.app.core.database import SessionLocal, init_db  # noqa: E402
from backend.app.core import models  # noqa: E402

# ================================================================
# 常量
# ================================================================
SEED = 20260711
COURSE = "artificial_intelligence"
PY_COURSE = "python_programming"
SEED_SOURCE = "teacher_knowledge_graph_demo_v1"
DEMO_STUDENTS = [f"demo-student-{i}" for i in range(1, 21)]
DEMO_NICKS = [
    "小李", "小王", "小张", "小赵", "小孙", "小周", "小吴", "小郑",
    "小冯", "小陈", "小楚", "小卫", "小蒋", "小沈", "小韩", "小杨",
    "小朱", "小秦", "小尤", "小何",
]
TIER_MAP = {
    # 20% 高 / 50% 稳定 / 30% 风险 = 4/10/6
    **{f"demo-student-{i}": "high" for i in range(1, 5)},
    **{f"demo-student-{i}": "stable" for i in range(5, 15)},
    **{f"demo-student-{i}": "risk" for i in range(15, 21)},
}
TIER_BASE_MASTERY = {
    "high": 0.84,    # 在区间 [0.72, 0.94]
    "stable": 0.62,  # 在区间 [0.45, 0.76]
    "risk": 0.36,    # 在区间 [0.16, 0.52]
}
ALLOWED_MISTAKE_TYPES = {
    "misconception", "knowledge_gap", "concept_boundary",
    "careless", "calculation", "reading",
}
ALLOWED_RECORD_TYPES = {"quiz", "resource_view", "question", "practice"}
ALLOWED_RELATION_TYPES = {"prerequisite", "part_of", "related_to", "applies_to", "extends"}
ALLOWED_BLOOM = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
ALLOWED_DIFFICULTY = {"basic", "intermediate", "advanced"}


# ================================================================
# KP 元数据定义（50 节点）
# ================================================================
KP_META: Dict[str, Dict[str, Any]] = {
    # -------- 旧 KPs（28 个，已有部分元数据，缺 bloom）--------
    "python_basics": {
        "name": "Python 基础编程", "bloom": "apply", "difficulty": "basic",
        "chapter": "Python 先修课 1-3 章",
        "description": "Python 语法、变量、控制流、函数、模块与包管理。理解 Python 解释执行、动态类型与缩进语义，能独立编写中等规模脚本。",
        "learning_objectives": ["解释 Python 解释执行与动态类型的含义", "使用控制流与函数组织代码", "使用模块与包组织中等规模脚本"],
        "keywords": ["Python", "语法", "函数", "模块", "控制流"],
        "typical_tasks": ["写一个含列表/字典处理的脚本", "使用模块拆分多文件项目"],
        "common_misconceptions": ["把 Python 当强类型语言", "混淆 is 与 =="],
        "estimated_minutes": 240,
    },
    "data_structures": {
        "name": "数据结构与算法", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "Python 先修课 4 章 / AI 课 13 章",
        "description": "列表、字典、栈、队列、树、图与基本算法（排序、查找、递归）。能够用合适结构组织数据并分析复杂度。",
        "learning_objectives": ["比较数组/链表/哈希表的时间复杂度", "实现栈/队列/树等基本结构", "使用递归与分治解决典型问题"],
        "keywords": ["数组", "链表", "哈希表", "树", "图", "复杂度"],
        "typical_tasks": ["实现 LRU 缓存", "用栈判断括号匹配"],
        "common_misconceptions": ["认为哈希表永远是 O(1)", "忽视递归栈溢出"],
        "estimated_minutes": 300,
    },
    "linear_algebra": {
        "name": "线性代数（机器学习）", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 2 章",
        "description": "矩阵运算、向量空间、特征值与特征向量、SVD 分解。理解几何含义并能在 ML 公式中熟练运用。",
        "learning_objectives": ["解释矩阵乘法的几何含义", "计算矩阵的特征值与特征向量", "运用 SVD 分解降维"],
        "keywords": ["矩阵", "特征值", "SVD", "向量空间"],
        "typical_tasks": ["用 NumPy 实现 PCA", "求解最小二乘"],
        "common_misconceptions": ["混淆行秩与列秩", "不理解正交矩阵的几何意义"],
        "estimated_minutes": 240,
    },
    "probability_statistics": {
        "name": "概率与统计（机器学习）", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 2 章",
        "description": "概率分布、条件概率、贝叶斯推断、参数估计与假设检验。理解机器学习中的不确定性建模。",
        "learning_objectives": ["计算条件概率与贝叶斯公式", "解释常见概率分布的适用场景", "完成简单假设检验"],
        "keywords": ["贝叶斯", "分布", "假设检验", "MLE"],
        "typical_tasks": ["实现朴素贝叶斯分类", "完成 A/B 检验分析"],
        "common_misconceptions": ["混淆先验与似然", "忽视样本独立性"],
        "estimated_minutes": 240,
    },
    "ml_basics": {
        "name": "机器学习基础（核心）", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 13 章",
        "description": "学习范式、损失函数、评估指标、过拟合与正则化。理解监督/无监督/强化学习的边界与典型场景。",
        "learning_objectives": ["比较监督、无监督与强化学习的差异", "解释偏差-方差权衡", "选用合适的评估指标"],
        "keywords": ["监督学习", "无监督学习", "过拟合", "评估指标"],
        "typical_tasks": ["用交叉验证评估模型", "画学习曲线诊断过拟合"],
        "common_misconceptions": ["把训练集当测试集", "只看准确率不看召回率"],
        "estimated_minutes": 240,
    },
    "supervised_learning": {
        "name": "监督学习方法", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 13 章",
        "description": "线性回归、逻辑回归、KNN、SVM 等核心监督方法。能够根据数据规模与分布选择合适模型。",
        "learning_objectives": ["实现线性回归与逻辑回归", "解释 KNN 的距离度量影响", "选择合适的监督学习方法"],
        "keywords": ["线性回归", "逻辑回归", "KNN", "SVM"],
        "typical_tasks": ["训练房价预测回归模型", "完成二分类逻辑回归"],
        "common_misconceptions": ["忽视特征归一化", "对所有问题都用默认超参"],
        "estimated_minutes": 300,
    },
    "unsupervised_learning": {
        "name": "无监督学习方法", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 14 章",
        "description": "K-Means、层次聚类、DBSCAN、PCA、t-SNE 等无监督方法。能够发现数据中的隐藏结构。",
        "learning_objectives": ["实现 K-Means 与 K-Means++", "比较 PCA 与 t-SNE 的适用场景", "用轮廓系数评估聚类"],
        "keywords": ["K-Means", "PCA", "t-SNE", "聚类"],
        "typical_tasks": ["对用户分群做 K-Means", "用 PCA 可视化高维数据"],
        "common_misconceptions": ["混淆聚类与分类的评估指标", "直接对类别特征做 PCA"],
        "estimated_minutes": 300,
    },
    "decision_trees": {
        "name": "决策树与集成（进阶）", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 15 章",
        "description": "CART、ID3/C4.5、随机森林、GBDT、XGBoost。理解集成学习的偏差-方差互补。",
        "learning_objectives": ["计算信息增益与基尼系数", "实现随机森林", "比较 Bagging 与 Boosting"],
        "keywords": ["CART", "随机森林", "XGBoost", "GBDT"],
        "typical_tasks": ["训练信用卡欺诈检测模型", "用 SHAP 解释 XGBoost"],
        "common_misconceptions": ["认为树模型不需要特征缩放", "忽视类别特征编码"],
        "estimated_minutes": 300,
    },
    "svm": {
        "name": "支持向量机（SVM）", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 16 章",
        "description": "最大间隔、核函数、对偶问题与 SMO 算法。理解 SVM 的几何直觉与核技巧。",
        "learning_objectives": ["解释最大间隔的几何意义", "写出 SVM 的对偶形式", "选择合适的核函数"],
        "keywords": ["SVM", "核函数", "对偶", "SMO"],
        "typical_tasks": ["用 RBF 核完成非线性分类", "用网格搜索选 C 与 gamma"],
        "common_misconceptions": ["把 SVM 当万能分类器", "忽略核函数计算代价"],
        "estimated_minutes": 360,
    },
    "neural_networks": {
        "name": "神经网络基础（深度学习）", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 3 章",
        "description": "感知机、多层感知机、激活函数、损失函数与基础正则化。理解神经网络的前向与反向计算。",
        "learning_objectives": ["解释激活函数的作用", "推导 MSE 与交叉熵损失", "实现含 Dropout 的 MLP"],
        "keywords": ["MLP", "激活函数", "损失函数", "Dropout"],
        "typical_tasks": ["手写 MLP 分类 MNIST", "比较 ReLU 与 Sigmoid"],
        "common_misconceptions": ["认为更深的网络一定更好", "忽视梯度消失/爆炸"],
        "estimated_minutes": 300,
    },
    "backpropagation": {
        "name": "反向传播算法", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 17 章",
        "description": "链式法则、计算图、自动求导、梯度下降与动量法。理解 BP 算法的工程实现。",
        "learning_objectives": ["推导多层网络的 BP 公式", "比较 SGD、Momentum、Adam", "调试梯度异常"],
        "keywords": ["BP", "梯度下降", "Adam", "计算图"],
        "typical_tasks": ["手写 BP 训练 XOR 网络", "用学习率调度器"],
        "common_misconceptions": ["把学习率调大当成万能药", "忽视梯度裁剪"],
        "estimated_minutes": 360,
    },
    "mlp": {
        "name": "多层感知机（MLP）", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 13 章",
        "description": "全连接层、BN、Dropout 与正则化。理解 MLP 在结构化数据上的优势与局限。",
        "learning_objectives": ["搭建含 BN 的 MLP", "用 L2 正则化缓解过拟合", "对比 MLP 与树模型在表格数据上的表现"],
        "keywords": ["MLP", "BN", "Dropout", "正则化"],
        "typical_tasks": ["用 MLP 完成房价预测", "对比 MLP 与 XGBoost"],
        "common_misconceptions": ["对所有表格数据都首选 MLP", "忽视 BatchNorm 的位置"],
        "estimated_minutes": 240,
    },
    "cnn": {
        "name": "卷积神经网络（视觉）", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 4 章",
        "description": "卷积、池化、感受野、ResNet 与现代轻量 CNN。理解卷积对图像的归纳偏置。",
        "learning_objectives": ["解释卷积与池化的作用", "计算感受野", "用 ResNet 完成图像分类"],
        "keywords": ["CNN", "卷积", "池化", "ResNet"],
        "typical_tasks": ["用 CNN 完成 CIFAR-10 分类", "可视化卷积核"],
        "common_misconceptions": ["认为池化层有可学习参数", "忽视感受野的累积"],
        "estimated_minutes": 360,
    },
    "rnn": {
        "name": "循环神经网络（序列）", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 18 章",
        "description": "时序建模、BPTT、梯度消失/爆炸与序列填充。理解 RNN 在序列数据上的工作机制。",
        "learning_objectives": ["推导 RNN 的前向与反向", "解释 BPTT 的截断策略", "实现字符级语言模型"],
        "keywords": ["RNN", "BPTT", "梯度消失", "序列"],
        "typical_tasks": ["用 RNN 完成文本生成", "对比 RNN 与 Transformer"],
        "common_misconceptions": ["认为 RNN 能记忆所有历史", "忽视填充对梯度的污染"],
        "estimated_minutes": 300,
    },
    "lstm": {
        "name": "LSTM 与 GRU（门控）", "bloom": "apply", "difficulty": "advanced",
        "chapter": "AI 课 18 章",
        "description": "门控机制、长依赖、双向 LSTM 与 GRU。理解 LSTM 如何缓解梯度消失。",
        "learning_objectives": ["解释 LSTM 三个门的作用", "对比 LSTM 与 GRU", "用双向 LSTM 提升序列标注"],
        "keywords": ["LSTM", "GRU", "门控", "长依赖"],
        "typical_tasks": ["用 LSTM 完成情感分类", "用双向 LSTM 做 NER"],
        "common_misconceptions": ["认为 LSTM 解决一切长依赖", "忽视遗忘门初始化偏置"],
        "estimated_minutes": 300,
    },
    "attention_mechanism": {
        "name": "注意力机制（核心）", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 5 章",
        "description": "Self-Attention、Query/Key/Value、多头注意力与缩放点积。理解注意力的几何含义。",
        "learning_objectives": ["解释 Q/K/V 的角色", "推导多头注意力的参数量", "实现掩码注意力"],
        "keywords": ["Self-Attention", "QKV", "多头", "缩放点积"],
        "typical_tasks": ["手写 Self-Attention", "可视化注意力权重"],
        "common_misconceptions": ["认为注意力权重越高越重要", "忽视 mask 的因果性"],
        "estimated_minutes": 360,
    },
    "transformer": {
        "name": "Transformer 架构", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 5 章",
        "description": "Encoder/Decoder、位置编码、层归一化、残差连接。理解现代大语言模型的基础架构。",
        "learning_objectives": ["解释位置编码的必要性", "搭建 Encoder-Decoder", "用 PyTorch 实现完整 Transformer"],
        "keywords": ["Transformer", "位置编码", "Encoder", "Decoder"],
        "typical_tasks": ["用 Transformer 完成机器翻译", "微调 BERT 完成分类"],
        "common_misconceptions": ["把 BERT 当 Decoder", "忽视 Pre-LN 与 Post-LN 差异"],
        "estimated_minutes": 420,
    },
    "nlp_basics": {
        "name": "NLP 基础任务", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 19 章",
        "description": "分词、词向量、命名实体识别、文本分类。理解自然语言处理的基本任务与技术演进。",
        "learning_objectives": ["比较 jieba 与 BPE 分词", "训练 Word2Vec 词向量", "完成 NER 任务"],
        "keywords": ["分词", "Word2Vec", "NER", "文本分类"],
        "typical_tasks": ["用 Word2Vec 找近义词", "用 BERT 完成情感分类"],
        "common_misconceptions": ["认为分词只是切分", "混淆词性标注与 NER"],
        "estimated_minutes": 240,
    },
    "rag": {
        "name": "检索增强生成（RAG 实战）", "bloom": "evaluate", "difficulty": "advanced",
        "chapter": "AI 课 9 章",
        "description": "文档切块、嵌入、检索、重排、生成。理解 RAG 全链路及其在企业知识问答中的落地。",
        "learning_objectives": ["比较滑动窗口与语义切块", "选择合适的嵌入模型", "评估 RAG 答案忠实度"],
        "keywords": ["RAG", "嵌入", "检索", "重排"],
        "typical_tasks": ["搭建 FAQ 检索问答", "用 RAG 减少大模型幻觉"],
        "common_misconceptions": ["认为 RAG 解决所有幻觉", "忽视检索质量对答案的影响"],
        "estimated_minutes": 360,
    },
    "reinforcement_learning": {
        "name": "强化学习进阶", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 7 章",
        "description": "MDP、Q-Learning、策略梯度、PPO 与奖励设计。理解强化学习的核心挑战。",
        "learning_objectives": ["推导 Bellman 方程", "实现 Q-Learning", "解释 PPO 的剪切目标"],
        "keywords": ["MDP", "Q-Learning", "PPO", "策略梯度"],
        "typical_tasks": ["训练 CartPole 智能体", "实现 DQN 玩 Atari"],
        "common_misconceptions": ["认为奖励越大越好", "忽视探索-利用平衡"],
        "estimated_minutes": 420,
    },
    "ai_project_practice": {
        "name": "AI 项目实战（端到端）", "bloom": "create", "difficulty": "advanced",
        "chapter": "AI 课 12 章",
        "description": "数据采集、清洗、建模、评估、部署、监控全流程。理解工程化 AI 项目的最佳实践。",
        "learning_objectives": ["规划 AI 项目里程碑", "搭建数据-训练-部署流水线", "监控数据漂移与性能衰减"],
        "keywords": ["数据", "建模", "部署", "监控"],
        "typical_tasks": ["完成 Kaggle 完整比赛", "部署模型到生产环境"],
        "common_misconceptions": ["忽视数据质量", "一次性发布不做监控"],
        "estimated_minutes": 600,
    },
    "multi_agent_systems": {
        "name": "多智能体系统（MAS）", "bloom": "create", "difficulty": "advanced",
        "chapter": "AI 课 6 章",
        "description": "通信、协作、对抗、Debate。理解多智能体协同的协议设计与工程实现。",
        "learning_objectives": ["设计多智能体通信协议", "实现 Planner-Worker-Critic 流水线", "评估多 Agent 协作效果"],
        "keywords": ["MAS", "Debate", "协作", "对抗"],
        "typical_tasks": ["用 Debate 提升答案质量", "实现角色分工流水线"],
        "common_misconceptions": ["把多 Agent 当成多线程", "忽视通信开销"],
        "estimated_minutes": 480,
    },
    "multimodal_llm": {
        "name": "多模态大模型（VLM）", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 8 章",
        "description": "视觉-语言、音频、跨模态对齐。理解多模态大模型的架构与训练范式。",
        "learning_objectives": ["解释跨模态对齐原理", "调用多模态 API 完成图文问答", "评估图文生成质量"],
        "keywords": ["VLM", "多模态", "跨模态", "图文"],
        "typical_tasks": ["用 GPT-4V 完成图理解", "训练 CLIP 检索器"],
        "common_misconceptions": ["认为多模态只是图像分类", "忽视 token 化的差异"],
        "estimated_minutes": 360,
    },
    "ai_agent": {
        "name": "AI Agent（规划与工具）", "bloom": "create", "difficulty": "advanced",
        "chapter": "AI 课 10 章",
        "description": "规划、工具调用、反思、ReAct。理解 LLM 驱动的智能体设计模式。",
        "learning_objectives": ["实现 Plan-Act-Observe 循环", "设计工具注册与解析", "评估 Agent 任务完成度"],
        "keywords": ["Agent", "ReAct", "工具调用", "规划"],
        "typical_tasks": ["搭建 PDF 问答 Agent", "实现网络搜索 Agent"],
        "common_misconceptions": ["认为 Agent 越复杂越好", "忽视工具错误处理"],
        "estimated_minutes": 480,
    },
    "mcp_protocol": {
        "name": "MCP 协议（上下文）", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 11 章",
        "description": "Model Context Protocol 消息格式、工具描述与会话管理。理解模型与外部系统的标准化交互。",
        "learning_objectives": ["解释 MCP 的消息结构", "实现一个 MCP 客户端", "调试 MCP 工具调用错误"],
        "keywords": ["MCP", "上下文", "协议", "工具"],
        "typical_tasks": ["实现自定义 MCP 工具", "用 MCP 接入数据库"],
        "common_misconceptions": ["把 MCP 当 RPC", "忽视权限与作用域"],
        "estimated_minutes": 240,
    },
    "learning_science": {
        "name": "学习科学理论", "bloom": "understand", "difficulty": "basic",
        "chapter": "AI 课 2 章",
        "description": "认知负荷、间隔重复、刻意练习。理解学习的科学原理与个性化学习的理论基础。",
        "learning_objectives": ["解释艾宾浩斯遗忘曲线", "比较间隔重复与集中练习", "设计刻意练习计划"],
        "keywords": ["认知负荷", "间隔重复", "刻意练习", "遗忘曲线"],
        "typical_tasks": ["用 SM2 算法安排复习", "设计练习反馈闭环"],
        "common_misconceptions": ["把反复看书当练习", "忽视间隔与反馈"],
        "estimated_minutes": 180,
    },
    "cognitive_diagnosis": {
        "name": "认知诊断模型", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 2 章",
        "description": "BKT、DINA、IRT、错因分析。理解认知诊断在个性化学习中的应用。",
        "learning_objectives": ["解释 BKT 的四个参数", "实现简化 DINA", "归因错题的知识缺漏"],
        "keywords": ["BKT", "DINA", "IRT", "错因"],
        "typical_tasks": ["用 BKT 估计掌握度", "用 DINA 诊断属性掌握"],
        "common_misconceptions": ["把 BKT 当准确率", "忽视项目反应理论假设"],
        "estimated_minutes": 360,
    },
    "data_visualization": {
        "name": "数据可视化（分析）", "bloom": "apply", "difficulty": "basic",
        "chapter": "AI 课 2 章",
        "description": "图表选择、感知原则、可解释性。理解如何用可视化讲述数据故事。",
        "learning_objectives": ["根据数据类型选择图表", "避免常见可视化误区", "设计可解释的可视化"],
        "keywords": ["图表选择", "感知原则", "可解释性"],
        "typical_tasks": ["画学习曲线诊断模型", "用热力图展示错因分布"],
        "common_misconceptions": ["滥用饼图", "忽视颜色编码障碍"],
        "estimated_minutes": 180,
    },
    "learning_analytics_ethics": {
        "name": "学习分析伦理（治理）", "bloom": "evaluate", "difficulty": "basic",
        "chapter": "AI 课 2 章",
        "description": "隐私、公平、知情同意。理解学习分析在数据使用中的伦理边界。",
        "learning_objectives": ["识别学习分析中的隐私风险", "设计公平的评估指标", "取得有效的知情同意"],
        "keywords": ["隐私", "公平", "知情同意", "治理"],
        "typical_tasks": ["评审 AI 产品的隐私设计", "撰写伦理影响评估"],
        "common_misconceptions": ["把数据匿名化当绝对安全", "忽视算法偏见"],
        "estimated_minutes": 180,
    },
    # -------- 新 KPs（21 个，缺一切元数据）--------
    "AI_001": {
        "name": "人工智能概述", "bloom": "understand", "difficulty": "basic",
        "chapter": "AI 课 1 章",
        "description": "理解 AI 的定义、发展阶段（符号主义、连接主义、深度学习）与典型应用场景。能够描述 AI 与机器学习、深度学习的关系。",
        "learning_objectives": ["解释 AI / ML / DL 三者关系", "列举三类 AI 应用", "评估 AI 的能力边界"],
        "keywords": ["AI", "发展史", "应用场景"],
        "typical_tasks": ["做一份 AI 综述报告", "评估一个 AI 产品的能力"],
        "common_misconceptions": ["把 AI 等同于 ChatGPT", "忽视 AI 的局限性"],
        "estimated_minutes": 90,
    },
    "AI_002": {
        "name": "搜索算法", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 1 章",
        "description": "无信息搜索（BFS/DFS/UCS）、启发式搜索（贪婪、A*）与对抗搜索（Minimax、α-β）。能够为问题选择合适搜索策略。",
        "learning_objectives": ["实现 BFS/DFS 解八数码", "用 A* 求解最短路径", "用 α-β 剪枝实现井字棋"],
        "keywords": ["BFS", "A*", "Minimax", "α-β"],
        "typical_tasks": ["用 A* 求解迷宫", "实现 α-β 井字棋"],
        "common_misconceptions": ["A* 总能找到最优解（需可采纳启发）", "忽视启发式设计代价"],
        "estimated_minutes": 240,
    },
    "AI_003": {
        "name": "知识表示与推理", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 1 章",
        "description": "谓词逻辑、产生式系统、语义网络与知识图谱。理解知识表示的方法与推理机制。",
        "learning_objectives": ["用谓词逻辑表达知识", "构建小型知识图谱", "完成前向/反向推理"],
        "keywords": ["谓词逻辑", "知识图谱", "推理"],
        "typical_tasks": ["用 SWRL 写推理规则", "构建课程知识图谱"],
        "common_misconceptions": ["把本体当数据库", "忽视推理的可计算性"],
        "estimated_minutes": 240,
    },
    "AI_004": {
        "name": "机器学习基础", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 2 章",
        "description": "机器学习三要素（模型、损失、优化）、数据集划分与评估指标。理解监督/无监督学习的边界。",
        "learning_objectives": ["解释三要素的作用", "完成数据集划分", "选用合适评估指标"],
        "keywords": ["模型", "损失", "优化", "评估"],
        "typical_tasks": ["用交叉验证选模型", "画混淆矩阵"],
        "common_misconceptions": ["把训练集当测试集", "只看准确率"],
        "estimated_minutes": 180,
    },
    "AI_005": {
        "name": "监督学习算法", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 5 章",
        "description": "线性回归、逻辑回归、决策树、SVM、KNN 的原理与适用场景。能够根据数据选择合适算法。",
        "learning_objectives": ["比较 5 类监督算法", "为给定问题选算法", "解释算法间的偏差-方差"],
        "keywords": ["监督学习", "对比", "选型"],
        "typical_tasks": ["对比 5 个算法在鸢尾花上的表现", "解释选型理由"],
        "common_misconceptions": ["对所有问题都选最复杂算法", "忽视数据预处理"],
        "estimated_minutes": 240,
    },
    "AI_005_01": {
        "name": "线性回归与逻辑回归", "bloom": "apply", "difficulty": "basic",
        "chapter": "AI 课 5 章",
        "description": "线性回归的最小二乘解与梯度下降；逻辑回归的二分类与正则化。能够推导公式并实现。",
        "learning_objectives": ["推导线性回归的闭式解", "用梯度下降训练逻辑回归", "用 L1/L2 正则化"],
        "keywords": ["线性回归", "逻辑回归", "正则化"],
        "typical_tasks": ["用线性回归预测房价", "用逻辑回归做信用卡欺诈"],
        "common_misconceptions": ["把逻辑回归当回归", "忽视特征归一化"],
        "estimated_minutes": 180,
    },
    "AI_005_02": {
        "name": "决策树与集成学习", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 5 章",
        "description": "ID3/C4.5/CART、Bagging、Boosting 与 Stacking。理解集成学习对偏差-方差的调节。",
        "learning_objectives": ["比较三类集成方法", "实现随机森林", "用 XGBoost 完成分类"],
        "keywords": ["决策树", "Bagging", "Boosting"],
        "typical_tasks": ["用 XGBoost 做销量预测", "解释特征重要性"],
        "common_misconceptions": ["认为树模型不需要调参", "忽视类别特征处理"],
        "estimated_minutes": 240,
    },
    "AI_005_03": {
        "name": "支持向量机SVM", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 5 章",
        "description": "硬间隔 SVM、软间隔与核函数。理解 SVM 的几何含义与对偶形式。",
        "learning_objectives": ["解释最大间隔几何意义", "写出 SVM 对偶形式", "选择 RBF/多项式核"],
        "keywords": ["SVM", "核函数", "对偶"],
        "typical_tasks": ["用 RBF 核完成非线性分类", "调 C 与 gamma"],
        "common_misconceptions": ["认为 SVM 总是最优", "忽视核函数计算复杂度"],
        "estimated_minutes": 300,
    },
    "AI_006": {
        "name": "神经网络与深度学习", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 3 章",
        "description": "神经元模型、激活函数、前馈网络与 BP 算法。理解深度学习的基本结构与训练机制。",
        "learning_objectives": ["解释激活函数的作用", "推导 BP 公式", "用 PyTorch 训练 MLP"],
        "keywords": ["神经网络", "深度学习", "BP"],
        "typical_tasks": ["用 MLP 分类 MNIST", "对比不同激活函数"],
        "common_misconceptions": ["认为网络越深越好", "忽视梯度问题"],
        "estimated_minutes": 240,
    },
    "AI_006_01": {
        "name": "卷积神经网络(CNN)", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 4 章",
        "description": "卷积层、池化层、感受野与经典 CNN 架构。能够用 CNN 完成图像分类与目标检测。",
        "learning_objectives": ["解释卷积与池化", "计算感受野", "用 ResNet 完成分类"],
        "keywords": ["CNN", "卷积", "ResNet"],
        "typical_tasks": ["用 ResNet 分类 CIFAR-10", "可视化卷积核"],
        "common_misconceptions": ["忽视感受野累积", "认为池化有参数"],
        "estimated_minutes": 300,
    },
    "AI_006_02": {
        "name": "循环神经网络(RNN)", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 5 章",
        "description": "RNN 前向、BPTT、梯度问题与简单序列任务。理解序列建模的挑战。",
        "learning_objectives": ["推导 RNN 的 BPTT", "实现字符级语言模型", "解释梯度消失/爆炸"],
        "keywords": ["RNN", "BPTT", "梯度"],
        "typical_tasks": ["用 RNN 生成文本", "调试梯度爆炸"],
        "common_misconceptions": ["RNN 能记住所有历史", "忽视填充对梯度的影响"],
        "estimated_minutes": 300,
    },
    "AI_006_03": {
        "name": "Transformer与注意力机制", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 5 章",
        "description": "Self-Attention、Multi-Head、位置编码与 Transformer 完整结构。理解现代大模型的基础架构。",
        "learning_objectives": ["推导 Self-Attention 公式", "解释位置编码必要性", "搭建 Transformer"],
        "keywords": ["Transformer", "Self-Attention", "位置编码"],
        "typical_tasks": ["用 Transformer 翻译", "微调 BERT"],
        "common_misconceptions": ["BERT 是 Decoder", "忽视 mask 的因果性"],
        "estimated_minutes": 360,
    },
    "AI_007": {
        "name": "自然语言处理(NLP)", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 5 章",
        "description": "分词、词向量、命名实体识别、文本分类、机器翻译。理解 NLP 的核心任务与演进。",
        "learning_objectives": ["比较经典与预训练方法", "用 BERT 完成文本分类", "完成 NER 任务"],
        "keywords": ["NLP", "BERT", "NER"],
        "typical_tasks": ["用 BERT 做情感分析", "完成机器翻译"],
        "common_misconceptions": ["把 BERT 当通用模型", "忽视任务特定微调"],
        "estimated_minutes": 240,
    },
    "AI_008": {
        "name": "计算机视觉(CV)", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 4 章",
        "description": "图像分类、目标检测、语义分割与经典模型。理解 CV 的主要任务与现代方法。",
        "learning_objectives": ["用 ResNet 做图像分类", "用 YOLO 做目标检测", "用 U-Net 做分割"],
        "keywords": ["CV", "目标检测", "分割"],
        "typical_tasks": ["用 YOLO 检测行人", "用 U-Net 做医学图像分割"],
        "common_misconceptions": ["把分类当万能任务", "忽视数据增强"],
        "estimated_minutes": 300,
    },
    "AI_009": {
        "name": "强化学习", "bloom": "analyze", "difficulty": "advanced",
        "chapter": "AI 课 7 章",
        "description": "MDP、Q-Learning、策略梯度与 PPO。理解强化学习在游戏、机器人等场景的应用。",
        "learning_objectives": ["推导 Bellman 方程", "实现 Q-Learning", "训练 PPO 智能体"],
        "keywords": ["MDP", "Q-Learning", "PPO"],
        "typical_tasks": ["训练 CartPole", "实现 DQN"],
        "common_misconceptions": ["奖励越大越好", "忽视探索"],
        "estimated_minutes": 360,
    },
    "AI_010": {
        "name": "AI伦理与前沿趋势", "bloom": "evaluate", "difficulty": "basic",
        "chapter": "AI 课 1 章",
        "description": "AI 伦理、对齐、可解释性与前沿趋势。理解 AI 发展中的社会议题与技术挑战。",
        "learning_objectives": ["列举 AI 伦理问题", "解释可解释性方法", "评估前沿趋势的影响"],
        "keywords": ["AI 伦理", "可解释性", "前沿趋势"],
        "typical_tasks": ["写一份 AI 伦理影响评估", "调研 AGI 进展"],
        "common_misconceptions": ["把可解释性当可视化", "忽视社会影响"],
        "estimated_minutes": 120,
    },
    "CODE_001": {
        "name": "Python编程基础", "bloom": "apply", "difficulty": "basic",
        "chapter": "Python 先修课 1 章",
        "description": "Python 语法、变量、控制流、函数与文件操作。能够独立编写中等规模脚本。",
        "learning_objectives": ["使用控制流组织程序", "编写带参数的函数", "读写文件"],
        "keywords": ["Python", "语法", "控制流", "文件"],
        "typical_tasks": ["写一个数据清洗脚本", "封装工具函数"],
        "common_misconceptions": ["混淆可变与不可变类型", "忽视异常处理"],
        "estimated_minutes": 240,
    },
    "CODE_002": {
        "name": "深度学习框架(PyTorch)", "bloom": "apply", "difficulty": "intermediate",
        "chapter": "AI 课 17 章",
        "description": "PyTorch 张量、自动求导、nn.Module 与 DataLoader。能够用 PyTorch 搭建并训练网络。",
        "learning_objectives": ["使用 Tensor 完成运算", "实现自定义 nn.Module", "用 DataLoader 加载数据"],
        "keywords": ["PyTorch", "Tensor", "DataLoader"],
        "typical_tasks": ["用 PyTorch 训练 MLP", "实现自定义 Dataset"],
        "common_misconceptions": ["混淆 requires_grad", "忽视 batch 维度"],
        "estimated_minutes": 300,
    },
    "MATH_001": {
        "name": "线性代数基础", "bloom": "understand", "difficulty": "basic",
        "chapter": "AI 课 2 章",
        "description": "矩阵、向量、行列式、特征值与 SVD 分解。理解线性代数在机器学习中的作用。",
        "learning_objectives": ["解释矩阵乘法的几何意义", "计算特征值", "理解 SVD 的作用"],
        "keywords": ["矩阵", "特征值", "SVD"],
        "typical_tasks": ["用 NumPy 求解线性方程组", "完成 PCA 推导"],
        "common_misconceptions": ["忽视几何含义", "混淆左右奇异向量"],
        "estimated_minutes": 240,
    },
    "MATH_002": {
        "name": "概率论与数理统计", "bloom": "understand", "difficulty": "basic",
        "chapter": "AI 课 2 章",
        "description": "随机变量、概率分布、贝叶斯公式与统计推断。理解概率在机器学习中的核心地位。",
        "learning_objectives": ["解释常见分布的适用场景", "应用贝叶斯公式", "完成置信区间估计"],
        "keywords": ["概率", "贝叶斯", "统计推断"],
        "typical_tasks": ["用贝叶斯做垃圾邮件分类", "完成 A/B 检验"],
        "common_misconceptions": ["混淆先验与后验", "忽视独立性假设"],
        "estimated_minutes": 240,
    },
    "MATH_003": {
        "name": "微积分与最优化", "bloom": "understand", "difficulty": "intermediate",
        "chapter": "AI 课 2 章",
        "description": "导数、偏导数、链式法则与梯度下降。理解优化在机器学习中的核心地位。",
        "learning_objectives": ["计算多元函数偏导", "应用链式法则", "解释梯度下降收敛条件"],
        "keywords": ["导数", "梯度", "优化"],
        "typical_tasks": ["手写梯度下降", "对比 Adam 与 SGD"],
        "common_misconceptions": ["认为梯度为零就是最优", "忽视学习率"],
        "estimated_minutes": 240,
    },
}


# ================================================================
# KP 关系定义（100-130 目标）
# ================================================================
# 既有 79 条 + 新增 30-40 条 = 110-119 条
KP_RELATIONS_NEW: List[Dict[str, Any]] = [
    # MATH → AI/ML 基础（先修）— 8 条
    {"source": "MATH_001", "target": "linear_algebra", "type": "related_to", "weight": 0.85},
    {"source": "MATH_001", "target": "backpropagation", "type": "applies_to", "weight": 0.75},
    {"source": "MATH_001", "target": "cnn", "type": "applies_to", "weight": 0.70},
    {"source": "MATH_002", "target": "probability_statistics", "type": "related_to", "weight": 0.90},
    {"source": "MATH_002", "target": "supervised_learning", "type": "applies_to", "weight": 0.70},
    {"source": "MATH_002", "target": "reinforcement_learning", "type": "applies_to", "weight": 0.75},
    {"source": "MATH_003", "target": "backpropagation", "type": "applies_to", "weight": 0.80},
    {"source": "MATH_003", "target": "ml_basics", "type": "applies_to", "weight": 0.70},

    # Python 基础 → ML 工具链 — 5 条
    {"source": "CODE_001", "target": "data_structures", "type": "prerequisite", "weight": 0.85},
    {"source": "CODE_002", "target": "mlp", "type": "applies_to", "weight": 0.80},
    {"source": "CODE_002", "target": "cnn", "type": "applies_to", "weight": 0.80},
    {"source": "CODE_002", "target": "transformer", "type": "applies_to", "weight": 0.75},
    {"source": "CODE_002", "target": "ai_project_practice", "type": "applies_to", "weight": 0.85},

    # AI 001-010（基础）→ 后续（挑核心 14 条）— 14 条
    {"source": "AI_001", "target": "ml_basics", "type": "prerequisite", "weight": 0.95},
    {"source": "AI_001", "target": "learning_analytics_ethics", "type": "related_to", "weight": 0.70},
    {"source": "AI_002", "target": "AI_003", "type": "part_of", "weight": 0.75},
    {"source": "AI_002", "target": "reinforcement_learning", "type": "applies_to", "weight": 0.65},
    {"source": "AI_003", "target": "rag", "type": "applies_to", "weight": 0.80},
    {"source": "AI_004", "target": "ml_basics", "type": "related_to", "weight": 0.95},
    {"source": "AI_005", "target": "supervised_learning", "type": "extends", "weight": 0.90},
    {"source": "AI_005_01", "target": "supervised_learning", "type": "part_of", "weight": 0.85},
    {"source": "AI_005_02", "target": "decision_trees", "type": "related_to", "weight": 0.90},
    {"source": "AI_005_03", "target": "svm", "type": "related_to", "weight": 0.95},
    {"source": "AI_006", "target": "neural_networks", "type": "extends", "weight": 0.95},
    {"source": "AI_006_01", "target": "cnn", "type": "related_to", "weight": 0.95},
    {"source": "AI_006_02", "target": "rnn", "type": "related_to", "weight": 0.95},
    {"source": "AI_006_03", "target": "transformer", "type": "related_to", "weight": 0.95},

    # 应用层 + 跨域 — 8 条
    {"source": "AI_007", "target": "nlp_basics", "type": "extends", "weight": 0.95},
    {"source": "AI_008", "target": "cnn", "type": "applies_to", "weight": 0.85},
    {"source": "AI_009", "target": "reinforcement_learning", "type": "related_to", "weight": 0.95},
    {"source": "AI_010", "target": "learning_analytics_ethics", "type": "related_to", "weight": 0.85},
    {"source": "mcp_protocol", "target": "ai_agent", "type": "applies_to", "weight": 0.75},
    {"source": "multimodal_llm", "target": "ai_project_practice", "type": "applies_to", "weight": 0.75},
    {"source": "multi_agent_systems", "target": "ai_project_practice", "type": "applies_to", "weight": 0.80},
    {"source": "transformer", "target": "nlp_basics", "type": "applies_to", "weight": 0.80},
]


# ================================================================
# BKT 行为数据：错题 stem 模板 / Assessment 事件
# ================================================================
MISTAKE_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "python_basics": [
        {"stem": "在 Python 中，列表与元组的主要区别是？", "answer": "可变性", "etype": "concept_boundary"},
        {"stem": "Python 中 GIL 的影响是？", "answer": "限制多线程并行", "etype": "concept_boundary"},
    ],
    "supervised_learning": [
        {"stem": "逻辑回归的输出范围是？", "answer": "[0,1]", "etype": "concept_boundary"},
        {"stem": "线性回归的损失函数是？", "answer": "MSE", "etype": "knowledge_gap"},
    ],
    "cnn": [
        {"stem": "CNN 中池化层的作用是？", "answer": "降维 + 保持平移不变性", "etype": "misconception"},
        {"stem": "ResNet 引入残差连接的主要目的是？", "answer": "缓解梯度消失", "etype": "knowledge_gap"},
    ],
    "transformer": [
        {"stem": "Transformer 中位置编码的作用是？", "answer": "注入序列顺序信息", "etype": "knowledge_gap"},
        {"stem": "Self-Attention 三个矩阵 QKV 分别来自？", "answer": "同一输入的不同投影", "etype": "misconception"},
    ],
    "rag": [
        {"stem": "RAG 系统最容易出现的失败模式是？", "answer": "检索召回不足", "etype": "knowledge_gap"},
        {"stem": "RAG 与微调的主要区别是？", "answer": "外部知识 vs 参数化知识", "etype": "concept_boundary"},
    ],
    "reinforcement_learning": [
        {"stem": "Q-Learning 是基于什么的算法？", "answer": "值函数", "etype": "knowledge_gap"},
        {"stem": "PPO 的核心机制是？", "answer": "剪切目标", "etype": "misconception"},
    ],
    "ai_agent": [
        {"stem": "ReAct 范式中 Act 之后的下一步是？", "answer": "Observation", "etype": "concept_boundary"},
        {"stem": "Agent 工具调用错误的主要原因是？", "answer": "参数 schema 不匹配", "etype": "careless"},
    ],
    "ml_basics": [
        {"stem": "过拟合的主要表现是？", "answer": "训练好测试差", "etype": "misconception"},
        {"stem": "评估模型最常用的交叉验证方法是？", "answer": "k-fold", "etype": "knowledge_gap"},
    ],
}


# ================================================================
# 工具函数
# ================================================================
def _seeded_random() -> random.Random:
    return random.Random(SEED)


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return f"kg_demo_v1_{prefix}_{raw}"


def _make_kp_payload() -> Dict[str, Dict[str, Any]]:
    """返回 KP_id -> {description, metadata_data} 计划。"""
    out: Dict[str, Dict[str, Any]] = {}
    for kp_id, meta in KP_META.items():
        out[kp_id] = {
            "description": meta["description"],
            "metadata": {
                "bloom_level": meta["bloom"],
                "difficulty": meta["difficulty"],
                "chapter": meta["chapter"],
                "learning_objectives": list(meta["learning_objectives"]),
                "keywords": list(meta["keywords"]),
                "typical_tasks": list(meta["typical_tasks"]),
                "common_misconceptions": list(meta["common_misconceptions"]),
                "estimated_minutes": int(meta["estimated_minutes"]),
                "synthetic_demo": True,
                "seed_source": SEED_SOURCE,
            },
        }
    return out


# ================================================================
# Plan 收集
# ================================================================
def collect_kp_plans() -> List[Tuple[str, str, dict, dict]]:
    """(kp_id, action, existing_meta, plan) — action in {'update_full','merge_metadata'}"""
    plans: List[Tuple[str, str, dict, dict]] = []
    payloads = _make_kp_payload()
    with SessionLocal() as db:
        existing = {kp.id: kp for kp in db.query(models.KnowledgePointRecord).all()}
    for kp_id, payload in payloads.items():
        if kp_id not in existing:
            # 不在 DB 中 → 全量新增（少见，但允许）
            plans.append((kp_id, "insert", {}, {"description": payload["description"],
                                                "metadata_data": payload["metadata"]}))
            continue
        row = existing[kp_id]
        existing_meta = dict(row.metadata_data or {})
        existing_desc = row.description or ""
        # 描述：已有非空 → 保留；否则用 plan
        new_desc = existing_desc if existing_desc.strip() else payload["description"]
        # metadata: 浅合并
        merged = dict(existing_meta)
        changed = False
        for k, v in payload["metadata"].items():
            if k in ("synthetic_demo", "seed_source"):
                merged[k] = v
                continue
            if k not in merged or not merged.get(k):
                merged[k] = v
                changed = True
        # 即使 metadata 没变也写入以保持标记；但若完全一致则不重写
        if (new_desc != existing_desc) or changed:
            plans.append((kp_id, "update", {"metadata": existing_meta, "description": existing_desc},
                          {"description": new_desc, "metadata_data": merged}))
        else:
            # 已完整 — 仅补齐合成标记（不动其他）
            if not (merged.get("synthetic_demo") and merged.get("seed_source") == SEED_SOURCE):
                merged["synthetic_demo"] = True
                merged["seed_source"] = SEED_SOURCE
                plans.append((kp_id, "tag_only", {"metadata": existing_meta},
                              {"description": existing_desc, "metadata_data": merged}))
    return plans


def collect_relation_plans() -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []
    with SessionLocal() as db:
        existing_pairs = {
            (r.source_id, r.target_id, r.relation_type)
            for r in db.query(models.KnowledgeRelationRecord).all()
        }
        all_kp_ids = {kp.id for kp in db.query(models.KnowledgePointRecord).all()}
    for rel in KP_RELATIONS_NEW:
        s, t, wtype = rel["source"], rel["target"], rel["type"]
        if s not in all_kp_ids or t not in all_kp_ids:
            continue
        if s == t:
            continue
        if wtype not in ALLOWED_RELATION_TYPES:
            continue
        w = max(0.4, min(1.0, float(rel.get("weight", 0.5))))
        if (s, t, wtype) in existing_pairs:
            continue
        plans.append({
            "source_id": s, "target_id": t, "relation_type": wtype, "weight": w,
            "metadata_data": {"synthetic_demo": True, "seed_source": SEED_SOURCE},
        })
    return plans


def collect_bkt_plans() -> List[Dict[str, Any]]:
    """对尚未覆盖的 KP 添加 8-20 名演示学生的 BKT 记录。"""
    plans: List[Dict[str, Any]] = []
    rng = _seeded_random()
    # 难度映射（basic=1, intermediate=2, advanced=3）
    diff_to_penalty = {"basic": 0.0, "intermediate": 0.08, "advanced": 0.18}
    with SessionLocal() as db:
        existing_pairs = {
            (r.user_id, r.knowledge_point_id)
            for r in db.query(models.BktStateRecord).all()
        }
        kps = {kp.id: kp for kp in db.query(models.KnowledgePointRecord).all()}
    # 找出尚未覆盖的 KP
    covered_kps = {kp_id for (u, kp_id) in existing_pairs}
    missing_kps = [kp_id for kp_id in kps if kp_id not in covered_kps]
    # 对每个 missing KP，挑选 8-20 个学生
    for kp_id in missing_kps:
        kp = kps[kp_id]
        meta = kp.metadata_data or {}
        diff = meta.get("difficulty", "intermediate")
        penalty = diff_to_penalty.get(diff, 0.08)
        # 高 tier 学生优先出现；随机选 8-20
        student_count = rng.randint(12, 18)
        # 抽取学生：分层 4:6:3 (high:stable:risk)
        n_high = max(2, round(student_count * 0.25))
        n_stable = max(4, round(student_count * 0.55))
        n_risk = max(2, student_count - n_high - n_stable)
        high_students = [s for s, t in TIER_MAP.items() if t == "high"]
        stable_students = [s for s, t in TIER_MAP.items() if t == "stable"]
        risk_students = [s for s, t in TIER_MAP.items() if t == "risk"]
        chosen = []
        chosen += rng.sample(high_students, min(n_high, len(high_students)))
        chosen += rng.sample(stable_students, min(n_stable, len(stable_students)))
        chosen += rng.sample(risk_students, min(n_risk, len(risk_students)))
        for user_id in chosen:
            tier = TIER_MAP[user_id]
            base = TIER_BASE_MASTERY[tier]
            # 难度惩罚 + 噪声
            mastery = base - penalty + rng.uniform(-0.06, 0.06)
            mastery = max(0.05, min(0.98, mastery))
            # 历史 4-10 条
            n_hist = rng.randint(4, 8)
            now = time.time()
            history = []
            for j in range(n_hist):
                ts = now - rng.uniform(1, 30) * 86400
                is_correct = rng.random() < mastery
                history.append({
                    "timestamp": ts,
                    "correct": bool(is_correct),
                    "source": rng.choice(["quiz", "practice", "question"]),
                    "difficulty": diff,
                    "response_time_seconds": rng.randint(20, 180),
                    "synthetic_demo": True,
                    "seed_source": SEED_SOURCE,
                })
            plans.append({
                "user_id": user_id,
                "knowledge_point_id": kp_id,
                "p_learned": round(mastery, 4),
                "p_transit": round(0.08 + rng.uniform(-0.02, 0.05), 4),
                "p_slip": round(0.05 + rng.uniform(-0.02, 0.04), 4),
                "p_guess": round(0.15 + rng.uniform(-0.05, 0.05), 4),
                "history": history,
            })
    return plans


def collect_mistake_plans() -> List[Dict[str, Any]]:
    """为每 KP 增 0-3 条错题（demo 学生）。"""
    plans: List[Dict[str, Any]] = []
    rng = _seeded_random()
    risk_students = [s for s, t in TIER_MAP.items() if t == "risk"]
    stable_students = [s for s, t in TIER_MAP.items() if t == "stable"]
    with SessionLocal() as db:
        kp_ids = [kp.id for kp in db.query(models.KnowledgePointRecord).all()]
    n_per_kp = rng.randint(0, 3)
    for kp_id in kp_ids:
        templates = MISTAKE_TEMPLATES.get(kp_id, [
            {"stem": f"针对「{kp_id}」知识点的常见错误示例", "answer": "略", "etype": "knowledge_gap"},
        ])
        # 错题集中在风险学生 + 部分稳定学生
        student_pool = risk_students + stable_students[:3]
        for i in range(n_per_kp):
            user_id = rng.choice(student_pool)
            tpl = rng.choice(templates)
            etype = tpl["etype"]
            if etype not in ALLOWED_MISTAKE_TYPES:
                etype = "knowledge_gap"
            mid = _stable_id("mistake", user_id, kp_id, i)
            plans.append({
                "id": mid,
                "user_id": user_id,
                "knowledge_point_id": kp_id,
                "question_data": {
                    "stem": tpl["stem"],
                    "topic": kp_id,
                    "difficulty": "intermediate",
                    "expected_answer": tpl["answer"],
                    "synthetic_demo": True,
                    "seed_source": SEED_SOURCE,
                },
                "error_type": etype,
                "analysis": f"该错题主要表现为{etype}，建议复习「{kp_id}」对应章节并完成 3-5 道变式练习。",
                "created_at": time.time() - rng.uniform(0, 30) * 86400,
            })
    return plans


def collect_assessment_plans() -> List[Dict[str, Any]]:
    """每个学生 30 天内 8-20 条学习活动（quiz/resource_view/question/practice）。"""
    plans: List[Dict[str, Any]] = []
    rng = _seeded_random()
    now = time.time()
    with SessionLocal() as db:
        kp_ids = [kp.id for kp in db.query(models.KnowledgePointRecord).all()]
    for user_id in DEMO_STUDENTS:
        tier = TIER_MAP[user_id]
        base = TIER_BASE_MASTERY[tier]
        # 风险学生 7-30 天未活跃
        if tier == "risk":
            n_records = rng.randint(0, 4)
            oldest_age = rng.randint(7, 30)
        else:
            n_records = rng.randint(10, 18)
            oldest_age = rng.randint(1, 12)
        # 时间分布：30 天内错开
        day_offsets = sorted(rng.uniform(0.5, oldest_age * 1.0) for _ in range(n_records))
        for k, day_offset in enumerate(day_offsets):
            rtype = rng.choices(
                list(ALLOWED_RECORD_TYPES), weights=[0.35, 0.2, 0.25, 0.2]
            )[0]
            kp = rng.choice(kp_ids)
            score = base + rng.uniform(-0.18, 0.18)
            score = max(0.0, min(1.0, score))
            duration = rng.randint(60, 600) if rtype == "quiz" else rng.randint(30, 360)
            ext_id = _stable_id("assess", user_id, k, day_offset)
            plans.append({
                "external_id": ext_id,
                "user_id": user_id,
                "record_type": rtype,
                "score": round(score, 4),
                "topic": kp,
                "duration": float(duration),
                "metadata_data": {
                    "synthetic_demo": True,
                    "seed_source": SEED_SOURCE,
                    "demo_day_offset_days": round(day_offset, 2),
                },
                "timestamp": now - day_offset * 86400,
            })
    return plans


def collect_profile_plans() -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []
    rng = _seeded_random()
    learning_styles = [
        ("视觉型", "实践型"), ("听觉型", "阅读型"),
        ("动觉型", "视觉型"), ("阅读型", "实践型"),
    ]
    for i, user_id in enumerate(DEMO_STUDENTS):
        tier = TIER_MAP[user_id]
        nick = DEMO_NICKS[i] if i < len(DEMO_NICKS) else f"同学{i+1}"
        base = TIER_BASE_MASTERY[tier]
        primary, secondary = rng.choice(learning_styles)
        if tier == "high":
            mode, pace, depth = "项目驱动", "快", "原理深挖"
        elif tier == "stable":
            mode, pace, depth = "讲练结合", "适中", "原理理解"
        else:
            mode, pace, depth = "基础补强", "慢", "基础先行"
        weak_pattern = "concept_boundary" if tier == "high" else (
            "knowledge_gap" if tier == "stable" else "misconception"
        )
        weak_topics = {
            "high": ["multi_agent_systems", "ai_project_practice"],
            "stable": ["backpropagation", "transformer"],
            "risk": ["python_basics", "ml_basics", "data_structures"],
        }[tier]
        plan = {
            "user_id": user_id,
            "version": 4,
            "profile_data": {
                "nickname": nick,
                "tier": tier,
                "learning_style": f"{primary} · {pace}",
                "knowledge_base": {
                    "level": tier,
                    "score": round(base, 3),
                    "topics": ["transformer", "attention_mechanism"] if tier == "high" else (
                        ["ml_basics", "supervised_learning"] if tier == "stable"
                        else ["python_basics", "data_structures"]
                    ),
                },
                "cognitive_style": {
                    "primary": primary,
                    "secondary": secondary,
                },
                "learning_preference": {
                    "mode": mode,
                    "pace": pace,
                    "depth": depth,
                },
                "weak_points": {
                    "topics": list(weak_topics),
                    "patterns": [weak_pattern],
                },
                "synthetic_demo": True,
                "seed_source": SEED_SOURCE,
            },
        }
        plans.append(plan)
    return plans


# ================================================================
# 应用层
# ================================================================
def _apply_kp_plans(plans: List[Tuple[str, str, dict, dict]], apply: bool):
    if not apply:
        return 0, 0
    inserted = updated = 0
    with SessionLocal() as db:
        for kp_id, action, _old, plan in plans:
            row = db.get(models.KnowledgePointRecord, kp_id)
            if row is None:
                row = models.KnowledgePointRecord(id=kp_id, course=COURSE, name=KP_META[kp_id]["name"])
                db.add(row)
                inserted += 1
            else:
                updated += 1
            row.description = plan["description"]
            row.metadata_data = plan["metadata_data"]
        db.commit()
    return inserted, updated


def _apply_relation_plans(plans: List[Dict[str, Any]], apply: bool):
    if not apply:
        return 0
    inserted = 0
    with SessionLocal() as db:
        for p in plans:
            row = models.KnowledgeRelationRecord(**p)
            db.add(row)
            inserted += 1
        db.commit()
    return inserted


def _apply_bkt_plans(plans: List[Dict[str, Any]], apply: bool):
    if not apply:
        return 0
    inserted = 0
    with SessionLocal() as db:
        for p in plans:
            row = models.BktStateRecord(**p)
            db.add(row)
            inserted += 1
        db.commit()
    return inserted


def _apply_mistake_plans(plans: List[Dict[str, Any]], apply: bool):
    if not apply:
        return 0
    inserted = 0
    with SessionLocal() as db:
        for p in plans:
            existing = db.get(models.MistakeRecord, p["id"])
            if existing is not None:
                continue
            row = models.MistakeRecord(**p)
            db.add(row)
            inserted += 1
        db.commit()
    return inserted


def _apply_assessment_plans(plans: List[Dict[str, Any]], apply: bool):
    if not apply:
        return 0
    inserted = 0
    with SessionLocal() as db:
        for p in plans:
            existing = db.query(models.AssessmentRecord).filter(
                models.AssessmentRecord.external_id == p["external_id"]
            ).first()
            if existing is not None:
                continue
            row = models.AssessmentRecord(**p)
            db.add(row)
            inserted += 1
        db.commit()
    return inserted


def _apply_profile_plans(plans: List[Dict[str, Any]], apply: bool):
    if not apply:
        return 0, 0
    inserted = updated = 0
    with SessionLocal() as db:
        for p in plans:
            row = db.get(models.ProfileRecord, p["user_id"])
            if row is None:
                row = models.ProfileRecord(user_id=p["user_id"])
                db.add(row)
                inserted += 1
            else:
                # 已存在 → 浅合并：保留旧 user-* 字段，覆写 profile_data
                updated += 1
            row.profile_data = p["profile_data"]
            row.version = max(row.version or 1, p["version"])
        db.commit()
    return inserted, updated


# ================================================================
# 报告与主流程
# ================================================================
def report() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    with SessionLocal() as db:
        out["kp_count"] = db.query(models.KnowledgePointRecord).count()
        # 描述 / Bloom 用 Python 端过滤（SQLite JSON 函数兼容）
        kps = db.query(models.KnowledgePointRecord).all()
        out["kp_with_description"] = sum(1 for k in kps if (k.description or "").strip())
        out["kp_with_bloom"] = sum(
            1 for k in kps
            if (k.metadata_data or {}).get("bloom_level")
        )
        out["kp_with_difficulty"] = sum(
            1 for k in kps
            if (k.metadata_data or {}).get("difficulty")
        )
        out["relation_count"] = db.query(models.KnowledgeRelationRecord).count()
        out["relation_self_loop"] = db.query(models.KnowledgeRelationRecord).filter(
            models.KnowledgeRelationRecord.source_id == models.KnowledgeRelationRecord.target_id
        ).count()
        out["bkt_distinct_kp"] = db.query(models.BktStateRecord.knowledge_point_id).distinct().count()
        out["bkt_demo_kp"] = db.query(models.BktStateRecord.knowledge_point_id).filter(
            models.BktStateRecord.user_id.in_(DEMO_STUDENTS)
        ).distinct().count()
        out["mistake_count"] = db.query(models.MistakeRecord).count()
        out["mistake_unknown"] = db.query(models.MistakeRecord).filter(
            models.MistakeRecord.error_type == "unknown"
        ).count()
        out["mistake_demo"] = db.query(models.MistakeRecord).filter(
            models.MistakeRecord.user_id.in_(DEMO_STUDENTS)
        ).count()
        out["assessment_count"] = db.query(models.AssessmentRecord).count()
        out["assessment_demo"] = db.query(models.AssessmentRecord).filter(
            models.AssessmentRecord.user_id.in_(DEMO_STUDENTS)
        ).count()
        out["profile_count"] = db.query(models.ProfileRecord).count()
        out["profile_demo"] = db.query(models.ProfileRecord).filter(
            models.ProfileRecord.user_id.in_(DEMO_STUDENTS)
        ).count()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="教师端知识图谱数据补全")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not (args.dry_run or args.apply):
        args.dry_run = True

    init_db()
    print("=" * 70)
    print(f"教师端知识图谱数据补全 v1 (mode={'APPLY' if args.apply else 'DRY-RUN'})")
    print("=" * 70)

    # 一. KP 元数据
    kp_plans = collect_kp_plans()
    print(f"\n[I] KP 元数据计划: {len(kp_plans)} 个 KP 需要更新/标记")
    ins, upd = _apply_kp_plans(kp_plans, args.apply)
    print(f"   -> {'insert=' + str(ins) if args.apply else '(dry-run)'} update={upd}")

    # 二. 关系
    rel_plans = collect_relation_plans()
    print(f"\n[II] KP 关系新增: {len(rel_plans)} 条")
    rel_ins = _apply_relation_plans(rel_plans, args.apply)
    print(f"   -> insert={rel_ins if args.apply else '(dry-run)'}")

    # 三. BKT
    bkt_plans = collect_bkt_plans()
    print(f"\n[III] BKT 证据新增: {len(bkt_plans)} 条 (20 学生 × {len(bkt_plans)//20} KP)")
    bkt_ins = _apply_bkt_plans(bkt_plans, args.apply)
    print(f"   -> insert={bkt_ins if args.apply else '(dry-run)'}")

    # 四. 错题 + 评估
    mst_plans = collect_mistake_plans()
    print(f"\n[IV-a] 错题新增: {len(mst_plans)} 条")
    mst_ins = _apply_mistake_plans(mst_plans, args.apply)
    print(f"   -> insert={mst_ins if args.apply else '(dry-run)'}")

    asm_plans = collect_assessment_plans()
    print(f"\n[IV-b] 评估活动新增: {len(asm_plans)} 条")
    asm_ins = _apply_assessment_plans(asm_plans, args.apply)
    print(f"   -> insert={asm_ins if args.apply else '(dry-run)'}")

    # 五. 画像
    prof_plans = collect_profile_plans()
    print(f"\n[V] 画像数据: {len(prof_plans)} 个学生")
    p_ins, p_upd = _apply_profile_plans(prof_plans, args.apply)
    print(f"   -> insert={p_ins} update={p_upd}" if args.apply else "   -> (dry-run)")

    # 报告
    print("\n" + "-" * 70)
    print("统计报告（写入后）")
    print("-" * 70)
    r = report()
    for k, v in r.items():
        print(f"  {k}: {v}")

    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
