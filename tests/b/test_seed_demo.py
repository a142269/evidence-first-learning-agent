"""
种子数据导入测试 —— 验证幂等性和数据完整性
"""
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.core import models  # noqa: F401


def _prepare(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return sessions


def test_seed_is_idempotent_and_populates_three_learners(tmp_path):
    from scripts.seed_demo import seed_database, SEED_PATH

    sessions = _prepare(tmp_path)

    # 第一次导入（B20 起 seed.json 含 5 学生 demo-student-1..5）
    stats1 = seed_database(sessions, str(SEED_PATH))
    assert stats1["profiles"] == 5
    assert stats1["paths"] == 5
    assert stats1["assessments"] >= 6

    # 第二次导入 —— 应该全部跳过
    stats2 = seed_database(sessions, str(SEED_PATH))
    assert stats2["profiles"] == 0, f"二次导入应跳过画像，实际: {stats2}"
    assert stats2["paths"] == 0, f"二次导入应跳过路径，实际: {stats2}"
    assert stats2["skipped"] >= 5

    # 验证数据完整性
    from backend.app.repositories.profile_repo import ProfileRepository
    from backend.app.repositories.path_repo import LearningPathRepository
    from backend.app.repositories.assessment_repo import AssessmentRepository

    profile_repo = ProfileRepository(sessions)
    path_repo = LearningPathRepository(sessions)
    assessment_repo = AssessmentRepository(sessions)

    # 画像：5 个学生都有数据
    for uid in [
        "demo-student-1",
        "demo-student-2",
        "demo-student-3",
        "demo-student-4",
        "demo-student-5",
    ]:
        profile = profile_repo.get(uid)
        assert profile, f"{uid} 画像缺失"
        assert len(profile) >= 6, f"{uid} 画像维度不足: {len(profile)}"

    # 路径：每个学生至少 1 条
    for uid in [
        "demo-student-1",
        "demo-student-2",
        "demo-student-3",
        "demo-student-4",
        "demo-student-5",
    ]:
        paths = path_repo.list(user_id=uid)
        assert len(paths) >= 1, f"{uid} 学习路径缺失"

    # 评估：demo-student-1 有 quiz 评估
    summary = assessment_repo.summary("demo-student-1")
    assert summary["total_sessions"] >= 2
    assert summary["quiz_avg_score"] > 0
