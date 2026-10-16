from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core import models  # noqa: F401
from backend.app.core.database import Base


def test_assessment_record_preserves_external_id(monkeypatch):
    from backend.app.api.v1 import assessment

    captured = {}

    class Repo:
        def add(self, user_id, record):
            captured.update(record)
            return record

    monkeypatch.setattr(assessment, "_repository", Repo())
    result = assessment.add_record(
        "student-1",
        {
            "external_id": "path-1:task-1:completed",
            "type": "task_completed",
            "metadata": {"path_id": "path-1", "task_id": "task-1"},
        },
    )

    assert captured["external_id"] == "path-1:task-1:completed"
    assert result["record"]["metadata"]["task_id"] == "task-1"


def test_path_schedule_returns_deadlines_tasks_and_feasibility():
    from backend.app.api.v1.insights import _build_path_schedule

    today = date(2026, 7, 12)
    stages = [
        {"id": 0, "title": "基础概念", "kp_ids": ["a"], "estimated_minutes": 120},
        {"id": 1, "title": "核心方法", "kp_ids": ["b"], "estimated_minutes": 180},
    ]
    result = _build_path_schedule(
        stages,
        goal="掌握人工智能基础",
        target_date=(today + timedelta(days=3)).isoformat(),
        daily_minutes=60,
        interest="自然语言处理",
        today=today,
    )

    assert result["constraints"]["goal"] == "掌握人工智能基础"
    assert result["recommended_daily_minutes"] == 75
    assert result["feasibility"]["status"] == "insufficient"
    assert len(result["stage_deadlines"]) == 2
    assert result["today_tasks"][0]["duration_minutes"] <= 60
    assert result["milestones"][-1]["due_date"] == (today + timedelta(days=3)).isoformat()


def test_resource_weight_sorting_prefers_high_weight_type():
    from backend.app.api.v1.insights import _sort_recommendation_items

    items = [
        {"title": "讲义", "type": "document"},
        {"title": "练习", "type": "quiz"},
        {"title": "导图", "type": "mindmap"},
    ]
    ranked = _sort_recommendation_items(
        items,
        {"document": 1.0, "quiz": 2.0, "mindmap": 1.5},
    )

    assert [item["title"] for item in ranked] == ["练习", "导图", "讲义"]


def test_resource_weight_sorting_normalizes_document_aliases():
    from backend.app.api.v1.insights import _sort_recommendation_items

    ranked = _sort_recommendation_items(
        [{"title": "练习", "type": "quiz"}, {"title": "讲义", "type": "doc"}],
        {"document": 3.0, "quiz": 1.0},
    )
    assert ranked[0]["title"] == "讲义"


def test_resource_sorting_keeps_primary_weakness_ahead_of_type_weight():
    from backend.app.api.v1.insights import _sort_recommendation_items

    ranked = _sort_recommendation_items(
        [
            {"title": "次要薄弱点练习", "type": "quiz", "kp_id": "AI_006_02"},
            {"title": "多模态大模型综述", "type": "document", "kp_id": "AI_015"},
        ],
        {"document": 1.0, "quiz": 2.0},
        {"AI_015": 0, "AI_006_02": 1},
    )
    assert ranked[0]["kp_id"] == "AI_015"


def test_assessment_summary_keeps_all_completed_task_ids(tmp_path):
    from backend.app.repositories.assessment_repo import AssessmentRepository

    engine = create_engine(f"sqlite:///{tmp_path / 'learning-loop.db'}")
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    repo = AssessmentRepository(sessions)
    repo.add("u1", {
        "external_id": "path-1:task-1:completed",
        "type": "task_completed",
        "metadata": {"task_id": "task-1"},
    })
    for index in range(12):
        repo.add("u1", {"type": "quiz", "score": 100, "topic": str(index)})

    summary = repo.summary("u1")
    assert summary["completed_task_ids"] == ["task-1"]


def test_stage_content_resolves_persisted_kp_ids_to_real_learning_items():
    from backend.app.api.v1.learning_path import _build_stage_content

    path = {
        "id": "path-1",
        "stages": [{
            "id": "stage-1",
            "title": "基础诊断与补齐",
            "kp_ids": ["AI_001", "python_basics"],
        }],
    }
    catalog = {
        "AI_001": {
            "name": "人工智能概述",
            "description": "理解人工智能的定义、发展与应用。",
            "bloom_level": "remember",
            "difficulty": 1,
            "estimated_minutes": 120,
        },
        "python_basics": {
            "name": "Python 基础",
            "description": "掌握变量、控制流、函数与模块。",
            "bloom_level": "apply",
            "difficulty": 1,
            "estimated_minutes": 90,
        },
    }

    result = _build_stage_content(
        path,
        "stage-1",
        catalog=catalog,
        masteries={"AI_001": 0.82, "python_basics": 0.63},
    )

    assert result["stage"]["title"] == "基础诊断与补齐"
    assert [item["name"] for item in result["items"]] == ["人工智能概述", "Python 基础"]
    assert result["items"][0]["mastery_pct"] == 82
    assert result["items"][1]["description"] == "掌握变量、控制流、函数与模块。"
    assert result["source"] == "persisted_learning_path × knowledge_catalog × bkt"


def test_stage_content_supports_legacy_kps_field():
    from backend.app.api.v1.learning_path import _build_stage_content

    result = _build_stage_content(
        {
            "id": "seed-path-1",
            "stages": [{"title": "NLP 与 Transformer", "kps": ["nlp_basics", "transformer"]}],
        },
        "0",
        catalog={
            "nlp_basics": {"name": "NLP 基础", "description": "分词、词向量与文本表示。"},
            "transformer": {"name": "Transformer", "description": "注意力与编码器架构。"},
        },
        masteries={"nlp_basics": 0.62, "transformer": 0.48},
    )

    assert result["total"] == 2
    assert [item["name"] for item in result["items"]] == ["NLP 基础", "Transformer"]
