"""Pure formatting / scoring helpers used across the diagnosis reporter."""
# ruff: noqa: RUF001
from __future__ import annotations

import hashlib
import re
from typing import Any


def bar(value: float, width: int = 20) -> str:
    """Render an ASCII progress bar; values outside [0,1] are clamped."""
    bounded_value = bounded(value)
    filled = round(bounded_value * width)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {bounded_value:.0%}"


def stars(value: float) -> str:
    filled = round(bounded(value) * 5)
    return "*" * filled + "-" * (5 - filled)


def bounded(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def label_score(label: str) -> float:
    mapping = {
        "极高": 0.95,
        "高": 0.85,
        "较高": 0.75,
        "中": 0.6,
        "适中": 0.6,
        "较低": 0.4,
        "低": 0.3,
        "被动": 0.35,
    }
    return mapping.get(label, 0.55)


def keyword_score(text: str, positive_keywords: list[str]) -> float:
    if any(keyword in text for keyword in positive_keywords):
        return 0.82
    return 0.55


def dict_at(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    return value if isinstance(value, dict) else {}


def stable_seed(text: str) -> int:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-")
    return cleaned or "student"


def archetype_from_nickname(nickname: str) -> str | None:
    """Extract the parenthesised archetype tag from `小明（自驱型）`-style names."""
    match = re.search(r"[（(]\s*([^()）]+?)\s*[)）]", nickname)
    if match:
        return match.group(1)
    return None
