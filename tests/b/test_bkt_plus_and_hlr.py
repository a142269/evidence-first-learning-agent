"""Tests for BKT+ per-student parameters (T2.6) and HLR / three-way comparison (T2.5).

覆盖场景：
- BKT+ 参数拟合不崩溃
- BKT+ 预测在 [0,1] 范围内
- BKT+ 参数摘要
- HLR 半衰期预测
- HLR 拟合
- 三方对照报告生成
"""
from __future__ import annotations

import pytest

from backend.app.services.cognitive_diagnosis.bkt_plus import BKTPlus, bkt_plus_adapter_fit
from backend.app.services.spaced_repetition.hlr import HLRModel, sm2_vs_fsrs_vs_hlr_report


# ─── BKT+ tests ──────────────────────────────────────

def test_bkt_plus_fit_and_predict():
    """BKT+ 应能拟合数据并输出合理预测。"""
    data = {
        "s1": [
            {"skill_id": "kp1", "correct": 0, "timestamp": 1},
            {"skill_id": "kp1", "correct": 0, "timestamp": 2},
            {"skill_id": "kp1", "correct": 1, "timestamp": 3},
            {"skill_id": "kp1", "correct": 1, "timestamp": 4},
        ],
        "s2": [
            {"skill_id": "kp1", "correct": 1, "timestamp": 1},
            {"skill_id": "kp1", "correct": 1, "timestamp": 2},
            {"skill_id": "kp2", "correct": 0, "timestamp": 3},
            {"skill_id": "kp2", "correct": 1, "timestamp": 4},
        ],
    }
    model = bkt_plus_adapter_fit(data)
    # Predictions should be in [0,1]
    p1 = model.predict("s1", "kp1", [0, 0, 1])
    p2 = model.predict("s2", "kp2", [0, 1])
    assert 0.0 <= p1 <= 1.0
    assert 0.0 <= p2 <= 1.0
    # Summary should have 2 students and 2 skills
    summary = model.params_summary()
    assert summary["n_students"] == 2
    assert summary["n_skills"] == 2


def test_bkt_plus_params_individual():
    """每个学生应有独立的 L0 / T。"""
    data = {
        "s1": [{"skill_id": "kp1", "correct": 1}] * 10,
        "s2": [{"skill_id": "kp1", "correct": 0}] * 10,
    }
    model = BKTPlus()
    model.fit(data)
    p1 = model.get_params("s1", "kp1")
    p2 = model.get_params("s2", "kp1")
    assert p1["L0"] > p2["L0"]  # s1 had all correct, should have higher L0


# ─── HLR tests ───────────────────────────────────────

def test_hlr_predict_recall():
    """HLR 预测应在 [0,1] 范围内。"""
    hlr = HLRModel()
    p = hlr.predict_recall(n_reviews=5, time_since_last=1.0)
    assert 0.0 <= p <= 1.0
    # 更长的时间应降低记忆概率
    p_later = hlr.predict_recall(n_reviews=5, time_since_last=10.0)
    assert p_later < p


def test_hlr_fit():
    """HLR 拟合不应崩溃且 theta 应有变化。"""
    hlr = HLRModel()
    initial = list(hlr.theta)
    data = [
        {"n_reviews": 1, "time_since_last": 1.0, "recalled": True},
        {"n_reviews": 1, "time_since_last": 10.0, "recalled": False},
        {"n_reviews": 5, "time_since_last": 1.0, "recalled": True},
        {"n_reviews": 5, "time_since_last": 30.0, "recalled": False},
    ] * 10
    hlr.fit(data)
    assert hlr.theta != initial or all(t == 0 for t in initial)


def test_hlr_next_interval():
    """next_interval 应返回正数。"""
    hlr = HLRModel()
    interval = hlr.next_interval(n_reviews=3, target_p=0.9)
    assert interval > 0


# ─── Three-way comparison report ───────────────────────

def test_three_way_report():
    """对照报告应生成结构化数据。"""
    report = sm2_vs_fsrs_vs_hlr_report(n_items=50)
    assert "sm2" in report
    assert "fsrs" in report
    assert "hlr" in report
    assert report["n_items"] == 50
