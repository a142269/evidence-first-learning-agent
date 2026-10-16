"""
PPTX 子包 - 声明式 + 教学法驱动 + 7 layouts + SVG/Mermaid 嵌入 + QR 深链 + Linter

公共入口:
- SlideDeckSpec        声明式大纲
- SlideDeckBuilder     主构建器
- get_slide_deck_builder() 单例

兼容旧 API:
- PPTXOutline / SlideContent / PPTXBuilder 仍可在 pptx_builder.py 处获取
"""
from __future__ import annotations

from backend.app.services.multimodal.pptx.builder import (
    SlideDeckBuilder,
    get_slide_deck_builder,
    reset_builder,
)
from backend.app.services.multimodal.pptx.linter import LintReport, PPTXLinter
from backend.app.services.multimodal.pptx.spec import (
    AgendaSlide,
    Asset,
    BloomLevel,
    CheckpointSlide,
    CodeSlide,
    ComparisonSlide,
    ConceptSlide,
    CoverSlide,
    DeckBuildResult,
    DeckMeta,
    SlideDeckSpec,
    SlideRenderResult,
    SlideSpec,
    WorkedExampleSlide,
)
from backend.app.services.multimodal.pptx.theme import (
    THEMES,
    Theme,
    contrast_ratio,
    get_theme,
    list_themes,
    meets_wcag_aa,
)

__all__ = [
    # spec
    "BloomLevel",
    "Asset",
    "DeckMeta",
    "SlideDeckSpec",
    "SlideSpec",
    "CoverSlide",
    "AgendaSlide",
    "ConceptSlide",
    "ComparisonSlide",
    "WorkedExampleSlide",
    "CodeSlide",
    "CheckpointSlide",
    "DeckBuildResult",
    "SlideRenderResult",
    # theme
    "Theme",
    "THEMES",
    "get_theme",
    "list_themes",
    "contrast_ratio",
    "meets_wcag_aa",
    # builder
    "SlideDeckBuilder",
    "get_slide_deck_builder",
    "reset_builder",
    # linter
    "PPTXLinter",
    "LintReport",
]
