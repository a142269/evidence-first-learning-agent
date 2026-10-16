"""合成查询库 — Multi-Agent Debate 收敛性研究用

设计:
    - 5 类别 × 10 题 = 50 个合成查询
    - 每类模拟真实大学生可能提出的问题
    - 标注期望的辩论行为: 预期轮数 / 最难维度 / 卡点类型

类别:
    theory     — 概念解释 (预期快速收敛: 知识库覆盖好)
    code       — 代码/实现 (预期中等: 代码正确性难判别)
    ambiguous  — 模糊/不完整问题 (预期慢收敛: 需先澄清)
    compare    — 对比/比较 (预期快速: 结构清晰)
    edge       — 边缘/陷阱 (预期困难: 概念边界模糊)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

# ================================================================
# 查询模型
# ================================================================
@dataclass
class SyntheticQuery:
    """合成查询"""
    id: str
    text: str
    category: str                      # theory / code / ambiguous / compare / edge
    expected_behavior: str             # 期望辩论行为描述
    expected_rounds: int               # 预期通过轮数
    hardest_dimension: str             # 最难通过的维度
    stagnation_risk: str               # "low" / "medium" / "high"


# ================================================================
# 5 类 × 10 题
# ================================================================
SYNTHETIC_QUERIES: List[SyntheticQuery] = [
    # ================================================================
    # theory — 概念解释 (知识库覆盖好，预期 1-2 轮)
    # ================================================================
    SyntheticQuery("t01", "什么是卷积神经网络？请详细讲解", "theory",
                   "快速通过: RAG命中高，Bloom达到understand即可", 1, "citation", "low"),
    SyntheticQuery("t02", "反向传播算法的数学原理是什么？", "theory",
                   "中等: 需要数学公式+推导步骤", 2, "pedagogy", "low"),
    SyntheticQuery("t03", "Transformer的注意力机制如何工作？", "theory",
                   "快速: 经典话题，知识库覆盖好", 1, "citation", "low"),
    SyntheticQuery("t04", "什么是过拟合？怎么解决？", "theory",
                   "快速: 定义+解决方案，结构清晰", 1, "pedagogy", "low"),
    SyntheticQuery("t05", "强化学习和监督学习的区别是什么？", "theory",
                   "快速: 对比型，容易通过", 1, "citation", "low"),
    SyntheticQuery("t06", "请解释梯度下降的各种变体（SGD/Momentum/Adam）", "theory",
                   "中等: 多个概念需要逐一讲解", 2, "pedagogy", "low"),
    SyntheticQuery("t07", "什么是贝叶斯定理？在机器学习中怎么用？", "theory",
                   "快速: 基础概念", 1, "citation", "low"),
    SyntheticQuery("t08", "L1和L2正则化有什么不同？", "theory",
                   "快速: 对比型", 1, "citation", "low"),
    SyntheticQuery("t09", "什么是PCA主成分分析？讲一下数学推导", "theory",
                   "中等: 数学推导需要步骤", 2, "pedagogy", "medium"),
    SyntheticQuery("t10", "请解释交叉熵损失函数", "theory",
                   "快速: 单一概念", 1, "pedagogy", "low"),

    # ================================================================
    # code — 代码/实现 (代码正确性难判别，预期 2 轮)
    # ================================================================
    SyntheticQuery("c01", "用Python实现一个简单的CNN，在MNIST上训练", "code",
                   "中等: 代码量较大，需要注释", 2, "pedagogy", "medium"),
    SyntheticQuery("c02", "怎么写一个PyTorch的DataLoader？给个例子", "code",
                   "快速: 短代码+示例", 1, "pedagogy", "low"),
    SyntheticQuery("c03", "实现softmax函数，要求数值稳定", "code",
                   "快速: 短函数", 1, "factual", "low"),
    SyntheticQuery("c04", "用NumPy从零实现线性回归的梯度下降", "code",
                   "中等: 需要数学+代码双重正确", 2, "factual", "medium"),
    SyntheticQuery("c05", "写一个Transformer的self-attention实现", "code",
                   "中等: 代码量中，需解释", 2, "pedagogy", "medium"),
    SyntheticQuery("c06", "怎么用scikit-learn做交叉验证？给个例子", "code",
                   "快速: 调包代码", 1, "citation", "low"),
    SyntheticQuery("c07", "实现一个简单的决策树（不调包）", "code",
                   "困难: 算法复杂度高，代码量大", 2, "factual", "high"),
    SyntheticQuery("c08", "写一个batch normalization的前向传播", "code",
                   "中等: 需要公式+代码", 2, "factual", "medium"),
    SyntheticQuery("c09", "实现LeNet-5并用在CIFAR-10上", "code",
                   "中等: 经典网络", 2, "pedagogy", "medium"),
    SyntheticQuery("c10", "用Python实现K-means聚类算法", "code",
                   "中等: 算法代码中等长度", 2, "pedagogy", "medium"),

    # ================================================================
    # ambiguous — 模糊/不完整问题 (需澄清，预期 2+ 轮)
    # ================================================================
    SyntheticQuery("a01", "AI怎么学？", "ambiguous",
                   "困难: 问题极度模糊，Critic会判bloom不达标", 2, "bloom", "high"),
    SyntheticQuery("a02", "帮我理解机器学习", "ambiguous",
                   "困难: 无具体目标", 2, "bloom", "high"),
    SyntheticQuery("a03", "那个什么网络来着，就是处理图像的", "ambiguous",
                   "困难: 需猜测用户意图", 2, "factual", "high"),
    SyntheticQuery("a04", "怎么提升模型效果？", "ambiguous",
                   "困难: 问题过于开放", 2, "pedagogy", "high"),
    SyntheticQuery("a05", "深度学习怎么做？", "ambiguous",
                   "困难: 无范围", 2, "bloom", "high"),
    SyntheticQuery("a06", "刚才那个概念再讲一下", "ambiguous",
                   "困难: 缺少上下文", 2, "factual", "high"),
    SyntheticQuery("a07", "帮我看看这个对不对", "ambiguous",
                   "困难: 无具体内容", 2, "factual", "high"),
    SyntheticQuery("a08", "loss不下降怎么办？", "ambiguous",
                   "中等: 有具体场景但缺细节", 2, "pedagogy", "medium"),
    SyntheticQuery("a09", "这个参数怎么调？", "ambiguous",
                   "困难: 无上下文", 2, "factual", "high"),
    SyntheticQuery("a10", "它为什么不work？", "ambiguous",
                   "困难: 极度模糊", 2, "factual", "high"),

    # ================================================================
    # compare — 对比/比较 (结构清晰，预期 1 轮)
    # ================================================================
    SyntheticQuery("p01", "CNN和RNN有什么区别？各适合什么场景？", "compare",
                   "快速: 对比型，结构清晰", 1, "citation", "low"),
    SyntheticQuery("p02", "TensorFlow和PyTorch哪个更好？", "compare",
                   "快速: 需要客观比较", 1, "citation", "low"),
    SyntheticQuery("p03", "ReLU和Sigmoid激活函数对比", "compare",
                   "快速: 经典对比", 1, "pedagogy", "low"),
    SyntheticQuery("p04", "BatchNorm vs LayerNorm vs GroupNorm", "compare",
                   "中等: 三个概念比较", 1, "citation", "low"),
    SyntheticQuery("p05", "GPT和BERT架构差异", "compare",
                   "快速: 经典对比", 1, "citation", "low"),
    SyntheticQuery("p06", "监督学习、无监督学习、强化学习对比", "compare",
                   "快速: 三类比较", 1, "pedagogy", "low"),
    SyntheticQuery("p07", "随机森林和梯度提升树哪个好？", "compare",
                   "快速: 对比型", 1, "citation", "low"),
    SyntheticQuery("p08", "MSE和交叉熵损失什么时候用？", "compare",
                   "快速: 应用场景比较", 1, "pedagogy", "low"),
    SyntheticQuery("p09", "Transformer vs LSTM 性能对比", "compare",
                   "快速: 经典话题", 1, "citation", "low"),
    SyntheticQuery("p10", "数据并行 vs 模型并行 什么场景选哪个？", "compare",
                   "快速: 工程对比", 1, "citation", "low"),

    # ================================================================
    # edge — 边缘/陷阱 (概念边界模糊，预期困难)
    # ================================================================
    SyntheticQuery("e01", "什么是AGI？现在实现了吗？", "edge",
                   "困难: 定义模糊，容易过度陈述", 2, "factual", "high"),
    SyntheticQuery("e02", "量子计算会取代深度学习吗？", "edge",
                   "困难: 跨领域推测，RAG覆盖差", 2, "factual", "high"),
    SyntheticQuery("e03", "AI有意识吗？", "edge",
                   "困难: 哲学+科学交叉", 2, "factual", "high"),
    SyntheticQuery("e04", "大模型的涌现能力是真的还是错觉？", "edge",
                   "困难: 学术争议话题", 2, "citation", "high"),
    SyntheticQuery("e05", "用AI预测股票，可行吗？为什么？", "edge",
                   "困难: 需要客观分析+限制条件", 2, "pedagogy", "high"),
    SyntheticQuery("e06", "自监督学习是未来吗？", "edge",
                   "困难: 预测性话题", 2, "citation", "high"),
    SyntheticQuery("e07", "ChatGPT真的理解语言吗？", "edge",
                   "困难: 哲学+技术交叉", 2, "factual", "high"),
    SyntheticQuery("e08", "神经网络为什么需要这么多数据？人脑不需要", "edge",
                   "困难: 认知科学交叉", 2, "pedagogy", "high"),
    SyntheticQuery("e09", "prompt engineering是真正的技能还是暂时的？", "edge",
                   "困难: 预测性+争议性", 2, "citation", "high"),
    SyntheticQuery("e10", "AI会让程序员失业吗？", "edge",
                   "困难: 社会话题，需谨慎", 2, "factual", "high"),
]


# ================================================================
# 查询采样工具
# ================================================================
def get_queries_by_category(category: str) -> List[SyntheticQuery]:
    """获取某类别所有查询"""
    return [q for q in SYNTHETIC_QUERIES if q.category == category]


def get_balanced_sample(n_per_category: int = 3) -> List[SyntheticQuery]:
    """从每个类别均匀采样"""
    import random
    random.seed(42)
    sample: List[SyntheticQuery] = []
    categories = sorted(set(q.category for q in SYNTHETIC_QUERIES))
    for cat in categories:
        cat_queries = get_queries_by_category(cat)
        sample.extend(random.sample(cat_queries, min(n_per_category, len(cat_queries))))
    return sample


def get_all() -> List[SyntheticQuery]:
    return list(SYNTHETIC_QUERIES)


def category_stats() -> dict:
    """各类别统计"""
    stats: dict = {}
    for q in SYNTHETIC_QUERIES:
        c = q.category
        if c not in stats:
            stats[c] = {"count": 0, "total_rounds": 0}
        stats[c]["count"] += 1
        stats[c]["total_rounds"] += q.expected_rounds
    for c in list(stats.keys()):
        stats[c]["avg_expected_rounds"] = round(
            stats[c]["total_rounds"] / stats[c]["count"], 2
        )
        del stats[c]["total_rounds"]
    return stats
