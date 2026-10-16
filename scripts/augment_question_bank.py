#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资料库完整性补全 - 题库结构统一脚本（v1）

依据：
    交接清单/22-A-项目全面评审报告-前后端与资料库-0711.md · 六.3 P1 题库结构

执行内容：
    1. 合并 choice + fill + programming 三类题到统一 schema（带 bloom_6x3）
    2. 补 30+ 道 true_false 判断题（覆盖 28 个 KP）
    3. 输出到 data/question_bank_consolidated.json（不覆盖原文件）

schema 统一原则：
    - choice: 保留 options + answer
    - fill: 保留 stem + answer (expected_keywords 折入 answer 后备字段)
    - programming: 保留 stem + answer + test_harness
    - true_false: options=["对","错"] + answer="A"|"B"

幂等性：
    - 通过 hash(content) 计算 stable_id，确保重跑不重复
    - --dry-run 打印计划，--apply 写文件
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_FILE = DATA_DIR / "question_bank_consolidated.json"

KP_NAMES: Dict[str, str] = {
    "python_basics": "Python 基础编程",
    "data_structures": "数据结构与算法",
    "linear_algebra": "线性代数（机器学习）",
    "probability_statistics": "概率与统计（机器学习）",
    "ml_basics": "机器学习基础",
    "supervised_learning": "监督学习方法",
    "unsupervised_learning": "无监督学习方法",
    "decision_trees": "决策树与集成",
    "svm": "支持向量机",
    "neural_networks": "神经网络基础",
    "backpropagation": "反向传播算法",
    "mlp": "多层感知机（MLP）",
    "cnn": "卷积神经网络（视觉）",
    "rnn": "循环神经网络（序列）",
    "lstm": "LSTM 与 GRU",
    "attention_mechanism": "注意力机制",
    "transformer": "Transformer 架构",
    "nlp_basics": "NLP 基础任务",
    "rag": "检索增强生成（RAG）",
    "reinforcement_learning": "强化学习进阶",
    "ai_project_practice": "AI 项目实战",
    "multi_agent_systems": "多智能体系统",
    "multimodal_llm": "多模态大模型",
    "ai_agent": "AI Agent 规划与工具",
    "mcp_protocol": "MCP 协议",
    "learning_science": "学习科学理论",
    "cognitive_diagnosis": "认知诊断模型",
    "data_visualization": "数据可视化",
}

BLOOM_LEVELS = ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]


def _stable_id(prefix: str, payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:10]}"


# ================================================================
# 加载 + 标准化
# ================================================================
def _load_choice(path: Path) -> List[Dict[str, Any]]:
    d = json.loads(path.read_text(encoding="utf-8"))
    items = d.get("questions", d if isinstance(d, list) else [])
    out: List[Dict[str, Any]] = []
    for q in items:
        q = dict(q)
        q.setdefault("type", "multiple_choice")
        if "bloom_6x3" not in q:
            q["bloom_6x3"] = _guess_bloom6x3(q)
        out.append(q)
    return out


def _load_fill(path: Path) -> List[Dict[str, Any]]:
    d = json.loads(path.read_text(encoding="utf-8"))
    items = d.get("questions", d if isinstance(d, list) else [])
    out: List[Dict[str, Any]] = []
    for q in items:
        q = dict(q)
        q["type"] = "fill_blank"
        # 标准化 answer 字段
        if "answer" not in q and "expected_keywords" in q:
            q["answer"] = q["expected_keywords"][0] if q["expected_keywords"] else ""
        # 标准化 options
        q.setdefault("options", [])
        # bloom_6x3
        q.setdefault("bloom_6x3", _guess_bloom6x3(q, default_sub="recognizing",
                                                 default_knowledge="factual"))
        out.append(q)
    return out


def _load_programming(path: Path) -> List[Dict[str, Any]]:
    d = json.loads(path.read_text(encoding="utf-8"))
    items = d.get("questions", d if isinstance(d, list) else [])
    out: List[Dict[str, Any]] = []
    for q in items:
        q = dict(q)
        q["type"] = "programming"
        q.setdefault("options", [])
        if "answer" not in q and "expected_keywords" in q:
            q["answer"] = ", ".join(q["expected_keywords"])
        q.setdefault("bloom_6x3", _guess_bloom6x3(q, default_level="Apply",
                                                  default_sub="executing",
                                                  default_knowledge="procedural"))
        out.append(q)
    return out


def _guess_bloom6x3(q: Dict[str, Any], default_level: str = "Remember",
                   default_sub: str = "recalling",
                   default_knowledge: str = "factual") -> Dict[str, Any]:
    bloom = q.get("bloom") or default_level
    return {
        "level": bloom.lower(),
        "sub_level": default_sub,
        "knowledge_dimension": default_knowledge,
        "method": "schema_normalized",
        "score": 1,
    }


# ================================================================
# 判断题生成
# ================================================================
TF_TEMPLATES: List[Tuple[str, str, bool, str]] = [
    # (kp_id, statement, is_true, explanation)
    ("python_basics",
     "Python 中字符串是不可变类型，调用字符串方法不会修改原字符串而是返回新对象。",
     True, "Python 字符串是不可变类型；'hello'.replace('l','L') 返回新字符串，原串不变。"),
    ("python_basics",
     "Python 的列表与字典都是不可变类型，无法在原位修改。",
     False, "列表（list）和字典（dict）都是可变类型；元组（tuple）才是不可变类型。"),
    ("data_structures",
     "哈希表在平均情况下查找、插入、删除的时间复杂度都是 O(1)。",
     True, "在哈希冲突均匀分布时，dict/set 的平均复杂度为 O(1)；最坏 O(n)。"),
    ("data_structures",
     "栈是 FIFO（先进先出）的数据结构。",
     False, "栈是 LIFO（后进先出）；FIFO 是队列（queue）。"),
    ("linear_algebra",
     "矩阵的秩等于其行向量组的最大线性无关组的大小。",
     True, "矩阵的行秩与列秩相等，等于行/列向量的最大线性无关组大小。"),
    ("linear_algebra",
     "任何方阵都存在特征值与特征向量。",
     True, "在复数域上任何 n×n 方阵都有 n 个特征值（计重数）。"),
    ("probability_statistics",
     "若两个事件独立，则它们一定不相关。",
     True, "独立 ⇒ 不相关；反之不一定成立（不相关只说明协方差为零）。"),
    ("probability_statistics",
     "贝叶斯公式的先验概率可以在观察到证据后被更新为后验概率。",
     True, "贝叶斯推断的核心就是先验 → 后验的更新过程。"),
    ("ml_basics",
     "训练集准确率 99%、测试集准确率 60% 通常意味着模型存在过拟合。",
     True, "训练表现远好于测试表现是过拟合的典型特征。"),
    ("ml_basics",
     "交叉验证可以完全消除模型选择带来的偏差。",
     False, "交叉验证只能估计泛化误差，不能消除选择偏差，仍需谨慎设计实验。"),
    ("supervised_learning",
     "逻辑回归是用于二分类问题的线性模型，输出经过 sigmoid 函数映射到 0-1 区间。",
     True, "逻辑回归是广义线性模型，sigmoid 把线性输出压缩为概率。"),
    ("supervised_learning",
     "KNN 算法对特征尺度不敏感。",
     False, "KNN 基于距离，特征尺度不一致会导致量纲大的特征主导结果，需要归一化。"),
    ("unsupervised_learning",
     "K-Means 聚类需要预先指定簇的数量 K。",
     True, "K-Means 必须先给定 K；肘部法则或轮廓系数可辅助选择。"),
    ("unsupervised_learning",
     "PCA 是一种有监督的降维方法。",
     False, "PCA 是无监督降维，不使用标签信息。"),
    ("decision_trees",
     "信息增益越大，说明该特征对分类的区分度越高。",
     True, "信息增益反映特征对降低标签不确定性的贡献。"),
    ("decision_trees",
     "随机森林比单棵决策树更容易过拟合。",
     False, "随机森林通过 bagging 与特征随机性降低方差，更不容易过拟合。"),
    ("svm",
     "线性可分支持向量机的最优分类面只与支持向量有关，与其他样本无关。",
     True, "SVM 的对偶问题中只有支持向量的拉格朗日乘子非零，最优解由它们决定。"),
    ("svm",
     "核函数的引入会让 SVM 只能处理线性问题。",
     False, "核函数让 SVM 在高维（甚至无限维）特征空间隐式线性可分，扩展到非线性问题。"),
    ("neural_networks",
     "ReLU 激活函数的输出范围是 [0, +∞)。",
     True, "ReLU(x) = max(0, x)，非负无上界。"),
    ("neural_networks",
     "Dropout 在训练和推理时都按相同概率随机丢弃神经元。",
     False, "Dropout 只在训练时随机失活，推理时全部使用并按比例缩放。"),
    ("backpropagation",
     "反向传播算法是链式求导法则在计算图上的应用。",
     True, "BP 实质是按计算图反向传播梯度，依赖链式法则。"),
    ("backpropagation",
     "梯度下降的学习率越大，模型一定收敛得越快。",
     False, "学习率过大会导致震荡甚至发散；需要合适值或调度策略。"),
    ("cnn",
     "卷积层通过权值共享显著减少参数数量。",
     True, "同一卷积核在整张输入上滑动，参数只与核大小有关，与输入尺寸无关。"),
    ("cnn",
     "池化层包含可学习参数。",
     False, "最大池化/平均池化没有可学习参数；只有卷积和全连接有参数。"),
    ("rnn",
     "RNN 的隐藏状态在每个时间步都会被更新。",
     True, "RNN 的核心是隐藏状态 h_t = f(h_{t-1}, x_t)，逐时间步更新。"),
    ("rnn",
     "LSTM 通过门控机制有效缓解了 RNN 的梯度消失问题。",
     True, "LSTM 的输入/遗忘/输出门让梯度沿记忆细胞更稳定地传播。"),
    ("attention_mechanism",
     "自注意力机制中 Query、Key、Value 来自同一序列的线性投影。",
     True, "Self-Attention 的 Q/K/V 来自同一输入 X 的不同投影矩阵。"),
    ("attention_mechanism",
     "注意力权重之和必须等于 1。",
     True, "注意力权重经过 softmax，总和为 1，构成概率分布。"),
    ("transformer",
     "Transformer 完全抛弃了 RNN 和 CNN，仅依赖注意力机制建模序列。",
     True, "原论文中 encoder/decoder 都使用自注意力和前馈网络，无 RNN/CNN。"),
    ("transformer",
     "位置编码只与位置有关，与词本身的语义无关。",
     True, "原论文使用 sin/cos 固定位置编码；后续工作加入可学习位置编码。"),
    ("nlp_basics",
     "词嵌入（如 Word2Vec）可以将高维 one-hot 向量映射到低维稠密向量。",
     True, "Word2Vec/GloVe 把词表示为低维稠密实数向量，捕捉语义关系。"),
    ("nlp_basics",
     "中文分词只需要按空格切分即可。",
     False, "中文没有天然空格，需要 jieba 等分词工具；英文才按空格分词。"),
    ("rag",
     "RAG 系统的核心思想是把外部知识检索的结果与 LLM 生成过程结合。",
     True, "RAG = Retrieval-Augmented Generation，检索 + 生成双阶段。"),
    ("rag",
     "RAG 完全消除了大模型产生幻觉的可能。",
     False, "RAG 减少幻觉但不能完全消除，仍需引用约束、CoV 校验等机制。"),
    ("reinforcement_learning",
     "Q-Learning 是一种基于值函数的无模型强化学习算法。",
     True, "Q-Learning 不需要环境模型，直接学习状态-动作值 Q(s,a)。"),
    ("reinforcement_learning",
     "强化学习中的奖励信号必须是即时给与的。",
     False, "奖励可以是延迟的（sparse reward），学习需要信用分配机制。"),
    ("ai_agent",
     "ReAct 范式把推理（Reasoning）与行动（Acting）显式交替。",
     True, "ReAct = Thought → Action → Observation 循环。"),
    ("ai_agent",
     "AI Agent 不需要任何外部工具就能完成复杂任务。",
     False, "Agent 核心能力之一就是工具调用（tool use），常需检索/计算/代码执行。"),
    ("multi_agent_systems",
     "Multi-Agent Debate 通过多角色辩论可以提升答案的事实准确率。",
     True, "辩论+裁决机制在多 Agent 协作中常用于提升稳定性与准确性。"),
    ("multi_agent_systems",
     "多智能体系统的通信一定是同步阻塞的。",
     False, "通信可以是同步/异步、阻塞/非阻塞多种模式。"),
    ("mcp_protocol",
     "MCP（Model Context Protocol）规定了模型与外部工具/上下文交互的消息格式。",
     True, "MCP 是模型-工具间的标准化协议。"),
    ("mcp_protocol",
     "MCP 与 OpenAPI 规范完全等价，可以直接替换。",
     False, "MCP 面向模型上下文，OpenAPI 面向 REST API；用途不同。"),
    ("learning_science",
     "艾宾浩斯遗忘曲线表明学习后立即开始遗忘，初期遗忘最快。",
     True, "20 分钟内约遗忘 42%，1 天后约 66%，衰减逐步变缓。"),
    ("learning_science",
     "分散学习（间隔重复）效果通常不如集中学习。",
     False, "间隔重复被证明显著优于集中学习（massed practice）。"),
    ("cognitive_diagnosis",
     "BKT 模型用四个参数描述学生掌握与题目表现：p_init、p_transit、p_slip、p_guess。",
     True, "Bayesian Knowledge Tracing 的标准四参数定义。"),
    ("cognitive_diagnosis",
     "DINA 模型假设属性掌握与题目表现是确定性映射（加入 slip/guess 噪声）。",
     True, "DINA 是认知诊断中的非补偿性模型，参数 slip/guess 控制噪声。"),
    ("data_visualization",
     "柱状图适合比较分类之间的数值大小。",
     True, "柱状图最直观的用途是分类对比。"),
    ("data_visualization",
     "饼图是展示多类别比例变化趋势的最佳选择。",
     False, "饼图难以精确比较；趋势变化更适合折线图/堆叠柱状图。"),
    ("multimodal_llm",
     "多模态大模型可以同时处理图像、文本、音频等不同输入。",
     True, "多模态 LLM 统一表征多模态输入并跨模态推理。"),
    ("multimodal_llm",
     "图像描述（captioning）任务是多模态生成的经典应用。",
     True, "Image Captioning 是视觉-语言跨模态生成的代表任务。"),
    ("ai_project_practice",
     "AI 项目的端到端流程通常包括数据采集、清洗、建模、评估、部署与监控。",
     True, "这是 AI 工程化的标准闭环。"),
    ("ai_project_practice",
     "模型上线后不需要再监控与迭代。",
     False, "数据漂移、概念漂移等问题要求持续监控与重训。"),
]


def _build_true_false_questions() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, (kp_id, statement, is_true, expl) in enumerate(TF_TEMPLATES):
        correct = "A" if is_true else "B"
        q: Dict[str, Any] = {
            "id": _stable_id("tf", {"kp": kp_id, "stem": statement, "ans": correct}),
            "kp_id": kp_id,
            "kp_name": KP_NAMES.get(kp_id, kp_id),
            "bloom": "Remember" if idx % 3 == 0 else ("Understand" if idx % 3 == 1 else "Apply"),
            "type": "true_false",
            "stem": statement,
            "difficulty": 1 if idx % 4 == 0 else 2,
            "explanation": expl,
            "tags": [kp_id, "true_false", "judge"],
            "options": ["对", "错"],
            "answer": correct,
            "bloom_6x3": {
                "level": "remember",
                "sub_level": "recognizing",
                "knowledge_dimension": "factual",
                "method": "template_generated",
                "score": 1,
            },
            "source": "scripts/augment_question_bank.py",
            "created_at": time.time(),
        }
        out.append(q)
    return out


# ================================================================
# 主流程
# ================================================================
def collect_all() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen_ids: set = set()
    files: List[Tuple[str, Path, Any]] = [
        ("choice", DATA_DIR / "question_bank.json", _load_choice),
        ("choice_extra_0703", DATA_DIR / "question_bank_extra_0703.json",
         lambda p: _load_choice_or_list(p)),
        ("choice_extra_0704", DATA_DIR / "question_bank_extra_0704.json",
         lambda p: _load_choice_or_list(p)),
        ("choice_analytics_0708", DATA_DIR / "question_bank_analytics_0708.json",
         lambda p: _load_choice_or_list(p)),
        ("fill", DATA_DIR / "question_bank_fill.json", _load_fill),
        ("programming", DATA_DIR / "question_bank_programming.json", _load_programming),
        ("programming_extra_0704", DATA_DIR / "question_bank_programming_extra_0704.json",
         lambda p: _load_programming(p)),
    ]
    for label, path, loader in files:
        if not path.exists():
            print(f"  [WARN] missing: {path.name}")
            continue
        before = len(items)
        try:
            loaded = loader(path)
        except Exception as e:
            print(f"  [ERR] {path.name}: {e}")
            continue
        added = 0
        for q in loaded:
            qid = q.get("id")
            if qid and qid in seen_ids:
                continue
            if qid:
                seen_ids.add(qid)
            items.append(q)
            added += 1
        print(f"  loaded {label:<28} raw={len(loaded):>3} new={added:>3} (now {len(items)})")
    items.extend(_build_true_false_questions())
    print(f"  +true_false generated          +{len(TF_TEMPLATES)} (now {len(items)})")
    return items


def _load_choice_or_list(path: Path) -> List[Dict[str, Any]]:
    """json list 格式的直接题库。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(d, list):
        out = []
        for q in d:
            q = dict(q)
            q.setdefault("type", "multiple_choice")
            if "bloom_6x3" not in q:
                q["bloom_6x3"] = _guess_bloom6x3(q)
            out.append(q)
        return out
    return _load_choice(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="题库结构统一 + 判断题补全")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not (args.dry_run or args.apply):
        args.dry_run = True

    print("=" * 60)
    print(f"题库结构统一 (mode={'APPLY' if args.apply else 'DRY-RUN'})")
    print("=" * 60)
    items = collect_all()

    # 统计
    by_type: Dict[str, int] = {}
    by_kp: Dict[str, int] = {}
    by_bloom: Dict[str, int] = {}
    for q in items:
        by_type[q.get("type", "?")] = by_type.get(q.get("type", "?"), 0) + 1
        by_kp[q.get("kp_id", "?")] = by_kp.get(q.get("kp_id", "?"), 0) + 1
        b = q.get("bloom", "?")
        by_bloom[b] = by_bloom.get(b, 0) + 1

    print("\n--- type distribution ---")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t}: {n}")
    print(f"\n  TOTAL: {len(items)} | KP coverage: {len(by_kp)}/28")
    print("\n--- bloom distribution ---")
    for b in BLOOM_LEVELS:
        if b in by_bloom:
            print(f"  {b}: {by_bloom[b]}")

    # 持久化
    if args.apply:
        payload = {
            "_meta": {
                "version": "consolidated-v1-0711",
                "source_files": [
                    "question_bank.json", "question_bank_extra_0703.json",
                    "question_bank_extra_0704.json", "question_bank_analytics_0708.json",
                    "question_bank_fill.json", "question_bank_programming.json",
                    "question_bank_programming_extra_0704.json",
                ],
                "schema": "unified (choice + fill + programming + true_false)",
                "generated_at": time.time(),
                "type_distribution": by_type,
                "bloom_distribution": by_bloom,
                "kp_coverage": len(by_kp),
            },
            "questions": items,
        }
        OUTPUT_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n  WROTE: {OUTPUT_FILE}")
        print(f"  size: {OUTPUT_FILE.stat().st_size} bytes")
    else:
        print(f"\n  [DRY-RUN] would write to: {OUTPUT_FILE}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
