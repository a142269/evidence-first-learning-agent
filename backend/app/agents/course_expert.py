"""
课程专家 Agent —— 生成讲解文档和拓展阅读材料

对应赛题需求2（资源生成）：专业课程讲解文档、拓展阅读材料
"""
from __future__ import annotations

import logging
from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse

logger = logging.getLogger(__name__)


class CourseExpertAgent(BaseAgent):
    """课程专家 —— 基于课程知识库生成讲解文档和拓展阅读"""

    @property
    def name(self) -> str:
        return "course_expert"

    @property
    def description(self) -> str:
        return "基于课程知识库生成专业讲解文档和拓展阅读材料"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名经验丰富的大学教授，擅长将复杂知识讲解得通俗易懂。\n\n"
            "你的任务是根据学生的需求，生成高质量的课程讲解文档。\n\n"
            "要求：\n"
            "1. 内容结构清晰：使用标题、小标题、列表组织\n"
            "2. 由浅入深：先给出核心概念，再展开细节\n"
            "3. 注重举例：用生动的例子帮助理解\n"
            "4. 个性化适配：根据学生画像调整难度和风格\n"
            "5. 输出格式：Markdown 格式，包含适当的代码块和公式\n"
            "6. 关联知识：在文末提供相关知识点的拓展方向\n"
            "7. 如果有 RAG 检索到的课程材料，优先参考这些材料\n"
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """生成课程讲解文档"""
        # 构建融合画像 + RAG 的 prompt
        user_prompt = self._build_prompt(context)

        result = await self._acall_llm(
            user_prompt=user_prompt,
            history=context.conversation_history,
            extra_system=self._strategy_extra_system(context),
            temperature=0.5,
        )

        return self._success(
            content=result,
            content_type="markdown",
            resources=[{
                "type": "document",
                "title": f"课程讲解：{context.user_input[:30]}",
                "format": "markdown",
            }],
        )

    def _build_prompt(self, context: AgentContext) -> str:
        parts = [f"学生请求：{context.user_input}\n"]

        if context.profile:
            level = context.profile.get("knowledge_base", {}).get("level", "未知")
            pref = context.profile.get("learning_preference", {})
            parts.append(f"学生知识水平：{level}")
            if pref:
                parts.append(f"学习偏好：{pref}")

        if context.rag_results:
            parts.append("\n## 课程知识库参考材料")
            for i, doc in enumerate(context.rag_results[:5], 1):
                parts.append(f"[参考 {i}] {doc.get('content', '')[:500]}")

        parts.append("\n请基于以上信息生成详细的课程讲解文档。")
        return "\n".join(parts)
