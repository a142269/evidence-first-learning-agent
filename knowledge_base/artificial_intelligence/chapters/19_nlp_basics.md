---
chapter_id: '19'
slug: nlp_basics
title: NLP 基础
kp_ids:
- AI_007
bloom_focus:
- Understand
- Apply
prerequisites:
- '18'
estimated_minutes: 50
---

# 19: 自然语言处理 (NLP) 基础 · 赋予机器语言的灵魂

> **Bloom 层级**: Understand → Apply
> **建议学时**: 50 分钟
> **前置知识**: 18-循环神经网络与LSTM

## 学习目标
1. 掌握自然语言处理（NLP）的核心任务分类（序列标注、文本分类、句对建模、生成式任务）。
2. 梳理文本预处理的标准流水线，理解分词、归一化以及 BPE/WordPiece 子词切分算法的必要性。
3. 对比 One-hot、Word2Vec 和上下文词向量（如 BERT、大模型隐层）在语义表示上的演进与优劣。
4. 应用基础的基线模型（如 TF-IDF + Logistic Regression）解决特定限制下的文本分类问题。
5. 认识 NLP 技术在 A3 教育智能体中（如学生提问意图识别、答案提取）的应用与局限。

## 19.1 NLP 任务全景
自然语言处理是 AI 领域最璀璨的明珠。我们根据“输入和输出的形态”将 NLP 任务进行归类：
- **文本分类 (Text Classification)**：输入一段话，输出一个类别。如：情感分析（评论→好评/差评）、意图识别（“这题怎么做？”→求助意图）。
- **序列标注 (Sequence Labeling)**：输入一句话，给这句话里的每一个词打上标签。最典型的是**命名实体识别 (NER)**，比如把“李华在北京读书”标注为：李华(PER)-在(O)-北京(LOC)-读书(O)。
- **句对建模 (Pair Modeling)**：输入两句话，判断它们的关系。如：文本相似度、问答匹配（Query-Document Matching），这是所有搜索和推荐系统的底层逻辑。
- **生成任务 (Text Generation)**：输入文本，输出全新的文本。如：机器翻译、文本摘要、对话系统（ChatGPT）。

## 19.2 文本预处理与子词切分
计算机不认识文字，只认识数字。把一段人类文字喂给模型前，必须经过严格的预处理流水线：
**清洗 (Cleaning)** $\rightarrow$ **分词 (Tokenization)** $\rightarrow$ **归一化 (Normalization)** $\rightarrow$ **子词切分 (Subword)** $\rightarrow$ **向量化 (Embedding)**。

**为什么需要子词切分 (Subword Tokenization)？**
在英文中，如果按空格分词，遇到 `Transformer`、`Transforming`、`Transformed` 就会把它们当成完全不同的三个独立词，不仅词表会爆炸，遇到没见过的生僻词（OOV）系统就会崩溃。
**BPE (Byte-Pair Encoding)** 算法通过统计相邻字符对的频率，将低频词拆散，高频词合并。例如将 `transformer` 切分成 `['trans', 'form', 'er']`。
这也是如今所有大模型（如 GPT、LLaMA、Qwen）底层的标准切词方案。

## 19.3 词向量：从静态走向动态
如何把一个词变成计算机能运算的向量？
- **One-hot 编码**：最古老的方法，词表有多大，向量就有多长，除了当前词的位置是 1，其他全是 0。缺点是极其稀疏，且无法计算“苹果”和“香蕉”之间的相似度。
- **Word2Vec (静态词向量)**：2013 年提出的里程碑。它认为“一个词的含义由它的上下文决定”。训练出来的词向量具有神奇的几何属性：`Vector(国王) - Vector(男) + Vector(女) ≈ Vector(女王)`。但它也有致命缺陷：**无法解决多义词**，比如“苹果手机”和“吃苹果”里的“苹果”使用的是同一个固定向量。
- **ELMo 与 BERT (上下文词向量)**：2018 年，NLP 迎来了它的 ImageNet 时刻。借助深层网络（LSTM / Transformer），模型在看到“吃苹果”时，会结合“吃”这个上下文，动态地生成“水果苹果”的向量，彻底解决了一词多义问题。

## 19.4 教育智能体场景案例
在 A3 系统中，NLP 无处不在。
**意图识别 (Intent Classification)**：当学生在对话框里输入“帮我总结一下第二章的重点”时，`Planner Agent` 需要立刻识别出这是一个 `Summarize_Request` 意图，从而决定调用 `Course Expert Agent` 而不是闲聊 Agent。
- 在计算资源有限的边缘网关上，我们可以使用传统的 **TF-IDF 结合线性分类器 (LinearSVC)**，它在几十毫秒内就能给出极其精准的意图分类结果，而不需要每次都去调用昂贵且延迟高的大语言模型。

## 19.5 常见误区
- **误区 1：既然有了大模型，以前的 TF-IDF 和线性分类器都可以扔掉了。**
  - **为什么错**：在许多中小规模的、分类标签固定的文本分类任务（如垃圾邮件拦截、简单的意图分流）中，TF-IDF 加上简单的逻辑回归不仅训练极快，推理延迟更是只有深度学习模型的百分之一，并且在特定领域的准确率（0.95+）并不比微调后的 BERT 差。大炮不一定适合打蚊子。
- **误区 2：评估机器翻译或文本摘要的质量时，BLEU 分数越高越好。**
  - **为什么错**：BLEU 依靠计算系统输出与人工参考答案中“完全相同的词组（N-gram）”来打分。如果系统输出了“我非常开心”，而参考答案是“我极其高兴”，因为词汇不同，BLEU 可能会打出很低的分数，但语义上是完全正确的。目前行业更倾向于使用基于语义的 BERTScore 甚至是由强 LLM（如 GPT-4）来进行人工替代打分 (LLM-as-a-Judge)。
- **误区 3：中文 NLP 不需要子词切分，直接用结巴（jieba）分词就够了。**
  - **为什么错**：基于词典的传统中文分词很难处理层出不穷的网络新词和专业术语，且会导致词表过于庞大。现代中文大模型（如 Qwen、ChatGLM）全部采用了基于字节或字符级别的 BPE/SentencePiece 方案，既控制了词表大小，又完美兼容了多语言和代码。

## 19.6 可运行示例：几行代码实现基于 TF-IDF 的意图分类
以下 Python 示例展示了不使用庞大神经网络，仅用传统的 NLP 机器学习管道，如何高效且高精度地完成学生的意图分类任务。

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import classification_report
import jieba

# 1. 准备极简的数据集 (模拟学生在 A3 里的提问)
# 标签: 0=知识问答, 1=作业求助, 2=闲聊
train_texts = [
    "什么是反向传播？", "请解释一下支持向量机", "卷积神经网络的原理",
    "帮我看看这道数学题怎么解", "我作业做不出来了求答案", "第三题的解题步骤是什么",
    "今天天气真不错", "你喜欢吃什么", "讲个笑话听听"
]
train_labels = [0, 0, 0, 1, 1, 1, 2, 2, 2]

test_texts = [
    "梯度消失是怎么回事",     # 预期: 0
    "这道微积分作业太难了",   # 预期: 1
    "你好啊，智能体"         # 预期: 2
]
test_labels = [0, 1, 2]

# 2. 中文必须先分词 (以空格分隔)
def tokenize(texts):
    return [" ".join(jieba.lcut(text)) for text in texts]

X_train = tokenize(train_texts)
X_test = tokenize(test_texts)

# 3. 构建经典的 NLP Pipeline: TF-IDF特征提取 + 逻辑回归分类器
model = make_pipeline(
    TfidfVectorizer(ngram_range=(1, 2)), # 提取一元词和二元词汇组合
    LogisticRegression(C=1.0)
)

# 4. 训练与预测
model.fit(X_train, train_labels)
predictions = model.predict(X_test)

print("=== TF-IDF 意图分类器结果 ===")
for text, pred in zip(test_texts, predictions):
    intent_map = {0: "知识问答", 1: "作业求助", 2: "闲聊"}
    print(f"输入: '{text}' -> 预测意图: {intent_map[pred]}")

print("\n--- 分类报告 ---")
print(classification_report(test_labels, predictions))
```

## 19.7 本章小结
1. NLP 任务繁多，但大致可抽象为分类、标注、匹配和生成四大范式。
2. 数据预处理（特别是现代大模型的 BPE 切词技术）决定了模型理解语言的地基。
3. 词表示从 One-hot 的稀疏孤立，进化到 Word2Vec 的几何聚类，最终在 BERT 和 LLM 的上下文语境中达到巅峰。
4. 虽然大模型几乎席卷了 NLP 的所有生成任务，但在端侧低延迟场景下，TF-IDF 配合线性分类器依然是轻量级的常青树。

## 19.10 可运行代码示例

下面用 Python 标准库实现中文简易分词 + TF-IDF 文本分类器雏形。零依赖演示 NLP 任务的最底层流程。

```python
'''19 章 · 分词 + TF-IDF 词向量 — 标准库实现'''
import math
import re
from collections import Counter

# 1. 一个极简中文"分词"（按字符 + 高频词合并）
VOCAB = ["机器", "学习", "深度", "神经网络", "卷积", "循环", "注意力",
         "分类", "聚类", "回归", "梯度", "反向传播"]

def tokenize_zh(text: str) -> list[str]:
    '''优先匹配词表，否则按字切分'''
    tokens = []
    i = 0
    while i < len(text):
        matched = None
        for w in VOCAB:
            if text[i:i+len(w)] == w:
                matched = w
                break
        if matched:
            tokens.append(matched)
            i += len(matched)
        else:
            tokens.append(text[i])
            i += 1
    return tokens

# 2. 训练语料（4 个样本，2 个类别）
docs = [
    ("机器学习是人工智能的核心"),
    ("深度学习基于神经网络"),
    ("卷积神经网络擅长图像"),
    ("循环神经网络处理序列"),
]
labels = ["AI", "AI", "CV", "NLP"]

# 3. 词袋 + TF-IDF
tokenized = [tokenize_zh(d) for d in docs]
df: dict[str, int] = {}
for toks in tokenized:
    for t in set(toks):
        df[t] = df.get(t, 0) + 1
N = len(docs)
idf = {t: math.log((N + 1) / (df_t + 1)) + 1 for t, df_t in df.items()}

def tfidf_vec(tokens: list[str]) -> dict[str, float]:
    tf = Counter(tokens)
    return {t: tf[t] * idf.get(t, 0) for t in tf}

vecs = [tfidf_vec(toks) for toks in tokenized]
print("TF-IDF 向量 (前 5 维):")
for i, v in enumerate(vecs):
    top = sorted(v.items(), key=lambda x: -x[1])[:5]
    print(f"  doc{i+1} ({labels[i]}): {top}")

# 4. 余弦相似度 + 简易最近邻分类
def cosine(a: dict, b: dict) -> float:
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    den = math.sqrt(sum(v*v for v in a.values())) * math.sqrt(sum(v*v for v in b.values()))
    return num / den if den else 0.0

def classify(query: str) -> tuple[str, list[tuple[str, float]]]:
    qv = tfidf_vec(tokenize_zh(query))
    scores = [(labels[i], cosine(qv, v)) for i, v in enumerate(vecs)]
    scores.sort(key=lambda x: -x[1])
    return scores[0][0], scores

# 5. 推理
tests = ["反向传播是神经网络的关键", "卷积是图像处理的核心"]
for q in tests:
    pred, scores = classify(q)
    print(f"\nQ: {q}")
    print(f"  预测类别: {pred}   相似度: {[round(s, 3) for _, s in scores]}")

print("\n→ 现代 NLP 用预训练模型 (BERT/GPT) 替代 TF-IDF，向量语义更丰富。")
```
\n## 19.8 练习思考
1. **词向量特性**：Word2Vec 的 Skip-gram 模型训练目标是“使用中心词预测周围的词”。为什么这种看似荒谬的做法，最终能训练出具有极强语义相关性的词向量？
2. **序列标注**：在命名实体识别（NER）中，如果我们在模型输出层只使用简单的 Softmax 函数，可能会预测出 `O`（非实体）后面紧跟着 `I-PER`（人名内部）这种违背 BIO 规则的错误序列。应该引入什么经典算法层来解决这个问题？
3. **架构选型**：在 A3 系统的“错题搜索”模块中，学生输入“导数公式”，系统需要在 10 万道题库中极速召回相关的题目。你应该选择“双塔模型（Two-Tower）”还是“单塔交互模型（One-Tower）”？为什么？
4. **生成评估**：当系统自动为学生的一篇长文阅读生成了摘要，由于存在“一义多词”现象，BLEU 分数极低。你可以使用当前流行的哪种大语言模型评估范式（Paradigm）来替代传统指标以获得更公正的打分？

## 19.9 拓展阅读
- NLP 词表示里程碑：阅读 `Distributed Representations of Words and Phrases and their Compositionality` (Mikolov et al., 2013)
- BPE 切词算法的详细原理解析：检索 `Neural Machine Translation of Rare Words with Subword Units` (Sennrich et al., 2015)
- 生成任务的现代评估方式：了解 `G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment`
