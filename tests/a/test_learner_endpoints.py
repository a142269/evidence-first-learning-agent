"""learner 视角端点 + reverse-plan 测试（7/9 优化：补齐前端既有调用的 404 端点）

覆盖:
    1. POST /cognitive/reverse-plan — 可达 / 不可达 / 目标已达成三分支
    2. GET  /learner/learning_path  — 无路径兜底 + 教师推送路径后可查
    3. GET  /learner/mastery_history — 无数据兜底 + BKT 更新后按日聚合
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app_client(tmp_path_factory) -> TestClient:
    from backend.app.core.database import configure_database, init_db

    db_path = tmp_path_factory.mktemp("learner") / "learner.db"
    configure_database(f"sqlite:///{db_path.as_posix()}")
    init_db()

    from backend.app.main import app
    client = TestClient(app)
    token = client.post("/api/v1/auth/login", json={
        "account": "teacher", "password": "123456",
    }).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


class TestReversePlan:
    def test_achievable(self, app_client: TestClient):
        r = app_client.post("/api/v1/cognitive/reverse-plan", json={
            "current_mastery": 0.3, "target_mastery": 0.7, "horizon_days": 14,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "achievable"
        assert data["daily_questions"] >= 1
        assert data["projected_mastery"] >= 0.7
        assert data["current_mastery"] == 0.3

    def test_already_reached(self, app_client: TestClient):
        r = app_client.post("/api/v1/cognitive/reverse-plan", json={
            "current_mastery": 0.9, "target_mastery": 0.8, "horizon_days": 14,
        })
        data = r.json()
        assert data["status"] == "achievable"
        assert data["daily_questions"] == 0

    def test_unreachable(self, app_client: TestClient):
        r = app_client.post("/api/v1/cognitive/reverse-plan", json={
            "current_mastery": 0.05, "target_mastery": 0.99, "horizon_days": 1,
        })
        data = r.json()
        assert data["status"] == "unreachable"
        assert data["daily_questions"] is None


class TestLearnerPath:
    def test_no_path_fallback(self, app_client: TestClient):
        r = app_client.get("/api/v1/learner/learning_path", params={
            "user_id": "learner-empty", "course": "artificial_intelligence",
        })
        assert r.status_code == 200
        assert r.json()["path"] == []

    def test_path_after_teacher_assign(self, app_client: TestClient):
        app_client.post("/api/v1/teacher/assignments/path", json={
            "user_id": "learner-p1",
            "title": "图谱叠加测试路径",
            "stages": ["线性回归", "神经网络"],
        })
        r = app_client.get("/api/v1/learner/learning_path", params={
            "user_id": "learner-p1", "course": "artificial_intelligence",
        })
        data = r.json()
        assert data["title"] == "图谱叠加测试路径"
        assert [p["name"] for p in data["path"]] == ["线性回归", "神经网络"]
        assert [p["order"] for p in data["path"]] == [1, 2]
        assert data["current_index"] == 0


class TestMasteryHistory:
    def test_no_data_fallback(self, app_client: TestClient):
        r = app_client.get("/api/v1/learner/mastery_history", params={
            "user_id": "learner-empty", "kp_id": "kp_none", "days": 30,
        })
        assert r.status_code == 200
        assert r.json()["history"] == []

    def test_history_after_bkt_updates(self, app_client: TestClient):
        for correct in (True, True, False):
            app_client.post("/api/v1/cognitive/bkt/update", json={
                "user_id": "learner-h1", "kp_id": "kp_test_hist", "correct": correct,
            })
        r = app_client.get("/api/v1/learner/mastery_history", params={
            "user_id": "learner-h1", "kp_id": "kp_test_hist", "days": 30,
        })
        data = r.json()
        assert data["kp_id"] == "kp_test_hist"
        assert len(data["history"]) >= 1
        today = data["history"][-1]
        # 三次答题都发生在今天 → 聚到同一天
        assert today["attempts"] == 3
        assert today["correct"] == 2
        assert 0.0 < today["mastery"] <= 1.0
        assert len(today["date"]) == 10  # YYYY-MM-DD
