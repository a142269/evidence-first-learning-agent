"""Plan P1-1 + P1-6：Agent Tools 注册表与 ToolCallTrace 自动化测试。

目标：
- 验证 4 个核心工具 (lookup_knowledge_point / query_knowledge_graph /
  execute_code / search_resources) 都能跑通，不抛 5xx
- 验证 ToolCallTrace 真有记录，前端 /api/v1/agent-tools/trace 能拿到
- 验证按 session_id 分组隔离 (Plan P1-1 增量)
- 验证 tools 的 OpenAI function-call schema 合法

不依赖真实 RAG / KG / 网络：所有 service 层异常被吞掉转成 error 字段，
trace 必须仍然能写入。TestClient 不启动 uvicorn。
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
    from backend.app.api.v1.agent_tools import router as tools_router

    a = FastAPI()
    a.include_router(tools_router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_trace():
    """每个测试前清空全局 trace，避免互相污染。"""
    from backend.app.services.agent_tools.registry import (
        get_tool_trace, reset_tool_trace,
    )
    reset_tool_trace()
    yield
    reset_tool_trace()


# ================================================================
# 4 个核心工具：直接调用
# ================================================================
class TestToolHandlers:
    """直接调用 _lookup_kp / _query_kg / _exec_code / _search_res，
    验证 handler 不会向上抛异常，且 _traced_call 写入 trace。"""

    @pytest.mark.asyncio
    async def test_lookup_kp_records_trace(self):
        from backend.app.services.agent_tools.registry import (
            _lookup_kp, get_tool_trace,
        )
        result = await _lookup_kp("Self-Attention", __session_id__="t-lookup")
        assert isinstance(result, dict)
        trace = get_tool_trace().recent("t-lookup", limit=10)
        assert len(trace) == 1
        rec = trace[0]
        assert rec["tool"] == "lookup_knowledge_point"
        assert rec["args"].get("kp_name") == "Self-Attention"
        assert "latency_ms" in rec
        # success 字段必须存在（不管 RAG 在不在场，handler 必须不抛）
        assert isinstance(rec["success"], bool)

    @pytest.mark.asyncio
    async def test_query_kg_records_trace(self):
        from backend.app.services.agent_tools.registry import (
            _query_kg, get_tool_trace,
        )
        result = await _query_kg("transformer", hop=2, __session_id__="t-kg")
        # 即使 KG 不可用，handler 必须返回 dict
        assert isinstance(result, dict)
        trace = get_tool_trace().recent("t-kg", limit=10)
        assert len(trace) == 1
        assert trace[0]["tool"] == "query_knowledge_graph"

    @pytest.mark.asyncio
    async def test_exec_code_records_trace(self):
        from backend.app.services.agent_tools.registry import (
            _exec_code, get_tool_trace,
        )
        result = await _exec_code(
            language="python",
            code="print('hello trace')",
            timeout=5,
            __session_id__="t-exec",
        )
        assert isinstance(result, dict)
        assert result.get("tool") == "execute_code"
        trace = get_tool_trace().recent("t-exec", limit=10)
        assert len(trace) == 1
        assert trace[0]["tool"] == "execute_code"

    @pytest.mark.asyncio
    async def test_search_resources_records_trace(self):
        from backend.app.services.agent_tools.registry import (
            _search_res, get_tool_trace,
        )
        result = await _search_res(
            query="Self-Attention",
            resource_type="pptx",
            limit=3,
            __session_id__="t-search",
        )
        assert isinstance(result, dict)
        assert "results" in result or "found" in result
        trace = get_tool_trace().recent("t-search", limit=10)
        assert len(trace) == 1
        assert trace[0]["tool"] == "search_resources"


# ================================================================
# 内部容错：handler 抛异常时 _traced_call 必须吞掉并转 error
# ================================================================
class TestTracedCallErrorTolerance:
    """Plan P1-1 约束：handler 异常必须被吞，trace 永远能写成功。"""

    @pytest.mark.asyncio
    async def test_handler_exception_still_records(self):
        from backend.app.services.agent_tools import registry as reg

        def _boom(**kw):
            raise RuntimeError("synthetic service outage")

        # 直接走 _traced_call：模拟 handler 抛异常的兜底路径
        out = reg._traced_call(
            "lookup_knowledge_point", _boom,
            __session_id__="t-boom", kp_name="X",
        )
        # 返回结构化的失败 dict，而不是向上抛
        assert isinstance(out, dict)
        assert out.get("success") is False
        assert "RuntimeError" in out.get("error", "")

        trace = reg.get_tool_trace().recent("t-boom", limit=10)
        assert len(trace) == 1
        rec = trace[0]
        assert rec["success"] is False
        assert "RuntimeError" in rec["error"]


# ================================================================
# Trace 环形缓冲 & session 隔离
# ================================================================
class TestTraceSessionIsolation:
    def test_different_sessions_isolated(self):
        from backend.app.services.agent_tools.registry import (
            _traced_call, get_tool_trace,
        )

        def _ok(**kw):
            return {"ok": True, "x": kw.get("x")}

        for sid in ("alpha", "beta"):
            _traced_call("lookup_knowledge_point", _ok, __session_id__=sid, x=sid)
        _traced_call("search_resources", _ok, __session_id__="alpha", x="solo")

        alpha = get_tool_trace().recent("alpha", limit=10)
        beta = get_tool_trace().recent("beta", limit=10)
        assert len(alpha) == 2
        assert len(beta) == 1
        # 最新在前
        assert alpha[0]["tool"] == "search_resources"
        assert alpha[0]["args"]["x"] == "solo"
        assert alpha[1]["tool"] == "lookup_knowledge_point"

    def test_stats_aggregate(self):
        from backend.app.services.agent_tools.registry import (
            _traced_call, get_tool_trace,
        )

        def _ok(**kw):
            return {"ok": True}

        def _fail(**kw):
            raise ValueError("nope")

        _traced_call("lookup_knowledge_point", _ok, __session_id__="s")
        _traced_call("search_resources", _ok, __session_id__="s")
        _traced_call("execute_code", _fail, __session_id__="s")

        stats = get_tool_trace().stats("s")
        assert stats["total"] == 3
        assert stats["success"] == 2
        assert stats["failed"] == 1
        assert abs(stats["success_rate"] - 2 / 3) < 0.01
        assert stats["by_tool"]["lookup_knowledge_point"] == 1
        assert stats["by_tool"]["search_resources"] == 1
        assert stats["by_tool"]["execute_code"] == 1


# ================================================================
# /api/v1/agent-tools/trace API
# ================================================================
class TestTraceAPI:
    def test_trace_endpoint_returns_items(self, client: TestClient):
        # 先写一条
        client.get("/api/v1/agent-tools/trace")
        # 用工具记录一条
        from backend.app.services.agent_tools.registry import _traced_call
        def _ok():
            return {"ok": True, "tool": "X"}

        _traced_call("lookup_knowledge_point", _ok, __session_id__="api-t-1", arg_name="X")

        r = client.get("/api/v1/agent-tools/trace", params={"session_id": "api-t-1", "limit": 5})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] >= 1
        assert any(it["tool"] == "lookup_knowledge_point" for it in body["items"])

    def test_trace_stats_endpoint(self, client: TestClient):
        from backend.app.services.agent_tools.registry import _traced_call

        def _ok(**kw):
            return {"ok": True}

        for i in range(3):
            _traced_call("search_resources", _ok, __session_id__="api-stats", i=i)

        r = client.get("/api/v1/agent-tools/trace/stats", params={"session_id": "api-stats"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 3
        assert body["success"] == 3
        assert body["by_tool"]["search_resources"] == 3

    def test_trace_clear_endpoint(self, client: TestClient):
        from backend.app.services.agent_tools.registry import _traced_call, get_tool_trace

        def _ok(**kw):
            return {"ok": True}

        _traced_call("execute_code", _ok, __session_id__="api-clear")
        assert get_tool_trace().recent("api-clear", limit=10)

        r = client.post("/api/v1/agent-tools/trace/clear", params={"session_id": "api-clear"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert get_tool_trace().recent("api-clear", limit=10) == []


# ================================================================
# OpenAI function-call schema 合法
# ================================================================
class TestOpenAISchema:
    def test_all_tools_have_valid_openai_format(self):
        from backend.app.services.agent_tools.registry import get_tool_registry

        tools = get_tool_registry().to_openai_tools()
        assert len(tools) == 5
        names = {t["function"]["name"] for t in tools}
        assert names == {
            "lookup_knowledge_point",
            "query_knowledge_graph",
            "execute_code",
            "search_resources",
            "generate_learning_materials",
        }
        for t in tools:
            assert t["type"] == "function"
            assert "name" in t["function"]
            assert "description" in t["function"]
            assert "parameters" in t["function"]
            params = t["function"]["parameters"]
            assert params["type"] == "object"
            assert isinstance(params.get("properties"), dict)
            # required 必须存在，可以为空 list
            assert isinstance(params.get("required"), list)
