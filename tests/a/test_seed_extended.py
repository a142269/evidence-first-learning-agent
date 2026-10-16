"""A-owned 扩展种子（seed_extended.json）测试。

锁住演示容量目标：6 学生 / 120+ 答题 / 20 知识点 / 30 KG 边 / 6 路径，
并验证幂等性（二次导入零新增）。
"""
from __future__ import annotations

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from backend.app.core import models  # noqa: F401 - register tables
from backend.app.core.database import Base
from backend.app.core.models import (
    AssessmentRecord,
    BktStateRecord,
    DinaStateRecord,
    KnowledgePointRecord,
    KnowledgeRelationRecord,
    LearningPathRecord,
    ProfileRecord,
    Sm2ScheduleRecord,
)


def _fresh_sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed_ext.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _count(sessions, model) -> int:
    with sessions() as db:
        return db.query(func.count()).select_from(model).scalar()


def test_extended_hits_day3_volumes(tmp_path):
    from scripts.seed_demo import seed_database, seed_extended, SEED_PATH

    sessions = _fresh_sessions(tmp_path)

    baseline = seed_database(sessions, str(SEED_PATH))
    # seed.json 现在含 5 学生（B20 扩到 demo-student-1..5），所以 baseline == 5；
    # seed_extended.json 里 extra_students / extra_paths 是这 5 个的子集，幂等跳过 -> 0。
    assert baseline["profiles"] == 5
    assert baseline["paths"] == 5

    ext = seed_extended(sessions)
    assert ext["extra_profiles"] == 1
    assert ext["extra_paths"] == 1
    assert ext["knowledge_points"] == 20
    assert ext["kg_relations"] == 30
    assert ext["extra_assessments"] == 118
    assert ext["bkt_states"] == 60
    assert ext["dina_states"] == 60
    assert ext["sm2_schedules"] == 30

    assert _count(sessions, ProfileRecord) == 6
    assert _count(sessions, LearningPathRecord) == 6
    with sessions() as db:
        compare_profile = db.get(ProfileRecord, "demo-student-21")
        assert compare_profile.profile_data["display_name"] == "林同学（筑基型）"
        assert compare_profile.profile_data["nickname"] == "林同学（筑基型）"
    # baseline seed.json 11 + extended 118 = 129
    assert _count(sessions, AssessmentRecord) == 129
    assert _count(sessions, KnowledgePointRecord) == 20
    assert _count(sessions, KnowledgeRelationRecord) == 30


def test_extended_is_idempotent(tmp_path):
    from scripts.seed_demo import seed_database, seed_extended, SEED_PATH

    sessions = _fresh_sessions(tmp_path)
    seed_database(sessions, str(SEED_PATH))
    seed_extended(sessions)

    ext2 = seed_extended(sessions)
    for key in (
        "extra_profiles",
        "extra_paths",
        "extra_assessments",
        "knowledge_points",
        "kg_relations",
        "bkt_states",
        "dina_states",
        "sm2_schedules",
    ):
        assert ext2[key] == 0, f"二次导入 {key} 应为 0，实际 {ext2[key]}"
    assert ext2["skipped"] > 0


def test_extended_algorithm_states_use_valid_ranges(tmp_path):
    from scripts.seed_demo import seed_database, seed_extended, SEED_PATH

    sessions = _fresh_sessions(tmp_path)
    seed_database(sessions, str(SEED_PATH))
    seed_extended(sessions)

    with sessions() as db:
        for row in db.query(BktStateRecord).all():
            assert 0.05 <= row.p_learned <= 0.95
            assert 0.0 <= row.p_slip <= 1.0
            assert 0.0 <= row.p_guess <= 1.0
        for row in db.query(DinaStateRecord).all():
            assert 0.05 <= row.mastery <= 0.95
        for row in db.query(Sm2ScheduleRecord).all():
            assert row.repetitions >= 0
            assert row.interval_days >= 1
            assert 1.3 <= row.easiness <= 3.0


def test_knowledge_graph_relations_reference_existing_kps(tmp_path):
    from scripts.seed_demo import seed_extended

    sessions = _fresh_sessions(tmp_path)
    seed_extended(sessions)

    with sessions() as db:
        kp_ids = {row.id for row in db.query(KnowledgePointRecord).all()}
        for rel in db.query(KnowledgeRelationRecord).all():
            assert rel.source_id in kp_ids
            assert rel.target_id in kp_ids
            assert rel.relation_type
            assert 0.0 <= rel.weight <= 1.0
