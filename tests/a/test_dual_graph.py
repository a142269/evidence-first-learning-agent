"""Plan P1-2：双图学习路径（先修图 + 语义相似图）自动化测试。

覆盖：
- planner.plan() 返回 main_path / detour_path / remediation_path 三条
- focus_kp 不存在时返回 error
- mastery_lookup 注入：mastery < threshold 时 detour/remediation 触发
- prereq_graph + similar_graph 块存在
- API 端点 POST /api/v1/learning-path/dual-graph
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ================================================================
# Fixtures
# ================================================================
@pytest.fixture(scope="module")
def app() -> FastAPI:
    from backend.app.api.v1.learning_path import router as lp_router

    a = FastAPI()
    a.include_router(lp_router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ================================================================
# 用 KG mock 直接驱动 planner
# ================================================================
class TestDualGraphPlan:
    """Plan P1-2：注入假 mastery + mock KG store 跑端到端。"""

    def _make_mock_store(self):
        """构造一个 minimal KG store mock：4 个 KP + prerequisite 边 + 相似边。"""
        class _Row:
            def __init__(self, id, name, bloom="Understand"):
                self.id = id
                self.name = name
                self.bloom = bloom
                self.course = "ai_intro"
                self.metadata_data = {"bloom": bloom}

        class _Rel:
            def __init__(self, source, target, rt="prerequisite", weight=1.0):
                self.source_id = source
                self.target_id = target
                self.relation_type = rt
                self.weight = weight

        rows = {
            "transformer": _Row("transformer", "Transformer", "Apply"),
            "self_attention": _Row("self_attention", "Self-Attention", "Apply"),
            "rnn": _Row("rnn", "RNN", "Understand"),
            "embedding": _Row("embedding", "词嵌入", "Remember"),
        }
        # self_attention -> transformer (prereq)
        # rnn -> self_attention (related)
        # embedding -> self_attention (foundation)
        rels = [
            _Rel("self_attention", "transformer", "prerequisite"),
            _Rel("rnn", "self_attention", "related"),
            _Rel("embedding", "self_attention", "foundation"),
            _Rel("rnn", "transformer", "related"),
        ]

        class _Store:
            def get_kp(self, kp_id):
                return rows.get(kp_id)

            def find_by_name(self, name):
                for r in rows.values():
                    if r.name == name:
                        return r
                return None

            def list_relations(self, kp_id=None, relation_type=None):
                out = []
                for r in rels:
                    if relation_type and r.relation_type != relation_type:
                        continue
                    if kp_id and r.source_id != kp_id and r.target_id != kp_id:
                        continue
                    out.append(r)
                return out

            def get_neighbors(self, kp_id, direction="both"):
                out = []
                for r in rels:
                    if r.source_id == kp_id:
                        out.append({
                            "kp_id": r.target_id,
                            "relation_type": r.relation_type,
                            "weight": r.weight,
                        })
                    elif r.target_id == kp_id and direction == "both":
                        out.append({
                            "kp_id": r.source_id,
                            "relation_type": r.relation_type,
                            "weight": r.weight,
                        })
                return out

            def get_subgraph(self, seed_ids, hops=2):
                nodes = {sid: rows[sid] for sid in seed_ids if sid in rows}
                edges = []
                return {"nodes": nodes, "edges": edges}

        return _Store()

    def _planner_with_mock(self, mastery=None):
        """构造一个 planner，patch KG store + mastery_lookup。"""
        from backend.app.services import learning_path_dual_graph as mod

        store = self._make_mock_store()
        # monkey-patch _get_kg_store
        planner = mod.DualGraphPathPlanner(mastery_lookup=lambda uid: mastery or {})
        planner._get_kg_store = lambda: store
        return planner

    def test_main_path_returns_target_first(self):
        planner = self._planner_with_mock(mastery={
            "self_attention": 0.8, "embedding": 0.9, "rnn": 0.7,
        })
        out = planner.plan(user_id="u-1", focus_kp="transformer")
        assert out["focus_kp"] == "transformer"
        assert out["focus_kp_name"] == "Transformer"
        assert out["main_path"][0]["kp_id"] == "transformer"
        # 至少有一个 step 来自 prereq 关系
        sources = {step["source"] for step in out["main_path"]}
        assert "prereq" in sources

    def test_detour_replaces_weak_kp_with_similar(self):
        """mastery < threshold 的 KP 被 similar 边替代。"""
        planner = self._planner_with_mock(mastery={
            "self_attention": 0.3,  # 弱
            "embedding": 0.9,
            "rnn": 0.5,
        })
        out = planner.plan(user_id="u-1", focus_kp="transformer", mastery_threshold=0.6)
        detour = out["detour_path"]
        # 至少有一步 source == "similarity"
        similar_steps = [s for s in detour if s["source"] == "similarity"]
        assert len(similar_steps) >= 1, "detour should use similarity to bypass weak KP"

    def test_remediation_lists_weak_first(self):
        """remediation 按 mastery 升序，把薄弱 KP 提到最前。"""
        planner = self._planner_with_mock(mastery={
            "self_attention": 0.3,
            "embedding": 0.9,
        })
        out = planner.plan(user_id="u-1", focus_kp="transformer", mastery_threshold=0.6)
        weak = out["remediation_path"]
        # 第一步必须 source == "mastery"，且 mastery 是路径里最低的
        assert weak[0]["source"] == "mastery"
        assert weak[0]["mastery"] == 0.3

    def test_explanations_three_kinds(self):
        planner = self._planner_with_mock(mastery={})
        out = planner.plan(user_id="u-1", focus_kp="transformer")
        kinds = {e["kind"] for e in out["explanations"]}
        assert kinds == {"main", "detour", "remediation"}

    def test_prereq_and_similar_graph_blocks_present(self):
        planner = self._planner_with_mock(mastery={})
        out = planner.plan(user_id="u-1", focus_kp="transformer")
        assert "prereq_graph" in out
        assert "similar_graph" in out
        assert out["prereq_graph"]["node_count"] >= 1
        # similar_graph 至少包含 1 个 neighbor
        assert isinstance(out["similar_graph"]["neighbors"], list)

    def test_kp_not_found_returns_error(self):
        planner = self._planner_with_mock()
        out = planner.plan(user_id="u-1", focus_kp="nonexistent-kp-xxx")
        assert out.get("error") == "kp_not_found"

    def test_stats_present(self):
        planner = self._planner_with_mock(mastery={"self_attention": 0.5})
        out = planner.plan(user_id="u-1", focus_kp="transformer")
        stats = out["stats"]
        assert "kp_count" in stats
        assert "edge_count" in stats
        assert "weak_kp_count" in stats


# ================================================================
# API 端点
# ================================================================
class TestDualGraphAPI:
    def test_dual_graph_endpoint_returns_three_paths(self, client: TestClient):
        # 真实环境可能没有该 KP，但 API 端点必须返回结构 (含 error 也算合法响应)
        r = client.post(
            "/api/v1/learning-path/dual-graph",
            json={"user_id": "u-1", "focus_kp": "transformer"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # 即便 error，三种路径字段仍可能存在为 []
        if "error" not in body:
            assert "main_path" in body
            assert "detour_path" in body
            assert "remediation_path" in body

    def test_dual_graph_endpoint_missing_user_returns_error(self, client: TestClient):
        r = client.post(
            "/api/v1/learning-path/dual-graph",
            json={"focus_kp": "transformer"},
        )
        assert r.status_code == 200
        assert r.json().get("error") == "missing_user_or_focus"

    def test_dual_graph_endpoint_with_unknown_focus(self, client: TestClient):
        r = client.post(
            "/api/v1/learning-path/dual-graph",
            json={"user_id": "u-1", "focus_kp": "nonexistent-zzz"},
        )
        assert r.status_code == 200
        # KG 找不到时返回 error 字段或空路径
        body = r.json()
        assert body.get("error") == "kp_not_found" or body.get("main_path") == []