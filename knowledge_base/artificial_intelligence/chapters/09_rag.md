---
chapter_id: 09
slug: rag
title: 检索增强生成 (RAG)
kp_ids:
- AI_011
bloom_focus:
- Apply
- Evaluate
prerequisites:
- '05'
- '19'
estimated_minutes: 55
---

# 09: 检索增强生成 (RAG) · 从检索到可信生成

> **Bloom 层级**: Understand → Apply → Evaluate
> **建议学时**: 55 分钟
> **前置知识**: 05-Transformer、19-NLP基础

## 学习目标
1. 明确定义 RAG 的三大核心组件：检索、生成与溯源。
2. 梳理并描述文档加载、清洗、分块、Embedding、索引、召回、重排序、答案生成和引用展示的完整流程。
3. 评估并解释 Chunk size、overlap、top_k、相似度阈值以及重排序等关键参数对最终生成质量的影响。
4. 区分 GraphRAG 与普通向量检索在结构表达和多跳推理上的本质区别。
5. 分析 A3 项目中如何利用 RAG 技术实现知识库溯源徽章、课程检索及错题归因。

## 9.1 RAG 的核心概念：检索 + 生成 + 溯源
大语言模型虽然知识渊博，但存在致命弱点：“幻觉”（胡编乱造）和“知识截断”（不知道最新的信息或企业的私有数据）。

**定义与直觉解释**：检索增强生成（Retrieval-Augmented Generation, RAG）本质上就是给模型一场“开卷考试”。在回答用户问题前，模型首先去一个外挂的“图书馆”（知识库）里把相关的资料（检索）翻出来，然后结合这些资料（溯源引用）来回答问题（生成）。

**教育场景例子**：当学生问“什么是梯度消失？”时，如果直接让 LLM 回答，它可能会基于全网数据给出一个极其深奥的数学证明。而使用 RAG 技术，系统会先在《人工智能导论》课程的特定章节中检索“梯度消失”的段落，然后让 LLM 基于这些段落生成符合大二学生认知水平的解释，并附上“参考自：第三章 第2节”的溯源徽章。

## 9.2 RAG 的完整工作流程
构建一个成熟的 RAG 系统，就像建立一个现代化的图书检索与答疑系统。其流水线可以分为“建库”与“问答”两阶段：

### 阶段一：建库（Data Ingestion）
1. **文档加载与清洗 (Load & Clean)**：读取 PDF、Markdown、Word 等格式的文档，去除多余的空格、HTML 标签、水印等干扰信息。
2. **分块 (Chunking)**：把一整本书切成若干个小段落（Chunk）。因为 LLM 的上下文窗口有限，且检索整本书的向量效率极低。
3. **向量化 (Embedding)**：利用 Embedding 模型，将每一块纯文本转换为高维向量。语义相近的文本，其向量在空间中的距离就越近。
4. **索引 (Indexing)**：将文本块和对应的向量存入向量数据库（如 Chroma、Milvus），构建高效的检索索引。

### 阶段二：问答（Retrieval & Generation）
5. **查询向量化**：将用户的提问用同一个 Embedding 模型转化为向量。
6. **召回 (Retrieval/Recall)**：在向量数据库中计算提问向量与所有文本块向量的距离，召回最相似的 Top-K 个文本块。
7. **重排序 (Reranking)**：可选步骤。由于召回模型往往是双塔模型，精度有限；这里引入更慢但更准的 Cross-Encoder 模型，对召回的 Top-K 文本块重新打分排序，剔除无关内容。
8. **答案生成 (Generation)**：将排在最前面的文本块与用户的提问拼接成一个 Prompt：“请根据以下参考资料回答问题：...”。交给 LLM 生成最终答案。
9. **引用展示 (Citation)**：前端不仅展示答案，还要把 LLM 所依赖的 Chunk 来源高亮展示给用户，完成溯源。

## 9.3 关键参数解析
在 RAG 的工程实践中，参数调优决定了系统的生死：
- **Chunk size (分块大小)**：每个片段包含的字符数。太大，会导致上下文中混杂过多无关信息（“大海捞针”）；太小，会破坏语义完整性，导致 LLM 看不懂。
- **Chunk overlap (分块重叠度)**：相邻两个块之间重叠的字符数。防止切分时刚好把一个重要的长句子或公式从中间腰斩。
- **Top-k (召回数量)**：传给 LLM 的文档块数量。增加 K 能提高包含正确答案的概率（Recall），但会消耗更多 token 成本，甚至因为引入太多噪声导致 LLM 出现混乱。
- **Similarity Threshold (相似度阈值)**：如果在数据库中找不到与问题相似度高于该阈值的文档，系统应当拒绝回答（“对不起，课程资料中未找到相关内容”），而不是强行让 LLM 编造。

## 9.4 GraphRAG 与普通向量检索
**普通向量检索的局限**：普通 RAG 是“扁平”的，它只能根据文本的字面语义去匹配。如果学生问一个跨章节的宏大问题：“请总结深度学习如何改善计算机视觉？”，普通 RAG 可能会召回一堆零散的片段，无法形成全局认知。

**GraphRAG 的区别**：
- GraphRAG 引入了**知识图谱（Knowledge Graph）**。它在建库时，利用大模型抽取出文本中的“实体”（如：CNN）和“关系”（如：用于图像分类）。
- 检索时，它不仅通过向量寻找节点，还会顺着图谱的“边”进行多跳推理（Multi-hop Reasoning），将关联的子图整个提取出来。
- **优势**：极大地提升了对复杂问题、全局总结性问题以及需要跨文档推理问题的回答质量。

## 9.5 A3 项目中的 RAG 应用案例
在 A3 个性化学习多智能体系统中，RAG 是构建可信教育环境的核心底座：
1. **课程章节检索**：Course_Expert Agent 在回答前，必须严格从 `knowledge_base` 的 Markdown 文件中检索相关内容，禁止脱离讲义自由发挥。
2. **错题归因支撑**：当学生做错题时，Evaluator Agent 会利用 RAG 检索该题考察的知识点对应的内容，向学生精确指出“你没有掌握教材第 9 章第 2 节的这个公式”。
3. **知识库溯源徽章**：前端界面为每个生成的解答都配备了“溯源徽章”。学生点击徽章，屏幕侧边栏会立刻滑出对应的原文段落，极大地增强了系统的学术严谨性与信任感。

## 9.6 常见误区
- **误区 1：只要检索到了相关内容，LLM 就一定能给出正确答案。**
  - **为什么错**：LLM 依然可能患有“注意力不集中”症。如果检索回来的 Top-5 块中有 4 块是无关的噪声，只有 1 块包含正确答案，LLM 很可能会被噪声误导而生成错误信息。因此，重排序（Reranking）非常重要。
- **误区 2：为了让大模型懂我们的私有知识，必须用这些数据微调（Fine-Tuning）模型，RAG 只是辅助。**
  - **为什么错**：微调是用来改变模型说话“风格”和“格式”的，让模型通过微调记住具体的知识（如公司财报、特定教材）既昂贵又极易遗忘，而且无法溯源。引入私有知识，RAG 才是首选方案。
- **误区 3：Chunk 切得越长，包含的信息越多，效果肯定越好。**
  - **为什么错**：Chunk 越长，其对应的向量语义就越模糊（平均化）。这会导致检索时的相似度计算不准确，反而把真正精准的小段落淹没掉。

## 9.7 可运行示例：使用标准库实现简化版 TF-IDF 检索
为了理解检索的最基本原理，我们不依赖任何第三方向量库（如 Chroma），仅使用 Python 标准库中的 `math` 和 `collections` 实现一个简化版的 TF-IDF（词频-逆文档频率）检索系统。虽然生产环境常用稠密向量检索，但 TF-IDF 这种稀疏检索至今在关键词匹配上仍具奇效。

```python
import math
from collections import Counter
import re

class SimpleTFIDFRetriever:
    def __init__(self):
        self.documents = []
        self.vocab = set()
        self.doc_tf = []      # 每篇文档的词频
        self.idf = {}         # 逆文档频率
        
    def _tokenize(self, text):
        # 简单分词：按字切分，过滤标点
        text = re.sub(r'[^\w\s]', '', text)
        return [char for char in text.replace(" ", "")]

    def add_documents(self, docs):
        self.documents = docs
        N = len(docs)
        doc_word_counts = []
        
        # 计算 TF (Term Frequency)
        for doc in docs:
            tokens = self._tokenize(doc)
            self.vocab.update(tokens)
            counter = Counter(tokens)
            # 归一化 TF = 该词出现次数 / 文档总词数
            tf = {k: v / len(tokens) for k, v in counter.items()}
            self.doc_tf.append(tf)
            doc_word_counts.append(set(tokens))
            
        # 计算 IDF (Inverse Document Frequency)
        for word in self.vocab:
            # 包含该词的文档数
            doc_count = sum(1 for d_words in doc_word_counts if word in d_words)
            # IDF 公式: log(文档总数 / (包含该词的文档数 + 1))
            self.idf[word] = math.log(N / (doc_count + 1))

    def retrieve(self, query, top_k=2):
        query_tokens = self._tokenize(query)
        scores = []
        
        for i, tf in enumerate(self.doc_tf):
            score = 0
            for q_word in query_tokens:
                if q_word in tf:
                    # TF * IDF
                    score += tf[q_word] * self.idf.get(q_word, 0)
            scores.append((score, self.documents[i]))
            
        # 按得分从高到低排序
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_k]

if __name__ == "__main__":
    docs = [
        "RAG的核心是检索和生成。检索负责找资料，生成负责总结回答。",
        "Transformer架构完全抛弃了RNN，利用自注意力机制实现了并行计算。",
        "在A3项目中，我们给知识库的内容打上标签，方便前端展示溯源徽章。",
        "多模态大模型可以同时处理文本、图像和语音信息。"
    ]
    
    retriever = SimpleTFIDFRetriever()
    retriever.add_documents(docs)
    
    query = "A3系统的溯源功能是怎么做的？"
    results = retriever.retrieve(query, top_k=2)
    
    print(f"提问: {query}\n")
    print("TF-IDF 检索结果 (Top-2):")
    for rank, (score, doc) in enumerate(results):
        print(f"{rank+1}. 得分: {score:.4f} | 内容: {doc}")
```

## 9.8 本章小结
1. RAG 系统通过“检索+生成”架构，有效抑制了 LLM 的事实幻觉，使得 AI 回答拥有可验证的信源。
2. 一个完整的 RAG 流水线必须经过精细的文档清洗与分块，依赖高质量的 Embedding 和检索算法，并配以重排序来提纯上下文。
3. 参数如 Chunk size 和 Top-k 极大影响检索质量，需要在“语义完整”与“噪声控制”之间找到平衡。
4. GraphRAG 通过引入知识图谱，打破了纯文本片段的孤岛，赋予系统全局理解与多跳推理的能力。
5. 在教育系统如 A3 项目中，RAG 的“溯源徽章”是建立师生信任、支撑学习辅导的刚需机制。

## 9.11 可运行代码示例

下面用 Python 标准库实现一个迷你 RAG 检索流程：分词 → TF-IDF 索引 → 余弦相似度 → Top-K。完全零依赖。

```python
'''09 章 · 简化版 RAG 检索流程 (TF-IDF) — 标准库实现'''
import math
import re
from collections import Counter

# 1. 文档库（实际场景从 knowledge_base/ 加载）
docs = [
    "Transformer 使用 Self-Attention 机制建模序列依赖。",
    "反向传播通过链式法则逐层计算梯度。",
    "卷积神经网络擅长图像特征提取。",
    "RAG 检索增强生成结合检索与生成。",
    "强化学习通过奖励信号优化策略。",
]

# 2. 简单分词
def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,。、]+", text) if t]

# 3. 构建 TF-IDF 索引
def build_index(docs: list[str]) -> tuple[list[Counter], dict[str, float], list[set]]:
    tokenized = [tokenize(d) for d in docs]
    df: dict[str, int] = {}
    for tokens in tokenized:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    idf = {t: math.log((n + 1) / (df_t + 1)) + 1 for t, df_t in df.items()}
    tfidf = []
    for tokens in tokenized:
        tf = Counter(tokens)
        vec = {t: tf[t] * idf[t] for t in tf}
        tfidf.append(vec)
    return tfidf, idf, [set(t) for t in tokenized]

# 4. 余弦相似度
def cosine(a: dict, b: dict) -> float:
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    den = math.sqrt(sum(v*v for v in a.values())) * math.sqrt(sum(v*v for v in b.values()))
    return num / den if den else 0.0

# 5. 向量化查询
def query_to_vec(q: str, idf: dict[str, float]) -> dict:
    tokens = tokenize(q)
    tf = Counter(tokens)
    return {t: tf[t] * idf.get(t, 0) for t in tf}

# === 主流程 ===
tfidf, idf, _ = build_index(docs)

def retrieve(query: str, top_k: int = 3) -> list[tuple[int, float, str]]:
    qv = query_to_vec(query, idf)
    scored = [(i, cosine(qv, dv), docs[i]) for i, dv in enumerate(tfidf)]
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]

# 演示检索
queries = ["Self-Attention 怎么工作？", "RAG 的核心思想", "图像识别用什么模型？"]
for q in queries:
    print(f"\nQ: {q}")
    for idx, score, text in retrieve(q):
        print(f"  [{score:.3f}] (doc#{idx}) {text}")

# 实际 RAG：拿到 Top-K 文本后拼到 LLM prompt 里
print("\n→ Top-K 文本将作为 context 拼入 LLM 的 prompt，生成最终回答。")
```
\n## 9.9 练习思考
1. **策略选择**：假设你要处理一份包含大量复杂数学公式的 PDF 教材。在“文档加载与清洗”以及“分块”这两个步骤中，你可能会遇到什么困难？该如何解决？
2. **性能优化**：如果系统发现在召回阶段（Top-50）其实包含了正确答案，但 LLM 最终拿到的 Top-5 却都是无关内容，流水线中哪个环节出了问题？应如何改进？
3. **架构扩展**：在 A3 系统的场景下，为什么“混合检索（向量相似度 + 关键词 BM25）”往往比单纯的向量检索效果更好？举例说明。
4. **机制对比**：如果用户问：“请帮我把本课程提到的所有 AI 发展史按时间轴总结一下”。普通 RAG 和 GraphRAG 在处理这个问题时的表现会有何不同？

## 9.10 拓展阅读
- RAG 综述论文：检索关键词 `Retrieval-Augmented Generation for Large Language Models: A Survey`
- GraphRAG 微软开源项目论文：检索关键词 `From Local to Global: A Graph RAG Approach to Query-Focused Summarization`
- 文档解析与向量库工具生态：了解 `LangChain`、`LlamaIndex` 以及开源向量库 `ChromaDB` 和 `Milvus` 的官方文档。
