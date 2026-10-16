"""
测试: 单 Agent 私聊模式 (Direct Message / target_agent)

覆盖:
- 合法 target_agent 只调用一个 agent，不包含 profile
- 6 个合法 partner.key 都能正确映射到后端 agent
- 非法 target_agent 静默忽略，回退为普通群聊模式
- process_turn target_agent 透传到 OrchestrationStage → PipelineContext
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.app.agents.orchestrator import (
    AgentOrchestrator,
    PARTNER_TO_AGENT,
    VALID_AGENT_KEYS,
    resolve_target_agent,
)
from backend.app.agents.base import AgentContext, AgentResponse


# ================================================================
# Fixtures — 含全部 6 个后端 agent 的 mock 注册表
# ================================================================
@pytest.fixture
def dm_agent_registry():
    """模拟 Agent 注册表，覆盖全部 6 个单 Agent 映射目标。"""
    registry = {}

    # 为每个后端 agent name 创建一个 mock
    agent_specs = [
        ("path_planner", "path_planner", "学习路径已生成"),
        ("tutor", "tutor", "知识点讲解完毕"),
        ("doc_gen", "doc_gen", "文档已生成"),
        ("exercise", "exercise", "练习题已生成"),
        ("evaluator", "evaluator", "评估完成"),
        ("safe_decline", "safe_decline", "该请求超出教学边界"),
        # 群聊模式也需要 profile
        ("profile", "profile", "画像已更新"),
    ]

    for agent_name, cls_name, content in agent_specs:
        mock_cls = MagicMock()
        mock_instance = MagicMock()
        mock_instance.name = agent_name
        mock_instance.execute = AsyncMock(
            return_value=AgentResponse(
                agent_name=agent_name,
                success=True,
                content=content,
            )
        )
        mock_cls.return_value = mock_instance
        registry[agent_name] = mock_cls

    return registry


@pytest.fixture
def dm_orchestrator(mock_llm_client, dm_agent_registry):
    """返回含全部 6 个 agent 的 Orchestrator"""
    return AgentOrchestrator(
        llm_client=mock_llm_client, agent_registry=dm_agent_registry,
    )


# ================================================================
# 映射表测试
# ================================================================
class TestPartnerToAgentMapping:
    """PARTNER_TO_AGENT 映射完整性"""

    def test_all_six_partners_mapped(self):
        """6 个 partner.key 都有映射"""
        expected = {"planner", "tutor", "content", "quiz", "evaluation", "safety"}
        assert set(PARTNER_TO_AGENT.keys()) == expected

    def test_valid_agent_keys_matches(self):
        """VALID_AGENT_KEYS 与 PARTNER_TO_AGENT keys 一致"""
        assert VALID_AGENT_KEYS == frozenset(PARTNER_TO_AGENT.keys())

    @pytest.mark.parametrize("partner_key,expected_agent", [
        ("planner", "path_planner"),
        ("tutor", "tutor"),
        ("content", "doc_gen"),
        ("quiz", "exercise"),
        ("evaluation", "evaluator"),
        ("safety", "safe_decline"),
    ])
    def test_resolve_each_key(self, partner_key, expected_agent):
        """每个 partner.key 正确映射到后端 agent name"""
        assert resolve_target_agent(partner_key) == expected_agent

    def test_resolve_invalid_key_returns_none(self):
        """非法 key 返回 None"""
        assert resolve_target_agent("nonexistent") is None
        assert resolve_target_agent("") is None
        assert resolve_target_agent(None) is None


class TestRealSafetyAgent:
    """真实 SafeDeclineAgent 兼容 BaseAgent 抽象接口"""

    @pytest.mark.asyncio
    async def test_safe_decline_instantiates_and_executes(self):
        """safety 单 Agent 目标对应的真实 Agent 可实例化并返回模板回复"""
        from backend.app.agents.safe_decline_agent import SafeDeclineAgent

        agent = SafeDeclineAgent(llm_client=MagicMock())
        resp = await agent.execute(AgentContext(user_input="今天天气怎么样"))

        assert resp.success is True
        assert resp.agent_name == "safe_decline"
        assert resp.content


# ================================================================
# 单 Agent 模式 process_turn 测试
# ================================================================
class TestDirectMessage:
    """单 Agent 私聊模式测试"""

    @pytest.mark.asyncio
    async def test_target_agent_skips_orchestration(self, dm_orchestrator):
        """指定 target_agent 时跳过多 Agent 编排，只返回 1 个结果"""
        results = await dm_orchestrator.process_turn(
            user_input="什么是梯度下降",
            profile={},
            context={},
            target_agent="tutor",
        )
        assert len(results) == 1
        result = list(results.values())[0]
        assert result.success is True

    @pytest.mark.asyncio
    async def test_target_agent_no_profile_update(self, dm_orchestrator):
        """私聊模式不触发 profile_update"""
        results = await dm_orchestrator.process_turn(
            user_input="讲解 CNN",
            profile={},
            context={},
            target_agent="tutor",
        )
        agent_names = [r.agent_name for r in results.values()]
        assert "profile" not in agent_names

    @pytest.mark.asyncio
    @pytest.mark.parametrize("partner_key,expected_agent_name", [
        ("planner", "path_planner"),
        ("tutor", "tutor"),
        ("content", "doc_gen"),
        ("quiz", "exercise"),
        ("evaluation", "evaluator"),
        ("safety", "safe_decline"),
    ])
    async def test_each_valid_target_agent(
        self, dm_orchestrator, partner_key, expected_agent_name,
    ):
        """6 个合法 target_agent 各自路由到正确的后端 agent"""
        results = await dm_orchestrator.process_turn(
            user_input="测试消息",
            profile={},
            context={},
            target_agent=partner_key,
        )
        assert len(results) == 1
        result = list(results.values())[0]
        assert result.agent_name == expected_agent_name
        assert result.success is True

    @pytest.mark.asyncio
    async def test_invalid_target_agent_fallback(self, dm_orchestrator):
        """非法 target_agent 静默忽略，走群聊模式"""
        results = await dm_orchestrator.process_turn(
            user_input="讲解 CNN",
            profile={},
            context={},
            target_agent="nonexistent",
        )
        # 应该走群聊模式，可能返回多个 Agent 结果
        # 至少包含一个结果
        assert len(results) >= 1
        # 不应包含 dm_0 这个 task_id（单 Agent 模式的标识）
        assert "dm_0" not in results

    @pytest.mark.asyncio
    async def test_none_target_agent_normal_mode(self, dm_orchestrator):
        """target_agent=None 走正常群聊模式"""
        results = await dm_orchestrator.process_turn(
            user_input="讲解 CNN",
            profile={},
            context={},
            target_agent=None,
        )
        assert len(results) >= 1
        assert "dm_0" not in results

    @pytest.mark.asyncio
    async def test_dm_result_key_is_dm_0(self, dm_orchestrator):
        """单 Agent 模式返回的 dict key 是 dm_0"""
        results = await dm_orchestrator.process_turn(
            user_input="测试",
            profile={},
            context={},
            target_agent="tutor",
        )
        assert "dm_0" in results

    @pytest.mark.asyncio
    async def test_dm_passes_rag_and_history(self, dm_orchestrator):
        """单 Agent 模式正确传递 rag_results 和 conversation_history"""
        rag_results = [{"content": "RAG content", "score": 0.9}]
        history = [{"role": "user", "content": "previous question"}]

        results = await dm_orchestrator.process_turn(
            user_input="测试",
            profile={},
            context={},
            conversation_history=history,
            rag_results=rag_results,
            target_agent="tutor",
        )
        assert len(results) == 1
        # 验证 agent 被调用
        result = list(results.values())[0]
        assert result.success is True


# ================================================================
# ResourceGeneratorAgent 单 Agent 模式测试
# ================================================================
class TestResourceGeneratorDirectMessage:
    """验证 ResourceGeneratorAgent 在单 Agent 私聊模式下不误触发资源生成"""

    @pytest.mark.asyncio
    async def test_dm_no_keywords_does_not_generate_document(self):
        """单 Agent 模式下，学生问题不含资源关键词时不强制生成文档"""
        from backend.app.agents.resource_generator_agent import (
            ResourceGeneratorAgent,
        )
        from backend.app.agents.base import AgentContext

        agent = ResourceGeneratorAgent(llm_client=MagicMock())
        # Mock LLM 返回对话式回答
        agent._acall_llm = AsyncMock(return_value="这是关于梯度下降的讲解...")

        ctx = AgentContext(
            user_input="什么是梯度下降",
            session_id="dm-test",
            extra={"action": "direct_message", "task_id": "dm_0"},
        )
        resp = await agent.execute(ctx)

        assert resp.success is True
        assert resp.content_type == "markdown"
        # 不应包含资源生成相关的内容
        assert "生成以下真实可下载资源" not in resp.content
        # 不应有 resources
        assert not resp.resources

    @pytest.mark.asyncio
    async def test_dm_with_keywords_still_generates(self):
        """单 Agent 模式下，学生明确请求资源时正常生成"""
        from backend.app.agents.resource_generator_agent import (
            ResourceGeneratorAgent,
        )
        from backend.app.agents.base import AgentContext

        agent = ResourceGeneratorAgent(llm_client=MagicMock())

        # Mock tool registry
        with patch(
            "backend.app.agents.resource_generator_agent.get_tool_registry"
        ) as mock_reg:
            mock_tool = MagicMock()
            mock_tool.schema.name = "generate_learning_materials"
            mock_handler = AsyncMock(return_value={
                "success": True,
                "results": {
                    "document": {
                        "success": True,
                        "metadata": {"title": "CNN 讲义"},
                        "filepath": "/tmp/test.pdf",
                    }
                },
            })
            mock_tool.handler = mock_handler
            mock_reg.return_value.list_a_tools.return_value = [mock_tool]

            ctx = AgentContext(
                user_input="帮我生成一份 CNN 的文档",
                session_id="dm-test",
                extra={"action": "direct_message", "task_id": "dm_0"},
            )
            resp = await agent.execute(ctx)

            assert resp.success is True
            assert len(resp.resources) == 1
            assert resp.resources[0]["type"] == "document"

    @pytest.mark.asyncio
    async def test_dm_scene_context_no_false_positive(self):
        """模拟实验场场景上下文前缀 [实验场·实验楼·阿匠] 不触发资源生成"""
        from backend.app.agents.resource_generator_agent import (
            ResourceGeneratorAgent,
        )
        from backend.app.agents.base import AgentContext

        agent = ResourceGeneratorAgent(llm_client=MagicMock())
        agent._acall_llm = AsyncMock(return_value="这是讲解...")

        ctx = AgentContext(
            user_input="[实验场·实验楼·阿匠]\n什么是反向传播",
            session_id="dm-test",
            extra={"action": "direct_message", "task_id": "dm_0"},
        )
        resp = await agent.execute(ctx)

        assert resp.success is True
        assert not resp.resources
        assert "生成以下真实可下载资源" not in resp.content


# ================================================================
# Pipeline 单 Agent 模式集成测试
# ================================================================
class TestPipelineSingleAgentMode:
    """验证 PipelineContext 单 Agent 模式字段正确传播"""

    def test_pipeline_context_has_target_agent_field(self):
        """PipelineContext 有 target_agent 和 single_agent_mode 字段"""
        from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext
        ctx = PipelineContext(session_id="x", target_agent="tutor")
        assert ctx.target_agent == "tutor"
        assert ctx.single_agent_mode is False

    def test_pipeline_context_default_target_agent_none(self):
        """PipelineContext 默认 target_agent 为 None"""
        from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext
        ctx = PipelineContext(session_id="x")
        assert ctx.target_agent is None
        assert ctx.single_agent_mode is False

    @pytest.mark.asyncio
    async def test_orchestration_stage_sets_single_agent_mode(self):
        """OrchestrationStage 在 target_agent 合法时设置 single_agent_mode"""
        from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext
        from backend.app.api.v1.chat_pipeline.stages.orchestration import (
            OrchestrationStage,
        )

        # Mock orchestrator
        mock_orch = MagicMock()
        mock_orch.process_turn = AsyncMock(return_value={
            "dm_0": AgentResponse(agent_name="tutor", success=True, content="ok"),
        })

        ctx = PipelineContext(
            session_id="x",
            user_input="测试",
            session={"profile": {}, "history": []},
            target_agent="tutor",
            services={"orchestrator": mock_orch},
        )

        stage = OrchestrationStage()
        await stage.run(ctx)

        # 验证 process_turn 被调用时传了 target_agent
        call_kwargs = mock_orch.process_turn.call_args
        assert call_kwargs.kwargs.get("target_agent") == "tutor"
        # 验证 single_agent_mode 被设置
        assert ctx.single_agent_mode is True

    @pytest.mark.asyncio
    async def test_debate_reflection_skipped_in_single_agent_mode(self):
        """DebateReflectionStage 在 single_agent_mode 时跳过"""
        from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext
        from backend.app.api.v1.chat_pipeline.stages.orchestration import (
            DebateReflectionStage,
        )

        ctx = PipelineContext(
            session_id="x",
            user_input="测试",
            single_agent_mode=True,
            agent_results={
                "dm_0": AgentResponse(agent_name="tutor", success=True, content="ok"),
            },
        )

        stage = DebateReflectionStage()
        # 应该直接返回，不执行辩论/反思
        await stage.run(ctx)
        # debate_log 和 reflection_log 应该没有被设置
        assert ctx.debate_log is None
        assert ctx.reflection_log == {}

    @pytest.mark.asyncio
    async def test_persist_stage_skips_profile_in_single_agent_mode(self):
        """PersistStage 在 single_agent_mode 时不合并画像"""
        from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext
        from backend.app.api.v1.chat_pipeline.stages.outputs import PersistStage
        from backend.app.api.v1.chat_pipeline.session import SessionStore

        store = SessionStore()
        sid, session = store.get_or_create()
        # 预置画像
        store.merge_profile(session, {"existing": "value"})

        primary = AgentResponse(
            agent_name="tutor", success=True, content="answer",
            profile_updates={"new_field": "should_not_be_merged"},
        )
        ctx = PipelineContext(
            session_id=sid,
            user_input="问题",
            session=session,
            primary_response=primary,
            aggregated_text="answer",
            agent_results={"dm_0": primary},
            single_agent_mode=True,
            services={"session_store": store},
        )

        await PersistStage().run(ctx)

        # 画像不应包含 new_field
        assert "new_field" not in session.get("profile", {})
        assert session["profile"].get("existing") == "value"
