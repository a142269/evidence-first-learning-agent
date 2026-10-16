"""Mermaid 渲染基线 —— 评委演示 SLO：P99 < 3s（含 3 级降级）"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.bench

_SIMPLE_MINDMAP = """mindmap
  root((机器学习))
    监督学习
      回归
      分类
    无监督学习
      聚类
      降维
"""

_SIMPLE_FLOWCHART = """flowchart LR
A[输入] --> B[预处理]
B --> C{是否合规?}
C -->|是| D[模型推理]
C -->|否| E[拒绝]
D --> F[输出]
"""


def test_bench_mermaid_render_mindmap(benchmark):
    from backend.app.services.multimodal.mermaid_renderer import MermaidRenderer

    renderer = MermaidRenderer()
    result = benchmark.pedantic(
        renderer.render, args=(_SIMPLE_MINDMAP,), kwargs={"rid": "bench-mindmap"},
        rounds=5, iterations=1,
    )
    assert "method" in result
    assert "mermaid_text" in result


def test_bench_mermaid_render_flowchart(benchmark):
    from backend.app.services.multimodal.mermaid_renderer import MermaidRenderer

    renderer = MermaidRenderer()
    result = benchmark.pedantic(
        renderer.render, args=(_SIMPLE_FLOWCHART,), kwargs={"rid": "bench-flow"},
        rounds=5, iterations=1,
    )
    assert "method" in result


def test_bench_mermaid_extract_blocks(benchmark):
    from backend.app.services.multimodal.mermaid_renderer import MermaidRenderer

    text = (
        "前面文字\n```mermaid\n" + _SIMPLE_MINDMAP + "```\n"
        "中间\n```mermaid\n" + _SIMPLE_FLOWCHART + "```\n"
        "尾部\n"
    )
    blocks = benchmark.pedantic(
        MermaidRenderer.extract_blocks, args=(text,),
        rounds=10, iterations=5,
    )
    assert len(blocks) == 2
