---
chapter_id: '06'
slug: multi_agent_systems
title: 多智能体系统
kp_ids:
- AI_012
bloom_focus:
- Analyze
- Create
prerequisites:
- '10'
estimated_minutes: 45
---

# 06: 多智能体系统（Multi-Agent System） · 复杂任务的协同破局

> **Bloom 层级**: Analyze → Create
> **建议学时**: 45 分钟
> **前置知识**: 10-AI Agent

## 学习目标
1. 区分单 Agent 与多 Agent 的核心差异及其在教育场景中的局限性与优势。
2. 识别并设计多智能体系统中的关键角色分工（如 planner、tutor、course_expert 等）。
3. 应用常见的协作模式（串行流水线、并行协作、仲裁器、反思改写）解决特定学习任务。
4. 建立应对多智能体协作中冲突与一致性问题（观点/事实冲突、工具失败、超时降级）的策略。
5. 通过自包含代码模拟多个 Agent 处理学生请求的过程。

## 6.1 单 Agent 与多 Agent 的区别
**直觉解释**：单 Agent 就像一位“全科家教”，什么都要管；多 Agent 就像一个“教研团队”，有课程专家、出题专家、学习规划师和评估专家。

- **单 Agent 局限性**：当把 LLM 当成“全能助手”时，所有指令和工具都会塞进一个庞大的 System Prompt 中。这不仅会导致上下文超长，还会引起“角色定位漂移”——在处理复杂任务时，模型可能在“生成讲解”和“更新画像”之间顾此失彼，导致每件事都做得平庸。
- **多 Agent 优势**：通过角色拆分，每个 Agent 拥有独立的 Prompt、特定的工具集和聚焦的子目标。这样可以极大地降低单个模型的推理负担，并支持并行处理，提高系统稳定性和响应速度。

## 6.2 多智能体角色分工
在 A3 个性化学习系统中，我们设计了明确的角色分工，每个角色各司其职：
- **Planner (规划师)**：总控中枢，负责意图识别、任务拆解和路由调度。
- **Course_Expert (课程专家)**：通过 RAG 检索知识库，提供事实准确的知识点讲解。
- **Tutor (辅导员)**：根据学生画像，用苏格拉底式提问或生动的比喻与学生互动。
- **Quiz (题库专家)**：根据知识点和学生的 Bloom 层级，动态生成或推荐练习题。
- **Multimodal (多模态专家)**：把文本讲解转化为思维导图代码、语音 (TTS) 或配图描述。
- **Evaluator (评估专家)**：批改学生答案，分析错误原因。
- **Profile (画像专家)**：默默在后台分析学生的交互记录，更新学生的知识掌握状态（BKT）和学习偏好。

## 6.3 协作模式
多智能体协同并不是简单的堆砌，而是需要精密的编排协议：
1. **串行流水线 (Pipeline)**：任务流转如同工厂流水线。例如：`Profile` 读取偏好 -> `Course_Expert` 生成大纲 -> `Quiz` 生成题目。
2. **并行协作 (Parallel)**：当任务互不依赖时同时执行。例如，生成文本讲解的同时，让 `Multimodal` Agent 去生成配图，最后在前端合并。
3. **仲裁器 (Arbitrator)**：当多个 Agent 的输出需要综合时，由仲裁器负责整合。例如，综合多个专家的建议输出最终的学习方案。
4. **反思改写 (Reflection)**：生成-评估-修正循环。例如，`Course_Expert` 输出讲解后，`Evaluator` 检查是否符合学生年级，如果不符合则打回要求 `Course_Expert` 重写。

## 6.4 冲突与一致性管理
在复杂的协同中，不同 Agent 之间难免出现冲突，必须设计系统级的容错和仲裁机制：
- **观点冲突**：比如 `Tutor` 认为学生该复习，而 `Planner` 认为该学新课。**对策**：引入基于优先级的仲裁器（Arbitrator），如规定 `Planner` 的系统级指令优先级最高。
- **事实冲突**：不同 Agent 检索到了冲突的知识。**对策**：要求所有事实性陈述必须附带知识库溯源引用（Citation），以底层 `knowledge_base` 的信息为唯一 Truth。
- **工具失败**：当某个 Agent 调用的外部 API（如代码执行沙盒）失败时。**对策**：不应让整个系统崩溃，而是捕获异常，并由该 Agent 向 `Planner` 返回明确的错误码。
- **超时降级**：某个 Agent 推理过慢。**对策**：设置严格的 Timeout。超时后，系统切断该 Agent 的执行，切换到备用小模型或返回默认的 Mock 数据以保证用户体验。

## 6.5 教育场景案例：“我不懂 RAG”
**场景描述**：学生在界面中输入“我不懂 RAG 是什么，能给我讲讲吗？”
**A3 项目多 Agent 协作流程**：
1. **Planner** 识别到用户意图为“知识点讲解”，将任务分解。
2. **Profile** 并行读取该学生的数据，发现其“喜欢生动的比喻”且“刚学完向量”。
3. **Course_Expert** 使用 RAG 检索课程库中的 `09_rag.md`，提取 RAG 的定义和步骤。
4. **Tutor** 接收到 Profile 和 Course_Expert 的输入，生成讲解：“RAG 就像是开卷考试。你之前学的向量就是书里的索引...”
5. **Multimodal** 并行工作，将 RAG 的流程（检索、拼接、生成）转化为一张 Mermaid 流程图代码。
6. **Quiz** 预生成一道关于 RAG 的难度为 `Understand` 的判断题备用。
7. **Planner** 将 Tutor、Multimodal 和 Quiz 的结果打包返回给前端展示，并通知 Profile 记录“学生发起了对 RAG 的提问”。

## 6.6 常见误区
- **误区 1：多智能体就是写个 for 循环多次调用同一个模型。**
  - **为什么错**：多智能体的核心在于**异构性**和**角色分工**。每个 Agent 应该有独立的 Prompt 设定、不同的工具权限，甚至底层可以使用不同尺寸的模型（例如 Planner 用 GPT-4，Profile 用小模型）。
- **误区 2：系统里 Agent 角色越多，系统就越聪明。**
  - **为什么错**：角色越多意味着通信开销呈指数级上升，且更容易陷入死循环或无意义的互相闲聊。优秀的系统应遵循“奥卡姆剃刀”原则，保留最少且必要的 Agent。
- **误区 3：没有状态管理，直接把上一个 Agent 的输出扔给下一个。**
  - **为什么错**：这会导致上下文断裂和回答割裂。必须有统一的 State / Context 对象在 Agent 之间流转，记录 `session_id`、`history` 和 `profile`，以维持全局一致性。

## 6.7 可运行示例：模拟 Agent 流水线处理请求
以下是一个自包含的 Python 示例，演示如何用代码组织一个简单的多 Agent 流水线（Pipeline）来处理同一个学习请求。为了能够离线运行，我们将模型调用替换为了简单的字符串处理和逻辑模拟。

```python
import time

class BaseAgent:
    def __init__(self, name):
        self.name = name

    def execute(self, state: dict) -> dict:
        print(f"[{self.name}] 开始处理...")
        time.sleep(0.5) # 模拟推理耗时
        return self._process(state)
        
    def _process(self, state: dict) -> dict:
        raise NotImplementedError

class ProfileAgent(BaseAgent):
    def _process(self, state: dict) -> dict:
        # 模拟读取数据库
        student_id = state.get("student_id")
        state["profile"] = {"preference": "通俗比喻", "level": "初学者"}
        print(f"  -> 获取到学生画像: {state['profile']}")
        return state

class ExpertAgent(BaseAgent):
    def _process(self, state: dict) -> dict:
        query = state.get("query", "")
        # 模拟检索知识库
        if "RAG" in query.upper():
            state["knowledge"] = "RAG全称检索增强生成，分为检索、上下文拼接、生成三步。"
        else:
            state["knowledge"] = "未找到相关知识点。"
        print(f"  -> 检索到专业知识: {state['knowledge']}")
        return state

class TutorAgent(BaseAgent):
    def _process(self, state: dict) -> dict:
        knowledge = state.get("knowledge", "")
        pref = state.get("profile", {}).get("preference", "")
        
        # 模拟基于画像的文本生成
        if pref == "通俗比喻":
            state["reply"] = f"老师来给你打个比方！{knowledge} 简单来说，这就像是开卷考试带着小抄进考场！"
        else:
            state["reply"] = f"以下是标准解释：{knowledge}"
            
        print(f"  -> 生成定制回复: {state['reply']}")
        return state

class MultiAgentPipeline:
    def __init__(self, agents):
        self.agents = agents
        
    def run(self, initial_state: dict) -> dict:
        current_state = initial_state
        for agent in self.agents:
            current_state = agent.execute(current_state)
        return current_state

if __name__ == "__main__":
    print("=== A3 学习请求处理开始 ===")
    request_state = {
        "student_id": "STU_001",
        "query": "我不懂什么是RAG，能讲讲吗？"
    }
    
    # 编排流水线：画像 -> 专家检索 -> 辅导员生成
    pipeline = MultiAgentPipeline(agents=[
        ProfileAgent("画像专家"),
        ExpertAgent("课程专家"),
        TutorAgent("辅导员智能体")
    ])
    
    final_state = pipeline.run(request_state)
    print("=== 处理完成 ===")
    print(f"最终输出给学生的回复: {final_state['reply']}")
```

## 6.8 本章小结
1. 单 Agent 面临角色漂移和上下文压力；多智能体通过专业化分工（Planner、Tutor、Quiz 等）降低单个模型的负担。
2. 协同需要设计合理的架构（串行流水线、并行协作、仲裁器）与统一的状态管理机制。
3. 冲突与容错（超时降级、事实仲裁）是保证教育级多智能体系统可用性的关键防线。
4. 在 A3 系统中，多个 Agent 无缝配合，能够将一个简单的学生提问转化为包含讲解、多模态展示和题目练习的综合学习体验。

## 6.11 可运行代码示例

下面模拟一个三角色多 Agent 流水线：研究 Agent → 编程 Agent → 评审 Agent。每轮迭代产出一份草稿 + 反馈，直到评审通过。

```python
'''06 章 · 多 Agent 消息传递模拟 — 3 个角色协作完成一道编程题'''
import random
from dataclasses import dataclass, field

random.seed(11)

@dataclass
class Message:
    sender: str
    receiver: str
    content: str

@dataclass
class Agent:
    name: str
    role: str
    inbox: list = field(default_factory=list)

    def send(self, other: 'Agent', content: str):
        msg = Message(self.name, other.name, content)
        other.inbox.append(msg)
        print(f"  [{self.name} -> {other.name}] {content[:80]}")

researcher = Agent("Researcher", "研究")
coder      = Agent("Coder",      "编程")
reviewer   = Agent("Reviewer",   "评审")

TASK = "用 Python 写一个快速排序"
print(f"任务: {TASK}\n")

# Round 1
researcher.send(coder, f"研究：{TASK} 的关键步骤是分治 + 递归。")
coder.send(reviewer, "草稿 v1:\ndef qs(a):\n    if len(a)<=1: return a\n    p=a[0]; return qs([x for x in a[1:] if x<p])+[p]+qs([x for x in a[1:] if x>=p])")
reviewer.send(coder, "评审：OK 通过。")

# Round 2 (不同任务，看流水线复用)
TASK2 = "实现 LRU 缓存"
print(f"\n任务: {TASK2}\n")
researcher.send(coder, f"研究：{TASK2} 用 OrderedDict 或双向链表 + 哈希表。")
coder.send(reviewer, "草稿 v1:\nfrom collections import OrderedDict\nclass LRU(OrderedDict):\n    def get(self,k):\n        if k in self: self.move_to_end(k); return self[k]\n    def put(self,k,v):\n        self[k]=v; self.move_to_end(k);\n        if len(self)>self.cap: self.popitem(last=False)")
reviewer.send(coder, "评审：通过，注意线程安全。")

print(f"\n消息总线统计: 研究 {len(researcher.inbox)}, 编程 {len(coder.inbox)}, 评审 {len(reviewer.inbox)}")
```
\n## 6.9 练习思考
1. **角色设计**：如果要在 A3 系统中加入一个“情绪安抚 Agent”，它应该在流水线的哪个位置介入？它的输入和输出分别应该包含什么？
2. **容错机制**：假设并行协作中，`Multimodal Agent` 因为代码沙盒崩溃导致生成思维导图超时。系统此时该怎么做才不会让用户一直看着加载动画？
3. **架构辨析**：比较“基于规则的意图路由”与“利用 LLM 自动规划任务链路”这两种方式的优缺点，A3 项目为何选择混合使用？
4. **反思改写**：请设计一个具体的场景，说明 `Evaluator` 如何通过反思机制让 `Course_Expert` 修改其输出。

## 6.10 拓展阅读
- 相关框架检索：`AutoGen: Enabling Next-Gen LLM Applications`、`LangGraph framework`
- 多智能体教育应用：搜索 `Multi-Agent System for Personalized E-learning` 相关综述。
- 架构模式：查阅吴恩达 (Andrew Ng) 关于 `Agentic Design Patterns` (反思、工具使用、规划、多智能体协作) 的系列讲座。
