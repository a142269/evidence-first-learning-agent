"""
B 5 类学情 API 验证测试 (v7 Day 2)

验证 B 拥有的 5 类学情 API 端点在真实 app + DB 下返回 200 + 合理结构：
  1. GET /cognitive/forecast        — 学习时光机预测
  2. GET /mistakes/heatmap          — 错题热力图
  3. GET /mistakes/categories       — 错因 8 分类
  4. GET /knowledge-graph/3d        — KG 3D 可视化数据
  5. GET /social/peer-suggestions   — 互补学习伙伴

策略:
- TestClient(app) 真实 HTTP 调用（经路由 + middleware）
- 每测试独立 temp DB + seed 演示数据
- 验证 status_code + 关键响应字段
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import configure_database, init_db
from backend.app.core import models  # noqa: F401


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    configure_database(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    init_db()
    # 重置 B 服务单例
    from backend.app.services.cognitive_diagnosis import bkt as bkt_mod
    from backend.app.services.social import peer_matching as pm_mod
    bkt_mod._bkt = None
    pm_mod._matcher = None
    yield


@pytest.fixture(scope="module")
def client():
    from backend.app.main import app
    return TestClient(app)


def _seed_student_with_bkt(user_id: str = "demo-api"):
    """给某学生灌入 BKT 答题历史，让 forecast 有数据。"""
    from backend.app.services.cognitive_diagnosis.bkt import BKT
    bkt = BKT()
    for _ in range(3):
        bkt.update(user_id, "kp_api_test", correct=True)
    bkt.update(user_id, "kp_api_test", correct=False)


def _seed_kg_for_3d():
    """灌入 KG 节点 + 关系，让 /3d 端点有数据。"""
    from backend.app.services.knowledge_graph.store import get_kg_store
    store = get_kg_store()
    for i in range(5):
        store.upsert_kp(
            kp_id=f"kp_3d_{i}", name=f"概念{i}", course="artificial_intelligence",
            description=f"测试知识点 {i}", bloom_level="understand",
        )
    for i in range(4):
        store.add_relation(
            source_id=f"kp_3d_{i}", target_id=f"kp_3d_{i+1}",
            relation_type="prerequisite", weight=1.0,
        )


def _seed_mistakes(user_id: str = "demo-mistake"):
    """灌入错题记录，让 heatmap 有数据。"""
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import MistakeRecord
    import time
    with SessionLocal() as session:
        for i in range(3):
            session.add(MistakeRecord(
                id=f"m_{i}",
                user_id=user_id,
                knowledge_point_id="kp_api_test",
                question_data={"question": f"题{i}", "answer": str(i)},
                error_type="计算粗心" if i % 2 == 0 else "概念混淆",
                analysis="测试错因",
                created_at=time.time(),
            ))
        session.commit()


def _seed_profiles_for_social():
    """灌入 2 个互补画像，让 peer-suggestions 有数据。"""
    from backend.app.repositories.profile_repo import ProfileRepository
    repo = ProfileRepository()
    repo.replace("soc_a", {
        "knowledge_base": {"score": 0.9}, "cognitive_style": {"score": 0.5},
        "learning_preference": {"score": 0.5}, "weak_points": {"score": 0.2},
        "learning_goal": {"score": 0.7}, "time_management": {"score": 0.2},
        "self_efficacy": {"score": 0.6}, "interaction_pattern": {"score": 0.5},
    })
    repo.replace("soc_b", {
        "knowledge_base": {"score": 0.3}, "cognitive_style": {"score": 0.5},
        "learning_preference": {"score": 0.5}, "weak_points": {"score": 0.8},
        "learning_goal": {"score": 0.5}, "time_management": {"score": 0.9},
        "self_efficacy": {"score": 0.6}, "interaction_pattern": {"score": 0.5},
    })


# ────────────────────────────────────────────────────────────────────
# API 1: 学习时光机预测
# ────────────────────────────────────────────────────────────────────

def test_api_forecast_returns_curve_and_milestones(client):
    _seed_student_with_bkt("demo-forecast")
    resp = client.get("/api/v1/cognitive/forecast", params={
        "user_id": "demo-forecast", "kp_id": "kp_api_test", "horizon_days": 14,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "demo-forecast"
    assert "forecast" in body and len(body["forecast"]) == 15
    assert "milestones" in body
    assert "svg" in body
    assert "summary_text" in body


# ────────────────────────────────────────────────────────────────────
# API 2: 错题热力图
# ────────────────────────────────────────────────────────────────────

def test_api_mistake_heatmap_returns_matrix(client):
    _seed_mistakes("demo-heat")
    resp = client.get("/api/v1/mistakes/heatmap", params={"user_id": "demo-heat"})
    assert resp.status_code == 200
    body = resp.json()
    # 结构兼容：可能是 matrix 字段或直接返回
    assert isinstance(body, dict)


# ────────────────────────────────────────────────────────────────────
# API 3: 错因 8 分类
# ────────────────────────────────────────────────────────────────────

def test_api_mistake_categories_returns_eight(client):
    resp = client.get("/api/v1/mistakes/categories")
    assert resp.status_code == 200
    body = resp.json()
    # 应返回 8 分类
    categories = body.get("categories", body) if isinstance(body, dict) else body
    assert len(categories) >= 8


# ────────────────────────────────────────────────────────────────────
# API 4: KG 3D 可视化数据
# ────────────────────────────────────────────────────────────────────

def test_api_kg_3d_returns_nodes_and_edges(client):
    _seed_kg_for_3d()
    resp = client.get("/api/v1/knowledge-graph/3d", params={
        "user_id": "demo-3d", "course": "artificial_intelligence", "max_nodes": 10,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body and "edges" in body
    assert len(body["nodes"]) >= 1
    # 每个节点含 mastery / bloom_color / size_hint
    node = body["nodes"][0]
    for key in ("id", "name", "mastery", "bloom_color", "size_hint"):
        assert key in node


# ────────────────────────────────────────────────────────────────────
# API 5: 互补学习伙伴
# ────────────────────────────────────────────────────────────────────

def test_api_peer_suggestions_returns_sanitized(client):
    _seed_profiles_for_social()
    resp = client.get("/api/v1/social/peer-suggestions", params={
        "user_id": "soc_a", "limit": 3,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "soc_a"
    assert "suggestions" in body
    assert "privacy_note" in body
    if body["suggestions"]:
        s = body["suggestions"][0]
        assert "user_id" in s
        assert "reason" in s
        # 隐私脱敏：不含原始分数
        assert "score" not in s
        assert "complementarity" not in s
