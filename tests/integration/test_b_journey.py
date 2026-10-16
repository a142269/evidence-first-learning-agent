"""
B 学情流水线端到端集成测试 (v7 Day 1)

验证 B 拥有的学情评估完整链路可在真实 DB + 真实服务对象下跑通：
    1. DINA 拟合 → slip/guess/mastery 估计
    2. BKT 增量更新 → P(L) 上升
    3. SM-2 调度 → 间隔重复队列
    4. Peer Matching → 互补推荐
    5. 时光机预测 → 30 天曲线 + 里程碑

策略:
- 每个测试用独立 temp DB (configure_database + init_db)
- 用真实 service 单例（重置单例缓存）
- 不打真实 LLM API
- 覆盖 happy path + 关键状态变化
"""
from __future__ import annotations

import pytest

from backend.app.core.database import configure_database, init_db, SessionLocal
from backend.app.core import models  # noqa: F401


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    """Per-test temp SQLite — 完全隔离，不污染开发库。"""
    db_path = tmp_path / "b_journey.db"
    configure_database(f"sqlite:///{db_path.as_posix()}")
    init_db()
    # 重置 B 服务单例，确保从新 DB 起步
    from backend.app.services.cognitive_diagnosis import bkt as bkt_mod
    from backend.app.services.cognitive_diagnosis import dina as dina_mod
    from backend.app.services.spaced_repetition import sm2 as sm2_mod
    from backend.app.services.social import peer_matching as pm_mod
    bkt_mod._bkt = None
    dina_mod._dina = None
    sm2_mod._sm2 = None
    pm_mod._matcher = None
    yield


# ────────────────────────────────────────────────────────────────────
# Journey 1: DINA 拟合 → slip/guess/mastery 估计
# ────────────────────────────────────────────────────────────────────

def test_dina_fit_produces_slip_guess_and_mastery():
    """DINA EM 在小规模数据上能跑通并产出合理参数。"""
    from backend.app.services.cognitive_diagnosis.dina import DINA

    # 3 学生 × 3 题 × 2 知识点
    items = [
        {"item_id": 1, "kp_ids": ["kp_a"]},
        {"item_id": 2, "kp_ids": ["kp_b"]},
        {"item_id": 3, "kp_ids": ["kp_a", "kp_b"]},
    ]
    responses = {
        1: {1: 1, 2: 0, 3: 1},   # 掌握 a 不掌握 b
        2: {1: 0, 2: 1, 3: 0},   # 掌握 b 不掌握 a
        3: {1: 1, 2: 1, 3: 1},   # 都掌握
    }
    dina = DINA(max_iter=50)
    dina.fit(
        responses=responses,
        q_matrix=dina.build_q_matrix(items, ["kp_a", "kp_b"]),
        item_ids=[1, 2, 3],
        kp_ids=["kp_a", "kp_b"],
    )
    # 拟合后 slip/guess 在合理范围 [0, 0.5]
    for j in [1, 2, 3]:
        assert 0.0 <= dina.slip_.get(j, 0.1) <= 0.5
        assert 0.0 <= dina.guess_.get(j, 0.2) <= 0.5
    # 学生 3（全对）对两个知识点 mastery 都应较高
    assert dina.alpha_.get(3, {}).get("kp_a", 0) >= 0.5
    assert dina.alpha_.get(3, {}).get("kp_b", 0) >= 0.5


# ────────────────────────────────────────────────────────────────────
# Journey 2: BKT 增量更新 → P(L) 随答对上升
# ────────────────────────────────────────────────────────────────────

def test_bkt_update_increases_mastery_on_correct_answers():
    """连续答对后 P(L) 应单调上升。"""
    from backend.app.services.cognitive_diagnosis.bkt import BKT

    bkt = BKT()
    p0 = bkt.update("s1", "kp_x", correct=True)
    p1 = bkt.update("s1", "kp_x", correct=True)
    p2 = bkt.update("s1", "kp_x", correct=True)
    assert p0 < p1 < p2
    assert p2 > 0.5  # 三次答对后应过半
    # get_mastery 查询一致
    assert abs(bkt.get_mastery("s1", "kp_x") - p2) < 1e-9


def test_bkt_trend_detected_after_sequence():
    """连续答对 → improving 趋势。"""
    from backend.app.services.cognitive_diagnosis.bkt import BKT

    bkt = BKT()
    for _ in range(4):
        bkt.update("s2", "kp_y", correct=True)
    trend = bkt.trend("s2", "kp_y")
    assert trend in ("improving", "stable")


# ────────────────────────────────────────────────────────────────────
# Journey 3: SM-2 调度 → 间隔重复队列
# ────────────────────────────────────────────────────────────────────

def test_sm2_schedule_advances_with_good_reviews():
    """高质量复习 → interval 增长。"""
    from backend.app.services.spaced_repetition.sm2 import SM2

    sm2 = SM2()
    r1 = sm2.review("u1", "item_1", quality=5)
    assert r1["interval"] == 1
    r2 = sm2.review("u1", "item_1", quality=5)
    assert r2["interval"] == 6  # 第二次 6 天
    r3 = sm2.review("u1", "item_1", quality=5)
    assert r3["interval"] > 6   # 第三次 > 6


def test_sm2_resets_on_poor_quality():
    """quality < 3 → 重置 repetitions。"""
    from backend.app.services.spaced_repetition.sm2 import SM2

    sm2 = SM2()
    sm2.review("u1", "item_2", quality=5)
    r = sm2.review("u1", "item_2", quality=1)  # 答得差
    assert r["repetitions"] == 0
    assert r["interval"] == 1


# ────────────────────────────────────────────────────────────────────
# Journey 4: Peer Matching → 互补推荐
# ────────────────────────────────────────────────────────────────────

def test_peer_matching_finds_complementary_partner():
    """有画像的库中能找到互补伙伴。"""
    from backend.app.repositories.profile_repo import ProfileRepository
    from backend.app.services.social.peer_matching import get_peer_matcher

    repo = ProfileRepository()
    repo.replace("alpha", {
        "knowledge_base": {"score": 0.9}, "cognitive_style": {"score": 0.5},
        "learning_preference": {"score": 0.5}, "weak_points": {"score": 0.2},
        "learning_goal": {"score": 0.7}, "time_management": {"score": 0.2},
        "self_efficacy": {"score": 0.6}, "interaction_pattern": {"score": 0.5},
    })
    repo.replace("beta", {
        "knowledge_base": {"score": 0.3}, "cognitive_style": {"score": 0.5},
        "learning_preference": {"score": 0.5}, "weak_points": {"score": 0.8},
        "learning_goal": {"score": 0.5}, "time_management": {"score": 0.9},
        "self_efficacy": {"score": 0.6}, "interaction_pattern": {"score": 0.5},
    })
    peers = get_peer_matcher().find_complementary_peers("alpha", limit=3)
    assert len(peers) >= 1
    assert peers[0]["user_id"] == "beta"
    assert peers[0]["complementarity"] > 0


# ────────────────────────────────────────────────────────────────────
# Journey 5: 时光机预测 → 30 天曲线 + 里程碑
# ────────────────────────────────────────────────────────────────────

def test_forecaster_predicts_30day_curve_with_milestones():
    """30 天预测产出 31 个点 + 里程碑检测。"""
    from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster

    f = BKTForecaster(p_transit=0.2, daily_practice_rate=0.8)
    forecast = f.forecast(current_mastery=0.4, horizon_days=30)
    assert len(forecast) == 31  # day 0..30
    assert forecast[0].p_learned == 0.4
    # 高练习率下 30 天后应有显著增长
    assert forecast[-1].p_learned > 0.4
    # 每个点都有 CI
    for fp in forecast:
        assert 0.0 <= fp.ci_low <= fp.p_learned <= fp.ci_high <= 1.0
    milestones = f.find_milestones(forecast)
    # 80% 里程碑在高练习率下应达成
    assert any(m["target"] == 0.80 for m in milestones) or forecast[-1].p_learned < 0.8


def test_forecaster_reverse_plan_achievable_target():
    """目标倒推：可达目标返回 daily_questions > 0。"""
    from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster

    result = BKTForecaster().reverse_plan(
        current_mastery=0.3, target_mastery=0.85, horizon_days=30,
    )
    assert result["status"] == "achievable"
    assert result["daily_questions"] is not None
    assert result["daily_questions"] >= 1


# ────────────────────────────────────────────────────────────────────
# Journey 6: 完整链路 DINA → BKT → SM-2 串联
# ────────────────────────────────────────────────────────────────────

def test_full_pipeline_dina_to_bkt_to_sm2():
    """一个学生：先 DINA 诊断 → 再用 BKT 跟踪 → 错题入 SM-2 队列。"""
    from backend.app.services.cognitive_diagnosis.dina import DINA
    from backend.app.services.cognitive_diagnosis.bkt import BKT
    from backend.app.services.spaced_repetition.sm2 import SM2

    # 1. DINA 拟合得到初始 mastery
    items = [{"item_id": 1, "kp_ids": ["kp_a"]}]
    responses = {1: {1: 0}, 2: {1: 1}}  # 学生1答错，学生2答对
    dina = DINA(max_iter=30)
    dina.fit(responses, dina.build_q_matrix(items, ["kp_a"]), [1], ["kp_a"])
    initial_mastery = dina.alpha_.get(1, {}).get("kp_a", 0.5)

    # 2. BKT 从 DINA mastery 起步，继续答题跟踪
    bkt = BKT(p_initial=initial_mastery)
    p = bkt.update("student_1", "kp_a", correct=True)
    assert p > initial_mastery  # 答对后上升

    # 3. 错题入 SM-2 队列
    sm2 = SM2()
    sched = sm2.review("student_1", "kp_a::item_1", quality=2)  # 答错
    assert sched["repetitions"] == 0  # quality<3 重置
    assert sched["interval"] == 1


# ────────────────────────────────────────────────────────────────────
# Journey 7: 错题本 8 分类 + 变式题
# ────────────────────────────────────────────────────────────────────

def test_mistake_review_classifies_and_generates_variants():
    from backend.app.services.mistake_review import classify_error, generate_variants

    # 计算粗心：答案数值接近
    result = classify_error(student_answer="8", correct_answer="7")
    assert "error_type" in result
    assert "confidence" in result
    assert result["error_type"] in (
        "知识缺漏", "计算失误", "概念混淆", "阅读理解",
        "审题不清", "方法选择错", "计算粗心", "概念边界混淆",
    )

    # 变式题生成
    variants = generate_variants(
        question="什么是 CNN？",
        correct_answer="卷积神经网络",
        kp_id="kp_cnn",
        kp_name="CNN",
    )
    assert isinstance(variants, list)
    assert len(variants) >= 1
    for v in variants:
        assert "bloom_level" in v and "question" in v


# ────────────────────────────────────────────────────────────────────
# Journey 8: GraphRAG 检索 → KG 邻居
# ────────────────────────────────────────────────────────────────────

def test_graphrag_retrieve_and_kg_neighbors():
    """KG store 能存取知识点 + 关系，邻居查询返回结构化结果。"""
    from backend.app.services.knowledge_graph.store import get_kg_store

    store = get_kg_store()
    store.upsert_kp(kp_id="kp_cnn", name="CNN", course="ai",
                    description="卷积神经网络", bloom_level="understand")
    store.upsert_kp(kp_id="kp_pool", name="池化", course="ai",
                    description="池化层", bloom_level="understand")
    store.add_relation(source_id="kp_cnn", target_id="kp_pool",
                       relation_type="part_of", weight=1.0)

    neighbors = store.get_neighbors("kp_cnn")
    assert isinstance(neighbors, list)
    assert any(n.get("kp_id") == "kp_pool" for n in neighbors)
