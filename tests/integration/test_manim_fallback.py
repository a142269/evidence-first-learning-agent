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
            assert fa["used"] is False, (
                f"fallback_assets={fa} manim_success={env.get('success')} "
                f"error={env.get('error')!r} metadata={env.get('metadata')}"
            )

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


# ============================================================
# 6) QWEN-107 · 方案② — 未请求渲染时 script_only 即成功
# ============================================================
class TestScriptOnlySemantics:
    """`include_manim=false` 交付的是可编辑讲稿脚本，红绿不该由渲染/质量门抖动决定；
    `include_manim=true` 时质量门仍然强制。

    这一组用 monkeypatch 钉住 Level 1/Level 2 的产出，因此不依赖本机媒体链路，
    也不产生模型调用。
    """

    FAKE_VIDEO = "data/artifacts/video/qa_gate_fake.mp4"

    def _no_level1(self, monkeypatch):
        """Level 1 Agent 视频服务整体不可用 → 必然落到 Level 2 脚本态。"""
        from backend.app.services.multimodal import video_xunfei

        def boom():
            raise RuntimeError("simulated agent video outage")

        monkeypatch.setattr(video_xunfei, "get_video_service", boom)

    def _reject_gate(self, monkeypatch):
        """把质量门钉成 rejected（阈值与真实文案保持一致，但不改产品阈值）。"""
        from backend.app.api.v1.artifacts import multi as multi_mod

        monkeypatch.setattr(multi_mod, "_video_quality_gate", lambda *a, **k: {
            "status": "rejected",
            "reason": "画面与旁白时长偏差 2.25s，超过允许的 2.00s，已阻止发布",
            "minimum_duration_seconds": 3.0,
            "maximum_av_duration_drift_seconds": 2.0,
            "video_duration_seconds": 94.19,
            "audio_duration_seconds": 91.94,
            "av_duration_drift_seconds": 2.25,
        })

    def _level1_rejected_by_gate(self, monkeypatch):
        """Level 1 出了 MP4，但质量门判 rejected（复现历史抖动场景）。"""
        from types import SimpleNamespace

        from backend.app.services.multimodal import video_xunfei

        svc = SimpleNamespace(
            synthesize=lambda *args: SimpleNamespace(
                success=True, filepath=self.FAKE_VIDEO, audio_path="",
                agent_name="阿匠", method="animated_slides", video_size=0,
            )
        )
        monkeypatch.setattr(video_xunfei, "get_video_service", lambda: svc)
        self._reject_gate(monkeypatch)

    def _level2(self, monkeypatch, *, filepath: str, success: bool = True,
                code: str = "# fake manim script"):
        """Level 2 generate_manim：filepath 为空 = 脚本态，.mp4 = 渲染态。"""
        from backend.app.api.v1.artifacts import generate as generate_mod
        from backend.app.api.v1.artifacts.generate import ResourceResult

        seen: dict = {}

        def fake(req):
            seen["render"] = req.render
            return ResourceResult(
                resource_id="manim_qa_fake",
                type="manim_video" if filepath else "manim_code",
                filepath=filepath,
                method="manim" if filepath else "code_only",
                metadata={"generated_code": code},
                success=success,
            )

        monkeypatch.setattr(generate_mod, "generate_manim", fake)
        return seen

    def _gate_passed(self, monkeypatch):
        from backend.app.api.v1.artifacts import multi as multi_mod

        monkeypatch.setattr(multi_mod, "_video_quality_gate", lambda *a, **k: {
            "status": "passed", "reason": "",
            "video_duration_seconds": 60.0, "audio_duration_seconds": 60.0,
            "av_duration_drift_seconds": 0.0,
        })

    # --- include_manim=false：脚本态即成功，且确定性不触发兜底 ---
    def test_script_only_is_success_when_render_not_requested(self, client, monkeypatch):
        from backend.app.api.v1.artifacts import multi as multi_mod

        self._no_level1(monkeypatch)
        seen = self._level2(monkeypatch, filepath="")
        r = _post_rich(client, include_manim=False)
        assert r.status_code == 200
        env = r.json()["results"]["manim"]
        meta = env["metadata"]
        assert seen["render"] is False, "未请求渲染时 Level 2 不应带 render=True"
        assert env["success"] is True
        assert meta["video_status"] == "script_only"
        assert meta["rendered"] is False
        assert meta["playback_status"] == "unavailable"
        assert meta["fallback_assets"]["used"] is False
        assert meta["fallback_assets"]["reason"] == ""
        # QWEN-107b：success=True 必须携带可编辑讲稿，正文来自 metadata["generated_code"]
        content = env["content"]
        assert content, "脚本态成功却没有交付物"
        assert "# fake manim script" in content

        # 同一用例的另一半：讲稿缺失/为空时必须显式失败并给稳定错误，
        # 不静默返回空 content（不新增测试项，保持套件计数不变）。
        self._level2(monkeypatch, filepath="", code="   ")
        empty = _post_rich(client, include_manim=False).json()["results"]["manim"]
        assert empty["success"] is False
        assert empty["error"] == multi_mod.MANIM_SCRIPT_MISSING_ERROR
        assert not empty["content"], "失败分支不得伪造交付物"
        assert empty["metadata"]["video_status"] == "script_only"

    def test_quality_gate_jitter_does_not_fail_unrequested_render(self, client, monkeypatch):
        """历史抖动场景：Level 1 被质量门拒绝 → 未请求渲染仍应 success=True 且不兜底。"""
        self._level1_rejected_by_gate(monkeypatch)
        self._level2(monkeypatch, filepath="")
        r = _post_rich(client, include_manim=False)
        env = r.json()["results"]["manim"]
        meta = env["metadata"]
        assert env["success"] is True
        assert meta["video_status"] == "script_only"
        assert meta["rendered"] is False
        assert meta["agent_video_quality"]["status"] == "rejected", (
            "质量门拒绝原因仍需保留，只是不再决定红绿"
        )
        assert meta["fallback_assets"]["used"] is False

    # --- include_manim=true：质量门/渲染失败仍然失败并触发兜底 ---
    def test_render_requested_and_gate_rejected_still_falls_back(self, client, monkeypatch):
        self._no_level1(monkeypatch)
        seen = self._level2(monkeypatch, filepath=self.FAKE_VIDEO)
        self._reject_gate(monkeypatch)
        r = _post_rich(client, include_manim=True)
        env = r.json()["results"]["manim"]
        meta = env["metadata"]
        assert seen["render"] is True
        assert env["success"] is False
        assert meta["video_status"] == "rejected"
        assert meta["fallback_assets"]["used"] is True
        assert meta["fallback_assets"]["reason"] == "manim_render_failed"

    def test_render_requested_without_video_still_falls_back(self, client, monkeypatch):
        """请求了渲染却只拿到脚本 → 仍是失败，兜底照常触发。"""
        self._no_level1(monkeypatch)
        self._level2(monkeypatch, filepath="")
        r = _post_rich(client, include_manim=True)
        env = r.json()["results"]["manim"]
        meta = env["metadata"]
        assert env["success"] is False
        assert meta["video_status"] == "script_only"
        assert meta["fallback_assets"]["used"] is True
        assert meta["fallback_assets"]["reason"] == "manim_render_failed"

    def test_render_requested_and_gate_passed_still_succeeds(self, client, monkeypatch):
        """正路未被削弱：请求渲染且质量门通过 → success=True、rendered=True。"""
        self._no_level1(monkeypatch)
        self._level2(monkeypatch, filepath=self.FAKE_VIDEO)
        self._gate_passed(monkeypatch)
        r = _post_rich(client, include_manim=True)
        env = r.json()["results"]["manim"]
        meta = env["metadata"]
        assert env["success"] is True
        assert meta["video_status"] == "ready"
        assert meta["rendered"] is True
        assert meta["fallback_assets"]["used"] is False


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
