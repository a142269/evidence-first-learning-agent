from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


CANONICAL_ERROR_CODES = {
    "conceptual_misunderstanding",
    "calculation_error",
    "application_transfer",
    "careless_error",
    "reading_comprehension",
    "memory_gap",
    "strategy_error",
    "incomplete_answer",
}


def _fresh_database(tmp_path: Path, filename: str = "unification.db"):
    from backend.app.core.database import SessionLocal, configure_database, init_db

    configure_database(f"sqlite:///{(tmp_path / filename).as_posix()}")
    init_db()
    return SessionLocal


def test_review_and_agent_run_models_are_persisted(tmp_path: Path) -> None:
    from sqlalchemy import inspect

    from backend.app.core.models import AgentRunRecord, ReviewEventRecord

    session_factory = _fresh_database(tmp_path)
    from backend.app.core import database

    table_names = set(inspect(database.engine).get_table_names())

    assert ReviewEventRecord.__tablename__ in table_names
    assert AgentRunRecord.__tablename__ in table_names

    with session_factory() as db:
        db.add(
            ReviewEventRecord(
                user_id="demo-student-1",
                item_id="kp-1",
                item_type="knowledge_point",
                rating=4,
                before_mastery=0.42,
                after_mastery=0.55,
                duration_minutes=8.5,
                reviewed_at=1_720_000_000,
                metadata_data={"source": "test"},
            )
        )
        db.add(
            AgentRunRecord(
                id="run-test-1",
                session_id="session-test-1",
                user_id="demo-student-1",
                workflow_type="path_planning",
                agents=["planner", "diagnosis"],
                tool_calls=3,
                artifact_count=1,
                success_count=2,
                duration_ms=920,
                status="success",
                metadata_data={"source": "test"},
                created_at=1_720_000_000,
            )
        )
        db.commit()

        assert db.query(ReviewEventRecord).count() == 1
        assert db.query(AgentRunRecord).count() == 1


def test_demo_seed_rebuilds_only_demo_business_data_with_sane_distributions(
    tmp_path: Path,
) -> None:
    from collections import Counter, defaultdict
    from datetime import datetime, timezone

    from backend.app.core.models import (
        AssessmentRecord,
        BktStateRecord,
        KnowledgePointRecord,
        LearningPathRecord,
        MistakeRecord,
        ProfileRecord,
    )
    from scripts.seed_demo_business_data import seed_business_data

    session_factory = _fresh_database(tmp_path, "seed-quality.db")
    with session_factory() as db:
        for index, name in enumerate(
            ("机器学习基础", "神经网络", "注意力机制", "Transformer", "RAG", "多智能体")
        ):
            db.add(
                KnowledgePointRecord(
                    id=f"kp-{index + 1}",
                    name=name,
                    course="artificial_intelligence",
                )
            )
        db.add(ProfileRecord(user_id="real-student", profile_data={"display_name": "真实学生"}))
        db.add(
            AssessmentRecord(
                external_id="real-assessment",
                user_id="real-student",
                record_type="quiz",
                score=88,
                duration=30,
                timestamp=1_720_000_000,
            )
        )
        db.add(
            LearningPathRecord(
                id="legacy-demo-path",
                user_id="demo-student-1",
                title="旧重复路径",
            )
        )
        db.commit()

    first = seed_business_data(session_factory, anchor_date="2026-07-11")
    second = seed_business_data(session_factory, anchor_date="2026-07-11")

    assert first["complete"] is True
    assert first["table_counts"] == second["table_counts"]

    anchor_ts = datetime(2026, 7, 11, 12, tzinfo=timezone.utc).timestamp()
    with session_factory() as db:
        assert db.query(KnowledgePointRecord).count() == 6
        assert db.get(ProfileRecord, "real-student") is not None
        assert (
            db.query(AssessmentRecord)
            .filter(AssessmentRecord.external_id == "real-assessment")
            .count()
            == 1
        )

        demo_users = [f"demo-student-{index}" for index in range(1, 21)]
        path_counts = Counter(
            user_id
            for (user_id,) in db.query(LearningPathRecord.user_id)
            .filter(LearningPathRecord.user_id.like("demo-student-%"))
            .all()
        )
        assert path_counts == Counter({user_id: 1 for user_id in demo_users})

        assessments = (
            db.query(AssessmentRecord)
            .filter(AssessmentRecord.user_id.like("demo-student-%"))
            .all()
        )
        counts = Counter(row.user_id for row in assessments)
        assert all(12 <= counts[user_id] <= 40 for user_id in demo_users)
        assert all(5 <= row.duration <= 45 for row in assessments)

        daily_minutes: dict[tuple[str, str], float] = defaultdict(float)
        for row in assessments:
            day = datetime.fromtimestamp(row.timestamp, tz=timezone.utc).date().isoformat()
            daily_minutes[(row.user_id, day)] += row.duration
        assert max(daily_minutes.values()) <= 1_440

        bkt_rows = (
            db.query(BktStateRecord)
            .filter(BktStateRecord.user_id.like("demo-student-%"))
            .all()
        )
        assert bkt_rows
        assert all(
            row.history
            and all(
                {"ts", "p_before", "p_after", "correct"} <= set(event)
                for event in row.history
            )
            for row in bkt_rows
        )

        mistake_codes = {
            code
            for (code,) in db.query(MistakeRecord.error_type)
            .filter(MistakeRecord.user_id.like("demo-student-%"))
            .distinct()
            .all()
        }
        assert mistake_codes <= CANONICAL_ERROR_CODES
        assert len(mistake_codes) >= 6

        latest_by_user = {
            user_id: max(row.timestamp for row in assessments if row.user_id == user_id)
            for user_id in demo_users
        }
        activity_levels = {
            "active" if anchor_ts - ts <= 7 * 86400 else
            "dormant" if anchor_ts - ts <= 30 * 86400 else
            "inactive"
            for ts in latest_by_user.values()
        }
        assert activity_levels == {"active", "dormant", "inactive"}


def _seed_overview_database(tmp_path: Path):
    from backend.app.core.models import KnowledgePointRecord
    from scripts.seed_demo_business_data import seed_business_data

    session_factory = _fresh_database(tmp_path, "overview.db")
    with session_factory() as db:
        for kp_id, name in (
            ("ml_basics", "机器学习基础"),
            ("neural_networks", "神经网络"),
            ("attention", "注意力机制"),
            ("transformer", "Transformer"),
            ("rag", "RAG"),
            ("multi_agent", "多智能体"),
        ):
            db.add(
                KnowledgePointRecord(
                    id=kp_id,
                    name=name,
                    course="artificial_intelligence",
                )
            )
        db.commit()
    seed_business_data(session_factory, anchor_date="2026-07-11")
    return session_factory


def test_student_overview_uses_one_consistent_backend_aggregation(tmp_path: Path) -> None:
    from backend.app.api.v1.insights import student_overview
    from backend.app.core.models import BktStateRecord, MistakeRecord

    session_factory = _seed_overview_database(tmp_path)
    result = student_overview("demo-student-1")

    assert set(result) >= {
        "user_id",
        "generated_at",
        "summary",
        "activity",
        "assessment",
        "profile",
        "path",
        "collaboration",
        "review",
    }
    assert 0 <= result["summary"]["average_mastery_pct"] <= 100
    assert 0 <= result["summary"]["profile_completeness_pct"] <= 100
    assert result["activity"]["this_week_minutes"] < 1_440 * 7
    assert result["activity"]["calendar"]
    assert result["activity"]["hour_distribution"]
    assert result["assessment"]["recent"]
    assert result["profile"]["dimensions"]
    assert result["profile"]["mastery_trend"]
    assert result["profile"]["knowledge_points"]
    assert result["path"]["stages"]
    assert result["path"]["today_tasks"]
    knowledge_point_tasks = [
        task for task in result["path"]["today_tasks"] if task.get("kp_id")
    ]
    assert knowledge_point_tasks
    assert all(task.get("kp_name") for task in knowledge_point_tasks)
    assert all(
        task["kp_id"] not in task.get("title", "")
        for task in knowledge_point_tasks
        if task["kp_name"] != task["kp_id"]
    )
    assert result["path"]["updated_at"]
    assert result["path"]["updated_date"]
    assert 0 <= result["review"]["completion_rate_pct"] <= 100

    with session_factory() as db:
        bkt_rows = db.query(BktStateRecord).filter_by(user_id="demo-student-1").all()
        expected_mastery = round(
            sum(row.p_learned for row in bkt_rows) / len(bkt_rows) * 100,
            1,
        )
        expected_mistakes = db.query(MistakeRecord).filter_by(user_id="demo-student-1").count()
    assert result["summary"]["average_mastery_pct"] == expected_mastery
    assert result["summary"]["mistake_count"] == expected_mistakes
    assert all(
        {"kp_id", "kp_name", "mastery_pct"} <= set(item)
        for item in result["profile"]["knowledge_points"]
    )


def test_student_overview_normalizes_legacy_second_durations(tmp_path: Path) -> None:
    from backend.app.api.v1.insights import student_overview
    from backend.app.core.models import AssessmentRecord

    session_factory = _seed_overview_database(tmp_path)
    with session_factory() as db:
        db.add(
            AssessmentRecord(
                external_id="legacy-seconds-record",
                user_id="demo-student-1",
                record_type="quiz",
                score=80,
                topic="Transformer",
                duration=1800,
                metadata_data={"source": "legacy"},
                timestamp=datetime(2026, 7, 11, 10, tzinfo=timezone.utc).timestamp(),
            )
        )
        db.commit()

    result = student_overview("demo-student-1")
    legacy = next(
        item for item in result["assessment"]["recent"]
        if item["external_id"] == "legacy-seconds-record"
    )
    assert legacy["duration_minutes"] == 30
    assert legacy["normalized_from_legacy"] is True


def test_review_submission_persists_and_history_returns_event(
    tmp_path: Path, monkeypatch,
) -> None:
    from backend.app.api.v1 import spaced_repetition
    from backend.app.api.v1.spaced_repetition import ReviewIn

    session_factory = _fresh_database(tmp_path, "review-history.db")

    class FakeSm2:
        def get_schedule(self, user_id: str, item_id: str):
            return {"easiness": 2.5, "repetitions": 1, "mastery": 0.42}

        def review(self, user_id: str, item_id: str, quality: int):
            return {
                "easiness": 2.6,
                "interval": 3,
                "repetitions": 2,
                "next_review_at": 1_720_086_400,
                "last_review_at": 1_720_000_000,
                "mastery": 0.55,
            }

    monkeypatch.setattr(spaced_repetition, "get_sm2", lambda: FakeSm2())
    response = spaced_repetition.post_review(
        ReviewIn(
            user_id="demo-student-1",
            item_id="transformer",
            algorithm="sm2",
            quality=4,
            duration_minutes=8,
        )
    )
    history = spaced_repetition.get_review_history("demo-student-1")

    assert response["review_event_id"]
    assert history["total"] == 1
    assert history["items"][0]["item_id"] == "transformer"
    assert history["items"][0]["rating"] == 4
    assert history["items"][0]["duration_minutes"] == 8

    from backend.app.core.models import ReviewEventRecord

    with session_factory() as db:
        assert db.query(ReviewEventRecord).count() == 1


def test_metrics_summary_includes_persisted_agent_run_history(tmp_path: Path) -> None:
    from backend.app.api.v1.metrics import metrics_summary

    _seed_overview_database(tmp_path)
    result = metrics_summary()

    assert result["agents"]["runs_total"] > 0
    assert result["agents"]["tool_calls_total"] > 0
    assert result["agents"]["success_rate_pct"] > 0
    assert result["artifacts"]["persisted_total"] > 0


def test_teacher_class_analytics_uses_shared_names_risks_and_activity_levels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend.app.api.v1 import teacher

    _seed_overview_database(tmp_path)
    anchor_ts = datetime(2026, 7, 11, 12, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(teacher.time, "time", lambda: anchor_ts)
    result = teacher.class_analytics(
        course="artificial_intelligence",
        days=90,
        weak_top=5,
        risk_top=20,
    )

    assert len(result["students"]) == 20
    assert {student["activity_level"] for student in result["students"]} == {
        "active",
        "dormant",
        "inactive",
    }
    assert all(student["display_name"] != student["user_id"] for student in result["students"])

    risk_levels = {student["level"] for student in result["risk_students"]}
    assert risk_levels == {"high", "medium", "low"}
    assert all(0 <= student["risk_score_pct"] <= 100 for student in result["risk_students"])
    assert all(student["display_name"] for student in result["risk_students"])
    assert all(student["activity_level"] for student in result["risk_students"])
    assert all(student["reasons"] for student in result["risk_students"])

    assert result["error_distribution"]
    assert all({"code", "label", "count", "ratio_pct"} <= set(item) for item in result["error_distribution"])
    assert all(item["label"] not in {"concept", "application", "unknown"} for item in result["error_distribution"])


def test_mistake_insight_parser_rejects_json_with_wrong_contract() -> None:
    from backend.app.services.mistake_insights import _parse_llm_response

    incompatible_report = {
        "overall_score": 0.74,
        "strengths": ["concepts"],
        "recommendations": ["practice"],
    }

    assert _parse_llm_response(json.dumps(incompatible_report)) is None


def test_mistake_top_up_is_idempotent_and_isolated(tmp_path: Path) -> None:
    from sqlalchemy import func

    from backend.app.core.models import (
        AssessmentRecord,
        KnowledgePointRecord,
        LearningPathRecord,
        MistakeRecord,
        ProfileRecord,
        Sm2ScheduleRecord,
    )
    from scripts.seed_demo_business_data import top_up_demo_mistakes

    session_factory = _fresh_database(tmp_path, "mistake-top-up.db")
    with session_factory() as db:
        for kp_id, name in (
            ("ml_basics", "机器学习基础"),
            ("neural_networks", "神经网络"),
            ("attention", "注意力机制"),
            ("transformer", "Transformer"),
            ("rag", "RAG"),
            ("multi_agent", "多智能体"),
        ):
            db.add(KnowledgePointRecord(id=kp_id, name=name, course="artificial_intelligence"))

        for user_index in range(1, 21):
            user_id = f"demo-student-{user_index}"
            for item in range(3):
                db.add(
                    MistakeRecord(
                        id=f"existing-{user_id}-{item}",
                        user_id=user_id,
                        knowledge_point_id="ml_basics",
                        question_data={"stem": f"已有错题 {item + 1}"},
                        error_type="conceptual_misunderstanding",
                        analysis="已有分析",
                        created_at=1_720_000_000 + item,
                    )
                )

        db.add(ProfileRecord(user_id="real-student", profile_data={"display_name": "真实学生"}))
        db.add(AssessmentRecord(external_id="real-assessment", user_id="real-student", score=90))
        db.add(LearningPathRecord(id="real-path", user_id="real-student", title="真实路径"))
        db.add(
            MistakeRecord(
                id="real-mistake",
                user_id="real-student",
                knowledge_point_id="ml_basics",
                question_data={"stem": "真实用户错题"},
                error_type="calculation_error",
                analysis="真实分析",
            )
        )
        db.commit()

        unrelated_before = {
            "profiles": db.query(ProfileRecord).count(),
            "assessments": db.query(AssessmentRecord).count(),
            "paths": db.query(LearningPathRecord).count(),
        }

    first = top_up_demo_mistakes(session_factory, anchor_date="2026-07-11")
    second = top_up_demo_mistakes(session_factory, anchor_date="2026-07-11")

    assert first["inserted"] > 0
    assert first["complete"] is True
    assert set(first["error_codes"]) == CANONICAL_ERROR_CODES
    assert second["inserted"] == 0
    assert second["after_total"] == first["after_total"]

    with session_factory() as db:
        counts = dict(
            db.query(MistakeRecord.user_id, func.count(MistakeRecord.id))
            .filter(MistakeRecord.user_id.like("demo-student-%"))
            .group_by(MistakeRecord.user_id)
            .all()
        )
        assert len(counts) == 20
        assert all(15 <= count <= 20 for count in counts.values())

        generated = (
            db.query(MistakeRecord)
            .filter(MistakeRecord.id.like("demo-business-seed-v2-%"))
            .all()
        )
        assert generated
        assert all(
            {"question", "stem", "student_answer", "correct_answer", "explanation", "source"}
            <= set(row.question_data)
            for row in generated
        )
        assert {row.error_type for row in generated} == CANONICAL_ERROR_CODES

        for user_id, count in counts.items():
            unresolved = (
                db.query(MistakeRecord)
                .filter_by(user_id=user_id, resolved_at=None)
                .count()
            )
            assert 0.3 <= unresolved / count <= 0.5

        unresolved_kps = {
            (row.user_id, row.knowledge_point_id)
            for row in db.query(MistakeRecord)
            .filter(MistakeRecord.user_id.like("demo-student-%"), MistakeRecord.resolved_at.is_(None))
            .all()
        }
        schedules = {
            (row.user_id, row.item_id)
            for row in db.query(Sm2ScheduleRecord)
            .filter(Sm2ScheduleRecord.user_id.like("demo-student-%"))
            .all()
        }
        assert unresolved_kps <= schedules

        assert db.get(MistakeRecord, "real-mistake") is not None
        assert unrelated_before == {
            "profiles": db.query(ProfileRecord).count(),
            "assessments": db.query(AssessmentRecord).count(),
            "paths": db.query(LearningPathRecord).count(),
        }


def test_mistake_api_uses_stem_as_question_fallback(tmp_path: Path) -> None:
    from backend.app.api.v1 import mistakes
    from backend.app.core.models import MistakeRecord

    session_factory = _fresh_database(tmp_path, "mistake-question-fallback.db")
    with session_factory() as db:
        db.add(
            MistakeRecord(
                id="stem-only-mistake",
                user_id="demo-student-1",
                knowledge_point_id="ml_basics",
                question_data={
                    "stem": "请解释机器学习中的过拟合，并给出一种缓解方法。",
                    "student_answer": "训练次数太多。",
                    "correct_answer": "模型过度拟合训练数据，可使用正则化等方法缓解。",
                    "explanation": "应同时说明训练集表现和泛化能力的差异。",
                },
                error_type="conceptual_misunderstanding",
                analysis="概念理解偏差",
            )
        )
        db.commit()

    records = mistakes._gather_user_records("demo-student-1")
    detail = mistakes._find_mistake("stem-only-mistake")

    assert records[0]["question"] == "请解释机器学习中的过拟合，并给出一种缓解方法。"
    assert detail is not None
    assert detail["question"] == records[0]["question"]
