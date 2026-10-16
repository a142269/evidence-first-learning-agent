"""
测试: Agent 基类 (base.py)

覆盖:
- AgentContext 默认值和字段赋值
- AgentResponse 成功/失败构造
- BaseAgent._build_messages 标准/带历史/带额外系统提示
- BaseAgent._success / _error 快捷构造
"""
from __future__ import annotations

import pytest
from dataclasses import asdict

from backend.app.agents.base import AgentContext, AgentResponse, BaseAgent


# ================================================================
# Concrete Agent for testing BaseAgent
# ================================================================
class _TestAgent(BaseAgent):
    """最小化具体 Agent，用于测试基类方法"""

    @property
    def name(self) -> str:
        return "test_agent"

    @property
    def description(self) -> str:
        return "用于测试的 Agent"

    @property
    def system_prompt(self) -> str:
        return "你是一个测试助手，请如实回答问题。"

    async def execute(self, context: AgentContext) -> AgentResponse:
        return self._success("测试完成")


@pytest.fixture
def test_agent(mock_llm_client):
    """返回一个使用 Mock LLMClient 的 TestAgent"""
    return _TestAgent(llm_client=mock_llm_client)


# ================================================================
# AgentContext 测试
# ================================================================
class TestAgentContext:
    """AgentContext 数据类测试"""

    def test_default_values(self):
        """默认值：空字符串、空字典、空列表"""
        ctx = AgentContext()
        assert ctx.user_input == ""
        assert ctx.session_id == ""
        assert ctx.profile == {}
        assert ctx.course_name == ""
        assert ctx.conversation_history == []
        assert ctx.rag_results == []
        assert ctx.extra == {}

    def test_full_context(self, agent_context):
        """完整 AgentContext 各字段正确赋值"""
        assert agent_context.user_input == "请给我讲解一下卷积神经网络"
        assert agent_context.session_id == "test-session-001"
        assert agent_context.profile["knowledge_base"]["level"] == "入门"
        assert agent_context.course_name == "artificial_intelligence"
        assert len(agent_context.conversation_history) == 2
        assert agent_context.extra["strategy_prompt"].startswith("学生当前情绪积极")

    def test_extra_can_be_empty(self):
        """extra 为空字典时不应崩溃"""
        ctx = AgentContext(user_input="你好", extra={})
        assert ctx.extra == {}


# ================================================================
# AgentResponse 测试
# ================================================================
class TestAgentResponse:
    """AgentResponse 数据类测试"""

    def test_success_response(self):
        """成功响应包含 content 和 success=True"""
        resp = AgentResponse(
            agent_name="test",
            success=True,
            content="Hello World",
            content_type="markdown",
        )
        assert resp.success is True
        assert resp.content == "Hello World"
        assert resp.content_type == "markdown"
        assert resp.error == ""
        assert resp.resources == []

    def test_error_response(self):
        """失败响应包含 error 和 success=False"""
        resp = AgentResponse(
            agent_name="test",
            success=False,
            error="LLM 调用超时",
        )
        assert resp.success is False
        assert resp.error == "LLM 调用超时"
        assert resp.content == ""

    def test_with_resources(self):
        """响应可携带资源列表"""
        resp = AgentResponse(
            agent_name="course_expert",
            success=True,
            content="讲解文档内容...",
            resources=[
                {"id": "res-1", "type": "document", "title": "CNN 入门"},
                {"id": "res-2", "type": "mindmap", "title": "CNN 思维导图"},
            ],
        )
        assert len(resp.resources) == 2
        assert resp.resources[0]["type"] == "document"

    def test_with_profile_updates(self):
        """响应可携带画像更新"""
        resp = AgentResponse(
            agent_name="profile_agent",
            success=True,
            profile_updates={"knowledge_base": {"level": "进阶", "known_topics": ["CNN"]}},
        )
        assert resp.profile_updates["knowledge_base"]["level"] == "进阶"

    def test_with_metadata(self):
        """响应可携带 metadata"""
        resp = AgentResponse(
            agent_name="quiz_generator",
            success=True,
            metadata={
                "bloom_level": "apply",
                "kp_ids": ["kp_cnn", "kp_pooling"],
                "difficulty": "medium",
            },
        )
        assert resp.metadata["bloom_level"] == "apply"
        assert len(resp.metadata["kp_ids"]) == 2


# ================================================================
# BaseAgent._build_messages 测试
# ================================================================
class TestBuildMessages:
    """_build_messages 方法测试"""

    def test_standard(self, test_agent):
        """标准调用：system + user，无历史"""
        msgs = test_agent._build_messages("讲解 CNN")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "测试助手" in msgs[0]["content"]
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"] == "讲解 CNN"

    def test_with_history(self, test_agent):
        """带对话历史"""
        history = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ]
        msgs = test_agent._build_messages("Q3", history=history)
        # system + 4 history + 1 user = 6
        assert len(msgs) == 6
        assert msgs[1]["content"] == "Q1"
        assert msgs[2]["content"] == "A1"

    def test_history_truncated(self, test_agent):
        """长历史被截断到最近 10 条（5 轮）"""
        history = [{"role": "user", "content": f"Q{i}"} for i in range(30)]
        msgs = test_agent._build_messages("new Q", history=history)
        # system + 10 history + 1 user = 12
        assert len(msgs) == 12

    def test_with_extra_system(self, test_agent):
        """额外系统提示词追加到 system prompt 末尾"""
        msgs = test_agent._build_messages("问题", extra_system="【策略】语气温柔")
        system_content = msgs[0]["content"]
        assert "【策略】语气温柔" in system_content
        # 原始 system prompt 应该在前面
        assert "测试助手" in system_content

    def test_empty_extra_system(self, test_agent):
        """额外系统提示词为空时不影响"""
        msgs = test_agent._build_messages("问题", extra_system="")
        assert msgs[0]["role"] == "system"
        assert "测试助手" in msgs[0]["content"]


# ================================================================
# BaseAgent._success / _error 测试
# ================================================================
class TestSuccessError:
    """快捷构造方法测试"""

    def test_success_minimal(self, test_agent):
        resp = test_agent._success("完成")
        assert resp.agent_name == "test_agent"
        assert resp.success is True
        assert resp.content == "完成"
        assert resp.content_type == "markdown"

    def test_success_with_resources(self, test_agent):
        resp = test_agent._success(
            "文档内容",
            resources=[{"id": "r1", "type": "doc", "title": "T"}],
        )
        assert len(resp.resources) == 1

    def test_error(self, test_agent):
        resp = test_agent._error("出错了")
        assert resp.success is False
        assert resp.error == "出错了"
        assert resp.content == ""


# ================================================================
# BaseAgent._strategy_extra_system 测试
# ================================================================
class TestStrategyExtraSystem:
    """_strategy_extra_system 方法测试"""

    def test_with_strategy(self, test_agent, agent_context):
        extra = test_agent._strategy_extra_system(agent_context)
        assert extra.startswith("学生当前情绪积极")

    def test_no_strategy(self, test_agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(user_input="你好")
        extra = test_agent._strategy_extra_system(ctx)
        assert extra == ""

    def test_empty_extra(self, test_agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(user_input="你好", extra={})
        extra = test_agent._strategy_extra_system(ctx)
        assert extra == ""


# ================================================================
# 集成：完整 execute 流程
# ================================================================
@pytest.mark.asyncio
async def test_execute_with_context(test_agent, agent_context):
    """Agent.execute() 返回正确的 AgentResponse"""
    resp = await test_agent.execute(agent_context)
    assert resp.agent_name == "test_agent"
    assert resp.success is True

# ============================================================
# Plan D · 2.2 — 异步 LLM 调用验证
# ============================================================
class TestAsyncLLMCall:
    """Plan D · 2.2 验证 BaseAgent 的 _acall_llm 异步路径"""

    def test_acall_llm_method_exists(self, test_agent):
        """BaseAgent 必须暴露 _acall_llm 异步方法（且为 coroutinefunction）"""
        assert hasattr(test_agent, "_acall_llm")
        assert callable(test_agent._acall_llm)
        import inspect
        assert inspect.iscoroutinefunction(test_agent._acall_llm)

    def test_acall_llm_stream_method_exists(self, test_agent):
        """BaseAgent 必须暴露 _acall_llm_stream 异步生成器方法"""
        import inspect
        assert inspect.isasyncgenfunction(test_agent._acall_llm_stream)

    @pytest.mark.asyncio
    async def test_acall_llm_delegates_to_llm_achat(self):
        """_acall_llm 内部委托给 self.llm.achat()，不调用同步 .chat()"""
        from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
        from backend.app.core.llm_client import LLMClient

        class _Probe(BaseAgent):
            @property
            def name(self):
                return "probe"

            @property
            def description(self):
                return "probe"

            @property
            def system_prompt(self):
                return "probe"

            async def execute(self, context):
                return AgentResponse(agent_name="probe", success=True, content="ok")

        class _MockLLM:
            def __init__(self):
                self.chat_called = 0
                self.achat_called = 0

            def chat(self, messages, temperature=None):
                self.chat_called += 1
                return "sync-fallback"

            async def achat(self, messages, temperature=None):
                self.achat_called += 1
                return "async-result"

        mock = _MockLLM()
        agent = _Probe(llm_client=mock)
        result = await agent._acall_llm("user prompt")
        assert result == "async-result"
        assert mock.achat_called == 1
        assert mock.chat_called == 0  # 关键：异步方法不能调同步 .chat

    @pytest.mark.asyncio
    async def test_concurrent_acall_llm_is_concurrent(self):
        """并发 3 个 _acall_llm 应聚集在 ~1 个 mock 耗时，而不是 3 倍"""
        import asyncio
        import time
        from backend.app.agents.base import BaseAgent
        from backend.app.core.llm_client import LLMClient

        class _Slow(BaseAgent):
            @property
            def name(self):
                return "slow"

            @property
            def description(self):
                return "slow"

            @property
            def system_prompt(self):
                return "slow"

            async def execute(self, context):
                return None

        llm = LLMClient()

        async def patched_achat(messages, temperature=None, max_tokens=None):
            await asyncio.sleep(0.05)
            return "ok"

        llm.achat = patched_achat
        agent = _Slow(llm_client=llm)

        t0 = time.perf_counter()
        results = await asyncio.gather(
            agent._acall_llm("q1"),
            agent._acall_llm("q2"),
            agent._acall_llm("q3"),
        )
        elapsed = time.perf_counter() - t0

        assert results == ["ok", "ok", "ok"]
        # 串行需 3 * 0.05 = 0.15s；并发应 < 0.12s
        assert elapsed < 0.12, f"并发应 < 0.12s, got {elapsed:.3f}s"
