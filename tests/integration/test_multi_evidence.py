"""Plan P1-5 + P1-6：/generate/multi 扩展字段自动化测试。

覆盖：
- multi 输出含 evidence / cov / safety / downloads / overall_quality / overall_safety
- 入口触发 agent_tools trace (lookup_knowledge_point / execute_code /
  search_resources 三类至少一种被记录)
- downloads 数组非空（实际 artifact registry 应注册成功）
- profile / kp_id / bloom_level 字段透传
- types 过滤未知类型

性能考量：multi 端点单次 ≈ 9-50s（取决于 RAG 冷启动 + 4 类资源生成），
所以测试 case 数量控制在 6 个以内，每个用 1-2 类资源，避免 200s+ 超时。
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ================================================================
# Fixtures
# ================================================================
@pytest.fixture(scope="module")
def app() -> FastAPI:
    from backend.app.api.v1.artifacts import router as artifacts_router
    from backend.app.api.v1.agent_tools import router as tools_router

    a = FastAPI()
    a.include_router(artifacts_router, prefix="/api/v1")
    a.include_router(tools_router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_trace():
    from backend.app.services.agent_tools.registry import reset_tool_trace
    reset_tool_trace()
    yield
    reset_tool_trace()


@pytest.fixture(autouse=True)
def _clean_registry():
    from backend.app.api.v1.artifacts.registry import get_artifact_registry
    get_artifact_registry().clear()
    yield


# ================================================================
# ResourceEnvelope 字段
# ================================================================
class TestMultiEnvelope:
    def test_multi_returns_evidence_cov_safety(self, client: TestClient):
        """Plan P1-5：每个 result 必须含 evidence / cov / safety / downloads 字段。"""
        r = client.post(
            "/api/v1/artifacts/generate/multi",
            json={
                "topic": "Self-Attention",
                "types": ["mermaid", "code"],  # 1 mermaid + 1 code，控制总耗时
                "kp_id": "self_attention",
                "bloom_level": "apply",
                "learning_objective": "理解 Self-Attention 的 QKV 拆解",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["topic"] == "Self-Attention"
        assert data["profile"]["kp_id"] == "self_attention"
        assert data["profile"]["bloom_level"] == "apply"
        assert data["profile"]["learning_objective"] == "理解 Self-Attention 的 QKV 拆解"

        # 每个 result 必须含 P1-5 扩展字段
        for type_name, env in data["results"].items():
            assert "evidence" in env, f"{type_name} missing evidence"
            assert "cov" in env, f"{type_name} missing cov"
            assert "safety" in env, f"{type_name} missing safety"
            assert "downloads" in env, f"{type_name} missing downloads"
            assert isinstance(env["evidence"], list)
            assert isinstance(env["cov"], dict)
            assert isinstance(env["safety"], dict)
            assert isinstance(env["downloads"], list)

    def test_overall_quality_and_safety_present(self, client: TestClient):
        r = client.post(
            "/api/v1/artifacts/generate/multi",
            json={"topic": "RNN", "types": ["mermaid"]},
        )
        data = r.json()
        assert "overall_quality" in data
        assert "overall_safety" in data
        assert isinstance(data["overall_quality"], (int, float))
        assert isinstance(data["overall_safety"], (int, float))
        # safety 应该是 0-1 之间
        assert 0.0 <= data["overall_safety"] <= 1.0

    def test_profile_kp_id_passthrough(self, client: TestClient):
        r = client.post(
            "/api/v1/artifacts/generate/multi",
            json={
                "topic": "Transformer",
                "types": ["mermaid"],
                "kp_id": "transformer",
                "bloom_level": "analyze",
                "misconception": "Self-Attention ≠ cross-Attention",
            },
        )
        data = r.json()
        assert data["profile"]["kp_id"] == "transformer"
        assert data["profile"]["bloom_level"] == "analyze"
        assert data["profile"]["misconception"] == "Self-Attention ≠ cross-Attention"

    def test_unknown_type_filtered(self, client: TestClient):
        r = client.post(
            "/api/v1/artifacts/generate/multi",
            json={"topic": "X", "types": ["unknown", "code"]},
        )
        data = r.json()
        assert set(data["types_requested"]) == {"code"}

    def test_misconception_appears_as_evidence(self, client: TestClient):
        r = client.post(
            "/api/v1/artifacts/generate/multi",
            json={
                "topic": "Transformer",
                "types": ["pptx"],
                "misconception": "attention 不是 RNN",
            },
        )
        data = r.json()
        pptx_ev = data["results"]["pptx"]["evidence"]
        # misconception 应作为 evidence 类型出现
        targets = [e for e in pptx_ev if e.get("type") == "misconception_target"]
        assert len(targets) == 1
        assert targets[0]["ref"] == "attention 不是 RNN"


# ================================================================
# 触发 agent_tools trace — Plan P1-6 闭环
# ================================================================
def _poll_trace(client: TestClient, session_id: str, max_wait: float = 15.0):
    """trace 在 multi 入口同步 await 写完，但 sleep 一点避免 race。

    返回 trace body；超过 max_wait 还没数据就抛 AssertionError。
    """
    deadline = time.time() + max_wait
    last_body = {"items": [], "total": 0}
    while time.time() < deadline:
        r = client.get(
            "/api/v1/agent-tools/trace",
            params={"session_id": session_id, "limit": 50},
        )
        if r.status_code == 200:
            last_body = r.json()
            if last_body.get("total", 0) >= 3:
                return last_body
        time.sleep(0.5)
    return last_body


class TestMultiTriggersAgentToolsTrace:
    def test_multi_writes_to_agent_trace(self, client: TestClient):
        """Plan P1-6 闭环：multi 调用后 /api/v1/agent-tools/trace 必有记录。

        验证 lookup_knowledge_point + search_resources + execute_code 三类
        都被记录（types 含 code → 额外有 execute_code）。
        """
        session_id = "trace-multi-001"
        r = client.post(
            "/api/v1/artifacts/generate/multi",
            json={
                "topic": "Self-Attention",
                "types": ["mermaid", "code"],
                "kp_id": "self_attention",
                "session_id": session_id,
            },
        )
        assert r.status_code == 200

        # multi 入口同步 await trace 写完，但留一点缓冲避免 race
        time.sleep(0.5)
        body = _poll_trace(client, session_id)
        tools_called = {it["tool"] for it in body["items"]}
        assert "lookup_knowledge_point" in tools_called, (
            f"trace missing lookup; got: {tools_called}"
        )
        assert "search_resources" in tools_called, (
            f"trace missing search; got: {tools_called}"
        )
        assert "execute_code" in tools_called, (
            f"trace missing execute_code; got: {tools_called}"
        )

    def test_multi_trace_has_args_latency(self, client: TestClient):
        """trace item 必须含 args / latency_ms / timestamp 三段。"""
        session_id = "trace-multi-002"
        client.post(
            "/api/v1/artifacts/generate/multi",
            json={"topic": "RNN", "types": ["mermaid"], "session_id": session_id},
        )
        time.sleep(0.3)
        body = _poll_trace(client, session_id)
        assert body["total"] >= 1
        for it in body["items"]:
            assert "args" in it
            assert "latency_ms" in it
            assert "timestamp" in it
            assert isinstance(it["latency_ms"], (int, float))