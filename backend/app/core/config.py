"""
应用配置中心
迁移自旧项目 core/config.py，新增 LLM / RAG / 多智能体 配置项
"""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

_dotenv_loaded = False

# DeepSeek 于 2026-07-24 弃用 deepseek-chat / deepseek-reasoner 两个模型名。
# 为兼容评审环境中仍配置旧名称的 .env，运行时自动映射到新模型名。
# 旧模型名兼容到当前 Flash 模型；思考模式由调用参数单独决定。
_DEEPSEEK_MODEL_ALIASES = {
    "deepseek-chat": "deepseek-flash",
    "deepseek-reasoner": "deepseek-flash",
    "deepseek-v4-flash": "deepseek-flash",
}


def _normalize_deepseek_model(name: str) -> str:
    key = (name or "").strip()
    return _DEEPSEEK_MODEL_ALIASES.get(key, key)


def _ensure_dotenv():
    global _dotenv_loaded
    if not _dotenv_loaded:
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        _dotenv_loaded = True


def _project_root() -> Path:
    """项目根目录"""
    return Path(__file__).resolve().parents[3]


@dataclass
class LLMConfig:
    """大模型配置 —— 支持 DeepSeek(默认) / 讯飞星火 / 通用 OpenAI 兼容接口"""
    # LLM 提供商显式控制：deepseek / spark / openai_compatible / none
    # 不再因 spark 凭证存在就自动切换 LLM，TTS/Video 用独立凭证
    provider_override: str = ""  # 由 LLM_PROVIDER 环境变量控制

    # 讯飞星火配置（仅当 LLM_PROVIDER=spark 时用于 LLM）
    spark_app_id: str = ""
    spark_api_key: str = ""
    spark_api_secret: str = ""
    spark_domain: str = "generalv3.5"  # 星火版本: general / generalv3 / generalv3.5
    spark_url: str = "wss://spark-api.xf-yun.com/v3.5/chat"

    # 讯飞图像理解（OCR 用）—— 复用 SPARK_APP_ID / API_KEY / API_SECRET
    spark_image_url: str = "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"
    spark_image_domain: str = "imagev3"  # general | imagev3

    # OpenAI 兼容接口（DeepSeek / 通义 / Kimi 等）
    openai_base_url: str = "https://api.deepseek.com/v1"
    # Secrets must only be injected through the environment or a deployment
    # secret manager. Never add a provider key as a source-code default.
    openai_api_key: str = ""
    openai_model: str = "deepseek-flash"
    openai_extra_body: dict = field(default_factory=dict)

    # 通用参数
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 300

    @classmethod
    def from_env(cls) -> "LLMConfig":
        _ensure_dotenv()
        return cls(
            provider_override=os.getenv("LLM_PROVIDER", "").strip().lower(),
            spark_app_id=os.getenv("SPARK_APP_ID", ""),
            spark_api_key=os.getenv("SPARK_API_KEY", ""),
            spark_api_secret=os.getenv("SPARK_API_SECRET", ""),
            spark_domain=os.getenv("SPARK_DOMAIN", "generalv3.5"),
            spark_url=os.getenv("SPARK_URL", "wss://spark-api.xf-yun.com/v3.5/chat"),
            spark_image_url=os.getenv(
                "SPARK_IMAGE_URL", "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"
            ),
            spark_image_domain=os.getenv("SPARK_IMAGE_DOMAIN", "imagev3"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=_normalize_deepseek_model(
                os.getenv("OPENAI_MODEL", "deepseek-flash")
            ),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            timeout=int(os.getenv("LLM_TIMEOUT", "300")),
        )

    @property
    def provider(self) -> str:
        """确定当前使用的 LLM 提供商

        优先级：
        1. LLM_PROVIDER 环境变量显式指定（deepseek / spark / none）
        2. A3_OFFLINE_DEMO=1 → none
        3. 有 spark 凭证 → spark（向后兼容）
        4. 有 openai 配置 → openai_compatible
        5. 都没有 → none
        """
        _ensure_dotenv()
        if os.getenv("A3_OFFLINE_DEMO", "").lower() in ("1", "true"):
            return "none"
        # 显式指定优先
        if self.provider_override:
            if self.provider_override == "deepseek":
                return "openai_compatible"
            if self.provider_override in ("spark", "openai_compatible", "none"):
                return self.provider_override
        # 向后兼容：无显式指定时，有 spark 凭证就用 spark
        if self.spark_app_id and self.spark_api_key:
            return "spark"
        if self.openai_base_url and self.openai_api_key:
            return "openai_compatible"
        return "none"


@dataclass
class KimiConfig:
    """PPT 专用 Kimi/OpenAI-compatible 接入配置。

    该配置与全局 DeepSeek、讯飞 Spark 配置隔离，避免 PPT 生成误切换其它
    Agent 的推理模型。``base_url`` 可以填写 Moonshot 地址，也可以填写
    讯飞 MaaS 的 OpenAI-compatible HTTP 地址；模型名由对应控制台提供。
    """

    api_key: str = ""
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = ""
    timeout: int = 600

    @classmethod
    def from_env(cls) -> "KimiConfig":
        _ensure_dotenv()
        return cls(
            api_key=os.getenv("KIMI_API_KEY", "").strip(),
            base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1").strip(),
            model=os.getenv("KIMI_MODEL", "").strip(),
            timeout=int(os.getenv("KIMI_TIMEOUT", "600")),
        )

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


@dataclass
class XunfeiConfig:
    """讯飞配置

    与 LLMConfig 分离：
    - LLM 思考用 DeepSeek（由 LLM_PROVIDER=deepseek 控制）
    - TTS 用讯飞（用独立凭证 XUNFEI_TTS_*）
    - 数字人视频用讯飞（用独立凭证 XUNFEI_VID_*）
    - 向后兼容：若无独立凭证，回退到 SPARK_* 凭证
    """
    # TTS 语音合成凭证（优先使用独立凭证）
    tts_app_id: str = ""
    tts_api_key: str = ""
    tts_api_secret: str = ""

    # 数字人视频生成凭证
    vid_app_id: str = ""
    vid_api_key: str = ""
    vid_api_secret: str = ""
    vid_timeout: int = 180

    @classmethod
    def from_env(cls) -> "XunfeiConfig":
        _ensure_dotenv()
        # TTS 凭证：优先 XUNFEI_TTS_*，回退 SPARK_*
        tts_app = os.getenv("XUNFEI_TTS_APP_ID", "") or os.getenv("SPARK_APP_ID", "")
        tts_key = os.getenv("XUNFEI_TTS_API_KEY", "") or os.getenv("SPARK_API_KEY", "")
        tts_sec = os.getenv("XUNFEI_TTS_API_SECRET", "") or os.getenv("SPARK_API_SECRET", "")
        # 数字人视频凭证
        vid_app = os.getenv("XUNFEI_VID_APP_ID", "")
        vid_key = os.getenv("XUNFEI_VID_API_KEY", "")
        vid_sec = os.getenv("XUNFEI_VID_API_SECRET", "")
        vid_timeout = int(os.getenv("XUNFEI_VID_TIMEOUT", "180"))
        return cls(
            tts_app_id=tts_app,
            tts_api_key=tts_key,
            tts_api_secret=tts_sec,
            vid_app_id=vid_app,
            vid_api_key=vid_key,
            vid_api_secret=vid_sec,
            vid_timeout=vid_timeout,
        )

    @property
    def tts_available(self) -> bool:
        return bool(self.tts_app_id and self.tts_api_key and self.tts_api_secret)

    @property
    def vid_available(self) -> bool:
        """数字人视频 API 是否可用"""
        return bool(self.vid_app_id and self.vid_api_key and self.vid_api_secret)


@dataclass
class RAGConfig:
    """RAG 检索增强生成配置"""
    # 向量数据库
    vector_db_type: str = "chroma"  # chroma / faiss
    vector_db_path: str = ""  # 默认在 project_root/data/vector_store

    # Embedding
    # Enterprise deployments use an OpenAI-compatible cloud embedding endpoint.
    # The legacy local vector-store setting remains for offline demos.
    embedding_model: str = ""
    embedding_dim: int = 1024

    # 检索参数
    default_top_k: int = 5
    chunk_size: int = 2000
    chunk_overlap: int = 200

    # 课程知识库路径
    knowledge_base_path: str = ""  # 默认在 project_root/knowledge_base

    @classmethod
    def from_env(cls) -> "RAGConfig":
        _ensure_dotenv()
        root = _project_root()
        return cls(
            vector_db_type=os.getenv("VECTOR_DB_TYPE", "chroma"),
            vector_db_path=os.getenv("VECTOR_DB_PATH", str(root / "data" / "vector_store")),
            embedding_model=os.getenv("EMBEDDING_MODEL", ""),
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
            default_top_k=int(os.getenv("RAG_TOP_K", "5")),
            chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "2000")),
            chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "200")),
            knowledge_base_path=os.getenv("KNOWLEDGE_BASE_PATH", str(root / "knowledge_base")),
        )


@dataclass
class AppConfig:
    """应用全局配置"""
    app_name: str = "A3 个性化学习智能体系统"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # 会话管理
    session_max_age: int = 7200  # 2小时
    max_history_turns: int = 20  # 保留最近20轮对话

    # 学习画像维度（标准 8 维，满足赛题要求）
    profile_dimensions: list = field(default_factory=lambda: [
        "knowledge_base",       # 知识基础
        "cognitive_style",      # 认知风格
        "error_pattern",        # 易错倾向
        "learning_habit",       # 学习习惯
        "learning_progress",    # 学习进度
        "interest_model",       # 兴趣目标
        "resource_preference",  # 资源偏好
        "self_learning_ability",  # 自主学习能力
    ])

    # 课程配置
    default_course: str = "artificial_intelligence"

    llm: LLMConfig = field(default_factory=LLMConfig)
    kimi: KimiConfig = field(default_factory=KimiConfig)
    xunfei: XunfeiConfig = field(default_factory=XunfeiConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        _ensure_dotenv()
        return cls(
            debug=os.getenv("DEBUG", "false").lower() == "true",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            default_course=os.getenv("DEFAULT_COURSE", "artificial_intelligence"),
            llm=LLMConfig.from_env(),
            kimi=KimiConfig.from_env(),
            xunfei=XunfeiConfig.from_env(),
            rag=RAGConfig.from_env(),
        )


# 全局单例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config
