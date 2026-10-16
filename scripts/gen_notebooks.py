"""
为 A3 项目生成 6 个 Jupyter Notebook (P0 6 章节)
每个 notebook 包含: 简介 markdown + 核心代码 + 解读 + 练习扩展
"""
import os
import json

OUT = r"F:\比赛\中软杯\A3\data\code_examples"
os.makedirs(OUT, exist_ok=True)


def make_notebook(cells, kernel="python3"):
    """构造一个 .ipynb 文件结构"""
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": kernel},
            "language_info": {"name": "python", "version": "3.9"}
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }


def md_cell(source):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source if isinstance(source, list) else [source]
    }


def code_cell(source):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source if isinstance(source, list) else [source]
    }


# ============= Notebook 1: 05 Transformer =============
nb1 = make_notebook([
    md_cell([
        "# 05 Transformer 与大语言模型 · 代码示例\n",
        "\n",
        "**章节**: 05_transformer_and_llm.md\n",
        "**学习目标**: 亲手跑通一个简化版 Self-Attention 权重计算\n",
        "**A3 关联**: A3 系统的多智能体「大脑」基于 Transformer 架构\n",
        "\n",
        "运行本 notebook 需要 numpy。在 A3 项目中,我们用同样的原理做 Embedding、向量检索。"
    ]),
    code_cell([
        "import numpy as np\n",
        "\n",
        "def softmax(x):\n",
        "    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))\n",
        "    return e_x / e_x.sum(axis=-1, keepdims=True)\n",
        "\n",
        "def simplified_self_attention(X, W_q, W_k, W_v):\n",
        "    Q = np.dot(X, W_q)\n",
        "    K = np.dot(X, W_k)\n",
        "    V = np.dot(X, W_v)\n",
        "    d_k = Q.shape[-1]\n",
        "    scores = np.dot(Q, K.T) / np.sqrt(d_k)\n",
        "    weights = softmax(scores)\n",
        "    output = np.dot(weights, V)\n",
        "    return weights, output"
    ]),
    md_cell([
        "### 解读\n",
        "\n",
        "- `Q/K/V` 三个矩阵由输入 `X` 与权重矩阵相乘得到,代表查询、键、值\n",
        "- `QK^T / sqrt(d_k)` 是注意力得分的核心公式,除以根号 d_k 防止数值爆炸\n",
        "- `softmax` 把分数归一化为概率分布,每行加起来等于 1\n",
        "- 最终输出 = 注意力权重 × V,即对每个位置的 V 加权求和"
    ]),
    code_cell([
        "np.random.seed(42)\n",
        "X = np.random.randn(4, 8)        # 4 个词,每个 8 维\n",
        "W_q = np.random.randn(8, 4)\n",
        "W_k = np.random.randn(8, 4)\n",
        "W_v = np.random.randn(8, 4)\n",
        "\n",
        "weights, out = simplified_self_attention(X, W_q, W_k, W_v)\n",
        "print(\"注意力权重矩阵 (4x4):\")\n",
        "print(np.round(weights, 2))\n",
        "print(\"\\n每行和:\", weights.sum(axis=1).round(2))"
    ]),
    md_cell([
        "### 拓展练习\n",
        "\n",
        "1. 试着把 `d_model` 改为 16,观察权重矩阵的分布是否更平滑\n",
        "2. 实现 Multi-Head 版本:把 `d_model` 切成 4 个头,每个头独立计算注意力后拼接\n",
        "3. 在 A3 系统中,这个简化版注意力可以用作 RAG 检索的「轻量级 Embedding」\n"
    ])
])
with open(os.path.join(OUT, "ch05_transformer.ipynb"), "w", encoding="utf-8") as f:
    json.dump(nb1, f, ensure_ascii=False, indent=1)


# ============= Notebook 2: 06 Multi-Agent =============
nb2 = make_notebook([
    md_cell([
        "# 06 多智能体系统 · 代码示例\n",
        "\n",
        "**章节**: 06_multi_agent_systems.md\n",
        "**学习目标**: 模拟 Planner / Tutor / Evaluator 三个 Agent 协作\n",
        "**A3 关联**: 模拟 A3 系统的虚拟教师团队"
    ]),
    code_cell([
        "class Blackboard:\n",
        "    \"\"\"共享黑板,所有 Agent 通过它通信\"\"\"\n",
        "    def __init__(self):\n",
        "        self.state = {}\n",
        "    def write(self, key, value):\n",
        "        self.state[key] = value\n",
        "    def read(self, key, default=None):\n",
        "        return self.state.get(key, default)\n",
        "\n",
        "class TutorAgent:\n",
        "    def process(self, bb):\n",
        "        topic = bb.read(\"topic\")\n",
        "        bb.write(\"material\", f\"[{topic}] 的简化讲解:核心要点 1, 2, 3\")\n",
        "        return bb\n",
        "\n",
        "class EvaluatorAgent:\n",
        "    def process(self, bb):\n",
        "        # 简单判定: 长度超过 10 个字就算 PASSED\n",
        "        material = bb.read(\"material\", \"\")\n",
        "        bb.write(\"eval_status\", \"PASSED\" if len(material) > 10 else \"REJECTED\")\n",
        "        return bb\n",
        "\n",
        "class PlannerAgent:\n",
        "    def __init__(self):\n",
        "        self.tutor = TutorAgent()\n",
        "        self.evaluator = EvaluatorAgent()\n",
        "    def run(self, topic):\n",
        "        bb = Blackboard()\n",
        "        bb.write(\"topic\", topic)\n",
        "        for retry in range(3):\n",
        "            self.tutor.process(bb)\n",
        "            self.evaluator.process(bb)\n",
        "            if bb.read(\"eval_status\") == \"PASSED\":\n",
        "                return bb.read(\"material\")\n",
        "        return \"FAILED: 达到最大重试次数\""
    ]),
    md_cell([
        "### 解读\n",
        "\n",
        "- `Blackboard`: 全局共享状态,所有 Agent 读写同一份数据\n",
        "- `TutorAgent`: 写讲解材料\n",
        "- `EvaluatorAgent`: 审核材料是否合格\n",
        "- `PlannerAgent`: 串行调度,失败时重试,达到上限后降级返回"
    ]),
    code_cell([
        "planner = PlannerAgent()\n",
        "result = planner.run(\"Transformer 注意力机制\")\n",
        "print(\"最终输出:\", result)"
    ]),
    md_cell([
        "### 拓展练习\n",
        "\n",
        "1. 给 Evaluator 加一个「超长」判定,材料字数过多也 REJECTED\n",
        "2. 增加一个 ProfileAgent,在 Planner 调度前先读取「学生掌握度」\n",
        "3. 把 Blackboard 改成 dict 列表,记录每次交互历史,方便事后审计"
    ])
])
with open(os.path.join(OUT, "ch06_multi_agent.ipynb"), "w", encoding="utf-8") as f:
    json.dump(nb2, f, ensure_ascii=False, indent=1)


# ============= Notebook 3: 08 Multimodal =============
nb3 = make_notebook([
    md_cell([
        "# 08 多模态大模型 · 代码示例\n",
        "\n",
        "**章节**: 08_multimodal_llm.md\n",
        "**学习目标**: 模拟「把同一知识点转成多种资源描述」的流程\n",
        "**A3 关联**: A3 系统的多模态资源生成(文字/思维导图/语音/代码)"
    ]),
    code_cell([
        "from collections import Counter\n",
        "import re\n",
        "\n",
        "KNOWLEDGE_POINT = {\n",
        "    \"name\": \"Transformer 自注意力\",\n",
        "    \"definition\": \"Self-Attention 通过 Q/K/V 三个向量计算序列中任意两个位置的关联度。\",\n",
        "    \"analogy\": \"想象一个鸡尾酒会,你能自动过滤噪声,聚焦当前说话的人。\",\n",
        "    \"formula\": \"Attention(Q,K,V) = softmax(QKᵀ/√d_k)V\"\n",
        "}\n",
        "\n",
        "def gen_text_explanation(kp):\n",
        "    return f\"{kp['name']}:{kp['definition']}\"\n",
        "\n",
        "def gen_mindmap_code(kp):\n",
        "    return f\"\"\"```mermaid\n",
        "mindmap\n",
        "  root(({kp['name']}))\n",
        "    定义\n",
        "      ::icon(fa fa-book)\n",
        "      {kp['definition'][:20]}\n",
        "    直觉\n",
        "      {kp['analogy'][:20]}\n",
        "    公式\n",
        "      {kp['formula']}\n",
        "```\"\"\"\n",
        "\n",
        "def gen_quiz(kp):\n",
        "    return {\n",
        "        \"stem\": f\"请解释 {kp['name']} 的核心思想。\",\n",
        "        \"bloom\": \"Understand\",\n",
        "        \"answer\": kp['definition']\n",
        "    }\n",
        "\n",
        "def gen_audio_script(kp):\n",
        "    return f\"【停顿】同学们好,今天我们学习 {kp['name']}。{kp['analogy']}【停顿】\""
    ]),
    md_cell([
        "### 解读\n",
        "\n",
        "- `gen_text_explanation`: 生成文字讲解\n",
        "- `gen_mindmap_code`: 生成 Mermaid 思维导图代码(可在前端渲染)\n",
        "- `gen_quiz`: 生成 Bloom 层级题目\n",
        "- `gen_audio_script`: 生成 TTS 朗读脚本(对应 voice_scripts/)"
    ]),
    code_cell([
        "print(\"=== 文字讲解 ===\")\n",
        "print(gen_text_explanation(KNOWLEDGE_POINT))\n",
        "\n",
        "print(\"\\n=== 思维导图代码 ===\")\n",
        "print(gen_mindmap_code(KNOWLEDGE_POINT))\n",
        "\n",
        "print(\"\\n=== 题目 ===\")\n",
        "print(gen_quiz(KNOWLEDGE_POINT))\n",
        "\n",
        "print(\"\\n=== 语音脚本 ===\")\n",
        "print(gen_audio_script(KNOWLEDGE_POINT))"
    ]),
    md_cell([
        "### 拓展练习\n",
        "\n",
        "1. 增加 `gen_manim_script` 函数,输出一个 Manim 动画代码片段\n",
        "2. 根据 Bloom 层级动态调整 gen_quiz 的难度(Remember/Apply/Create)\n",
        "3. 把所有 gen 函数改造成「流水线」,支持链式调用"
    ])
])
with open(os.path.join(OUT, "ch08_multimodal.ipynb"), "w", encoding="utf-8") as f:
    json.dump(nb3, f, ensure_ascii=False, indent=1)


# ============= Notebook 4: 09 RAG =============
nb4 = make_notebook([
    md_cell([
        "# 09 检索增强生成 (RAG) · 代码示例\n",
        "\n",
        "**章节**: 09_rag.md\n",
        "**学习目标**: 跑通一个 TF-IDF 简化版 RAG 检索器\n",
        "**A3 关联**: A3 系统的「知识库溯源」功能核心"
    ]),
    code_cell([
        "from sklearn.feature_extraction.text import TfidfVectorizer\n",
        "from sklearn.metrics.pairwise import cosine_similarity\n",
        "import numpy as np\n",
        "\n",
        "# 模拟 A3 课程知识库 chunk\n",
        "documents = [\n",
        "    \"Transformer 使用 Self-Attention 机制实现并行计算,解决 RNN 长程遗忘。\",\n",
        "    \"过拟合指模型在训练集表现好但在测试集表现差,可通过正则化缓解。\",\n",
        "    \"多智能体系统由 Planner、Tutor、Evaluator 等多个 Agent 协作完成任务。\",\n",
        "    \"RAG 通过检索外部知识库来缓解大模型幻觉,并支持答案溯源。\",\n",
        "    \"BKT 模型用贝叶斯更新追踪学生在每个知识点上的掌握度。\"\n",
        "]\n",
        "\n",
        "def rag_retrieve(query, docs, top_k=2):\n",
        "    vectorizer = TfidfVectorizer()\n",
        "    tfidf = vectorizer.fit_transform(docs + [query])\n",
        "    doc_vecs = tfidf[:-1]\n",
        "    query_vec = tfidf[-1]\n",
        "    sims = cosine_similarity(query_vec, doc_vecs).flatten()\n",
        "    top_idx = np.argsort(sims)[::-1][:top_k]\n",
        "    return [(docs[i], sims[i]) for i in top_idx]"
    ]),
    md_cell([
        "### 解读\n",
        "\n",
        "- 把所有文档和查询一起向量化,确保在同一个词表空间\n",
        "- 计算查询向量与每个文档的余弦相似度\n",
        "- 取 top_k 个最相关的文档作为召回结果"
    ]),
    code_cell([
        "queries = [\n",
        "    \"什么是 Self-Attention?\",\n",
        "    \"如何缓解过拟合?\",\n",
        "    \"A3 怎么用多个 AI 协作?\",\n",
        "    \"大模型为什么会胡说八道?\",\n",
        "    \"BKT 是怎么工作的?\"\n",
        "]\n",
        "\n",
        "for q in queries:\n",
        "    print(f\"\\n【提问】: {q}\")\n",
        "    results = rag_retrieve(q, documents)\n",
        "    for doc, score in results:\n",
        "        print(f\"  [相似度 {score:.3f}] {doc}\")"
    ]),
    md_cell([
        "### 拓展练习\n",
        "\n",
        "1. 改成基于 sentence-transformers 的版本,对比效果\n",
        "2. 加入 chunk overlap 切分,模拟真实 Markdown 章节切块\n",
        "3. 把召回结果塞进 Prompt,实现完整 RAG 闭环(不调大模型,只打印 prompt)"
    ])
])
with open(os.path.join(OUT, "ch09_rag.ipynb"), "w", encoding="utf-8") as f:
    json.dump(nb4, f, ensure_ascii=False, indent=1)


# ============= Notebook 5: 10 AI Agent =============
nb5 = make_notebook([
    md_cell([
        "# 10 AI Agent 智能体 · 代码示例\n",
        "\n",
        "**章节**: 10_ai_agent.md\n",
        "**学习目标**: 模拟一个 Plan-and-Execute 风格的简单 Agent\n",
        "**A3 关联**: 模拟 A3 系统 Planner Agent 的核心调度逻辑"
    ]),
    code_cell([
        "class SimpleAgent:\n",
        "    \"\"\"Plan-and-Execute 风格的简单 Agent\"\"\"\n",
        "    def __init__(self, name):\n",
        "        self.name = name\n",
        "        self.memory = []\n",
        "\n",
        "    def plan(self, goal):\n",
        "        \"\"\"把目标拆成步骤\"\"\"\n",
        "        if \"讲解\" in goal:\n",
        "            return [\"检索知识库\", \"生成讲解\", \"自评质量\"]\n",
        "        elif \"出题\" in goal:\n",
        "            return [\"读取掌握度\", \"选 Bloom 层级\", \"生成题目\"]\n",
        "        else:\n",
        "            return [\"理解目标\", \"执行\"]\n",
        "\n",
        "    def execute(self, step):\n",
        "        \"\"\"执行一步,返回结果\"\"\"\n",
        "        result = f\"[{self.name}] 已完成: {step}\"\n",
        "        self.memory.append(result)\n",
        "        return result\n",
        "\n",
        "    def run(self, goal):\n",
        "        print(f\"\\n[{self.name}] 收到目标: {goal}\")\n",
        "        plan = self.plan(goal)\n",
        "        print(f\"[{self.name}] 计划: {plan}\")\n",
        "        for step in plan:\n",
        "            result = self.execute(step)\n",
        "            print(f\"  -> {result}\")\n",
        "        return self.memory"
    ]),
    md_cell([
        "### 解读\n",
        "\n",
        "- `plan(goal)`: 根据目标字符串匹配不同的规划模板\n",
        "- `execute(step)`: 模拟执行一步,把结果记入 memory\n",
        "- `run(goal)`: 端到端跑完一个目标"
    ]),
    code_cell([
        "tutor = SimpleAgent(\"Tutor\")\n",
        "result = tutor.run(\"请讲解 Transformer 注意力机制\")\n",
        "print(\"\\n最终 memory:\", result)"
    ]),
    md_cell([
        "### 拓展练习\n",
        "\n",
        "1. 加入 reflection:每步执行后自我评估,失败则重新 plan\n",
        "2. 加入 tool calling:execute 可以调用外部 API(用伪函数代替)\n",
        "3. 实现 ReAct 模式:把 plan 和 execute 合并成 step,边想边做"
    ])
])
with open(os.path.join(OUT, "ch10_ai_agent.ipynb"), "w", encoding="utf-8") as f:
    json.dump(nb5, f, ensure_ascii=False, indent=1)


# ============= Notebook 6: 12 AI Project Practice =============
nb6 = make_notebook([
    md_cell([
        "# 12 AI 项目实战 · 代码示例\n",
        "\n",
        "**章节**: 12_ai_project_practice.md\n",
        "**学习目标**: 跑通 A3 系统的最小闭环伪代码\n",
        "**A3 关联**: 这是 A3 系统端到端流水线的代码骨架"
    ]),
    code_cell([
        "class A3MinimumLoop:\n",
        "    \"\"\"A3 个性化学习系统的最小可演示闭环\"\"\"\n",
        "    def __init__(self, student_id):\n",
        "        self.student_id = student_id\n",
        "        self.profile = {\"transformer\": 0.5, \"rag\": 0.3}\n",
        "\n",
        "    def retrieve(self, query):\n",
        "        return f\"[知识库召回] {query} 相关的章节内容\"\n",
        "\n",
        "    def generate_explanation(self, query, context, profile):\n",
        "        return f\"[Tutor 讲解] 基于 {context},学生当前掌握度 {profile}\"\n",
        "\n",
        "    def generate_quiz(self, topic, level):\n",
        "        return {\"stem\": f\"请简述 {topic} 的核心思想\", \"level\": level}\n",
        "\n",
        "    def evaluate(self, quiz, answer):\n",
        "        is_correct = \"简述\" in answer or len(answer) > 5\n",
        "        return is_correct, (\"回答正确\" if is_correct else \"未答到要点\")\n",
        "\n",
        "    def update_profile(self, topic, delta):\n",
        "        self.profile[topic] = max(0, min(1, self.profile.get(topic, 0.5) + delta))\n",
        "\n",
        "    def process_query(self, query):\n",
        "        # 1. 画像读取\n",
        "        # 2. 知识库检索\n",
        "        context = self.retrieve(query)\n",
        "        # 3. 个性化讲解\n",
        "        explanation = self.generate_explanation(query, context, self.profile)\n",
        "        # 4. 推送练习\n",
        "        quiz = self.generate_quiz(\"transformer\", self.profile[\"transformer\"])\n",
        "        return {\"explanation\": explanation, \"quiz\": quiz}"
    ]),
    md_cell([
        "### 解读\n",
        "\n",
        "A3 的最小闭环包含 6 步:画像 → 检索 → 讲解 → 出题 → 评估 → 画像更新\n",
        "\n",
        "本代码骨架省略了 LLM 调用(用字符串模拟),但保留了完整的数据流。\n",
        "在真实 A3 系统中,retrieve/evaluate/explanation 内部都会调用大模型 + RAG。"
    ]),
    code_cell([
        "a3 = A3MinimumLoop(student_id=\"demo-student-1\")\n",
        "\n",
        "# 模拟一次完整交互\n",
        "result = a3.process_query(\"我不懂注意力机制\")\n",
        "print(\"【讲解】:\", result[\"explanation\"])\n",
        "print(\"【题目】:\", result[\"quiz\"])\n",
        "\n",
        "# 模拟学生答题\n",
        "is_correct, feedback = a3.evaluate(result[\"quiz\"], \"注意力机制就是 QKV 三向量\")\n",
        "print(\"\\n【评估】:\", \"正确\" if is_correct else \"错误\", \"-\", feedback)\n",
        "\n",
        "# 画像更新\n",
        "delta = +0.1 if is_correct else -0.05\n",
        "a3.update_profile(\"transformer\", delta)\n",
        "print(\"\\n【新掌握度】 transformer =\", a3.profile[\"transformer\"])"
    ]),
    md_cell([
        "### 拓展练习\n",
        "\n",
        "1. 把所有方法内部改成调用真实 LLM(用伪函数代替)\n",
        "2. 增加一个 Evaluator Agent,模拟「二次评审」逻辑\n",
        "3. 给每一步加上耗时统计,输出响应时延报告"
    ])
])
with open(os.path.join(OUT, "ch12_ai_project.ipynb"), "w", encoding="utf-8") as f:
    json.dump(nb6, f, ensure_ascii=False, indent=1)


print("Wrote 6 Jupyter Notebooks:")
for f in sorted(os.listdir(OUT)):
    if f.endswith(".ipynb"):
        size = os.path.getsize(os.path.join(OUT, f))
        print(f"  {f:30s} {size:>6} B")
