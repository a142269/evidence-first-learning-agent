"""
TTS 讯飞语音合成 — WebSocket 流式版 v3 (Phase 1 重构)

设计:
    - VoiceCatalog: 8 种预置音色 + 自定义参数
    - SynthesisRequest: Pydantic-style 请求模型，参数校验
    - SynthesisResult: 标准化输出（路径 / 方法 / 耗时）
    - 降级链: 讯飞 WebSocket → 离线 Mock (回显文本)
    - MP3 缓存: 同文本+同音色命中缓存直接返回

API 参考:
    讯飞 TTS WebAPI v2: https://www.xfyun.cn/doc/tts/online_tts/API.html

Phase 2 计划:
    - 接入 Viseme (嘴型同步数据)
    - 接入情感语音 (emotion 参数)
    - 流式 chunk 输出 (不等待全部合成完)
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import importlib
import json
import logging
import os
from pathlib import Path
import ssl
from threading import Lock, Thread
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import certifi

logger = logging.getLogger(__name__)

# ================================================================
# 常量
# ================================================================
ARTIFACTS_DIR = Path("data/artifacts/mp3")
TTS_HOST = "tts-api.xfyun.cn"
TTS_PATH = "/v2/tts"
TTS_URL = f"wss://{TTS_HOST}{TTS_PATH}"

# 音色库
VOICE_CATALOG: Dict[str, Dict[str, Any]] = {
    "xiaoyan": {
        "name": "小燕", "gender": "female", "style": "标准女声",
        "description": "青年女声，适合教学讲解",
        "recommended_for": ["讲解", "答疑", "朗读"],
    },
    "xiaofeng": {
        "name": "小峰", "gender": "male", "style": "标准男声",
        "description": "青年男声，适合正式讲解",
        "recommended_for": ["课程", "讲座"],
    },
    "xiaoxin": {
        "name": "小新", "gender": "female", "style": "活泼童声",
        "description": "活泼童声，适合轻松场景",
        "recommended_for": ["趣味问答", "游戏化"],
    },
    "xiaoqian": {
        "name": "小倩", "gender": "female", "style": "温柔女声",
        "description": "温柔女声，适合辅导安慰",
        "recommended_for": ["辅导", "鼓励"],
    },
    "xiaokun": {
        "name": "小坤", "gender": "male", "style": "成熟男声",
        "description": "成熟男声，适合学术讲解",
        "recommended_for": ["论文朗读", "深度讲解"],
    },
    "xiaomeng": {
        "name": "小萌", "gender": "female", "style": "甜美女声",
        "description": "甜美女声，适合轻松学习",
        "recommended_for": ["入门课程", "儿童教育"],
    },
    "laowang": {
        "name": "老王", "gender": "male", "style": "幽默男声",
        "description": "幽默男声，适合段子手风格",
        "recommended_for": ["趣味教学", "段子手"],
    },
    "zhixiang": {
        "name": "志祥", "gender": "male", "style": "严肃男声",
        "description": "严肃男声，适合正式场合",
        "recommended_for": ["考试说明", "正式通知"],
    },
}

DEFAULT_VOICE = "xiaoyan"
MAX_TEXT_LENGTH: int = 800          # 讯飞限制: 单次最多 800 字符
CACHE_ENABLED: bool = True
CACHE_MAX_AGE: float = 86400        # 缓存 24 小时


# Python 3.10 + 部分新版 Conda/OpenSSL 组合在 Windows 上读取系统证书库时，
# 可能把 DER 证书交给 OpenSSL 后触发 ASN1: NOT_ENOUGH_DATA。显式使用
# certifi 的 PEM CA bundle 可避开该运行时兼容问题，同时继续进行严格证书校验。
_SYSTEM_CREATE_DEFAULT_CONTEXT = ssl.create_default_context


def _create_verified_ssl_context(
    purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH,
    *,
    cafile: Optional[str] = None,
    capath: Optional[str] = None,
    cadata: Any = None,
) -> ssl.SSLContext:
    if cafile is None and capath is None and cadata is None:
        cafile = certifi.where()
    return _SYSTEM_CREATE_DEFAULT_CONTEXT(
        purpose=purpose,
        cafile=cafile,
        capath=capath,
        cadata=cadata,
    )


# ================================================================
# 数据模型
# ================================================================
@dataclass
class SynthesisParams:
    """TTS 合成参数"""
    voice: str = DEFAULT_VOICE
    speed: int = 50          # 0-100，50 为正常
    volume: int = 50         # 0-100
    pitch: int = 50          # 0-100


@dataclass
class SynthesisResult:
    """TTS 合成结果"""
    filepath: str = ""
    method: str = ""                # "xunfei" / "mock" / "cache" / "no_credentials"
    duration_ms: float = 0.0
    voice: str = DEFAULT_VOICE
    text_length: int = 0
    audio_size: int = 0             # bytes
    error: str = ""
    cached: bool = False

    @property
    def success(self) -> bool:
        return bool(self.filepath) and not self.error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": self.filepath,
            "method": self.method,
            "duration_ms": round(self.duration_ms, 1),
            "voice": self.voice,
            "text_length": self.text_length,
            "audio_size": self.audio_size,
            "cached": self.cached,
            "error": self.error,
        }


# ================================================================
# 参数校验器
# ================================================================
class TTSValidator:
    """TTS 参数校验"""

    @staticmethod
    def validate_params(params: SynthesisParams) -> List[str]:
        """校验参数，返回错误列表"""
        errors: List[str] = []

        if params.voice not in VOICE_CATALOG:
            errors.append(
                f"不支持的音色: {params.voice}，可选: {list(VOICE_CATALOG.keys())}"
            )

        for name, value, (lo, hi) in [
            ("speed", params.speed, (0, 100)),
            ("volume", params.volume, (0, 100)),
            ("pitch", params.pitch, (0, 100)),
        ]:
            if not (lo <= value <= hi):
                errors.append(f"{name} 参数超出范围 [{lo}, {hi}]: {value}")

        return errors

    @staticmethod
    def validate_text(text: str) -> Optional[str]:
        """校验文本，返回 None 或错误消息"""
        if not text or not text.strip():
            return "文本为空"
        if len(text) > MAX_TEXT_LENGTH:
            return f"文本过长 ({len(text)} > {MAX_TEXT_LENGTH})"
        return None


# ================================================================
# MP3 缓存
# ================================================================
class TTSCache:
    """TTS 结果缓存

    缓存键: hash(text + voice)
    """

    def __init__(self, max_age: float = CACHE_MAX_AGE):
        self._max_age = max_age
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    def get(
        self, text: str, voice: str,
        speed: int = 50, volume: int = 50, pitch: int = 50,
        engine_profile: str = "default",
    ) -> Optional[str]:
        """命中缓存返回文件路径，否则返回 None"""
        if not CACHE_ENABLED:
            return None

        cache_key = self._key(text, voice, speed, volume, pitch, engine_profile)
        cache_path = ARTIFACTS_DIR / f"_cache_{cache_key}.mp3"

        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age < self._max_age:
                logger.debug(f"[TTS] cache hit: {cache_key}")
                return str(cache_path)
            # 过期 → 删除
            try:
                cache_path.unlink()
            except OSError:
                pass

        return None

    def put(
        self, text: str, voice: str, filepath: str,
        speed: int = 50, volume: int = 50, pitch: int = 50,
        engine_profile: str = "default",
    ) -> None:
        """写入缓存"""
        if not CACHE_ENABLED:
            return

        cache_key = self._key(text, voice, speed, volume, pitch, engine_profile)
        cache_path = ARTIFACTS_DIR / f"_cache_{cache_key}.mp3"

        try:
            import shutil
            shutil.copy2(filepath, cache_path)
        except OSError as exc:
            logger.warning(f"[TTS] cache write failed: {exc}")

    @staticmethod
    def _key(
        text: str, voice: str,
        speed: int = 50, volume: int = 50, pitch: int = 50,
        engine_profile: str = "default",
    ) -> str:
        raw = f"{text}|{voice}|{speed}|{volume}|{pitch}"
        if engine_profile != "default":
            raw += f"|{engine_profile}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]


# ================================================================
# 讯飞 TTS WebSocket 客户端
# ================================================================
class XunfeiTTSClient:
    """讯飞 TTS WebSocket 底层客户端"""

    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
    ):
        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret

    @property
    def available(self) -> bool:
        return bool(self._app_id and self._api_key and self._api_secret)

    def synthesize(
        self, text: str, params: SynthesisParams, timeout: int = 15,
    ) -> Optional[bytes]:
        """通过 WebSocket 合成语音，返回原始音频字节

        Returns:
            音频字节 (MP3)，失败返回 None
        """
        if not self.available:
            return None

        try:
            import websocket
        except ImportError:
            logger.warning("[TTS] websocket-client 未安装")
            return None

        url = self._build_auth_url()
        payload = self._build_payload(text, params)
        chunks: List[bytes] = []
        errors: List[str] = []

        def on_message(ws, message: str) -> None:
            data = json.loads(message)
            code = data.get("code", -1)
            if code != 0:
                errors.append(f"API error code={code}")
                ws.close()
                return
            audio_b64 = data.get("data", {}).get("audio", "")
            if audio_b64:
                chunks.append(base64.b64decode(audio_b64))
            if data.get("data", {}).get("status") == 2:
                ws.close()

        def on_error(ws, error: Any) -> None:
            errors.append(str(error))

        def on_open(ws) -> None:
            ws.send(payload)

        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_open=on_open,
        )
        try:
            ssl_context = _create_verified_ssl_context()
        except Exception as exc:
            logger.warning("[TTS] 无法创建 certifi SSL 上下文: %s", exc)
            return None

        thread = Thread(
            target=lambda: ws.run_forever(sslopt={"context": ssl_context}),
            daemon=True,
        )
        thread.start()
        thread.join(timeout)

        if errors:
            logger.warning(f"[TTS] errors: {errors}")
            return None
        return b"".join(chunks) if chunks else None

    def _build_auth_url(self) -> str:
        now = datetime.utcnow()
        date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        signing_string = (
            f"host: {TTS_HOST}\ndate: {date}\nGET {TTS_PATH} HTTP/1.1"
        )
        signature = base64.b64encode(
            hmac.new(
                self._api_secret.encode(),
                signing_string.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()
        auth_origin = (
            f'api_key="{self._api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )
        auth = base64.b64encode(auth_origin.encode()).decode()
        params = urlencode({
            "authorization": auth,
            "date": date,
            "host": TTS_HOST,
        })
        return f"{TTS_URL}?{params}"

    def _build_payload(self, text: str, params: SynthesisParams) -> str:
        text_b64 = base64.b64encode(text.encode()).decode()
        # XUNFEI_TTS_VCN 允许整体替换讯飞发音人（例如控制台已授权的
        # aisjiuxu / x4 系列等更自然的音色），无需改动上层音色目录。
        # 值必须是当前 App 在“在线语音合成(流式)”里已授权的 vcn。
        vcn = os.getenv("XUNFEI_TTS_VCN", "").strip() or params.voice
        return json.dumps({
            "common": {"app_id": self._app_id},
            "business": {
                "aue": "lame",          # MP3
                "sfl": 1,               # 流式返回
                "vcn": vcn,
                "speed": params.speed,
                "volume": params.volume,
                "pitch": params.pitch,
                "tte": "UTF8",
            },
            "data": {
                "status": 2,            # 一次性合成
                "text": text_b64,
            },
        })


# ================================================================
# Edge-TTS 合成器（免费微软 TTS，无需 API Key）
# ================================================================
# 讯飞音色 → edge-tts 音色映射
_EDGE_VOICE_MAP: Dict[str, str] = {
    "xiaoyan": "zh-CN-XiaoxiaoNeural",
    "xiaofeng": "zh-CN-YunyangNeural",
    "xiaoxin": "zh-CN-XiaoyiNeural",
    "xiaoqian": "zh-CN-XiaoxiaoNeural",
    # 云希比新闻播报型云扬更自然，适合阿匠的课程视频旁白。
    "xiaokun": "zh-CN-YunxiNeural",
    "xiaomeng": "zh-CN-XiaoyiNeural",
    "laowang": "zh-CN-YunyangNeural",
    "zhixiang": "zh-CN-YunyangNeural",
}

# 针对教学旁白做轻量音色调校，避免默认回退成同一个女声。
_EDGE_VOICE_PROFILE: Dict[str, Tuple[int, int, int]] = {
    # rate %, volume %, pitch Hz
    "xiaoyan": (-3, 6, 1),
    "xiaofeng": (-2, 7, -1),
    "xiaoxin": (3, 5, 2),
    "xiaoqian": (-5, 5, 1),
    "xiaokun": (-1, 5, -1),
    "xiaomeng": (1, 5, 2),
    "laowang": (-1, 8, -3),
    "zhixiang": (-6, 8, -3),
}

_EDGE_TTS_IMPORT_LOCK = Lock()
_EDGE_TTS_IMPORT_ATTEMPTED = False
_EDGE_TTS_MODULE: Any = None


def _load_edge_tts_module() -> Any:
    """安全加载 edge-tts，并为其 aiohttp SSL 常量注入 certifi CA。

    aiohttp 会在导入阶段立即调用 ``ssl.create_default_context()``。如果当前
    Python/OpenSSL 无法读取 Windows 证书库，异常会发生在业务 try/except 之前。
    这里只在受导入锁保护的极短窗口内替换工厂函数，导入结束后立即恢复；由
    aiohttp/edge-tts 创建并缓存的 SSLContext 仍保持严格证书校验。
    """
    global _EDGE_TTS_IMPORT_ATTEMPTED, _EDGE_TTS_MODULE

    if _EDGE_TTS_IMPORT_ATTEMPTED:
        return _EDGE_TTS_MODULE

    with _EDGE_TTS_IMPORT_LOCK:
        if _EDGE_TTS_IMPORT_ATTEMPTED:
            return _EDGE_TTS_MODULE

        original_factory = ssl.create_default_context
        try:
            ssl.create_default_context = _create_verified_ssl_context
            _EDGE_TTS_MODULE = importlib.import_module("edge_tts")
        except Exception as exc:
            # ImportError 以外还可能是 aiohttp 导入阶段的 SSL/OpenSSL 异常。
            # 失败必须返回 None，让上层继续走讯飞或 Mock，不能中断整条视频链路。
            logger.warning("[TTS] edge-tts 加载失败，继续降级: %s", exc)
            _EDGE_TTS_MODULE = None
        finally:
            ssl.create_default_context = original_factory
            _EDGE_TTS_IMPORT_ATTEMPTED = True

    return _EDGE_TTS_MODULE


class EdgeTTSSynthesizer:
    """使用微软 edge-tts 生成真实语音（免费、无需 API Key）。

    作为讯飞 WebSocket 不可用时的第一降级方案，
    生成的 MP3 文件可以被浏览器直接播放。
    """

    @staticmethod
    def synthesize(
        text: str, resource_id: str, voice: str = "xiaoyan",
        speed: int = 50, volume: int = 50, pitch: int = 50,
    ) -> Optional[str]:
        """返回 MP3 文件路径，失败返回 None。"""
        import asyncio

        edge_tts = _load_edge_tts_module()
        if edge_tts is None:
            return None

        edge_voice = _EDGE_VOICE_MAP.get(voice, "zh-CN-XiaoxiaoNeural")
        base_rate, base_volume, base_pitch = _EDGE_VOICE_PROFILE.get(voice, (0, 5, 0))
        rate = max(-35, min(35, base_rate + round((speed - 50) * 0.6)))
        edge_volume = max(-30, min(40, base_volume + round((volume - 50) * 0.6)))
        edge_pitch = max(-20, min(20, base_pitch + round((pitch - 50) * 0.3)))
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        filepath = ARTIFACTS_DIR / f"{resource_id}_edge.mp3"

        try:
            async def _run():
                communicate = edge_tts.Communicate(
                    text,
                    edge_voice,
                    rate=f"{rate:+d}%",
                    volume=f"{edge_volume:+d}%",
                    pitch=f"{edge_pitch:+d}Hz",
                )
                await communicate.save(str(filepath))

            # 在同步上下文中运行 async edge-tts
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 已在事件循环中，用线程池跑
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        pool.submit(lambda: asyncio.run(_run())).result()
                else:
                    loop.run_until_complete(_run())
            except RuntimeError:
                asyncio.run(_run())

            if filepath.exists() and filepath.stat().st_size > 100:
                logger.info(f"[TTS] edge-tts saved: {filepath} ({filepath.stat().st_size} bytes)")
                return str(filepath)
            return None
        except Exception as exc:
            logger.warning(f"[TTS] edge-tts failed: {exc}")
            return None


# ================================================================
# 离线 Mock 合成器
# ================================================================
class MockSynthesizer:
    """离线 Mock TTS — 无需 API Key 也能返回结果

    生成一个最小 WAV 文件（1 秒静音），保证下载链路完整。
    使用 Python 内置 wave 模块，无需额外依赖。
    """

    @staticmethod
    def synthesize(text: str, resource_id: str) -> str:
        """返回 mock MP3 文件路径"""
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        filepath = ARTIFACTS_DIR / f"{resource_id}_mock.mp3"

        if not filepath.exists():
            # 生成有效的 WAV 文件（1 秒静音，44100Hz 16bit mono）
            import struct
            import wave
            wav_path = ARTIFACTS_DIR / f"{resource_id}_mock.wav"
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(44100)
                # 1 秒静音 = 44100 个采样点，每个 2 字节
                wf.writeframes(struct.pack("<" + "h" * 44100, *([0] * 44100)))
            # 返回 wav 路径而非 mp3（内容一致，扩展名适配浏览器播放）
            return str(wav_path)

        return str(filepath)


# ================================================================
# XunfeiTTSService — 统一入口
# ================================================================
class XunfeiTTSService:
    """讯飞 TTS 语音合成服务

    用法:
        tts = XunfeiTTSService()
        result = tts.synthesize("你好，欢迎学习CNN", resource_id="res_001")
        print(result.filepath)  # "data/artifacts/mp3/res_001.mp3"

    降级链:
        1. 缓存命中 → 直接返回
        2. 讯飞 WebSocket → 流式合成 MP3
        3. Mock 合成器 → 最小静音 MP3（保证链路完整）
    """

    def __init__(self):
        from backend.app.core.config import get_config

        # 优先使用独立的讯飞 TTS 凭证，回退到 spark 凭证
        try:
            xf = get_config().xunfei
            app_id = xf.tts_app_id
            api_key = xf.tts_api_key
            api_secret = xf.tts_api_secret
        except Exception:
            # 向后兼容：若 xunfei 配置不可用，回退到 llm spark 凭证
            cfg = get_config().llm
            app_id = cfg.spark_app_id
            api_key = cfg.spark_api_key
            api_secret = cfg.spark_api_secret

        self._client = XunfeiTTSClient(
            app_id=app_id,
            api_key=api_key,
            api_secret=api_secret,
        )
        self._cache = TTSCache()
        self._mock = MockSynthesizer()
        self._validator = TTSValidator()
        self._available = self._client.available

        os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    @property
    def available(self) -> bool:
        return self._available

    def synthesize(
        self,
        text: str,
        resource_id: str,
        voice: str = DEFAULT_VOICE,
        speed: int = 50,
        volume: int = 50,
        pitch: int = 50,
        prefer_natural: bool = False,
    ) -> SynthesisResult:
        """合成语音

        Args:
            text: 要合成的文本 (≤ 800 字符)
            resource_id: 资源标识符（用于文件命名）
            voice: 音色名 (xiaoyan/xiaofeng/...)
            speed: 语速 0-100
            volume: 音量 0-100
            pitch: 音调 0-100

        Returns:
            SynthesisResult
        """
        start = time.perf_counter()

        # 参数校验
        params = SynthesisParams(voice=voice, speed=speed, volume=volume, pitch=pitch)
        param_errors = self._validator.validate_params(params)
        if param_errors:
            return SynthesisResult(
                method="invalid_params",
                error="; ".join(param_errors),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        # 文本校验 + 截断
        text_error = self._validator.validate_text(text)
        if text_error:
            return SynthesisResult(
                method="invalid_text",
                error=text_error,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        text = text[:MAX_TEXT_LENGTH]

        # ---- Level 1: 缓存 ----
        engine_profile = "natural-neural-v1" if prefer_natural else "default"
        # 讯飞 vcn 被环境变量覆盖时并入缓存键，避免换音色后命中旧缓存。
        vcn_override = os.getenv("XUNFEI_TTS_VCN", "").strip()
        if vcn_override:
            engine_profile = f"{engine_profile}|vcn:{vcn_override}"
        cached = self._cache.get(
            text, voice, speed, volume, pitch, engine_profile,
        )
        if cached:
            return SynthesisResult(
                filepath=cached,
                method="cache",
                voice=voice,
                text_length=len(text),
                duration_ms=(time.perf_counter() - start) * 1000,
                cached=True,
            )

        # 视频旁白优先使用更具自然停连的神经网络音色；网络不可用时仍回退讯飞。
        if prefer_natural:
            edge_fp = EdgeTTSSynthesizer.synthesize(
                text, resource_id, voice, speed=speed, volume=volume, pitch=pitch,
            )
            if edge_fp:
                self._cache.put(
                    text, voice, edge_fp, speed, volume, pitch, engine_profile,
                )
                return SynthesisResult(
                    filepath=edge_fp,
                    method="edge-tts-natural",
                    voice=voice,
                    text_length=len(text),
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

        # ---- Level 2: 讯飞 WebSocket ----
        if self._client.available:
            audio = self._client.synthesize(text, params)
            if audio:
                filepath = self._save_audio(audio, resource_id)
                self._cache.put(
                    text, voice, filepath, speed, volume, pitch, engine_profile,
                )
                return SynthesisResult(
                    filepath=filepath,
                    method="xunfei",
                    voice=voice,
                    text_length=len(text),
                    audio_size=len(audio),
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

        # ---- Level 2.5: edge-tts 降级（免费微软 TTS，无需 API Key）----
        logger.info(f"[TTS] 讯飞不可用，尝试 edge-tts 降级")
        edge_fp = EdgeTTSSynthesizer.synthesize(
            text, resource_id, voice, speed=speed, volume=volume, pitch=pitch,
        )
        if edge_fp:
            self._cache.put(
                text, voice, edge_fp, speed, volume, pitch, engine_profile,
            )
            return SynthesisResult(
                filepath=edge_fp,
                method="edge-tts",
                voice=voice,
                text_length=len(text),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

        # ---- Level 3: Mock 降级 ----
        logger.info(f"[TTS] edge-tts 不可用，降级到 Mock")
        filepath = self._mock.synthesize(text, resource_id)
        return SynthesisResult(
            filepath=filepath,
            method="mock",
            voice=voice,
            text_length=len(text),
            duration_ms=(time.perf_counter() - start) * 1000,
        )

    @staticmethod
    def _save_audio(audio: bytes, resource_id: str) -> str:
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        fp = ARTIFACTS_DIR / f"{resource_id}.mp3"
        with open(fp, "wb") as f:
            f.write(audio)
        logger.info(f"[TTS] saved: {fp} ({len(audio)} bytes)")
        return str(fp)

    @staticmethod
    def list_voices() -> List[Dict[str, Any]]:
        """获取所有可用音色"""
        return [
            {
                "id": vid,
                "name": v["name"],
                "gender": v["gender"],
                "style": v["style"],
                "description": v["description"],
            }
            for vid, v in VOICE_CATALOG.items()
        ]


# ================================================================
# 全局单例
# ================================================================
_tts: Optional[XunfeiTTSService] = None


def get_tts_service() -> XunfeiTTSService:
    """获取 TTS 服务单例"""
    global _tts
    if _tts is None:
        _tts = XunfeiTTSService()
    return _tts


def reset_tts_service() -> None:
    """测试用：重置单例"""
    global _tts
    _tts = None
