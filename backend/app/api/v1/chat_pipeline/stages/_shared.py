"""
Stage 模块共享单例与工厂

从原 chat.py 模块级状态迁移. 测试时可通过 PipelineContext.services 注入替代。
"""
from __future__ import annotations

from typing import Optional

from backend.app.agents import AGENT_REGISTRY, AgentOrchestrator
from backend.app.core.llm_client import LLMClient
from backend.app.services.safety.content_filter import ContentSafetyChecker


_shared_llm: Optional[LLMClient] = None
_shared_orchestrator: Optional[AgentOrchestrator] = None
_shared_safety: Optional[ContentSafetyChecker] = None


def get_shared_llm() -> LLMClient:
    global _shared_llm
    if _shared_llm is None:
        _shared_llm = LLMClient()
    return _shared_llm


def get_shared_orchestrator() -> AgentOrchestrator:
    global _shared_orchestrator
    if _shared_orchestrator is None:
        _shared_orchestrator = AgentOrchestrator(
            llm_client=get_shared_llm(), agent_registry=AGENT_REGISTRY,
        )
    return _shared_orchestrator


def get_shared_safety() -> ContentSafetyChecker:
    global _shared_safety
    if _shared_safety is None:
        _shared_safety = ContentSafetyChecker()
    return _shared_safety


def reset_shared_state() -> None:
    """测试用: 重置全部全局单例"""
    global _shared_llm, _shared_orchestrator, _shared_safety
    _shared_llm = None
    _shared_orchestrator = None
    _shared_safety = None
