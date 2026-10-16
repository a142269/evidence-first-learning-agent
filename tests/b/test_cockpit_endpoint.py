"""
Cockpit 聚合端点测试 — B 竞赛增强计划 B.3

验证 GET /api/v1/cockpit/student/{user_id} 端点。
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import configure_database, init_db
from backend.app.core import models  # noqa: F401


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    db_path = tmp_path / "test_cockpit.db"
    configure_database(f"sqlite:///{db_path}")
    init_db()
    yield


@pytest.fixture
def client(_isolated_db):
    from backend.app.main import app
    return TestClient(app)


def _seed_profile(user_id: str, knowledge_base: float = 0.7):
    """灌入一个学生画像。"""
    from backend.app.api.v1.profile import _profiles
    _profiles[user_id] = {
        "knowledge_base": knowledge_base,
        "cognitive_style": "visual",
        "learning_preference": "video",
        "weak_points": ["CNN pooling", "RNN gradient"],
        "learning_goal": "exam",
        "self_efficacy": 0.65,
    }


def test_cockpit_demo_student_1(client):
    """demo-student-1 返回 200 + 完整字段。"""
    _seed_profile("demo-student-1")
    resp = client.get("/api/v1/cockpit/student/demo-student-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "demo-student-1"
    assert "generated_at" in data
    assert "profile" in data
    assert "kg" in data
    assert "forecast" in data
    assert "attribution" in data
    assert "cov" in data
    assert "debate" in data


def test_cockpit_demo_student_1_falls_back_to_seed_profile(client):
    """真实 demo 学生在未手工灌 profile 时也应能回退到 seed 数据。"""
    from backend.app.api.v1.profile import _profiles

    _profiles.pop("demo-student-1", None)

    resp = client.get("/api/v1/cockpit/student/demo-student-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "demo-student-1"
    assert data["profile"]["dimensions"]["learning_goals"] == ["多模态理解与 Transformer 工程"]


def test_cockpit_demo_student_2(client):
    """demo-student-2 也能正常返回。"""
    _seed_profile("demo-student-2", knowledge_base=0.45)
    resp = client.get("/api/v1/cockpit/student/demo-student-2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "demo-student-2"
    assert data["profile"]["dimensions"]["knowledge_base"] == 0.45


def test_cockpit_not_found(client):
    """不存在的用户也返回 200，由各子块自行降级。"""
    resp = client.get("/api/v1/cockpit/student/nonexistent-user")
    assert resp.status_code == 200
    data = resp.json()
    assert "profile" in data
    assert "kg" in data


def test_cockpit_profile_radar_6d(client):
    """profile.radar_6d 应该有 6 个元素。"""
    _seed_profile("demo-student-3")
    resp = client.get("/api/v1/cockpit/student/demo-student-3")
    assert resp.status_code == 200
    data = resp.json()
    radar = data["profile"]["radar_6d"]
    assert isinstance(radar, list)
    assert len(radar) == 6
    assert all(isinstance(v, (int, float)) for v in radar)


def test_cockpit_field_completeness(client):
    """所有顶层字段都存在且类型正确。"""
    _seed_profile("demo-student-4")
    resp = client.get("/api/v1/cockpit/student/demo-student-4")
    assert resp.status_code == 200
    data = resp.json()
    # profile
    assert isinstance(data["profile"]["dimensions"], dict)
    assert isinstance(data["profile"]["radar_6d"], list)
    # kg
    assert "current_kp" in data["kg"]
    assert isinstance(data["kg"]["neighbors_2hop"], list)
    # forecast
    assert data["forecast"]["horizon_days"] == 7
    assert isinstance(data["forecast"]["curve"], list)
    # attribution
    assert isinstance(data["attribution"]["latest_mistakes"], list)
    assert isinstance(data["attribution"]["category_distribution"], dict)
    # cov
    assert isinstance(data["cov"]["recent_claims"], list)
    # debate
    assert isinstance(data["debate"]["recent_traces"], list)


def test_cockpit_completeness_excludes_unknown_placeholders(monkeypatch):
    from backend.app.api.v1 import cockpit
    from backend.app.services.profile_schema import normalize_profile

    profile = normalize_profile({
        "knowledge_base": {"level": "middle", "score": 0.6},
    })
    monkeypatch.setattr(cockpit, "_load_profile_record", lambda user_id: profile)

    assert cockpit._fetch_profile("u1")["completeness"] == 12.5


def test_cockpit_schema_uses_learning_goals_list(client):
    """cockpit schema 应暴露计划约定的 learning_goals 列表字段。"""
    _seed_profile("demo-student-5")
    resp = client.get("/api/v1/cockpit/student/demo-student-5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"]["dimensions"]["learning_goals"] == ["exam"]


def test_cockpit_maps_forecast_service_output(client, monkeypatch):
    """forecast 应复用 timemachine_service 的真实字段并映射为 curve/mastery。"""
    _seed_profile("demo-student-6")

    class _FakeTimeMachineService:
        def forecast(self, user_id: str, kp_id: str, horizon_days: int = 7):
            return {
                "forecast": [
                    {"day": 0, "p_learned": 0.42},
                    {"day": 1, "p_learned": 0.55},
                ]
            }

    monkeypatch.setattr(
        "backend.app.services.timemachine_service.get_timemachine_service",
        lambda: _FakeTimeMachineService(),
    )

    resp = client.get("/api/v1/cockpit/student/demo-student-6")
    assert resp.status_code == 200
    data = resp.json()
    assert data["forecast"]["curve"] == [
        {"day": 0, "mastery": 0.42},
        {"day": 1, "mastery": 0.55},
    ]


def test_cockpit_maps_kg_neighbors(client, monkeypatch):
    """kg 应复用 GraphRetriever 的 recommended 邻居结果。"""
    _seed_profile("demo-student-7")

    class _KP:
        def __init__(self, kp_id: str, name: str):
            self.id = kp_id
            self.name = name

    class _FakeKG:
        @staticmethod
        def list_kps():
            return [_KP("kp-a", "CNN")]

    class _FakeRetriever:
        kg = _FakeKG()

        @staticmethod
        def find_neighbors(kp_id: str, depth: int = 2, direction: str = "both"):
            return {
                "recommended": [
                    {
                        "id": "kp-b",
                        "name": "Backprop",
                        "relation_path": [{"source": kp_id, "target": "kp-b", "relation": "prereq"}],
                    },
                    {
                        "id": "kp-c",
                        "name": "Pooling",
                        "relation_path": [],
                    },
                ]
            }

    monkeypatch.setattr(
        "backend.app.services.knowledge_graph.retriever.get_graph_retriever",
        lambda: _FakeRetriever(),
    )

    resp = client.get("/api/v1/cockpit/student/demo-student-7")
    assert resp.status_code == 200
    data = resp.json()
    assert data["kg"]["current_kp"] == "CNN"
    assert data["kg"]["neighbors_2hop"] == [
        {"id": "kp-b", "name": "Backprop", "distance": 1},
        {"id": "kp-c", "name": "Pooling", "distance": 2},
    ]


@pytest.mark.parametrize("user_id", [f"demo-student-{i}" for i in range(1, 6)])
def test_cockpit_demo_users_meet_p0_readiness(client, user_id):
    """5 个 demo user 的 P0 字段不能只是结构存在，还要有可展示内容。"""
    resp = client.get(f"/api/v1/cockpit/student/{user_id}")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["profile"]["radar_6d"]) == 6
    assert len(data["forecast"]["curve"]) >= 7
    assert data["forecast"]["counterfactual"]


def test_cockpit_demo_payload_includes_phase1_rich_blocks(client):
    """demo fallback 应提供足够丰富的 P1/P2 数据供 cockpit 组件展示。"""
    payloads = {
        f"demo-student-{i}": client.get(f"/api/v1/cockpit/student/demo-student-{i}").json()
        for i in range(1, 6)
    }

    assert any(len(data["kg"]["neighbors_2hop"]) >= 5 for data in payloads.values())
    assert any(len(data["attribution"]["category_distribution"]) >= 3 for data in payloads.values())
    assert any(sum(1 for claim in data["cov"]["recent_claims"] if claim["verified"]) >= 3 for data in payloads.values())
    assert any(len(data["debate"]["recent_traces"]) >= 2 for data in payloads.values())
    assert all(
        {
            "scaffolding_score",
            "answer_leak_risk",
            "misconception_reinforcement_risk",
            "student_uptake_prompt",
        }
        <= set(data["safety"].keys())
        for data in payloads.values()
    )
    assert any(
        sum(
            1
            for value in (data["ledger"].get("source_distribution") or {}).values()
            if isinstance(value, (int, float)) and value > 0
        )
        >= 5
        for data in payloads.values()
    )
    assert any(
        any(bool(claim.get("conflict_warning")) for claim in data["ledger"].get("claims", []))
        for data in payloads.values()
    )
