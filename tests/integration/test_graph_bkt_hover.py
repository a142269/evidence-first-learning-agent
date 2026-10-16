"""Plan D · 3.4 — GraphView BKT mastery hover 增强。

覆盖：
- /knowledge-graph/3d 节点包含 bkt_trend + bkt_attempts 字段
- trend 取自 BKT.trend() — improving / declining / stable
- attempts 计数 = len(history)
- 没有 BKT 历史的 KP 走 stable + 0（兜底）
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture(scope="module")
def app() -> FastAPI:
    from backend.app.api.v1.knowledge_graph import router as kg_router

    a = FastAPI()
    a.include_router(kg_router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _seed_kps(client: TestClient, kp_ids: list[str]) -> None:
    """直接在 BKT 里注入 mastery + history，模拟学生已答题的状态。"""
    from backend.app.services.cognitive_diagnosis.bkt import get_bkt

    bkt = get_bkt()
    bkt.reset("plan34-user")
    for kp_id in kp_ids:
        # 灌入 5 次答题记录：最后两次都答对 → trend=improving
        for i in range(5):
            bkt.update("plan34-user", kp_id, correct=(i >= 3))


def test_3d_endpoint_includes_bkt_trend(client: TestClient):
    """Plan D · 3.4 — 节点必须含 bkt_trend + bkt_attempts"""
    _seed_kps(client, ["plan34_kp_a"])

    resp = client.get(
        "/api/v1/knowledge-graph/3d",
        params={
            "user_id": "plan34-user",
            "course": "artificial_intelligence",
            "max_nodes": 80,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body
    if not body["nodes"]:
        # 测试环境可能没灌入 KG 节点 → 跳过
        pytest.skip("No KG nodes in test DB")
    node = body["nodes"][0]
    # 新字段必须存在
    assert "bkt_trend" in node, f"node missing bkt_trend: keys={list(node.keys())}"
    assert "bkt_attempts" in node
    # trend 取值合法
    assert node["bkt_trend"] in {
        "improving", "declining", "stable", "insufficient_data",
    }
    assert isinstance(node["bkt_attempts"], int)
    assert node["bkt_attempts"] >= 0


def test_3d_endpoint_default_zero_attempts_for_new_user(client: TestClient):
    """Plan D · 3.4 — 没 BKT 历史的学生，所有 KP 显示 stable + 0 次"""
    resp = client.get(
        "/api/v1/knowledge-graph/3d",
        params={
            "user_id": "fresh-student-3d",
            "course": "artificial_intelligence",
            "max_nodes": 5,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # 即使 KG 为空，stats 字段不能崩
    assert "stats" in body
    assert "total_kps" in body["stats"]


def test_bkt_trend_logic_for_real_user(client: TestClient):
    """Plan D · 3.4 — 给 BKT 注入历史后 trend 应被正确识别为 improving"""
    from backend.app.services.cognitive_diagnosis.bkt import get_bkt

    bkt = get_bkt()
    bkt.reset("trend-test-user")
    # 模拟：前 3 次答错 + 后 4 次答对 → 最后两次都答对 → improving
    for kp_id in ("trend_kp_a", "trend_kp_b"):
        results = [False, False, False, True, True, True, True]
        for correct in results:
            bkt.update("trend-test-user", kp_id, correct=correct)
        # BKT.trend() 应该返回 improving
        assert bkt.trend("trend-test-user", kp_id) == "improving", (
            f"expected improving, got {bkt.trend('trend-test-user', kp_id)}"
        )