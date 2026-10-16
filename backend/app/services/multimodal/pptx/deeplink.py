"""
QR 深链生成 - 创新点

每张幻灯片右下角 QR 码 → 扫码回到 chat session, 按本张幻灯片主题追问。

URL 设计:
    {base_url}/chat?session={session_id}&topic={url-encoded title}&slide={idx}

降级:
- qrcode 未安装时返回 None, PPTX 不放 QR (不阻塞渲染)
"""
from __future__ import annotations

import hashlib
import logging
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

QR_DIR = Path("data/artifacts/qr")
DEFAULT_BASE_URL = "https://f3.edu.local/chat"


@dataclass
class DeepLinkResult:
    qr_path: Optional[str]
    url: str
    method: str  # "qrcode" / "disabled" / "error"
    error: str = ""


def build_deeplink_url(
    session_id: str,
    title: str,
    slide_index: int,
    base_url: str = DEFAULT_BASE_URL,
) -> str:
    """构建深链 URL"""
    qs = urllib.parse.urlencode({
        "session": session_id or "guest",
        "topic": title[:80],
        "slide": slide_index,
    })
    return f"{base_url}?{qs}"


def generate_deeplink_qr(
    session_id: str,
    title: str,
    slide_index: int,
    base_url: str = DEFAULT_BASE_URL,
    box_size: int = 4,
) -> DeepLinkResult:
    """生成幻灯片对应的 QR 深链 PNG

    Returns:
        DeepLinkResult, qr_path 为 None 表示降级
    """
    url = build_deeplink_url(session_id, title, slide_index, base_url)

    try:
        import qrcode
    except ImportError:
        return DeepLinkResult(
            qr_path=None, url=url, method="disabled",
            error="qrcode not installed",
        )

    try:
        QR_DIR.mkdir(parents=True, exist_ok=True)
        cache_key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        out_path = QR_DIR / f"qr_{cache_key}.png"
        if not out_path.exists():
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=box_size, border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(str(out_path))
        return DeepLinkResult(
            qr_path=str(out_path), url=url, method="qrcode",
        )
    except Exception as exc:
        logger.warning(f"[QR] generate failed: {exc}")
        return DeepLinkResult(
            qr_path=None, url=url, method="error", error=str(exc),
        )
