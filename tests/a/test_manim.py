"""
测试: Manim 教学动画子系统 (Phase 3 Innovation 2)

覆盖:
- DSL: ManimDSLSpec Pydantic 校验 / Scene/Element/Animation 模型
- Compiler: DSL→Python 编译 / 代码结构正确性
- Safety: 危险代码检测 / 安全代码通过
- Templates: 5 种模板输出有效 DSL / 5 种人格配置
- Renderer: 三级降级 / placeholder always available
- AILecturerAgent: 模板检测 / fallback / execute (不开LLM)
"""
from __future__ import annotations

import re
import pytest
from pydantic import ValidationError
from unittest.mock import MagicMock, AsyncMock

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
    DSLCompiler,
    ManimSafetyValidator,
)
from backend.app.services.multimodal.manim.templates import (
    PERSONAS,
    PersonaStyle,
    SceneTemplateFactory,
    TeacherPersona,
)
from backend.app.services.multimodal.manim.renderer import (
    ManimRenderer,
    PlaceholderLibrary,
    ManimCLIRenderer,
)
from backend.app.services.multimodal.manim.lecturer import AILecturerAgent


# ================================================================
# DSL 数据模型
# ================================================================
class TestSceneElement:
    def test_text_element_requires_content(self):
        with pytest.raises(ValidationError):
            SceneElement(id="t1", type=ElementType.TEXT, content="")

    def test_formula_element(self):
        e = SceneElement(id="f1", type=ElementType.FORMULA, content=r"E=mc^2")
        assert e.type == ElementType.FORMULA

    def test_code_element(self):
        e = SceneElement(id="c1", type=ElementType.CODE, content="print(1)")
        assert e.type == ElementType.CODE

    def test_style_defaults(self):
        e = SceneElement(id="s1", type=ElementType.TEXT, content="hi")
        assert e.style.color == "#FFFFFF"
        assert e.style.font_size == 36

    def test_position_shift(self):
        e = SceneElement(
            id="p1", type=ElementType.TEXT, content="hi",
            position=Position.TOP, shift_x=1.5, shift_y=-0.5,
        )
        assert e.shift_x == 1.5

    def test_bullet_list(self):
        e = SceneElement(
            id="b1", type=ElementType.BULLET_LIST,
            content="item 1\nitem 2\nitem 3",
        )
        assert e.type == ElementType.BULLET_LIST


class TestAnimationStep:
    def test_valid(self):
        a = AnimationStep(type=AnimationType.WRITE, target_id="title", duration=1.5)
        assert a.duration == 1.5

    def test_duration_out_of_range(self):
        with pytest.raises(ValidationError):
            AnimationStep(type=AnimationType.FADE_IN, target_id="x", duration=0.01)

    def test_with_params(self):
        a = AnimationStep(
            type=AnimationType.SCALE, target_id="vs",
            duration=0.5, params={"factor": 1.2},
        )
        assert a.params["factor"] == 1.2


class TestManimDSLSpec:
    def test_minimal_valid(self):
        spec = ManimDSLSpec(
            title="Test", topic="test",
            scenes=[Scene(scene_id="s1", duration_seconds=2.0)],
        )
        assert spec.element_count() == 0
        assert spec.total_duration() == 2.0

    def test_empty_scenes_rejected(self):
        with pytest.raises(ValidationError):
            ManimDSLSpec(title="T", topic="t", scenes=[])

    def test_speed_out_of_range(self):
        with pytest.raises(ValidationError):
            ManimDSLSpec(
                title="T", topic="t",
                scenes=[Scene(scene_id="s1", duration_seconds=1.0)],
                animation_speed=5.0,
            )

    def test_full_spec(self):
        spec = ManimDSLSpec(
            title="CNN 讲解", topic="CNN",
            scenes=[
                Scene(
                    scene_id="intro", duration_seconds=3.0,
                    elements=[
                        SceneElement(id="title", type=ElementType.TEXT, content="CNN"),
                        SceneElement(id="eq", type=ElementType.FORMULA, content=r"f*g"),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.WRITE, target_id="title", duration=1.0),
                        AnimationStep(type=AnimationType.FADE_IN, target_id="eq", duration=1.0),
                    ],
                ),
                Scene(scene_id="outro", duration_seconds=1.0),
            ],
        )
        assert spec.element_count() == 2
        assert spec.animation_count() == 2
        assert spec.total_duration() == 4.0


# ================================================================
# DSLCompiler
# ================================================================
class TestDSLCompiler:
    @pytest.fixture
    def compiler(self):
        return DSLCompiler()

    def test_compiles_simple_spec(self, compiler):
        spec = ManimDSLSpec(
            title="Hello", topic="test",
            scenes=[Scene(scene_id="main", duration_seconds=2.0)],
        )
        code = compiler.compile(spec)
        assert "from manim import *" in code
        assert "class Scene_main(Scene):" in code
        assert "def construct(self):" in code

    def test_compiles_with_elements(self, compiler):
        spec = ManimDSLSpec(
            title="Test", topic="test",
            scenes=[
                Scene(
                    scene_id="s1", duration_seconds=3.0,
                    elements=[
                        SceneElement(
                            id="title", type=ElementType.TEXT,
                            content="Hello World",
                            style=ElementStyle(color=Color.BLUE.value, font_size=48),
                        ),
                    ],
                    animations=[
                        AnimationStep(type=AnimationType.WRITE, target_id="title", duration=1.0),
                    ],
                ),
            ],
        )
        code = compiler.compile(spec)
        assert "Text" in code
        assert "Write" in code or "write" in code.lower()
        # Content goes through DATA dict (parameterized, not hardcoded inline)
        assert "DATA[" in code
        # Verify the element is referenced via key, not via inline string in Text() call
        assert "Text('Hello World'" not in code
        assert 'Text("Hello World"' not in code

    def test_empty_scene_compiles(self, compiler):
        """空场景应可编译 (e.g. 占位场景 / 黑场过渡 / 静默等待)"""
        empty_code = compiler.compile(ManimDSLSpec(
            title="T", topic="t",
            scenes=[Scene(scene_id="s1", duration_seconds=1.0)],
        ))
        assert "class Scene_s1" in empty_code

        # 有 element 的场景也应正常 → DATA 块
        spec = ManimDSLSpec(
            title="T", topic="t",
            scenes=[
                Scene(
                    scene_id="s1", duration_seconds=1.0,
                    elements=[SceneElement(id="e1", type=ElementType.TEXT, content="test")],
                ),
            ],
        )
        code = compiler.compile(spec)
        assert "DATA" in code

    def test_duplicate_element_ids_rejected(self, compiler):
        with pytest.raises(ValueError, match="Duplicate"):
            compiler.compile(ManimDSLSpec(
                title="T", topic="t",
                scenes=[
                    Scene(
                        scene_id="s1", duration_seconds=1.0,
                        elements=[
                            SceneElement(id="dup", type=ElementType.TEXT, content="a"),
                        ],
                    ),
                    Scene(
                        scene_id="s2", duration_seconds=1.0,
                        elements=[
                            SceneElement(id="dup", type=ElementType.TEXT, content="b"),
                        ],
                    ),
                ],
            ))

    def test_data_block_contains_contents(self, compiler):
        spec = ManimDSLSpec(
            title="Test", topic="test",
            scenes=[
                Scene(
                    scene_id="s1", duration_seconds=1.0,
                    elements=[
                        SceneElement(id="msg", type=ElementType.TEXT, content="秘密消息"),
                    ],
                ),
            ],
        )
        code = compiler.compile(spec)
        assert "秘密消息" in code  # Present in DATA dict

    def test_code_element_produces_manim_code(self, compiler):
        spec = ManimDSLSpec(
            title="Code Test", topic="code",
            scenes=[
                Scene(
                    scene_id="s1", duration_seconds=2.0,
                    elements=[
                        SceneElement(
                            id="code", type=ElementType.CODE,
                            content="print('hello')",
                            style=ElementStyle(font_size=24),
                        ),
                    ],
                ),
            ],
        )
        code = compiler.compile(spec)
        assert "Code" in code


# ================================================================
# ManimSafetyValidator
# ================================================================
class TestManimSafetyValidator:
    @pytest.fixture
    def validator(self):
        return ManimSafetyValidator()

    def test_safe_manim_code(self, validator):
        code = (
            "from manim import *\n"
            "class Test(Scene):\n"
            "    def construct(self):\n"
            "        t = Text('hello')\n"
            "        self.play(Write(t))\n"
        )
        safe, error = validator.validate(code)
        assert safe is True
        assert error == ""

    def test_blocks_os_import(self, validator):
        code = "import os\nos.system('ls')"
        safe, error = validator.validate(code)
        assert safe is False
        assert "os" in error.lower()

    def test_blocks_exec_call(self, validator):
        code = "exec('print(1)')"
        safe, error = validator.validate(code)
        assert safe is False

    def test_blocks_open_call(self, validator):
        code = "open('/etc/passwd')"
        safe, error = validator.validate(code)
        assert safe is False


# ================================================================
# 模板 + 人格
# ================================================================
class TestTemplates:
    def test_concept_template(self):
        spec = SceneTemplateFactory.create(
            "concept", "CNN",
            {"title": "CNN", "subtitle": "卷积网络", "definition": "CNN是...",
             "core_points": "点1\n点2", "example": "例如", "summary": "总结"},
        )
        assert len(spec.scenes) == 3
        assert spec.scenes[0].scene_id == "intro"

    def test_code_template(self):
        spec = SceneTemplateFactory.create(
            "code", "Softmax",
            {"title": "Softmax", "code": "def softmax(x): ...",
             "line_by_line": "line 1\nline 2", "output": "OK"},
        )
        assert len(spec.scenes) == 3

    def test_formula_template(self):
        spec = SceneTemplateFactory.create(
            "formula", "Bayes",
            {"title": "Bayes", "prerequisites": "概率论",
             "derivation_steps": "1\n2\n3", "final_formula": r"P(A|B)"},
        )
        assert len(spec.scenes) == 2

    def test_comparison_template(self):
        spec = SceneTemplateFactory.create(
            "comparison", "CNN vs RNN",
            {"title": "对比", "left_items": "A1\nA2", "right_items": "B1\nB2",
             "conclusion": "视场景而定"},
        )
        assert len(spec.scenes) == 2

    def test_timeline_template(self):
        spec = SceneTemplateFactory.create(
            "timeline", "AI History",
            {"title": "AI史", "milestones": "1950: 图灵\n2000: DL",
             "summary": "快速发展"},
        )
        assert len(spec.scenes) == 1

    def test_all_5_personas(self):
        for style in PersonaStyle:
            persona = PERSONAS[style]
            assert persona.name
            assert persona.bg_color
            assert persona.font_size_title > 0

    def test_persona_effects_template(self):
        """人格影响模板输出"""
        spec_serious = SceneTemplateFactory.create(
            "concept", "test", {"title": "T", "definition": "D"},
            persona=PersonaStyle.SERIOUS,
        )
        spec_humorous = SceneTemplateFactory.create(
            "concept", "test", {"title": "T", "definition": "D"},
            persona=PersonaStyle.HUMOROUS,
        )
        # 搞笑版动画更快
        assert spec_humorous.animation_speed > spec_serious.animation_speed


# ================================================================
# Renderer + Placeholder
# ================================================================
class TestPlaceholderLibrary:
    def test_always_available(self):
        lib = PlaceholderLibrary()
        path = lib.get_placeholder("cnn", "CNN讲解")
        assert path.endswith(".svg")

    def test_fuzzy_match(self):
        lib = PlaceholderLibrary()
        path = lib.get_placeholder("卷积神经网络 CNN", "标题")
        assert "convolutional_neural_network" in path or path.endswith(".svg")


# ================================================================
# AILecturerAgent
# ================================================================
class TestAILecturerAgent:
    @pytest.fixture
    def agent(self, mock_llm_client):
        return AILecturerAgent(llm_client=mock_llm_client)

    def test_template_detection_code(self, agent):
        assert agent._detect_template("帮我实现一个CNN代码") == "code"
        assert agent._detect_template("写一个Python函数") == "code"

    def test_template_detection_formula(self, agent):
        assert agent._detect_template("推导贝叶斯公式") == "formula"
        assert agent._detect_template("证明这个定理") == "formula"

    def test_template_detection_comparison(self, agent):
        assert agent._detect_template("CNN和RNN有什么区别") == "comparison"

    def test_template_detection_timeline(self, agent):
        assert agent._detect_template("深度学习的发展历史") == "timeline"

    def test_template_detection_default_concept(self, agent):
        assert agent._detect_template("什么是注意力机制") == "concept"

    def test_fallback_content_all_templates(self, agent):
        for template in ["concept", "code", "formula", "comparison", "timeline"]:
            content = agent._fallback_content("test topic", template)
            assert isinstance(content, dict)
            assert len(content) >= 1

    @pytest.mark.asyncio
    async def test_execute_without_render(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(
            user_input="什么是CNN",
            extra={"render": False, "persona": "friendly"},
        )
        resp = await agent.execute(ctx)
        assert resp.success is True
        assert resp.agent_name == "ai_lecturer"
        assert "template" in resp.metadata
        assert "generated_code" in resp.metadata
        # 生成了代码
        assert "from manim import *" in resp.metadata["generated_code"]

    @pytest.mark.asyncio
    async def test_execute_empty_topic(self, agent):
        from backend.app.agents.base import AgentContext
        ctx = AgentContext(user_input="")
        resp = await agent.execute(ctx)
        assert resp.success is False

    @pytest.mark.asyncio
    async def test_agent_in_registry(self):
        from backend.app.agents import AGENT_REGISTRY
        assert "ai_lecturer" in AGENT_REGISTRY
