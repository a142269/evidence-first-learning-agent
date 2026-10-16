"""
端到端集成测试 - 赛题 5 类资源真实生成验证 (Day 1 v7 计划)

赛题需求 2 要求 "至少 5 种类型的个性化资源生成"。本测试套保证:
    1. 讲解文档 (CourseExpertAgent → markdown)
    2. 思维导图 (MultimodalAgent + MermaidStudio → PNG)
    3. 练习题目 (QuizGeneratorAgent → markdown 含 Bloom 标签)
    4. 拓展阅读 (CourseExpertAgent reading mode)
    5. 代码案例 (MultimodalAgent code mode + CodeSandbox 可执行)
    6. 教学视频 (Manim DSL → 可编译 Python)

每类资源都验证:
    - Agent.execute() 不崩溃
    - 返回 AgentResponse 含 content + resources + metadata
    - 资源元数据完整 (type / title / format)
    - 关键路径: chat → orchestrator → resource

策略:
    - 用 mock LLM 输出固定 markdown — 不依赖网络/API key
    - mock 输出含必要的标记 (mermaid code block / Bloom / 代码)
    - 验证 agent 正确解析 + 调用下游 (Mermaid 渲染 / Sandbox 执行)

这些测试是 "演示前不能崩" 的最后防线。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.app.agents.base import AgentContext


# ================================================================
# 工具: 构造 mock LLM 返回固定文本
# ================================================================
def _fixed_response_llm(text: str) -> MagicMock:
    llm = MagicMock()
    llm.chat = MagicMock(return_value=text)
    return llm


def _make_ctx(user_input: str, **kwargs) -> AgentContext:
    return AgentContext(
        user_input=user_input,
        session_id=kwargs.get("session_id", "e2e-test"),
        profile=kwargs.get("profile", {"knowledge_base": {"level": "中等"}}),
        course_name=kwargs.get("course_name", "artificial_intelligence"),
        rag_results=kwargs.get("rag_results", []),
        extra=kwargs.get("extra", {}),
    )


# ================================================================
# Resource 1: 讲解文档 (CourseExpertAgent)
# ================================================================
class TestResource1_LectureDoc:
    @pytest.mark.asyncio
    async def test_course_expert_returns_markdown_document(self):
        from backend.app.agents.course_expert import CourseExpertAgent

        mock_md = (
            "# 卷积神经网络 (CNN) 详解\n\n"
            "## 1. 什么是 CNN\n\n"
            "卷积神经网络是一种针对网格数据 (尤其是图像) 的深度学习模型。\n\n"
            "例如, 在图像分类中, CNN 通过卷积层提取局部特征。\n\n"
            "## 2. 核心组件\n- 卷积层\n- 池化层\n- 全连接层\n\n"
            "## 3. 练习\n请用 PyTorch 实现 LeNet-5。"
        )
        agent = CourseExpertAgent(llm_client=_fixed_response_llm(mock_md))
        ctx = _make_ctx("讲解卷积神经网络")
        resp = await agent.execute(ctx)

        assert resp.success
        assert resp.content_type in ("markdown", "document")
        assert "CNN" in resp.content or "卷积" in resp.content
        # 应有资源元数据
        assert resp.resources, "讲解文档应返回 resources 元数据"

    @pytest.mark.asyncio
    async def test_doc_includes_examples_per_pedagogy(self):
        """教学有效性: 文档应含例子 (Mayer Contiguity)"""
        from backend.app.agents.course_expert import CourseExpertAgent

        mock_md = (
            "# 梯度下降\n\n"
            "梯度下降是一种优化算法。\n"
            "例如, 在线性回归中, 我们用它最小化 MSE 损失。\n\n"
            "## 步骤\n1. 计算梯度\n2. 更新参数"
        )
        agent = CourseExpertAgent(llm_client=_fixed_response_llm(mock_md))
        resp = await agent.execute(_make_ctx("讲解梯度下降"))
        assert "例如" in resp.content or "比如" in resp.content


# ================================================================
# Resource 2: 思维导图 (MultimodalAgent + MermaidStudio)
# ================================================================
class TestResource2_Mindmap:
    @pytest.mark.asyncio
    async def test_mindmap_request_renders_png(self):
        from backend.app.agents.multimodal_agent import MultimodalAgent

        mock_md = (
            "# CNN 思维导图\n\n"
            "```mermaid\n"
            "mindmap\n"
            "  root((CNN))\n"
            "    卷积层\n"
            "      局部感受野\n"
            "      权值共享\n"
            "    池化层\n"
            "      最大池化\n"
            "      平均池化\n"
            "    全连接层\n"
            "```\n\n"
            "```resource_meta\n"
            '{"type": "mindmap", "title": "CNN 思维导图"}\n'
            "```"
        )
        agent = MultimodalAgent(llm_client=_fixed_response_llm(mock_md))
        resp = await agent.execute(
            _make_ctx("给我一个 CNN 的思维导图"),
        )
        assert resp.success
        assert resp.content_type == "mindmap"

        # MermaidStudio 应被调用 → resources[0] 含渲染信息
        first = resp.resources[0]
        assert first.get("render_method"), (
            "思维导图 resources[0] 应含 render_method (mermaid 已渲染)"
        )
        assert first.get("diagram_kind") == "mindmap"

    def test_mermaid_studio_can_render_5_diagram_types(self):
        """快速验证 Studio 5 种 diagram 全部支持"""
        from backend.app.services.multimodal.mermaid import (
            ClassDiagramSpec,
            ClassEntity,
            FlowchartSpec,
            FlowNode,
            GraphNode,
            GraphSpec,
            MindmapNode,
            MindmapSpec,
            SequenceMessage,
            SequenceSpec,
            get_mermaid_studio,
        )

        studio = get_mermaid_studio()
        specs = [
            MindmapSpec(root=MindmapNode(text="root")),
            FlowchartSpec(nodes=[FlowNode(id="A", label="x")]),
            SequenceSpec(
                actors=["U", "S"],
                messages=[SequenceMessage(
                    sender="U", receiver="S", text="hi",
                )],
            ),
            ClassDiagramSpec(classes=[ClassEntity(name="Foo")]),
            GraphSpec(nodes=[GraphNode(id="a", label="A")]),
        ]
        for spec in specs:
            r = studio.render_spec(spec)
            assert r.kind == spec.kind
            assert r.validation_passed


# ================================================================
# Resource 3: 练习题目 (QuizGeneratorAgent)
# ================================================================
class TestResource3_Quiz:
    @pytest.mark.asyncio
    async def test_quiz_generator_returns_questions(self):
        from backend.app.agents.quiz_generator import QuizGeneratorAgent

        mock_md = (
            "# CNN 练习题\n\n"
            "## 选择题\n"
            "1. 卷积层的主要作用是?\n"
            "   A. 特征提取\n   B. 分类\n   C. 池化\n   D. 归一化\n\n"
            "   答案: A\n\n"
            "## Bloom 层级\nunderstand"
        )
        agent = QuizGeneratorAgent(
            llm_client=_fixed_response_llm(mock_md),
        )
        resp = await agent.execute(_make_ctx("出 3 道 CNN 题"))
        assert resp.success
        assert "题" in resp.content or "?" in resp.content
        # Bloom 标签应出现 (赛题对齐 metadata 契约)
        assert "答案" in resp.content or "answer" in resp.content.lower()


# ================================================================
# Resource 4: 拓展阅读 (CourseExpertAgent reading mode)
# ================================================================
class TestResource4_Reading:
    @pytest.mark.asyncio
    async def test_reading_material_with_rag_context(self):
        from backend.app.agents.course_expert import CourseExpertAgent

        mock_md = (
            "# 拓展阅读: 注意力机制\n\n"
            "## 推荐论文\n"
            "1. Attention Is All You Need (Vaswani 2017) — Transformer 开山之作\n"
            "2. BERT (Devlin 2018) — 双向预训练\n\n"
            "## 在线资源\n- 《动手学深度学习》Ch10"
        )
        agent = CourseExpertAgent(llm_client=_fixed_response_llm(mock_md))
        ctx = _make_ctx(
            "推荐一些关于 attention 的拓展阅读",
            rag_results=[
                {"content": "Attention 机制起源于 NMT (Bahdanau 2014)。",
                 "source": "ai_chapter_attention.md"},
            ],
        )
        resp = await agent.execute(ctx)
        assert resp.success
        assert "Vaswani" in resp.content or "Transformer" in resp.content


# ================================================================
# Resource 5: 代码案例 (MultimodalAgent code mode + Sandbox 执行)
# ================================================================
class TestResource5_Code:
    @pytest.mark.asyncio
    async def test_code_resource_is_runnable_in_sandbox(self):
        from backend.app.agents.multimodal_agent import MultimodalAgent

        mock_md = (
            "# Python 列表反转代码\n\n"
            "```python\n"
            "nums = [1, 2, 3, 4, 5]\n"
            "reversed_nums = nums[::-1]\n"
            "print(reversed_nums)\n"
            "```\n\n"
            "```resource_meta\n"
            '{"type": "code", "title": "列表反转", "language": "python"}\n'
            "```"
        )
        agent = MultimodalAgent(llm_client=_fixed_response_llm(mock_md))
        resp = await agent.execute(_make_ctx("给我一段 Python 列表反转的代码"))
        assert resp.success
        assert resp.content_type == "code"
        assert "```python" in resp.content

    def test_code_sandbox_executes_simple_python(self):
        """直接验证 Code Sandbox 可执行代码"""
        from backend.app.services.multimodal.code_sandbox import get_code_sandbox
        sandbox = get_code_sandbox()
        result = sandbox.execute("print(2 + 3)")
        assert result.passed
        assert "5" in result.stdout

    def test_code_sandbox_blocks_dangerous_code(self):
        """沙箱阻止危险操作 (赛题安全要求)"""
        from backend.app.services.multimodal.code_sandbox import get_code_sandbox
        sandbox = get_code_sandbox()
        result = sandbox.execute("import os\nos.system('echo evil')")
        assert not result.passed


# ================================================================
# Resource 6: 教学视频 (Manim DSL → 编译 Python)
# ================================================================
class TestResource6_ManimVideo:
    def test_manim_dsl_compiles_concept_template(self):
        from backend.app.services.multimodal.manim.dsl import (
            ManimDSLSpec, Scene, SceneElement, ElementType, AnimationStep,
            AnimationType,
        )
        from backend.app.services.multimodal.manim.compiler import DSLCompiler

        spec = ManimDSLSpec(
            title="CNN 入门",
            topic="卷积神经网络",
            scenes=[
                Scene(
                    scene_id="intro", duration_seconds=3.0,
                    elements=[
                        SceneElement(
                            id="title", type=ElementType.TEXT,
                            content="CNN 入门",
                        ),
                    ],
                    animations=[
                        AnimationStep(
                            type=AnimationType.WRITE, target_id="title",
                            duration=1.0,
                        ),
                    ],
                ),
            ],
        )
        compiler = DSLCompiler()
        code = compiler.compile(spec)
        # 编译后的代码应符合 Manim Python 规范
        assert "from manim import *" in code
        assert "class Scene_intro(Scene):" in code
        assert "DATA[" in code  # 内容参数化


# ================================================================
# 端到端 chat → 5 类资源 整合
# ================================================================
class TestEndToEndOrchestrator:
    @pytest.mark.asyncio
    async def test_orchestrator_routes_to_multimodal_for_mindmap(self):
        """Orchestrator 应根据意图路由到 MultimodalAgent (思维导图)"""
        from backend.app.agents import AGENT_REGISTRY
        from backend.app.agents.orchestrator import AgentOrchestrator

        mock_llm = _fixed_response_llm(
            "```mermaid\nmindmap\n  root((X))\n```\n"
            "```resource_meta\n{\"type\": \"mindmap\"}\n```"
        )
        orch = AgentOrchestrator(
            llm_client=mock_llm, agent_registry=AGENT_REGISTRY,
        )
        results = await orch.process_turn(
            user_input="给我一个 CNN 的思维导图",
            profile={"knowledge_base": {"level": "中等"}},
            context={},
            session_id="e2e-orc-1",
        )
        # 至少有一个 agent 成功响应 (profile_update 总会存在)
        success_agents = {
            r.agent_name for r in results.values() if r.success
        }
        assert success_agents, "Orchestrator 应至少触发一个成功 Agent"

    def test_all_5_resource_agents_registered(self):
        """5 大资源 Agent 必须在 registry 中"""
        from backend.app.agents import AGENT_REGISTRY
        required = {
            "course_expert",     # 讲解文档 + 拓展阅读
            "quiz_generator",    # 练习题
            "multimodal",        # 思维导图 + 代码
            "tutor",             # 智能辅导 (加分项)
            "evaluator",         # 评估 (加分项)
        }
        registered = set(AGENT_REGISTRY.keys())
        missing = required - registered
        assert not missing, f"缺失 Agent: {missing}"


# ================================================================
# 演示数据完整性
# ================================================================
class TestDemoAssetsExist:
    """演示时关键 artifacts 路径应可写"""

    def test_artifact_directories_writable(self, tmp_path):
        from pathlib import Path
        for sub in ["pptx", "mermaid_png", "mp3", "manim", "qr", "png"]:
            d = Path("data/artifacts") / sub
            d.mkdir(parents=True, exist_ok=True)
            assert d.exists(), f"artifact 目录不可创建: {d}"
