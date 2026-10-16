"""Plan D · 2.4 — Manim 三级降级补强：Mermaid + TTS 双轨兜底。

覆盖：
- /multi-with-fallback 在 manim 不可用时，metadata.fallback_assets 触发
  mermaid + tts 双轨兜底
- fallback_assets.used / reason / method 字段齐全
- mermaid / tts 各自 success 时把字段透传到 envelope
- 单边失败（mermaid 挂 / tts 挂）不阻塞另一边
- include_manim=false 时不触发兜底
- /multi 原始端点**不被破坏**（Plan D 设计原则：尽量不动已有代码）
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
    from backend.app.api.v1.artifacts import router as artifacts_router

    a = FastAPI()
    a.include_router(artifacts_router, prefix="/api/v1")
    return a


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_registry():
    from backend.app.api.v1.artifacts.registry import get_artifact_registry
    get_artifact_registry().clear()
    yield


def _post_rich(client: TestClient, **overrides):
    body = {
        "topic": "Transformer Self-Attention",
        "types": ["manim"],
        "kp_id": "self_attention",
        "bloom_level": "apply",
        "include_manim": False,
    }
    body.update(overrides)
    return client.post("/api/v1/artifacts/generate/multi-with-fallback", json=body)


# ============================================================
# 1) 原始 /multi 端点没有被破坏（Plan D 设计红线）
# ============================================================
class TestOriginalMultiNotTouched:
    def test_original_multi_endpoint_intact(self, client: TestClient):
        """Plan D · 2.4 — 原 /generate/multi 行为完全不变"""
        r = client.post(
            "/api/v1/artifacts/generate/multi",
            json={"topic": "RNN", "types": ["mermaid"]},
        )
        assert r.status_code == 200
        data = r.json()
        # 原 envelope 五件套
        for type_name, env in data["results"].items():
            for key in ("evidence", "cov", "safety", "downloads", "metadata"):
                assert key in env

    def test_original_multi_manim_has_no_fallback_assets(self, client: TestClient):
        """原 /multi 的 manim envelope 不应有 fallback_assets 字段（不污染）"""
        r = client.post(
            "/api/v1/artifacts/generate/multi",
            json={"topic": "X", "types": ["manim"], "include_manim": False},
        )
        assert r.status_code == 200
        env = r.json()["results"]["manim"]
        # 原 /multi 不应有 fallback_assets
        assert "fallback_assets" not in env.get("metadata", {})


# ============================================================
# 2) 新端点基本行为
# ============================================================
class TestRichEndpoint:
    def test_no_manim_skips_fallback(self, client: TestClient):
        """不含 manim 类型时，新端点等价于原 /multi"""
        r = client.post(
            "/api/v1/artifacts/generate/multi-with-fallback",
            json={"topic": "RNN", "types": ["mermaid"]},
        )
        assert r.status_code == 200
        data = r.json()
        # 没有 manim → results 不应有 manim 字段
        assert "manim" not in data.get("results", {})

    def test_rich_returns_evidence_cov_safety(self, client: TestClient):
        """新端点必须保留 P1-5 五件套"""
        r = _post_rich(client)
        assert r.status_code == 200
        env = r.json()["results"]["manim"]
        for key in ("evidence", "cov", "safety", "downloads", "metadata"):
            assert key in env


# ============================================================
# 3) fallback_assets 字段
# ============================================================
class TestFallbackAssets:
    def test_fallback_assets_keys_present_when_needed(self, client: TestClient):
        """include_manim=true 时若 manim 不可用，fallback_assets 五字段齐全"""
        r = _post_rich(client, include_manim=True)
        assert r.status_code == 200
        env = r.json()["results"]["manim"]
        meta = env["metadata"]
        assert "fallback_assets" in meta, (
            f"fallback_assets missing, got keys: {list(meta.keys())}"
        )
        fa = meta["fallback_assets"]
        for key in ("used", "reason", "method", "mermaid", "tts"):
            assert key in fa

    def test_code_only_skips_fallback(self, client: TestClient):
        """include_manim=false → fallback_assets.used 应为 False"""
        r = _post_rich(client, include_manim=False)
        assert r.status_code == 200
        env = r.json()["results"]["manim"]
        fa = env["metadata"].get("fallback_assets")
        # 如果 include_manim=False，fallback_assets 应该 used=False
        if fa:
            assert fa["used"] is False

    def test_fallback_reason_is_known_value(self, client: TestClient):
        """触发兜底时，reason 必须在已知集合内"""
        r = _post_rich(client, include_manim=True)
        env = r.json()["results"]["manim"]
        fa = env["metadata"].get("fallback_assets", {})
        if fa.get("used"):
            assert fa["reason"] in {
                "manim_render_failed",
                "manim_fell_back_to_placeholder",
            }


# ============================================================
# 4) _trim_envelope 工具函数
# ============================================================
class TestTrimHelper:
    def test_trim_drops_evidence_cov_safety(self):
        """Plan D · 2.4 — _trim_envelope 去掉重复字段"""
        from backend.app.api.v1.artifacts.multi import ResourceEnvelope
        from backend.app.api.v1.artifacts.multi_with_fallback import _trim_envelope

        env = ResourceEnvelope(
            success=True, type="mermaid", content="x" * 1500,
            filepath="/tmp/x.svg",
            evidence=[{"type": "rag_chunk"}],
            cov={"checked": True}, safety={"checked": True},
            downloads=[{"id": "y"}], metadata={"kp_id": "z"},
        )
        trimmed = _trim_envelope(env)
        # 透传
        assert trimmed["type"] == "mermaid"
        assert trimmed["success"] is True
        assert trimmed["filepath"] == "/tmp/x.svg"
        # content 截到 600
        assert len(trimmed["content_preview"]) == 600
        # downloads 透传
        assert trimmed["downloads"] == [{"id": "y"}]
        # evidence / cov / safety 不进 fallback
        assert "evidence" not in trimmed
        assert "cov" not in trimmed
        assert "safety" not in trimmed


# ============================================================
# 5) 兜底链单边失败的容错
# ============================================================
class TestFallbackResilience:
    def test_fallback_chain_survives_mermaid_failure(self, client: TestClient, monkeypatch):
        """mermaid 失败时，tts 仍能拿到"""
        from backend.app.api.v1.artifacts import multi as multi_mod
        from backend.app.api.v1.artifacts.multi_with_fallback import (
            _build_manim_fallback,
        )

        async def fake_gen_mermaid(req):
            raise RuntimeError("simulated mermaid failure")

        async def fake_gen_tts(req):
            return multi_mod.ResourceEnvelope(
                success=True, type="tts", content="narration",
                filepath="/tmp/narration.mp3",
            )

        monkeypatch.setattr(multi_mod, "_gen_mermaid", fake_gen_mermaid)
        monkeypatch.setattr(multi_mod, "_gen_tts", fake_gen_tts)

        req = multi_mod.MultiResourceRequest(
            topic="X", types=["manim"], include_manim=True,
        )
        # 直接构造失败的 manim envelope
        manim_env = multi_mod.ResourceEnvelope(
            success=False, type="manim", error="forced",
        )
        fallback = asyncio_run(_build_manim_fallback(manim_env, req))
        assert fallback["used"] is True
        assert fallback["mermaid"] is None  # mermaid 挂了
        assert fallback["tts"] is not None
        assert fallback["tts"]["type"] == "tts"


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
