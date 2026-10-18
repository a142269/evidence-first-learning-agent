"""群聊协作资源的用户可读性与媒体路由回归测试。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.agents import AGENT_REGISTRY
from backend.app.agents.base import AgentContext
from backend.app.agents.evaluator_agent import EvaluatorAgent
from backend.app.agents.orchestrator import AgentOrchestrator
from backend.app.agents.quiz_generator import QuizGeneratorAgent
from backend.app.agents.resource_generator_agent import (
    ResourceGeneratorAgent,
    _extract_topic,
    _extract_pptx_template,
    _requested_resource_types,
    _user_readable_failure,
)
from backend.app.api.v1.artifacts import multi as multi_mod
from backend.app.api.v1.artifacts.multi import MultiResourceRequest
from backend.app.api.v1.chat import _bind_session_user
from backend.app.services.multimodal.mermaid.spec import MindmapNode, MindmapSpec
from backend.app.services.multimodal.mermaid.templates import build_mindmap
from backend.app.services.multimodal.mermaid.validator import MermaidValidator


def test_long_collaboration_description_is_compacted_before_validation():
    request = MultiResourceRequest(
        topic="Transformer",
        description=("五位智能体协作生成高级学习资料。" * 80) + "结尾必须保留用户约束。",
        types=["mermaid"],
    )

    assert len(request.description) <= 400
    assert "…" in request.description
    assert request.description.endswith("结尾必须保留用户约束。")


def test_video_quality_gate_rejects_visible_audio_tail(monkeypatch):
    durations = iter([12.0, 14.0])
    monkeypatch.setattr(
        multi_mod, "_probe_media_duration_seconds", lambda _path: next(durations),
    )

    result = multi_mod._video_quality_gate("lesson.mp4", "lesson.mp3")

    assert result["status"] == "rejected"
    assert result["av_duration_drift_seconds"] == 2.0
    assert "画面与旁白" in result["reason"]


@pytest.mark.asyncio
async def test_quiz_is_completed_to_requested_count_without_exposing_protocol():
    agent = QuizGeneratorAgent()
    single_question = [{
        "id": 1,
        "type": "choice",
        "difficulty": "easy",
        "bloom": "remember",
        "question": "Self-Attention 中 Q 的主要作用是什么？",
        "options": ["A. 发起匹配", "B. 保存标签", "C. 编码位置", "D. 归一化"],
        "answer": "A",
        "explanation": "Q 表示当前位置用于检索相关信息的查询向量。",
    }]
    agent._acall_llm = AsyncMock(
        return_value=f"```quiz_json\n{json.dumps(single_question, ensure_ascii=False)}\n```"
    )
    context = AgentContext(
        user_input="设计 12 道由易到难的分层练习，覆盖概念、推导与代码 Debug。",
        course_name="artificial_intelligence",
        extra={"collaboration_request": "围绕「Transformer 架构」开展五位智能体协作。"},
    )

    response = await agent.execute(context)
    questions = response.metadata["quiz_data"]

    assert response.success is True
    assert len(questions) == 12
    assert [item["id"] for item in questions] == list(range(1, 13))
    assert "Transformer 架构" in response.resources[0]["title"]
    for leaked in ("quiz_json", "人类可读的完整题目", "练习题：设计", "命题约束", "{\""):
        assert leaked not in response.content


def test_mindmap_translates_mermaid_control_characters_in_labels():
    spec = MindmapSpec(root=MindmapNode(
        text="Transformer 架构",
        children=[MindmapNode(
            text="Q/K/V (shape: [B,H,N,D])",
            children=[
                MindmapNode(text="缩放点积 {Softmax(QKᵀ/√dₖ)}"),
                MindmapNode(text="Masking (Padding Mask & Look-ahead Mask)"),
            ],
        )],
    ))

    code = build_mindmap(spec)
    report = MermaidValidator().validate(code)

    assert report.passed()
    assert "Q/K/V （shape： 【B,H,N,D】）" in code
    assert "缩放点积 〔Softmax（QKᵀ/√dₖ）〕" in code
    assert "Masking （Padding Mask ＆ Look-ahead Mask）" in code
    assert code.count("(") == code.count(")") == 2


def test_mermaid_renderer_does_not_reuse_unverified_legacy_error_png(tmp_path, monkeypatch):
    from backend.app.services.multimodal.mermaid import renderer as renderer_mod

    monkeypatch.setattr(renderer_mod, "PNG_DIR", tmp_path)
    renderer = renderer_mod.MermaidRenderer()
    code = "mindmap\n  root((Transformer))\n    Self-Attention"
    out_path = tmp_path / f"{renderer_mod._hash(code)}.png"
    out_path.write_bytes(b"legacy mermaid parse error screenshot")

    def successful_render(_code, target):
        target.write_bytes(b"fresh verified png")
        return renderer_mod.RenderResult(png_path=str(target), method="mmdc")

    monkeypatch.setattr(renderer, "_try_mmdc", successful_render)
    first = renderer.render(code)
    second = renderer.render(code)

    assert first.method == "mmdc"
    assert out_path.read_bytes() == b"fresh verified png"
    assert out_path.with_suffix(".verified").exists()
    assert second.method == "cache"


def test_media_content_client_forces_xunfei_spark(monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace
    from backend.app.core import config as config_module
    from backend.app.core.llm_client import create_xunfei_spark_client

    monkeypatch.delenv("A3_OFFLINE_DEMO", raising=False)
    fake = replace(config_module.get_config().llm, spark_app_id="test-app", spark_api_key="test-key", spark_api_secret="test-secret")
    monkeypatch.setattr(config_module, "get_config", lambda: SimpleNamespace(llm=fake))
    client = create_xunfei_spark_client()

    assert client.config.provider == "spark"


def test_ppt_uses_kimi_and_video_copy_stays_on_xunfei(monkeypatch):
    class FakeXunfeiClient:
        def chat(self, messages, **_kwargs):
            system = str(messages[0].get("content", ""))
            if "事实边界审校员" in system:
                return json.dumps({
                    "audience": "高校学习者",
                    "communication_job": "建立可验证理解",
                    "central_takeaway": "理解并应用 Transformer",
                    "narrative_arc": "问题→机制→案例→迁移",
                    "slides": [
                        {
                            "title": f"结论式标题{i}",
                            "narrative_job": "推进理解",
                            "key_message": "核心结论",
                            "evidence": ["证据一", "证据二"],
                            "visual_intent": "单一主视觉",
                            "layout_hint": "worked_example" if i == 3 else "concept",
                        }
                        for i in range(1, 9)
                    ],
                }, ensure_ascii=False)
            if "PPT" in system:
                return json.dumps({
                    "slides": [
                        {"title": f"第{i}页", "bullets": ["具体要点一", "具体要点二", "具体要点三"]}
                        for i in range(1, 6)
                    ],
                    "summary": ["核心总结"],
                    "review": ["复习问题"],
                }, ensure_ascii=False)
            return "。".join(["这是由科大讯飞星火生成的个性化视频讲稿"] * 12)

    monkeypatch.setattr(multi_mod, "_deepseek_ppt_outline_client", lambda: FakeXunfeiClient())
    monkeypatch.setattr(multi_mod, "_kimi_ppt_content_client", lambda: FakeXunfeiClient())
    monkeypatch.setattr(multi_mod, "_xunfei_media_content_client", lambda: FakeXunfeiClient())

    ppt = multi_mod._llm_pptx_content("Transformer")
    lecture, source = multi_mod._build_video_lecture_text(
        MultiResourceRequest(topic="Transformer", types=["manim"]),
    )

    assert ppt["content_source"] == "kimi"
    # 2026-07-15：Kimi 单次调用同时负责叙事大纲与逐页内容，本地蓝图仅兜底。
    assert ppt["outline_source"] == "kimi"
    assert source == "xunfei_spark"
    assert len(lecture) >= 120


def test_audio_and_video_are_mounted_on_the_resource_agent():
    assert AGENT_REGISTRY["audio"] is ResourceGeneratorAgent
    assert AGENT_REGISTRY["generate_audio"] is ResourceGeneratorAgent
    assert AGENT_REGISTRY["video"] is ResourceGeneratorAgent
    assert AGENT_REGISTRY["generate_video"] is ResourceGeneratorAgent


def test_internal_validation_error_is_rewritten_for_students():
    raw = "ValidationError: String should have at most 400 characters [type=string_too_long]"

    readable = _user_readable_failure(raw)

    assert "ValidationError" not in readable
    assert "string_too_long" not in readable
    assert "单独重试" in readable


def test_ppt_request_stays_single_type_and_ignores_incidental_demo_wording():
    assert _requested_resource_types("我需要一份用于演示的 Transformer PPT") == ["pptx"]
    assert _requested_resource_types("只需要 PPT，其他资源不要生成") == ["pptx"]
    assert _requested_resource_types("PPT 和视频都需要") == ["pptx", "manim"]
    assert _requested_resource_types("生成 PPT 和视频", action="generate_ppt") == ["pptx"]
    # @阿匠 历史上会被编排成 generate_doc；文本中的明确资源类型必须覆盖
    # 这个通用动作，不能扩大成文档或整套资源。
    assert _requested_resource_types("我只想要二分查找的 PPT", action="generate_doc") == ["pptx"]


def test_ppt_topic_extraction_removes_request_wrapper_and_resource_suffix():
    assert _extract_topic("我想要二分查找的ppt") == "二分查找"
    assert _extract_topic("我想学习二分查找的 PPT") == "二分查找"
    assert _extract_topic("@阿匠 请帮我生成一份 Transformer 架构的PPT") == "Transformer 架构"


def test_ppt_generation_defensively_normalizes_resource_suffix():
    assert multi_mod._normalize_pptx_topic("梯度下降的PPT") == "梯度下降"
    assert multi_mod._normalize_pptx_topic("Transformer 课件") == "Transformer"


def test_ppt_blueprint_string_evidence_is_not_split_into_single_characters():
    blueprint = {
        "slides": [
            {
                "title": "学习率",
                "key_message": "学习率决定每次更新步长",
                "evidence": "泰勒展开",
                "layout_hint": "concept",
            }
        ]
    }
    slides = multi_mod._slides_from_blueprint(blueprint, "梯度下降")
    assert slides[0]["bullets"] == ["学习率决定每次更新步长", "泰勒展开"]
    assert multi_mod._pptx_text_items(["泰", "勒", "展", "开"]) == ["泰勒展开"]


def test_ppt_theme_selection_is_stable_but_not_always_academic():
    assert multi_mod._select_pptx_theme("梯度下降", {"variant": "advanced_project"}, True) == "high_contrast"
    assert multi_mod._select_pptx_theme("概率统计", {"variant": "advanced_project"}, True) == "academic"
    assert multi_mod._select_pptx_theme("概率统计", {"variant": "foundation_guided"}, True) == "modern"


def test_kimi_ppt_quality_gate_rejects_empty_code_page():
    blueprint = [
        {"title": f"第{i}页", "layout_hint": "code" if i == 5 else "concept"}
        for i in range(1, 6)
    ]
    raw = [
        {
            "title": f"第{i}页",
            "bullets": ["具体结论一", "具体结论二", "具体结论三"],
            "code_block": "" if i == 5 else "",
        }
        for i in range(1, 6)
    ]

    with pytest.raises(ValueError, match="代码页"):
        multi_mod._validate_kimi_pptx_slides(raw, blueprint, "梯度下降")


def test_ppt_provider_trace_reports_fallback_reason():
    trace = multi_mod._pptx_provider_trace({
        "content_source": "template_fallback",
        "outline_source": "deepseek",
        "provider_errors": {"kimi": "RuntimeError: rate limited"},
    })

    assert trace["deepseek"]["used"] is True
    assert trace["kimi"]["used"] is False
    assert trace["fallback"] is True
    assert "rate limited" in trace["errors"]["kimi"]


def test_ppt_template_name_is_extracted_without_accepting_paths():
    assert _extract_pptx_template("只生成 PPT，使用 tech-blue 模板") == "tech-blue"
    assert _extract_pptx_template("模板名：academic_v2") == "academic_v2"
    assert _extract_pptx_template("模板：F:\\secret\\deck.pptx") == ""


@pytest.mark.asyncio
async def test_ajiang_ppt_mention_routes_to_ppt_action_only():
    orchestrator = AgentOrchestrator(llm_client=MagicMock(), agent_registry={})

    intents = await orchestrator._classify_intent(
        "@阿匠 我想要一份二分查找的 PPT，其他资源不要生成",
        {},
    )

    assert "generate_ppt" in intents
    assert "generate_doc" not in intents
    assert "generate_video" not in intents


def test_demo_profiles_produce_distinct_resource_strategies():
    # Keep this regression independent of the developer's mutable local DB.
    data_dir = Path(__file__).resolve().parents[2] / "data"
    seed = json.loads((data_dir / "seed.json").read_text(encoding="utf-8"))
    extended = json.loads((data_dir / "seed_extended.json").read_text(encoding="utf-8"))
    du = next(row["profile"] for row in seed["students"]
              if row["user_id"] == "demo-student-1")
    lin = next(row["profile"] for row in extended["extra_students"]
               if row["user_id"] == "demo-student-21")

    du_plan = multi_mod._personalization_plan(du)
    lin_plan = multi_mod._personalization_plan(lin)
    du_hint = multi_mod._profile_hint_str(du)
    lin_hint = multi_mod._profile_hint_str(lin)

    assert du_plan["variant"] == "advanced_project"
    assert lin_plan["variant"] == "foundation_guided"
    assert du_plan["theme_name"] != lin_plan["theme_name"]
    assert du_hint != lin_hint
    assert "进阶实战版" in du_hint
    assert "基础引导版" in lin_hint


def test_personalization_focus_stays_inside_requested_topic():
    focus = multi_mod._topic_personalized_focus(
        "二分查找",
        {"focus": "probability_statistics、reinforcement_learning"},
    )
    assert "二分查找" in focus
    assert "probability_statistics" not in focus
    assert "reinforcement_learning" not in focus


def test_ppt_profile_hint_removes_unrelated_weaknesses():
    hint, plan = multi_mod._scope_pptx_personalization(
        "梯度下降",
        "版本:进阶实战版；重点补强:probability_statistics、reinforcement_learning；节奏:较快",
        {"focus": "probability_statistics、reinforcement_learning"},
    )

    assert "probability_statistics" not in hint
    assert "reinforcement_learning" not in hint
    assert "梯度下降" in hint
    assert "梯度下降" in plan["focus"]


def test_pptx_blueprint_limits_code_pages_and_preserves_visual_variety():
    slides = [
        {"title": f"页{i}", "layout_hint": "code"}
        for i in range(1, 8)
    ]
    slides[1]["title"] = "方案对比"
    balanced = multi_mod._balance_pptx_blueprint_layouts(slides)
    layouts = [item["layout_hint"] for item in balanced]
    assert layouts.count("code") <= 2
    assert layouts.count("comparison") >= 1
    assert layouts.count("concept") >= 2
    assert layouts.count("worked_example") >= 2


@pytest.mark.asyncio
async def test_resource_agent_does_not_surface_unrequested_failures(monkeypatch):
    handler = AsyncMock(return_value={
        "success": True,
        "results": {
            "pptx": {
                "success": True,
                "filepath": "data/artifacts/pptx/demo.pptx",
                "metadata": {"title": "Transformer · 个性化课件"},
            },
            "manim": {"success": False, "error": "ffmpeg failed"},
        },
    })
    registry = MagicMock()
    registry.list_a_tools.return_value = [SimpleNamespace(
        schema=SimpleNamespace(name="generate_learning_materials"),
        handler=handler,
    )]
    monkeypatch.setattr(
        "backend.app.agents.resource_generator_agent.get_tool_registry",
        lambda: registry,
    )

    response = await ResourceGeneratorAgent().execute(AgentContext(
        user_input="我需要一份 Transformer PPT",
        session_id="single-ppt",
    ))

    assert [resource["type"] for resource in response.resources] == ["pptx"]
    assert "视频" not in response.content
    assert "失败" not in response.content


@pytest.mark.asyncio
async def test_resource_agent_never_presents_manim_script_as_video(monkeypatch):
    handler = AsyncMock(return_value={
        "success": True,
        "results": {
            "manim": {
                "success": True,
                "content": "from manim import Scene",
                "filepath": "",
                "downloads": [{
                    "id": "manim_script_only",
                    "type": "manim_code",
                    "filename": "lesson.py",
                    "exists": False,
                }],
                "metadata": {
                    "title": "Transformer 动画脚本",
                    "video_status": "script_only",
                    "playback_status": "unavailable",
                },
            },
        },
    })
    registry = MagicMock()
    registry.list_a_tools.return_value = [SimpleNamespace(
        schema=SimpleNamespace(name="generate_learning_materials"),
        handler=handler,
    )]
    monkeypatch.setattr(
        "backend.app.agents.resource_generator_agent.get_tool_registry",
        lambda: registry,
    )

    response = await ResourceGeneratorAgent().execute(AgentContext(
        user_input="生成 Transformer 教学视频",
        session_id="strict-video",
    ))

    assert response.resources == []
    assert "准备了讲解视频" not in response.content


@pytest.mark.asyncio
async def test_resource_agent_accepts_real_mp4_video(monkeypatch):
    handler = AsyncMock(return_value={
        "success": True,
        "results": {
            "manim": {
                "success": True,
                "filepath": "data/artifacts/video/transformer.mp4",
                "downloads": [{
                    "id": "vid_transformer",
                    "type": "video",
                    "filename": "transformer.mp4",
                    "exists": True,
                }],
                "metadata": {
                    "title": "Transformer 视频讲解",
                    "video_status": "ready",
                    "playback_status": "ready",
                },
            },
        },
    })
    registry = MagicMock()
    registry.list_a_tools.return_value = [SimpleNamespace(
        schema=SimpleNamespace(name="generate_learning_materials"),
        handler=handler,
    )]
    monkeypatch.setattr(
        "backend.app.agents.resource_generator_agent.get_tool_registry",
        lambda: registry,
    )

    response = await ResourceGeneratorAgent().execute(AgentContext(
        user_input="生成 Transformer 教学视频",
        session_id="playable-video",
    ))

    assert [resource["type"] for resource in response.resources] == ["manim"]
    assert response.resources[0]["filepath"].endswith(".mp4")


@pytest.mark.asyncio
async def test_resource_agent_forwards_student_identity_and_inline_content(monkeypatch):
    handler = AsyncMock(return_value={
        "success": True,
        "results": {
            "code": {
                "success": True,
                "content": "print('student-specific')",
                "metadata": {"title": "个性化代码", "code": "print('student-specific')"},
            },
        },
    })
    registry = MagicMock()
    registry.list_a_tools.return_value = [SimpleNamespace(
        schema=SimpleNamespace(name="generate_learning_materials"),
        handler=handler,
    )]
    monkeypatch.setattr(
        "backend.app.agents.resource_generator_agent.get_tool_registry",
        lambda: registry,
    )

    response = await ResourceGeneratorAgent().execute(AgentContext(
        user_input="生成一段 Transformer 代码示例",
        session_id="student-specific-session",
        extra={"user_id": "demo-student-21"},
    ))

    assert handler.await_args.kwargs["user_id"] == "demo-student-21"
    assert response.resources[0]["content"] == "print('student-specific')"


def test_multi_resource_intents_create_one_public_ajiang_task():
    orchestrator = AgentOrchestrator(llm_client=MagicMock(), agent_registry={})

    tasks = orchestrator._plan_tasks(["generate_doc", "generate_mindmap"], {})

    assert len(tasks) == 1
    assert tasks[0].agent_name == "doc_gen"


def test_multi_resource_ajiang_tasks_merge_without_losing_explicit_types():
    orchestrator = AgentOrchestrator(llm_client=MagicMock(), agent_registry={})

    tasks = orchestrator._plan_tasks(
        ["generate_ppt", "generate_video"],
        {},
    )

    assert len(tasks) == 1
    assert tasks[0].agent_name == "doc_gen"
    assert tasks[0].action == "generate_doc"


def test_binding_demo_student_hydrates_and_switches_profile():
    session = {"session_id": "profile-hydration-test", "profile": {}}

    _bind_session_user(session, {"user_id": "demo-student-1"})
    du_score = session["profile"]["knowledge_base"]["score"]
    _bind_session_user(session, {"user_id": "demo-student-21"})
    lin_score = session["profile"]["knowledge_base"]["score"]

    assert session["profile_user_id"] == "demo-student-21"
    assert du_score > lin_score > 0


def test_primary_and_comparison_students_have_distinct_bkt_baselines():
    from backend.app.services.cognitive_diagnosis.bkt import BKT, _seed_demo_bkt

    model = BKT()
    _seed_demo_bkt(model)

    du_masteries = model.get_all_masteries("demo-student-1")
    lin_masteries = model.get_all_masteries("demo-student-21")

    assert len(du_masteries) >= 10
    assert len(lin_masteries) >= 10
    assert sum(du_masteries.values()) / len(du_masteries) > (
        sum(lin_masteries.values()) / len(lin_masteries)
    ) > 0


@pytest.mark.asyncio
async def test_audio_request_is_classified_as_audio_generation():
    orchestrator = AgentOrchestrator(llm_client=MagicMock(), agent_registry={})

    intents = await orchestrator._classify_intent("请生成 Transformer 语音导学", {})

    assert "generate_audio" in intents


@pytest.mark.asyncio
async def test_evaluator_exposes_evidence_aware_svg_descriptions():
    agent = EvaluatorAgent()
    agent._gather_bkt_data = MagicMock(return_value={
        "self_attention": {"p_learned": 0.64, "trend": "up"},
        "multi_head": {"p_learned": 0.41, "trend": "flat"},
    })
    agent._acall_llm = AsyncMock(return_value=(
        "目前计划可执行，但应优先补齐多头注意力的张量变换。\n"
        "```evaluation_result\n"
        '{"overall_score":0.68,"dimensions":{"计划可行性":0.72,"先修掌握":0.55}}\n'
        "```"
    ))
    context = AgentContext(
        user_input="评估三天计划可行性",
        session_id="demo-user",
        profile={"knowledge_base": {"score": 0.62}, "time_management": {"score": 0.75}},
    )

    response = await agent.execute(context)
    metadata = response.resources[0]["metadata"]

    assert response.success is True
    assert metadata["evidence_status"] == "sufficient"
    assert len(metadata["visualizations"]) == 2
    assert all(item["data_uri"].startswith("data:image/svg+xml;base64,") for item in metadata["visualizations"])
    assert all(item["alt"] and item["description"] for item in metadata["visualizations"])
    assert "evaluation_result" not in response.content
