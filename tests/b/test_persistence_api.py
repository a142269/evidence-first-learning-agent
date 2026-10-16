from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core import models  # noqa: F401
from backend.app.core.database import Base
from backend.app.repositories.assessment_repo import AssessmentRepository
from backend.app.repositories.path_repo import LearningPathRepository
from backend.app.repositories.profile_repo import ProfileRepository


def _sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_profile_api_uses_repository_and_preserves_response(tmp_path, monkeypatch):
    from backend.app.api.v1 import profile as api

    sessions = _sessions(tmp_path)
    repo = ProfileRepository(sessions)
    monkeypatch.setattr(api, "_repository", repo, raising=False)

    response = api.update_profile(
        "u1",
        {"updates": {"knowledge_base": {"level": "middle", "score": 0.6}}},
    )

    assert response["profile"]["knowledge_base"]["score"] == 0.6
    assert response["total_dimensions"] == 8
    assert response["filled_dimensions"] == 1
    assert response["completeness"] == 12.5
    assert ProfileRepository(sessions).get("u1")["knowledge_base"]["level"] == "middle"


def test_profile_api_falls_back_to_seed_for_demo_user(monkeypatch):
    from backend.app.api.v1 import profile as api

    class EmptyRepository:
        def get(self, user_id):
            return None

    monkeypatch.setattr(api, "_repository", EmptyRepository(), raising=False)

    response = api.get_profile("demo-student-1")

    assert response["filled_dimensions"] == 8
    assert response["total_dimensions"] == 8
    assert response["completeness"] == 100.0
    assert response["profile"]["knowledge_base"]


def test_profile_api_maps_legacy_updates_to_standard_eight_schema(tmp_path, monkeypatch):
    from backend.app.api.v1 import profile as api

    sessions = _sessions(tmp_path)
    repo = ProfileRepository(sessions)
    monkeypatch.setattr(api, "_repository", repo, raising=False)

    response = api.update_profile(
        "u2",
        {
            "updates": {
                "weak_points": {"topics": ["rnn-gradient"]},
                "learning_preference": {"preferred_format": "diagram"},
            },
            "source": "chat",
        },
    )

    standard = {
        "knowledge_base",
        "cognitive_style",
        "error_pattern",
        "learning_habit",
        "learning_progress",
        "interest_model",
        "resource_preference",
        "self_learning_ability",
    }
    assert standard.issubset(response["profile"])
    assert response["profile"]["error_pattern"]["topics"] == ["rnn-gradient"]
    assert response["profile"]["learning_habit"]["preferred_format"] == "diagram"
    assert response["profile"]["resource_preference"]["preferred_format"] == "diagram"
    assert response["profile"]["weak_points"]["topics"] == ["rnn-gradient"]


def test_learning_path_api_uses_repository_and_preserves_progress(tmp_path, monkeypatch):
    from backend.app.api.v1 import learning_path as api

    sessions = _sessions(tmp_path)
    repo = LearningPathRepository(sessions)
    monkeypatch.setattr(api, "_repository", repo, raising=False)

    saved = api.save_path({
        "user_id": "u1",
        "title": "Python path",
        "stages": [{"title": "basic"}, {"title": "oop"}],
    })
    updated = api.update_progress(
        saved["path_id"], {"stage_index": 0, "completed": True}
    )

    assert updated["path"]["progress"] == 50.0
    assert LearningPathRepository(sessions).get(saved["path_id"])["current_stage"] == 1


def test_assessment_api_uses_repository_and_preserves_summary(tmp_path, monkeypatch):
    from backend.app.api.v1 import assessment as api

    sessions = _sessions(tmp_path)
    repo = AssessmentRepository(sessions)
    monkeypatch.setattr(api, "_repository", repo, raising=False)

    api.add_record("u1", {"type": "quiz", "score": 88, "topic": "list"})
    summary = api.get_assessment("u1")

    assert summary["quiz_avg_score"] == 88.0
    assert summary["recent_records"][0]["topic"] == "list"
    assert AssessmentRepository(sessions).summary("u1")["total_sessions"] == 1
