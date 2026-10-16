"""
安全工具: API Key 校验、内容过滤 Token 生成
"""
import hashlib
import secrets
import time
from typing import Optional


def generate_session_id() -> str:
    """生成唯一会话ID"""
    return secrets.token_hex(16)


def generate_api_token(prefix: str = "a3") -> str:
    """生成 API Token"""
    rand = secrets.token_hex(24)
    ts = int(time.time())
    return f"{prefix}_{ts}_{rand}"


def hash_content(content: str) -> str:
    """内容哈希 —— 用于去重和缓存"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def mask_sensitive(text: str, keep_start: int = 3, keep_end: int = 2) -> str:
    """脱敏处理 —— 保留首尾字符"""
    if len(text) <= keep_start + keep_end:
        return "*" * len(text)
    return text[:keep_start] + "*" * (len(text) - keep_start - keep_end) + text[-keep_end:]


def verify_csrf_token(token: str, stored: str) -> bool:
    """CSRF Token 校验（恒定时间比较）"""
    return secrets.compare_digest(token, stored)
