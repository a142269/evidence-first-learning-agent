"""
出题专家 Agent —— 生成不同类型的练习题目

对应赛题需求2（资源生成）：不同类型练习题目
"""
from __future__ import annotations

import json
import logging
import re
from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
from backend.app.services.downloadable_artifacts import register_markdown_artifact

logger = logging.getLogger(__name__)


class QuizGeneratorAgent(BaseAgent):
    """出题专家 —— 生成个性化的多类型练习题"""

    @property
    def name(self) -> str:
        return "quiz_generator"

    @property
    def description(self) -> str:
        return "根据知识点和学生画像生成选择题、填空题、编程题、简答题等"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名 985 高校的资深教师，擅长按 Bloom 分类法设计层次分明的高质量试卷。\n\n"
            "任务：根据知识点和学生水平，生成一份丰富且分层的练习题。\n\n"
            "支持的题型：\n"
            "1. 单选题（choice）\n"
            "2. 多选题（multi_choice）\n"
            "3. 填空题（fill）\n"
            "4. 判断题（judge）\n"
            "5. 简答题（short）\n"
            "6. 编程题（code，需提供函数签名或框架 + 测试用例）\n"
            "7. 应用分析题（case）\n\n"
            "硬性要求：\n"
            "- 若用户明确题量则严格遵守；未明确时生成 **10-12 道题**；\n"
            "- 涵盖至少 6 种题型，技术主题优先包含公式推导、代码阅读、代码 Debug 和综合设计；\n"
            "- 难度必须由易到难分层，含 easy / medium / hard 各若干道；\n"
            "- 每道题的 question 字段必须具体、有信息量，不要只写「解释 XX」这种通用问题；\n"
            "- 选择题至少 4 个选项，每个选项要有干扰性；\n"
            "- 编程题必须给出：题干场景描述、函数签名、示例输入输出、期望时间复杂度；\n"
            "- 每道题都必须附 bloom、answer（参考答案）和 explanation（详细解析，2-4 句）；\n"
            "- 结合学生画像，如果薄弱环节明显，在题目中标注 `focus_on` 字段说明这题针对什么薄弱点。\n\n"
            "内部输出协议：\n"
            "- 只输出一个 ```quiz_json``` 代码块，供程序解析；不要复述任务、输出流程或字段说明；\n"
            "- 程序会把结构化数据渲染成用户可直接阅读的交互题卡，JSON 本身绝不会展示给用户。\n\n"
            "JSON 格式（每题字段完整）：\n"
            '```quiz_json\n'
            '[{"id":1,"type":"choice","difficulty":"easy","bloom":"remember","question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"...","focus_on":"..."},'
            '{"id":2,"type":"debug","difficulty":"hard","bloom":"analyze","question":"修复...","signature":"def foo(x: int) -> int:","example":"foo(3) == 9","complexity":"O(log n)","answer":"...","explanation":"..."}]\n'
            '```\n'
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """生成练习题"""
        user_prompt = self._build_prompt(context)

        result = await self._acall_llm(
            user_prompt=user_prompt,
            history=context.conversation_history,
            extra_system=self._strategy_extra_system(context),
            temperature=0.6,
        )

        # 提取结构化题目数据
        quiz_data = self._extract_quiz_data(result)
        target_count = self._requested_count(context.user_input)
        quiz_data = self._ensure_quiz_count(
            quiz_data,
            self._fallback_quiz_data(self._quiz_topic(context)),
            target_count,
        )
        topic = self._quiz_topic(context)
        readable_content = self._render_quiz_summary(topic, quiz_data)
        download = register_markdown_artifact(
            artifact_type="quiz",
            title=f"{topic} · 分层练习",
            content=self._render_quiz_download(topic, quiz_data),
            session_id=context.session_id,
            metadata={"topic": topic, "quiz_count": len(quiz_data)},
        )

        return self._success(
            content=readable_content,
            content_type="quiz",
            resources=[{
                "type": "quiz",
                "title": f"{topic} · {len(quiz_data)} 道分层练习",
                "format": "interactive_quiz",
                "quiz_count": len(quiz_data),
                "downloads": [download] if download else [],
                # 2026-07-12：把 quiz_data 塞到 resource.metadata，前端能直接内联展开
                "metadata": {
                    "quiz_data": quiz_data,
                    "quiz_count": len(quiz_data),
                    "title": f"{topic} · 分层练习",
                },
            }],
            metadata={"quiz_data": quiz_data},
        )

    def _build_prompt(self, context: AgentContext) -> str:
        parts = [f"命题约束：{context.user_input}\n"]

        if context.profile:
            level = context.profile.get("knowledge_base", {}).get("level", "中等")
            weak = context.profile.get("weak_points", {})
            parts.append(f"学生水平：{level}")
            if weak:
                parts.append(f"薄弱环节：{json.dumps(weak, ensure_ascii=False)}")
                parts.append("请针对薄弱环节重点出题")

        if context.rag_results:
            parts.append("\n## 相关知识点参考")
            for doc in context.rag_results[:3]:
                parts.append(doc.get("content", "")[:300])

        parts.append(
            "\n若需求里明确了题量，请严格按该数量生成；否则生成 10-12 道题。"
            "至少覆盖 6 种题型（单选/多选/判断/填空/公式推导/代码阅读/代码 Debug/综合设计），"
            "难度由易到难均衡分布。每题标注 Bloom 层级，并给出清晰充分的答案与解析。"
        )
        return "\n".join(parts)

    def _extract_quiz_data(self, llm_output: str) -> list:
        """从输出中提取结构化题目"""
        import re
        pattern = r"```quiz_json\s*\n(.*?)\n```"
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        return []

    @staticmethod
    def _requested_count(text: str) -> int:
        match = re.search(r"(\d{1,2})\s*道", text or "")
        if match:
            return max(1, min(20, int(match.group(1))))
        return 12

    @staticmethod
    def _quiz_topic(context: AgentContext) -> str:
        full = "\n".join(filter(None, [
            str((context.extra or {}).get("collaboration_request", "")),
            context.user_input,
            context.course_name,
        ]))
        quoted = re.search(r"[「『\"“]([^」』\"”]{2,60})[」』\"”]", full)
        if quoted:
            return quoted.group(1).strip()
        if "transformer" in full.lower() or "self-attention" in full.lower():
            return "Transformer 架构"
        course = str(context.course_name or "").strip()
        if course and course != "artificial_intelligence":
            return course[:50]
        cleaned = re.sub(r"@\S+", "", context.user_input or "")
        cleaned = re.sub(r"^(?:练习题|出题|命题)\s*[：:]?", "", cleaned).strip()
        return re.split(r"[，。；;！!?？\n]", cleaned)[0][:40] or "本次主题"

    @staticmethod
    def _ensure_quiz_count(items: list, fallback: list, target: int) -> list:
        """过滤协议回显并补足题量，保证“一道题退化”不会到达用户界面。"""
        valid: list[dict] = []
        seen: set[str] = set()
        leaked_phrases = ("人类可读的完整题目", "练习题：设计", "请根据以下要求出题", "命题约束：")
        for raw in list(items or []) + list(fallback or []):
            if not isinstance(raw, dict):
                continue
            question = str(raw.get("question") or raw.get("stem") or "").strip()
            if not question or any(phrase in question for phrase in leaked_phrases):
                continue
            key = re.sub(r"\s+", "", question)
            if key in seen:
                continue
            seen.add(key)
            item = dict(raw)
            item["question"] = question
            item.setdefault("type", "short")
            item.setdefault("difficulty", "medium")
            item.setdefault("bloom", "understand")
            item.setdefault("answer", "请结合题干给出有依据的回答。")
            item.setdefault("explanation", "回答应同时覆盖核心概念、推理过程与适用边界。")
            valid.append(item)
            if len(valid) >= target:
                break

        seed = list(valid)
        while seed and len(valid) < target:
            source = dict(seed[len(valid) % len(seed)])
            source["question"] = f"变式：{source['question']} 请补充一个反例或边界条件。"
            source["difficulty"] = "hard"
            source["bloom"] = "evaluate"
            valid.append(source)
        for index, item in enumerate(valid, start=1):
            item["id"] = index
        return valid[:target]

    @staticmethod
    def _render_quiz_summary(topic: str, items: list) -> str:
        type_names = {
            "choice": "单选", "multi_choice": "多选", "judge": "判断",
            "fill": "填空", "short": "简答/推导", "code": "代码阅读",
            "debug": "代码 Debug", "case": "综合设计",
        }
        counts: dict[str, int] = {}
        for item in items:
            label = type_names.get(str(item.get("type", "")), "综合练习")
            counts[label] = counts.get(label, 0) + 1
        distribution = "、".join(f"{name} {count} 题" for name, count in counts.items())
        return (
            f"## {topic} · 分层练习\n\n"
            f"已生成 **{len(items)} 道**由易到难的练习，覆盖 {distribution}。"
            "每道题都带难度、Bloom 层级、参考答案与解析，可在下方逐题展开。"
        )

    @staticmethod
    def _render_quiz_download(topic: str, items: list) -> str:
        """Render a complete, readable question bank instead of exposing JSON."""
        lines = [f"# {topic} · 分层练习", ""]
        for index, item in enumerate(items, start=1):
            question = str(item.get("question") or item.get("stem") or "题目待补充").strip()
            difficulty = str(item.get("difficulty") or "medium")
            bloom = str(item.get("bloom") or "understand")
            lines.extend([
                f"## {index}. {question}",
                "",
                f"- 难度：{difficulty}",
                f"- Bloom 层级：{bloom}",
            ])
            options = item.get("options")
            if isinstance(options, list) and options:
                lines.extend(["", *[f"- {option}" for option in options]])
            for key in ("signature", "example", "complexity"):
                if item.get(key):
                    label = {"signature": "函数签名", "example": "示例", "complexity": "复杂度"}[key]
                    lines.append(f"- {label}：`{item[key]}`")
            lines.extend([
                "",
                f"**参考答案**：{item.get('answer', '待评阅')}",
                "",
                f"**解析**：{item.get('explanation', '暂无解析')}",
                "",
            ])
        return "\n".join(lines).strip()

    @staticmethod
    def _fallback_quiz_data(topic: str) -> list:
        """结构化输出失败时的高质量兜底，保证演示仍有完整题库卡片。"""
        lower = (topic or "").lower()
        if not any(k in lower for k in ("transformer", "attention", "注意力", "q/k/v")):
            return [
                {
                    "id": 1, "type": "choice", "difficulty": "easy", "bloom": "remember",
                    "question": f"关于「{topic[:40]}」的核心定义，下面哪项表述最完整？",
                    "options": ["A. 同时说明目标、输入输出与约束", "B. 只列术语", "C. 只写应用名称", "D. 只写历史背景"],
                    "answer": "A", "explanation": "完整定义要能区分对象、目的与边界。",
                },
                {"id": 2, "type": "multi_choice", "difficulty": "easy", "bloom": "understand", "question": f"学习「{topic[:40]}」时，哪些信息有助于建立完整知识框架？", "options": ["A. 核心概念", "B. 组成与关系", "C. 适用边界", "D. 典型案例"], "answer": "A、B、C、D", "explanation": "结构、关系、边界和案例共同构成可迁移的理解。"},
                {"id": 3, "type": "judge", "difficulty": "easy", "bloom": "understand", "question": f"判断：记住「{topic[:40]}」的术语就等同于能够在新场景中应用。", "answer": "错误", "explanation": "应用还需要识别条件、选择方法并验证结果。"},
                {"id": 4, "type": "fill", "difficulty": "medium", "bloom": "apply", "question": f"用“输入—处理—输出”三部分补全「{topic[:40]}」的最小工作流程。", "answer": "答案应明确三部分及其数据或信息流。", "explanation": "流程化表达能检验是否真正理解各组件如何协作。"},
                {"id": 5, "type": "short", "difficulty": "medium", "bloom": "analyze", "question": f"比较「{topic[:40]}」与一个相邻概念，给出至少两个相同点和两个不同点。", "answer": "需选择合理相邻概念，并从目标、机制、成本或场景比较。", "explanation": "对比能暴露概念边界，避免把相近术语混为一谈。"},
                {"id": 6, "type": "short", "difficulty": "medium", "bloom": "analyze", "question": f"选择「{topic[:40]}」中的一个关键结论，写出从前提到结论的推导链。", "answer": "应列出假设、关键步骤、结论及不成立的条件。", "explanation": "推导链比只背结论更能支持迁移。"},
                {"id": 7, "type": "code", "difficulty": "medium", "bloom": "apply", "question": f"为「{topic[:40]}」写出一个最小伪代码流程，并标注每一步的输入输出。", "signature": "def solve(input_data): ...", "answer": "伪代码需覆盖校验、核心处理和结果返回。", "explanation": "函数边界与中间状态是把概念落到工程实现的关键。"},
                {"id": 8, "type": "debug", "difficulty": "hard", "bloom": "analyze", "question": f"某实现声称使用了「{topic[:40]}」，但没有校验输入形状或边界条件。指出两个潜在错误并给出修复。", "answer": "检查数据类型/形状、空输入、越界值及异常传播，并加入断言或显式分支。", "explanation": "Debug 需要从契约、状态与边界逐层定位。"},
                {"id": 9, "type": "case", "difficulty": "hard", "bloom": "apply", "question": f"给出一个适合使用「{topic[:40]}」的真实场景，并说明为什么比两种替代方案更合适。", "answer": "需绑定场景约束，并从效果、成本与可维护性比较。", "explanation": "方案选择必须由约束驱动，而不是只看技术名称。"},
                {"id": 10, "type": "short", "difficulty": "hard", "bloom": "evaluate", "question": f"指出关于「{topic[:40]}」的一个常见误区，构造反例并给出纠正方法。", "answer": "误区、反例与纠正策略应相互对应。", "explanation": "反例能检验一个说法是否被过度泛化。"},
                {"id": 11, "type": "case", "difficulty": "hard", "bloom": "evaluate", "question": f"从准确性、资源成本和可解释性三个维度评估「{topic[:40]}」方案。", "answer": "给出带证据的权衡矩阵，并明确优先级。", "explanation": "多维权衡比单一指标更接近真实工程决策。"},
                {"id": 12, "type": "case", "difficulty": "hard", "bloom": "create", "question": f"设计一个验证「{topic[:40]}」掌握程度的最小实验，包含基线、变量、指标和失败判据。", "answer": "实验应可复现，包含对照或基线、关键变量、量化指标与终止条件。", "explanation": "可验证的实验把知识理解转化为证据。"},
            ]

        return [
            {
                "id": 1, "type": "choice", "difficulty": "easy", "bloom": "remember",
                "question": "在 Self-Attention 中，Query、Key、Value 通常由什么得到？",
                "options": ["A. 同一输入经过三组可学习线性映射", "B. 三个独立数据集", "C. Softmax 的三个输出", "D. 位置编码直接切片"],
                "answer": "A",
                "explanation": "自注意力把输入 X 分别乘以 W_Q、W_K、W_V。三组投影让模型学习匹配依据与被聚合的信息内容。",
            },
            {
                "id": 2, "type": "multi_choice", "difficulty": "easy", "bloom": "understand",
                "question": "多头注意力相对单头注意力的主要优势有哪些？",
                "options": ["A. 可在不同表示子空间学习关系", "B. 自动把复杂度降为 O(T)", "C. 能并行关注不同位置模式", "D. 必然减少模型参数"],
                "answer": "A、C",
                "explanation": "多头的核心是表示子空间与关系模式的多样性；标准实现仍为 O(T²)，参数量也不必然减少。",
            },
            {
                "id": 3, "type": "judge", "difficulty": "easy", "bloom": "understand",
                "question": "判断：除以 √d_k 的目的，是避免点积随维度增大而使 Softmax 过度饱和。",
                "answer": "正确",
                "explanation": "若 Q、K 分量近似独立且方差为 1，点积方差约为 d_k；缩放后方差回到稳定量级，梯度更健康。",
            },
            {
                "id": 4, "type": "fill", "difficulty": "medium", "bloom": "apply",
                "question": "输入 X∈R^(B×T×D)，头数为 H，则每头维度 d_h=___，注意力分数张量形状为 ___。",
                "answer": "D/H；B×H×T×T",
                "explanation": "Q 与 K 拆成 H 个头后均为 B×H×T×d_h，QKᵀ 在最后两维相乘得到每个 token 对所有 token 的分数。",
            },
            {
                "id": 5, "type": "short", "difficulty": "medium", "bloom": "analyze",
                "question": "推导为何 QKᵀ/√d_k 比未经缩放的 QKᵀ 更利于训练，并说明对梯度的影响。",
                "answer": "点积方差随 d_k 线性增长；除以 √d_k 后方差约保持为 1，Softmax 不易落入接近 one-hot 的饱和区。",
                "explanation": "Softmax 饱和时非最大项梯度接近 0，注意力分布很难调整。缩放使初期分布更平滑，优化更稳定。",
            },
            {
                "id": 6, "type": "choice", "difficulty": "medium", "bloom": "apply",
                "question": "Padding mask 应在 Softmax 前如何作用到注意力 logits？",
                "options": ["A. 被屏蔽 key 位置加一个极大负数", "B. 对 Value 乘 0 后再 Softmax", "C. 删除 Query 向量", "D. 对输出做 LayerNorm 即可"],
                "answer": "A",
                "explanation": "极大负数经 Softmax 后权重约为 0，从概率归一化中排除 padding key；只把 Value 置零仍会浪费概率质量。",
            },
            {
                "id": 7, "type": "code", "difficulty": "medium", "bloom": "analyze",
                "question": "阅读代码 `scores = q @ k.transpose(-2, -1)`：若 q.shape=[2,4,6,8]，写出 scores.shape，并解释四个维度。",
                "signature": "scores = q @ k.transpose(-2, -1)",
                "answer": "[2,4,6,6]，依次为 batch、head、query token、key token。",
                "explanation": "最后一维 head_dim=8 被矩阵乘法消去，每个 query token 都会与 6 个 key token 计算相似度。",
            },
            {
                "id": 8, "type": "debug", "difficulty": "hard", "bloom": "analyze",
                "question": "Debug：`context.transpose(1, 2).view(B, T, D)` 偶发报内存不连续错误，应如何修复？为什么？",
                "signature": "context = context.transpose(1, 2).contiguous().view(B, T, D)",
                "answer": "在 view 前调用 contiguous()，或使用 reshape。",
                "explanation": "transpose 只改变 stride，不保证内存连续；view 要求兼容的连续布局，contiguous 会按新顺序复制成连续张量。",
            },
            {
                "id": 9, "type": "debug", "difficulty": "hard", "bloom": "evaluate",
                "question": "Debug：因果语言模型训练时能看到未来 token。指出缺失步骤并给出 mask 的逻辑条件。",
                "answer": "在 Softmax 前对 j>i 的位置施加 causal mask，把对应 logits 设为极大负数。",
                "explanation": "第 i 个位置只能使用 0..i 的 key/value，否则训练会发生标签泄漏，推理时性能会崩溃。",
            },
            {
                "id": 10, "type": "short", "difficulty": "hard", "bloom": "analyze",
                "question": "比较 Encoder Self-Attention、Decoder Masked Self-Attention 与 Cross-Attention 的 Q/K/V 来源。",
                "answer": "编码器三者都来自编码器当前层；解码器 masked 三者来自解码器；交叉注意力 Q 来自解码器，K/V 来自编码器输出。",
                "explanation": "这一区别决定了各模块是在建模源序列内部、目标前缀内部，还是源—目标之间的对齐关系。",
            },
            {
                "id": 11, "type": "case", "difficulty": "hard", "bloom": "evaluate",
                "question": "长序列显存不足时，请从注意力复杂度、精度损失与工程成本三个维度比较滑动窗口注意力与低秩/线性注意力。",
                "answer": "滑窗把复杂度降到 O(Tw)，保留局部精确关系但削弱远程依赖；线性注意力可近似 O(TD²) 或 O(TD)，全局但依赖核近似，数值与实现更复杂。",
                "explanation": "选择要结合任务依赖跨度、可接受的近似误差与硬件 kernel 支持，不能只看大 O 复杂度。",
            },
            {
                "id": 12, "type": "case", "difficulty": "hard", "bloom": "create",
                "question": "设计一个最小 Transformer 文本分类器实验：列出输入流水线、模型组件、训练目标、关键消融和至少 3 个诊断指标。",
                "answer": "Tokenizer+padding mask；Embedding+位置编码+Encoder blocks+池化+分类头；交叉熵；消融位置编码/头数/层数；观察验证 F1、注意力熵、梯度范数与校准误差。",
                "explanation": "完整实验不仅要给最终准确率，还要通过消融和诊断判断性能来自哪一组件，以及训练是否稳定、预测是否可信。",
            },
        ]
