from __future__ import annotations

import os
from dataclasses import dataclass

MANUAL_MODELSCOPE_BASE_URL = "https://api.deepseek.com/v1"
# Kept as a named compatibility constant for callers, but intentionally
# empty: credentials are supplied by MODELSCOPE_API_KEY or an explicit input.
MANUAL_MODELSCOPE_API_KEY = ""
# DeepSeek 于 2026-07-24 弃用 deepseek-chat / deepseek-reasoner，
# 新模型名：deepseek-v4-flash（对应旧 chat/reasoner）/ deepseek-v4-pro
MANUAL_MODELSCOPE_MODEL_NAME = "deepseek-v4-flash"
MANUAL_MODELSCOPE_TIMEOUT = 720

# 若外部环境仍配置旧模型名，运行时自动映射到新名字，避免 model not found。
_DEEPSEEK_MODEL_ALIASES = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-flash",
}


def _clean(value: str) -> str:
    return str(value or "").strip().strip("`").strip('"').strip("'")


def _normalize_model(name: str) -> str:
    key = _clean(name)
    return _DEEPSEEK_MODEL_ALIASES.get(key, key)


@dataclass(frozen=True)
class LLMRuntimeConfig:
    base_url: str
    api_key: str
    model_name: str
    timeout: int = 720


def load_llm_runtime_config(
    base_url: str = "",
    api_key: str = "",
    model_name: str = "",
    timeout: int = 0,
) -> LLMRuntimeConfig:
    final_base_url = (
        _clean(base_url)
        or _clean(os.getenv("MODELSCOPE_BASE_URL", ""))
        or _clean(MANUAL_MODELSCOPE_BASE_URL)
        or "https://api.deepseek.com/v1"
    )
    final_api_key = _clean(api_key) or _clean(os.getenv("MODELSCOPE_API_KEY", "")) or _clean(MANUAL_MODELSCOPE_API_KEY)
    final_model_name = _normalize_model(
        _clean(model_name) or _clean(os.getenv("MODELSCOPE_MODEL_NAME", "")) or _clean(MANUAL_MODELSCOPE_MODEL_NAME)
    )
    timeout_val = int(timeout or MANUAL_MODELSCOPE_TIMEOUT or 720)
    return LLMRuntimeConfig(
        base_url=final_base_url,
        api_key=final_api_key,
        model_name=final_model_name,
        timeout=timeout_val,
    )
