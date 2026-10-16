"""
测试: ConversationPipeline + 7 阶段 + SessionStore + SSE EventBuffer

覆盖目标 ≥ 25 用例:
- StageMetrics / ConversationTelemetry 数据模型 (4)
- ConversationPipeline 调度器 (timeout / retry / fallback / fatal) (6)
- SessionStore (新建 / 过期 / 历史裁剪 / 画像合并 / 实时状态) (6)
- EventBuffer (publish / replay / 容量 / Last-Event-ID 解析) (5)
- 7 个 Stage 子类单元行为 (7+)
- 端到端 mock pipeline 集成 (3)
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.agents.base import AgentResponse
from backend.app.api.v1.chat_pipeline.events import (
    EventBuffer,
    SSEEvent,
    parse_last_event_id,
    sse_format,
    sse_heartbeat,
)
from backend.app.api.v1.chat_pipeline.pipeline import (
    ConversationPipeline,
    ConversationTelemetry,
    PipelineContext,
    Stage,
    StageMetrics,
)
from backend.app.api.v1.chat_pipeline.session import (
    SessionStore,
    reset_session_store,
)


# ================================================================
# 测试辅助
# ================================================================
class _OkStage(Stage):
    name = "ok"
    timeout_seconds = 1.0

    def __init__(self, mark: str = "ok"):
        self.mark = mark
        self.calls = 0

    async def run(self, ctx: PipelineContext) -> None:
        self.calls += 1
        ctx.user_input += f"|{self.mark}"


class _FlakyStage(Stage):
    """前 N 次失败, 第 N+1 次成功"""
    name = "flaky"
    timeout_seconds = 1.0
    retry_count = 2

    def __init__(self, fail_times: int = 1):
        self.fail_times = fail_times
        self.calls = 0

    async def run(self, ctx: PipelineContext) -> None:
        self.calls += 1
        if self.calls <= self.fail_times:
            msg = f"flaky failure {self.calls}"
            raise RuntimeError(msg)


class _SlowStage(Stage):
    name = "slow"
    timeout_seconds = 0.05

    async def run(self, ctx: PipelineContext) -> None:
        await asyncio.sleep(0.5)


class _FatalStage(Stage):
    name = "fatal"
    timeout_seconds = 1.0
    fatal_on_fail = True

    async def run(self, ctx: PipelineContext) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    async def fallback(self, ctx, error):
        return False  # 降级失败


class _FallbackOkStage(Stage):
    name = "fallback_ok"
    timeout_seconds = 1.0
    fatal_on_fail = True

    async def run(self, ctx: PipelineContext) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    async def fallback(self, ctx, error):
        ctx.aggregated_text = "fallback content"
        return True


# ================================================================
# 1) StageMetrics + ConversationTelemetry
# ================================================================
class TestTelemetry:
    def test_stage_metrics_default(self):
        m = StageMetrics(name="rag")
        assert m.success is True
        assert m.retries == 0
        assert m.fallback_used is False

    def test_telemetry_records_agent(self):
        t = ConversationTelemetry()
        t.record_agent("course_expert")
        t.record_agent("quiz_generator")
        t.record_agent("")  # 空名跳过
        assert t.agent_call_chain == ["course_expert", "quiz_generator"]

    def test_telemetry_records_tokens(self):
        t = ConversationTelemetry()
        t.record_tokens(prompt=100, completion=200)
        t.record_tokens(prompt=50)
        assert t.token_usage["prompt"] == 150
        assert t.token_usage["completion"] == 200
        assert t.token_usage["total"] == 350

    def test_telemetry_summary_shape(self):
        t = ConversationTelemetry(session_id="abc")
        t.add_stage(StageMetrics(name="s1", duration_ms=12.5))
        t.add_stage(StageMetrics(
            name="s2", duration_ms=8.0, success=False, error="oops",
        ))
        s = t.summary()
        assert s["session_id"] == "abc"
        assert s["total_ms"] == pytest.approx(20.5)
        assert [stage["name"] for stage in s["stages"]] == ["s1", "s2"]
        assert s["stages"][1]["error"] == "oops"


# ================================================================
# 2) ConversationPipeline 调度
# ================================================================
class TestPipelineScheduler:
    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        s1, s2, s3 = _OkStage("a"), _OkStage("b"), _OkStage("c")
        p = ConversationPipeline([s1, s2, s3])
        ctx = PipelineContext(session_id="x", user_input="start")
        await p.execute(ctx)
        assert ctx.user_input == "start|a|b|c"

    @pytest.mark.asyncio
    async def test_retry_then_succeed(self):
        flaky = _FlakyStage(fail_times=1)  # 一次失败 → 一次重试成功
        p = ConversationPipeline([flaky])
        ctx = PipelineContext(session_id="x")
        await p.execute(ctx)
        m = ctx.telemetry.stage_metrics[0]
        assert m.success is True
        assert m.retries == 1

    @pytest.mark.asyncio
    async def test_retry_exhausted_runs_fallback(self):
        flaky = _FlakyStage(fail_times=99)
        p = ConversationPipeline([flaky])
        ctx = PipelineContext(session_id="x")
        await p.execute(ctx)
        m = ctx.telemetry.stage_metrics[0]
        assert m.success is False
        # fallback 默认 return True
        assert m.fallback_used is True

    @pytest.mark.asyncio
    async def test_timeout_recorded(self):
        slow = _SlowStage()
        p = ConversationPipeline([slow])
        ctx = PipelineContext(session_id="x")
        await p.execute(ctx)
        m = ctx.telemetry.stage_metrics[0]
        assert m.success is False
        assert "timeout" in m.error.lower()

    @pytest.mark.asyncio
    async def test_fatal_stage_terminates(self):
        fatal = _FatalStage()
        after = _OkStage("after")
        p = ConversationPipeline([fatal, after])
        ctx = PipelineContext(session_id="x")
        await p.execute(ctx)
        # 第一阶段 fatal → 第二阶段不应执行
        assert after.calls == 0
        assert ctx.telemetry.stage_metrics[0].fatal is True

    @pytest.mark.asyncio
    async def test_fatal_fallback_success_continues(self):
        """fatal + fallback 成功 → 流水线继续"""
        recovered = _FallbackOkStage()
        after = _OkStage("after")
        p = ConversationPipeline([recovered, after])
        ctx = PipelineContext(session_id="x")
        await p.execute(ctx)
        # fallback 返回 True → fatal 不生效, 继续
        assert after.calls == 1
        assert ctx.telemetry.stage_metrics[0].fallback_used is True

    def test_empty_pipeline_rejected(self):
        with pytest.raises(ValueError):
            ConversationPipeline([])


# ================================================================
# 3) SessionStore
# ================================================================
class TestSessionStore:
    def setup_method(self):
        reset_session_store()

    def test_create_new_session(self):
        store = SessionStore()
        sid, session = store.get_or_create()
        assert sid.startswith("sess_")
        assert session["history"] == []
        assert session["profile"] == {}

    def test_get_existing(self):
        store = SessionStore()
        sid, session = store.get_or_create()
        sid2, session2 = store.get_or_create(sid)
        assert sid == sid2
        assert session is session2

    def test_history_truncates(self):
        store = SessionStore(max_history_turns=2)
        _, session = store.get_or_create()
        for i in range(10):
            store.append_history(session, "user", f"msg{i}")
        # 2 * 2 = 4 messages 上限
        assert len(session["history"]) == 4
        assert session["history"][-1]["content"] == "msg9"

    def test_profile_merge_deep(self):
        store = SessionStore()
        _, session = store.get_or_create()
        store.merge_profile(session, {
            "knowledge_base": {"level": "入门", "depth": 1}
        })
        store.merge_profile(session, {"knowledge_base": {"level": "进阶"}})
        # 深度合并: depth 保留, level 更新
        assert session["profile"]["knowledge_base"]["level"] == "进阶"
        assert session["profile"]["knowledge_base"]["depth"] == 1

    def test_realtime_state_store(self):
        store = SessionStore()
        sid, _ = store.get_or_create()
        store.set_realtime_state(sid, {"confusion": 0.3})
        assert store.get_realtime_state(sid) == {"confusion": 0.3}

    def test_evict_expired(self):
        store = SessionStore(max_session_age=0.05)
        sid, session = store.get_or_create()
        time.sleep(0.1)
        # 触发 evict
        store.get_or_create("brand-new")
        assert store.get(sid) is None

    def test_clear_session(self):
        store = SessionStore()
        sid, _ = store.get_or_create()
        assert store.clear(sid) is True
        assert store.clear("nonexistent") is False


# ================================================================
# 4) SSE EventBuffer + 编码
# ================================================================
class TestSSEEvents:
    def test_sse_format_basic(self):
        out = sse_format("chunk", "hello", event_id=42)
        assert "id: 42" in out
        assert "event: chunk" in out
        assert "hello" in out
        assert out.endswith("\n\n")

    def test_sse_format_without_id(self):
        out = sse_format("done", {"ok": True})
        assert "id:" not in out
        assert "event: done" in out

    def test_heartbeat_is_comment(self):
        out = sse_heartbeat()
        assert out.startswith(":")

    def test_parse_last_event_id_valid(self):
        assert parse_last_event_id("17") == 17
        assert parse_last_event_id("  42  ") == 42

    def test_parse_last_event_id_invalid(self):
        assert parse_last_event_id(None) == 0
        assert parse_last_event_id("") == 0
        assert parse_last_event_id("abc") == 0
        assert parse_last_event_id("-5") == 0  # 负数被钳到 0

    def test_event_buffer_publish_and_replay(self):
        buf = EventBuffer("sess_x", capacity=10)
        e1 = buf.publish("chunk", "hello")
        e2 = buf.publish("chunk", "world")
        e3 = buf.publish("done", None)

        assert e1.event_id == 1
        assert e3.event_id == 3
        replayed = buf.replay_after(1)
        assert [e.event_id for e in replayed] == [2, 3]

    def test_event_buffer_capacity_evicts(self):
        buf = EventBuffer("sess_x", capacity=3)
        for i in range(5):
            buf.publish("chunk", i)
        # 仅保留最新 3 条 (id 3, 4, 5)
        assert buf.size() == 3
        assert buf.latest_id == 5

    def test_replay_after_zero_returns_all(self):
        buf = EventBuffer("sess_x", capacity=5)
        buf.publish("chunk", "a")
        buf.publish("chunk", "b")
        assert len(buf.replay_after(0)) == 2

    def test_sse_event_to_lines_round_trip(self):
        evt = SSEEvent(
            event_id=7, event_type="meta",
            payload={"k": "v"}, created_at=time.time(),
        )
        text = evt.to_sse_lines()
        assert "id: 7" in text
        assert "event: meta" in text


# ================================================================
# 5) 单 Stage 行为 (针对真实 7 Stage)
# ================================================================
class TestInputValidationStage:
    @pytest.mark.asyncio
    async def test_empty_message_aborts(self):
        from backend.app.api.v1.chat_pipeline.stages import InputValidationStage
        s = InputValidationStage()
        ctx = PipelineContext(session_id="x", user_input="   ")
        with pytest.raises(ValueError):
            await s.run(ctx)
        assert ctx.abort_reason == "message_required"

    @pytest.mark.asyncio
    async def test_too_long_aborts(self):
        from backend.app.api.v1.chat_pipeline.stages import InputValidationStage
        s = InputValidationStage()
        ctx = PipelineContext(session_id="x", user_input="x" * 5000)
        with pytest.raises(ValueError):
            await s.run(ctx)
        assert ctx.abort_reason == "message_too_long"

    @pytest.mark.asyncio
    async def test_valid_input_passes(self):
        from backend.app.api.v1.chat_pipeline.stages import InputValidationStage
        s = InputValidationStage()
        ctx = PipelineContext(
            session_id="x", user_input=" 讲解 CNN ",
            session={"role_view": "student"},
        )
        await s.run(ctx)
        assert ctx.validated is True
        assert ctx.user_input == "讲解 CNN"


class TestRAGStage:
    @pytest.mark.asyncio
    async def test_rag_fallback_empty_on_error(self):
        from backend.app.api.v1.chat_pipeline.stages import RAGRetrievalStage
        broken = MagicMock()
        broken.retrieve = MagicMock(side_effect=RuntimeError("rag down"))

        s = RAGRetrievalStage(top_k=3)
        ctx = PipelineContext(
            session_id="x", user_input="讲解 CNN",
            services={"rag_service": broken},
        )
        # Pipeline 会调 fallback, 这里手动模拟
        try:
            await s.run(ctx)
        except RuntimeError:
            await s.fallback(ctx, RuntimeError("rag down"))
        assert ctx.rag_results == []

    @pytest.mark.asyncio
    async def test_rag_normal_flow(self):
        from backend.app.api.v1.chat_pipeline.stages import RAGRetrievalStage
        mock_rag = MagicMock()
        mock_rag.retrieve = MagicMock(return_value=[
            {"content": "CNN ...", "score": 0.9, "course": "ai"},
        ])
        s = RAGRetrievalStage()
        ctx = PipelineContext(
            session_id="x", user_input="CNN",
            services={"rag_service": mock_rag},
        )
        await s.run(ctx)
        assert len(ctx.rag_results) == 1


class TestAggregationStage:
    @pytest.mark.asyncio
    async def test_aggregation_picks_primary_skips_meta(self):
        from backend.app.api.v1.chat_pipeline.stages import AggregationStage

        mock_safety = MagicMock()
        mock_safety.validate = AsyncMock(return_value=None)
        s = AggregationStage()

        agent_results = {
            "t1": AgentResponse(
                agent_name="profile_agent", success=True, content="profile",
                profile_updates={"k": "v"},
            ),
            "t2": AgentResponse(
                agent_name="course_expert", success=True,
                content="# CNN\n卷积神经网络很重要", content_type="markdown",
            ),
            "t3": AgentResponse(
                agent_name="critic_agent", success=True, content="review",
            ),
        }
        ctx = PipelineContext(
            session_id="x", user_input="讲解 CNN",
            agent_results=agent_results,
            services={"safety": mock_safety},
        )
        await s.run(ctx)
        assert ctx.primary_response.agent_name == "course_expert"
        assert ctx.profile_response.agent_name == "profile_agent"
        assert "CNN" in ctx.aggregated_text

    @pytest.mark.asyncio
    async def test_aggregation_no_primary_fallback(self):
        from backend.app.api.v1.chat_pipeline.stages import AggregationStage
        mock_safety = MagicMock()
        mock_safety.validate = AsyncMock(return_value=None)
        s = AggregationStage()
        ctx = PipelineContext(
            session_id="x", user_input="x",
            agent_results={},
            services={"safety": mock_safety},
        )
        await s.run(ctx)
        # 无 primary → 兜底响应
        assert ctx.primary_response is not None
        assert ctx.primary_response.success is False


class TestPublicAgentMessageContract:
    def test_five_agents_are_serialized_as_distinct_named_messages(self):
        from backend.app.api.v1.chat import _serialize_agent_messages

        ctx = PipelineContext(
            session_id="team-contract",
            user_input="@智狐 @智灵 @阿匠 @小龙 @团团 请分别回答",
            agent_results={
                "profile": AgentResponse(agent_name="profile", success=True, content="画像"),
                "content": AgentResponse(agent_name="doc_gen", success=True, content="导图和代码"),
                "quiz": AgentResponse(agent_name="exercise", success=True, content="题库"),
                "planner": AgentResponse(agent_name="path_planner", success=True, content="路径"),
                "evaluation": AgentResponse(agent_name="evaluator", success=True, content="评估"),
                "tutor": AgentResponse(agent_name="tutor", success=True, content="讲解"),
            },
        )

        messages = _serialize_agent_messages(ctx)

        assert [item["display_name"] for item in messages] == [
            "智狐", "智灵", "阿匠", "小龙", "团团",
        ]
        assert len({item["task_id"] for item in messages}) == 5
        assert all(item["content"] for item in messages)

    def test_structured_blocks_do_not_leak_into_agent_bubble(self):
        from backend.app.api.v1.chat import _serialize_agent_messages

        ctx = PipelineContext(
            session_id="clean-contract",
            user_input="@小龙 出题",
            agent_results={
                "quiz": AgentResponse(
                    agent_name="exercise",
                    success=True,
                    content="题目正文\n```quiz_json\n[{\"id\":1}]\n```",
                ),
            },
        )
        [message] = _serialize_agent_messages(ctx)
        assert message["content"] == "题目正文"


class TestPersistStage:
    @pytest.mark.asyncio
    async def test_persist_appends_history(self):
        from backend.app.api.v1.chat_pipeline.stages import PersistStage
        store = SessionStore()
        sid, session = store.get_or_create()
        primary = AgentResponse(
            agent_name="course_expert", success=True, content="hello",
        )
        ctx = PipelineContext(
            session_id=sid, user_input="问题",
            session=session, primary_response=primary,
            aggregated_text="hello",
            agent_results={"t1": primary},
            services={"session_store": store},
        )
        await PersistStage().run(ctx)
        history = session["history"]
        assert history[-2]["role"] == "user"
        assert history[-1]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_persist_merges_profile_from_profile_agent(self):
        from backend.app.api.v1.chat_pipeline.stages import PersistStage
        store = SessionStore()
        sid, session = store.get_or_create()
        prof = AgentResponse(
            agent_name="profile_agent", success=True,
            profile_updates={"goal": "进阶 AI"},
        )
        primary = AgentResponse(
            agent_name="course_expert", success=True, content="x",
        )
        ctx = PipelineContext(
            session_id=sid, user_input="x",
            session=session, primary_response=primary,
            profile_response=prof, aggregated_text="x",
            agent_results={"p": prof, "c": primary},
            services={"session_store": store},
        )
        await PersistStage().run(ctx)
        assert session["profile"]["goal"] == "进阶 AI"


# ================================================================
# 6) 端到端 mock pipeline 集成
# ================================================================
class TestPipelineE2E:
    @pytest.mark.asyncio
    async def test_e2e_with_all_stage_mocks(self):
        """构造全 mock 流水线, 验证 Telemetry 和数据流"""

        class _SetRAG(Stage):
            name = "set_rag"
            timeout_seconds = 1.0

            async def run(self, ctx):
                ctx.rag_results = [{"content": "x", "score": 0.5}]

        class _SetAgents(Stage):
            name = "set_agents"
            timeout_seconds = 1.0

            async def run(self, ctx):
                ctx.agent_results = {
                    "t1": AgentResponse(
                        agent_name="course_expert", success=True,
                        content="ok content",
                    ),
                }
                ctx.telemetry.record_agent("course_expert")

        class _SetText(Stage):
            name = "set_text"
            timeout_seconds = 1.0

            async def run(self, ctx):
                first = next(iter(ctx.agent_results.values()))
                ctx.primary_response = first
                ctx.aggregated_text = first.content

        pipeline = ConversationPipeline([_SetRAG(), _SetAgents(), _SetText()])
        ctx = PipelineContext(session_id="e2e-1", user_input="讲解")
        await pipeline.execute(ctx)

        assert ctx.aggregated_text == "ok content"
        assert ctx.telemetry.agent_call_chain == ["course_expert"]
        assert len(ctx.telemetry.stage_metrics) == 3
        assert all(m.success for m in ctx.telemetry.stage_metrics)

    @pytest.mark.asyncio
    async def test_pipeline_session_id_propagates_to_telemetry(self):
        ctx = PipelineContext(session_id="sess_abc")
        p = ConversationPipeline([_OkStage("z")])
        await p.execute(ctx)
        assert ctx.telemetry.session_id == "sess_abc"
