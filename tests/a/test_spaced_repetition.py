"""Plan D · 3.3 — spaced_repetition 端点测试

覆盖：
* daily 端点（无 due 时返空 + 正常 return items + retention_curve）
* review 端点（加队列 + 多次提交 + 状态更新）
* stats 端点
* schedule 端点（404 处理）
* enqueue 端点
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app

client = TestClient(app)


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture
def user() -> str:
    return "demo-student-1"


@pytest.fixture(autouse=True)
def isolated_algorithm_state(tmp_path, monkeypatch):
    """Keep endpoint tests from writing schedules/events into the demo DB."""
    from backend.app.api.v1 import spaced_repetition
    from backend.app.core import database
    from backend.app.services.spaced_repetition.sm2 import SM2

    engine = create_engine(f"sqlite:///{tmp_path / 'spaced-repetition.db'}")
    database.Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    model = SM2()

    monkeypatch.setattr(spaced_repetition, "get_sm2", lambda: model)
    monkeypatch.setattr(database, "SessionLocal", sessions)


# ============================================================
# 路由 + 端点基础
# ============================================================
class TestSpacedRepetitionEndpoints:
    def test_endpoint_registered(self):
        """5 个端点都已注册"""
        routes = {
            r.path
            for r in app.routes
            if hasattr(r, "path") and "/spaced-repetition" in r.path
        }
        for expected in (
            "/api/v1/spaced-repetition/daily/{user_id}",
            "/api/v1/spaced-repetition/review",
            "/api/v1/spaced-repetition/stats/{user_id}",
            "/api/v1/spaced-repetition/schedule/{user_id}/{item_id}",
            "/api/v1/spaced-repetition/enqueue",
        ):
            assert expected in routes, f"missing route: {expected}"

    def test_daily_returns_structure(self, user):
        r = client.get(f"/api/v1/spaced-repetition/daily/{user}?limit=10")
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == user
        assert "total_due" in body
        assert "stats" in body
        assert "algorithm" in body
        assert "items" in body
        # 主力算法目前是 SM2
        assert body["algorithm"] == "sm2"

    def test_daily_invalid_limit_returns_422(self, user):
        r = client.get(f"/api/v1/spaced-repetition/daily/{user}?limit=999")
        assert r.status_code == 422

    def test_stats(self, user):
        r = client.get(f"/api/v1/spaced-repetition/stats/{user}")
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == user
        assert "total_items" in body
        assert "due_today" in body
        assert "due_item_count" in body
        assert "average_easiness" in body


# ============================================================
# Review 流
# ============================================================
class TestReviewFlow:
    def test_enqueue_first_then_review(self, user):
        """先把一条加入复习队列，然后评分"""
        # 1) enqueue
        r = client.post(
            "/api/v1/spaced-repetition/enqueue",
            json={"user_id": user, "item_id": "test_kp_001"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "enqueued"

        # 2) review with quality=5
        r2 = client.post(
            "/api/v1/spaced-repetition/review",
            json={"user_id": user, "item_id": "test_kp_001", "quality": 5},
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body["quality"] == 5
        assert body["state"]["repetitions"] >= 1
        # 间隔按 quality>=3 算法递增
        assert body["state"]["interval"] >= 1

    def test_review_low_quality_resets_interval(self, user):
        """quality < 3 应重置 repetitions = 0, interval = 1"""
        client.post(
            "/api/v1/spaced-repetition/enqueue",
            json={"user_id": user, "item_id": "test_kp_002"},
        )
        # 先 quality=5 走通
        client.post(
            "/api/v1/spaced-repetition/review",
            json={"user_id": user, "item_id": "test_kp_002", "quality": 5},
        )
        # 再 quality=0 重置
        r = client.post(
            "/api/v1/spaced-repetition/review",
            json={"user_id": user, "item_id": "test_kp_002", "quality": 0},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["state"]["repetitions"] == 0
        assert body["state"]["interval"] == 1

    def test_schedule_endpoint(self, user):
        client.post(
            "/api/v1/spaced-repetition/enqueue",
            json={"user_id": user, "item_id": "test_kp_003"},
        )
        r = client.get(
            f"/api/v1/spaced-repetition/schedule/{user}/test_kp_003",
        )
        assert r.status_code == 200
        body = r.json()
        assert "state" in body
        assert "easiness" in body["state"]

    def test_schedule_not_found_returns_404(self, user):
        r = client.get(
            f"/api/v1/spaced-repetition/schedule/{user}/nonexistent_kp",
        )
        assert r.status_code == 404


# ============================================================
# 数据契约（关键字段必存在）
# ============================================================
class TestDataContracts:
    def test_daily_item_includes_backend_knowledge_point_and_question(self, user):
        client.post(
            "/api/v1/spaced-repetition/enqueue",
            json={"user_id": user, "item_id": "AI_006_03"},
        )

        body = client.get(f"/api/v1/spaced-repetition/daily/{user}?limit=20").json()
        item = next(it for it in body["items"] if it["item_id"] == "AI_006_03")

        assert item["knowledge_point"]["name"] == "Transformer与注意力机制"
        assert item["question"]["id"].startswith("q-")
        assert item["question"]["stem"]
        assert item["question"]["options"]
        assert "answer" not in item["question"]

    def test_daily_items_have_required_fields(self, user):
        # 加几个测试项确保 daily 返回结构稳定
        for i in range(3):
            client.post(
                "/api/v1/spaced-repetition/enqueue",
                json={"user_id": user, "item_id": f"contract_kp_{i}"},
            )
            client.post(
                "/api/v1/spaced-repetition/review",
                json={"user_id": user, "item_id": f"contract_kp_{i}", "quality": 4},
            )

        r = client.get(f"/api/v1/spaced-repetition/daily/{user}?limit=20")
        body = r.json()
        items = body["items"]
        for it in items:
            assert "item_id" in it
            assert "easiness" in it
            assert "interval_days" in it
            assert "repetitions" in it
            # retention_curve 是 nested dict
            assert "retention_curve" in it
            rc = it["retention_curve"]
            assert isinstance(rc, dict)
            # 至少含 3 个检查点
            assert len(rc) >= 3
