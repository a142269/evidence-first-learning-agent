from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if str(v).strip()]
        except Exception:
            parts = [seg.strip() for seg in text.replace("；", ";").split(";")]
            return [seg for seg in parts if seg and seg.lower() != "nan"]
    return []


@dataclass
class NarrativeGenerator:
    phrases_cfg: dict[str, Any] = field(default_factory=dict)

    def _risk_text(self, risk_level: str) -> str:
        mapping = {
            "high": "当前处于高关注区间，建议辅导员优先安排连续跟踪。",
            "medium": "当前处于中关注区间，建议按周复核关键行为代理指标。",
            "low": "当前处于低关注区间，建议保持稳定节奏并持续观察。",
        }
        return mapping.get(str(risk_level).lower(), mapping["low"])

    def _peer_phrase(self, peer_compare: dict[str, Any]) -> str:
        if not peer_compare:
            return "同群体分位数据暂不完整，当前以可用行为代理指标进行解释。"
        valid = []
        for key in ["night_activity_peer_pct", "formal_activity_peer_pct", "stable_partner_peer_pct"]:
            if key in peer_compare:
                try:
                    valid.append((key, float(peer_compare[key])))
                except Exception:
                    continue
        if not valid:
            return "同群体分位数据暂不完整，当前以可用行为代理指标进行解释。"
        cn = {
            "night_activity_peer_pct": "夜间活跃分位",
            "formal_activity_peer_pct": "活动参与分位",
            "stable_partner_peer_pct": "稳定同伴分位",
        }
        segs = [f"{cn[k]}{v:.0%}" for k, v in valid]
        return "；".join(segs)

    def _trend_phrase(self, trend_4w: dict[str, Any]) -> str:
        if not trend_4w:
            return "近4周趋势数据不足，建议补齐周级快照后再复核。"
        cn = {
            "night_activity_delta_4w": "夜间活跃变化",
            "running_frequency_delta_4w": "运动频率变化",
            "formal_activity_delta_4w": "正式活动变化",
        }
        segs = []
        for key, label in cn.items():
            value = trend_4w.get(key)
            try:
                num = float(value)
            except Exception:
                num = 0.0
            direction = "上升" if num > 0 else ("下降" if num < 0 else "持平")
            segs.append(f"{label}{direction}({num:+.3f})")
        return "；".join(segs)

    def mode_narrative(self, mode_name: str, label: str, score: float) -> str:
        tone = self.phrases_cfg.get("growth_tone_prefix", "从成长视角看，")
        level = "优势项" if score >= 0.75 else ("稳定项" if score >= 0.45 else "关注项")
        return f"{tone}{mode_name}当前识别为{label}，属于{level}，该结论基于行为代理特征。"

    def advice_narrative(self, direction: str, plan_text: str) -> dict[str, Any]:
        steps = [x.strip() for x in str(plan_text).replace("；", ";").split(";") if x.strip()]
        return {
            "direction": direction,
            "detailed_plan": steps,
        }

    def build_summary(self, portrait_row: pd.Series) -> dict[str, Any]:
        risk_level = str(portrait_row.get("risk_level", "low")).lower()
        risk_score = float(pd.to_numeric(portrait_row.get("risk_score", 0.0), errors="coerce") or 0.0)
        trend = _to_dict(portrait_row.get("trend_4w"))
        peer = _to_dict(portrait_row.get("peer_compare"))
        factors = _to_list(portrait_row.get("core_explain_factors"))
        return {
            "risk_overview": f"{self._risk_text(risk_level)} 当前综合风险得分为{risk_score:.3f}。",
            "trend_overview": self._trend_phrase(trend),
            "peer_overview": self._peer_phrase(peer),
            "core_factors": factors[:5],
            "behavior_proxy_statement": "以下解释基于校园行为代理信号，不构成医学或心理诊断。",
        }
