"""A3 学习系统 · 种子数据导入脚本（v2 · 大数据量版）

依据《交接清单/21-学情数据与知识库完整性补充方案.md》生成。

执行方式：
    python -c "from backend.app.core.seed_db import seed_all; seed_all()"

设计要点：
- 幂等：每条记录插入前先查重，重复则跳过
- 单表独立 try-except，一张失败不影响其他
- 随机种子固定为 42，可复现
- 时间基准为 time.time()，30 天 = 30 * 86400
"""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.app.core.database import SessionLocal, init_db
from backend.app.core import models


# ================================================================
# 常量
# ================================================================
SEED = 42
COURSE = "artificial_intelligence"
_TEACHER_ID = "teacher"
_TEACHER_NAME = "王老师"
_NOW = time.time()
_DAY = 86400
_TEACHER_RESOURCE_TAGS = ["机器学习", "深度学习", "Python", "基础", "进阶", "实战", "AI", "复习"]


# ================================================================
# 28 个标准知识点（与方案第四章一致，id 全文固定）
# ================================================================
KNOWLEDGE_POINTS: List[Dict[str, Any]] = [
    {"id": "python_basics", "name": "Python 基础编程", "description": "语法、变量、控制流、函数、模块", "bloom": "Apply", "difficulty": 1},
    {"id": "data_structures", "name": "数据结构与算法", "description": "列表、字典、栈、队列、树与图", "bloom": "Apply", "difficulty": 2},
    {"id": "linear_algebra", "name": "线性代数（机器学习）", "description": "矩阵运算、特征值与特征向量、SVD", "bloom": "Understand", "difficulty": 2},
    {"id": "probability_statistics", "name": "概率与统计（机器学习）", "description": "分布、条件概率、贝叶斯推断", "bloom": "Understand", "difficulty": 2},
    {"id": "ml_basics", "name": "机器学习基础（核心）", "description": "学习范式、评估指标、过拟合与正则化", "bloom": "Understand", "difficulty": 2},
    {"id": "supervised_learning", "name": "监督学习方法", "description": "线性回归、逻辑回归、KNN", "bloom": "Apply", "difficulty": 3},
    {"id": "unsupervised_learning", "name": "无监督学习方法", "description": "K-Means、PCA、聚类与降维", "bloom": "Apply", "difficulty": 3},
    {"id": "decision_trees", "name": "决策树与集成（进阶）", "description": "CART、随机森林、GBDT、XGBoost", "bloom": "Apply", "difficulty": 3},
    {"id": "svm", "name": "支持向量机（SVM）", "description": "最大间隔、核函数、SMO", "bloom": "Analyze", "difficulty": 4},
    {"id": "neural_networks", "name": "神经网络基础（深度学习）", "description": "MLP、激活函数、损失函数", "bloom": "Apply", "difficulty": 3},
    {"id": "backpropagation", "name": "反向传播算法", "description": "链式求导、梯度下降、动量法", "bloom": "Analyze", "difficulty": 4},
    {"id": "mlp", "name": "多层感知机（MLP）", "description": "全连接层、正则化、Dropout", "bloom": "Apply", "difficulty": 3},
    {"id": "cnn", "name": "卷积神经网络（视觉）", "description": "卷积、池化、ResNet、感受野", "bloom": "Apply", "difficulty": 3},
    {"id": "rnn", "name": "循环神经网络（序列）", "description": "时序建模、梯度消失、BPTT", "bloom": "Apply", "difficulty": 3},
    {"id": "lstm", "name": "LSTM 与 GRU（门控）", "description": "门控机制、长依赖、双向", "bloom": "Apply", "difficulty": 4},
    {"id": "attention_mechanism", "name": "注意力机制（核心）", "description": "Self-Attention、QKV、多头", "bloom": "Analyze", "difficulty": 4},
    {"id": "transformer", "name": "Transformer 架构", "description": "Encoder/Decoder、位置编码、层归一化", "bloom": "Analyze", "difficulty": 4},
    {"id": "nlp_basics", "name": "NLP 基础任务", "description": "分词、词向量、命名实体识别", "bloom": "Understand", "difficulty": 2},
    {"id": "rag", "name": "检索增强生成（RAG 实战）", "description": "文档切块、嵌入、重排、生成", "bloom": "Evaluate", "difficulty": 4},
    {"id": "reinforcement_learning", "name": "强化学习进阶", "description": "MDP、Q-Learning、策略梯度、PPO", "bloom": "Analyze", "difficulty": 4},
    {"id": "ai_project_practice", "name": "AI 项目实战（端到端）", "description": "数据处理、建模、部署全流程", "bloom": "Create", "difficulty": 5},
    {"id": "multi_agent_systems", "name": "多智能体系统（MAS）", "description": "通信、协作、对抗、Debate", "bloom": "Create", "difficulty": 5},
    {"id": "multimodal_llm", "name": "多模态大模型（VLM）", "description": "视觉-语言、音频、跨模态对齐", "bloom": "Analyze", "difficulty": 4},
    {"id": "ai_agent", "name": "AI Agent（规划与工具）", "description": "规划、工具调用、反思、ReAct", "bloom": "Create", "difficulty": 4},
    {"id": "mcp_protocol", "name": "MCP 协议（上下文）", "description": "Model Context Protocol 消息与工具", "bloom": "Understand", "difficulty": 3},
    {"id": "learning_science", "name": "学习科学理论", "description": "认知负荷、间隔重复、刻意练习", "bloom": "Understand", "difficulty": 2},
    {"id": "cognitive_diagnosis", "name": "认知诊断模型", "description": "BKT、DINA、IRT、错因分析", "bloom": "Analyze", "difficulty": 4},
    {"id": "data_visualization", "name": "数据可视化（分析）", "description": "图表选择、感知原则、可解释性", "bloom": "Apply", "difficulty": 2},
    {"id": "learning_analytics_ethics", "name": "学习分析伦理（治理）", "description": "隐私、公平、知情同意", "bloom": "Evaluate", "difficulty": 2},
]


# ================================================================
# 30 条 KP 关系（与方案第六章 seed_extended.json 同步）
# ================================================================
KNOWLEDGE_RELATIONS: List[Dict[str, Any]] = [
    {"source": "python_basics", "target": "data_structures", "type": "prerequisite", "weight": 0.9},
    {"source": "python_basics", "target": "ml_basics", "type": "prerequisite", "weight": 0.8},
    {"source": "linear_algebra", "target": "ml_basics", "type": "prerequisite", "weight": 0.85},
    {"source": "probability_statistics", "target": "ml_basics", "type": "prerequisite", "weight": 0.85},
    {"source": "ml_basics", "target": "supervised_learning", "type": "prerequisite", "weight": 0.9},
    {"source": "ml_basics", "target": "unsupervised_learning", "type": "prerequisite", "weight": 0.85},
    {"source": "supervised_learning", "target": "decision_trees", "type": "specialization", "weight": 0.8},
    {"source": "supervised_learning", "target": "svm", "type": "specialization", "weight": 0.75},
    {"source": "ml_basics", "target": "neural_networks", "type": "prerequisite", "weight": 0.8},
    {"source": "linear_algebra", "target": "neural_networks", "type": "prerequisite", "weight": 0.8},
    {"source": "neural_networks", "target": "backpropagation", "type": "related", "weight": 0.9},
    {"source": "neural_networks", "target": "mlp", "type": "specialization", "weight": 0.85},
    {"source": "neural_networks", "target": "cnn", "type": "specialization", "weight": 0.85},
    {"source": "neural_networks", "target": "rnn", "type": "specialization", "weight": 0.85},
    {"source": "rnn", "target": "lstm", "type": "specialization", "weight": 0.9},
    {"source": "rnn", "target": "attention_mechanism", "type": "extends", "weight": 0.7},
    {"source": "lstm", "target": "attention_mechanism", "type": "related", "weight": 0.75},
    {"source": "attention_mechanism", "target": "transformer", "type": "foundation", "weight": 0.95},
    {"source": "transformer", "target": "nlp_basics", "type": "enables", "weight": 0.7},
    {"source": "nlp_basics", "target": "rag", "type": "prerequisite", "weight": 0.8},
    {"source": "transformer", "target": "rag", "type": "foundation", "weight": 0.85},
    {"source": "transformer", "target": "multimodal_llm", "type": "foundation", "weight": 0.8},
    {"source": "neural_networks", "target": "reinforcement_learning", "type": "related", "weight": 0.6},
    {"source": "supervised_learning", "target": "reinforcement_learning", "type": "contrast", "weight": 0.5},
    {"source": "probability_statistics", "target": "reinforcement_learning", "type": "prerequisite", "weight": 0.7},
    {"source": "cnn", "target": "ai_project_practice", "type": "used_in", "weight": 0.8},
    {"source": "rag", "target": "ai_project_practice", "type": "used_in", "weight": 0.85},
    {"source": "transformer", "target": "ai_project_practice", "type": "used_in", "weight": 0.8},
    {"source": "ai_agent", "target": "multi_agent_systems", "type": "enables", "weight": 0.85},
    {"source": "ai_agent", "target": "mcp_protocol", "type": "used_in", "weight": 0.7},
    {"source": "rag", "target": "mcp_protocol", "type": "related", "weight": 0.5},
    {"source": "ml_basics", "target": "data_visualization", "type": "used_in", "weight": 0.7},
    {"source": "ml_basics", "target": "cognitive_diagnosis", "type": "foundation", "weight": 0.75},
    {"source": "learning_science", "target": "cognitive_diagnosis", "type": "related", "weight": 0.8},
    {"source": "cognitive_diagnosis", "target": "learning_analytics_ethics", "type": "related", "weight": 0.6},
]


# ================================================================
# 20 个学生人设（与方案第三章一致）
# ================================================================
# 每个学生：mastery_bias / 风格标签 / 强势 KP 列表 / 薄弱 KP 列表
STUDENTS: List[Dict[str, Any]] = [
    # 学霸层 4 人 (0.78-0.95)
    {"user_id": "demo-student-1", "nickname": "杜同学", "tier": "excellent", "mastery_bias": 0.78,
     "style": "视觉型·自驱", "focus_kps": ["transformer", "attention_mechanism", "cnn", "rag"], "weak_kps": ["probability_statistics", "reinforcement_learning"]},
    {"user_id": "demo-student-2", "nickname": "小李", "tier": "excellent", "mastery_bias": 0.88,
     "style": "读写型·自驱", "focus_kps": ["ml_basics", "supervised_learning", "decision_trees", "data_visualization"], "weak_kps": ["multimodal_llm", "mcp_protocol"]},
    {"user_id": "demo-student-3", "nickname": "小赵", "tier": "excellent", "mastery_bias": 0.85,
     "style": "动手型·自驱", "focus_kps": ["ai_project_practice", "ai_agent", "multi_agent_systems", "neural_networks"], "weak_kps": ["learning_science", "learning_analytics_ethics"]},
    {"user_id": "demo-student-7", "nickname": "小陈", "tier": "excellent", "mastery_bias": 0.82,
     "style": "视觉型·自驱", "focus_kps": ["linear_algebra", "python_basics", "mlp", "backpropagation"], "weak_kps": ["rag", "ai_agent", "multi_agent_systems"]},

    # 良好层 6 人 (0.60-0.80)
    {"user_id": "demo-student-4", "nickname": "小慧", "tier": "good", "mastery_bias": 0.65,
     "style": "读写型·协作", "focus_kps": ["nlp_basics", "rag", "data_structures"], "weak_kps": ["probability_statistics", "linear_algebra"]},
    {"user_id": "demo-student-8", "nickname": "小王", "tier": "good", "mastery_bias": 0.72,
     "style": "听觉型·自驱", "focus_kps": ["ml_basics", "supervised_learning", "data_visualization"], "weak_kps": ["reinforcement_learning", "rnn", "lstm"]},
    {"user_id": "demo-student-9", "nickname": "小刘", "tier": "good", "mastery_bias": 0.68,
     "style": "动手型·协作", "focus_kps": ["cnn", "mlp", "ai_project_practice"], "weak_kps": ["rnn", "lstm", "mcp_protocol"]},
    {"user_id": "demo-student-10", "nickname": "小周", "tier": "good", "mastery_bias": 0.70,
     "style": "视觉型·自驱", "focus_kps": ["python_basics", "data_structures", "ai_agent"], "weak_kps": ["linear_algebra", "probability_statistics"]},
    {"user_id": "demo-student-11", "nickname": "小吴", "tier": "good", "mastery_bias": 0.63,
     "style": "读写型·协作", "focus_kps": ["decision_trees", "unsupervised_learning"], "weak_kps": ["svm", "neural_networks", "backpropagation"]},
    {"user_id": "demo-student-12", "nickname": "小郑", "tier": "good", "mastery_bias": 0.75,
     "style": "动手型·自驱", "focus_kps": ["rag", "ai_agent", "ai_project_practice"], "weak_kps": ["multimodal_llm", "mcp_protocol"]},

    # 中等层 6 人 (0.40-0.60)
    {"user_id": "demo-student-5", "nickname": "小强", "tier": "medium", "mastery_bias": 0.50,
     "style": "动手型·实践", "focus_kps": ["python_basics", "ai_project_practice"], "weak_kps": ["linear_algebra", "probability_statistics", "ml_basics"]},
    {"user_id": "demo-student-13", "nickname": "小孙", "tier": "medium", "mastery_bias": 0.45,
     "style": "视觉型·协作", "focus_kps": ["cnn", "data_visualization"], "weak_kps": ["transformer", "attention_mechanism", "backpropagation", "rag"]},
    {"user_id": "demo-student-14", "nickname": "小朱", "tier": "medium", "mastery_bias": 0.55,
     "style": "读写型·实践", "focus_kps": ["python_basics", "data_structures"], "weak_kps": ["transformer", "attention_mechanism", "svm"]},
    {"user_id": "demo-student-15", "nickname": "小胡", "tier": "medium", "mastery_bias": 0.48,
     "style": "听觉型·协作", "focus_kps": ["nlp_basics"], "weak_kps": ["probability_statistics", "linear_algebra", "ml_basics"]},
    {"user_id": "demo-student-16", "nickname": "小郭", "tier": "medium", "mastery_bias": 0.52,
     "style": "动手型·实践", "focus_kps": ["cnn", "python_basics"], "weak_kps": ["backpropagation", "mlp", "decision_trees"]},
    {"user_id": "demo-student-17", "nickname": "小林", "tier": "medium", "mastery_bias": 0.58,
     "style": "视觉型·自驱", "focus_kps": ["rag", "data_visualization"], "weak_kps": ["multi_agent_systems", "ai_agent", "mcp_protocol"]},

    # 待提升层 4 人 (0.15-0.40)
    {"user_id": "demo-student-6", "nickname": "小杨", "tier": "weak", "mastery_bias": 0.25,
     "style": "视觉型·实践", "focus_kps": ["python_basics"], "weak_kps": ["ml_basics", "linear_algebra", "probability_statistics", "neural_networks", "cnn"]},
    {"user_id": "demo-student-18", "nickname": "小何", "tier": "weak", "mastery_bias": 0.30,
     "style": "听觉型·协作", "focus_kps": [], "weak_kps": ["python_basics", "linear_algebra", "ml_basics", "supervised_learning", "data_structures"]},
    {"user_id": "demo-student-19", "nickname": "小罗", "tier": "weak", "mastery_bias": 0.35,
     "style": "读写型·实践", "focus_kps": ["python_basics", "ai_project_practice"], "weak_kps": ["linear_algebra", "ml_basics", "transformer", "rag"]},
    {"user_id": "demo-student-20", "nickname": "小高", "tier": "weak", "mastery_bias": 0.20,
     "style": "动手型·协作", "focus_kps": [], "weak_kps": ["python_basics", "data_structures", "linear_algebra", "probability_statistics", "ml_basics", "neural_networks"]},
]


# 错题错误类型（8 类，按方案）
ERROR_TYPES = ["概念混淆", "概念边界混淆", "知识缺漏", "审题不清", "计算失误", "计算粗心", "方法选择错", "阅读理解"]


# ================================================================
# 错题题库（按 KP 分类的题面/答案/错误范例模板）
# ================================================================
# 每个 KP 提供若干题面与正确答案模板，错题时随机挑题目 + 拼装学生错误答案
MISTAKE_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "python_basics": [
        {"q": "Python 中 def f(x, items=[]): items.append(x) 多次调用为什么会累加？",
         "sa": "因为列表会被复制，每次都同一份。", "ca": "默认参数在函数定义时只求值一次，多个调用共享同一个列表。应改为 def f(x, items=None): items = items or []"},
        {"q": "Python 装饰器 @property 的作用是什么？",
         "sa": "就是给类加属性。", "ca": "@property 把方法转为只读属性，调用 obj.attr 时实际执行方法，可封装 getter / setter / deleter"},
        {"q": "Python 中 yield 与 return 的核心区别？",
         "sa": "yield 就是 return 的别名。", "ca": "yield 返回值后暂停函数并保留执行状态，下次 next() 从 yield 继续；return 直接终止函数。生成器依赖 yield 实现惰性计算"},
        {"q": "Python 列表与元组的本质区别？",
         "sa": "元组比列表快。", "ca": "列表是可变序列 (可变对象)，元组是不可变序列。不可变性使元组可哈希、可作为 dict 键"},
        {"q": "Python 中 *args 与 **kwargs 的用法区别？",
         "sa": "都是位置参数。", "ca": "*args 接收额外位置参数为元组，**kwargs 接收关键字参数为字典，函数定义时组合使用可实现通用接口"},
    ],
    "data_structures": [
        {"q": "哈希表 (dict) 的平均查找复杂度是多少？",
         "sa": "O(n)。", "ca": "平均 O(1)，最坏 O(n)（哈希冲突严重时）。Python dict 通过开放寻址 + 随机探测保持接近 O(1)"},
        {"q": "栈和队列的核心区别？",
         "sa": "栈快队列慢。", "ca": "栈是 LIFO (后进先出)，队列是 FIFO (先进先出)。栈用 list.append/pop，队列用 collections.deque"},
        {"q": "二叉搜索树的中序遍历结果有什么性质？",
         "sa": "随机排列。", "ca": "得到有序序列（左 < 根 < 右），BST 配合中序遍历可用于排序与有序查找"},
    ],
    "linear_algebra": [
        {"q": "矩阵 A 的特征值 λ 和特征向量 v 满足什么关系？",
         "sa": "λ 是行列式。", "ca": "Av = λv，等价于 (A - λI)v = 0 且 det(A - λI) = 0；特征向量刻画矩阵沿某方向上的伸缩"},
        {"q": "SVD 分解 A = UΣVᵀ 中 U 与 V 的含义？",
         "sa": "U 是特征值，V 是特征向量。", "ca": "U 是 AAᵀ 的特征向量 (左奇异向量)，V 是 AᵀA 的特征向量 (右奇异向量)，Σ 是对角奇异值矩阵"},
        {"q": "矩阵乘法 AB 中 A 是 3×4, B 是 4×5，结果维度？",
         "sa": "4×4。", "ca": "结果 3×5；矩阵乘法要求 A 的列数 = B 的行数，输出行数=A 行数，列数=B 列数"},
        {"q": "正定矩阵的判定方法？",
         "sa": "对角线元素都大于 0。", "ca": "所有特征值 > 0；或所有顺序主子式 > 0；xᵀAx > 0 对所有非零 x 成立"},
    ],
    "probability_statistics": [
        {"q": "贝叶斯公式 P(A|B) = ?",
         "sa": "P(A) + P(B)。", "ca": "P(A|B) = P(B|A)·P(A) / P(B)。描述在已知 B 发生后 A 的后验概率"},
        {"q": "独立事件的定义？",
         "sa": "两个事件互不影响。", "ca": "P(A∩B) = P(A)·P(B)；独立不蕴含互斥，互斥也不蕴含独立（除非其中一个概率为 0）"},
        {"q": "正态分布的 3σ 原则含义？",
         "sa": "三倍标准差以内一定有数据。", "ca": "约 99.73% 数据落在 μ±3σ 内，常用于异常值检测：超出 3σ 视为离群点"},
    ],
    "ml_basics": [
        {"q": "什么是过拟合？如何判断？",
         "sa": "模型太大了。", "ca": "训练集表现好但验证/测试集差。判断：训练损失持续下降而验证损失先降后升；可借助学习曲线观察"},
        {"q": "K 折交叉验证 K=5 含义？",
         "sa": "把数据分 5 份，挑 1 份训练。", "ca": "数据分 5 份，每次取 4 份训练 + 1 份验证，循环 5 次取平均。降低对单一划分的依赖"},
        {"q": "L1 与 L2 正则化的选择场景？",
         "sa": "都是惩罚权重。", "ca": "L1 产生稀疏权重（特征选择）；L2 权重平滑（防过拟合、抗共线）。特征多且需可解释选 L1，否则选 L2"},
        {"q": "偏差-方差权衡核心？",
         "sa": "偏差和方差都小才好。", "ca": "模型复杂度↑偏差↓方差↑；复杂度↓偏差↑方差↓。需在二者间找平衡点使总误差最小"},
    ],
    "supervised_learning": [
        {"q": "线性回归的损失函数？",
         "sa": "准确率。", "ca": "均方误差 MSE = (1/n)·Σ(y - ŷ)²。最小二乘闭式解 θ = (XᵀX)⁻¹Xᵀy"},
        {"q": "逻辑回归为什么用 sigmoid？",
         "sa": "让结果在 0-1 之间。", "ca": "将线性输出映射为 (0,1) 概率；与对数损失组合得到凸优化问题，可用梯度下降稳定求解"},
        {"q": "KNN 的 K 值过大有何影响？",
         "sa": "更准。", "ca": "K 过大导致欠拟合（决策边界过于平滑，远处样本主导）；K 过小导致过拟合与噪声敏感。常用交叉验证选 K"},
    ],
    "unsupervised_learning": [
        {"q": "K-Means 的目标函数？",
         "sa": "让簇内距离最大。", "ca": "最小化簇内平方和 SSE = Σ Σ ||x - μₖ||²；对初始化敏感，易陷入局部最优，常用 K-Means++ 改善"},
        {"q": "PCA 的核心思想？",
         "sa": "找最重要的特征。", "ca": "将数据投影到方差最大的正交方向（主成分），保留前 k 个主成分实现降维。无监督、线性"},
        {"q": "聚类评估指标 silhouette score 含义？",
         "sa": "聚类数量的指标。", "ca": "s = (b - a) / max(a, b)，a=同簇平均距离，b=最近异簇平均距离。范围 [-1, 1]，越大聚类越合理"},
    ],
    "decision_trees": [
        {"q": "信息增益的计算公式？",
         "sa": "最大值。", "ca": "IG(D, A) = H(D) - H(D|A)，其中 H(D) 是数据集熵，H(D|A) 是按特征 A 划分后的条件熵"},
        {"q": "随机森林为什么能降低方差？",
         "sa": "树更多。", "ca": "Bagging 采样 + 特征子集扰动 → 多棵决策树独立训练，对结果取平均；降低单棵树过拟合带来的方差"},
        {"q": "XGBoost 与 GBDT 的关键差异？",
         "sa": "XGBoost 更快。", "ca": "XGBoost 加了二阶导数信息、正则化项（叶子权重 L2）、列采样与缺失值自动处理，工程上支持并行"},
    ],
    "svm": [
        {"q": "SVM 的最大间隔准则？",
         "sa": "间隔越大越好。", "ca": "求解 max 2/||w||，等价于 min (1/2)||w||² s.t. yᵢ(w·xᵢ+b) ≥ 1；使超平面到最近样本距离最大"},
        {"q": "核函数的作用？",
         "sa": "让 SVM 更快。", "ca": "将低维不可分数据映射到高维特征空间使其线性可分；常见核：RBF、多项式、Sigmoid"},
        {"q": "SVM 对偶问题的求解方法？",
         "sa": "梯度下降。", "ca": "SMO (Sequential Minimal Optimization) 序列选择两个 α 变量解析求解，循环至 KKT 条件满足"},
    ],
    "neural_networks": [
        {"q": "ReLU 在 x<0 时的输出与问题？",
         "sa": "输出 0，没问题。", "ca": "输出 0，可能导致神经元永久死亡 (Dead ReLU)，梯度永远为 0 不可更新。LeakyReLU / PReLU 可缓解"},
        {"q": "Dropout 在训练/测试时的行为差异？",
         "sa": "一样。", "ca": "训练时按概率 p 随机丢弃神经元并缩放剩余权重；测试时使用全部神经元不丢弃，等价于集成多子网络"},
        {"q": "MLP 的万能逼近定理？",
         "sa": "MLP 可拟合任意分布。", "ca": "单隐层 + 足够多神经元 + 非线性激活可逼近任意紧集上的连续函数；但定理不保证可学习性与泛化"},
    ],
    "backpropagation": [
        {"q": "反向传播的核心原理？",
         "sa": "从后往前推。", "ca": "链式求导：从输出向输入逐层计算损失对各参数的梯度，配合梯度下降更新权重；本质是动态规划的高效梯度计算"},
        {"q": "梯度消失的原因？",
         "sa": "学习率太小。", "ca": "深层网络中 sigmoid/tanh 导数 < 1，连乘导致浅层梯度趋近于 0；改用 ReLU、残差连接、BatchNorm 缓解"},
        {"q": "BGD 与 SGD 的差异？",
         "sa": "BGD 用全部，SGD 用一个。", "ca": "BGD 每轮用全量数据算梯度（稳定但慢）；SGD 每样本更新（快但震荡），Mini-batch 折中"},
    ],
    "mlp": [
        {"q": "为什么 MLP 需要非线性激活？",
         "sa": "让模型更准。", "ca": "若全是线性层，无论多少层都等价于单层线性变换；非线性激活让网络能拟合复杂函数"},
        {"q": "MLP 的权重初始化为什么重要？",
         "sa": "让训练更快。", "ca": "Xavier/He 初始化保持各层激活方差稳定，避免梯度消失/爆炸；不当初始化会导致训练停滞"},
        {"q": "MLP 中 BatchNorm 的作用？",
         "sa": "让数据标准化。", "ca": "对每层输入做 mini-batch 维度的归一化，使激活分布稳定，允许更大学习率并缓解梯度问题"},
    ],
    "cnn": [
        {"q": "CNN 池化层的主要作用？",
         "sa": "学滤波器。", "ca": "下采样降低空间尺寸、减少参数、增强平移不变性；最大池化保留显著特征，平均池化保留整体信息"},
        {"q": "两层 3×3 卷积 vs 一层 5×5 卷积的等效性？",
         "sa": "结果不同。", "ca": "感受野相同 (5×5)，但两层 3×3 多了 1 次非线性 + 参数量更少 (18 vs 25)，是 VGG 的设计精髓"},
        {"q": "残差连接为什么有效？",
         "sa": "让网络更深。", "ca": "y = F(x) + x 让梯度可直接跨层传播，缓解深度网络退化问题（不是消失），让训练几百层成为可能"},
    ],
    "rnn": [
        {"q": "RNN 梯度消失的主要原因？",
         "sa": "数据太长。", "ca": "时间步反向传播时 Jacobian 矩阵连乘，激活导数 < 1 导致梯度指数衰减；LSTM/GRU 通过门控缓解"},
        {"q": "RNN 与前馈网络的核心区别？",
         "sa": "RNN 有循环。", "ca": "RNN 在时间步之间共享权重并保留隐藏状态，可处理变长序列；前馈网络假设输入独立"},
        {"q": "双向 RNN 的优势？",
         "sa": "更快。", "ca": "同时利用过去与未来上下文信息（如 NER、翻译），在需要全局语义的场景显著提升；但要求整序列可获取，不适合流式任务"},
    ],
    "lstm": [
        {"q": "LSTM 三个门的作用？",
         "sa": "三个一样的门。", "ca": "遗忘门决定丢弃旧细胞信息；输入门控制新信息写入；输出门控制细胞状态对隐藏层输出。共同缓解长依赖梯度消失"},
        {"q": "GRU 与 LSTM 的主要差异？",
         "sa": "名字不同。", "ca": "GRU 把遗忘门与输入门合并为更新门，把细胞状态与隐藏状态合并，参数更少、训练更快；LSTM 表达力更强"},
    ],
    "attention_mechanism": [
        {"q": "Self-Attention 的 QKV 含义？",
         "sa": "三个权重矩阵。", "ca": "Q (Query) 当前 token 的查询，K (Key) 序列中所有 token 的索引，V (Value) 携带的内容；注意力 = softmax(QKᵀ/√d)V"},
        {"q": "为什么要除以 √dₖ？",
         "sa": "让结果小一点。", "ca": "防止 dₖ 大时 QKᵀ 内积方差大导致 softmax 梯度极小，√dₖ 缩放使方差稳定为 1"},
        {"q": "多头注意力的优势？",
         "sa": "参数更多。", "ca": "多个子空间并行学习不同语义的依赖关系；每头维度 dₖ = d_model / h，拼接后线性投影。总计算量与单头接近"},
    ],
    "transformer": [
        {"q": "Transformer 位置编码的作用？",
         "sa": "让模型认识顺序。", "ca": "Self-Attention 本身置换不变，位置编码 (sin/cos 或可学习) 注入 token 位置信息，使模型区分不同序列"},
        {"q": "LayerNorm vs BatchNorm？",
         "sa": "LN 是 batch，BN 是 layer。", "ca": "LN 对单个样本的所有特征做归一化（不受 batch 影响，适合 NLP 变长序列）；BN 对 batch 维度归一化（CV 常用）"},
        {"q": "Encoder 与 Decoder 的结构差异？",
         "sa": "一样。", "ca": "Encoder 用双向 Self-Attention；Decoder 用掩码 Self-Attention（看不到未来）+ Cross-Attention（attend to Encoder 输出）"},
    ],
    "nlp_basics": [
        {"q": "TF-IDF 的核心思想？",
         "sa": "出现次数多就重要。", "ca": "TF (词频) × IDF (逆文档频率) 平衡高频词与稀有词；IDF = log(N/df) 抑制停用词、突出区分性词汇"},
        {"q": "Word2Vec 的两种训练模式？",
         "sa": "训练数据。", "ca": "CBOW 用上下文预测中心词；Skip-gram 用中心词预测上下文。Skip-gram 在低频词上表现更好"},
        {"q": "中文分词的主要难点？",
         "sa": "没有空格。", "ca": "歧义切分（组合/切分歧义）、未登录词（命名实体、新词）。常用 Jieba、THULAC、BERT 分词器解决"},
    ],
    "rag": [
        {"q": "RAG 为什么需要重排 (Rerank)？",
         "sa": "为了快。", "ca": "向量召回 Top-K 可能有噪声，Rerank 模型 (Cross-Encoder) 精排显著提升上下文质量，从而改善 LLM 生成准确度"},
        {"q": "RAG 文本切块大小如何影响检索效果？",
         "sa": "块小好。", "ca": "块过大切块内信息冗余稀释语义，块过小丢失上下文。一般 200-500 token，可结合句子/段落边界动态切分"},
        {"q": "为什么 RAG 用向量数据库而不是关键词搜索？",
         "sa": "更快。", "ca": "向量检索支持语义相似度，召回率高；关键词 (BM25) 字面匹配，准确但召回低。生产常混合 (Hybrid Search + RRF)"},
    ],
    "reinforcement_learning": [
        {"q": "Q-Learning 更新公式？",
         "sa": "Q = Q + α。", "ca": "Q(s,a) ← Q(s,a) + α[r + γ·max Q(s',a') - Q(s,a)]。TD 目标用下一状态最大 Q，off-policy"},
        {"q": "MDP 五元组？",
         "sa": "两个。", "ca": "<S, A, P, R, γ>：状态集、动作集、转移概率 P(s'|s,a)、奖励函数 R(s,a)、折扣因子 γ"},
        {"q": "Policy Gradient 与 Value-Based 区别？",
         "sa": "参数不同。", "ca": "Policy Gradient (REINFORCE/PPO) 直接参数化 π(a|s) 并对策略梯度上升；Value-Based (DQN) 学习 Q 函数再隐式取 argmax"},
    ],
    "ai_project_practice": [
        {"q": "AI 项目数据切分常用比例？",
         "sa": "5:5。", "ca": "训练/验证/测试 = 6:2:2 或 7:1:2。小数据集用 K 折交叉验证；测试集只用一次评估最终模型"},
        {"q": "模型部署常见方式？",
         "sa": "复制粘贴。", "ca": "REST API (FastAPI/Flask) + Docker；或 ONNX/TorchServe 在线推理；批处理用 Airflow 调度"},
    ],
    "multi_agent_systems": [
        {"q": "Multi-Agent Debate 的核心思想？",
         "sa": "多个 Agent 重复说。", "ca": "多个 LLM Agent 提出不同观点并互相批判，通过多轮辩论收敛更鲁棒的答案；降低单 Agent 的幻觉与偏置"},
        {"q": "Agent 间通信协议常用形式？",
         "sa": "函数调用。", "ca": "消息队列 (Pub/Sub)、共享黑板 (Blackboard)、结构化 JSON RPC、FIPA-ACL 等；MCP 是 LLM 工具调用统一协议"},
    ],
    "multimodal_llm": [
        {"q": "CLIP 的核心思想？",
         "sa": "两个网络。", "ca": "把图像和文本映射到同一向量空间，对比学习让匹配的图文对距离近；可零样本分类与跨模态检索"},
        {"q": "多模态融合的常见策略？",
         "sa": "拼接。", "ca": "早期融合 (输入层 concat)、晚期融合 (决策层融合)、交叉注意力 (Cross-Attention)、Q-Former 等"},
    ],
    "ai_agent": [
        {"q": "ReAct 模式的核心？",
         "sa": "循环执行。", "ca": "Reason + Act 交替：模型先推理下一步动作并调用工具，拿到观察后再推理；适合需要工具的复杂任务"},
        {"q": "Agent 规划 (Planning) 的常见方法？",
         "sa": "提示工程。", "ca": "任务分解 (CoT/ToT)、子目标生成、ReWOO、Reflexion 自反思；本质是把长任务拆为可验证的子步骤"},
    ],
    "mcp_protocol": [
        {"q": "MCP 协议的设计目标？",
         "sa": "替代 HTTP。", "ca": "为 LLM 工具调用定义统一协议，模型/客户端/服务器解耦，类比 LSP (Language Server Protocol) 在 IDE 中的角色"},
        {"q": "MCP 消息的典型字段？",
         "sa": "URL。", "ca": "JSON-RPC 风格：method (tools/list, tools/call)、params、id、result/error。传输支持 stdio 与 HTTP+SSE"},
    ],
    "learning_science": [
        {"q": "间隔重复的核心原则？",
         "sa": "反复做。", "ca": "按遗忘曲线动态排复习间隔 (1d/3d/7d/14d/...)，稳定记忆；SM-2/Anki 是经典实现"},
        {"q": "认知负荷的三种类型？",
         "sa": "两种。", "ca": "内在 (任务本身复杂度)、外在 (呈现方式造成)、关联 (学习投入)。教学设计应降低外在、增加关联"},
    ],
    "cognitive_diagnosis": [
        {"q": "BKT 与 DINA 的核心差异？",
         "sa": "都是诊断。", "ca": "BKT 是 HMM 跟踪每个 KP 掌握概率；DINA 是确定性属性，假设学生掌握 KP 集后能否答对由 slip/guess 决定"},
        {"q": "IRT 的核心参数？",
         "sa": "两个。", "ca": "难度 b、区分度 a、猜测 c (3PL)；刻画学生能力与题目特性的关系，用于自适应测试与能力评估"},
    ],
    "data_visualization": [
        {"q": "选择图表的核心原则？",
         "sa": "好看。", "ca": "匹配数据类型：分类用条形/饼图、连续分布用直方图/箱线、关系用散点/折线、组成用堆叠；先想清楚要传达什么信息"},
        {"q": "可视化误用的常见问题？",
         "sa": "颜色多。", "ca": "纵轴截断夸大差异、双 Y 轴误导、3D 饼图难读、彩虹色图无序；遵循 Cleveland-McGill 感知效率排序"},
    ],
    "learning_analytics_ethics": [
        {"q": "学习分析数据的核心伦理原则？",
         "sa": "不公开。", "ca": "知情同意、最小化收集、目的限定、数据安全、可解释性、公平性。学生画像/错题属于敏感个人信息需脱敏"},
        {"q": "算法偏见在教育场景的表现？",
         "sa": "没有。", "ca": "训练数据偏差导致弱势学生被错误标记为低潜力；需要定期审计、跨群体公平指标监控、可申诉机制"},
    ],
}


# ================================================================
# 工具函数
# ================================================================
def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _score_for_tier(tier: str) -> Tuple[float, float]:
    """返回 (low, high) 分数区间"""
    return {
        "excellent": (0.75, 0.98),
        "good": (0.55, 0.85),
        "medium": (0.35, 0.70),
        "weak": (0.15, 0.55),
    }[tier]


def _xp_for_tier(tier: str) -> Tuple[int, int]:
    return {
        "excellent": (3000, 5000),
        "good": (1500, 3000),
        "medium": (800, 1500),
        "weak": (300, 800),
    }[tier]


def _streak_for_tier(tier: str) -> Tuple[int, int]:
    return {
        "excellent": (8, 20),
        "good": (3, 12),
        "medium": (1, 7),
        "weak": (0, 3),
    }[tier]


def _progress_for_tier(tier: str) -> Tuple[float, float]:
    return {
        "excellent": (60.0, 90.0),
        "good": (30.0, 60.0),
        "medium": (10.0, 40.0),
        "weak": (0.0, 20.0),
    }[tier]


def _mistake_count_for_tier(tier: str) -> Tuple[int, int]:
    """每学生错题条数"""
    return {
        "excellent": (15, 20),
        "good": (20, 25),
        "medium": (25, 30),
        "weak": (30, 35),
    }[tier]


def _assessment_count_for_tier(tier: str) -> int:
    """每学生评估记录数"""
    return {
        "excellent": 70,
        "good": 65,
        "medium": 60,
        "weak": 50,
    }[tier]


def _pick_kp_for_student(student: Dict[str, Any]) -> str:
    """根据学生强势/薄弱 KP 偏好选 KP"""
    if random.random() < 0.7 and student["focus_kps"]:
        return random.choice(student["focus_kps"])
    if random.random() < 0.6 and student["weak_kps"]:
        return random.choice(student["weak_kps"])
    return random.choice([kp["id"] for kp in KNOWLEDGE_POINTS])


# ================================================================
# Seed 函数
# ================================================================
def seed_knowledge_points() -> int:
    inserted = 0
    with SessionLocal() as db:
        for kp in KNOWLEDGE_POINTS:
            try:
                row = db.get(models.KnowledgePointRecord, kp["id"])
                if row is None:
                    # 名称冲突时，附加 id 后缀以保证 (course, name) 唯一
                    existing_names = {
                        n for (n,) in db.query(models.KnowledgePointRecord.name)
                        .filter(models.KnowledgePointRecord.course == COURSE)
                        .all()
                    }
                    final_name = kp["name"]
                    if final_name in existing_names:
                        final_name = f"{kp['name']} · v2"
                    db.add(models.KnowledgePointRecord(
                        id=kp["id"],
                        course=COURSE,
                        name=final_name,
                        description=kp["description"],
                        metadata_data={"bloom": kp["bloom"], "difficulty": kp["difficulty"]},
                    ))
                    inserted += 1
                else:
                    # 同步元数据（幂等）
                    row.name = kp["name"]
                    row.description = kp["description"]
                    row.course = COURSE
                    row.metadata_data = {"bloom": kp["bloom"], "difficulty": kp["difficulty"]}
                db.commit()
            except Exception:
                db.rollback()
                continue
    return inserted


def seed_knowledge_relations() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing = {
            (r.source_id, r.target_id, r.relation_type)
            for r in db.query(models.KnowledgeRelationRecord).all()
        }
        for rel in KNOWLEDGE_RELATIONS:
            key = (rel["source"], rel["target"], rel["type"])
            if key in existing:
                continue
            # 检查源/目标 KP 是否存在；若不存在则跳过（按外键约束保护）
            src = db.get(models.KnowledgePointRecord, rel["source"])
            tgt = db.get(models.KnowledgePointRecord, rel["target"])
            if not src or not tgt:
                continue
            db.add(models.KnowledgeRelationRecord(
                source_id=rel["source"],
                target_id=rel["target"],
                relation_type=rel["type"],
                weight=rel["weight"],
                metadata_data={},
            ))
            inserted += 1
        db.commit()
    return inserted


def seed_profiles() -> int:
    inserted = 0
    with SessionLocal() as db:
        for s in STUDENTS:
            tier = s["tier"]
            score_low, score_high = _score_for_tier(tier)
            # 拼画像
            profile_data = {
                "user_id": s["user_id"],
                "nickname": s["nickname"],
                "tier": tier,
                "learning_style": s["style"],
                "knowledge_base": {
                    "level": {"excellent": "高级", "good": "中高", "medium": "中级", "weak": "初级"}[tier],
                    "score": round(s["mastery_bias"], 2),
                    "topics": [k for k in s["focus_kps"][:3]],
                },
                "cognitive_style": {
                    "primary": s["style"].split("·")[0],
                    "secondary": s["style"].split("·")[1] if "·" in s["style"] else "",
                },
                "learning_preference": {
                    "mode": {"excellent": "项目驱动", "good": "混合学习", "medium": "主题学习", "weak": "基础补强"}[tier],
                    "pace": {"excellent": "较快", "good": "中等", "medium": "中等", "weak": "较慢"}[tier],
                    "depth": {"excellent": "原理深挖", "good": "原理+实战", "medium": "实战为主", "weak": "入门引导"}[tier],
                },
                "weak_points": {
                    "topics": s["weak_kps"],
                    "patterns": [random.choice(ERROR_TYPES) for _ in range(2)],
                },
                "learning_goal": {
                    "target": {"excellent": "AI 算法工程师", "good": "AI 应用开发", "medium": "AI 入门就业", "weak": "建立基础"}[tier],
                    "timeline": {"excellent": "6个月", "good": "9个月", "medium": "12个月", "weak": "18个月"}[tier],
                },
                "time_management": {
                    "weekly_hours": {"excellent": 30, "good": 22, "medium": 15, "weak": 8}[tier],
                    "best_time": random.choice(["晚上", "上午", "下午", "深夜"]),
                    "consistency": {"excellent": "高", "good": "中", "medium": "中", "weak": "低"}[tier],
                },
                "self_efficacy": {
                    "confidence": round(s["mastery_bias"], 2),
                    "persistence": {"excellent": "高", "good": "中", "medium": "中", "weak": "低"}[tier],
                    "help_seeking": "积极" if "协作" in s["style"] else "中等",
                },
                "interaction_pattern": {
                    "style": "协作型" if "协作" in s["style"] else "自驱型",
                    "depth": {"excellent": "探索式", "good": "目标导向", "medium": "应用导向", "weak": "引导式"}[tier],
                    "feedback": "需要具体反馈" if tier in ("excellent", "good") else "需要鼓励",
                },
            }
            row = db.get(models.ProfileRecord, s["user_id"])
            if row is None:
                db.add(models.ProfileRecord(
                    user_id=s["user_id"],
                    profile_data=profile_data,
                    version=1,
                    created_at=_NOW,
                    updated_at=_NOW,
                ))
                inserted += 1
            else:
                # 已存在则更新画像内容（保持幂等且升级内容）
                row.profile_data = profile_data
                row.version = (row.version or 1) + 1
                row.updated_at = _NOW
        db.commit()
    return inserted


def seed_bkt_states() -> int:
    inserted = 0
    with SessionLocal() as db:
        for s in STUDENTS:
            for kp in KNOWLEDGE_POINTS:
                # 唯一性检查
                existing = (
                    db.query(models.BktStateRecord)
                    .filter(
                        models.BktStateRecord.user_id == s["user_id"],
                        models.BktStateRecord.knowledge_point_id == kp["id"],
                    )
                    .first()
                )
                if existing is not None:
                    continue
                bias = s["mastery_bias"]
                # 强势 KP 提升，薄弱 KP 拉低
                if kp["id"] in s["focus_kps"]:
                    p_learned = _clamp(bias + random.uniform(0.10, 0.20))
                elif kp["id"] in s["weak_kps"]:
                    p_learned = _clamp(bias - random.uniform(0.20, 0.30))
                else:
                    p_learned = _clamp(bias + random.uniform(-0.10, 0.10))
                # 难度调整：难度越高 p_learned 越低
                p_learned = _clamp(p_learned - (kp["difficulty"] - 2) * 0.03)
                p_transit = round(random.uniform(0.08, 0.15), 3)
                p_slip = round(random.uniform(0.05, 0.15), 3)
                p_guess = round(random.uniform(0.15, 0.25), 3)
                # history 5-10 条
                history_len = random.randint(5, 10)
                history = []
                for i in range(history_len):
                    ts = _NOW - (history_len - i) * random.uniform(0.5, 3) * _DAY
                    correct = random.random() < p_learned
                    history.append({"ts": ts, "correct": bool(correct)})
                db.add(models.BktStateRecord(
                    user_id=s["user_id"],
                    knowledge_point_id=kp["id"],
                    p_learned=round(p_learned, 4),
                    p_transit=p_transit,
                    p_slip=p_slip,
                    p_guess=p_guess,
                    history=history,
                    updated_at=_NOW,
                ))
                inserted += 1
        db.commit()
    return inserted


def seed_mistakes() -> int:
    inserted = 0
    seq_per_student: Dict[str, int] = {s["user_id"]: 0 for s in STUDENTS}
    with SessionLocal() as db:
        existing_ids = {m.id for m in db.query(models.MistakeRecord.id).all()}
        for s in STUDENTS:
            tier = s["tier"]
            lo, hi = _mistake_count_for_tier(tier)
            n_mistakes = random.randint(lo, hi)
            for _ in range(n_mistakes):
                seq_per_student[s["user_id"]] += 1
                seq = seq_per_student[s["user_id"]]
                mid = f"mistake_seed_{s['user_id'].replace('demo-student-', '')}_{seq:03d}"
                if mid in existing_ids:
                    continue
                kp_id = _pick_kp_for_student(s)
                tpl = random.choice(MISTAKE_TEMPLATES.get(kp_id, [
                    {"q": f"关于 {kp_id} 的概念辨析题", "sa": "我不太确定", "ca": "需要结合具体定义回答"},
                ]))
                error_type = random.choices(
                    ERROR_TYPES,
                    weights=[25, 15, 20, 10, 10, 8, 7, 5],
                )[0]
                # 创建时间分布在最近 30 天
                days_ago = random.uniform(0.5, 30)
                created_at = _NOW - days_ago * _DAY
                # 70% 未解决，30% 已解决（解决时间在创建后 3-10 天）
                is_resolved = random.random() < 0.30
                resolved_at = (created_at + random.uniform(3, 10) * _DAY) if is_resolved else None
                db.add(models.MistakeRecord(
                    id=mid,
                    user_id=s["user_id"],
                    knowledge_point_id=kp_id,
                    question_data={
                        "question": tpl["q"],
                        "student_answer": tpl["sa"],
                        "correct_answer": tpl["ca"],
                    },
                    error_type=error_type,
                    analysis=f"错因分析：该生属于 {tier} 层级，在 {kp_id} 上存在 {error_type}。建议复习相关 KP 并完成配套练习。",
                    created_at=created_at,
                    resolved_at=resolved_at,
                ))
                inserted += 1
        db.commit()
    return inserted


def seed_assessments() -> int:
    inserted = 0
    with SessionLocal() as db:
        # 幂等：拉出已存在的 (user_id, record_type, topic, timestamp) 集合
        existing = set()
        for uid, rt, topic, ts in db.query(
            models.AssessmentRecord.user_id,
            models.AssessmentRecord.record_type,
            models.AssessmentRecord.topic,
            models.AssessmentRecord.timestamp,
        ).all():
            existing.add((uid, rt, topic, round(float(ts), 1)))
        for s in STUDENTS:
            n = _assessment_count_for_tier(s["tier"])
            added = 0
            attempts = 0
            while added < n and attempts < n * 3:
                attempts += 1
                kp_id = _pick_kp_for_student(s)
                record_type = random.choices(
                    ["quiz", "question", "resource_view", "activity"],
                    weights=[40, 25, 25, 10],
                )[0]
                score_low, score_high = _score_for_tier(s["tier"])
                if record_type in ("quiz", "question"):
                    score = round(random.uniform(score_low, score_high), 3)
                else:
                    score = None
                # 30 天分布
                days_ago = random.uniform(0.1, 30)
                timestamp = _NOW - days_ago * _DAY - random.uniform(0, _DAY)
                key = (s["user_id"], record_type, kp_id, round(timestamp, 1))
                if key in existing:
                    continue
                existing.add(key)
                duration = round(random.uniform(60, 1800), 1)
                kp_meta = next((k for k in KNOWLEDGE_POINTS if k["id"] == kp_id), None)
                bloom = kp_meta["bloom"] if kp_meta else "Apply"
                db.add(models.AssessmentRecord(
                    user_id=s["user_id"],
                    record_type=record_type,
                    score=score,
                    topic=kp_id,
                    duration=duration,
                    metadata_data={"kp_id": kp_id, "bloom": bloom},
                    timestamp=timestamp,
                ))
                inserted += 1
                added += 1
        db.commit()
    return inserted


def seed_learning_paths() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing_ids = {p.id for p in db.query(models.LearningPathRecord.id).all()}
        for s in STUDENTS:
            tier = s["tier"]
            pid = f"seed-path-{s['user_id']}"
            if pid in existing_ids:
                continue
            # 路径阶段
            stages = [
                {"title": "Python 编程与数据结构", "kps": ["python_basics", "data_structures"]},
                {"title": "数学基础（线代 + 概率）", "kps": ["linear_algebra", "probability_statistics"]},
                {"title": "机器学习基础", "kps": ["ml_basics", "supervised_learning", "unsupervised_learning"]},
                {"title": "深度学习（MLP/CNN/RNN）", "kps": ["neural_networks", "mlp", "cnn", "rnn", "lstm"]},
                {"title": "NLP 与 Transformer", "kps": ["nlp_basics", "attention_mechanism", "transformer"]},
                {"title": "前沿应用（RAG/Agent/RL）", "kps": ["rag", "ai_agent", "reinforcement_learning", "ai_project_practice"]},
            ]
            # 不同学生侧重不同阶段顺序
            if tier == "weak":
                stages = stages[:4]
            elif tier == "medium":
                stages = stages[:5]
            prog_lo, prog_hi = _progress_for_tier(tier)
            progress = round(random.uniform(prog_lo, prog_hi), 1)
            current_stage = int(progress / 100 * len(stages))
            if current_stage >= len(stages):
                current_stage = len(stages) - 1
            db.add(models.LearningPathRecord(
                id=pid,
                user_id=s["user_id"],
                title=f"{s['nickname']} · AI 学习路径（{ {'excellent':'拔高','good':'进阶','medium':'稳进','weak':'补强'}[tier] }版）",
                stages=stages,
                current_stage=current_stage,
                progress=progress,
                metadata_data={"recommended_by": "system", "tier": tier, "generated_at": _NOW},
                created_at=_NOW - random.uniform(1, 30) * _DAY,
                updated_at=_NOW,
            ))
            inserted += 1
        db.commit()
    return inserted


def _resource_content(kind: str, title: str, kp_ids: List[str]) -> str:
    """生成 300-800 字的 Markdown 内容"""
    kp_list = "、".join(kp_ids)
    if kind == "document":
        return (
            f"# {title}\n\n"
            f"## 一、章节目标\n\n本讲义围绕 **{kp_list}** 展开，帮助学习者建立完整的知识脉络。\n\n"
            f"## 二、核心概念\n\n"
            f"1. 基础定义：理解每个知识点的形式化描述\n"
            f"2. 关键公式：掌握核心公式的推导与适用条件\n"
            f"3. 典型应用：了解该知识点在主流框架中的落地方式\n\n"
            f"## 三、常见误区\n\n"
            f"- 望文生义：将公式机械套用，不区分条件\n"
            f"- 顺序混淆：在流程性知识（如反向传播）中跳过关键步骤\n"
            f"- 缺少验证：未在测试集上验证假设\n\n"
            f"## 四、配套练习\n\n完成配套 quiz（3-5 题），并尝试用真实数据集复现示例。\n\n"
            f"## 五、延伸阅读\n\n推荐阅读：deeplearningbook.org、distill.pub 相关章节。\n"
        )
    if kind == "quiz":
        return (
            f"# {title} · 练习题\n\n"
            f"## 题 1（基础）\n请用一句话概括 **{kp_ids[0]}** 的核心思想。\n\n"
            f"## 题 2（应用）\n给定一个简单场景，写出 **{kp_ids[0] if len(kp_ids)==1 else kp_ids[1]}** 的实现伪代码。\n\n"
            f"## 题 3（综合）\n对比 **{kp_list}** 三者的关系与适用场景。\n\n"
            f"## 参考答案\n见教师端资源库。\n"
        )
    if kind == "ppt":
        return (
            f"# {title} · PPT 大纲\n\n"
            f"## Slide 1  · 章节导览\n- 学习目标\n- 知识图谱定位\n\n"
            f"## Slide 2  · 核心概念 · {kp_ids[0]}\n- 定义\n- 关键性质\n- 图示\n\n"
            f"## Slide 3  · 公式与推导\n- 形式化定义\n- 关键推导步骤\n\n"
            f"## Slide 4  · 应用案例\n- 工业落地\n- 学术研究\n\n"
            f"## Slide 5  · 常见误区\n- 概念混淆\n- 公式误用\n\n"
            f"## Slide 6  · 总结与练习\n- 小结\n- 课后思考题\n"
        )
    if kind == "code":
        return (
            f"# {title} · 代码案例\n\n"
            f"```python\n"
            f"\"\"\"{title} — 配套代码示例\"\"\"\n"
            f"import numpy as np\n\n"
            f"# 1. 数据准备\n"
            f"X = np.random.randn(100, {len(kp_ids)})\n"
            f"y = np.random.randint(0, 2, 100)\n\n"
            f"# 2. 核心实现：{kp_ids[0]}\n"
            f"def core_fn(x, params):\n"
            f"    \"\"\"根据 {' / '.join(kp_ids)} 的核心思想实现\"\"\"\n"
            f"    return np.tanh(x @ params)\n\n"
            f"# 3. 训练循环（伪）\n"
            f"params = np.zeros(X.shape[1])\n"
            f"for epoch in range(10):\n"
            f"    pred = core_fn(X, params)\n"
            f"    loss = ((pred - y) ** 2).mean()\n"
            f"    params -= 0.01 * 2 * (pred - y).mean() * X.mean(axis=0)\n"
            f"    print('epoch=', epoch, 'loss=', round(loss, 4))\n"
            f"```\n\n"
            f"运行后查看训练损失变化。\n"
        )
    if kind == "mindmap":
        return (
            f"# {title}\n\n"
            f"```mermaid\nmindmap\n"
            f"  root(({kp_ids[0]}))\n"
            + "\n".join(f"    {kp_id}\n      要点 A\n      要点 B" for kp_id in kp_ids)
            + "\n```\n"
        )
    return f"# {title}\n\n内容占位符。\n"


def seed_teacher_resources() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing_ids = {r.id for r in db.query(models.ResourceRecord.id).all()}

        # 25 份课程级已发布
        course_kp_pool = [k["id"] for k in KNOWLEDGE_POINTS]
        course_resources = [
            ("机器学习基础补充讲义", "document", ["ml_basics", "supervised_learning"]),
            ("线性代数速查手册", "document", ["linear_algebra"]),
            ("概率统计核心公式汇总", "document", ["probability_statistics"]),
            ("决策树信息增益案例", "document", ["decision_trees"]),
            ("支持向量机几何直观", "document", ["svm"]),
            ("神经网络基础讲义", "document", ["neural_networks", "mlp"]),
            ("反向传播手把手推导", "document", ["backpropagation"]),
            ("CNN 卷积与池化可视化", "document", ["cnn"]),
            ("RNN 与 LSTM 序列建模", "document", ["rnn", "lstm"]),
            ("Self-Attention 图解", "document", ["attention_mechanism", "transformer"]),
            ("Transformer 完整架构梳理", "document", ["transformer"]),
            ("NLP 基础：分词与词向量", "document", ["nlp_basics"]),
            ("RAG 检索增强生成实战", "document", ["rag"]),
            ("强化学习入门到 PPO", "document", ["reinforcement_learning"]),
            ("AI Agent 规划与工具调用", "document", ["ai_agent", "mcp_protocol"]),
            ("Multi-Agent 协作模式", "document", ["multi_agent_systems"]),
            ("多模态大模型综述", "document", ["multimodal_llm"]),
            ("数据可视化原则", "document", ["data_visualization"]),
            ("学习分析伦理守则", "document", ["learning_analytics_ethics"]),
            ("BKT 与认知诊断基础", "document", ["cognitive_diagnosis"]),
            ("ML 基础配套练习", "quiz", ["ml_basics", "supervised_learning"]),
            ("深度学习综合题库", "quiz", ["mlp", "cnn", "rnn"]),
            ("Transformer 概念辨析", "quiz", ["attention_mechanism", "transformer"]),
            ("RAG 工程实践测验", "quiz", ["rag"]),
            ("AI 综合项目案例分析", "quiz", ["ai_project_practice", "ai_agent"]),
        ]
        for idx, (title, kind, kps) in enumerate(course_resources, start=1):
            rid = f"teacher_res_seed_course_{idx:03d}"
            if rid in existing_ids:
                continue
            db.add(models.ResourceRecord(
                id=rid,
                user_id="",  # 课程级
                type=kind,
                title=title,
                content=_resource_content(kind, title, kps),
                content_type="markdown",
                agent_name="teacher",
                metadata_data={
                    "course": COURSE,
                    "scope": "course",
                    "status": "published",
                    "created_by": "teacher",
                    "target_user_ids": [],
                    "kp_ids": kps,
                },
                tags=_pick_tags(kps, kind),
                created_at=_NOW - random.uniform(1, 14) * _DAY,
            ))
            inserted += 1

        # 10 份学生级（指派给特定学生）
        student_resources = [
            ("杜同学专属：Transformer 强化包", "document", "demo-student-1", ["transformer", "attention_mechanism"]),
            ("杜同学专属：概率统计补强", "quiz", "demo-student-1", ["probability_statistics"]),
            ("小强专属：数学基础速成", "document", "demo-student-5", ["linear_algebra", "probability_statistics"]),
            ("小强专属：Python 编程练习", "code", "demo-student-5", ["python_basics"]),
            ("小杨专属：入门学习路径", "ppt", "demo-student-6", ["python_basics", "ml_basics"]),
            ("小杨专属：MLP 概念入门", "document", "demo-student-6", ["neural_networks", "mlp"]),
            ("小何专属：基础补强包", "document", "demo-student-18", ["python_basics", "ml_basics"]),
            ("小高专属：零基础导论", "document", "demo-student-20", ["python_basics"]),
            ("小高专属：数据结构练习", "code", "demo-student-20", ["data_structures"]),
            ("小孙专属：深度学习综合", "document", "demo-student-13", ["transformer", "attention_mechanism", "backpropagation"]),
        ]
        for idx, (title, kind, uid, kps) in enumerate(student_resources, start=1):
            rid = f"teacher_res_seed_student_{idx:03d}"
            if rid in existing_ids:
                continue
            db.add(models.ResourceRecord(
                id=rid,
                user_id=uid,
                type=kind,
                title=title,
                content=_resource_content(kind, title, kps),
                content_type="markdown",
                agent_name="teacher",
                metadata_data={
                    "course": COURSE,
                    "scope": "student",
                    "status": "published",
                    "created_by": "teacher",
                    "target_user_ids": [uid],
                    "kp_ids": kps,
                },
                tags=_pick_tags(kps, kind) + ["个性化"],
                created_at=_NOW - random.uniform(1, 14) * _DAY,
            ))
            inserted += 1

        # 5 份草稿
        draft_resources = [
            ("草稿：RAG 工程实践 V2", "document", ["rag", "ai_project_practice"]),
            ("草稿：Agent 高级主题", "document", ["ai_agent", "multi_agent_systems"]),
            ("草稿：强化学习实战", "ppt", ["reinforcement_learning"]),
            ("草稿：综合项目模板", "code", ["ai_project_practice"]),
            ("草稿：MCP 协议细节", "mindmap", ["mcp_protocol"]),
        ]
        for idx, (title, kind, kps) in enumerate(draft_resources, start=1):
            rid = f"teacher_res_seed_draft_{idx:03d}"
            if rid in existing_ids:
                continue
            db.add(models.ResourceRecord(
                id=rid,
                user_id="",
                type=kind,
                title=title,
                content=_resource_content(kind, title, kps),
                content_type="markdown",
                agent_name="teacher",
                metadata_data={
                    "course": COURSE,
                    "scope": "course",
                    "status": "draft",
                    "created_by": "teacher",
                    "target_user_ids": [],
                    "kp_ids": kps,
                },
                tags=_pick_tags(kps, kind) + ["草稿"],
                created_at=_NOW - random.uniform(0.5, 7) * _DAY,
            ))
            inserted += 1
        db.commit()
    return inserted


def _pick_tags(kps: List[str], kind: str) -> List[str]:
    base = []
    for kp_id in kps[:2]:
        kp = next((k for k in KNOWLEDGE_POINTS if k["id"] == kp_id), None)
        if kp:
            base.append(kp["name"])
    if kind in ("document", "ppt"):
        base.append("讲义")
    elif kind == "quiz":
        base.append("练习")
    elif kind == "code":
        base.append("代码")
    elif kind == "mindmap":
        base.append("思维导图")
    return list(dict.fromkeys(base))[:5]


def seed_gamification() -> int:
    inserted = 0
    with SessionLocal() as db:
        for s in STUDENTS:
            existing = db.get(models.GamificationProfileRecord, s["user_id"])
            if existing is not None:
                continue
            xp_lo, xp_hi = _xp_for_tier(s["tier"])
            xp = random.randint(xp_lo, xp_hi)
            level = xp // 500 + 1
            streak_lo, streak_hi = _streak_for_tier(s["tier"])
            streak = random.randint(streak_lo, streak_hi)
            ach_pool = [
                {"key": "first_quiz", "label": "初次答题", "icon": "🎯"},
                {"key": "ten_quizzes", "label": "十题斩", "icon": "🔟"},
                {"key": "no_mistakes", "label": "零错题周", "icon": "✨"},
                {"key": "seven_day_streak", "label": "七日连击", "icon": "🔥"},
                {"key": "level_5", "label": "登堂入室", "icon": "🏆"},
                {"key": "first_path", "label": "完成首个学习路径", "icon": "🛤️"},
                {"key": "ask_tutor", "label": "向猫头讲师求助", "icon": "🦉"},
                {"key": "share_resource", "label": "分享资源", "icon": "📤"},
            ]
            n_ach = random.randint(2, 5)
            achievements = random.sample(ach_pool, n_ach)
            db.add(models.GamificationProfileRecord(
                user_id=s["user_id"],
                xp=xp,
                level=level,
                streak_days=streak,
                achievements=achievements,
                updated_at=_NOW,
            ))
            inserted += 1
        db.commit()
    return inserted


def seed_sm2_schedules() -> int:
    inserted = 0
    with SessionLocal() as db:
        # 取每个学生 BKT 中掌握度 > 0.6 的前 5 个 KP
        for s in STUDENTS:
            rows = (
                db.query(models.BktStateRecord)
                .filter(
                    models.BktStateRecord.user_id == s["user_id"],
                    models.BktStateRecord.p_learned > 0.6,
                )
                .order_by(models.BktStateRecord.p_learned.desc())
                .limit(5)
                .all()
            )
            if len(rows) < 5:
                # 不足 5 条时随便补几个 KP
                kp_ids = [r.knowledge_point_id for r in rows]
                for kp in KNOWLEDGE_POINTS:
                    if kp["id"] not in kp_ids and len(rows) >= 5:
                        break
                    if kp["id"] not in kp_ids:
                        # 构造一个伪 row
                        from types import SimpleNamespace
                        rows.append(SimpleNamespace(
                            user_id=s["user_id"],
                            knowledge_point_id=kp["id"],
                            p_learned=0.61,
                        ))
            existing_items = {
                it.item_id
                for it in db.query(models.Sm2ScheduleRecord)
                .filter(models.Sm2ScheduleRecord.user_id == s["user_id"])
                .all()
            }
            for r in rows[:5]:
                if r.knowledge_point_id in existing_items:
                    continue
                rep = random.randint(0, 3)
                interval = random.choice([1, 2, 3, 5, 7, 10, 14])
                easiness = round(random.uniform(2.0, 2.8), 2)
                due = _NOW + interval * _DAY
                db.add(models.Sm2ScheduleRecord(
                    user_id=s["user_id"],
                    item_id=r.knowledge_point_id,
                    item_type="knowledge_point",
                    repetitions=rep,
                    interval_days=interval,
                    easiness=easiness,
                    due_at=due,
                    updated_at=_NOW,
                ))
                inserted += 1
        db.commit()
    return inserted


def seed_group_chat_messages() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing_msg_ids = {
            m.id for m in db.query(models.GroupChatMessageRecord.id).all()
        }
        # 给 5 个学生（每个 tier 选 1-2 个代表）预置 6-8 条历史消息
        rep_students = [
            "demo-student-1", "demo-student-7",       # 学霸
            "demo-student-4", "demo-student-10",      # 良好
            "demo-student-5", "demo-student-15",      # 中等
            "demo-student-6", "demo-student-20",      # 待提升
        ]
        # 一些常用消息模板
        text_templates = [
            "老师，这道题我看了三遍还是不确定，能帮我拆解一下吗？",
            "我今天做完了 RAG 章节的练习，错题分析里说我有知识缺漏，能再讲一下 chunk size 的影响吗？",
            "我用 PyTorch 跑通了 CNN 那个小项目，训练 loss 降得很慢，会是什么原因？",
            "请教一下 Transformer 的位置编码为什么不用可学习的？",
            "我想做一个简单的 AI Agent 练手项目，有什么推荐路径吗？",
            "请问多智能体系统的通信协议有什么比较主流的方案？",
            "我对 RAG 的重排 (Rerank) 还不太理解，能给个具体例子吗？",
            "为什么我的模型在训练集上 95% 但验证集只有 70%？",
        ]
        teacher_templates = [
            "请大家下周提交 3 道错题的复盘报告，关注错因归类。",
            "@杜同学 你的 Transformer 作业完成得很出色，请在小组分享。",
            "本周 RAG 章节新增 5 道综合题，建议错题数 > 5 的同学优先完成。",
            "学习路径已根据大家最近 7 天的活动数据更新，请刷新查看。",
        ]
        agent_templates = [
            "我注意到你在反向传播章节错了 3 题，可以从『链式法则+计算图』这两个角度复盘。",
            "基于你最近的活跃情况，建议先巩固 Python 基础，再进入 ML 章节。",
            "我已为你生成个性化学习路径，包含 6 个阶段，可在「学习路径」页查看。",
            "你提的 Rerank 问题很好，Cross-Encoder 比 Bi-Encoder 在精排上更准确，但速度更慢。",
        ]
        seq = 0
        for uid in rep_students:
            room_id = f"{COURSE}:{uid}"
            nickname = next(s["nickname"] for s in STUDENTS if s["user_id"] == uid)
            n_msgs = random.randint(6, 8)
            for i in range(n_msgs):
                seq += 1
                msg_id = f"gmsg_seed_{uid.replace('demo-student-', '')}_{i:02d}"
                if msg_id in existing_msg_ids:
                    continue
                # 随机选 message_type 分布：text 40, teacher 15, agent 20, resource 10, path 5, system 10
                mtype = random.choices(
                    ["text", "teacher_message", "agent_reply", "resource_card", "path_card", "system_notice"],
                    weights=[40, 15, 20, 10, 5, 10],
                )[0]
                if mtype == "text":
                    sender_id, sender_name, sender_role = uid, nickname, "student"
                    content = random.choice(text_templates)
                    payload = {}
                elif mtype == "teacher_message":
                    sender_id, sender_name, sender_role = _TEACHER_ID, _TEACHER_NAME, "teacher"
                    content = random.choice(teacher_templates)
                    payload = {}
                elif mtype == "agent_reply":
                    sender_id, sender_name, sender_role = "tutor_agent", "猫头讲师", "agent"
                    content = random.choice(agent_templates)
                    payload = {}
                elif mtype == "resource_card":
                    sender_id, sender_name, sender_role = _TEACHER_ID, _TEACHER_NAME, "teacher"
                    rid = f"teacher_res_seed_course_{random.randint(1, 25):03d}"
                    content = "为你推荐一份课程资源："
                    payload = {"resource_id": rid, "kind": "resource_card"}
                elif mtype == "path_card":
                    sender_id, sender_name, sender_role = "tutor_agent", "猫头讲师", "agent"
                    content = "已为你更新学习路径："
                    payload = {"path_id": f"seed-path-{uid}", "kind": "path_card"}
                else:  # system_notice
                    sender_id, sender_name, sender_role = "system", "系统", "system"
                    content = random.choice([
                        "本周班级活跃度排名已更新，请查看班级看板。",
                        "新增 3 道 RAG 章节配套练习。",
                        "RAG 章节学习路径已根据你的错题自动调整。",
                    ])
                    payload = {}
                # 时间在最近 7 天
                ts = _NOW - random.uniform(0.1, 7) * _DAY
                db.add(models.GroupChatMessageRecord(
                    id=msg_id,
                    room_id=room_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    sender_role=sender_role,
                    content=content,
                    message_type=mtype,
                    payload=payload,
                    created_at=ts,
                ))
                inserted += 1
        db.commit()
    return inserted


# ================================================================
# Python 程序设计课 · 种子数据
# ================================================================
PY_COURSE = "python_programming"

PY_KNOWLEDGE_POINTS: List[Dict[str, Any]] = [
    {"id": "py_overview", "name": "Python 语言概述", "description": "发展历史、设计哲学、解释型与动态类型", "bloom": "Understand", "difficulty": 1},
    {"id": "py_variables_types", "name": "变量与数据类型", "description": "int/float/str/bool、动态类型、可变与不可变对象", "bloom": "Understand", "difficulty": 1},
    {"id": "py_operators", "name": "运算符与表达式", "description": "算术/比较/逻辑/赋值运算符、优先级、海象运算符", "bloom": "Apply", "difficulty": 1},
    {"id": "py_control_flow", "name": "控制流（条件与循环）", "description": "if-elif-else、for/while、break/continue、enumerate/zip", "bloom": "Apply", "difficulty": 2},
    {"id": "py_functions", "name": "函数定义与参数", "description": "def/return、默认参数、*args/**kwargs、lambda、类型注解", "bloom": "Apply", "difficulty": 2},
    {"id": "py_lists", "name": "列表与列表推导式", "description": "增删改查、切片、列表推导式、时间复杂度、浅/深拷贝", "bloom": "Apply", "difficulty": 2},
    {"id": "py_dicts", "name": "字典与哈希表", "description": "键值对、get/setdefault、字典推导式、哈希表原理", "bloom": "Apply", "difficulty": 2},
    {"id": "py_tuples_sets", "name": "元组与集合", "description": "不可变序列、集合运算（并/交/差）、frozenset", "bloom": "Apply", "difficulty": 2},
    {"id": "py_strings", "name": "字符串操作", "description": "f-string、split/join/strip/replace、编码、不可变性", "bloom": "Apply", "difficulty": 2},
    {"id": "py_collections", "name": "collections 高级容器", "description": "defaultdict/Counter/deque/namedtuple/OrderedDict", "bloom": "Apply", "difficulty": 3},
    {"id": "py_classes", "name": "类与对象", "description": "class/__init__/self、实例/类属性、@property/@classmethod/@staticmethod", "bloom": "Apply", "difficulty": 3},
    {"id": "py_inheritance", "name": "继承与多态", "description": "单/多继承、super()、方法重写、MRO/C3线性化、鸭子类型", "bloom": "Apply", "difficulty": 3},
    {"id": "py_encapsulation", "name": "封装与 property", "description": "_protected/__private、名称改写、@property/@setter、dataclass", "bloom": "Apply", "difficulty": 3},
    {"id": "py_magic_methods", "name": "魔术方法", "description": "__repr__/__str__/__add__/__eq__/__getitem__/__iter__、运算符重载", "bloom": "Analyze", "difficulty": 3},
    {"id": "py_context_manager", "name": "上下文管理器", "description": "with/__enter__/__exit__、contextlib、资源管理", "bloom": "Apply", "difficulty": 3},
    {"id": "py_file_io", "name": "文件读写", "description": "open/read/write、文件模式、encoding、with open", "bloom": "Apply", "difficulty": 2},
    {"id": "py_pathlib", "name": "pathlib 路径操作", "description": "Path对象、glob/rglob、mkdir/stat、suffix/stem/parent", "bloom": "Apply", "difficulty": 2},
    {"id": "py_csv_json", "name": "CSV 与 JSON 处理", "description": "csv.DictReader/Writer、json.dumps/loads、序列化", "bloom": "Apply", "difficulty": 2},
    {"id": "py_exceptions", "name": "异常处理", "description": "try-except-else-finally、raise、异常层级、最佳实践", "bloom": "Apply", "difficulty": 3},
    {"id": "py_custom_exceptions", "name": "自定义异常", "description": "继承Exception、异常属性、raise from、业务异常设计", "bloom": "Analyze", "difficulty": 3},
    {"id": "py_stdlib", "name": "常用标准库", "description": "os/sys/datetime/re/math/random/logging/argparse", "bloom": "Apply", "difficulty": 2},
    {"id": "py_iterators_generators", "name": "迭代器与生成器", "description": "迭代器协议、yield、生成器函数/表达式、惰性计算", "bloom": "Analyze", "difficulty": 4},
    {"id": "py_decorators", "name": "装饰器", "description": "高阶函数、闭包、functools.wraps、带参装饰器、类装饰器", "bloom": "Analyze", "difficulty": 4},
    {"id": "py_project", "name": "Python 项目实战", "description": "项目结构、虚拟环境、pytest、模块化、打包发布", "bloom": "Create", "difficulty": 5},
]

PY_KNOWLEDGE_RELATIONS: List[Dict[str, Any]] = [
    {"source": "py_overview", "target": "py_variables_types", "type": "prerequisite", "weight": 0.9},
    {"source": "py_variables_types", "target": "py_operators", "type": "prerequisite", "weight": 0.9},
    {"source": "py_operators", "target": "py_control_flow", "type": "prerequisite", "weight": 0.85},
    {"source": "py_variables_types", "target": "py_lists", "type": "prerequisite", "weight": 0.8},
    {"source": "py_control_flow", "target": "py_functions", "type": "prerequisite", "weight": 0.9},
    {"source": "py_lists", "target": "py_dicts", "type": "related", "weight": 0.7},
    {"source": "py_lists", "target": "py_tuples_sets", "type": "related", "weight": 0.75},
    {"source": "py_variables_types", "target": "py_strings", "type": "prerequisite", "weight": 0.8},
    {"source": "py_dicts", "target": "py_collections", "type": "specialization", "weight": 0.85},
    {"source": "py_tuples_sets", "target": "py_collections", "type": "specialization", "weight": 0.75},
    {"source": "py_functions", "target": "py_classes", "type": "prerequisite", "weight": 0.85},
    {"source": "py_classes", "target": "py_inheritance", "type": "prerequisite", "weight": 0.9},
    {"source": "py_classes", "target": "py_encapsulation", "type": "specialization", "weight": 0.85},
    {"source": "py_classes", "target": "py_magic_methods", "type": "specialization", "weight": 0.8},
    {"source": "py_magic_methods", "target": "py_context_manager", "type": "prerequisite", "weight": 0.8},
    {"source": "py_strings", "target": "py_file_io", "type": "prerequisite", "weight": 0.7},
    {"source": "py_context_manager", "target": "py_file_io", "type": "related", "weight": 0.75},
    {"source": "py_file_io", "target": "py_pathlib", "type": "specialization", "weight": 0.8},
    {"source": "py_file_io", "target": "py_csv_json", "type": "specialization", "weight": 0.8},
    {"source": "py_dicts", "target": "py_csv_json", "type": "related", "weight": 0.6},
    {"source": "py_control_flow", "target": "py_exceptions", "type": "prerequisite", "weight": 0.75},
    {"source": "py_file_io", "target": "py_exceptions", "type": "related", "weight": 0.7},
    {"source": "py_classes", "target": "py_custom_exceptions", "type": "prerequisite", "weight": 0.8},
    {"source": "py_exceptions", "target": "py_custom_exceptions", "type": "prerequisite", "weight": 0.85},
    {"source": "py_functions", "target": "py_stdlib", "type": "prerequisite", "weight": 0.7},
    {"source": "py_file_io", "target": "py_stdlib", "type": "related", "weight": 0.6},
    {"source": "py_functions", "target": "py_iterators_generators", "type": "prerequisite", "weight": 0.85},
    {"source": "py_collections", "target": "py_iterators_generators", "type": "related", "weight": 0.7},
    {"source": "py_classes", "target": "py_decorators", "type": "prerequisite", "weight": 0.8},
    {"source": "py_iterators_generators", "target": "py_decorators", "type": "related", "weight": 0.65},
    {"source": "py_classes", "target": "py_project", "type": "used_in", "weight": 0.85},
    {"source": "py_csv_json", "target": "py_project", "type": "used_in", "weight": 0.8},
    {"source": "py_exceptions", "target": "py_project", "type": "used_in", "weight": 0.8},
    {"source": "py_stdlib", "target": "py_project", "type": "used_in", "weight": 0.75},
    {"source": "py_decorators", "target": "py_project", "type": "used_in", "weight": 0.7},
]

PY_STUDENTS: List[Dict[str, Any]] = [
    {"user_id": "demo-student-1", "nickname": "杜同学", "tier": "excellent", "mastery_bias": 0.82,
     "style": "视觉型·自驱", "focus_kps": ["py_decorators", "py_iterators_generators", "py_magic_methods", "py_classes"], "weak_kps": ["py_csv_json"]},
    {"user_id": "demo-student-2", "nickname": "小李", "tier": "excellent", "mastery_bias": 0.90,
     "style": "读写型·自驱", "focus_kps": ["py_functions", "py_lists", "py_dicts", "py_stdlib"], "weak_kps": ["py_decorators"]},
    {"user_id": "demo-student-3", "nickname": "小赵", "tier": "excellent", "mastery_bias": 0.85,
     "style": "动手型·自驱", "focus_kps": ["py_project", "py_file_io", "py_classes", "py_exceptions"], "weak_kps": ["py_iterators_generators"]},
    {"user_id": "demo-student-7", "nickname": "小陈", "tier": "excellent", "mastery_bias": 0.80,
     "style": "视觉型·自驱", "focus_kps": ["py_variables_types", "py_lists", "py_encapsulation", "py_inheritance"], "weak_kps": ["py_decorators", "py_custom_exceptions"]},
    {"user_id": "demo-student-4", "nickname": "小慧", "tier": "good", "mastery_bias": 0.68,
     "style": "读写型·协作", "focus_kps": ["py_strings", "py_dicts", "py_csv_json"], "weak_kps": ["py_inheritance", "py_magic_methods"]},
    {"user_id": "demo-student-8", "nickname": "小王", "tier": "good", "mastery_bias": 0.75,
     "style": "听觉型·自驱", "focus_kps": ["py_functions", "py_lists", "py_stdlib"], "weak_kps": ["py_iterators_generators", "py_decorators"]},
    {"user_id": "demo-student-9", "nickname": "小刘", "tier": "good", "mastery_bias": 0.70,
     "style": "动手型·协作", "focus_kps": ["py_classes", "py_file_io", "py_project"], "weak_kps": ["py_encapsulation", "py_context_manager"]},
    {"user_id": "demo-student-10", "nickname": "小周", "tier": "good", "mastery_bias": 0.72,
     "style": "视觉型·自驱", "focus_kps": ["py_variables_types", "py_control_flow", "py_functions"], "weak_kps": ["py_magic_methods", "py_decorators"]},
    {"user_id": "demo-student-11", "nickname": "小吴", "tier": "good", "mastery_bias": 0.65,
     "style": "读写型·协作", "focus_kps": ["py_tuples_sets", "py_collections"], "weak_kps": ["py_classes", "py_inheritance"]},
    {"user_id": "demo-student-12", "nickname": "小郑", "tier": "good", "mastery_bias": 0.78,
     "style": "动手型·自驱", "focus_kps": ["py_project", "py_file_io", "py_exceptions"], "weak_kps": ["py_iterators_generators"]},
    {"user_id": "demo-student-5", "nickname": "小强", "tier": "medium", "mastery_bias": 0.55,
     "style": "动手型·实践", "focus_kps": ["py_variables_types", "py_project"], "weak_kps": ["py_classes", "py_inheritance", "py_decorators"]},
    {"user_id": "demo-student-13", "nickname": "小孙", "tier": "medium", "mastery_bias": 0.48,
     "style": "视觉型·协作", "focus_kps": ["py_lists", "py_strings"], "weak_kps": ["py_classes", "py_magic_methods", "py_iterators_generators"]},
    {"user_id": "demo-student-14", "nickname": "小朱", "tier": "medium", "mastery_bias": 0.58,
     "style": "读写型·实践", "focus_kps": ["py_variables_types", "py_control_flow"], "weak_kps": ["py_inheritance", "py_encapsulation", "py_decorators"]},
    {"user_id": "demo-student-15", "nickname": "小胡", "tier": "medium", "mastery_bias": 0.52,
     "style": "听觉型·协作", "focus_kps": ["py_strings"], "weak_kps": ["py_dicts", "py_classes", "py_exceptions"]},
    {"user_id": "demo-student-16", "nickname": "小郭", "tier": "medium", "mastery_bias": 0.56,
     "style": "动手型·实践", "focus_kps": ["py_lists", "py_variables_types"], "weak_kps": ["py_magic_methods", "py_context_manager", "py_inheritance"]},
    {"user_id": "demo-student-17", "nickname": "小林", "tier": "medium", "mastery_bias": 0.60,
     "style": "视觉型·自驱", "focus_kps": ["py_csv_json", "py_stdlib"], "weak_kps": ["py_decorators", "py_iterators_generators", "py_custom_exceptions"]},
    {"user_id": "demo-student-6", "nickname": "小杨", "tier": "weak", "mastery_bias": 0.30,
     "style": "视觉型·实践", "focus_kps": ["py_variables_types"], "weak_kps": ["py_classes", "py_functions", "py_inheritance", "py_decorators", "py_iterators_generators"]},
    {"user_id": "demo-student-18", "nickname": "小何", "tier": "weak", "mastery_bias": 0.35,
     "style": "听觉型·协作", "focus_kps": [], "weak_kps": ["py_variables_types", "py_control_flow", "py_functions", "py_lists", "py_classes"]},
    {"user_id": "demo-student-19", "nickname": "小罗", "tier": "weak", "mastery_bias": 0.40,
     "style": "读写型·实践", "focus_kps": ["py_variables_types", "py_project"], "weak_kps": ["py_classes", "py_inheritance", "py_decorators", "py_iterators_generators"]},
    {"user_id": "demo-student-20", "nickname": "小高", "tier": "weak", "mastery_bias": 0.25,
     "style": "动手型·协作", "focus_kps": [], "weak_kps": ["py_variables_types", "py_control_flow", "py_functions", "py_lists", "py_classes", "py_exceptions"]},
]

PY_MISTAKE_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "py_overview": [
        {"q": "Python 属于编译型还是解释型语言？", "sa": "编译型。", "ca": "解释型语言，源代码在运行时由解释器逐行执行，无需预先编译为机器码"},
    ],
    "py_variables_types": [
        {"q": "Python 中 a = [1,2]; b = a; b.append(3) 后 a 的值？", "sa": "a 还是 [1,2]。", "ca": "a 变为 [1,2,3]。列表是可变对象，b = a 是引用赋值而非拷贝，二者指向同一对象"},
        {"q": "Python 中 is 和 == 的区别？", "sa": "一样。", "ca": "== 比较值是否相等；is 比较两个对象的身份（内存地址）是否相同。小整数缓存可能导致 is 也为 True 但语义不同"},
        {"q": "Python 中 0.1 + 0.2 == 0.3 的结果？", "sa": "True。", "ca": "False。浮点数精度问题导致 0.1+0.2 = 0.30000000000000004，应用 math.isclose() 比较"},
    ],
    "py_operators": [
        {"q": "Python 中 2 ** 3 ** 2 的结果？", "sa": "64。", "ca": "512。幂运算符 ** 是右结合的，等价于 2 ** (3 ** 2) = 2 ** 9 = 512"},
        {"q": "Python 中 True + True + False 的值？", "sa": "报错。", "ca": "2。bool 是 int 的子类，True=1, False=0，可参与算术运算"},
    ],
    "py_control_flow": [
        {"q": "for ... else 中 else 何时执行？", "sa": "每次循环后都执行。", "ca": "for 循环正常结束（未被 break 打断）时才执行 else 块"},
        {"q": "enumerate(['a','b','c'], start=1) 的输出？", "sa": "(0,'a')(1,'b')(2,'c')。", "ca": "(1,'a')(2,'b')(3,'c')。start 参数指定起始索引，默认为 0"},
    ],
    "py_functions": [
        {"q": "Python 中 def f(x, items=[]): items.append(x) 多次调用为什么会累加？",
         "sa": "因为列表会被复制，每次都同一份。", "ca": "默认参数在函数定义时只求值一次，多个调用共享同一个列表。应改为 def f(x, items=None): items = items or []"},
        {"q": "Python 中 *args 与 **kwargs 的用法区别？",
         "sa": "都是位置参数。", "ca": "*args 接收额外位置参数为元组，**kwargs 接收关键字参数为字典，组合使用可实现通用接口"},
        {"q": "lambda 表达式与 def 函数的区别？", "sa": "完全一样。", "ca": "lambda 是匿名单表达式函数，不能包含语句和多行；def 定义命名函数可含复杂逻辑。lambda 适合简短回调"},
    ],
    "py_lists": [
        {"q": "Python 列表 a = [1,2,3,4,5]; a[1:3] 的结果？", "sa": "[1,2,3]。", "ca": "[2,3]。切片是左闭右开区间，a[1:3] 取索引 1 和 2 的元素"},
        {"q": "列表的 insert(0, x) 时间复杂度？", "sa": "O(1)。", "ca": "O(n)。在头部插入需要移动后续所有元素。频繁头部操作应使用 collections.deque"},
        {"q": "浅拷贝 copy.copy(a) 与深拷贝 copy.deepcopy(a) 的区别？", "sa": "没有区别。", "ca": "浅拷贝只复制外层容器，内层嵌套对象仍共享引用；深拷贝递归复制所有层级，完全独立"},
    ],
    "py_dicts": [
        {"q": "哈希表 (dict) 的平均查找复杂度？", "sa": "O(n)。", "ca": "平均 O(1)，最坏 O(n)（哈希冲突严重时）。Python dict 通过开放寻址 + 随机探测保持接近 O(1)"},
        {"q": "Python 字典在 3.7+ 为什么保持插入顺序？", "sa": "因为排过序。", "ca": "CPython 3.7+ 实现使用紧凑的稀疏数组 + 顺序插入表，保证了插入顺序；3.6 是实现细节，3.7 正式成为语言规范"},
    ],
    "py_tuples_sets": [
        {"q": "Python 中元组 (1,) 和 (1) 的区别？", "sa": "一样。", "ca": "(1,) 是单元素元组；(1) 只是括号包裹的整数 1，不是元组。空元组是 ()"},
        {"q": "frozenset 与 set 的区别？", "sa": "frozenset 更快。", "ca": "frozenset 是不可变集合，可哈希、可作为 dict 的键或 set 的元素；set 是可变的，不可哈希"},
    ],
    "py_strings": [
        {"q": "Python 中 'a' * 3 的结果？", "sa": "['a','a','a']。", "ca": "'aaa'。字符串乘法返回重复拼接后的新字符串，不是列表"},
        {"q": "字符串 '  hello  '.strip() 的结果？", "sa": "'  hello'。", "ca": "'hello'。strip() 去除两端空白字符，lstrip/rstrip 分别去左/右端"},
        {"q": "f-string 中 {x:>10} 的含义？", "sa": "左对齐宽度 10。", "ca": "右对齐，总宽度 10 字符，不足左侧补空格。< 左对齐、^ 居中"},
    ],
    "py_collections": [
        {"q": "defaultdict(int) 访问不存在的键会怎样？", "sa": "报 KeyError。", "ca": "返回 0 并自动插入该键。defaultdict 用工厂函数生成默认值，避免手动 setdefault"},
        {"q": "Counter('aabbbc').most_common(2) 的结果？", "sa": "[('a',2),('b',3)]。", "ca": "[('b',3),('a',2)]。most_common 返回按计数降序排列的前 n 个元素"},
    ],
    "py_classes": [
        {"q": "@property 装饰器的作用？", "sa": "就是给类加属性。", "ca": "@property 把方法转为只读属性，调用 obj.attr 时实际执行方法，可封装 getter / setter / deleter"},
        {"q": "@staticmethod 和 @classmethod 的区别？", "sa": "一样。", "ca": "@staticmethod 不接收隐式首参数（普通函数挂在类上）；@classmethod 接收 cls 作为首参数，可访问/修改类状态"},
        {"q": "实例属性和类属性有什么区别？", "sa": "没有区别。", "ca": "类属性属于类本身，所有实例共享；实例属性属于单个实例，互不影响。查找时先找实例属性再找类属性"},
    ],
    "py_inheritance": [
        {"q": "super() 的作用？", "sa": "调用父类。", "ca": "super() 返回代理对象，按 MRO 顺序调用父类方法，避免硬编码父类名，支持多继承协作"},
        {"q": "Python 多继承的 MRO 是什么？", "sa": "从左到右。", "ca": "Method Resolution Order，C3 线性化算法确定方法查找顺序，可通过 ClassName.__mro__ 查看"},
    ],
    "py_encapsulation": [
        {"q": "Python 中 __attr（双下划线前缀）的作用？", "sa": "私有属性。", "ca": "触发名称改写（name mangling）：__attr 变成 _ClassName__attr，避免子类同名冲突，但仍可通过改写名访问，并非真正私有"},
        {"q": "dataclass 装饰器的好处？", "sa": "让类更快。", "ca": "自动生成 __init__/__repr__/__eq__ 等方法，减少样板代码，适合数据容器类"},
    ],
    "py_magic_methods": [
        {"q": "__repr__ 和 __str__ 的区别？", "sa": "一样。", "ca": "__str__ 面向用户（print/str），返回可读字符串；__repr__ 面向开发者（repr/交互式），应返回可重建对象的表达式"},
        {"q": "实现 __eq__ 后为什么还要实现 __hash__？", "sa": "不用。", "ca": "Python 规定：定义了 __eq__ 的类 __hash__ 被设为 None，实例变为不可哈希。如需可哈希需同时定义 __hash__"},
    ],
    "py_context_manager": [
        {"q": "with 语句中 __exit__ 返回 True 的效果？", "sa": "没有效果。", "ca": "返回 True 会抑制 with 块中的异常，使其不向外传播；返回 False 或 None 则异常正常传播"},
        {"q": "contextlib.contextmanager 装饰器的用法？", "sa": "替代 class。", "ca": "把生成器函数变为上下文管理器：yield 之前相当于 __enter__，yield 的值是 as 绑定的对象，yield 之后相当于 __exit__"},
    ],
    "py_file_io": [
        {"q": "open() 默认的文件模式？", "sa": "二进制读。", "ca": "文本模式只读 'rt'，可简写为 'r'。文本模式会做编码转换，二进制模式 'rb' 返回 bytes"},
        {"q": "with open('f.txt','w') as f 的好处？", "sa": "更快。", "ca": "确保文件在 with 块结束时自动关闭，即使发生异常也不会泄漏文件句柄，等价于 try-finally"},
    ],
    "py_pathlib": [
        {"q": "Path('./data').glob('**/*.md') 的作用？", "sa": "创建目录。", "ca": "递归搜索 data 目录下所有 .md 文件，返回 Path 迭代器"},
        {"q": "Path('config/settings.yaml').stem 的值？", "sa": "settings.yaml。", "ca": "settings。stem 返回不含后缀的文件名，suffix 返回后缀（.yaml），name 返回完整文件名"},
    ],
    "py_csv_json": [
        {"q": "json.dumps() 和 json.dump() 的区别？", "sa": "一样。", "ca": "dumps() 返回 JSON 字符串；dump() 直接写入文件对象。对应 loads() 和 load()"},
        {"q": "json.dumps({'name':'中文'}) 默认输出？", "sa": "{\"name\":\"中文\"}。", "ca": "{\"name\": \"\\u4e2d\\u6587\"}。默认 ensure_ascii=True 会转义非 ASCII 字符，需设置 ensure_ascii=False 保留中文"},
    ],
    "py_exceptions": [
        {"q": "try-except-else-finally 中 else 何时执行？", "sa": "有异常时。", "ca": "try 块没有抛出任何异常时才执行 else 块。finally 无论是否异常都执行"},
        {"q": "裸 except: 有什么问题？", "sa": "没问题。", "ca": "裸 except 会捕获所有异常包括 KeyboardInterrupt/SystemExit，可能隐藏严重错误。应捕获具体异常如 except ValueError:"},
    ],
    "py_custom_exceptions": [
        {"q": "自定义异常应继承哪个类？", "sa": "BaseException。", "ca": "应继承 Exception。BaseException 包括 SystemExit/KeyboardInterrupt 等不应被常规捕获的异常"},
        {"q": "raise ... from ... 的作用？", "sa": "替代原异常。", "ca": "链式异常：保留原始异常作为 __cause__，调试时可看到完整的异常链。raise NewError() from original_error"},
    ],
    "py_stdlib": [
        {"q": "datetime.now() 和 datetime.utcnow() 的区别？", "sa": "一样。", "ca": "now() 返回本地时区时间；utcnow() 返回 UTC 时间。Python 3.12+ 已弃用 utcnow()，推荐用 datetime.now(timezone.utc)"},
        {"q": "re.match() 和 re.search() 的区别？", "sa": "一样。", "ca": "match() 只从字符串开头匹配；search() 扫描整个字符串寻找第一个匹配。如需全文匹配用 fullmatch()"},
    ],
    "py_iterators_generators": [
        {"q": "yield 与 return 的核心区别？", "sa": "yield 就是 return 的别名。", "ca": "yield 返回值后暂停函数并保留执行状态，下次 next() 从 yield 继续；return 直接终止函数。生成器依赖 yield 实现惰性计算"},
        {"q": "生成器表达式 (x**2 for x in range(10)) 与列表推导式的区别？", "sa": "结果一样。", "ca": "生成器表达式返回迭代器，惰性求值，内存占用 O(1)；列表推导式一次性生成完整列表，内存占用 O(n)"},
    ],
    "py_decorators": [
        {"q": "装饰器的本质是什么？", "sa": "注释。", "ca": "装饰器是一个高阶函数：接收函数作为参数，返回新函数替换原函数。@decorator 等价于 func = decorator(func)"},
        {"q": "为什么带参数的装饰器需要三层嵌套？", "sa": "不需要。", "ca": "最外层接收参数，中间层接收被装饰函数，最内层是实际执行逻辑。@decorator(arg) 先调用 decorator(arg) 返回中间层，再对函数应用"},
        {"q": "functools.wraps 的作用？", "sa": "让装饰器更快。", "ca": "将被装饰函数的 __name__/__doc__/__module__ 等元信息复制到包装函数，避免调试时丢失原函数信息"},
    ],
    "py_project": [
        {"q": "虚拟环境的作用？", "sa": "让程序跑得更快。", "ca": "隔离项目依赖，避免不同项目间的包版本冲突。常用 venv/virtualenv/poetry 创建"},
        {"q": "requirements.txt 中 >= 和 == 的选择？", "sa": "都用 ==。", "ca": "== 固定版本确保可复现（部署时）；>= 允许兼容升级（开发时）。生产建议锁定版本或使用 lock 文件"},
    ],
}


# ── Python 种子函数 ──────────────────────────────────────────

def _py_pick_kp(student: Dict[str, Any]) -> str:
    if random.random() < 0.7 and student["focus_kps"]:
        return random.choice(student["focus_kps"])
    if random.random() < 0.6 and student["weak_kps"]:
        return random.choice(student["weak_kps"])
    return random.choice([kp["id"] for kp in PY_KNOWLEDGE_POINTS])


def seed_py_knowledge_points() -> int:
    inserted = 0
    with SessionLocal() as db:
        for kp in PY_KNOWLEDGE_POINTS:
            try:
                row = db.get(models.KnowledgePointRecord, kp["id"])
                if row is None:
                    existing_names = {
                        n for (n,) in db.query(models.KnowledgePointRecord.name)
                        .filter(models.KnowledgePointRecord.course == PY_COURSE)
                        .all()
                    }
                    final_name = kp["name"]
                    if final_name in existing_names:
                        final_name = f"{kp['name']} · v2"
                    db.add(models.KnowledgePointRecord(
                        id=kp["id"],
                        course=PY_COURSE,
                        name=final_name,
                        description=kp["description"],
                        metadata_data={"bloom": kp["bloom"], "difficulty": kp["difficulty"]},
                    ))
                    inserted += 1
                else:
                    row.name = kp["name"]
                    row.description = kp["description"]
                    row.course = PY_COURSE
                    row.metadata_data = {"bloom": kp["bloom"], "difficulty": kp["difficulty"]}
                db.commit()
            except Exception:
                db.rollback()
                continue
    return inserted


def seed_py_knowledge_relations() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing = {
            (r.source_id, r.target_id, r.relation_type)
            for r in db.query(models.KnowledgeRelationRecord).all()
        }
        for rel in PY_KNOWLEDGE_RELATIONS:
            key = (rel["source"], rel["target"], rel["type"])
            if key in existing:
                continue
            src = db.get(models.KnowledgePointRecord, rel["source"])
            tgt = db.get(models.KnowledgePointRecord, rel["target"])
            if not src or not tgt:
                continue
            db.add(models.KnowledgeRelationRecord(
                source_id=rel["source"],
                target_id=rel["target"],
                relation_type=rel["type"],
                weight=rel["weight"],
                metadata_data={},
            ))
            inserted += 1
        db.commit()
    return inserted


def seed_py_bkt_states() -> int:
    inserted = 0
    with SessionLocal() as db:
        for s in PY_STUDENTS:
            for kp in PY_KNOWLEDGE_POINTS:
                existing = (
                    db.query(models.BktStateRecord)
                    .filter(
                        models.BktStateRecord.user_id == s["user_id"],
                        models.BktStateRecord.knowledge_point_id == kp["id"],
                    )
                    .first()
                )
                if existing is not None:
                    continue
                bias = s["mastery_bias"]
                if kp["id"] in s["focus_kps"]:
                    p_learned = _clamp(bias + random.uniform(0.10, 0.20))
                elif kp["id"] in s["weak_kps"]:
                    p_learned = _clamp(bias - random.uniform(0.20, 0.30))
                else:
                    p_learned = _clamp(bias + random.uniform(-0.10, 0.10))
                p_learned = _clamp(p_learned - (kp["difficulty"] - 2) * 0.03)
                p_transit = round(random.uniform(0.08, 0.15), 3)
                p_slip = round(random.uniform(0.05, 0.15), 3)
                p_guess = round(random.uniform(0.15, 0.25), 3)
                history_len = random.randint(5, 10)
                history = []
                for i in range(history_len):
                    ts = _NOW - (history_len - i) * random.uniform(0.5, 3) * _DAY
                    correct = random.random() < p_learned
                    history.append({"ts": ts, "correct": bool(correct)})
                db.add(models.BktStateRecord(
                    user_id=s["user_id"],
                    knowledge_point_id=kp["id"],
                    p_learned=round(p_learned, 4),
                    p_transit=p_transit,
                    p_slip=p_slip,
                    p_guess=p_guess,
                    history=history,
                    updated_at=_NOW,
                ))
                inserted += 1
        db.commit()
    return inserted


def seed_py_mistakes() -> int:
    inserted = 0
    seq_per_student: Dict[str, int] = {s["user_id"]: 0 for s in PY_STUDENTS}
    with SessionLocal() as db:
        existing_ids = {m.id for m in db.query(models.MistakeRecord.id).all()}
        for s in PY_STUDENTS:
            tier = s["tier"]
            lo, hi = _mistake_count_for_tier(tier)
            n_mistakes = random.randint(lo, hi)
            for _ in range(n_mistakes):
                seq_per_student[s["user_id"]] += 1
                seq = seq_per_student[s["user_id"]]
                mid = f"mistake_py_{s['user_id'].replace('demo-student-', '')}_{seq:03d}"
                if mid in existing_ids:
                    continue
                kp_id = _py_pick_kp(s)
                tpl = random.choice(PY_MISTAKE_TEMPLATES.get(kp_id, [
                    {"q": f"关于 {kp_id} 的概念辨析题", "sa": "我不太确定", "ca": "需要结合具体定义回答"},
                ]))
                error_type = random.choices(ERROR_TYPES, weights=[25, 15, 20, 10, 10, 8, 7, 5])[0]
                days_ago = random.uniform(0.5, 30)
                created_at = _NOW - days_ago * _DAY
                is_resolved = random.random() < 0.30
                resolved_at = (created_at + random.uniform(3, 10) * _DAY) if is_resolved else None
                db.add(models.MistakeRecord(
                    id=mid,
                    user_id=s["user_id"],
                    knowledge_point_id=kp_id,
                    question_data={
                        "question": tpl["q"],
                        "student_answer": tpl["sa"],
                        "correct_answer": tpl["ca"],
                    },
                    error_type=error_type,
                    analysis=f"错因分析：该生属于 {tier} 层级，在 Python {kp_id} 上存在 {error_type}。建议复习相关知识点并完成配套练习。",
                    created_at=created_at,
                    resolved_at=resolved_at,
                ))
                inserted += 1
        db.commit()
    return inserted


def seed_py_assessments() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing = set()
        for uid, rt, topic, ts in db.query(
            models.AssessmentRecord.user_id,
            models.AssessmentRecord.record_type,
            models.AssessmentRecord.topic,
            models.AssessmentRecord.timestamp,
        ).all():
            existing.add((uid, rt, topic, round(float(ts), 1)))
        for s in PY_STUDENTS:
            n = _assessment_count_for_tier(s["tier"])
            added = 0
            attempts = 0
            while added < n and attempts < n * 3:
                attempts += 1
                kp_id = _py_pick_kp(s)
                record_type = random.choices(
                    ["quiz", "question", "resource_view", "activity"],
                    weights=[40, 25, 25, 10],
                )[0]
                score_low, score_high = _score_for_tier(s["tier"])
                if record_type in ("quiz", "question"):
                    score = round(random.uniform(score_low, score_high), 3)
                else:
                    score = None
                days_ago = random.uniform(0.1, 30)
                timestamp = _NOW - days_ago * _DAY - random.uniform(0, _DAY)
                key = (s["user_id"], record_type, kp_id, round(timestamp, 1))
                if key in existing:
                    continue
                existing.add(key)
                duration = round(random.uniform(60, 1800), 1)
                kp_meta = next((k for k in PY_KNOWLEDGE_POINTS if k["id"] == kp_id), None)
                bloom = kp_meta["bloom"] if kp_meta else "Apply"
                db.add(models.AssessmentRecord(
                    user_id=s["user_id"],
                    record_type=record_type,
                    score=score,
                    topic=kp_id,
                    duration=duration,
                    metadata_data={"kp_id": kp_id, "bloom": bloom, "course": PY_COURSE},
                    timestamp=timestamp,
                ))
                inserted += 1
                added += 1
        db.commit()
    return inserted


def seed_py_learning_paths() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing_ids = {p.id for p in db.query(models.LearningPathRecord.id).all()}
        for s in PY_STUDENTS:
            tier = s["tier"]
            pid = f"seed-py-path-{s['user_id']}"
            if pid in existing_ids:
                continue
            stages = [
                {"title": "Python 语言基础", "kps": ["py_overview", "py_variables_types", "py_operators"]},
                {"title": "控制流与函数", "kps": ["py_control_flow", "py_functions"]},
                {"title": "数据结构", "kps": ["py_lists", "py_dicts", "py_tuples_sets", "py_strings"]},
                {"title": "collections 与 OOP 入门", "kps": ["py_collections", "py_classes", "py_inheritance"]},
                {"title": "OOP 进阶", "kps": ["py_encapsulation", "py_magic_methods", "py_context_manager"]},
                {"title": "文件 IO 与异常处理", "kps": ["py_file_io", "py_pathlib", "py_csv_json", "py_exceptions", "py_custom_exceptions"]},
                {"title": "进阶特性与项目实战", "kps": ["py_stdlib", "py_iterators_generators", "py_decorators", "py_project"]},
            ]
            if tier == "weak":
                stages = stages[:4]
            elif tier == "medium":
                stages = stages[:5]
            prog_lo, prog_hi = _progress_for_tier(tier)
            progress = round(random.uniform(prog_lo, prog_hi), 1)
            current_stage = int(progress / 100 * len(stages))
            if current_stage >= len(stages):
                current_stage = len(stages) - 1
            db.add(models.LearningPathRecord(
                id=pid,
                user_id=s["user_id"],
                title=f"{s['nickname']} · Python 学习路径（{ {'excellent':'拔高','good':'进阶','medium':'稳进','weak':'补强'}[tier] }版）",
                stages=stages,
                current_stage=current_stage,
                progress=progress,
                metadata_data={"recommended_by": "system", "tier": tier, "course": PY_COURSE, "generated_at": _NOW},
                created_at=_NOW - random.uniform(1, 30) * _DAY,
                updated_at=_NOW,
            ))
            inserted += 1
        db.commit()
    return inserted


def _py_pick_tags(kps: List[str], kind: str) -> List[str]:
    base = []
    for kp_id in kps[:2]:
        kp = next((k for k in PY_KNOWLEDGE_POINTS if k["id"] == kp_id), None)
        if kp:
            base.append(kp["name"])
    if kind in ("document", "ppt"):
        base.append("讲义")
    elif kind == "quiz":
        base.append("练习")
    elif kind == "code":
        base.append("代码")
    elif kind == "mindmap":
        base.append("思维导图")
    return list(dict.fromkeys(base))[:5]


def seed_py_teacher_resources() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing_ids = {r.id for r in db.query(models.ResourceRecord.id).all()}
        course_resources = [
            ("Python 基础语法精讲", "document", ["py_overview", "py_variables_types", "py_operators"]),
            ("控制流与函数详解", "document", ["py_control_flow", "py_functions"]),
            ("列表与字典深入", "document", ["py_lists", "py_dicts"]),
            ("元组、集合与字符串", "document", ["py_tuples_sets", "py_strings"]),
            ("collections 高级容器指南", "document", ["py_collections"]),
            ("面向对象编程讲义", "document", ["py_classes", "py_inheritance"]),
            ("封装与 property 教程", "document", ["py_encapsulation"]),
            ("魔术方法完全指南", "document", ["py_magic_methods"]),
            ("上下文管理器与 with 语句", "document", ["py_context_manager"]),
            ("文件读写最佳实践", "document", ["py_file_io", "py_pathlib"]),
            ("CSV 与 JSON 数据处理", "document", ["py_csv_json"]),
            ("异常处理与自定义异常", "document", ["py_exceptions", "py_custom_exceptions"]),
            ("常用标准库速查", "document", ["py_stdlib"]),
            ("迭代器与生成器原理", "document", ["py_iterators_generators"]),
            ("装饰器从入门到精通", "document", ["py_decorators"]),
            ("Python 基础配套练习", "quiz", ["py_variables_types", "py_control_flow", "py_functions"]),
            ("数据结构综合题库", "quiz", ["py_lists", "py_dicts", "py_tuples_sets"]),
            ("OOP 概念辨析题", "quiz", ["py_classes", "py_inheritance", "py_encapsulation"]),
            ("进阶特性测验", "quiz", ["py_iterators_generators", "py_decorators"]),
            ("Python 综合项目案例", "quiz", ["py_project", "py_file_io", "py_exceptions"]),
        ]
        for idx, (title, kind, kps) in enumerate(course_resources, start=1):
            rid = f"teacher_res_py_course_{idx:03d}"
            if rid in existing_ids:
                continue
            db.add(models.ResourceRecord(
                id=rid,
                user_id="",
                type=kind,
                title=title,
                content=_resource_content(kind, title, kps),
                content_type="markdown",
                agent_name="teacher",
                metadata_data={
                    "course": PY_COURSE, "scope": "course", "status": "published",
                    "created_by": "teacher", "target_user_ids": [], "kp_ids": kps,
                },
                tags=_py_pick_tags(kps, kind),
                created_at=_NOW - random.uniform(1, 14) * _DAY,
            ))
            inserted += 1

        student_resources = [
            ("杜同学专属：装饰器强化包", "document", "demo-student-1", ["py_decorators", "py_iterators_generators"]),
            ("杜同学专属：CSV/JSON 补强", "quiz", "demo-student-1", ["py_csv_json"]),
            ("小强专属：OOP 速成", "document", "demo-student-5", ["py_classes", "py_inheritance"]),
            ("小强专属：函数练习", "code", "demo-student-5", ["py_functions"]),
            ("小杨专属：基础入门路径", "ppt", "demo-student-6", ["py_variables_types", "py_control_flow"]),
            ("小杨专属：类概念入门", "document", "demo-student-6", ["py_classes"]),
            ("小何专属：基础补强包", "document", "demo-student-18", ["py_variables_types", "py_control_flow"]),
            ("小高专属：零基础导论", "document", "demo-student-20", ["py_overview", "py_variables_types"]),
            ("小高专属：列表练习", "code", "demo-student-20", ["py_lists"]),
            ("小孙专属：OOP 综合讲义", "document", "demo-student-13", ["py_classes", "py_magic_methods"]),
        ]
        for idx, (title, kind, uid, kps) in enumerate(student_resources, start=1):
            rid = f"teacher_res_py_student_{idx:03d}"
            if rid in existing_ids:
                continue
            db.add(models.ResourceRecord(
                id=rid,
                user_id=uid,
                type=kind,
                title=title,
                content=_resource_content(kind, title, kps),
                content_type="markdown",
                agent_name="teacher",
                metadata_data={
                    "course": PY_COURSE, "scope": "student", "status": "published",
                    "created_by": "teacher", "target_user_ids": [uid], "kp_ids": kps,
                },
                tags=_py_pick_tags(kps, kind) + ["个性化"],
                created_at=_NOW - random.uniform(1, 14) * _DAY,
            ))
            inserted += 1

        draft_resources = [
            ("草稿：装饰器高级模式", "document", ["py_decorators"]),
            ("草稿：Python 项目模板", "code", ["py_project"]),
            ("草稿：异常处理最佳实践 V2", "document", ["py_exceptions", "py_custom_exceptions"]),
            ("草稿：生成器思维导图", "mindmap", ["py_iterators_generators"]),
            ("草稿：OOP 综合测验", "quiz", ["py_classes", "py_inheritance", "py_encapsulation"]),
        ]
        for idx, (title, kind, kps) in enumerate(draft_resources, start=1):
            rid = f"teacher_res_py_draft_{idx:03d}"
            if rid in existing_ids:
                continue
            db.add(models.ResourceRecord(
                id=rid,
                user_id="",
                type=kind,
                title=title,
                content=_resource_content(kind, title, kps),
                content_type="markdown",
                agent_name="teacher",
                metadata_data={
                    "course": PY_COURSE, "scope": "course", "status": "draft",
                    "created_by": "teacher", "target_user_ids": [], "kp_ids": kps,
                },
                tags=_py_pick_tags(kps, kind) + ["草稿"],
                created_at=_NOW - random.uniform(0.5, 7) * _DAY,
            ))
            inserted += 1
        db.commit()
    return inserted


def seed_py_sm2_schedules() -> int:
    inserted = 0
    with SessionLocal() as db:
        for s in PY_STUDENTS:
            rows = (
                db.query(models.BktStateRecord)
                .filter(
                    models.BktStateRecord.user_id == s["user_id"],
                    models.BktStateRecord.knowledge_point_id.in_([kp["id"] for kp in PY_KNOWLEDGE_POINTS]),
                    models.BktStateRecord.p_learned > 0.6,
                )
                .order_by(models.BktStateRecord.p_learned.desc())
                .limit(5)
                .all()
            )
            existing_items = {
                it.item_id
                for it in db.query(models.Sm2ScheduleRecord)
                .filter(models.Sm2ScheduleRecord.user_id == s["user_id"])
                .all()
            }
            for r in rows[:5]:
                if r.knowledge_point_id in existing_items:
                    continue
                rep = random.randint(0, 3)
                interval = random.choice([1, 2, 3, 5, 7, 10, 14])
                easiness = round(random.uniform(2.0, 2.8), 2)
                due = _NOW + interval * _DAY
                db.add(models.Sm2ScheduleRecord(
                    user_id=s["user_id"],
                    item_id=r.knowledge_point_id,
                    item_type="knowledge_point",
                    repetitions=rep,
                    interval_days=interval,
                    easiness=easiness,
                    due_at=due,
                    updated_at=_NOW,
                ))
                inserted += 1
        db.commit()
    return inserted


def seed_py_group_chat() -> int:
    inserted = 0
    with SessionLocal() as db:
        existing_msg_ids = {m.id for m in db.query(models.GroupChatMessageRecord.id).all()}
        rep_students = [
            "demo-student-1", "demo-student-7",
            "demo-student-4", "demo-student-10",
            "demo-student-5", "demo-student-15",
            "demo-student-6", "demo-student-20",
        ]
        text_templates = [
            "老师，Python 列表推导式和 for 循环到底什么时候用哪个？",
            "我今天写了个类，继承后 super().__init__() 报错了，能帮我看一下吗？",
            "装饰器看了三遍还是没理解闭包和它的关系，能再讲一下吗？",
            "with open 和直接 open 有什么区别？书上说要用 with 但没说为什么。",
            "我的字典在遍历时修改了键，报 RuntimeError，这是什么原理？",
            "请问 Python 多继承的 MRO 是怎么计算的？菱形继承好绕。",
            "生成器 yield 之后还能 send 值进去？这个机制太绕了。",
            "try-except-else 里的 else 到底什么时候执行？和 finally 有什么区别？",
        ]
        teacher_templates = [
            "本周 Python 作业：完成 OOP 章节练习，重点理解 super() 和 MRO。",
            "@杜同学 你的装饰器作业完成得很出色，请准备一个 3 分钟分享。",
            "本周新增 5 道生成器与迭代器综合题，建议错题数 > 5 的同学优先完成。",
            "Python 学习路径已更新，请根据自身情况选择合适阶段。",
        ]
        agent_templates = [
            "我注意到你在列表切片上错了 2 题，可以从左闭右开区间这个角度复盘。",
            "基于你最近的练习情况，建议先巩固函数与控制流，再进入 OOP 章节。",
            "我已为你生成 Python 个性化学习路径，包含 7 个阶段，可在「学习路径」页查看。",
            "你提的装饰器问题很好，关键是理解高阶函数和闭包：装饰器接收函数返回新函数。",
        ]
        seq = 0
        for uid in rep_students:
            room_id = f"{PY_COURSE}:{uid}"
            nickname = next(s["nickname"] for s in PY_STUDENTS if s["user_id"] == uid)
            n_msgs = random.randint(6, 8)
            for i in range(n_msgs):
                seq += 1
                msg_id = f"gmsg_py_{uid.replace('demo-student-', '')}_{i:02d}"
                if msg_id in existing_msg_ids:
                    continue
                mtype = random.choices(
                    ["text", "teacher_message", "agent_reply", "resource_card", "path_card", "system_notice"],
                    weights=[40, 15, 20, 10, 5, 10],
                )[0]
                if mtype == "text":
                    sender_id, sender_name, sender_role = uid, nickname, "student"
                    content = random.choice(text_templates)
                    payload = {}
                elif mtype == "teacher_message":
                    sender_id, sender_name, sender_role = _TEACHER_ID, _TEACHER_NAME, "teacher"
                    content = random.choice(teacher_templates)
                    payload = {}
                elif mtype == "agent_reply":
                    sender_id, sender_name, sender_role = "tutor_agent", "猫头讲师", "agent"
                    content = random.choice(agent_templates)
                    payload = {}
                elif mtype == "resource_card":
                    sender_id, sender_name, sender_role = _TEACHER_ID, _TEACHER_NAME, "teacher"
                    rid = f"teacher_res_py_course_{random.randint(1, 20):03d}"
                    content = "为你推荐一份 Python 课程资源："
                    payload = {"resource_id": rid, "kind": "resource_card"}
                elif mtype == "path_card":
                    sender_id, sender_name, sender_role = "tutor_agent", "猫头讲师", "agent"
                    content = "已为你更新 Python 学习路径："
                    payload = {"path_id": f"seed-py-path-{uid}", "kind": "path_card"}
                else:
                    sender_id, sender_name, sender_role = "system", "系统", "system"
                    content = random.choice([
                        "本周 Python 班级活跃度排名已更新，请查看班级看板。",
                        "新增 3 道 Python 装饰器章节配套练习。",
                        "Python 学习路径已根据你的错题自动调整。",
                    ])
                    payload = {}
                ts = _NOW - random.uniform(0.1, 7) * _DAY
                db.add(models.GroupChatMessageRecord(
                    id=msg_id,
                    room_id=room_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    sender_role=sender_role,
                    content=content,
                    message_type=mtype,
                    payload=payload,
                    created_at=ts,
                ))
                inserted += 1
        db.commit()
    return inserted


# ================================================================
# 入口
# ================================================================
def seed_du_student_demo() -> int:
    """补齐默认学生的可演示学习闭环，并统一展示名。

    该步骤幂等：固定 external_id 的近期活动只会写入一次；已有画像、
    路径和群聊只做定向修正，不会清空用户产生的数据。
    """
    changed = 0
    now = time.time()
    user_id = "demo-student-1"
    with SessionLocal() as db:
        profile = db.get(models.ProfileRecord, user_id)
        if profile:
            data = dict(profile.profile_data or {})
            if data.get("display_name") != "杜同学" or data.get("nickname") != "杜同学":
                data.update({"display_name": "杜同学", "nickname": "杜同学"})
                profile.profile_data = data
                profile.version = int(profile.version or 0) + 1
                profile.updated_at = now
                changed += 1

        path_specs = {
            "seed-path-demo-student-1": {
                "course": COURSE,
                "title": "杜同学 · 人工智能进阶学习路径",
                "today_tasks": [
                    {"id": "du-ai-review", "title": "复习「概率论与数理统计」", "description": "完成 3 道错题复盘", "kp_id": "probability_statistics", "estimated_minutes": 12, "type": "优先复习", "route": "/mistakes"},
                    {"id": "du-ai-learn", "title": "学习「强化学习」", "description": "阅读概念讲解并完成理解检查", "kp_id": "reinforcement_learning", "estimated_minutes": 15, "type": "继续学习", "route": "/graph?kp=reinforcement_learning"},
                    {"id": "du-ai-practice", "title": "练习「多智能体系统」", "description": "完成 5 道分层练习", "kp_id": "multi_agent_systems", "estimated_minutes": 10, "type": "完成练习", "route": "/chat?agent=quiz"},
                ],
            },
            "seed-py-path-demo-student-1": {
                "course": PY_COURSE,
                "title": "杜同学 · Python 程序设计进阶路径",
                "today_tasks": [
                    {"id": "du-py-review", "title": "复习「装饰器」", "description": "回顾闭包与函数对象", "kp_id": "py_decorators", "estimated_minutes": 12, "type": "优先复习", "route": "/mistakes"},
                    {"id": "du-py-learn", "title": "学习「迭代器与生成器」", "description": "完成代码示例与理解检查", "kp_id": "py_iterators_generators", "estimated_minutes": 15, "type": "继续学习", "route": "/graph?kp=py_iterators_generators"},
                    {"id": "du-py-practice", "title": "练习「CSV 与 JSON」", "description": "完成一个数据读写小任务", "kp_id": "py_csv_json", "estimated_minutes": 10, "type": "完成练习", "route": "/playground?topic=py_csv_json"},
                ],
            },
        }
        for path_id, spec in path_specs.items():
            path = db.get(models.LearningPathRecord, path_id)
            if not path:
                continue
            metadata = dict(path.metadata_data or {})
            metadata.update({
                "course": spec["course"],
                "today_tasks": spec["today_tasks"],
                "demo_profile": "杜同学",
            })
            path.title = spec["title"]
            path.metadata_data = metadata
            path.updated_at = now
            changed += 1

        recent_activities = [
            ("du-demo-ai-1", "quiz", "multi_agent_systems", 86, 22, 0.01),
            ("du-demo-ai-2", "learning", "reinforcement_learning", 82, 28, 0.04),
            ("du-demo-ai-3", "review", "probability_statistics", 78, 18, 0.08),
            ("du-demo-ai-4", "task_completed", "attention_mechanism", 90, 24, 0.12),
            ("du-demo-py-1", "practice", "py_decorators", 84, 20, 0.16),
            ("du-demo-py-2", "learning", "py_iterators_generators", 88, 26, 0.20),
        ]
        existing_activity_rows = {
            row.external_id: row for row in db.query(models.AssessmentRecord)
            .filter(models.AssessmentRecord.external_id.like("du-demo-%"))
            .all()
        }
        for external_id, kind, topic, score, duration, days_ago in recent_activities:
            existing = existing_activity_rows.get(external_id)
            if existing:
                existing.record_type = kind
                existing.topic = topic
                existing.score = score
                existing.duration = duration
                existing.timestamp = now - days_ago * _DAY
                existing.metadata_data = {"kp_id": topic, "duration_unit": "minutes", "seed": "du_student_demo"}
                changed += 1
                continue
            db.add(models.AssessmentRecord(
                external_id=external_id,
                user_id=user_id,
                record_type=kind,
                score=score,
                topic=topic,
                duration=duration,
                metadata_data={"kp_id": topic, "duration_unit": "minutes", "seed": "du_student_demo"},
                timestamp=now - days_ago * _DAY,
            ))
            changed += 1

        game = db.get(models.GamificationProfileRecord, user_id)
        if game:
            game.streak_days = max(int(game.streak_days or 0), 5)
            game.xp = max(int(game.xp or 0), 460)
            game.level = max(int(game.level or 1), 4)
            game.updated_at = now
            changed += 1

        for message in db.query(models.GroupChatMessageRecord).filter(
            models.GroupChatMessageRecord.sender_id == user_id,
        ).all():
            if message.sender_name != "杜同学":
                message.sender_name = "杜同学"
                changed += 1

        for message in db.query(models.GroupChatMessageRecord).filter(
            models.GroupChatMessageRecord.content.contains("@小明"),
        ).all():
            message.content = message.content.replace("@小明", "@杜同学")
            changed += 1

        for resource in db.query(models.ResourceRecord).filter(
            models.ResourceRecord.user_id == user_id,
            models.ResourceRecord.title.like("小明专属%"),
        ).all():
            resource.title = resource.title.replace("小明专属", "杜同学专属", 1)
            changed += 1

        db.commit()
    return changed


def seed_all(verbose: bool = True) -> Dict[str, int]:
    """执行所有 seed_*；返回各表插入条数。"""
    random.seed(SEED)
    init_db()  # 确保表已建
    results: Dict[str, int] = {}
    seeders = [
        ("knowledge_points", seed_knowledge_points),
        ("knowledge_relations", seed_knowledge_relations),
        ("profiles", seed_profiles),
        ("bkt_states", seed_bkt_states),
        ("mistakes", seed_mistakes),
        ("assessments", seed_assessments),
        ("learning_paths", seed_learning_paths),
        ("teacher_resources", seed_teacher_resources),
        ("gamification", seed_gamification),
        ("sm2_schedules", seed_sm2_schedules),
        ("group_chat", seed_group_chat_messages),
        # Python 程序设计课
        ("py_knowledge_points", seed_py_knowledge_points),
        ("py_knowledge_relations", seed_py_knowledge_relations),
        ("py_bkt_states", seed_py_bkt_states),
        ("py_mistakes", seed_py_mistakes),
        ("py_assessments", seed_py_assessments),
        ("py_learning_paths", seed_py_learning_paths),
        ("py_teacher_resources", seed_py_teacher_resources),
        ("py_sm2_schedules", seed_py_sm2_schedules),
        ("py_group_chat", seed_py_group_chat),
        ("du_student_demo", seed_du_student_demo),
    ]
    for name, fn in seeders:
        try:
            n = fn()
        except Exception as exc:  # noqa: BLE001
            n = -1
            if verbose:
                print(f"[seed:{name}] FAILED: {exc!r}")
        results[name] = n
        if verbose:
            print(f"[seed:{name}] inserted {n} rows")
    if verbose:
        total = sum(v for v in results.values() if v > 0)
        print(f"\n[seed_all] total inserted ≈ {total}")
    return results


if __name__ == "__main__":
    seed_all(verbose=True)
