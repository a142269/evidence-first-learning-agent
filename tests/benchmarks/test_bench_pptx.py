"""PPTX 生成基线 —— 评委演示 SLO：P99 < 5s"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.bench


@pytest.fixture(scope="module")
def outline():
    from backend.app.services.multimodal.pptx_builder import PPTXOutline, SlideContent

    return PPTXOutline(
        title="卷积神经网络入门",
        slides=[
            SlideContent(title="什么是 CNN", bullets=["局部感受野", "权值共享", "平移不变性"]),
            SlideContent(title="经典架构", bullets=["LeNet", "AlexNet", "ResNet"]),
            SlideContent(title="损失与优化", bullets=["交叉熵", "Adam", "学习率退火"]),
        ],
    )


def test_bench_outline_to_deck_spec(benchmark, outline):
    from backend.app.services.multimodal.pptx_builder import outline_to_deck_spec

    deck = benchmark.pedantic(
        outline_to_deck_spec, args=(outline,), kwargs={"session_id": "bench"},
        rounds=5, iterations=1,
    )
    assert len(deck.slides) >= 4
    assert deck.slides[0].layout == "cover"


def test_bench_pptx_build(benchmark, outline, tmp_path):
    from backend.app.services.multimodal.pptx_builder import PPTXBuilder

    builder = PPTXBuilder()

    def _run():
        return builder.build(outline, f"bench-{benchmark.name if hasattr(benchmark, 'name') else 'x'}")

    result = benchmark.pedantic(_run, rounds=3, iterations=1)
    assert "filepath" in result
    assert result["slides_count"] >= 3
