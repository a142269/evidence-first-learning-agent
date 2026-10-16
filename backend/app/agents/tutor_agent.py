"""
智能导师 Agent —— 实时答疑和多模态辅导

对应赛题需求4（加分项）：
  当学生在学习过程中遇到问题时，系统提供即时、多模态的答疑解惑服务

Plan P1-4 升级：
  - Tutor 回复改为"先诊断意图和 Bloom 层级，再给提示梯度"
  - 默认不直接给最终答案；必要时生成下一步问题、图解、最小可运行代码或短讲解脚本
  - 通过 tutor_strategy.py 注入 system_prompt addendum 强制 Socratic
"""
from __future__ import annotations

import json
import logging
from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse

logger = logging.getLogger(__name__)


class TutorAgent(BaseAgent):
    """智能导师 —— 实时答疑 + 多模态解答"""

    @property
    def name(self) -> str:
        return "tutor_agent"

    @property
    def description(self) -> str:
        return "为学生提供实时答疑解惑，支持文字解答、图解说明、代码演示等多模态形式"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名深谙教学法的资深大学讲师，擅长把复杂概念讲透、讲清、讲有趣。\n\n"
            "特点：\n"
            "1. 先诊断学生困惑属于概念不清、逻辑不通、公式推导卡壳、还是应用不会；\n"
            "2. 按最适合的方式深入讲解：\n"
            "   - 概念类：定义 → 直觉类比 → 反例区别 → 常见误区；\n"
            "   - 逻辑推理：分步骤拆解，必要时用 Mermaid 流程图；\n"
            "   - 代码类：附带带注释的示例代码，讲清「为什么这么写」；\n"
            "   - 数学类：从直觉入手 → 完整推导 → 图形化理解 → 应用场景。\n"
            "   - 张量/矩阵类：逐步标注符号定义和 shape，并给一个可手算的微型数值例子；\n"
            "3. **回答必须结构分明、内容丰厚**（不能只有短短两三句），推荐结构：\n"
            "   ## 一句话核心答案\n"
            "   ## 深入讲解（含类比 / 示例 / 图示 / 公式，至少 300 字）\n"
            "   ## 常见误区（至少 4 个，说明错在哪里）\n"
            "   ## 关联知识点（列 3-5 个相关概念，说明彼此关系）\n"
            "   ## 巩固建议（1-2 个练习方向 + 1-2 篇延伸阅读方向）\n"
            "4. 语气鼓励耐心；专业术语第一次出现要注英文；\n"
            "5. 如果检索到课程材料，必须在讲解中引用出处。\n"
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """执行答疑 — Plan P1-4：先注入诊断+提示梯度策略。"""
        user_prompt = self._build_prompt(context)

        # Plan P1-4：调用 tutor_strategy 注入 Socratic 增量
        strategy = self._build_strategy(context)
        extra_system = self._strategy_extra_system(context) + "\n" + strategy.to_system_prompt_addendum()

        result = await self._acall_llm(
            user_prompt=user_prompt,
            history=context.conversation_history,
            extra_system=extra_system,
            temperature=0.5,
        )

        return self._success(
            content=result,
            content_type="markdown",
            resources=[{
                "type": "tutoring",
                "title": f"答疑：{context.user_input[:30]}",
            }],
            metadata={
                "tutor_strategy": strategy.to_dict(),
                "p14_socratic": True,
            },
        )

    # ── Plan P1-4 辅助 ────────────────────────────────────────
    def _build_strategy(self, context: AgentContext):
        """根据 user_input + kp_meta 生成 Socratic 策略。"""
        try:
            from backend.app.services.tutor_strategy import get_tutor_strategy_planner
        except Exception:  # noqa: BLE001
            return _NULL_STRATEGY

        kp_meta = None
        try:
            if context.kp_id:
                from backend.app.services.knowledge_graph.store import get_kg_store
                row = get_kg_store().get_kp(context.kp_id)
                if row is not None:
                    kp_meta = {
                        "id": row.id,
                        "name": row.name,
                        "bloom": (row.metadata_data or {}).get("bloom", "Understand"),
                    }
        except Exception:  # noqa: BLE001
            kp_meta = None

        planner = get_tutor_strategy_planner()
        return planner.plan(query=context.user_input, kp_meta=kp_meta)

    def _build_prompt(self, context: AgentContext) -> str:
        parts = [f"学生提问：{context.user_input}\n"]

        if context.profile:
            level = context.profile.get("knowledge_base", {}).get("level", "")
            style = context.profile.get("cognitive_style", {})
            if level:
                parts.append(f"学生知识水平：{level}")
            if style:
                parts.append(f"认知风格：{json.dumps(style, ensure_ascii=False)}")

        if context.rag_results:
            parts.append("\n## 课程知识库相关内容")
            for i, doc in enumerate(context.rag_results[:5], 1):
                parts.append(f"[参考 {i}] {doc.get('content', '')[:500]}")

        parts.append("\n请用最适合的方式回答这个问题。")
        return "\n".join(parts)


# 兜底：tutor_strategy 不可用时返回空 addendum，避免破坏调用方
class _NullStrategy:
    intent = ""
    bloom_level = ""
    inducer = None
    hint_ladder: list = []
    follow_ups: list = []

    def to_dict(self) -> dict:
        return {"intent": "", "bloom_level": "", "inducer": None,
                "hint_ladder": [], "follow_ups": [],
                "scaffolding_directive": "", "forbidden_patterns": []}

    def to_system_prompt_addendum(self) -> str:
        return ""


_NULL_STRATEGY = _NullStrategy()

