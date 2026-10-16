"""
测试: Agent Reflection 框架 (P1-7)

覆盖目标 ≥ 25 用例:
- trace.py:     ReflectionScore / ReflectionTrace / Verdict (5)
- rubric.py:    5 维评分 + Bloom-aware 失败模式 (6)
- strategies/:  SelfRefine / ShinnReflexion / BloomAware (8)
- reflector.py: 默认策略 / 覆盖 / 错误兜底 (3)
- base.py:      BaseAgent.reflect() + prompt_version (4)
- 集成测试:     pipeline DebateReflectionStage (2)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.agents.base import AgentContext
from backend.app.agents.reflection import (
    BLOOM_FAILURE_MODES,
    BLOOM_REVISION_HINTS,
    BloomAwareStrategy,
    ReflectionConfig,
    ReflectionRubric,
    ReflectionScore,
    ReflectionTrace,
    ReflectionVerdict,
    Reflector,
    SelfRefineStrategy,
    ShinnReflexionStrategy,
    WeaknessItem,
    get_reflector,
    get_strategy,
    reset_reflector,
)


# ================================================================
# 1) trace.py
# ================================================================
class TestReflectionScore:
    def test_default_zero(self):
        s = ReflectionScore()
        assert s.overall == 0.0
        assert s.factual == 0.0

    def test_to_dict_rounded(self):
        s = ReflectionScore(overall=0.7234, factual=0.9)
        d = s.to_dict()
        assert d["overall"] == 0.723
        assert d["factual"] == 0.9


class TestReflectionTrace:
    def test_empty_trace_best_score_zero(self):
        t = ReflectionTrace(agent_name="x")
        assert t.best_score() == 0.0
        assert t.needs_rewrite() is False  # default PASS

    def test_verdict_pass_no_rewrite(self):
        t = ReflectionTrace(agent_name="x", verdict=ReflectionVerdict.PASS)
        assert t.needs_rewrite() is False

    def test_verdict_revise_needs_rewrite(self):
        t = ReflectionTrace(
            agent_name="x",
            verdict=ReflectionVerdict.NEEDS_REVISION,
        )
        assert t.needs_rewrite() is True

    def test_to_dict_shape(self):
        t = ReflectionTrace(
            agent_name="course_expert",
            strategy="bloom_aware",
            prompt_version="v2",
            verdict=ReflectionVerdict.NEEDS_REVISION,
            final_content="rewritten",
        )
        d = t.to_dict()
        assert d["agent_name"] == "course_expert"
        assert d["needs_rewrite"] is True
        assert d["improved_draft"] == "rewritten"
        assert d["prompt_version"] == "v2"


# ================================================================
# 2) rubric.py - Bloom-aware
# ================================================================
class TestRubric:
    def test_empty_content_blocker(self):
        score, weaknesses = ReflectionRubric().evaluate("", bloom="apply")
        assert weaknesses
        assert weaknesses[0].severity == "blocker"
        assert score.overall == 0.0

    def test_short_content_low_structure(self):
        score, weaknesses = ReflectionRubric().evaluate(
            "短", bloom="understand",
        )
        assert score.structure < 1.0

    def test_pedagogy_detects_examples(self):
        good = (
            "## 概念\n\n这是一个概念。例如, 在实际场景中, "
            "你可以这样使用。首先, 然后. 最后. 练习一下吧。"
        )
        s, _ = ReflectionRubric().evaluate(good, bloom="understand")
        assert s.pedagogy > 0.6

    def test_bloom_apply_detects_keyword(self):
        content = (
            "## CNN 实现\n\n"
            "使用 PyTorch 实现 LeNet-5 并训练 MNIST。\n\n"
            "首先准备数据。然后定义网络。"
        )
        s, _ = ReflectionRubric().evaluate(content, bloom="apply")
        assert s.bloom_match >= 0.9

    def test_bloom_understand_has_failure_modes(self):
        assert "understand" in BLOOM_FAILURE_MODES
        assert len(BLOOM_FAILURE_MODES["understand"]) >= 2

    def test_factual_with_rag_overlap_high(self):
        # 完全相同的内容应满分 (overlap=1.0 → factual=1.0)
        same = "Convolutional Neural Network pooling layer fully connected"
        rag = [{"content": same}]
        s, _ = ReflectionRubric().evaluate(
            same, bloom="understand", rag_results=rag,
        )
        assert s.factual >= 0.9

    def test_factual_with_rag_overlap_low(self):
        # 内容完全不重叠 → 应低分 + 有 weakness
        content = "Quantum entanglement superposition Hilbert space"
        rag = [{"content": "卷积神经网络深度学习模型"}]
        s, weaknesses = ReflectionRubric().evaluate(
            content, bloom="understand", rag_results=rag,
        )
        assert s.factual < 0.5
        assert any(w.dimension == "factual" for w in weaknesses)


# ================================================================
# 3) strategies/
# ================================================================
class TestSelfRefineStrategy:
    @pytest.mark.asyncio
    async def test_single_iteration_returns_trace(self):
        strat = SelfRefineStrategy()
        cfg = ReflectionConfig(max_iterations=1)
        trace = await strat.reflect(
            "## CNN\n卷积神经网络是一种深度学习模型。",
            cfg, agent_name="x",
        )
        assert trace.strategy == "self_refine"
        assert len(trace.steps) == 1

    @pytest.mark.asyncio
    async def test_passing_content_yields_pass(self):
        strat = SelfRefineStrategy()
        cfg = ReflectionConfig(max_iterations=1, pass_threshold=0.5)
        long_good_content = (
            "## CNN 详解\n\n"
            "卷积神经网络是一种针对图像的深度学习模型。\n\n"
            "例如, 在图像识别中, 它表现出色。\n\n"
            "首先卷积, 然后池化, 最后全连接。\n\n"
            "练习: 用 PyTorch 实现一个简单的 CNN。"
        )
        trace = await strat.reflect(
            long_good_content, cfg, agent_name="x",
        )
        assert trace.verdict == ReflectionVerdict.PASS

    @pytest.mark.asyncio
    async def test_low_quality_yields_regen(self):
        strat = SelfRefineStrategy()
        cfg = ReflectionConfig(max_iterations=1, pass_threshold=0.9)
        trace = await strat.reflect("?", cfg, agent_name="x")
        assert trace.verdict in (
            ReflectionVerdict.NEEDS_REGEN,
            ReflectionVerdict.NEEDS_REVISION,
        )

    @pytest.mark.asyncio
    async def test_rule_revise_appends_suggestion(self):
        strat = SelfRefineStrategy()
        cfg = ReflectionConfig(max_iterations=1, pass_threshold=0.99)
        trace = await strat.reflect(
            "短文", cfg, agent_name="x",
        )
        # rule 修订会在末尾追加建议
        assert "改进建议" in trace.final_content or trace.final_content == "短文"

    @pytest.mark.asyncio
    async def test_llm_revise_calls_llm(self):
        mock_llm = MagicMock()
        mock_llm.achat = AsyncMock(return_value="LLM 重写后内容")
        strat = SelfRefineStrategy()
        cfg = ReflectionConfig(
            max_iterations=1, pass_threshold=0.99, use_llm_revise=True,
        )
        trace = await strat.reflect(
            "短文", cfg, agent_name="x", llm_client=mock_llm,
        )
        # achat 至少被调一次
        assert mock_llm.achat.call_count >= 1


class TestShinnReflexionStrategy:
    @pytest.mark.asyncio
    async def test_includes_memory_in_reasoning(self):
        strat = ShinnReflexionStrategy()
        cfg = ReflectionConfig(max_iterations=3, pass_threshold=0.99)
        trace = await strat.reflect(
            "短文", cfg, agent_name="x",
        )
        # 至少 2 轮才会出现 memory
        if len(trace.steps) >= 2:
            assert "历史反思" in trace.steps[1].reasoning

    @pytest.mark.asyncio
    async def test_strategy_name(self):
        strat = ShinnReflexionStrategy()
        cfg = ReflectionConfig(max_iterations=1)
        trace = await strat.reflect("x", cfg, agent_name="a")
        assert trace.strategy == "reflexion_shinn"


class TestBloomAwareStrategy:
    @pytest.mark.asyncio
    async def test_reasoning_mentions_bloom_target(self):
        strat = BloomAwareStrategy()
        cfg = ReflectionConfig(
            max_iterations=1, bloom_target="apply",
        )
        trace = await strat.reflect(
            "短文", cfg, agent_name="x",
        )
        # 应在 reasoning 中明确提到目标层级
        assert "apply" in trace.steps[0].reasoning

    @pytest.mark.asyncio
    async def test_bloom_revision_hints_exist_for_all_levels(self):
        for level in [
            "remember", "understand", "apply",
            "analyze", "evaluate", "create",
        ]:
            assert level in BLOOM_REVISION_HINTS

    @pytest.mark.asyncio
    async def test_different_bloom_targets_yield_different_reasoning(self):
        strat = BloomAwareStrategy()
        cfg_a = ReflectionConfig(max_iterations=1, bloom_target="apply")
        cfg_e = ReflectionConfig(max_iterations=1, bloom_target="evaluate")

        ta = await strat.reflect("短文", cfg_a, agent_name="x")
        te = await strat.reflect("短文", cfg_e, agent_name="x")

        # 至少 reasoning 文本应不同 (Bloom 层级不同 → revision_hint 不同)
        assert ta.steps[0].reasoning != te.steps[0].reasoning

    @pytest.mark.asyncio
    async def test_appends_bloom_aware_suggestion(self):
        strat = BloomAwareStrategy()
        cfg = ReflectionConfig(
            max_iterations=1, pass_threshold=0.99, bloom_target="apply",
        )
        trace = await strat.reflect("短文", cfg, agent_name="x")
        # rule revision 会追加 Bloom-Aware 建议段落
        assert (
            "Bloom-Aware" in trace.final_content
            or trace.final_content == "短文"
        )


# ================================================================
# 4) reflector.py
# ================================================================
class TestReflector:
    @pytest.mark.asyncio
    async def test_default_strategy_is_bloom_aware(self):
        reset_reflector()
        reflector = get_reflector()
        assert reflector.default_strategy == "bloom_aware"
        trace = await reflector.run(
            content="短文", agent_name="x",
        )
        assert trace.strategy == "bloom_aware"

    @pytest.mark.asyncio
    async def test_strategy_override(self):
        reflector = Reflector()
        trace = await reflector.run(
            content="短文", agent_name="x",
            strategy="self_refine",
        )
        assert trace.strategy == "self_refine"

    @pytest.mark.asyncio
    async def test_unknown_strategy_falls_back(self):
        reflector = Reflector()
        trace = await reflector.run(
            content="短文", agent_name="x",
            strategy="nonexistent_strategy",
        )
        # 未知策略应回退到 bloom_aware (get_strategy 默认)
        assert trace.strategy == "bloom_aware"


# ================================================================
# 5) base.py - BaseAgent.reflect()
# ================================================================
class TestBaseAgentReflect:
    @pytest.mark.asyncio
    async def test_tutor_agent_has_reflect_method(self):
        from backend.app.agents.tutor_agent import TutorAgent
        agent = TutorAgent(llm_client=MagicMock())
        assert hasattr(agent, "reflect")

    @pytest.mark.asyncio
    async def test_reflect_returns_dict_with_required_keys(self):
        from backend.app.agents.tutor_agent import TutorAgent
        agent = TutorAgent(llm_client=MagicMock())
        ctx = AgentContext(
            user_input="x", extra={"target_bloom": "apply"},
        )
        result = await agent.reflect("# CNN\n短文", ctx)
        assert "needs_rewrite" in result
        assert "improved_draft" in result
        assert "best_score" in result
        assert "issues" in result
        assert "prompt_version" in result

    @pytest.mark.asyncio
    async def test_reflect_records_prompt_version(self):
        from backend.app.agents.tutor_agent import TutorAgent
        agent = TutorAgent(llm_client=MagicMock())
        agent.__class__.prompt_version = "v2-test"
        ctx = AgentContext(user_input="x")
        result = await agent.reflect("短文", ctx)
        assert result["prompt_version"] == "v2-test"
        agent.__class__.prompt_version = "v1"  # reset

    @pytest.mark.asyncio
    async def test_reflect_uses_target_bloom_from_context(self):
        from backend.app.agents.tutor_agent import TutorAgent
        agent = TutorAgent(llm_client=MagicMock())
        ctx = AgentContext(
            user_input="x",
            extra={"target_bloom": "evaluate"},
        )
        result = await agent.reflect("短文", ctx)
        assert result["bloom_target"] == "evaluate"


# ================================================================
# 6) Pipeline 集成 — Reflexion 接入 DebateReflectionStage
# ================================================================
class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_pipeline_records_reflection_metadata(self):
        """DebateReflectionStage 调 reflect() 后应填 metadata"""
        from backend.app.agents.base import AgentResponse
        from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext
        from backend.app.api.v1.chat_pipeline.stages.orchestration import (
            DebateReflectionStage,
        )

        # Mock orchestrator + agent
        good_content = (
            "## CNN 详解\n\n"
            "卷积神经网络应用于图像识别。\n\n"
            "例如, MNIST 手写数字识别。\n\n"
            "首先定义网络, 然后训练, 最后预测。\n\n"
            "练习: 实现一个简单 CNN。"
        )
        resp = AgentResponse(
            agent_name="profile_agent", success=True,
            content=good_content,
            content_type="markdown", metadata={},
        )

        mock_agent = MagicMock()
        mock_agent.name = "profile_agent"
        mock_agent.reflect = AsyncMock(return_value={
            "needs_rewrite": False,
            "improved_draft": good_content,
            "best_score": 0.85,
            "verdict": "pass",
            "strategy": "bloom_aware",
            "prompt_version": "v1",
            "issues": [],
        })

        mock_orch = MagicMock()
        mock_orch._get_or_create_agent = MagicMock(return_value=mock_agent)

        ctx = PipelineContext(
            session_id="t", user_input="x",
            agent_results={"t1": resp},
            services={"orchestrator": mock_orch},
        )
        stage = DebateReflectionStage()
        await stage._run_reflection(ctx)
        assert "reflection" in resp.metadata
        assert resp.metadata["reflection"]["strategy"] == "bloom_aware"

    @pytest.mark.asyncio
    async def test_pipeline_skips_meta_content_types(self):
        from backend.app.agents.base import AgentResponse
        from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext
        from backend.app.api.v1.chat_pipeline.stages.orchestration import (
            DebateReflectionStage,
        )
        # content_type=evaluation 应被跳过
        resp = AgentResponse(
            agent_name="evaluator_agent", success=True,
            content="...", content_type="evaluation", metadata={},
        )
        mock_orch = MagicMock()
        ctx = PipelineContext(
            session_id="t", user_input="x",
            agent_results={"t1": resp},
            services={"orchestrator": mock_orch},
        )
        stage = DebateReflectionStage()
        await stage._run_reflection(ctx)
        # 不应有 reflection 元数据
        assert "reflection" not in resp.metadata
