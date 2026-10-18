"""
MermaidStudio - 5 种图统一渲染入口

用法:
    studio = get_mermaid_studio()

    # 从 spec 渲染
    result = studio.render_spec(my_mindmap_spec)

    # 从 Mermaid 代码 (LLM 直接生成时)
    result = studio.render_code("mindmap\\n  root((CNN))...", kind="mindmap")

    # 从概念词列表自动构建简单 mindmap
    result = studio.from_concept(
        title="CNN", branches=["卷积", "池化", "全连接"],
    )

    # 知识图谱可视化
    result = studio.render_knowledge_graph(nodes=..., edges=...)

输出: MermaidResult 含 png_path / data_uri / mermaid_code / method / warnings
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from backend.app.services.multimodal.mermaid.renderer import MermaidRenderer
from backend.app.services.multimodal.mermaid.spec import (
    ClassDiagramSpec,
    DiagramSpec,
    FlowchartSpec,
    GraphEdge,
    GraphNode,
    GraphSpec,
    MermaidResult,
    MindmapNode,
    MindmapSpec,
    SequenceSpec,
)
from backend.app.services.multimodal.mermaid.templates import (
    build_mermaid_code,
)
from backend.app.services.multimodal.mermaid.validator import (
    MermaidValidator,
)


logger = logging.getLogger(__name__)


class MermaidStudio:
    """统一 Mermaid 工作室"""

    def __init__(
        self,
        renderer: Optional[MermaidRenderer] = None,
        validator: Optional[MermaidValidator] = None,
    ):
        self.renderer = renderer or MermaidRenderer()
        self.validator = validator or MermaidValidator()

    # ----------------------------------------------------------------
    # 主接口 1: 从 Pydantic spec 渲染
    # ----------------------------------------------------------------
    def render_spec(self, spec: DiagramSpec) -> MermaidResult:
        """从 spec → mermaid code → PNG"""
        start = time.perf_counter()
        code = build_mermaid_code(spec)
        return self._validate_and_render(
            code, kind=spec.kind, name_hint=getattr(spec, "title", ""),
            start=start,
        )

    # ----------------------------------------------------------------
    # 主接口 2: 从已有 Mermaid 代码渲染
    # ----------------------------------------------------------------
    def render_code(
        self, code: str, *, kind: str = "unknown", name_hint: str = "",
    ) -> MermaidResult:
        start = time.perf_counter()
        return self._validate_and_render(
            code, kind=kind, name_hint=name_hint, start=start,
        )

    # ----------------------------------------------------------------
    # 主接口 3: 概念词 → mindmap (一键 demo)
    # ----------------------------------------------------------------
    def from_concept(
        self,
        title: str,
        branches: List[str],
        leaves: Optional[Dict[str, List[str]]] = None,
    ) -> MermaidResult:
        """快速从主题词构建 mindmap

        Args:
            title:    中心主题
            branches: 一级分支文本列表
            leaves:   {branch_text: [leaf1, leaf2, ...]} 二级叶子 (可选)
        """
        leaves = leaves or {}
        root = MindmapNode(
            text=title or "主题",
            children=[
                MindmapNode(
                    text=b,
                    children=[
                        MindmapNode(text=lf)
                        for lf in leaves.get(b, [])[:6]
                    ],
                )
                for b in branches[:8]
            ],
        )
        spec = MindmapSpec(root=root)
        return self.render_spec(spec)

    # ----------------------------------------------------------------
    # 主接口 4: GraphRAG / 知识图谱 → 可视化
    # ----------------------------------------------------------------
    def render_knowledge_graph(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        title: str = "知识图谱",
        directed: bool = True,
    ) -> MermaidResult:
        """从 GraphRAG 的实体 / 关系数据渲染知识图谱

        Args:
            nodes: [{id, label, weight?, group?}]
            edges: [{source, target, label?, weight?}]
        """
        gnodes = [
            GraphNode(
                id=str(n.get("id", f"n{i}")),
                label=str(n.get("label", n.get("id", f"n{i}")))[:60],
                weight=float(n.get("weight", 1.0)),
                group=str(n.get("group", "")),
            )
            for i, n in enumerate(nodes[:50])
        ]
        node_ids = {n.id for n in gnodes}
        gedges: List[GraphEdge] = []
        for e in edges[:120]:
            s = str(e.get("source", ""))
            t = str(e.get("target", ""))
            if s in node_ids and t in node_ids:
                gedges.append(GraphEdge(
                    source=s, target=t,
                    label=str(e.get("label", ""))[:30],
                    weight=float(e.get("weight", 1.0)),
                ))
        spec = GraphSpec(
            nodes=gnodes, edges=gedges,
            directed=directed, title=title,
        )
        return self.render_spec(spec)

    # ----------------------------------------------------------------
    # 内部: 校验 + 渲染
    # ----------------------------------------------------------------
    def _validate_and_render(
        self, code: str, *, kind: str, name_hint: str, start: float,
    ) -> MermaidResult:
        # Bound work before invoking validators or browser renderers.
        if len(code) > 20000 or code.count("\n") > 300:
            return MermaidResult(
                kind=kind, mermaid_code=code, validation_passed=False,
                error="Mermaid source exceeds size limits", method="validation_failed",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        # 1) Validate
        report = self.validator.validate(code)
        validation_passed = report.passed()
        warnings = [
            f"[{i.code}] {i.message}"
            for i in report.warnings()
        ]
        errors = [
            f"[{i.code}] {i.message}"
            for i in report.errors()
        ]

        if not validation_passed:
            # 即使语法有错也尝试 placeholder 渲染, 不阻塞演示
            return MermaidResult(
                kind=kind, mermaid_code=code,
                validation_passed=False,
                warnings=warnings, error="; ".join(errors),
                method="validation_failed",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        # 2) Render
        r = self.renderer.render(code, name_hint=name_hint or kind)

        result = MermaidResult(
            kind=kind, mermaid_code=code,
            png_path=r.png_path, data_uri=r.data_uri,
            method=r.method,
            width_px=r.width_px, height_px=r.height_px,
            validation_passed=True,
            warnings=warnings,
            error=r.error,
            duration_ms=(time.perf_counter() - start) * 1000,
        )
        return result


# ================================================================
# 单例
# ================================================================
_studio: Optional[MermaidStudio] = None


def get_mermaid_studio() -> MermaidStudio:
    global _studio
    if _studio is None:
        _studio = MermaidStudio()
    return _studio


def reset_studio() -> None:
    global _studio
    _studio = None
