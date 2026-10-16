"""PromptCache + 语义重试 单元测试 (T2.10)

覆盖:
    1. cache key 稳定性（同 prompt 同 temperature 同 key；不同 temperature 不同 key）
    2. cache 命中：第二次调用不打下游
    3. TTL 过期：超 TTL 后视为未命中
    4. 语义重试：JSON 解析失败时追加格式约束重试
    5. 并发安全：多线程同时 set/get 不崩
    6. PROMPT_CACHE_ENABLED=0 时直通下游
    7. chat_json 的 lenient 解析（裸 JSON / ```json 围栏 / 含前后文）
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from backend.app.services.prompt_cache import (
    CachedLLMClient,
    PromptCache,
    _parse_json_lenient,
)


# ================================================================
# Fixture
# ================================================================
@pytest.fixture
def memory_cache() -> PromptCache:
    """内存 SQLite，避免磁盘 IO 让测试变慢/不稳。"""
    return PromptCache(db_path=":memory:")


@pytest.fixture
def mock_llm() -> MagicMock:
    """模拟 LLMClient，chat() 默认返回固定字符串。"""
    m = MagicMock()
    m.chat = MagicMock(return_value="hello world")
    return m


# ================================================================
# 1. Key 稳定性
# ================================================================
class TestCacheKey:
    def test_same_input_same_key(self) -> None:
        msgs = [{"role": "user", "content": "你好"}]
        k1 = PromptCache.make_key(msgs, temperature=0.7, max_tokens=512, model="spark")
        k2 = PromptCache.make_key(msgs, temperature=0.7, max_tokens=512, model="spark")
        assert k1 == k2
        assert len(k1) == 40  # SHA-1 hex

    def test_temperature_diff_produces_diff_key(self) -> None:
        msgs = [{"role": "user", "content": "你好"}]
        k_low = PromptCache.make_key(msgs, temperature=0.1, max_tokens=512)
        k_high = PromptCache.make_key(msgs, temperature=0.9, max_tokens=512)
        assert k_low != k_high

    def test_message_order_matters(self) -> None:
        a = [{"role": "user", "content": "A"}, {"role": "user", "content": "B"}]
        b = [{"role": "user", "content": "B"}, {"role": "user", "content": "A"}]
        assert PromptCache.make_key(a) != PromptCache.make_key(b)

    def test_dict_field_order_does_not_matter(self) -> None:
        """Canonical JSON 排序后 key 字段顺序无关。"""
        msg_a = [{"role": "user", "content": "test"}]
        # 用 extra 故意造同样字段不同序
        k1 = PromptCache.make_key(msg_a, extra={"a": 1, "b": 2})
        k2 = PromptCache.make_key(msg_a, extra={"b": 2, "a": 1})
        assert k1 == k2


# ================================================================
# 2. Cache 命中
# ================================================================
class TestCacheHit:
    def test_miss_then_hit(self, memory_cache: PromptCache, mock_llm: MagicMock) -> None:
        client = CachedLLMClient(inner=mock_llm, cache=memory_cache)
        msgs = [{"role": "user", "content": "你好"}]

        # 第一次：miss，调下游
        out1 = client.chat(msgs)
        assert out1 == "hello world"
        assert mock_llm.chat.call_count == 1

        # 第二次：hit，不调下游
        out2 = client.chat(msgs)
        assert out2 == "hello world"
        assert mock_llm.chat.call_count == 1, "second call must hit cache"

    def test_stats_tracks_hits(self, memory_cache: PromptCache, mock_llm: MagicMock) -> None:
        client = CachedLLMClient(inner=mock_llm, cache=memory_cache)
        msgs = [{"role": "user", "content": "x"}]

        client.chat(msgs)  # miss
        client.chat(msgs)  # hit
        client.chat(msgs)  # hit

        stats = memory_cache.stats()
        assert stats.total_entries == 1
        assert stats.total_hits == 2
        assert stats.hit_rate == pytest.approx(2 / 3, rel=1e-3)


# ================================================================
# 3. TTL
# ================================================================
class TestTTL:
    def test_expired_entry_treated_as_miss(self, mock_llm: MagicMock) -> None:
        # TTL 0.5s 便于快速测试
        cache = PromptCache(db_path=":memory:", ttl_seconds=1)
        client = CachedLLMClient(inner=mock_llm, cache=cache)

        msgs = [{"role": "user", "content": "x"}]
        client.chat(msgs)
        assert mock_llm.chat.call_count == 1

        time.sleep(1.2)  # 等待 TTL 过期
        client.chat(msgs)
        assert mock_llm.chat.call_count == 2, "TTL expired entry must be re-fetched"


# ================================================================
# 4. 语义重试
# ================================================================
class TestSemanticRetry:
    def test_chat_json_succeeds_first_try(
        self, memory_cache: PromptCache, mock_llm: MagicMock
    ) -> None:
        mock_llm.chat.return_value = '{"foo": "bar"}'
        client = CachedLLMClient(inner=mock_llm, cache=memory_cache)
        result = client.chat_json([{"role": "user", "content": "x"}])
        assert result == {"foo": "bar"}
        assert mock_llm.chat.call_count == 1

    def test_chat_json_retries_on_invalid_json(self, memory_cache: PromptCache) -> None:
        """第一次返回非法 JSON，第二次返回合法 → 总共调 2 次。"""
        responses = iter(
            [
                "not json at all",
                '{"ok": true}',
            ]
        )
        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(side_effect=lambda *a, **kw: next(responses))

        client = CachedLLMClient(inner=mock_llm, cache=memory_cache)
        result = client.chat_json([{"role": "user", "content": "x"}], max_retries=2)
        assert result == {"ok": True}
        assert mock_llm.chat.call_count == 2

    def test_chat_json_raises_after_all_retries(self, memory_cache: PromptCache) -> None:
        mock_llm = MagicMock()
        mock_llm.chat = MagicMock(return_value="完全不是 JSON")

        client = CachedLLMClient(inner=mock_llm, cache=memory_cache)
        with pytest.raises(ValueError, match="无法解析"):
            client.chat_json([{"role": "user", "content": "x"}], max_retries=1)
        # 总共调用 max_retries+1 = 2 次
        assert mock_llm.chat.call_count == 2


# ================================================================
# 5. 并发安全
# ================================================================
class TestConcurrency:
    def test_concurrent_set_get(self, memory_cache: PromptCache) -> None:
        """100 个线程并发写读，不应崩溃或丢数据。"""
        N = 100
        errors: List[Exception] = []

        def worker(i: int) -> None:
            try:
                key = f"key_{i}"
                memory_cache.set(key, f"value_{i}")
                got = memory_cache.get(key)
                assert got == f"value_{i}", f"got {got!r} for {key!r}"
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"concurrent errors: {errors[:3]}"
        assert memory_cache.stats().total_entries == N


# ================================================================
# 6. 关闭 cache
# ================================================================
class TestDisable:
    def test_env_disabled_bypasses_cache(
        self, memory_cache: PromptCache, mock_llm: MagicMock
    ) -> None:
        client = CachedLLMClient(inner=mock_llm, cache=memory_cache, enabled=False)
        msgs = [{"role": "user", "content": "x"}]

        client.chat(msgs)
        client.chat(msgs)
        # 两次都打下游，cache 完全旁路
        assert mock_llm.chat.call_count == 2
        assert memory_cache.stats().total_entries == 0


# ================================================================
# 7. _parse_json_lenient 解析能力
# ================================================================
class TestLenientParse:
    def test_plain_json(self) -> None:
        assert _parse_json_lenient('{"a": 1}') == {"a": 1}

    def test_json_in_code_fence(self) -> None:
        text = '```json\n{"a": 1}\n```'
        assert _parse_json_lenient(text) == {"a": 1}

    def test_json_with_preamble(self) -> None:
        text = '好的，结果如下：\n\n{"a": 1, "b": [2, 3]}\n\n以上。'
        assert _parse_json_lenient(text) == {"a": 1, "b": [2, 3]}

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_json_lenient("")

    def test_no_json_raises(self) -> None:
        with pytest.raises((ValueError, json.JSONDecodeError)):
            _parse_json_lenient("just plain text without any braces")


# ================================================================
# 8. clear 与 stats
# ================================================================
class TestClearAndStats:
    def test_clear_removes_all(self, memory_cache: PromptCache) -> None:
        for i in range(5):
            memory_cache.set(f"k{i}", f"v{i}")
        assert memory_cache.stats().total_entries == 5
        removed = memory_cache.clear()
        assert removed == 5
        assert memory_cache.stats().total_entries == 0
