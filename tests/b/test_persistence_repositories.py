from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.core import models  # noqa: F401


def _sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'repo.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_profile_repository_deep_merges_and_persists(tmp_path):
    from backend.app.repositories.profile_repo import ProfileRepository

    sessions = _sessions(tmp_path)
    repo = ProfileRepository(sessions)
    repo.upsert("u1", {"knowledge_base": {"level": "初级", "score": 0.3}})
    repo.upsert("u1", {"knowledge_base": {"score": 0.6}, "learning_goal": {"goal": "竞赛"}})

    stored = ProfileRepository(sessions).get("u1")
    assert stored == {
        "knowledge_base": {"level": "初级", "score": 0.6},
        "learning_goal": {"goal": "竞赛"},
    }

    assert repo.reset("u1") is True
    assert repo.get("u1") == {}


def test_learning_path_repository_orders_and_updates_progress(tmp_path):
    from backend.app.repositories.path_repo import LearningPathRepository

    sessions = _sessions(tmp_path)
    repo = LearningPathRepository(sessions)
    repo.save({
        "id": "path-old",
        "user_id": "u1",
        "title": "旧路径",
        "stages": [{"title": "A"}, {"title": "B"}],
        "created_at": 10.0,
    })
    repo.save({
        "id": "path-new",
        "user_id": "u1",
        "title": "新路径",
        "stages": [{"title": "C"}],
        "created_at": 20.0,
    })

    assert [item["id"] for item in repo.list("u1")] == ["path-new", "path-old"]
    updated = repo.update_progress("path-old", stage_index=0, completed=True)
    assert updated["current_stage"] == 1
    assert updated["progress"] == 50.0
    assert LearningPathRepository(sessions).get("path-old")["progress"] == 50.0


def test_assessment_repository_builds_compatible_summary(tmp_path):
    from backend.app.repositories.assessment_repo import AssessmentRepository

    sessions = _sessions(tmp_path)
    repo = AssessmentRepository(sessions)
    repo.add("u1", {"type": "quiz", "score": 80, "topic": "CNN", "timestamp": 10.0})
    repo.add("u1", {"type": "quiz", "score": 100, "topic": "RNN", "timestamp": 20.0})
    repo.add("u1", {"type": "resource_view", "topic": "Transformer", "timestamp": 30.0})
    repo.add("u1", {"type": "question", "topic": "Attention", "timestamp": 40.0})

    summary = AssessmentRepository(sessions).summary("u1")
    assert summary["total_sessions"] == 4
    assert summary["quiz_avg_score"] == 90.0
    assert summary["resources_used"] == 1
    assert summary["questions_asked"] == 1
    assert [row["topic"] for row in summary["recent_records"]] == [
        "CNN", "RNN", "Transformer", "Attention"
    ]
