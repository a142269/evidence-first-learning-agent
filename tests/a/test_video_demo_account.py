from __future__ import annotations


def test_recommendable_resources_are_published_course_learning_assets():
    from backend.app.api.v1 import insights

    good = {
        "id": "good",
        "user_id": "",
        "type": "document",
        "title": "RAG 工程实践讲义",
        "metadata": {
            "course": "artificial_intelligence",
            "scope": "course",
            "status": "published",
        },
    }
    draft = {
        **good,
        "id": "draft",
        "title": "草稿：RAG 工程实践",
        "metadata": {**good["metadata"], "status": "draft"},
    }
    transcript = {**good, "id": "chat", "type": "tutoring"}
    wrong_course = {
        **good,
        "id": "python",
        "metadata": {**good["metadata"], "course": "python_programming"},
    }

    assert insights._is_recommendable_resource(
        good, "demo-student-1", "artificial_intelligence"
    )
    assert not insights._is_recommendable_resource(
        draft, "demo-student-1", "artificial_intelligence"
    )
    assert not insights._is_recommendable_resource(
        transcript, "demo-student-1", "artificial_intelligence"
    )
    assert not insights._is_recommendable_resource(
        wrong_course, "demo-student-1", "artificial_intelligence"
    )


def test_personalization_chain_is_scoped_to_course_and_best_path(monkeypatch):
    from backend.app.api.v1 import insights, learning_path

    monkeypatch.setattr(
        insights,
        "_bkt_masteries",
        lambda _user_id: {"AI_001": 0.91, "AI_002": 0.57, "PY_001": 0.05},
    )
    monkeypatch.setattr(
        insights,
        "_load_kp_names",
        lambda course="": (
            {"AI_001": "人工智能概述", "AI_002": "搜索算法"}
            if course == "artificial_intelligence"
            else {"PY_001": "Python 控制流"}
        ),
    )
    monkeypatch.setattr(insights, "_get_learner_archetype", lambda _user_id: {})
    monkeypatch.setattr(insights, "_get_cognitive_style", lambda _user_id: "图像化")
    monkeypatch.setattr(
        insights,
        "_build_adaptive_strategy",
        lambda _user_id, course="": {
            "signals": [{"name": "course", "value": course}],
            "strategy": {"replan_recommended": False, "daily_practice_intensity": 4},
        },
    )
    monkeypatch.setattr(
        learning_path,
        "list_paths",
        lambda _user_id: {
            "paths": [
                {
                    "id": "ai-low",
                    "course": "artificial_intelligence",
                    "title": "AI 新路径",
                    "progress": 0,
                    "stages": [{}],
                },
                {
                    "id": "python-high",
                    "course": "python_programming",
                    "title": "Python 路径",
                    "progress": 99,
                    "stages": [{}],
                },
                {
                    "id": "ai-primary",
                    "course": "artificial_intelligence",
                    "title": "AI 主路径",
                    "progress": 82,
                    "stages": [{}, {}],
                },
            ]
        },
    )

    result = insights.personalization_chain(
        "demo-student-1", course="artificial_intelligence"
    )

    assert result["bkt_summary"]["total_kps"] == 2
    assert result["bkt_summary"]["mastered_count"] == 1
    assert [item["kp_id"] for item in result["bkt_summary"]["weakest"]] == [
        "AI_002"
    ]
    assert result["path_personalization"]["path_id"] == "ai-primary"
    assert result["cognitive_style"] == "图像化"
    assert result["adaptive_signals"][0]["value"] == "artificial_intelligence"


def test_cognitive_style_accepts_primary_profile_field(monkeypatch):
    from backend.app.api.v1 import insights, profile

    class _Repo:
        @staticmethod
        def get(_user_id: str):
            return {"cognitive_style": {"primary": "图像化"}}

    monkeypatch.setattr(profile, "_repository", _Repo())
    assert insights._get_cognitive_style("demo-student-1") == "图像化"
