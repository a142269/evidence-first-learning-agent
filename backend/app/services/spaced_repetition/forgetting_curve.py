"""
艾宾浩斯遗忘曲线可视化 —— 答辩创新点 #4 辅助

基于 Ebbinghaus (1885) 遗忘规律：
  R = e^(-t/S)

其中：
  - R: 记忆保留率 (0-1)
  - t: 距上次复习的天数
  - S: 记忆强度（与 SM-2 easiness 和 repetitions 相关）
"""
from __future__ import annotations

import math
from typing import Any, Dict, List


def forgetting_curve_retention(
    days_since_review: float,
    easiness: float = 2.5,
    repetitions: int = 0,
) -> float:
    """计算记忆保留率。

    记忆强度 S = easiness * (1 + 0.15 * repetitions)
    """
    S = easiness * (1 + 0.15 * max(0, repetitions))
    retention = math.exp(-days_since_review / max(S, 0.5))
    return round(retention, 4)


def retention_at_intervals(
    easiness: float = 2.5,
    repetitions: int = 0,
    days: List[int] = None,
) -> List[Dict[str, Any]]:
    """计算多个时间点的记忆保留率（用于画曲线）"""
    if days is None:
        days = [0, 1, 2, 3, 5, 7, 10, 15, 21, 30]
    return [
        {"day": d, "retention": forgetting_curve_retention(d, easiness, repetitions)}
        for d in days
    ]


def next_review_recommendation(
    retention_threshold: float = 0.7,
    easiness: float = 2.5,
    repetitions: int = 0,
    current_easiness: float | None = None,
    current_interval: int | None = None,
    last_quality: int | None = None,
) -> Dict[str, Any]:
    """推荐下次复习时间：当保留率降至 threshold 时"""
    if current_easiness is not None:
        easiness = current_easiness
    _ = current_interval, last_quality
    S = easiness * (1 + 0.15 * max(0, repetitions))
    # R = e^(-t/S) → t = -S * ln(R)
    days = -S * math.log(max(retention_threshold, 0.01))
    return {
        "recommended_days": round(days, 1),
        "retention_at_recommendation": retention_threshold,
        "memory_strength": round(S, 2),
    }
