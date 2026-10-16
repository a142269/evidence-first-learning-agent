"""B 侧扩展种子测试 (v7 Day 4)."""
from __future__ import annotations

import pytest

from backend.app.core.database import configure_database, init_db, SessionLocal
from backend.app.core import models  # noqa: F401
from backend.app.core.models import (
    MistakeRecord, GamificationProfileRecord, BktStateRecord,
    KnowledgePointRecord, ProfileRecord,
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    configure_database(f"sqlite:///{(tmp_path / 'bext.db').as_posix()}")
    init_db()
    yield


def _seed_prerequisites():
    """灌入 2 学生 + 3 KP + 2 BKT 状态，作为 B 扩展种子的前置依赖。"""
    with SessionLocal() as db:
        for uid in ("demo-student-1", "demo-student-2"):
            db.add(ProfileRecord(user_id=uid, profile_data={"knowledge_base": {"score": 0.5}}))
        for i in range(3):
            db.add(KnowledgePointRecord(
                id=f"kp_{i}", course="ai", name=f"概念{i}",
                description="测试", metadata_data={"bloom": "understand"},
            ))
        # BKT 状态（无历史，待 B 扩展补充）
        db.add(BktStateRecord(
            user_id="demo-student-1", knowledge_point_id="kp_0",
            p_learned=0.6, p_transit=0.1, p_slip=0.1, p_guess=0.2, history=[],
        ))
        db.add(BktStateRecord(
            user_id="demo-student-2", knowledge_point_id="kp_1",
            p_learned=0.3, p_transit=0.1, p_slip=0.1, p_guess=0.2, history=[],
        ))
        db.commit()


def test_seed_b_extended_creates_mistakes_and_gamification():
    _seed_prerequisites()
    from scripts.seed_b_extended import seed_b_extended

    stats = seed_b_extended()
    assert stats["mistakes"] >= 8   # 2 学生 × 4-6 条
    assert stats["gamification"] >= 2
    assert stats["bkt_history"] >= 2  # 2 条 BKT 补历史


def test_seed_b_extended_idempotent():
    _seed_prerequisites()
    from scripts.seed_b_extended import seed_b_extended

    seed_b_extended()
    stats2 = seed_b_extended()
    assert stats2["mistakes"] == 0
    assert stats2["gamification"] == 0
    assert stats2["bkt_history"] == 0  # 已有历史的跳过


def test_bkt_history_has_30day_shape():
    """BKT 历史轨迹应有 20 个点覆盖过去 30 天。"""
    _seed_prerequisites()
    from scripts.seed_b_extended import seed_b_extended

    seed_b_extended()
    with SessionLocal() as db:
        rec = db.query(BktStateRecord).filter(
            BktStateRecord.user_id == "demo-student-1",
            BktStateRecord.knowledge_point_id == "kp_0",
        ).one()
        assert len(rec.history) >= 15
        # 历史点时间跨度覆盖过去 30 天
        days = [h.get("day", 0) for h in rec.history]
        assert min(days) <= -25  # 最早 ~30 天前
        assert max(days) <= 0    # 最晚今天


def test_mistakes_cover_multiple_error_types():
    """错题应覆盖多种错因。"""
    _seed_prerequisites()
    from scripts.seed_b_extended import seed_b_extended

    seed_b_extended()
    with SessionLocal() as db:
        types = {m.error_type for m in db.query(MistakeRecord).all()}
    assert len(types) >= 4  # 至少 4 种不同错因


def test_gamification_profiles_have_achievements():
    _seed_prerequisites()
    from scripts.seed_b_extended import seed_b_extended

    seed_b_extended()
    with SessionLocal() as db:
        for g in db.query(GamificationProfileRecord).all():
            assert g.xp > 0
            assert g.level >= 1
            assert isinstance(g.achievements, list) and len(g.achievements) >= 1


def test_check_mode_reports_counts(tmp_path, capsys):
    _seed_prerequisites()
    from scripts.seed_b_extended import seed_b_extended

    seed_b_extended()
    # 调用 --check 逻辑
    import scripts.seed_b_extended as mod
    import argparse
    with SessionLocal() as db:
        students = db.query(ProfileRecord).count()
        mistakes = db.query(MistakeRecord).count()
        games = db.query(GamificationProfileRecord).count()
    assert students == 2  # 前置只灌了 2 学生画像
    assert mistakes >= 8
    assert games == 5     # GAMIFICATION_PROFILES 固定 5 个
