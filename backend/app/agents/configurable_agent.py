"""ConfigurableAgent — 统一执行教师配置的 Agent。

教师不上传任意 Python 代码；新 Agent 完全由配置驱动：
name / title / system_prompt / capabilities / allowed_tools / enabled。
Orchestrator 识别 @Agent名称 命中配置型 Agent 后，实例化本类执行。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.app.agents.base import AgentContext, AgentResponse, BaseAgent
from backend.app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "你是一名高校课程学习助手，请用简体中文、Markdown 格式回答学生问题，"
    "回答需准确、结构清晰，不编造事实。"
)


class ConfigurableAgent(BaseAgent):
    """配置驱动的通用 Agent —— 由 AgentConfigRecord 决定人设与提示词。"""

    prompt_version = "cfg-v1"

    def __init__(self, config: Dict[str, Any], llm_client: Optional[LLMClient] = None):
        super().__init__(llm_client=llm_client)
        self._config = dict(config or {})

    @property
    def name(self) -> str:
        return str(self._config.get("key") or "configurable")

    @property
    def display_name(self) -> str:
        return str(self._config.get("name") or self.name)

    @property
    def description(self) -> str:
        caps = "、".join(self._config.get("capabilities") or [])
        return str(self._config.get("role_desc") or "") + (f"（能力：{caps}）" if caps else "")

    @property
    def system_prompt(self) -> str:
        prompt = str(self._config.get("system_prompt") or "").strip()
        base = prompt or _DEFAULT_SYSTEM_PROMPT
        persona = (
            f"你的名字是「{self.display_name}」"
            f"{('，身份是' + str(self._config.get('title'))) if self._config.get('title') else ''}。"
        )
        caps = self._config.get("capabilities") or []
        caps_line = f"你擅长：{'、'.join(str(c) for c in caps)}。" if caps else ""
        return f"{persona}{caps_line}\n{base}"

    async def execute(self, context: AgentContext) -> AgentResponse:
        if not self._config.get("enabled", True):
            return self._error("agent_disabled")

        rag_block = ""
        for item in (context.rag_results or [])[:3]:
            # FIX-06（2026-07-17）：主 RAG 的正文字段是 content（兼容旧 text），
            # 此前只读 text 导致配置型 Agent 拿不到任何检索正文。
            text = str(item.get("content") or item.get("text") or "")[:600]
            if text:
                source = str(item.get("source") or "").strip()
                rag_block += f"\n---\n来源：{source}\n{text}" if source else f"\n---\n{text}"
        extra_system = (
            f"以下是课程知识库中检索到的参考资料，回答时可引用：{rag_block}"
            if rag_block
            else ""
        )

        try:
            content = await self._acall_llm(
                context.user_input,
                history=context.conversation_history,
                extra_system=extra_system,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("[ConfigurableAgent:%s] LLM 调用失败: %s", self.name, exc)
            return self._error(str(exc))

        if not (content or "").strip():
            return self._error("empty_llm_response")

        return self._success(
            content,
            content_type="markdown",
            metadata={
                "configurable": True,
                "agent_key": self.name,
                "agent_display_name": self.display_name,
                "agent_title": self._config.get("title", ""),
            },
        )
