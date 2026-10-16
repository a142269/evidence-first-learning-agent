#!/usr/bin/env python3
"""Day 4 题库生成器：20 KP × 10 题 = 200 道，按 Bloom 分布。

输出 data/question_bank.json，结构：
{
  "_meta": {"version": "...", "total": 200, "kp_count": 20, "bloom_distribution": {...}},
  "questions": [{"id": "...", "kp_id": "...", "bloom": "...", "type": "...", ...}]
}

使用：
    python -m scripts.build_question_bank
    python -m scripts.build_question_bank --check  # 不写文件，仅打印统计
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "question_bank.json"

# ============================================================
# 20 KP 事实库：与 seed_extended.json 的 KP 列表对齐
# ============================================================
KP_FACTS: dict[str, dict] = {
    "python_basics": {
        "name": "Python 基础",
        "concepts": ["不可变类型", "列表推导式", "生成器", "异常处理", "上下文管理器"],
        "code_examples": ["[x*2 for x in range(5)]", "with open(f) as fp", "yield"],
        "wrong_answers": ["JVM 字节码", "GIL 是 Java 概念", "Python 强类型不需检查"],
    },
    "data_structures": {
        "name": "数据结构",
        "concepts": ["散列表 O(1) 平均查询", "栈 LIFO", "队列 FIFO", "二叉搜索树", "图遍历"],
        "code_examples": ["dict.get(k, default)", "collections.deque", "heapq.heappush"],
        "wrong_answers": ["数组比链表插入快", "栈用于广度搜索", "字典天然有序"],
    },
    "linear_algebra": {
        "name": "线性代数",
        "concepts": ["向量内积", "矩阵乘法 (m,k)·(k,n)=(m,n)", "特征值分解", "奇异值分解", "范数"],
        "code_examples": ["np.dot(A, B)", "np.linalg.eig", "np.linalg.svd"],
        "wrong_answers": ["矩阵乘法可交换", "特征值唯一", "L1 范数比 L2 平滑"],
    },
    "probability_statistics": {
        "name": "概率与统计",
        "concepts": ["贝叶斯公式", "中心极限定理", "假设检验 p 值", "极大似然估计", "条件独立"],
        "code_examples": ["scipy.stats.norm.pdf", "scipy.stats.ttest_ind"],
        "wrong_answers": ["p 值 < 0.05 即接受 H0", "样本均值总等于总体均值", "独立等价于不相关"],
    },
    "ml_basics": {
        "name": "机器学习基础",
        "concepts": ["训练 / 验证 / 测试集", "偏差-方差权衡", "正则化", "过拟合", "交叉验证"],
        "code_examples": ["train_test_split", "GridSearchCV", "Pipeline"],
        "wrong_answers": ["训练集 acc 高即模型好", "正则化是数据增强", "验证集可反复用"],
    },
    "supervised_learning": {
        "name": "监督学习",
        "concepts": ["线性回归正规方程", "逻辑回归交叉熵", "Hinge Loss", "F1 = 2PR/(P+R)", "ROC-AUC"],
        "code_examples": ["LogisticRegression(C=1)", "f1_score(y, ŷ)", "roc_auc_score"],
        "wrong_answers": ["逻辑回归输出是回归值", "Accuracy 总比 F1 可靠", "AUC=0.5 是完美分类"],
    },
    "unsupervised_learning": {
        "name": "无监督学习",
        "concepts": ["KMeans 簇内方差最小", "DBSCAN 基于密度", "PCA 最大方差方向", "轮廓系数", "t-SNE 局部结构"],
        "code_examples": ["KMeans(n_clusters=K)", "PCA(n_components=0.95)", "DBSCAN(eps, min_samples)"],
        "wrong_answers": ["KMeans 自动选 K", "PCA 保留全部信息", "DBSCAN 需要预设簇数"],
    },
    "decision_trees": {
        "name": "决策树与集成",
        "concepts": ["基尼不纯度", "信息增益", "Bagging 降方差", "Boosting 降偏差", "XGBoost 二阶 Taylor"],
        "code_examples": ["RandomForestClassifier", "XGBClassifier", "feature_importances_"],
        "wrong_answers": ["Boosting 模型可并行", "决策树需要标准化", "RF 必然优于 XGBoost"],
    },
    "svm": {
        "name": "支持向量机",
        "concepts": ["最大间隔", "支持向量决定决策面", "核函数避免显式映射", "RBF 核 γ 控复杂度", "Hinge Loss"],
        "code_examples": ["SVC(kernel='rbf', C=1)", "LinearSVC", "Pipeline(StandardScaler, SVC)"],
        "wrong_answers": ["SVM 输出原生概率", "线性核与多项式核 d=1 不等价", "C 越大越欠拟合"],
    },
    "neural_networks": {
        "name": "神经网络基础",
        "concepts": ["前馈与反馈", "激活函数非线性", "权重初始化", "Dropout 正则", "BatchNorm"],
        "code_examples": ["nn.Linear(in, out)", "nn.ReLU()", "nn.BatchNorm1d"],
        "wrong_answers": ["线性激活也能深层", "Sigmoid 无梯度消失", "Dropout 推理时仍开启"],
    },
    "backpropagation": {
        "name": "反向传播",
        "concepts": ["链式法则", "自动微分反向模式", "梯度消失", "梯度裁剪", "Adam 自适应"],
        "code_examples": ["loss.backward()", "torch.optim.AdamW", "clip_grad_norm_"],
        "wrong_answers": ["前向模式适合深度学习", "AdamW 与 Adam 等价", "梯度裁剪改变梯度方向"],
    },
    "cnn": {
        "name": "卷积神经网络",
        "concepts": ["局部感受野", "权值共享", "池化降维", "ResNet 残差", "感受野公式"],
        "code_examples": ["nn.Conv2d(3, 64, 3)", "nn.MaxPool2d(2)", "ResNet-50"],
        "wrong_answers": ["卷积层参数与图像尺寸成正比", "池化引入参数", "ResNet 是 CNN 替代"],
    },
    "rnn": {
        "name": "循环神经网络",
        "concepts": ["共享时间步参数", "BPTT", "梯度消失", "LSTM 门控", "GRU 简化"],
        "code_examples": ["nn.LSTM(input, hidden)", "pack_padded_sequence", "h_t = f(x_t, h_{t-1})"],
        "wrong_answers": ["RNN 时间步参数不共享", "vanilla RNN 长序列稳定", "GRU 比 LSTM 参数多"],
    },
    "lstm": {
        "name": "LSTM 与 GRU",
        "concepts": ["遗忘门", "输入门", "细胞状态", "GRU 更新门", "门控缓解梯度消失"],
        "code_examples": ["nn.LSTM(num_layers=2, bidirectional=True)", "nn.GRU"],
        "wrong_answers": ["LSTM 完全消除梯度问题", "GRU 性能必弱于 LSTM", "双向 LSTM 可流式"],
    },
    "attention_mechanism": {
        "name": "注意力机制",
        "concepts": ["Q K V 三矩阵", "缩放点积", "Softmax 归一化", "多头注意力", "掩码"],
        "code_examples": ["nn.MultiheadAttention", "Q @ K.T / sqrt(d)", "torch.softmax"],
        "wrong_answers": ["注意力是 RNN 替代品", "缩放因子是经验值", "多头共享权重"],
    },
    "transformer": {
        "name": "Transformer",
        "concepts": ["Encoder/Decoder", "位置编码", "Layer Norm", "FFN 升降维", "残差"],
        "code_examples": ["TransformerEncoderLayer", "PositionalEncoding", "GPT decoder-only"],
        "wrong_answers": ["Transformer 含 RNN", "位置编码非必需", "Encoder-only 适合生成"],
    },
    "nlp_basics": {
        "name": "NLP 基础",
        "concepts": ["分词与子词", "BPE", "TF-IDF", "BiLSTM-CRF", "BLEU / ROUGE"],
        "code_examples": ["jieba.cut", "TfidfVectorizer", "BertTokenizer"],
        "wrong_answers": ["BLEU 是分类指标", "TF-IDF 是上下文向量", "BPE 是损失函数"],
    },
    "rag": {
        "name": "检索增强生成 (RAG)",
        "concepts": ["向量检索", "重排序", "Hybrid Search", "幻觉缓解", "Chunk Size"],
        "code_examples": ["chromadb.Collection.query", "BM25Retriever", "RerankerModel"],
        "wrong_answers": ["RAG 等于 fine-tune", "Chunk 越长越好", "向量检索必然精确"],
    },
    "reinforcement_learning": {
        "name": "强化学习",
        "concepts": ["MDP", "Bellman 方程", "Q-Learning", "Policy Gradient", "PPO"],
        "code_examples": ["env.step(action)", "Q(s,a) ← Q(s,a) + α[r + γ max Q(s',a')]"],
        "wrong_answers": ["RL 需要标签", "Q-Learning 是 on-policy", "PPO 没有 clip"],
    },
    "ai_project_practice": {
        "name": "AI 项目实战",
        "concepts": ["需求分析", "数据闭环", "模型上线", "A/B 实验", "监控漂移"],
        "code_examples": ["Docker compose up", "MLflow tracking", "Prometheus + Grafana"],
        "wrong_answers": ["AI 项目无需监控", "离线指标等于线上效果", "A/B 测试可省"],
    },
}

assert len(KP_FACTS) == 20, f"KP_FACTS 应为 20，当前 {len(KP_FACTS)}"

# Bloom 分布：每 KP 10 题 = R(2) + U(2) + Ap(2) + An(2) + Ev(1) + Cr(1)
BLOOM_PLAN = [
    ("Remember", 2),
    ("Understand", 2),
    ("Apply", 2),
    ("Analyze", 2),
    ("Evaluate", 1),
    ("Create", 1),
]
assert sum(n for _, n in BLOOM_PLAN) == 10


# ============================================================
# 模板：每个 Bloom 等级一组通用问句 + 选项 pattern
# ============================================================
def _stem(bloom: str, idx: int, kp_name: str, concept: str) -> str:
    """根据 Bloom 等级 + 索引生成题干。"""
    pool = {
        "Remember": [
            f"下列哪一项最准确描述 {kp_name} 中的「{concept}」？",
            f"在 {kp_name} 体系下，{concept} 主要属于哪一类范畴？",
        ],
        "Understand": [
            f"为什么 {concept} 在 {kp_name} 中是核心机制？",
            f"如何理解 {concept} 在 {kp_name} 场景下产生的作用？",
        ],
        "Apply": [
            f"在实际工程里，若需要应用 {concept}，下列哪种代码 / 设计最合适？",
            f"对 {kp_name} 任务，借助 {concept} 实现下列哪个目标最直接？",
        ],
        "Analyze": [
            f"针对 {kp_name} 中的 {concept}，下列分析哪一项是误区？",
            f"如果 {concept} 失效，会让 {kp_name} 整体出现什么连锁影响？",
        ],
        "Evaluate": [
            f"评价 {kp_name} 不同方案时，{concept} 的可靠性如何排序？",
        ],
        "Create": [
            f"设计一个新的 {kp_name} 应用场景，要求显式利用 {concept}，下列哪种构想最合理？",
        ],
    }
    options = pool[bloom]
    return options[idx % len(options)]


def _question_type(bloom: str) -> str:
    """Bloom 等级 → 题型。"""
    return {
        "Remember": "multiple_choice",
        "Understand": "multiple_choice",
        "Apply": "multiple_choice",
        "Analyze": "multiple_choice",
        "Evaluate": "short_answer",
        "Create": "open_ended",
    }[bloom]


def _difficulty(bloom: str) -> int:
    return {"Remember": 1, "Understand": 2, "Apply": 3, "Analyze": 4, "Evaluate": 4, "Create": 5}[bloom]


def _make_options(facts: dict, concept: str, idx: int) -> tuple[list[str], str]:
    """选项 + 正确答案字母（A/B/C/D），4 选 1。"""
    correct = concept
    wrong_pool = facts["wrong_answers"] + facts["code_examples"]
    if len(wrong_pool) < 3:
        wrong_pool = wrong_pool + ["以上都对", "以上都不对", "无法判断"]
    wrongs = [wrong_pool[(idx + i) % len(wrong_pool)] for i in range(3)]
    # 把正确答案插入第 (idx % 4) 位
    pos = idx % 4
    options = wrongs[:]
    options.insert(pos, correct)
    return options, "ABCD"[pos]


def _explanation(kp_name: str, concept: str, bloom: str) -> str:
    base = f"该题考查 {kp_name} 中「{concept}」的 {bloom} 级理解。"
    detail = {
        "Remember": f"识别正确表述：{concept} 是该领域的基础概念。",
        "Understand": f"理解层面：{concept} 在 {kp_name} 中起到关键支撑作用。",
        "Apply": f"应用层面：在工程实现时需依赖 {concept} 完成对应任务。",
        "Analyze": f"分析层面：与 {concept} 相关的常见误区需重点甄别。",
        "Evaluate": f"评价层面：需横向对比方案、权衡 {concept} 的适用性。",
        "Create": f"创造层面：在新场景中显式利用 {concept} 的能力。",
    }
    return base + detail[bloom]


def generate_questions() -> list[dict]:
    """主入口：生成 200 道结构化题。"""
    bank: list[dict] = []
    for kp_id, facts in KP_FACTS.items():
        kp_name = facts["name"]
        concepts = facts["concepts"]
        n_idx = 0
        for bloom, count in BLOOM_PLAN:
            for sub in range(count):
                concept = concepts[(n_idx) % len(concepts)]
                qtype = _question_type(bloom)
                stem = _stem(bloom, sub, kp_name, concept)
                entry: dict = {
                    "id": f"q-{kp_id}-{n_idx:02d}",
                    "kp_id": kp_id,
                    "kp_name": kp_name,
                    "bloom": bloom,
                    "type": qtype,
                    "stem": stem,
                    "difficulty": _difficulty(bloom),
                    "explanation": _explanation(kp_name, concept, bloom),
                    "tags": [kp_id, bloom.lower()],
                }
                if qtype == "multiple_choice":
                    options, answer = _make_options(facts, concept, n_idx)
                    entry["options"] = options
                    entry["answer"] = answer
                elif qtype == "short_answer":
                    entry["expected_keywords"] = [concept, kp_name]
                    entry["answer"] = (
                        f"评价应围绕 {concept} 的有效性、适用范围与对照方案展开，"
                        f"结合 {kp_name} 的核心约束给出排序依据。"
                    )
                else:  # open_ended
                    entry["expected_keywords"] = [concept, kp_name, "场景"]
                    entry["answer"] = (
                        f"设计要点：明确目标场景、说明如何调用 {concept}、给出关键指标，"
                        f"并讨论与 {kp_name} 其他能力的协同。"
                    )
                n_idx += 1
                bank.append(entry)
    return bank


def build_meta(bank: list[dict]) -> dict:
    bloom_dist = Counter(q["bloom"] for q in bank)
    kp_dist = Counter(q["kp_id"] for q in bank)
    type_dist = Counter(q["type"] for q in bank)
    digest = hashlib.sha1(
        json.dumps(bank, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return {
        "version": "day4-200-v1",
        "total": len(bank),
        "kp_count": len(kp_dist),
        "bloom_distribution": dict(bloom_dist),
        "type_distribution": dict(type_dist),
        "per_kp": dict(kp_dist),
        "content_hash": digest,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 200 道题题库")
    parser.add_argument("--check", action="store_true", help="仅打印统计，不写文件")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="输出 JSON 路径")
    args = parser.parse_args()

    bank = generate_questions()
    meta = build_meta(bank)

    print(f"[qbank] total={meta['total']} kp={meta['kp_count']} bloom={meta['bloom_distribution']} hash={meta['content_hash']}")
    if args.check:
        return

    payload = {"_meta": meta, "questions": bank}
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[qbank] written to {out}")


if __name__ == "__main__":
    main()
