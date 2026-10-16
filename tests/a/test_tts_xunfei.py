"""
测试: TTS 讯飞语音合成 (P1-6)

覆盖:
- SynthesisParams / SynthesisResult 数据模型
- TTSValidator: 音色/参数/文本校验
- TTSCache: 缓存命中/未命中/过期
- VoiceCatalog: 音色列表完整性
- XunfeiTTSService.synthesize(): 降级链 / 错误参数
"""
from __future__ import annotations

import ssl
import sys
from types import SimpleNamespace

import certifi
import pytest

import backend.app.services.multimodal.tts_xunfei as tts_module
from backend.app.services.multimodal.tts_xunfei import (
    _EDGE_VOICE_MAP,
    _EDGE_VOICE_PROFILE,
    DEFAULT_VOICE,
    MAX_TEXT_LENGTH,
    VOICE_CATALOG,
    EdgeTTSSynthesizer,
    MockSynthesizer,
    SynthesisParams,
    SynthesisResult,
    TTSCache,
    TTSValidator,
    XunfeiTTSClient,
    XunfeiTTSService,
    _create_verified_ssl_context,
    _load_edge_tts_module,
    get_tts_service,
    reset_tts_service,
)

_ORIGINAL_XUNFEI_SYNTHESIZE = XunfeiTTSClient.synthesize


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # 单元测试不访问真实语音供应商；网络链路由单独的诊断测试覆盖。
    monkeypatch.setattr(
        EdgeTTSSynthesizer,
        "synthesize",
        staticmethod(lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(
        XunfeiTTSClient,
        "synthesize",
        lambda self, *args, **kwargs: None,
    )
    reset_tts_service()


# ================================================================
# SynthesisParams
# ================================================================
class TestSynthesisParams:
    def test_defaults(self):
        p = SynthesisParams()
        assert p.voice == DEFAULT_VOICE
        assert p.speed == 50
        assert p.volume == 50
        assert p.pitch == 50

    def test_custom(self):
        p = SynthesisParams(voice="xiaofeng", speed=60, volume=80)
        assert p.voice == "xiaofeng"
        assert p.speed == 60


# ================================================================
# SynthesisResult
# ================================================================
class TestSynthesisResult:
    def test_success(self):
        r = SynthesisResult(filepath="/tmp/test.mp3", method="xunfei", voice="xiaoyan")
        assert r.success is True
        d = r.to_dict()
        assert d["method"] == "xunfei"

    def test_failure(self):
        r = SynthesisResult(error="no_credentials")
        assert r.success is False
        assert r.filepath == ""

    def test_cached(self):
        r = SynthesisResult(filepath="/tmp/cached.mp3", method="cache", cached=True)
        assert r.cached is True


# ================================================================
# TTSValidator
# ================================================================
class TestTTSValidator:
    def test_valid_params(self):
        errors = TTSValidator.validate_params(SynthesisParams())
        assert errors == []

    def test_invalid_voice(self):
        errors = TTSValidator.validate_params(SynthesisParams(voice="robot_999"))
        assert any("音色" in e for e in errors)

    def test_speed_out_of_range(self):
        errors = TTSValidator.validate_params(SynthesisParams(speed=150))
        assert any("speed" in e.lower() for e in errors)

    def test_volume_out_of_range(self):
        errors = TTSValidator.validate_params(SynthesisParams(volume=-10))
        assert any("volume" in e.lower() for e in errors)

    def test_empty_text(self):
        error = TTSValidator.validate_text("")
        assert error is not None
        assert "空" in error

    def test_text_too_long(self):
        error = TTSValidator.validate_text("A" * (MAX_TEXT_LENGTH + 1))
        assert error is not None
        assert "过长" in error

    def test_valid_text(self):
        error = TTSValidator.validate_text("你好世界")
        assert error is None


# ================================================================
# VoiceCatalog
# ================================================================
class TestVoiceCatalog:
    def test_at_least_3_voices(self):
        assert len(VOICE_CATALOG) >= 3

    def test_all_have_required_fields(self):
        for vid, v in VOICE_CATALOG.items():
            assert "name" in v
            assert "gender" in v
            assert "style" in v
            assert "description" in v

    def test_list_voices(self):
        voices = XunfeiTTSService.list_voices()
        assert len(voices) == len(VOICE_CATALOG)
        assert voices[0]["id"] in VOICE_CATALOG

    def test_every_agent_voice_has_edge_fallback_and_tuned_profile(self):
        assert set(VOICE_CATALOG) <= set(_EDGE_VOICE_MAP)
        assert set(VOICE_CATALOG) <= set(_EDGE_VOICE_PROFILE)
        assert _EDGE_VOICE_MAP["xiaokun"] == "zh-CN-YunxiNeural"


class TestTTSCacheKey:
    def test_voice_parameters_produce_distinct_cache_keys(self):
        normal = TTSCache._key("同一段讲解", "xiaokun")
        tuned = TTSCache._key("同一段讲解", "xiaokun", 47, 62, 48)
        assert normal != tuned

    def test_natural_engine_does_not_reuse_rigid_voice_cache(self):
        normal = TTSCache._key("同一段讲解", "xiaokun")
        natural = TTSCache._key(
            "同一段讲解", "xiaokun", 50, 50, 50, "natural-neural-v1",
        )
        assert normal != natural


# ================================================================
# SSL 兼容
# ================================================================
class TestSSLCompatibility:
    def test_verified_context_uses_certifi_bundle(self, monkeypatch):
        captured = {}
        sentinel = object()

        def fake_create_context(*, purpose, cafile, capath, cadata):
            captured.update({
                "purpose": purpose,
                "cafile": cafile,
                "capath": capath,
                "cadata": cadata,
            })
            return sentinel

        monkeypatch.setattr(
            tts_module, "_SYSTEM_CREATE_DEFAULT_CONTEXT", fake_create_context,
        )

        assert _create_verified_ssl_context() is sentinel
        assert captured["purpose"] is ssl.Purpose.SERVER_AUTH
        assert captured["cafile"] == certifi.where()
        assert captured["capath"] is None
        assert captured["cadata"] is None

    def test_edge_loader_catches_ssl_import_error_and_restores_factory(self, monkeypatch):
        original_factory = tts_module.ssl.create_default_context
        monkeypatch.setattr(tts_module, "_EDGE_TTS_IMPORT_ATTEMPTED", False)
        monkeypatch.setattr(tts_module, "_EDGE_TTS_MODULE", None)

        def fail_import(name):
            assert name == "edge_tts"
            assert (
                tts_module.ssl.create_default_context
                is tts_module._create_verified_ssl_context
            )
            raise ssl.SSLError("simulated Windows certificate-store failure")

        monkeypatch.setattr(tts_module.importlib, "import_module", fail_import)

        assert _load_edge_tts_module() is None
        assert tts_module.ssl.create_default_context is original_factory

    def test_xunfei_websocket_receives_verified_context(self, monkeypatch):
        captured = {}
        sentinel_context = object()

        class FakeWebSocketApp:
            def __init__(self, url, **callbacks):
                captured["url"] = url

            def run_forever(self, **kwargs):
                captured["run_kwargs"] = kwargs

        monkeypatch.setitem(
            sys.modules,
            "websocket",
            SimpleNamespace(WebSocketApp=FakeWebSocketApp),
        )
        monkeypatch.setattr(
            tts_module,
            "_create_verified_ssl_context",
            lambda: sentinel_context,
        )

        client = XunfeiTTSClient("app", "key", "secret")
        assert (
            _ORIGINAL_XUNFEI_SYNTHESIZE(
                client, "测试", SynthesisParams(), timeout=1,
            )
            is None
        )
        assert captured["run_kwargs"]["sslopt"]["context"] is sentinel_context


# ================================================================
# MockSynthesizer
# ================================================================
class TestMockSynthesizer:
    def test_creates_file(self, tmp_path):
        import os
        # 使用临时目录
        rid = "test_mock_001"
        fp = MockSynthesizer.synthesize("hello", rid)
        assert os.path.exists(fp)
        assert os.path.getsize(fp) > 0

    def test_idempotent(self):
        rid = "test_mock_002"
        fp1 = MockSynthesizer.synthesize("hello", rid)
        fp2 = MockSynthesizer.synthesize("hello", rid)
        assert fp1 == fp2  # 不重复创建


# ================================================================
# XunfeiTTSService 集成
# ================================================================
class TestXunfeiTTSService:
    def test_service_created(self):
        tts = get_tts_service()
        assert tts is not None

    def test_invalid_voice(self):
        tts = get_tts_service()
        result = tts.synthesize("测试文本", "test_001", voice="invalid_voice")
        assert not result.success
        assert "invalid" in result.error.lower() or "音色" in result.error

    def test_empty_text(self):
        tts = get_tts_service()
        result = tts.synthesize("", "test_001")
        assert not result.success
        assert result.method == "invalid_text"

    def test_mock_fallback(self):
        """当讯飞不可用时，Mock 降级生成静音 MP3"""
        tts = get_tts_service()
        result = tts.synthesize("测试文本", "test_mock_003")
        # 如果讯飞未配置，走 mock
        if result.method == "mock":
            assert result.success is True
            assert result.filepath

    def test_result_to_dict(self):
        tts = get_tts_service()
        result = tts.synthesize("测试", "test_dict")
        d = result.to_dict()
        assert "filepath" in d
        assert "method" in d
        assert "duration_ms" in d

    def test_singleton(self):
        t1 = get_tts_service()
        t2 = get_tts_service()
        assert t1 is t2
