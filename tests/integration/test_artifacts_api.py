"""
集成测试: /api/v1/artifacts/* 全部 16 个路由

覆盖:
- ArtifactRegistry CRUD + 单例 (4)
- 5 类 POST /generate/* 端点 (10+)
- /generate/multi 一键生成 (3)
- GET /list / /info / download / data-uri (5)
- /metrics + /metrics/summary + /metrics/health (4)

用 TestClient 模拟 HTTP 调用, 无需启动 uvicorn。
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """构造一个最小 FastAPI app, 装载所有 artifacts + metrics 路由"""
    from backend.app.api.v1.artifacts import router as artifacts_router
    from backend.app.api.v1.metrics import router as metrics_router

    a = FastAPI()
    a.include_router(artifacts_router, prefix="/api/v1")
    a.include_router(metrics_router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个测试前清空 registry, 避免互相干扰"""
    from backend.app.api.v1.artifacts.registry import get_artifact_registry
    get_artifact_registry().clear()
    yield


# ================================================================
# Registry
# ================================================================
class TestRegistry:
    def test_singleton(self):
        from backend.app.api.v1.artifacts.registry import (
            get_artifact_registry, reset_artifact_registry,
        )
        a = get_artifact_registry()
        b = get_artifact_registry()
        assert a is b
        reset_artifact_registry()
        c = get_artifact_registry()
        assert c is not a

    def test_register_and_list(self):
        from backend.app.api.v1.artifacts.registry import get_artifact_registry
        reg = get_artifact_registry()
        reg.register("r1", "pptx", "path/to/r1.pptx", session_id="s1")
        reg.register("r2", "mp3",  "path/to/r2.mp3",  session_id="s1")
        reg.register("r3", "pptx", "path/to/r3.pptx", session_id="s2")

        assert reg.size() == 3
        assert len(reg.list(artifact_type="pptx")) == 2
        assert len(reg.list(session_id="s1")) == 2

    def test_remove(self):
        from backend.app.api.v1.artifacts.registry import get_artifact_registry
        reg = get_artifact_registry()
        reg.register("r1", "pptx", "x")
        assert reg.remove("r1") is True
        assert reg.remove("nonexistent") is False

    def test_persistent_registry_survives_restart(self, tmp_path):
        from backend.app.api.v1.artifacts.registry import ArtifactRegistry

        index = tmp_path / "registry.json"
        first = ArtifactRegistry(storage_path=index)
        first.register("code_demo", "code_result", str(tmp_path / "demo.py"), metadata={"title": "示例"})

        restored = ArtifactRegistry(storage_path=index)
        assert restored.get("code_demo") is not None
        assert restored.get("code_demo").metadata["title"] == "示例"


# ================================================================
# POST /generate/pptx
# ================================================================
class TestGeneratePPTX:
    def test_generate_pptx_returns_200(self, client: TestClient):
        body = {
            "title": "CNN 入门",
            "subtitle": "Yann LeCun 1998",
            "slides": [
                {"title": "引入", "bullets": ["历史背景", "应用领域"]},
                {"title": "原理", "bullets": ["卷积", "池化"]},
            ],
            "summary": ["核心要点"],
            "review": ["复习问题1", "复习问题2"],
        }
        r = client.post("/api/v1/artifacts/generate/pptx", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["type"] == "pptx"
        assert data["success"]
        assert data["filepath"]
        assert data["metadata"]["slides_count"] >= 1

    def test_generate_pptx_missing_title_fails(self, client: TestClient):
        r = client.post("/api/v1/artifacts/generate/pptx", json={"slides": []})
        # Pydantic 校验失败 → 422
        assert r.status_code == 422


# ================================================================
# POST /generate/mermaid (思维导图 - 赛题必备)
# ================================================================
class TestGenerateMermaid:
    def test_from_concept_returns_png_path(self, client: TestClient):
        body = {
            "title": "CNN",
            "branches": ["卷积层", "池化层", "全连接层"],
            "leaves": {"卷积层": ["局部感受野", "权值共享"]},
        }
        r = client.post("/api/v1/artifacts/generate/mermaid", json=body)
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "mermaid_png"
        # 至少 mermaid_code 必有 (render 可能降级)
        assert data["metadata"]["mermaid_code"]
        assert "root((CNN))" in data["metadata"]["mermaid_code"]

    def test_from_code_validates_syntax(self, client: TestClient):
        body = {
            "code": "garbage diagram code",
            "kind": "mindmap",
        }
        r = client.post("/api/v1/artifacts/generate/mermaid-code", json=body)
        assert r.status_code == 200
        data = r.json()
        # 不合法的 mermaid 应被 validator 拦截
        assert not data["metadata"]["validation_passed"]


# ================================================================
# POST /generate/code (代码案例 + 真实运行)
# ================================================================
class TestGenerateCode:
    def test_simple_python_runs(self, client: TestClient):
        body = {"code": "print(2 + 3)", "language": "python"}
        r = client.post("/api/v1/artifacts/generate/code", json=body)
        assert r.status_code == 200
        data = r.json()
        assert data["success"]
        assert "5" in data["metadata"]["stdout"]
        assert data["metadata"]["execution_level"] in (1, 2, 3)

    def test_dangerous_code_blocked(self, client: TestClient):
        body = {"code": "import os\nos.system('echo evil')"}
        r = client.post("/api/v1/artifacts/generate/code", json=body)
        assert r.status_code == 200
        data = r.json()
        assert not data["success"]
        assert data["metadata"]["execution_level"] == 1

    def test_with_review_returns_hints(self, client: TestClient):
        body = {"code": "x = 1\ny = 2", "with_review": True}
        r = client.post("/api/v1/artifacts/generate/code", json=body)
        assert r.status_code == 200
        # AI review hints 应存在
        assert "review_hints" in r.json()["metadata"]


# ================================================================
# POST /generate/tts
# ================================================================
class TestGenerateTTS:
    def test_short_text_returns_audio_path(self, client: TestClient):
        body = {"text": "你好, 欢迎学习卷积神经网络。", "voice": "xiaoyan"}
        r = client.post("/api/v1/artifacts/generate/tts", json=body)
        assert r.status_code == 200
        data = r.json()
        # 无讯飞凭据时 edge-tts 是合法降级，再往后才到 mock
        assert data["filepath"]
        assert data["method"] in ("xunfei", "edge-tts", "mock", "cache")

    def test_voices_list(self, client: TestClient):
        r = client.get("/api/v1/artifacts/tts/voices")
        assert r.status_code == 200
        voices = r.json()["voices"]
        assert len(voices) >= 5
        assert any(v["id"] == "xiaoyan" for v in voices)


# ================================================================
# POST /generate/manim (默认不渲染, 仅生成 code, 避免依赖 LaTeX)
# ================================================================
class TestGenerateManim:
    def test_manim_returns_code(self, client: TestClient):
        body = {
            "topic": "梯度下降",
            "template": "concept",
            "persona": "serious",
            "render": False,
        }
        r = client.post("/api/v1/artifacts/generate/manim", json=body)
        assert r.status_code == 200
        data = r.json()
        # 不渲染 → 只有 generated_code
        assert data["metadata"]["generated_code"]
        assert "Scene" in data["metadata"]["generated_code"]


# ================================================================
# POST /generate/multi (演示高光)
# ================================================================
class TestGenerateMulti:
    def test_multi_with_3_types(self, client: TestClient):
        body = {
            "topic": "梯度下降",
            "types": ["mermaid", "code", "tts"],
            "manim_render": False,
        }
        r = client.post("/api/v1/artifacts/generate/multi", json=body)
        assert r.status_code == 200
        data = r.json()
        assert data["topic"] == "梯度下降"
        assert set(data["types_requested"]) == {"mermaid", "code", "tts"}
        assert len(data["results"]) == 3
        # 至少 mermaid + code 应成功
        assert data["success_count"] >= 2

    def test_multi_with_default_types(self, client: TestClient):
        body = {"topic": "RNN", "manim_render": False}
        r = client.post("/api/v1/artifacts/generate/multi", json=body)
        assert r.status_code == 200
        data = r.json()
        # 默认覆盖课件、导图、代码、语音/视频、文档与题库 7 类。
        assert data["types_requested"] == [
            "pptx", "mermaid", "code", "tts", "manim", "document", "quiz",
        ]

    def test_multi_unknown_type_filtered(self, client: TestClient):
        body = {
            "topic": "X", "types": ["unknown", "code"], "manim_render": False,
        }
        r = client.post("/api/v1/artifacts/generate/multi", json=body)
        assert r.status_code == 200
        data = r.json()
        assert data["types_requested"] == ["code"]


# ================================================================
# GET /list /info /download /data-uri
# ================================================================
class TestDownloadAndList:
    def test_list_after_generation(self, client: TestClient):
        # 先生成一个
        client.post(
            "/api/v1/artifacts/generate/mermaid",
            json={"title": "X", "branches": ["a", "b"]},
        )
        r = client.get("/api/v1/artifacts/list")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] >= 1
        assert any(a["type"] == "mermaid_png" for a in d["artifacts"])

    def test_list_filter_by_type(self, client: TestClient):
        client.post(
            "/api/v1/artifacts/generate/pptx",
            json={"title": "X", "slides": []},
        )
        r = client.get(
            "/api/v1/artifacts/list", params={"artifact_type": "pptx"},
        )
        assert r.status_code == 200
        d = r.json()
        assert all(a["type"] == "pptx" for a in d["artifacts"])

    def test_info_404_for_unknown(self, client: TestClient):
        r = client.get("/api/v1/artifacts/info/nonexistent_rid")
        assert r.status_code == 404

    def test_download_pptx_404(self, client: TestClient):
        r = client.get("/api/v1/artifacts/missing/pptx")
        assert r.status_code == 404


# ================================================================
# /metrics
# ================================================================
class TestMetrics:
    def test_prometheus_endpoint(self, client: TestClient):
        r = client.get("/api/v1/metrics")
        assert r.status_code == 200
        text = r.text
        # 预注册指标必有
        assert "llm_calls_total" in text
        assert "artifact_generated_total" in text
        assert "# TYPE" in text

    def test_summary_endpoint(self, client: TestClient):
        r = client.get("/api/v1/metrics/summary")
        assert r.status_code == 200
        d = r.json()
        assert "uptime_seconds" in d
        assert "artifacts" in d
        assert "llm" in d
        assert "by_type" in d["artifacts"]

    def test_health_endpoint(self, client: TestClient):
        r = client.get("/api/v1/metrics/health")
        assert r.status_code == 200
        d = r.json()
        assert "status" in d
        assert d["status"] in ("ok", "degraded")
        # 5 大子系统都应被检查
        for key in [
            "mermaid_studio", "pptx_builder", "code_sandbox",
            "tts_xunfei", "reflector",
        ]:
            assert key in d["checks"], f"health 应检查 {key}"
