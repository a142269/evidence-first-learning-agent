"""
ModelScope / OpenAI-Compatible HTTP LLM Client
————————————————————————————————————————————
**移植自老项目** `student-behavior-analysis/backend/app/services/reports/llm_service.py`

价值：
1. 纯标准库（urllib + http.client），不依赖 openai 包，部署最薄
2. 完整重试逻辑：HTTPError 上报、IncompleteRead 兼容、timeout 自动 2s 重试
3. deepseek-reasoner 等推理模型兼容（不发 temperature；可读 reasoning_content）
4. 错误信息精细化解析（_extract_error_text 支持嵌套 message）

定位：在 A3 LLM 降级链路中作为「第 3 通道」——
当讯飞星火 + DeepSeek-OpenAI 兼容接口同时失败时，
本通道用 ModelScope / SiliconFlow / 通义云等纯 HTTP 接口兜底。

使用：
  from backend.app.services.llm_modelscope_client import ModelScopeLLMClient
  client = ModelScopeLLMClient(base_url=..., api_key=..., timeout=60)
  text = client.chat(model="qwen-max", messages=[...], temperature=0.3)
"""
from __future__ import annotations

import http.client as http_client
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import error, request


def _clean_base_url(base_url: str) -> str:
    text = str(base_url or "").strip().strip("`").strip().strip('"').strip("'")
    return text.rstrip("/")


def _safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        return {}
    return {}


def _extract_error_text(payload: Dict[str, Any]) -> str:
    """从各种嵌套结构里抽出真正的人类可读错误信息"""
    message_text = str(payload.get("message", "")).strip()
    if message_text:
        parsed = _safe_json_loads(message_text)
        if parsed:
            nested = parsed.get("error")
            if isinstance(nested, dict):
                nested_msg = str(nested.get("message", "")).strip()
                if nested_msg:
                    return nested_msg
            parsed_msg = str(parsed.get("message", "")).strip()
            if parsed_msg:
                return parsed_msg
        return message_text
    err = payload.get("error")
    if isinstance(err, str) and err.strip():
        return err.strip()
    if isinstance(err, dict):
        message = str(err.get("message", "")).strip()
        if message:
            return message
    return ""


@dataclass
class ModelScopeLLMClient:
    """OpenAI 兼容协议的轻量 HTTP 客户端"""

    base_url: str
    api_key: str
    timeout: int = 60

    def __post_init__(self) -> None:
        self.base_url = _clean_base_url(self.base_url)

    @classmethod
    def from_env(cls) -> "ModelScopeLLMClient":
        """从 A3 配置层创建实例（A3 没有独立 cfg，则用环境变量兜底）"""
        import os

        try:
            from backend.app.core.config import get_config

            cfg = get_config().llm
            base_url = getattr(cfg, "openai_base_url", "") or os.getenv("MODELSCOPE_BASE_URL", "")
            api_key = getattr(cfg, "openai_api_key", "") or os.getenv("MODELSCOPE_API_KEY", "")
            timeout = int(getattr(cfg, "timeout", 60) or 60)
        except Exception:
            base_url = os.getenv("MODELSCOPE_BASE_URL", "")
            api_key = os.getenv("MODELSCOPE_API_KEY", "")
            timeout = int(os.getenv("MODELSCOPE_TIMEOUT", "60"))

        return cls(base_url=base_url, api_key=api_key, timeout=timeout)

    # ------------------------------------------------------------------
    # 底层请求（含重试 + IncompleteRead 兼容）
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url=url, method=method.upper(), data=data, headers=headers)
        max_retries = 2
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8", errors="ignore")
                    parsed = _safe_json_loads(body)
                    if parsed:
                        return parsed
                    return {"raw_text": body}
            except error.HTTPError as exc:
                text = exc.read().decode("utf-8", errors="ignore")
                return {"error": f"http_{exc.code}", "message": text}
            except http_client.IncompleteRead as exc:
                # deepseek-reasoner 推理时间长，可能 IncompleteRead
                partial = exc.partial.decode("utf-8", errors="ignore") if exc.partial else ""
                if partial.strip():
                    parsed = _safe_json_loads(partial)
                    if parsed:
                        return parsed
                last_exc = exc
                if attempt < max_retries:
                    time.sleep(2)
                    req = request.Request(url=url, method=method.upper(), data=data, headers=headers)
                    continue
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries and "timeout" in str(exc).lower():
                    time.sleep(2)
                    req = request.Request(url=url, method=method.upper(), data=data, headers=headers)
                    continue
                return {"error": "request_failed", "message": str(exc)}

        return {"error": "request_failed", "message": str(last_exc)}

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------
    def list_models(self) -> List[str]:
        payload = self._request("GET", "/models")
        if payload.get("error"):
            return []
        data = payload.get("data")
        names: List[str] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = str(item.get("id", "")).strip()
                    if name:
                        names.append(name)
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        names.append(text)
        elif isinstance(data, dict):
            for key in ["models", "items"]:
                items = data.get(key)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            name = str(item.get("id", "")).strip()
                            if name:
                                names.append(name)
                        elif isinstance(item, str):
                            text = item.strip()
                            if text:
                                names.append(text)
        return sorted(set(names))

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """同步 chat —— 返回纯文本，错误以 `[API_ERROR] xxx` 开头"""
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # 推理类模型不接受 temperature
        if "reasoner" not in model:
            payload["temperature"] = temperature

        result = self._request("POST", "/chat/completions", payload=payload)

        if result.get("error"):
            message = _extract_error_text(result)
            return f"[API_ERROR] {message}" if message else "[API_ERROR] model call failed"

        choices = result.get("choices", [])
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
                # deepseek-reasoner 内容可能在 reasoning_content
                reasoning = msg.get("reasoning_content", "")
                if isinstance(reasoning, str) and reasoning.strip():
                    return reasoning.strip()

        if isinstance(result.get("raw_text"), str):
            raw_text = str(result["raw_text"]).strip()
            parsed_raw = _safe_json_loads(raw_text)
            if parsed_raw:
                err_text = _extract_error_text(parsed_raw)
                if err_text:
                    return f"[API_ERROR] {err_text}"
            return raw_text

        if "message" in result:
            return str(result.get("message", ""))
        return ""
