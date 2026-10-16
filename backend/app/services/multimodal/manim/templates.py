"""
Teacher Personas + Scene Templates — 教学人格与场景模板系统

5 种人格:
    serious    — 严肃博士: 学术严谨，深色系，适合理工科讲解
    friendly   — 邻家学姐: 温和亲切，暖色系，适合入门引导
    humorous   — 段子手老师: 活泼幽默，高对比色，适合趣味教学
    minimalist — 极简工程师: 简洁高效，低饱和色，适合代码讲解
    academic   — 古典教授: 典雅庄重，暖暗色，适合理论推导

5 种场景模板:
    concept_explanation  — 概念讲解: 标题→定义→核心→例子→总结
    code_walkthrough     — 代码走读: 标题→代码块→逐行讲解→运行结果
    formula_derivation   — 公式推导: 标题→前置→推导步骤→最终公式
    comparison           — 对比分析: 标题→左项→右项→对比表→结论
    timeline             — 时间线: 标题→时间轴→关键节点→里程碑→总结

每套模板预定义了元素布局、动画序列、时长分配。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.multimodal.manim.dsl import (
    AnimationStep,
    AnimationType,
    Color,
    ElementType,
    ManimDSLSpec,
    Position,
    Scene,
    SceneElement,
    ElementStyle,
)


# ================================================================
# 教师人格
# ================================================================
class PersonaStyle(str, Enum):
    SERIOUS = "serious"
    FRIENDLY = "friendly"
    HUMOROUS = "humorous"
    MINIMALIST = "minimalist"
    ACADEMIC = "academic"


@dataclass
class TeacherPersona:
    """教学人格配置 — 控制视觉风格 + 教学策略"""
    id: PersonaStyle
    name: str
    tagline: str                        # 一句人设
    # 视觉
    bg_color: str
    primary_color: str
    accent_color: str
    text_color: str
    font_size_title: int
    font_size_body: int
    # 教学策略
    animation_speed: float              # 全局动画速度
    explanation_depth: str              # "basic" / "intermediate" / "advanced"
    humor_level: float                  # 0.0-1.0
    use_analogies: bool
    use_formulas: bool
    example_count: int                  # 期望例子数
    # TTS 音色
    tts_voice: str


# 5 种预定义人格
PERSONAS: Dict[PersonaStyle, TeacherPersona] = {
    PersonaStyle.SERIOUS: TeacherPersona(
        id=PersonaStyle.SERIOUS,
        name="严肃博士",
        tagline="严谨治学，一丝不苟",
        bg_color="#0D1117",
        primary_color=Color.TEAL.value,
        accent_color=Color.ORANGE.value,
        text_color=Color.WHITE.value,
        font_size_title=44,
        font_size_body=32,
        animation_speed=0.85,
        explanation_depth="advanced",
        humor_level=0.1,
        use_analogies=False,
        use_formulas=True,
        example_count=1,
        tts_voice="xiaokun",
    ),
    PersonaStyle.FRIENDLY: TeacherPersona(
        id=PersonaStyle.FRIENDLY,
        name="邻家学姐",
        tagline="轻松学习，一起进步",
        bg_color="#1B1B2F",
        primary_color=Color.PINK.value,
        accent_color=Color.GOLD.value,
        text_color=Color.WHITE.value,
        font_size_title=42,
        font_size_body=30,
        animation_speed=1.0,
        explanation_depth="basic",
        humor_level=0.3,
        use_analogies=True,
        use_formulas=False,
        example_count=3,
        tts_voice="xiaoqian",
    ),
    PersonaStyle.HUMOROUS: TeacherPersona(
        id=PersonaStyle.HUMOROUS,
        name="段子手老师",
        tagline="笑着学，记得牢",
        bg_color="#1A0A2E",
        primary_color=Color.YELLOW.value,
        accent_color=Color.PINK.value,
        text_color=Color.WHITE.value,
        font_size_title=48,
        font_size_body=34,
        animation_speed=1.2,
        explanation_depth="basic",
        humor_level=0.8,
        use_analogies=True,
        use_formulas=False,
        example_count=4,
        tts_voice="xiaoxin",
    ),
    PersonaStyle.MINIMALIST: TeacherPersona(
        id=PersonaStyle.MINIMALIST,
        name="极简工程师",
        tagline="少即是多，直击本质",
        bg_color="#0A0A0A",
        primary_color=Color.GREEN.value,
        accent_color=Color.BLUE.value,
        text_color=Color.LIGHT_GRAY.value,
        font_size_title=40,
        font_size_body=28,
        animation_speed=0.7,
        explanation_depth="intermediate",
        humor_level=0.0,
        use_analogies=False,
        use_formulas=True,
        example_count=1,
        tts_voice="xiaofeng",
    ),
    PersonaStyle.ACADEMIC: TeacherPersona(
        id=PersonaStyle.ACADEMIC,
        name="古典教授",
        tagline="追本溯源，格物致知",
        bg_color="#2C1810",
        primary_color=Color.GOLD.value,
        accent_color=Color.RED.value,
        text_color="#F5E6D3",
        font_size_title=42,
        font_size_body=30,
        animation_speed=0.9,
        explanation_depth="advanced",
        humor_level=0.05,
        use_analogies=True,
        use_formulas=True,
        example_count=2,
        tts_voice="zhixiang",
    ),
}


# ================================================================
# 场景模板工厂
# ================================================================
class SceneTemplateFactory:
    """根据主题 + 人格生成预填充的 ManimDSLSpec"""

    @classmethod
    def create(
        cls,
        template: str,
        topic: str,
        content: Dict[str, str],
        persona: PersonaStyle = PersonaStyle.SERIOUS,
    ) -> ManimDSLSpec:
        """创建 DSL Spec

        Args:
            template: "concept" / "code" / "formula" / "comparison" / "timeline"
            topic: 教学主题
            content: 模板所需内容片段
                concept: {title, subtitle, definition, core_points, example, summary}
                code: {title, code, line_by_line, output}
                formula: {title, prerequisites, derivation_steps, final_formula}
                comparison: {title, left_heading, left_items, right_heading, right_items, conclusion}
                timeline: {title, milestones: [{year, event}], summary}
            persona: 教学人格

        Returns:
            完整的 ManimDSLSpec，可直接编译
        """
        p = PERSONAS[persona]

        if template == "concept":
            return cls._concept_template(topic, content, p)
        elif template == "code":
            return cls._code_template(topic, content, p)
        elif template == "formula":
            return cls._formula_template(topic, content, p)
        elif template == "comparison":
            return cls._comparison_template(topic, content, p)
        elif template == "timeline":
            return cls._timeline_template(topic, content, p)
        else:
            raise ValueError(f"Unknown template: {template}")

    @classmethod
    def _concept_template(
        cls, topic: str, c: Dict[str, str], p: TeacherPersona,
    ) -> ManimDSLSpec:
        """概念讲解: 标题→定义→核心→例子→总结"""
        intro_elements: List[SceneElement] = [
            SceneElement(
                id="title", type=ElementType.TEXT,
                content=c.get("title", topic),
                position=Position.TOP,
                style=ElementStyle(color=p.primary_color, font_size=p.font_size_title),
            ),
        ]
        intro_animations: List[AnimationStep] = [
            AnimationStep(type=AnimationType.WRITE, target_id="title", duration=1.2),
        ]
        subtitle_text = SceneTemplateFactory._coerce_text(c.get("subtitle"))
        if subtitle_text:
            intro_elements.append(SceneElement(
                id="subtitle", type=ElementType.TEXT,
                content=subtitle_text,
                position=Position.CENTER,
                style=ElementStyle(color=p.text_color, font_size=p.font_size_body - 4),
                shift_y=-0.5,
            ))
            intro_animations.append(AnimationStep(
                type=AnimationType.FADE_IN, target_id="subtitle",
                duration=1.0, delay=0.3,
            ))

        return ManimDSLSpec(
            title=c.get("title", topic),
            description=f"{p.name}讲解: {topic}",
            topic=topic,
            concept_tags=[topic],
            color_scheme="dark",
            animation_speed=p.animation_speed,
            scenes=[
                # Scene 1: 标题 + 定义 (3s)
                Scene(
                    scene_id="intro",
                    title="引入",
                    duration_seconds=3.0,
                    background_color=p.bg_color,
                    elements=intro_elements,
                    animations=intro_animations,
                ),
                # Scene 2: 定义 + 核心要点 (5s)
                cls._build_core_scene(c, p),
                # Scene 3: 例子 + 总结 (4s) — 若都为空则跳过此场景
                *cls._build_example_scene(c, p),
            ],
        )

    @staticmethod
    def _coerce_text(v: Any) -> str:
        """归一化 — 列表用 \n 拼接, 字符串去空白, 其它 str()"""
        if v is None:
            return ""
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, (list, tuple)):
            return "\n".join(str(x).strip() for x in v if x).strip()
        return str(v).strip()

    @staticmethod
    def _build_core_scene(c: Dict[str, Any], p: TeacherPersona) -> Scene:
        elements: List[SceneElement] = [
            SceneElement(
                id="heading", type=ElementType.TEXT,
                content="核心要点",
                position=Position.TOP,
                style=ElementStyle(color=p.accent_color, font_size=p.font_size_title - 4),
            ),
        ]
        animations: List[AnimationStep] = [
            AnimationStep(type=AnimationType.FADE_IN, target_id="heading", duration=0.5),
        ]
        definition = SceneTemplateFactory._coerce_text(c.get("definition"))
        if definition:
            elements.append(SceneElement(
                id="definition", type=ElementType.TEXT,
                content=definition,
                position=Position.CENTER,
                style=ElementStyle(color=p.text_color, font_size=p.font_size_body),
            ))
            animations.append(AnimationStep(
                type=AnimationType.WRITE, target_id="definition",
                duration=2.0, delay=0.3,
            ))
        points = SceneTemplateFactory._coerce_text(c.get("core_points"))
        if points:
            elements.append(SceneElement(
                id="points", type=ElementType.BULLET_LIST,
                content=points,
                position=Position.BOTTOM,
                style=ElementStyle(color=p.text_color, font_size=p.font_size_body - 4),
                shift_y=-0.3,
            ))
            animations.append(AnimationStep(
                type=AnimationType.FADE_IN, target_id="points",
                duration=1.5, delay=0.5,
            ))
        return Scene(
            scene_id="core",
            title="核心要点",
            duration_seconds=5.0,
            background_color=p.bg_color,
            elements=elements,
            animations=animations,
        )

    @staticmethod
    def _build_example_scene(
        c: Dict[str, Any], p: TeacherPersona,
    ) -> List[Scene]:
        """例子 + 总结场景 — 若都为空则返回空列表 (跳过该场景)"""
        example_text = SceneTemplateFactory._coerce_text(c.get("example"))
        summary_text = SceneTemplateFactory._coerce_text(c.get("summary"))
        if not example_text and not summary_text:
            return []
        elements: List[SceneElement] = []
        animations: List[AnimationStep] = []
        if example_text:
            elements.append(SceneElement(
                id="example", type=ElementType.TEXT,
                content=example_text,
                position=Position.CENTER,
                style=ElementStyle(color=p.accent_color, font_size=p.font_size_body - 2),
                shift_y=0.5,
            ))
            animations.append(AnimationStep(
                type=AnimationType.WRITE, target_id="example", duration=1.5,
            ))
        if summary_text:
            elements.append(SceneElement(
                id="summary", type=ElementType.TEXT,
                content=summary_text,
                position=Position.BOTTOM,
                style=ElementStyle(color=p.text_color, font_size=p.font_size_body - 2),
                shift_y=-0.5,
            ))
            animations.append(AnimationStep(
                type=AnimationType.FADE_IN, target_id="summary",
                duration=1.5, delay=0.5,
            ))
        return [Scene(
            scene_id="example",
            title="例子与总结",
            duration_seconds=4.0,
            background_color=p.bg_color,
            elements=elements,
            animations=animations,
        )]

    @classmethod
    def _code_template(
        cls, topic: str, c: Dict[str, str], p: TeacherPersona,
    ) -> ManimDSLSpec:
        """代码走读: 标题→代码→逐行讲解→结果"""
        return ManimDSLSpec(
            title=c.get("title", f"{topic} 代码讲解"),
            description=f"{p.name}讲解: {topic}",
            topic=topic,
            color_scheme="dark",
            animation_speed=p.animation_speed,
            scenes=[
                Scene(
                    scene_id="code_intro",
                    title="代码走读",
                    duration_seconds=2.0,
                    background_color=p.bg_color,
                    elements=[
                        SceneElement(
                            id="title", type=ElementType.TEXT,
                            content=c.get("title", topic),
                            position=Position.TOP,
                            style=ElementStyle(color=p.primary_color, font_size=p.font_size_title),
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.WRITE, target_id="title", duration=1.0),
                    ],
                ),
                Scene(
                    scene_id="code_main",
                    title="代码",
                    duration_seconds=6.0,
                    background_color=p.bg_color,
                    elements=[
                        SceneElement(
                            id="code", type=ElementType.CODE,
                            content=c.get("code", "# No code provided"),
                            position=Position.LEFT,
                            style=ElementStyle(font_size=p.font_size_body - 10),
                            width=7.0, height=5.0, shift_x=-3.0,
                        ),
                        SceneElement(
                            id="explanation", type=ElementType.TEXT,
                            content=c.get("line_by_line", ""),
                            position=Position.RIGHT,
                            style=ElementStyle(color=p.text_color, font_size=p.font_size_body - 6),
                            width=5.0, shift_x=3.0,
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.CREATE, target_id="code", duration=2.0),
                        AnimationStep(type=AnimationType.WRITE, target_id="explanation", duration=3.0, delay=0.5),
                    ],
                ),
                Scene(
                    scene_id="code_output",
                    title="运行结果",
                    duration_seconds=2.0,
                    background_color=p.bg_color,
                    elements=[
                        SceneElement(
                            id="output", type=ElementType.TEXT,
                            content=c.get("output", "✓ 运行成功"),
                            position=Position.CENTER,
                            style=ElementStyle(color=Color.GREEN.value, font_size=p.font_size_body),
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.FADE_IN, target_id="output", duration=1.0),
                    ],
                ),
            ],
        )

    @classmethod
    def _formula_template(
        cls, topic: str, c: Dict[str, str], p: TeacherPersona,
    ) -> ManimDSLSpec:
        """公式推导: 标题→前置→推导→最终公式"""
        return ManimDSLSpec(
            title=c.get("title", f"{topic} 公式推导"),
            description=f"{p.name}讲解: {topic}",
            topic=topic,
            color_scheme="dark",
            animation_speed=p.animation_speed,
            scenes=[
                Scene(
                    scene_id="formula_intro",
                    title="前提条件",
                    duration_seconds=3.0,
                    background_color=p.bg_color,
                    elements=[
                        SceneElement(
                            id="title", type=ElementType.TEXT,
                            content=c.get("title", topic),
                            position=Position.TOP,
                            style=ElementStyle(color=p.primary_color, font_size=p.font_size_title),
                        ),
                        SceneElement(
                            id="prereqs", type=ElementType.TEXT,
                            content=c.get("prerequisites", ""),
                            position=Position.CENTER,
                            style=ElementStyle(color=p.text_color, font_size=p.font_size_body - 2),
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.WRITE, target_id="title", duration=1.0),
                        AnimationStep(type=AnimationType.FADE_IN, target_id="prereqs", duration=1.0, delay=0.3),
                    ],
                ),
                Scene(
                    scene_id="formula_steps",
                    title="推导步骤",
                    duration_seconds=6.0,
                    background_color=p.bg_color,
                    elements=[
                        SceneElement(
                            id="steps", type=ElementType.BULLET_LIST,
                            content=c.get("derivation_steps", ""),
                            position=Position.LEFT,
                            style=ElementStyle(color=p.text_color, font_size=p.font_size_body - 4),
                            width=6.0, shift_x=-3.0,
                        ),
                        SceneElement(
                            id="formula", type=ElementType.FORMULA,
                            content=c.get("final_formula", ""),
                            position=Position.RIGHT,
                            style=ElementStyle(color=p.accent_color, font_size=p.font_size_body + 2),
                            shift_x=3.0,
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.WRITE, target_id="steps", duration=3.0),
                        AnimationStep(type=AnimationType.FADE_IN, target_id="formula", duration=2.0, delay=1.0),
                    ],
                ),
            ],
        )

    @classmethod
    def _comparison_template(
        cls, topic: str, c: Dict[str, str], p: TeacherPersona,
    ) -> ManimDSLSpec:
        """对比分析: 标题→左→右→对比→结论"""
        return ManimDSLSpec(
            title=c.get("title", f"{topic} 对比分析"),
            description=p.tagline,
            topic=topic,
            color_scheme="dark",
            animation_speed=p.animation_speed,
            scenes=[
                Scene(
                    scene_id="compare_main",
                    title="对比分析",
                    duration_seconds=5.0,
                    background_color=p.bg_color,
                    elements=[
                        SceneElement(
                            id="title", type=ElementType.TEXT,
                            content=c.get("title", topic),
                            position=Position.TOP,
                            style=ElementStyle(color=p.primary_color, font_size=p.font_size_title),
                        ),
                        SceneElement(
                            id="left", type=ElementType.BULLET_LIST,
                            content=c.get("left_items", ""),
                            position=Position.LEFT,
                            style=ElementStyle(color=Color.BLUE.value, font_size=p.font_size_body - 4),
                            shift_x=-3.5,
                        ),
                        SceneElement(
                            id="right", type=ElementType.BULLET_LIST,
                            content=c.get("right_items", ""),
                            position=Position.RIGHT,
                            style=ElementStyle(color=Color.GREEN.value, font_size=p.font_size_body - 4),
                            shift_x=3.5,
                        ),
                        SceneElement(
                            id="vs", type=ElementType.TEXT,
                            content="VS",
                            position=Position.CENTER,
                            style=ElementStyle(color=p.accent_color, font_size=p.font_size_title),
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.WRITE, target_id="title", duration=0.8),
                        AnimationStep(type=AnimationType.FADE_IN, target_id="left", duration=1.5, delay=0.3),
                        AnimationStep(type=AnimationType.FADE_IN, target_id="right", duration=1.5, delay=0.3),
                        AnimationStep(type=AnimationType.SCALE, target_id="vs", duration=0.5, delay=0.5,
                                     params={"factor": 1.2}),
                    ],
                ),
                Scene(
                    scene_id="compare_conclusion",
                    title="结论",
                    duration_seconds=2.0,
                    background_color=p.bg_color,
                    elements=[
                        SceneElement(
                            id="conclusion", type=ElementType.TEXT,
                            content=c.get("conclusion", ""),
                            position=Position.CENTER,
                            style=ElementStyle(color=p.accent_color, font_size=p.font_size_body),
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.FADE_IN, target_id="conclusion", duration=1.5),
                    ],
                ),
            ],
        )

    @classmethod
    def _timeline_template(
        cls, topic: str, c: Dict[str, str], p: TeacherPersona,
    ) -> ManimDSLSpec:
        """时间线: 标题→节点→里程碑→总结"""
        milestones = c.get("milestones", "")
        items = [m.strip() for m in milestones.split("\n") if m.strip()][:7]

        return ManimDSLSpec(
            title=c.get("title", f"{topic} 发展历程"),
            description=p.tagline,
            topic=topic,
            color_scheme="dark",
            animation_speed=p.animation_speed,
            scenes=[
                Scene(
                    scene_id="timeline_main",
                    title="时间线",
                    duration_seconds=6.0,
                    background_color=p.bg_color,
                    elements=[
                        SceneElement(
                            id="title", type=ElementType.TEXT,
                            content=c.get("title", topic),
                            position=Position.TOP,
                            style=ElementStyle(color=p.primary_color, font_size=p.font_size_title),
                        ),
                        SceneElement(
                            id="milestones", type=ElementType.BULLET_LIST,
                            content="\n".join(items),
                            position=Position.CENTER,
                            style=ElementStyle(color=p.text_color, font_size=p.font_size_body - 6),
                        ),
                        SceneElement(
                            id="summary", type=ElementType.TEXT,
                            content=c.get("summary", ""),
                            position=Position.BOTTOM,
                            style=ElementStyle(color=p.accent_color, font_size=p.font_size_body - 4),
                            shift_y=-0.5,
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.WRITE, target_id="title", duration=0.8),
                        AnimationStep(type=AnimationType.WRITE, target_id="milestones", duration=3.0, delay=0.5),
                        AnimationStep(type=AnimationType.FADE_IN, target_id="summary", duration=1.0, delay=0.5),
                    ],
                ),
            ],
        )
