"""
错题归因 API 测试 — B 竞赛增强计划 T1.2 (B 端)

验证 GET /api/v1/mistakes/{id}/attribution 端点。
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import configure_database, init_db
from backend.app.core import models  # noqa: F401


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    init_db()
    yield


@pytest.fixture
def client(_isolated_db):
    from backend.app.main import app
    return TestClient(app)



def _record_mistake(client, user_id="demo") -> str:
    """录入一条错题，返回 mistake_id。"""
    resp = client.post(
        "/api/v1/mistakes/record",
        json={
            "user_id": user_id,
            "kp_id": "kp_cnn",
            "question": "CNN 的池化层作用是什么？",
            "student_answer": "提取特征",
            "correct_answer": "降低维度、减少计算量、防止过拟合",
            "error_type": "概念混淆",
        },
    )
    assert resp.status_code == 200
    return resp.json()["mistake_id"]


class TestMistakeAttributionAPI:
    def test_attribution_returns_8_categories(self, client):
        mid = _record_mistake(client)
        resp = client.get(f"/api/v1/mistakes/{mid}/attribution")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mistake_id"] == mid
        assert data["category"] in data["all_categories"]
        assert 0.0 <= data["confidence"] <= 1.0
        assert "evidence" in data
        assert "source" in data


    def test_attribution_recommended_bloom(self, client):
        mid = _record_mistake(client)
        resp = client.get(f"/api/v1/mistakes/{mid}/attribution")
        data = resp.json()
        bloom = data["recommended_bloom_level"]
        assert bloom in ["remember", "understand", "apply", "analyze", "evaluate", "create"]

    def test_attribution_remediation_advice(self, client):
        mid = _record_mistake(client)
        resp = client.get(f"/api/v1/mistakes/{mid}/attribution")
        data = resp.json()
        assert "remediation_advice" in data
        assert len(data["remediation_advice"]) > 5

    def test_attribution_not_found(self, client):
        resp = client.get("/api/v1/mistakes/nonexistent/attribution")
        assert resp.status_code == 404
