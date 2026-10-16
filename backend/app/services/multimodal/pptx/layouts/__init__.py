"""
Layouts 包 — 7 个教学法驱动的幻灯片渲染器

按职责拆为 3 个模块:
- intro.py:    Cover / Agenda
- explain.py:  Concept / Comparison / WorkedExample
- practice.py: Code / Checkpoint

通过 LAYOUT_REGISTRY 字典统一查找。
"""
from __future__ import annotations

from typing import Dict

from backend.app.services.multimodal.pptx.layouts._helpers import (
    LayoutRenderer,
    RenderContext,
)
from backend.app.services.multimodal.pptx.layouts.explain import (
    ComparisonLayout,
    ConceptLayout,
    WorkedExampleLayout,
)
from backend.app.services.multimodal.pptx.layouts.intro import (
    AgendaLayout,
    CoverLayout,
)
from backend.app.services.multimodal.pptx.layouts.practice import (
    CheckpointLayout,
    CodeLayout,
)


LAYOUT_REGISTRY: Dict[str, LayoutRenderer] = {
    "cover": CoverLayout(),
    "agenda": AgendaLayout(),
    "concept": ConceptLayout(),
    "comparison": ComparisonLayout(),
    "worked_example": WorkedExampleLayout(),
    "code": CodeLayout(),
    "checkpoint": CheckpointLayout(),
}


def get_layout(name: str) -> LayoutRenderer:
    """根据 layout 名查找 renderer, 未知降级为 concept"""
    return LAYOUT_REGISTRY.get(name) or LAYOUT_REGISTRY["concept"]


__all__ = [
    "LayoutRenderer",
    "RenderContext",
    "CoverLayout",
    "AgendaLayout",
    "ConceptLayout",
    "ComparisonLayout",
    "WorkedExampleLayout",
    "CodeLayout",
    "CheckpointLayout",
    "LAYOUT_REGISTRY",
    "get_layout",
]
