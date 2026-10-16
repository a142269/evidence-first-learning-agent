"""
讯飞星火图像理解 WebSocket 客户端（用于 OCR / 教材页面识别）

协议参考: https://www.xfyun.cn/doc/spark/ImageUnderstanding.html
接口地址: wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image
域: general | imagev3

鉴权与星火 Chat 一致：HMAC-SHA256 签名 host/date/request-line。

调用方向：
    图片 base64 + 一句提示词 → JSON（title / topics / blocks / formulas / summary）
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

logger = logging.getLogger(__name__)


DEFAULT_PROMPT = (
    "你是教材/题目页面 OCR 解析器。识别图片中所有可见文字，严格按以下规则输出：\n"
    "1. 只输出一段 JSON，禁止任何解释性文字或代码块围栏；\n"
    "2. 字段说明如下（值必须来自图片真实内容，看不清就留空字符串或空数组，禁止编造）：\n"
    "   - title: 图片顶部或最显眼的标题；无则空字符串\n"
    "   - language: 三选一 zh / en / mixed\n"
    "   - blocks: 数组，元素形如 {\"type\":\"heading|text|formula|code|list_item|caption\",\"content\":\"文本原文\"}\n"
    "   - topics: 从正文里提取的 2~5 个关键术语；抽不到就返回空数组 []\n"
    "   - summary: 一句话摘要，不超过 40 字\n"
    "   - formulas: 抽到的 LaTeX 公式数组，无则空数组\n"
    "3. 保留原文字符、大小写、标点；公式请转成 LaTeX。"
)


class XunfeiImageOCR:
    """讯飞图像理解客户端 —— 同步调用，一次一图。"""

    IMAGE_MAX_BYTES = 4 * 1024 * 1024  # 讯飞侧硬上限 4MB

    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        url: str = "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image",
        domain: str = "imagev3",
        timeout: int = 60,
    ) -> None:
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.url = url
        self.domain = domain
        self.timeout = timeout

    # ------------------------------------------------------------------
    # available: 静态方法, 让上层可以在不构造实例的情况下探测凭证
    # ------------------------------------------------------------------
    @classmethod
    def credentials_present(cls) -> bool:
        from backend.app.core.config import get_config

        cfg = get_config().llm
        return bool(cfg.spark_app_id and cfg.spark_api_key and cfg.spark_api_secret)

    @classmethod
    def from_config(cls) -> Optional["XunfeiImageOCR"]:
        from backend.app.core.config import get_config

        cfg = get_config().llm
        if not (cfg.spark_app_id and cfg.spark_api_key and cfg.spark_api_secret):
            return None
        return cls(
            app_id=cfg.spark_app_id,
            api_key=cfg.spark_api_key,
            api_secret=cfg.spark_api_secret,
            url=cfg.spark_image_url,
            domain=cfg.spark_image_domain,
            timeout=cfg.timeout,
        )

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def recognize(
        self,
        image_data: bytes,
        prompt: str = DEFAULT_PROMPT,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> Optional[dict[str, Any]]:
        """调用讯飞图像理解并返回解析后的 dict；失败返回 None。"""
        if not image_data:
            return None
        if len(image_data) > self.IMAGE_MAX_BYTES:
            logger.warning(
                "[XunfeiImageOCR] image too large: %d bytes (limit=%d)",
                len(image_data),
                self.IMAGE_MAX_BYTES,
            )
            return None

        raw = self._call_ws(image_data, prompt, temperature, max_tokens)
        if not raw:
            return None
        return _parse_json_output(raw)

    # ------------------------------------------------------------------
    # WebSocket 调用
    # ------------------------------------------------------------------
    def _call_ws(
        self,
        image_data: bytes,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        try:
            import websocket  # websocket-client
        except ImportError:
            logger.error("[XunfeiImageOCR] 请安装 websocket-client: pip install websocket-client")
            return ""

        try:
            auth_url = self._build_auth_url()
        except Exception as exc:
            logger.error("[XunfeiImageOCR] 构造鉴权 URL 失败: %s", exc)
            return ""

        payload = self._build_payload(image_data, prompt, temperature, max_tokens)

        chunks: list[str] = []
        err_msg: dict[str, str] = {"error": ""}

        def on_message(ws, message):
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                err_msg["error"] = f"invalid_json: {message[:200]}"
                ws.close()
                return
            header = data.get("header") or {}
            code = header.get("code", -1)
            if code != 0:
                err_msg["error"] = f"code={code} msg={header.get('message','')}"
                logger.warning("[XunfeiImageOCR] API error: %s", err_msg["error"])
                ws.close()
                return
            choices = ((data.get("payload") or {}).get("choices") or {})
            for item in choices.get("text", []) or []:
                text = item.get("content", "")
                if text:
                    chunks.append(text)
            if choices.get("status", 0) == 2:
                ws.close()

        def on_error(ws, error):
            err_msg["error"] = str(error)
            logger.warning("[XunfeiImageOCR] WS error: %s", error)

        def on_open(ws):
            ws.send(json.dumps(payload))

        ws = websocket.WebSocketApp(
            auth_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
        )
        # 讯飞 WS 只需短连接，用 timeout 限制最长等待
        ws.run_forever(ping_interval=0, ping_timeout=None)

        if err_msg["error"]:
            return ""
        return "".join(chunks).strip()

    # ------------------------------------------------------------------
    # 鉴权 URL
    # ------------------------------------------------------------------
    def _build_auth_url(self) -> str:
        parsed = urlparse(self.url)
        host = parsed.hostname
        path = parsed.path
        now = datetime.now(timezone.utc)
        date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature_sha = hmac.new(
            self.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode()

        auth_origin = (
            f'api_key="{self.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(auth_origin.encode("utf-8")).decode()

        params = {"authorization": authorization, "date": date, "host": host}
        return f"{self.url}?{urlencode(params)}"

    # ------------------------------------------------------------------
    # 请求体
    # ------------------------------------------------------------------
    def _build_payload(
        self,
        image_data: bytes,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        image_b64 = base64.b64encode(image_data).decode()
        return {
            "header": {"app_id": self.app_id},
            "parameter": {
                "chat": {
                    "domain": self.domain,
                    "temperature": max(0.0, min(1.0, float(temperature))),
                    "max_tokens": max(64, min(8192, int(max_tokens))),
                }
            },
            "payload": {
                "message": {
                    "text": [
                        # 讯飞硬性要求：第一条 message 必须是 image
                        {"role": "user", "content": image_b64, "content_type": "image"},
                        {"role": "user", "content": prompt, "content_type": "text"},
                    ]
                }
            },
        }


# ----------------------------------------------------------------------
# 输出解析：LLM 直接给 JSON 也可能夹带 ```json 包裹或说明性文字
# ----------------------------------------------------------------------
def _parse_json_output(raw: str) -> Optional[dict[str, Any]]:
    import re

    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # 直接尝试 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 兜底：抓第一个大括号块
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"summary": raw[:200], "blocks": [{"type": "text", "content": raw}]}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"summary": raw[:200], "blocks": [{"type": "text", "content": raw}]}
