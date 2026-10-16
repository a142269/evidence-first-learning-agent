"""Plan D · 3.3 — spaced-repetition 优先级融合 SM2 + BKT

覆盖：
- /daily 端点每条 item 必含 priority_score + priority_reason 字段
- /recommend 端点返回 Top-N（按 priority_score 降序）
- overdue_factor 越大 / mastery 越低 → priority_score 越高
- priority_score 在 [0, 1] 区间
- reason 含中文解释
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from backend.app.api.v1.spaced_repetition import router

    a = FastAPI()
    a.include_router(router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def isolated_sm2(monkeypatch):
    """Priority tests should not persist synthetic learners in the demo DB."""
    from backend.app.services.spaced_repetition import sm2 as sm2_module

    monkeypatch.setattr(sm2_module, "_sm2", sm2_module.SM2())


def _seed_due_with_mastery(user_id: str, kp_ids: list[str], correct: list[bool]) -> None:
    """给 BKT 注入历史，给 SM2 注入 due item（last_review_at=now-N天）"""
    from backend.app.services.cognitive_diagnosis.bkt import get_bkt
    from backend.app.services.spaced_repetition import get_sm2

    bkt = get_bkt()
    bkt.reset(user_id)
    sm2 = get_sm2()
    # SM2 没有 reset，按 user 走
    for kp_id, was_correct in zip(kp_ids, correct):
        # BKT 历史
        for _ in range(3 if was_correct else 5):
            bkt.update(user_id, kp_id, correct=was_correct)
        # SM2 直接走 review 接口，加进队列
        sm2.add_to_review_queue(user_id, kp_id)


class TestDailyEnriched:
    def test_daily_items_have_priority_fields(self, client: TestClient):
        """Plan D · 3.3 — /daily 每条 item 含 priority_score + reason"""
        r = client.get(
            "/api/v1/spaced-repetition/daily/d-priority-user-1",
            params={"limit": 5},
        )
        assert r.status_code == 200
        data = r.json()
        # 用户没数据时 items 是空数组，priority 字段可以不出现
        # 但只要 items 非空，每条都必须含 priority 字段
        for it in data.get("items", []):
            assert "priority_score" in it
            assert "priority_reason" in it
            assert isinstance(it["priority_score"], (int, float))
            assert 0.0 <= it["priority_score"] <= 1.0
            assert isinstance(it["priority_reason"], str)
            assert len(it["priority_reason"]) > 0

    def test_daily_items_sorted_by_priority_desc(self, client: TestClient):
        """Plan D · 3.3 — items 已按 priority_score 从高到低排序"""
        r = client.get(
            "/api/v1/spaced-repetition/daily/d-priority-user-2",
            params={"limit": 20},
        )
        data = r.json()
        scores = [it.get("priority_score", 0) for it in data.get("items", [])]
        if scores:
            assert scores == sorted(scores, reverse=True), (
                f"items not sorted desc: {scores}"
            )


class TestRecommendEndpoint:
    def test_recommend_returns_top_n(self, client: TestClient):
        """Plan D · 3.3 — /recommend 端点 Top-N"""
        r = client.get(
            "/api/v1/spaced-repetition/recommend/d-recommend-user-1",
            params={"limit": 3},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == "d-recommend-user-1"
        assert "recommendations" in data
        assert "total_candidates" in data
        assert "algorithm" in data
        assert isinstance(data["recommendations"], list)
        assert len(data["recommendations"]) <= 3
        for rec in data["recommendations"]:
            assert "item_id" in rec
            assert "priority_score" in rec
            assert "reason" in rec
            assert 0.0 <= rec["priority_score"] <= 1.0
            assert isinstance(rec["reason"], str)

    def test_recommend_limit_validation(self, client: TestClient):
        """Plan D · 3.3 — limit 在 [1, 10] 区间"""
        # limit=0 应被拒绝
        r = client.get(
            "/api/v1/spaced-repetition/recommend/d-user-x",
            params={"limit": 0},
        )
        assert r.status_code == 422
        # limit=11 应被拒绝
        r = client.get(
            "/api/v1/spaced-repetition/recommend/d-user-x",
            params={"limit": 11},
        )
        assert r.status_code == 422


class TestPriorityScoring:
    def test_compute_review_priority_low_mastery_high_score(self):
        """Plan D · 3.3 — 掌握度低 + 已逾期 → 分数高"""
        from backend.app.api.v1.spaced_repetition import _compute_review_priority
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt
        from backend.app.services.spaced_repetition import get_sm2

        user_id = "d-calc-low"
        bkt = get_bkt()
        bkt.reset(user_id)
        # 全部答错 → mastery 低
        for _ in range(8):
            bkt.update(user_id, "low_kp", correct=False)
        sm2 = get_sm2()
        sm2.add_to_review_queue(user_id, "low_kp")
        state = sm2.get_schedule(user_id, "low_kp") or {}
        # next_review_at 改成 5 天前 → overdue_factor 高
        state["next_review_at"] = time.time() - 5 * 86400
        score, reason = _compute_review_priority(user_id, state)
        assert score >= 0.4, f"low mastery + overdue should be high, got {score}"
        assert "逾期" in reason or "BKT" in reason

    def test_compute_review_priority_high_mastery_low_score(self):
        """Plan D · 3.3 — 掌握度高 + 未逾期 → 分数低"""
        from backend.app.api.v1.spaced_repetition import _compute_review_priority
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt
        from backend.app.services.spaced_repetition import get_sm2

        user_id = "d-calc-high"
        bkt = get_bkt()
        bkt.reset(user_id)
        # 全部答对 → mastery 高
        for _ in range(8):
            bkt.update(user_id, "high_kp", correct=True)
        sm2 = get_sm2()
        sm2.add_to_review_queue(user_id, "high_kp")
        state = sm2.get_schedule(user_id, "high_kp") or {}
        # next_review_at 是未来 → overdue_factor 接近 0
        state["next_review_at"] = time.time() + 86400
        score, reason = _compute_review_priority(user_id, state)
        assert score < 0.4, f"high mastery + not overdue should be low, got {score}"

    def test_priority_score_in_unit_interval(self):
        """Plan D · 3.3 — priority_score 永远在 [0, 1]"""
        from backend.app.api.v1.spaced_repetition import _compute_review_priority

        for offset_days in [-30, -1, 0, 1, 30]:
            state = {
                "item_id": "t",
                "easiness": 2.5,
                "interval": 1,
                "repetitions": 0,
                "next_review_at": time.time() + offset_days * 86400,
            }
            score, _ = _compute_review_priority("d-bounds-user", state)
            assert 0.0 <= score <= 1.0, f"out of range at {offset_days}d: {score}"
