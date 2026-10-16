"""
Mermaid Studio 子包 (P1-4)

针对赛题 "思维导图 / 流程图 / 知识图谱" 等可视化需求,
提供:
- 5 种声明式 Pydantic Spec (mindmap/flowchart/sequence/class/graph)
- 智能 diagram 类型识别 (detect_intent)
- Mermaid 语法预校验 (避免渲染时崩溃)
- 3 级降级渲染 (mmdc → Playwright → PIL 占位)
- 主入口: MermaidStudio

替代原 32 行 spaghetti mermaid_renderer.py。
"""
from __future__ import annotations

from backend.app.services.multimodal.mermaid.intent import (
    detect_intent,
    list_supported_kinds,
)
from backend.app.services.multimodal.mermaid.renderer import (
    MermaidRenderer,
    RenderResult,
)
from backend.app.services.multimodal.mermaid.spec import (
    ClassDiagramSpec,
    ClassEntity,
    ClassMember,
    ClassRelation,
    DiagramSpec,
    DiagramTheme,
    FlowEdge,
    FlowNode,
    FlowchartSpec,
    GraphEdge,
    GraphNode,
    GraphSpec,
    MermaidResult,
    MindmapNode,
    MindmapSpec,
    SequenceMessage,
    SequenceSpec,
)
from backend.app.services.multimodal.mermaid.studio import (
    MermaidStudio,
    get_mermaid_studio,
    reset_studio,
)
from backend.app.services.multimodal.mermaid.templates import (
    build_mermaid_code,
)
from backend.app.services.multimodal.mermaid.validator import (
    MermaidValidator,
    ValidationReport,
)


__all__ = [
    # spec
    "DiagramTheme",
    "MindmapNode", "MindmapSpec",
    "FlowNode", "FlowEdge", "FlowchartSpec",
    "SequenceMessage", "SequenceSpec",
    "ClassMember", "ClassEntity", "ClassRelation", "ClassDiagramSpec",
    "GraphNode", "GraphEdge", "GraphSpec",
    "DiagramSpec",
    "MermaidResult",
    # templates
    "build_mermaid_code",
    # validator
    "MermaidValidator",
    "ValidationReport",
    # renderer
    "MermaidRenderer",
    "RenderResult",
    # intent
    "detect_intent",
    "list_supported_kinds",
    # studio
    "MermaidStudio",
    "get_mermaid_studio",
    "reset_studio",
]
