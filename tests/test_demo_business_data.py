from __future__ import annotations

from pathlib import Path


def test_business_seed_is_complete_and_idempotent(tmp_path: Path) -> None:
    from backend.app.core.database import SessionLocal, configure_database, init_db
    from backend.app.core.models import KnowledgePointRecord, LearningPathRecord, ProfileRecord
    from scripts.seed_demo_business_data import seed_business_data

    configure_database(f"sqlite:///{(tmp_path / 'business-demo.db').as_posix()}")
    init_db()
    with SessionLocal() as db:
        for kp_id, name in (
            ("ml_basics", "机器学习基础"),
            ("attention_mechanism", "注意力机制"),
            ("transformer", "Transformer"),
        ):
            db.add(KnowledgePointRecord(id=kp_id, name=name, course="artificial_intelligence"))
        db.commit()

    first = seed_business_data(SessionLocal)
    second = seed_business_data(SessionLocal)

    assert first["complete"] is True
    assert first["student_coverage"] == second["student_coverage"]
    assert first["table_counts"] == second["table_counts"]
    assert first["demo_students"] == 20
    assert first["student_coverage"]["learner_archetypes"] == 20
    assert first["student_coverage"]["realtime_states"] == 20
    with SessionLocal() as db:
        profile = db.get(ProfileRecord, "demo-student-1")
        assert profile is not None
        assert profile.profile_data["display_name"] == "杜同学"
        path = (
            db.query(LearningPathRecord)
            .filter(LearningPathRecord.user_id == "demo-student-1")
            .one()
        )
        assert path.title.startswith("杜同学")
        assert path.metadata_data["course"] == "artificial_intelligence"


def test_prepare_video_account_repairs_identity_path_and_mistake_backlog(tmp_path: Path) -> None:
    from backend.app.core.database import SessionLocal, configure_database, init_db
    from backend.app.core.models import KnowledgePointRecord, LearningPathRecord, ProfileRecord
    from scripts.seed_demo_business_data import (
        SOURCE,
        prepare_video_demo_account,
        seed_business_data,
    )

    configure_database(f"sqlite:///{(tmp_path / 'video-demo.db').as_posix()}")
    init_db()
    with SessionLocal() as db:
        db.add(
            KnowledgePointRecord(
                id="AI_001",
                name="人工智能概述",
                course="artificial_intelligence",
            )
        )
        db.commit()
    seed_business_data(SessionLocal)

    with SessionLocal() as db:
        profile = db.get(ProfileRecord, "demo-student-1")
        profile.profile_data = {**profile.profile_data, "display_name": "小明", "nickname": "小明"}
        db.add(
            LearningPathRecord(
                id="path-generated-extra",
                user_id="demo-student-1",
                title="临时生成路径",
                stages=[],
                progress=0,
                metadata_data={"planned_by": "path_planner"},
            )
        )
        db.commit()

    result = prepare_video_demo_account(SessionLocal)

    assert result["complete"] is True
    assert result["user_id"] == "demo-student-1"
    assert result["display_name"] == "杜同学"
    assert result["path_count"] == 1
    assert result["open_mistakes"] <= 8
    with SessionLocal() as db:
        path = db.get(LearningPathRecord, f"{SOURCE}-demo-student-1-path")
        assert path is not None
        assert path.metadata_data["course"] == "artificial_intelligence"
        current_stage = path.stages[path.current_stage]
        assert current_stage["title"] == "多模态融合与专项补强"
        assert current_stage["kp_ids"][:3] == ["AI_015", "AI_006_03", "AI_008"]
        assert path.metadata_data["focus_kps"][:3] == ["AI_015", "AI_006_03", "AI_008"]
        assert path.metadata_data["today_tasks"][0]["kp_id"] == "AI_015"


def test_peer_comparison_and_realtime_fallback_use_seeded_data(tmp_path: Path) -> None:
    from backend.app.core.database import SessionLocal, configure_database, init_db
    from backend.app.core.models import KnowledgePointRecord
    from scripts.seed_demo_business_data import seed_business_data

    configure_database(f"sqlite:///{(tmp_path / 'business-api.db').as_posix()}")
    init_db()
    with SessionLocal() as db:
        db.add(
            KnowledgePointRecord(
                id="transformer",
                name="Transformer",
                course="artificial_intelligence",
            )
        )
        db.commit()
    seed_business_data(SessionLocal)

    from backend.app.api.v1.chat import get_realtime
    from backend.app.api.v1.insights import peer_comparison

    strong = peer_comparison("demo-student-2")
    developing = peer_comparison("demo-student-10")
    realtime = get_realtime("demo-session-demo-student-10")

    assert strong["cohort_size"] == 20
    assert strong["dimensions"]["knowledge_base"] != developing["dimensions"]["knowledge_base"]
    assert strong["peer_average"] != developing["peer_average"]
    assert realtime["state"]["confusion"] >= 0.5
    assert realtime["state"]["next_best_action"]
