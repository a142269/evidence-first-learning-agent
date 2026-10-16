from collections import Counter


def test_transformer_recommendation_pack_is_multimodal(monkeypatch):
    from backend.app.api.v1 import insights

    monkeypatch.setattr(insights, "_profile_style_text", lambda _user_id: "视觉型·动手型")

    pack = insights._multimodal_suggested_types(
        "demo-student-1", "transformer/attention"
    )

    assert pack[0] == "mindmap"
    assert {"mindmap", "video", "code", "quiz"}.issubset(pack)

    dashboard_pack = insights._multimodal_suggested_types("demo-student-1", "AI_015")
    assert {"mindmap", "video", "code", "quiz"}.issubset(dashboard_pack)


def test_rag_recommendation_pack_adds_audio_for_auditory_learner(monkeypatch):
    from backend.app.api.v1 import insights

    monkeypatch.setattr(insights, "_profile_style_text", lambda _user_id: "听觉型")

    pack = insights._multimodal_suggested_types("demo-student-21", "rag/retrieval")

    assert pack[0] == "tts"
    assert {"mindmap", "document", "code"}.issubset(pack)


def test_transformer_mistake_repair_materials_cover_visual_video_and_code():
    from backend.app.services.mistake_insights import _generate_learning_materials

    materials = _generate_learning_materials(Counter({"transformer/attention": 3}))

    assert {item["type"] for item in materials} == {"mindmap", "video", "code"}
