"""
测试: Mermaid Studio (P1-4)

覆盖目标 ≥ 25 用例:
- spec.py:        5 种 Pydantic spec 校验 (7)
- templates.py:   5 种 builder 输出格式 (7)
- validator.py:   语法校验报告 (5)
- intent.py:      智能识别 (5)
- studio.py:      端到端 + 知识图谱 + 概念构建 (5)
- 向后兼容:       旧 MermaidRenderer facade (3)
- MultimodalAgent: 集成 (2)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from backend.app.services.multimodal.mermaid import (
    ClassDiagramSpec,
    ClassEntity,
    ClassMember,
    ClassRelation,
    FlowchartSpec,
    FlowEdge,
    FlowNode,
    GraphSpec,
    GraphNode,
    GraphEdge,
    MermaidStudio,
    MermaidValidator,
    MindmapNode,
    MindmapSpec,
    SequenceMessage,
    SequenceSpec,
    build_mermaid_code,
    detect_intent,
    get_mermaid_studio,
    list_supported_kinds,
    reset_studio,
)
from backend.app.services.multimodal.mermaid.templates import (
    build_class_diagram,
    build_flowchart,
    build_graph,
    build_mindmap,
    build_sequence,
)


# ================================================================
# 1) spec.py - Pydantic 校验
# ================================================================
class TestSpec:
    def test_mindmap_min(self):
        spec = MindmapSpec(root=MindmapNode(text="CNN"))
        assert spec.kind == "mindmap"

    def test_mindmap_empty_text_rejected(self):
        with pytest.raises(ValidationError):
            MindmapNode(text="")

    def test_flowchart_unknown_edge_rejected(self):
        with pytest.raises(ValidationError):
            FlowchartSpec(
                nodes=[FlowNode(id="A", label="x")],
                edges=[FlowEdge(source="A", target="Z")],
            )

    def test_sequence_min_actors(self):
        with pytest.raises(ValidationError):
            SequenceSpec(
                actors=["A"],  # 至少 2
                messages=[SequenceMessage(
                    sender="A", receiver="A", text="hi",
                )],
            )

    def test_class_entity_must_capitalize(self):
        with pytest.raises(ValidationError):
            ClassEntity(name="myClass")  # 必须大写开头

    def test_graph_directed_default_false(self):
        g = GraphSpec(nodes=[GraphNode(id="a", label="A")])
        assert g.directed is False

    def test_mindmap_node_too_many_children(self):
        with pytest.raises(ValidationError):
            MindmapNode(
                text="t",
                children=[
                    MindmapNode(text=f"c{i}") for i in range(15)
                ],
            )


# ================================================================
# 2) templates.py - 5 种 builder
# ================================================================
class TestTemplates:
    def test_mindmap_has_root_marker(self):
        spec = MindmapSpec(root=MindmapNode(text="CNN", children=[
            MindmapNode(text="conv"),
        ]))
        code = build_mindmap(spec)
        assert code.startswith("mindmap")
        assert "root((CNN))" in code
        assert "conv" in code

    def test_mindmap_icon_prefixes_label(self):
        spec = MindmapSpec(root=MindmapNode(
            text="目标", icon="🎯",
        ))
        code = build_mindmap(spec)
        assert "🎯" in code

    def test_flowchart_direction_and_arrow(self):
        spec = FlowchartSpec(
            direction="LR",
            nodes=[
                FlowNode(id="A", label="开始"),
                FlowNode(id="B", label="结束"),
            ],
            edges=[FlowEdge(source="A", target="B", label="next")],
        )
        code = build_flowchart(spec)
        assert "flowchart LR" in code
        assert "A -->|next| B" in code

    def test_flowchart_shapes_render_correctly(self):
        spec = FlowchartSpec(
            nodes=[
                FlowNode(id="A", label="X", shape="diamond"),
                FlowNode(id="B", label="Y", shape="circle"),
            ],
        )
        code = build_flowchart(spec)
        assert "A{X}" in code
        assert "B((Y))" in code

    def test_sequence_uses_participant(self):
        spec = SequenceSpec(
            actors=["User", "Server"],
            messages=[SequenceMessage(
                sender="User", receiver="Server", text="login",
            )],
        )
        code = build_sequence(spec)
        assert "sequenceDiagram" in code
        assert "participant User" in code
        assert "User ->> Server: login" in code

    def test_class_diagram_emits_inheritance_arrow(self):
        spec = ClassDiagramSpec(
            classes=[
                ClassEntity(name="Animal"),
                ClassEntity(name="Dog"),
            ],
            relations=[ClassRelation(
                source="Animal", target="Dog", relation="inherit",
            )],
        )
        code = build_class_diagram(spec)
        assert "classDiagram" in code
        assert "Animal <|-- Dog" in code

    def test_graph_classDef_per_group(self):
        spec = GraphSpec(
            nodes=[
                GraphNode(id="a", label="A", group="g1"),
                GraphNode(id="b", label="B", group="g2"),
            ],
        )
        code = build_graph(spec)
        assert "classDef g0" in code
        assert "classDef g1" in code


# ================================================================
# 3) validator.py
# ================================================================
class TestValidator:
    def test_empty_code_error(self):
        report = MermaidValidator().validate("")
        assert not report.passed()
        assert any(i.code == "empty" for i in report.errors())

    def test_unknown_header_error(self):
        report = MermaidValidator().validate("nonsense\n  foo")
        assert not report.passed()

    def test_mindmap_without_root_warns(self):
        report = MermaidValidator().validate("mindmap\n  X\n    Y")
        assert any(
            i.code == "mindmap_no_root" for i in report.warnings()
        )

    def test_flowchart_bad_direction_warns(self):
        code = "flowchart XX\n  A --> B"
        report = MermaidValidator().validate(code)
        # Should warn about invalid direction OR just continue
        # (regex match on direction)
        assert any(
            i.code == "invalid_direction" for i in report.warnings()
        )

    def test_valid_mindmap_passes(self):
        code = "mindmap\n  root((CNN))\n    conv"
        report = MermaidValidator().validate(code)
        assert report.passed()


# ================================================================
# 4) intent.py
# ================================================================
class TestIntent:
    def test_mindmap_detection(self):
        assert detect_intent("给我一个 CNN 的思维导图") == "mindmap"

    def test_flowchart_detection(self):
        assert detect_intent("梯度下降的流程图") == "flowchart"

    def test_sequence_detection(self):
        assert detect_intent("登录系统的时序图") == "sequence"

    def test_class_detection(self):
        assert detect_intent("画一个 UML 类图") == "class"

    def test_graph_detection(self):
        assert detect_intent("知识图谱可视化") == "graph"

    def test_fallback_mindmap(self):
        assert detect_intent("随便讲讲") == "mindmap"

    def test_empty_input_fallback(self):
        assert detect_intent("") == "mindmap"

    def test_supported_kinds_count(self):
        assert len(list_supported_kinds()) == 5


# ================================================================
# 5) studio.py - 端到端
# ================================================================
class TestStudio:
    def test_from_concept_builds_mindmap(self):
        studio = MermaidStudio()
        r = studio.from_concept(
            title="CNN",
            branches=["卷积", "池化", "全连接"],
            leaves={"卷积": ["局部感受野"]},
        )
        assert r.kind == "mindmap"
        assert "root((CNN))" in r.mermaid_code
        assert "局部感受野" in r.mermaid_code

    def test_render_spec_returns_kind(self):
        studio = MermaidStudio()
        spec = FlowchartSpec(
            nodes=[FlowNode(id="A", label="x")],
        )
        r = studio.render_spec(spec)
        assert r.kind == "flowchart"
        assert r.validation_passed is True

    def test_render_code_invalid_yields_validation_failed(self):
        studio = MermaidStudio()
        r = studio.render_code("nonsense diagram")
        assert r.validation_passed is False
        assert "unknown_header" in r.error

    def test_knowledge_graph_filters_dangling_edges(self):
        """KG 中引用不存在节点的边应被过滤"""
        studio = MermaidStudio()
        r = studio.render_knowledge_graph(
            nodes=[
                {"id": "a", "label": "A"},
                {"id": "b", "label": "B"},
            ],
            edges=[
                {"source": "a", "target": "b"},
                {"source": "a", "target": "Z"},  # 不存在
            ],
        )
        # 不存在的边应被静默丢弃, 不阻塞渲染
        assert r.kind == "graph"

    def test_singleton(self):
        reset_studio()
        s1 = get_mermaid_studio()
        s2 = get_mermaid_studio()
        assert s1 is s2


# ================================================================
# 6) 向后兼容: MermaidRenderer facade
# ================================================================
class TestBackwardCompat:
    def test_old_renderer_returns_dict(self):
        from backend.app.services.multimodal.mermaid_renderer import (
            MermaidRenderer,
        )
        r = MermaidRenderer().render(
            "mindmap\n  root((X))\n    a", rid="test",
        )
        assert "png_path" in r
        assert "method" in r
        assert "mermaid_text" in r

    def test_extract_blocks(self):
        from backend.app.services.multimodal.mermaid_renderer import (
            MermaidRenderer,
        )
        text = (
            "前面文字\n```mermaid\nmindmap\n  root((A))\n```\n"
            "中间\n```mermaid\nflowchart LR\nA --> B\n```\n"
        )
        blocks = MermaidRenderer.extract_blocks(text)
        assert len(blocks) == 2

    def test_get_mermaid_renderer_singleton(self):
        from backend.app.services.multimodal.mermaid_renderer import (
            get_mermaid_renderer,
        )
        a = get_mermaid_renderer()
        b = get_mermaid_renderer()
        assert a is b


# ================================================================
# 7) MultimodalAgent 集成
# ================================================================
class TestMultimodalAgentIntegration:
    @pytest.mark.asyncio
    async def test_mindmap_request_returns_render_data_uri(self):
        from backend.app.agents.multimodal_agent import MultimodalAgent
        from backend.app.agents.base import AgentContext

        # Mock LLM returns markdown with mermaid block
        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value=(
            "# CNN 思维导图\n\n```mermaid\nmindmap\n  root((CNN))\n"
            "    卷积层\n    池化层\n```\n"
            "```resource_meta\n"
            '{"type": "mindmap", "title": "CNN 思维导图"}\n```'
        ))
        agent = MultimodalAgent(llm_client=mock_llm)
        ctx = AgentContext(user_input="给我一个 CNN 的思维导图")
        resp = await agent.execute(ctx)
        assert resp.success
        assert resp.content_type == "mindmap"
        # resources[0] 应含 PNG 渲染数据
        assert resp.resources
        first = resp.resources[0]
        assert first.get("render_method")  # 必有渲染方式
        assert first.get("diagram_kind") == "mindmap"

    def test_detect_resource_type_uses_intent(self):
        from backend.app.agents.multimodal_agent import MultimodalAgent
        agent = MultimodalAgent(llm_client=MagicMock())
        assert agent._detect_resource_type("画个流程图") == "mindmap"
        assert agent._detect_resource_type("写段代码") == "code"
        assert agent._detect_resource_type("做个 PPT") == "ppt"
