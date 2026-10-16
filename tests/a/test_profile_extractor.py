"""Plan D 2.3 — test_profile_extractor.py

覆盖：
1. 标准 ```profile_update 块
2. ```json fence
3. 无标签代码块
4. 含 // 单行注释
5. 含 /* ... */ 多行注释
6. 含尾逗号
7. JSON 不合法 -> 返回空 + status=json_parse_failed?（current 行为是 no_profile_block）
8. 完全没有块 -> no_profile_block
9. top-level JSON fallback
"""
from __future__ import annotations

import pytest

from backend.app.services.profile_extractor import (
    extract_profile_updates,
    parse_relaxed_json,
)


# ============================================================
# parse_relaxed_json 单元测试
# ============================================================
class TestParseRelaxedJSON:
    def test_strict_json(self):
        assert parse_relaxed_json('{"a": 1, "b": [1,2]}') == {"a": 1, "b": [1, 2]}

    def test_comments_stripped(self):
        # // 单行注释
        text = """{
            "a": 1,  // comment
            "b": 2
        }"""
        assert parse_relaxed_json(text) == {"a": 1, "b": 2}

    def test_block_comments_stripped(self):
        text = """{
            "a": 1, /* mid-line */
            "b": /* block */ 2
        }"""
        assert parse_relaxed_json(text) == {"a": 1, "b": 2}

    def test_trailing_commas_stripped(self):
        assert parse_relaxed_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}
        assert parse_relaxed_json('[1, 2, 3,]') == [1, 2, 3]

    def test_invalid_returns_none(self):
        assert parse_relaxed_json('{"a": }') is None
        assert parse_relaxed_json('not json') is None
        assert parse_relaxed_json('') is None


# ============================================================
# extract_profile_updates 集成测试（容错端到端）
# ============================================================
class TestExtractProfile:
    def test_standard_profile_update_block(self):
        text = """好, 这是我的讲解。

```profile_update
{
    "knowledge_base": {"level": "中级"},
    "learning_preference": {"preferred_format": "代码+图"}
}
```
"""
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert profile["knowledge_base"]["level"] == "中级"
        assert profile["learning_preference"]["preferred_format"] == "代码+图"

    def test_json_fence(self):
        text = """OK
```json
{"cognitive_style": "视觉型"}
```
"""
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert profile["cognitive_style"] == "视觉型"

    def test_unlabeled_fence(self):
        text = """讲解完毕
```
{"weak_points": ["反向传播"]}
```"""
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert profile["weak_points"] == ["反向传播"]

    def test_loose_label_fence(self):
        """LLM 偶尔 label 不换行也允许"""
        text = '```profile_update{"a": 1}```'
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert profile == {"a": 1}

    def test_comments_inside_block(self):
        text = """```profile_update
{
    "x": 1, // c
    "y": 2 /* mid */
}
```"""
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert profile == {"x": 1, "y": 2}

    def test_trailing_comma_inside_block(self):
        text = """```profile_update
{"a": 1, "b": [1, 2,], "c": {"d": 3,}}
```"""
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert profile == {"a": 1, "b": [1, 2], "c": {"d": 3}}

    def test_no_block_returns_no_profile_block(self):
        text = "今天是星期一, 我们来讨论 CNN"
        profile, status = extract_profile_updates(text)
        assert status == "no_profile_block"
        assert profile == {}

    def test_invalid_json_in_block_returns_no_profile_block(self):
        """当前实现：JSON 不合法 → 返回空 + no_profile_block（保守）"""
        text = """```profile_update
{invalid json here}
```"""
        profile, status = extract_profile_updates(text)
        # 不抛异常，期望 no_profile_block 或 json_parse_failed 之一（取决于实现）
        assert status in {"no_profile_block", "json_parse_failed"}
        assert profile == {}

    def test_top_level_json_fallback(self):
        """没有 fence 但有顶层 JSON 对象"""
        text = '好的. {"time_management": "周一到周五每晚 1h"}'
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert "time_management" in profile

    def test_chinese_value_unicode_safe(self):
        text = """```profile_update
{"knowledge_base": {"known_topics": ["线性代数", "数据结构"]}}
```"""
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert "线性代数" in profile["knowledge_base"]["known_topics"]


# ============================================================
# 性能 / 边界
# ============================================================
class TestBoundaries:
    def test_empty_input(self):
        profile, status = extract_profile_updates("")
        assert profile == {}
        assert status == "no_profile_block"

    def test_very_long_input_no_block(self):
        text = "x" * 100_000
        profile, status = extract_profile_updates(text)
        assert profile == {}

    def test_multiple_blocks_takes_first_valid(self):
        text = """```profile_update
{"a": 1}
```
中间文本
```json
{"b": 2}
```"""
        profile, status = extract_profile_updates(text)
        assert status == "success"
        assert profile["a"] == 1
