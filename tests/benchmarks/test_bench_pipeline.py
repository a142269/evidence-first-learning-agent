"""Pipeline 调度器基线 —— 阶段切换开销 + telemetry 上下文"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.bench


class _NoopStage:
    """空阶段：仅作 telemetry 时钟标记，测量调度器纯开销。"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.timeout_seconds = 5.0
        self.retry_count = 0
        self.fatal_on_fail = False

    async def run(self, ctx) -> None:  # noqa: D401
        ctx.session.setdefault("_visited", []).append(self.name)

    async def fallback(self, ctx, error) -> bool:
        return True


def _build_pipeline():
    from backend.app.api.v1.chat_pipeline.pipeline import ConversationPipeline

    return ConversationPipeline([_NoopStage(f"stage-{i}") for i in range(7)])


def _build_ctx():
    from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext

    return PipelineContext(
        session_id="bench-session",
        user_input="基准测试",
        course="artificial_intelligence",
    )


def test_bench_pipeline_seven_stages(benchmark):
    pipeline = _build_pipeline()

    def _run():
        return asyncio.run(pipeline.execute(_build_ctx()))

    ctx = benchmark.pedantic(_run, rounds=5, iterations=1)
    assert len(ctx.session.get("_visited", [])) == 7
    assert ctx.telemetry.pipeline_started_at > 0


def test_bench_pipeline_single_stage_overhead(benchmark):
    from backend.app.api.v1.chat_pipeline.pipeline import ConversationPipeline

    pipeline = ConversationPipeline([_NoopStage("solo")])

    def _run():
        return asyncio.run(pipeline.execute(_build_ctx()))

    ctx = benchmark.pedantic(_run, rounds=10, iterations=1)
    assert ctx.session["_visited"] == ["solo"]
