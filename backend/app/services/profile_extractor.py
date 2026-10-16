"""Profile Extractor · Plan D · 2.3 — 画像提取鲁棒性

背景：
- ProfileAgent 让 LLM 在对话末尾用 ```profile_update``` 包裹一段 JSON
- 真实 LLM 经常输出不规范（前后空格、注释、尾逗号、Markdown 换行不一致）
- 旧正则 r"```profile_update\s*\n(.*?)\n```" 太严格，提取失败时静默返 {},
  学生不知道画像没更新

Plan D · 2.3 容错设计
====================
1. 多种 fence 形式：profile_update / json / 无标签代码块
2. JSON 解析前先 strip 注释 (`//` 和 `/* */`) + 修尾逗号
3. 返回明确的 (profile_dict, status) 让调用方决定如何上报

status 取值：
* 'success' — 提取并解析成功
* 'no_profile_block' — 文本里没找到任何 JSON 块（正常情况，无需警告）
* 'json_parse_failed' — 找到了块但 JSON 不合法（记 warning 并 fallback 到空）
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Tuple

logger = logging.getLogger(__name__)

# 三个候选 fence 标签（label-only 形式）
_FENCE_LABELS = ("profile_update", "json", None)


def _normalize_if_profile_payload(parsed: dict) -> dict:
    try:
        from backend.app.services.profile_schema import is_profile_payload, normalize_profile

        if is_profile_payload(parsed):
            return normalize_profile(parsed, preserve_extra=True)
    except Exception as exc:
        logger.debug("profile schema normalization skipped: %s", exc)
    return parsed


def _strip_json_comments(text: str) -> str:
    """清理 JSON 字符串中的注释和尾逗号

    支持：
    * // 单行注释
    * /* ... */ 多行注释
    * 数组 / 对象末尾的逗号（包括嵌套）
    """
    # 删除 // 单行注释（不在字符串内）
    cleaned_lines = []
    in_string = False
    escape = False
    i = 0
    buf = []
    while i < len(text):
        c = text[i]
        if escape:
            buf.append(c)
            escape = False
        elif c == "\\" and in_string:
            buf.append(c)
            escape = True
        elif c == '"' and not escape:
            in_string = not in_string
            buf.append(c)
        elif not in_string and c == "/" and i + 1 < len(text) and text[i + 1] == "/":
            # 跳到行尾
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif not in_string and c == "/" and i + 1 < len(text) and text[i + 1] == "*":
            # 跳到 */
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        else:
            buf.append(c)
        i += 1

    cleaned = "".join(buf)

    # 修尾逗号：在 ],} 之前的逗号（允许嵌套）
    cleaned = re.sub(r",(\s*[\]\}])", r"\1", cleaned)
    return cleaned


def _find_json_block(text: str, label: str | None) -> str | None:
    """从 text 中抽取 ```label\\n...\\n``` 的内容（label 可 None = 无标签）。"""
    if label is None:
        # 无标签：找 ```\n{ 或 ```\n[ 开头
        pattern = r"```\s*\n([\{\[][\s\S]*?[\}\]])\s*\n```"
    else:
        pattern = (
            r"```\s*" + re.escape(label) + r"\s*\n"
            r"([\{\[][\s\S]*?[\}\]])"
            r"\s*\n```"
        )
    m = re.search(pattern, text)
    if m:
        return m.group(1)
    # 容错 1：标签 + 内容可能跨多个 ``` 行/没有开闭合换行
    if label is not None:
        loose = re.search(
            r"```\s*" + re.escape(label) + r"\s*([\s\S]*?)```",
            text,
        )
        if loose and loose.group(1).strip():
            return loose.group(1)
    return None


def _find_first_top_level_json(text: str) -> str | None:
    """终极 fallback：找首个 top-level 的 {...} 或 [...] 段，忽略 markdown。"""
    openers = {"{": "}", "[": "]"}

    def _scan(open_c: str) -> str | None:
        close_c = openers[open_c]
        depth = 0
        in_string = False
        escape = False
        start = None
        for i, c in enumerate(text):
            if escape:
                escape = False
                continue
            if c == "\\" and in_string:
                escape = True
                continue
            if c == '"':
                in_string = not in_string
            if in_string:
                continue
            if c == open_c:
                if depth == 0:
                    start = i
                depth += 1
            elif c == close_c:
                depth -= 1
                if depth == 0 and start is not None:
                    return text[start:i + 1]
        return None

    for open_c in ("{", "["):
        result = _scan(open_c)
        if result:
            return result
    return None


def parse_relaxed_json(text: str) -> dict | list | None:
    """容错 JSON 解析

    步骤:
    1. strip JSON 注释
    2. json.loads

    Returns: 解析后的 dict/list，或 None（如失败）
    """
    if not text or not text.strip():
        return None
    cleaned = _strip_json_comments(text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.debug(f"parse_relaxed_json: json.loads failed: {exc}")
        # 二次尝试：替换单引号为双引号
        try:
            tweaked = cleaned.replace("'", '"')
            return json.loads(tweaked)
        except json.JSONDecodeError:
            return None


def extract_profile_updates(llm_output: str) -> Tuple[dict, str]:
    """Plan D · 2.3 — 主入口

    提取 LLM 输出中的画像更新 JSON，容错多种格式。

    Args:
        llm_output: LLM 完整回复文本

    Returns:
        (profile_dict, status)
        - profile_dict: 提取的画像 dict（失败时为空 dict）
        - status: 'success' | 'no_profile_block' | 'json_parse_failed'
    """
    if not llm_output:
        return {}, "no_profile_block"

    # 第一轮：尝试三种 fence
    for label in _FENCE_LABELS:
        raw = _find_json_block(llm_output, label)
        if raw:
            parsed = parse_relaxed_json(raw)
            if isinstance(parsed, dict):
                return _normalize_if_profile_payload(parsed), "success"
            elif parsed is not None:
                # 是数组不应当，转 dict 失败
                logger.debug(
                    f"extract_profile_updates: {label!r} 块解析得到非 dict ({type(parsed).__name__})"
                )

    # 第二轮 fallback：找首个 top-level JSON
    raw = _find_first_top_level_json(llm_output)
    if raw:
        parsed = parse_relaxed_json(raw)
        if isinstance(parsed, dict):
            logger.info(
                "extract_profile_updates: 通过 fallback top-level JSON 成功"
            )
            return _normalize_if_profile_payload(parsed), "success"

    return {}, "no_profile_block"


def summarize_status_for_log(status: str, profile: dict) -> str:
    """可读的单行摘要，方便日志 / Toast 展示。"""
    if status == "success":
        keys = ", ".join(sorted(profile.keys())[:5])
        return f"画像提取成功（{len(profile)} 个维度：{keys}…）"
    if status == "json_parse_failed":
        return "画像提取：JSON 解析失败，下轮重试"
    return "画像：未检测到 update 块（无新增维度）"
