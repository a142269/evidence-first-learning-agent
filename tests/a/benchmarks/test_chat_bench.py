"""
性能基准测试: Orchestrator + LLM Client

基线保存: pytest tests/a/benchmarks/ --benchmark-save=baseline
回退检测: pytest tests/a/benchmarks/ --benchmark-compare=baseline --benchmark-columns=min,max,mean,median

Phase 0 目标: 建立初始基线值，不做性能 SLO 判定。
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

from backend.app.agents.orchestrator import AgentOrchestrator, AgentTask, AgentStatus
from backend.app.agents.base import AgentContext, AgentResponse
from backend.app.core.llm_client import LLMClient
from backend.app.core.config import AppConfig


# ================================================================
# Fixtures
# ================================================================
@pytest.fixture
def bench_llm():
    """Mock 模式的 LLMClient"""
    config = AppConfig.from_env()
    config.llm.spark_app_id = ""
    config.llm.openai_base_url = ""
    return LLMClient(config=config.llm)


@pytest.fixture
def bench_orchestrator(bench_llm):
    """含 mock Agent 的 Orchestrator"""
    profile_mock = MagicMock()
    profile_mock_instance = MagicMock()
    profile_mock_instance.name = "profile"
    profile_mock.return_value = profile_mock_instance
    profile_mock_instance.execute = AsyncMock(
        return_value=AgentResponse(agent_name="profile", success=True, content="ok")
    )

    course_mock = MagicMock()
    course_mock_instance = MagicMock()
    course_mock_instance.name = "course_expert"
    course_mock.return_value = course_mock_instance
    course_mock_instance.execute = AsyncMock(
        return_value=AgentResponse(agent_name="course_expert", success=True, content="ok")
    )

    registry = {"profile": profile_mock, "course_expert": course_mock, "tutor": course_mock}
    return AgentOrchestrator(llm_client=bench_llm, agent_registry=registry)


# ================================================================
# Benchmarks
# ================================================================
def test_llm_mock_chat_latency(bench_llm, benchmark):
    """Mock chat 延迟基线"""
    msgs = [
        {"role": "system", "content": "你是课程专家"},
        {"role": "user", "content": "讲解卷积神经网络"},
    ]

    def run():
        return bench_llm._mock_chat(msgs)

    result = benchmark(run)
    assert len(result) > 100


@pytest.mark.asyncio
async def test_orchestrator_process_turn_latency(bench_orchestrator, benchmark):
    """Orchestrator 单轮 process_turn 延迟"""
    async def run():
        return await bench_orchestrator.process_turn(
            user_input="给我讲解CNN",
            profile={},
            context={"session_id": "bench"},
        )

    result = await benchmark(run)
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_orchestrator_classify_intent_latency(bench_orchestrator, benchmark):
    """意图分类延迟（异步版）"""
    async def run():
        return await bench_orchestrator._classify_intent("给我讲解CNN然后出几道题", {})

    intents = await benchmark(run)
    # 当前是同步规则匹配，预期 <1ms
    assert "profile_update" in intents


def test_agent_context_creation(benchmark):
    """AgentContext 创建开销"""
    def run():
        return AgentContext(
            user_input="讲解 CNN",
            session_id="s1",
            profile={"kb": "mid"},
            course_name="ai",
        )

    ctx = benchmark(run)
    assert ctx.course_name == "ai"
