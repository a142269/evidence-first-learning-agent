"""
KG 邻居推荐 API 测试 — B 竞赛增强计划 T2.3

验证 GET /api/v1/knowledge-graph/neighbors 端点。
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import configure_database, init_db
from backend.app.core import models  # noqa: F401


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



def _seed_kg_with_neighbors():
    """灌入中心节点 + 2 个邻居 + 关系。"""
    from backend.app.services.knowledge_graph.store import get_kg_store
    store = get_kg_store()
    store.upsert_kp("kp_cnn", "卷积神经网络", course="ai", bloom_level="understand")
    store.upsert_kp("kp_rnn", "循环神经网络", course="ai", bloom_level="understand")
    store.upsert_kp("kp_transformer", "Transformer", course="ai", bloom_level="apply")
    store.add_relation("kp_cnn", "kp_rnn", "prerequisite", weight=0.8)
    store.add_relation("kp_cnn", "kp_transformer", "prerequisite", weight=0.6)


class TestKGNeighborsAPI:
    def test_neighbors_by_kp_id(self, client):
        _seed_kg_with_neighbors()
        resp = client.get("/api/v1/knowledge-graph/neighbors?kp=kp_cnn&depth=2&direction=prereq")
        assert resp.status_code == 200
        data = resp.json()
        assert data["center_kp"] == "kp_cnn"
        assert data["direction"] == "prereq"
        recs = data["recommended"]
        assert len(recs) >= 2
        names = {r["name"] for r in recs}
        assert "循环神经网络" in names
        assert "Transformer" in names

    def test_neighbors_by_name(self, client):
        _seed_kg_with_neighbors()
        resp = client.get("/api/v1/knowledge-graph/neighbors?kp=卷积神经网络&depth=2&direction=prereq")
        assert resp.status_code == 200
        data = resp.json()
        assert data["center_kp"] == "kp_cnn"
        assert data["total"] >= 2

    def test_neighbors_sort_by_weight(self, client):
        _seed_kg_with_neighbors()
        resp = client.get("/api/v1/knowledge-graph/neighbors?kp=kp_cnn&depth=2&direction=prereq")
        data = resp.json()
        recs = data["recommended"]
        weights = [r["relation_path"][0]["weight"] for r in recs if r["relation_path"]]
        assert weights == sorted(weights, reverse=True)

    def test_neighbors_not_found(self, client):
        resp = client.get("/api/v1/knowledge-graph/neighbors?kp=nonexistent_kp&depth=2")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert data["error"] == "kp_not_found"
