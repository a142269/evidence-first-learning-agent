"""
Manim 教学动画子系统 (Phase 3 Innovation 2)

公开 API:
    - dsl.py:        ManimDSLSpec + Scene/Element/Animation 数据模型
    - compiler.py:   DSLCompiler (DSL→Python) + ManimSafetyValidator
    - templates.py:  SceneTemplateFactory + 5 种 TeacherPersona
    - renderer.py:   ManimRenderer 三级降级 (manim→Playwright→placeholder)
    - lecturer.py:   AILecturerAgent (Agent 形态)
"""
from __future__ import annotations

from backend.app.services.multimodal.manim.dsl import (
    AnimationStep,
    AnimationType,
    Color,
    ElementStyle,
    ElementType,
    ManimDSLSpec,
    Position,
    Scene,
    SceneElement,
)
from backend.app.services.multimodal.manim.compiler import (
    CompilationError,
    DSLCompiler,
    ManimSafetyValidator,
    SafetyError,
)
from backend.app.services.multimodal.manim.templates import (
    PERSONAS,
    PersonaStyle,
    SceneTemplateFactory,
    TeacherPersona,
)
from backend.app.services.multimodal.manim.renderer import (
    ManimRenderer,
    RenderResult,
    get_manim_renderer,
)
# 注: AILecturerAgent 不在此导出 —— 它属于 agents 层 (依赖 agents.base)。
# 若在此导入会造成 manim → agents → manim 的循环引用。
# 需要时直接 from backend.app.services.multimodal.manim.lecturer import AILecturerAgent。

__all__ = [
    # DSL
    "ManimDSLSpec", "Scene", "SceneElement", "ElementStyle",
    "AnimationStep", "AnimationType", "ElementType",
    "Position", "Color", "PersonaStyle",
    # Compiler
    "DSLCompiler", "ManimSafetyValidator",
    "CompilationError", "SafetyError",
    # Templates
    "SceneTemplateFactory", "TeacherPersona", "PERSONAS",
    # Renderer
    "ManimRenderer", "RenderResult", "get_manim_renderer",
]
