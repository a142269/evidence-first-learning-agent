from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.models import BktStateRecord, KnowledgePointRecord, MistakeRecord, ProfileRecord
from backend.app.services.v2_learning_tools import ToolContext, V2LearningTools


@pytest.mark.asyncio
async def test_course_search_has_time_for_interactive_embedding(monkeypatch):
    monkeypatch.setenv("V2_COURSE_AUTH_MODE", "environment")

    def slow_retrieve(query, course):
        time.sleep(0.05)
        return [{"chunk_id": "c1", "source": "lesson.md", "content": "evidence"}]

    assert V2LearningTools(slow_retrieve).search_timeout_seconds > 20
    tools = V2LearningTools(slow_retrieve, timeout_seconds=0.01,
                            search_timeout_seconds=2.0)
    ctx = ToolContext(run_id="r1", user_id="alice", course_id="course-a", role="tutor")
    result = await tools.call(ctx, "search_course_evidence", {"query": "RAG"})
    assert result.status == "success"


@pytest.mark.asyncio
async def test_v2_tools_reject_model_supplied_identity_and_role_escalation(monkeypatch):
    monkeypatch.setenv("V2_COURSE_AUTH_MODE", "environment")
    seen = []
    tools = V2LearningTools(lambda query, course: seen.append((query, course)) or [
        {"chunk_id": "c1", "source": "lesson.md", "content": "evidence"}])
    tutor = ToolContext(run_id="r1", user_id="alice", course_id="course-a", role="tutor")
    assert (await tools.call(tutor, "search_course_evidence", {"query": "RAG", "user_id": "bob"})).status == "invalid_args"
    assert (await tools.call(tutor, "get_learning_profile", {})).status == "denied"
    answer = await tools.call(tutor, "search_course_evidence", {"query": "RAG"})
    assert answer.status == "success" and seen == [("RAG", "course-a")]
    assert set(answer.audit()) == {"tool", "version", "status", "latency_ms", "request_hash", "result_count"}
    assert "RAG" not in str(answer.audit())


@pytest.mark.asyncio
async def test_profile_and_mistakes_are_scoped_to_authenticated_user_and_course(tmp_path, monkeypatch):
    monkeypatch.setenv("V2_COURSE_AUTH_MODE", "environment")
    engine = create_engine(f"sqlite:///{(tmp_path / 'tools.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    for model in (ProfileRecord, KnowledgePointRecord, MistakeRecord, BktStateRecord):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as db:
        db.add_all([
            ProfileRecord(user_id="alice", profile_data={"learning_preference": {"mode": "混合学习"},
                                                           "private_note": "do not expose"}),
            ProfileRecord(user_id="bob", profile_data={"learning_preference": {"mode": "other"}}),
            KnowledgePointRecord(id="kp-a", course="course-a", name="检索"),
            KnowledgePointRecord(id="kp-b", course="course-b", name="别的课"),
            MistakeRecord(id="m-a", user_id="alice", knowledge_point_id="kp-a", error_type="concept"),
            MistakeRecord(id="m-b", user_id="bob", knowledge_point_id="kp-a", error_type="concept"),
            MistakeRecord(id="m-c", user_id="alice", knowledge_point_id="kp-b", error_type="concept"),
        ])
    tools = V2LearningTools(session_factory=factory)
    ctx = ToolContext(run_id="r1", user_id="alice", course_id="course-a", role="planner")
    profile = await tools.call(ctx, "get_learning_profile", {})
    assert profile.data == {"preference": {"mode": "混合学习"}, "weak_points": []}
    assert "private_note" not in str(profile.data)
    mistakes = await tools.call(ctx, "get_recent_mistakes", {})
    assert [item["knowledge_point_id"] for item in mistakes.data] == ["kp-a"]
    engine.dispose()
