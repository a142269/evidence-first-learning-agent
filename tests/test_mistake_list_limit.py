from backend.app.api.v1 import mistakes as mistake_api
from backend.app.services import mistake_insights as insight_service


def test_list_mistakes_limit_keeps_newest_records(monkeypatch) -> None:
    monkeypatch.setattr(mistake_api, "_db_available", False)
    monkeypatch.setattr(
        mistake_api,
        "_mistakes",
        {
            "student-limit": [
                {"id": "old", "created_at": 1, "error_type": "unknown"},
                {"id": "middle", "created_at": 2, "error_type": "unknown"},
                {"id": "new", "created_at": 3, "error_type": "unknown"},
            ]
        },
    )

    result = mistake_api.list_mistakes("student-limit", category="", limit=2, course="")

    assert result["total"] == 3
    assert [item["id"] for item in result["mistakes"]] == ["new", "middle"]


def test_mistake_insights_uses_only_unresolved_records(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(mistake_api, "_db_available", False)
    monkeypatch.setattr(
        mistake_api,
        "_mistakes",
        {
            "student-insights": [
                {"id": "resolved-bool", "created_at": 3, "kp_id": "old_kp", "resolved": True},
                {"id": "resolved-at", "created_at": 2, "kp_id": "done_kp", "resolved_at": 12345},
                {"id": "active", "created_at": 1, "kp_id": "current_kp", "resolved": False},
            ]
        },
    )

    def fake_generate(records, user_id, use_llm=True):
        captured["ids"] = [item["id"] for item in records]
        captured["user_id"] = user_id
        return {
            "summary": "ok",
            "weak_points": [],
            "error_pattern": "ok",
            "recommendations": {"similar_questions": [], "learning_materials": []},
            "evaluation": {"overall_score": 0.5, "strengths": [], "weaknesses": [], "suggestions": []},
            "source": "rule",
            "generated_at": 1,
        }

    monkeypatch.setattr(insight_service, "generate_mistake_insights", fake_generate)

    mistake_api.get_mistake_insights("student-insights", course="")

    assert captured["user_id"] == "student-insights"
    assert captured["ids"] == ["active"]


def test_mistake_insights_falls_back_to_history_when_all_resolved(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(mistake_api, "_db_available", False)
    monkeypatch.setattr(
        mistake_api,
        "_mistakes",
        {
            "student-history": [
                {"id": "resolved-new", "created_at": 2, "kp_id": "done_kp", "resolved": True},
                {"id": "resolved-old", "created_at": 1, "kp_id": "old_kp", "resolved_at": 12345},
            ]
        },
    )

    def fake_generate(records, user_id, use_llm=True):
        captured["ids"] = [item["id"] for item in records]
        captured["user_id"] = user_id
        return {
            "summary": "ok",
            "weak_points": [],
            "error_pattern": "ok",
            "recommendations": {"similar_questions": [], "learning_materials": []},
            "evaluation": {"overall_score": 0.5, "strengths": [], "weaknesses": [], "suggestions": []},
            "source": "rule",
            "generated_at": 1,
        }

    monkeypatch.setattr(insight_service, "generate_mistake_insights", fake_generate)

    mistake_api.get_mistake_insights("student-history", course="")

    assert captured["user_id"] == "student-history"
    assert captured["ids"] == ["resolved-new", "resolved-old"]
