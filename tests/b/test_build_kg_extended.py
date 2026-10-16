"""build_kg_extended 测试 (v7 Day 5-6 补完)."""
from __future__ import annotations

import pytest

from backend.app.core.database import configure_database, init_db, SessionLocal
from backend.app.core import models  # noqa: F401
from backend.app.core.models import KnowledgePointRecord, KnowledgeRelationRecord


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    configure_database(f"sqlite:///{(tmp_path / 'kgext.db').as_posix()}")
    init_db()
    yield


def test_build_kg_extended_creates_100_plus_nodes():
    from scripts.build_kg_extended import build_kg_extended

    stats = build_kg_extended()
    # 20 基线 + 87 新增 = 107
    assert stats["new_kps"] >= 100  # 基线+新增

    with SessionLocal() as db:
        total = db.query(KnowledgePointRecord).count()
    assert total >= 100  # 总数 100+


def test_build_kg_extended_creates_300_plus_relations():
    from scripts.build_kg_extended import build_kg_extended

    build_kg_extended()
    with SessionLocal() as db:
        total = db.query(KnowledgeRelationRecord).count()
    assert total >= 300  # 300+ 关系


def test_build_kg_extended_idempotent():
    from scripts.build_kg_extended import build_kg_extended

    build_kg_extended()
    stats2 = build_kg_extended()
    assert stats2["new_kps"] == 0
    assert stats2["new_relations"] == 0


def test_kps_have_community_metadata():
    """每个新 KP 的 metadata 应含 community 字段（社区标注）。"""
    from scripts.build_kg_extended import build_kg_extended

    build_kg_extended()
    with SessionLocal() as db:
        for kp in db.query(KnowledgePointRecord).all():
            if kp.id.startswith("python_") or kp.id in ("git_basics", "linux_basics"):
                comm = (kp.metadata_data or {}).get("community")
                assert comm is not None, f"{kp.id} 缺 community"


def test_relations_cover_multiple_types():
    """关系应覆盖多种类型。"""
    from scripts.build_kg_extended import build_kg_extended

    build_kg_extended()
    with SessionLocal() as db:
        types = {r.relation_type for r in db.query(KnowledgeRelationRecord).all()}
    assert len(types) >= 5  # 至少 5 种关系类型


def test_check_mode_reports_counts():
    from scripts.build_kg_extended import build_kg_extended, check_kg_stats

    build_kg_extended()
    s = check_kg_stats()
    assert s["total_kps"] >= 100
    assert s["total_relations"] >= 300
    assert "by_course" in s
    assert "by_community" in s
    assert "by_relation_type" in s


def test_kps_cover_six_courses():
    """KP 应覆盖 6 大课程域。"""
    from scripts.build_kg_extended import build_kg_extended, check_kg_stats

    build_kg_extended()
    s = check_kg_stats()
    assert len(s["by_course"]) >= 6
    for course in ("AI 入门", "AI 基础", "机器学习", "深度学习", "应用", "项目"):
        assert course in s["by_course"], f"缺课程: {course}"
