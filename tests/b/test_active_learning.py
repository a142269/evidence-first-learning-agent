"""Tests for Active Learning uncertainty sampler (T2.2).

覆盖场景：
- 熵计算单调性
- 无状态时的随机回退
- 有 BKT 状态时的熵排序
- 多策略一致性（entropy / margin / least_confident）
- 端点调用
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.services.active_learning.uncertainty_sampler import (
    UncertaintySampler,
    _binary_entropy,
    _bkt_predict_correct,
)
from backend.app.services.question_bank import QuestionBank
from backend.app.core.database import configure_database, init_db
from backend.app.core import models  # noqa: F401


# ─── Helpers ───────────────────────────────────────────

class FakeBank:
    """Minimal fake question bank."""
    def __init__(self, questions):
        self._questions = questions

    def filter(self, kp_id=None, bloom=None, **kwargs):
        qs = self._questions
        if kp_id:
            qs = [q for q in qs if q.get("kp_id") == kp_id]
        if bloom:
            qs = [q for q in qs if q.get("bloom") == bloom]
        return qs


# ─── Unit tests ────────────────────────────────────────

def test_binary_entropy_extremes():
    """Entropy(0) = 0, Entropy(1) = 0, Entropy(0.5) = max."""
    assert _binary_entropy(0.0) == pytest.approx(0.0, abs=1e-3)
    assert _binary_entropy(1.0) == pytest.approx(0.0, abs=1e-3)
    assert _binary_entropy(0.5) == pytest.approx(1.0, abs=1e-3)
    assert _binary_entropy(0.25) > _binary_entropy(0.1)
    assert _binary_entropy(0.25) > _binary_entropy(0.9)


def test_bkt_predict_correct():
    """BKT 公式正确性校验。"""
    # 完全掌握 + 无 slip = 100% 正确
    assert _bkt_predict_correct(1.0, 0.0, 0.0) == pytest.approx(1.0)
    # 完全未掌握 + 无 guess = 0% 正确
    assert _bkt_predict_correct(0.0, 0.0, 0.0) == pytest.approx(0.0)
    # 50% 掌握，slip=0.1, guess=0.2 → 0.5*0.9 + 0.5*0.2 = 0.55
    assert _bkt_predict_correct(0.5, 0.1, 0.2) == pytest.approx(0.55)


def test_recommend_without_states():
    """无 mastery 状态时，回退为随机采样。"""
    qs = [
        {"id": "q1", "kp_id": "kp1", "bloom": "understand", "question": "Q1"},
        {"id": "q2", "kp_id": "kp1", "bloom": "apply", "question": "Q2"},
        {"id": "q3", "kp_id": "kp2", "bloom": "remember", "question": "Q3"},
    ]
    sampler = UncertaintySampler(bank=FakeBank(qs))
    recs = sampler.recommend("u1", mastery_map={}, top_k=2)
    assert len(recs) == 2
    assert all(r["reason"] == "random_fallback" for r in recs)


def test_recommend_entropy_ranking():
    """有 BKT 状态时，按熵降序排列（越接近 0.5 越靠前）。"""
    qs = [
        {"id": "q1", "kp_id": "kp_a", "bloom": "understand", "question": "Q1"},
        {"id": "q2", "kp_id": "kp_b", "bloom": "understand", "question": "Q2"},
        {"id": "q3", "kp_id": "kp_c", "bloom": "understand", "question": "Q3"},
    ]
    sampler = UncertaintySampler(bank=FakeBank(qs))
    # mastery: kp_a=0.5 (max entropy), kp_b=0.9 (low entropy), kp_c=0.1 (low entropy)
    mastery = {"kp_a": 0.5, "kp_b": 0.9, "kp_c": 0.1}
    params = {
        "kp_a": {"slip": 0.1, "guess": 0.2},
        "kp_b": {"slip": 0.1, "guess": 0.2},
        "kp_c": {"slip": 0.1, "guess": 0.2},
    }
    recs = sampler.recommend("u1", mastery_map=mastery, param_map=params, top_k=3)
    assert len(recs) == 3
    # 最高熵应在第一位
    assert recs[0]["kp_id"] == "kp_a"
    # 熵值随排名递减
    scores = [r["score"] for r in recs]
    assert scores[0] > scores[1]
    assert scores[1] > scores[2]


def test_recommend_strategy_margin():
    """margin 策略下，kp_a (0.5) 仍应最靠前。"""
    qs = [
        {"id": "q1", "kp_id": "kp_a", "bloom": "understand", "question": "Q1"},
        {"id": "q2", "kp_id": "kp_b", "bloom": "understand", "question": "Q2"},
    ]
    sampler = UncertaintySampler(bank=FakeBank(qs))
    mastery = {"kp_a": 0.5, "kp_b": 0.9}
    params = {"kp_a": {"slip": 0.1, "guess": 0.2}, "kp_b": {"slip": 0.1, "guess": 0.2}}
    recs = sampler.recommend("u1", mastery_map=mastery, param_map=params, strategy="margin", top_k=2)
    assert recs[0]["kp_id"] == "kp_a"


# ─── API tests ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    db_path = tmp_path / "test.db"
    configure_database(f"sqlite:///{db_path}")
    init_db()
    yield


@pytest.fixture
def client(_isolated_db):
    from backend.app.main import app
    return TestClient(app)



class TestActiveLearningAPI:
    def test_graph_kp_filter_maps_to_real_question_bank_id(self, client):
        """图谱 AI_015 应映射到题库 multimodal_llm，并回写原图谱知识点。"""
        from backend.app.services.cognitive_diagnosis.state_repository import get_state_repo

        get_state_repo().save_bkt_state(
            "demo-multimodal",
            "AI_015",
            {
                "p_learned": 0.743,
                "p_transit": 0.1,
                "p_slip": 0.1,
                "p_guess": 0.2,
                "history": [],
            },
        )

        resp = client.post(
            "/api/v1/cognitive/next-best-question"
            "?user_id=demo-multimodal&kp_id=AI_015&top_k=3"
        )
        assert resp.status_code == 200
        recommendations = resp.json()["recommendations"]
        assert recommendations
        assert all(item["kp_id"] == "AI_015" for item in recommendations)
        assert all(item["question"]["kp_id"] == "AI_015" for item in recommendations)
        assert all(item["question"]["bank_kp_id"] == "multimodal_llm" for item in recommendations)

    def test_next_best_question_no_data(self, client):
        """没有 BKT/DINA 状态时，返回随机回退。"""
        resp = client.post("/api/v1/cognitive/next-best-question?user_id=demo-u1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "demo-u1"
        assert data["strategy"] == "entropy"
        assert data["based_on"] == "random"
        assert len(data["recommendations"]) == 5

    def test_next_best_question_with_bkt_state(self, client):
        """存入 BKT 状态后，推荐应基于熵排序。"""
        from backend.app.services.cognitive_diagnosis.state_repository import get_state_repo

        repo = get_state_repo()
        repo.save_bkt_state(
            "demo-u1",
            "kp_cnn",
            {
                "p_learned": 0.5,
                "p_transit": 0.1,
                "p_slip": 0.1,
                "p_guess": 0.2,
                "history": [],
            },
        )
        repo.save_bkt_state(
            "demo-u1",
            "kp_rnn",
            {
                "p_learned": 0.9,
                "p_transit": 0.1,
                "p_slip": 0.1,
                "p_guess": 0.2,
                "history": [],
            },
        )

        resp = client.post("/api/v1/cognitive/next-best-question?user_id=demo-u1&top_k=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["based_on"] == "bkt"
        recs = data["recommendations"]
        assert len(recs) == 2
        # kp_cnn (0.5) 熵更大，应排在前面
        cnn_scores = [r for r in recs if r.get("kp_id") == "kp_cnn"]
        rnn_scores = [r for r in recs if r.get("kp_id") == "kp_rnn"]
        if cnn_scores and rnn_scores:
            assert cnn_scores[0]["score"] > rnn_scores[0]["score"]

    def test_next_best_question_kp_filter(self, client):
        """kp_id 过滤应只返回该知识点下的题。"""
        resp = client.post("/api/v1/cognitive/next-best-question?user_id=demo-u1&kp_id=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendations"] == []
