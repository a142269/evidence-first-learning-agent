"""PromptCache + 语义重试 (T2.10)

为评委演示场景准备：现场配额超 / 网络抖动时，相同 prompt 走本地缓存直接返回，
避免重复打 LLM。语义重试在 JSON 解析失败时自动追加 "请严格输出 JSON" 提示重试。

设计:
    * Cache key   = SHA-1(canonical_json({messages, temperature, max_tokens, model}))
    * 存储后端   = SQLite (data/cache/prompt_cache.db)，线程安全
    * TTL        = 默认 7 天，按 created_at 过滤
    * 命中统计   = hit_count / last_hit_at，配 stats CLI 看命中率
    * 语义重试   = chat_json() 解析失败 → 追加格式约束最多重试 N 次

安全:
    * Key 含完整 prompt + 参数，不会出现"不同 prompt 相同 cache 值"
    * value 列存原始字符串，不再二次反序列化
    * 测试场景禁用磁盘 IO：传 ``db_path=":memory:"``
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# ================================================================
# 默认配置
# ================================================================
DEFAULT_DB_PATH = Path("data/cache/prompt_cache.db")
DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 天
SEMANTIC_RETRY_MAX = 2

# ================================================================
# 数据模型
# ================================================================
@dataclass(frozen=True)
class CacheStats:
    total_entries: int
    total_hits: int
    hit_rate: float  # 0.0 ~ 1.0
    oldest_entry_age_s: float
    newest_entry_age_s: float


# ================================================================
# PromptCache 本体
# ================================================================
class PromptCache:
    """SQLite 后端的 Prompt 缓存。

    使用方法::

        cache = PromptCache()
        key = cache.make_key(messages, temperature=0.7, max_tokens=512, model="spark")
        if (cached := cache.get(key)) is not None:
            return cached
        response = llm.chat(messages, temperature=0.7, max_tokens=512)
        cache.set(key, response)
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS prompt_cache (
            key          TEXT PRIMARY KEY,
            value        TEXT NOT NULL,
            created_at   REAL NOT NULL,
            hit_count    INTEGER NOT NULL DEFAULT 0,
            last_hit_at  REAL,
            tag          TEXT
        )
    """

    def __init__(
        self,
        db_path: Optional[Path | str] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

        if db_path is None:
            db_path = DEFAULT_DB_PATH
        if str(db_path) == ":memory:":
            self._db_path = ":memory:"
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            db_path = Path(db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = str(db_path)
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)

        self._conn.execute(self._SCHEMA)
        self._conn.commit()

    # ── Key 生成 ───────────────────────────────────────────
    @staticmethod
    def make_key(
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model: str = "default",
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成稳定的 cache key。

        采用 canonical JSON（sort_keys + ensure_ascii=False）确保等价 dict
        生成相同 key，规避字典 key 顺序漂移。
        """
        payload = {
            "messages": messages,
            "temperature": round(float(temperature), 4),
            "max_tokens": int(max_tokens),
            "model": model,
            "extra": extra or {},
        }
        canon = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha1(canon.encode("utf-8")).hexdigest()

    # ── 上下文管理 ─────────────────────────────────────────
    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            finally:
                cur.close()

    # ── 读写 ───────────────────────────────────────────────
    def get(self, key: str) -> Optional[str]:
        """命中 → 返回 value 并 hit_count+1；未命中或过期 → None。"""
        now = time.time()
        with self._cursor() as cur:
            cur.execute(
                "SELECT value, created_at FROM prompt_cache WHERE key = ?",
                (key,),
            )
            row = cur.fetchone()
            if row is None:
                return None

            value, created_at = row
            if now - created_at > self._ttl:
                # TTL 过期，懒删除
                cur.execute("DELETE FROM prompt_cache WHERE key = ?", (key,))
                return None

            cur.execute(
                "UPDATE prompt_cache SET hit_count = hit_count + 1, last_hit_at = ? "
                "WHERE key = ?",
                (now, key),
            )
            return str(value)

    def set(self, key: str, value: str, *, tag: Optional[str] = None) -> None:
        """写入或覆盖一个 cache 条目。"""
        now = time.time()
        with self._cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO prompt_cache "
                "(key, value, created_at, hit_count, last_hit_at, tag) "
                "VALUES (?, ?, ?, 0, NULL, ?)",
                (key, value, now, tag),
            )

    def clear(self) -> int:
        """清空缓存，返回删除条目数。"""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM prompt_cache")
            count = cur.fetchone()[0]
            cur.execute("DELETE FROM prompt_cache")
            return int(count)

    def stats(self) -> CacheStats:
        """命中率与年龄统计。"""
        now = time.time()
        with self._cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0), "
                "COALESCE(MIN(created_at), ?), COALESCE(MAX(created_at), ?) "
                "FROM prompt_cache",
                (now, now),
            )
            total, hits, oldest_at, newest_at = cur.fetchone()
            total = int(total or 0)
            hits = int(hits or 0)
            calls = total + hits
            return CacheStats(
                total_entries=total,
                total_hits=hits,
                hit_rate=(hits / calls) if calls > 0 else 0.0,
                oldest_entry_age_s=max(0.0, now - oldest_at) if total else 0.0,
                newest_entry_age_s=max(0.0, now - newest_at) if total else 0.0,
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ================================================================
# CachedLLMClient — 装饰已有 LLMClient
# ================================================================
class CachedLLMClient:
    """对已有 LLMClient.chat 加 cache 拦截 + 语义重试。

    包装而非继承，保持向后兼容：业务可选择性接入，不破坏现有调用方。
    """

    def __init__(
        self,
        inner: Any,  # backend.app.core.llm_client.LLMClient
        cache: Optional[PromptCache] = None,
        *,
        model_name: str = "default",
        enabled: Optional[bool] = None,
    ) -> None:
        self._inner = inner
        self._cache = cache or PromptCache()
        self._model = model_name
        # PROMPT_CACHE_ENABLED=0 关掉所有 cache（保留语义重试）
        if enabled is None:
            enabled = os.getenv("PROMPT_CACHE_ENABLED", "1") != "0"
        self._enabled = enabled

    @property
    def cache(self) -> PromptCache:
        return self._cache

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        *,
        tag: Optional[str] = None,
    ) -> str:
        """带 cache 的同步 chat。命中 cache 时不调下游。"""
        if not self._enabled:
            return str(self._inner.chat(messages, temperature=temperature, max_tokens=max_tokens))

        key = PromptCache.make_key(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            model=self._model,
        )
        cached = self._cache.get(key)
        if cached is not None:
            logger.info("[prompt_cache] hit key=%s len=%d", key[:8], len(cached))
            return cached

        logger.info("[prompt_cache] miss key=%s, calling downstream", key[:8])
        response: str = str(self._inner.chat(messages, temperature=temperature, max_tokens=max_tokens))
        if response:
            self._cache.set(key, response, tag=tag)
        return response

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1024,
        *,
        max_retries: int = SEMANTIC_RETRY_MAX,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """要求模型输出 JSON；解析失败时追加约束最多重试 ``max_retries`` 次。

        每次重试都会产生新的 cache key（因 messages 不同），缓存彼此独立。
        """
        attempt_messages = list(messages)
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            response = self.chat(
                attempt_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tag=tag,
            )
            try:
                return _parse_json_lenient(response)
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning(
                    "[prompt_cache] JSON 解析失败 attempt=%d/%d: %s",
                    attempt + 1, max_retries + 1, exc,
                )
                # 追加格式约束消息，作为下一轮 prompt 的尾部
                attempt_messages = list(messages) + [
                    {"role": "assistant", "content": response},
                    {
                        "role": "user",
                        "content": (
                            "上一条回复无法解析为 JSON。请仅返回严格合法的 JSON 对象，"
                            "不要包含 ```json 围栏、不要包含任何前后解释文字、"
                            "不要含尾随逗号。"
                        ),
                    },
                ]

        raise ValueError(
            f"chat_json 在 {max_retries + 1} 次重试后仍无法解析 JSON: {last_error}"
        )


def _parse_json_lenient(text: str) -> Dict[str, Any]:
    """从 LLM 响应文本中尽力解析 JSON。

    支持:
        - 纯 JSON 对象
        - ```json ... ``` 围栏
        - 前后含解释文字（截取第一个 { 到对应 } 的子串）
    """
    if not text or not text.strip():
        raise ValueError("empty response")

    stripped = text.strip()

    def _ensure_dict(obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict):
            return obj
        raise ValueError(f"expected JSON object, got {type(obj).__name__}")

    # 优先尝试纯 JSON
    try:
        return _ensure_dict(json.loads(stripped))
    except json.JSONDecodeError:
        pass

    # 尝试 ```json 围栏
    if "```" in stripped:
        # 取 ``` 之间的内容
        parts = stripped.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return _ensure_dict(json.loads(part))
            except json.JSONDecodeError:
                continue

    # 截取第一个 { 到最后一个 } 之间
    start = stripped.find("{")
    end = stripped.rfind("}")
    if 0 <= start < end:
        candidate = stripped[start : end + 1]
        return _ensure_dict(json.loads(candidate))

    raise ValueError(f"无法从响应中提取 JSON: {stripped[:80]!r}...")


# ================================================================
# 全局单例
# ================================================================
_default_cache: Optional[PromptCache] = None


def get_default_cache() -> PromptCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = PromptCache()
    return _default_cache


def reset_default_cache() -> None:
    """测试用：重置全局单例并关闭已有连接。"""
    global _default_cache
    if _default_cache is not None:
        _default_cache.close()
    _default_cache = None
