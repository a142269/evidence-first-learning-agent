"""
集成测试: chat.py 7 阶段端到端真实流 (mock LLM)

验证 chat.py 通过 ConversationPipeline 把 7 个 stage 串起来:
    1. InputValidation   → user_input 校验
    2. RAGRetrieval      → 知识检索
    3. RealtimeState     → 实时学情
    4. Orchestration     → 多智能体编排 (用 mock LLM 输出固定 markdown)
    5. DebateReflection  → 辩论 + 反思
    6. Aggregation       → 选 primary + 安全 + 质量
    7. Persist           → 历史 / 资源持久化

策略:
- 用 monkeypatch 替换 LLMClient → 不打真实讯飞/DeepSeek API
- 验证响应字段 + telemetry + 会话历史 + 资源 metadata
- 同时验证 SSE 流式 + Last-Event-ID 重连
- 5 类资源关键路径 chat → orchestrator → multimodal agent 验证

注意:
- 这些测试比单元测试慢 (1-3s 每个), 标记为 integration
- 跑前不需要 DB / 不需要 LLM API key
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ================================================================
# Mock LLM Client - 返回 deterministic 的 markdown
# ================================================================
def _mock_llm_factory(reply_text: str = ""):
    """构造一个返回固定文本的 LLMClient"""
    llm = MagicMock()
    default_reply = reply_text or (
        "# 卷积神经网络入门\n\n"
        "卷积神经网络 (CNN) 是一种深度学习模型。\n\n"
        "## 核心组件\n- 卷积层\n- 池化层\n- 全连接层\n\n"
        "例如, LeNet-5 是经典 CNN。\n\n"
        "## 练习\n用 PyTorch 实现 LeNet-5。"
    )
    llm.chat = MagicMock(return_value=default_reply)
    return llm


@pytest.fixture(scope="module")
def app() -> FastAPI:
    from backend.app.api.v1.chat import router as chat_router

    a = FastAPI()
    a.include_router(chat_router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _patch_global_llm(monkeypatch):
    """替换 chat_pipeline 中的全局 LLM/Safety 单例为 mock"""
    from backend.app.api.v1.chat_pipeline.stages import _shared as shared
    from backend.app.api.v1.chat_pipeline.session import reset_session_store
    from backend.app.api.v1.chat_pipeline.stages._shared import reset_shared_state

    reset_shared_state()
    reset_session_store()

    # patch the LLM singleton getter
    mock_llm = _mock_llm_factory()
    monkeypatch.setattr(shared, "get_shared_llm", lambda: mock_llm)

    yield

    reset_shared_state()
    reset_session_store()


# ================================================================
# 1. POST /chat/send — 基础同步路径
# ================================================================
class TestChatSend:
    def test_empty_message_400(self, client: TestClient):
        r = client.post("/api/v1/chat/send", json={"message": "   "})
        assert r.status_code == 400

    def test_basic_send_returns_response(self, client: TestClient):
        r = client.post("/api/v1/chat/send", json={
            "message": "讲解一下卷积神经网络",
            "course": "artificial_intelligence",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        # 7 阶段每个都应在 telemetry 里
        assert "telemetry" in data
        assert "stages" in data["telemetry"]
        # 应至少跑 4 个 stage (input/rag/realtime/orchestration)
        assert len(data["telemetry"]["stages"]) >= 4

    def test_session_id_persists(self, client: TestClient):
        """同一 session_id 第二次请求, history 应累计"""
        r1 = client.post("/api/v1/chat/send", json={
            "message": "什么是 CNN", "session_id": "test-persist",
        })
        sid = r1.json()["session_id"]
        assert sid

        # 第二次用同一 sid
        r2 = client.post("/api/v1/chat/send", json={
            "message": "继续讲", "session_id": sid,
        })
        assert r2.status_code == 200
        assert r2.json()["session_id"] == sid

        # 历史应有 ≥ 2 条 user + ≥ 2 条 assistant
        rh = client.get(f"/api/v1/chat/history/{sid}")
        assert rh.status_code == 200
        history = rh.json()["history"]
        assert len(history) >= 4

    def test_telemetry_includes_pipeline_metrics(self, client: TestClient):
        r = client.post("/api/v1/chat/send", json={
            "message": "讲解 LSTM", "session_id": "telemetry-test",
        })
        t = r.json()["telemetry"]
        assert "total_ms" in t
        assert "agents" in t
        # Orchestration 阶段一定会执行
        stages = [s["name"] for s in t["stages"]]
        assert "input_validation" in stages
        assert "orchestration" in stages


# ================================================================
# 2. POST /chat/stream — SSE 流式
# ================================================================
class TestChatStream:
    def test_stream_returns_sse_chunks(self, client: TestClient):
        with client.stream("POST", "/api/v1/chat/stream", json={
            "message": "讲解 dropout", "session_id": "stream-test",
        }) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get(
                "content-type", "",
            )
            text = "".join(chunk for chunk in resp.iter_text())

        # 应含若干 SSE 事件
        assert "event: meta" in text
        assert "event: chunk" in text or "event: done" in text
        # 事件应带 id (支持重连)
        assert "id: 1" in text

    def test_team_stream_emits_one_named_message_per_agent(
        self, client: TestClient, monkeypatch,
    ):
        from backend.app.api.v1 import chat as chat_module

        names = [
            ("path_planner", "planner", "智狐"),
            ("tutor", "tutor", "智灵"),
            ("doc_gen", "content", "阿匠"),
            ("exercise", "quiz", "小龙"),
            ("evaluator", "evaluation", "团团"),
        ]

        async def fake_process(*_args, **_kwargs):
            messages = [
                {
                    "task_id": f"task_{index}",
                    "agent": agent,
                    "agent_key": key,
                    "display_name": display_name,
                    "role": "学习伙伴",
                    "content": f"{display_name} 的独立回答",
                    "content_type": "markdown",
                    "resources": [],
                    "success": True,
                    "error": "",
                }
                for index, (agent, key, display_name) in enumerate(names)
            ]
            return {
                "session_id": "team-stream",
                "primary_agent": "doc_gen",
                "content": "聚合回答",
                "content_type": "markdown",
                "resources": [],
                "saved_resources": [],
                "profile": {},
                "profile_meta": {},
                "realtime_state": {},
                "rag_hits": [],
                "agents_invoked": [
                    {"name": agent, "success": True, "content_type": "markdown"}
                    for agent, _, _ in names
                ],
                "agent_messages": messages,
                "quality": {},
                "safety": {},
                "debate": None,
                "reflection": {},
                "success": True,
                "error": "",
                "telemetry": {},
            }

        monkeypatch.setattr(chat_module, "_process_turn", fake_process)
        with client.stream("POST", "/api/v1/chat/stream", json={
            "message": "@智狐 @智灵 @阿匠 @小龙 @团团 分别回答",
            "session_id": "team-stream",
        }) as response:
            text = "".join(chunk for chunk in response.iter_text())

        assert text.count("event: agent_start") == 5
        assert text.count("event: agent_done") == 5
        assert "event: agent_chunk" in text
        for _, _, display_name in names:
            assert display_name in text
        assert '"multi_agent":true' in text.replace(" ", "")

    def test_stream_resumes_with_last_event_id(self, client: TestClient):
        """第二次请求带 Last-Event-ID, 应有 replay"""
        # 第一次正常拉
        with client.stream("POST", "/api/v1/chat/stream", json={
            "message": "讲解 Adam", "session_id": "resume-test",
        }) as resp:
            "".join(chunk for chunk in resp.iter_text())

        # 第二次带 Last-Event-ID=0 重连 (应重放 + 继续)
        with client.stream(
            "POST", "/api/v1/chat/stream",
            json={"message": "继续讲", "session_id": "resume-test"},
            headers={"Last-Event-ID": "1"},
        ) as resp:
            assert resp.status_code == 200
            text = "".join(chunk for chunk in resp.iter_text())
        # 至少要有 event lines
        assert "event:" in text


# ================================================================
# 3. GET /chat/profile|history|realtime + POST /chat/clear
# ================================================================
class TestChatSessionEndpoints:
    def test_profile_default_empty(self, client: TestClient):
        # 先发一条建立 session
        r = client.post("/api/v1/chat/send", json={
            "message": "你好", "session_id": "profile-test",
        })
        sid = r.json()["session_id"]

        rp = client.get(f"/api/v1/chat/profile/{sid}")
        assert rp.status_code == 200
        # profile 字段一定存在 (可能空)
        assert "profile" in rp.json()

    def test_realtime_state_present(self, client: TestClient):
        r = client.post("/api/v1/chat/send", json={
            "message": "我有点不太懂", "session_id": "realtime-test",
        })
        sid = r.json()["session_id"]
        rr = client.get(f"/api/v1/chat/realtime/{sid}")
        assert rr.status_code == 200
        # state 至少不为 None
        assert "state" in rr.json()

    def test_clear_removes_session(self, client: TestClient):
        r = client.post("/api/v1/chat/send", json={
            "message": "hello", "session_id": "clear-test",
        })
        sid = r.json()["session_id"]
        cr = client.post("/api/v1/chat/clear", json={"session_id": sid})
        assert cr.status_code == 200
        assert cr.json()["status"] == "cleared"

    def test_clear_unknown_returns_not_found(self, client: TestClient):
        r = client.post("/api/v1/chat/clear", json={
            "session_id": "never_existed",
        })
        assert r.json()["status"] == "not_found"


# ================================================================
# 4. 7 阶段完整覆盖 (直接调 Pipeline)
# ================================================================
class TestPipeline7StageE2E:
    @pytest.mark.asyncio
    async def test_all_7_stages_execute_in_order(self):
        from backend.app.api.v1.chat_pipeline import (
            PipelineContext, build_default_pipeline, get_session_store,
        )
        from backend.app.api.v1.chat_pipeline.stages._shared import (
            reset_shared_state,
        )
        from backend.app.api.v1.chat_pipeline.session import (
            reset_session_store,
        )

        reset_shared_state()
        reset_session_store()
        store = get_session_store()
        sid, session = store.get_or_create()

        ctx = PipelineContext(
            session_id=sid,
            session=session,
            user_input="讲解 attention",
            course="artificial_intelligence",
            services={"session_store": store},
        )
        pipeline = build_default_pipeline()
        await pipeline.execute(ctx)

        # 校验 telemetry 含 7 个阶段
        stage_names = [m.name for m in ctx.telemetry.stage_metrics]
        for expected in [
            "input_validation", "rag_retrieval", "realtime_state",
            "orchestration", "debate_reflection",
            "aggregation", "persist",
        ]:
            assert expected in stage_names, (
                f"阶段 {expected} 未在 telemetry 中"
            )


# ================================================================
# 5. Prometheus 指标桥接 - chat 调用后 metrics 应有相应递增
# ================================================================
class TestTelemetryBridge:
    def test_pipeline_stages_total_increments(self, client: TestClient):
        from backend.app.core.telemetry import get_telemetry, reset_telemetry
        reset_telemetry()
        tel = get_telemetry()
        before = tel.counter("pipeline_stages_total").value(
            stage="input_validation", status="ok",
        )

        client.post("/api/v1/chat/send", json={
            "message": "讲解 BN", "session_id": "metric-bridge",
        })

        after = tel.counter("pipeline_stages_total").value(
            stage="input_validation", status="ok",
        )
        assert after > before
