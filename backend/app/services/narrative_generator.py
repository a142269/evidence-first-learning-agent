"""
学习评估叙事生成器（Narrative Generator）

**移植自老项目** `student-behavior-analysis/backend/app/services/reports/narrative_generator.py`

价值：用模板化拼接生成"评估报告自然语言"，避免每次都调 LLM。
- 趋势短语（上升 / 下降 / 持平 + 具体数字）
- 维度短语（优势项 / 稳定项 / 关注项）
- 同伴对比短语（分位数表述）
- 综合摘要（一句话状态 + 关键归因）

适用场景：
- EvaluatorAgent 输出报告的固定段落
- ProfileAgent 输出画像解读的固定段落
- AssessmentView 的"评估师评语"小卡片

设计思想：固定句式 + 数据填空，比每次调 LLM 快 100 倍，且永远不会幻觉。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------
def _to_dict(value: Any) -> Dict[str, Any]:
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


def _to_list(value: Any) -> List[str]:
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


def _to_num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, dict):
        value = value.get("score", default)
    try:
        return float(value)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# 主类
# ---------------------------------------------------------------------------
@dataclass
class NarrativeGenerator:
    """学习评估报告叙事生成器（模板化）"""

    phrases_cfg: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # 状态短语
    # ------------------------------------------------------------------
    def state_text(self, state: str) -> str:
        """学习状态总体描述：优秀 / 良好 / 中等 / 需关注"""
        mapping = {
            "excellent": "当前学习状态优秀，建议保持现有节奏并尝试更高阶挑战。",
            "good": "当前学习状态良好，可以在 1–2 个薄弱维度做针对性强化。",
            "average": "当前学习状态中等，建议按周复核知识掌握度并补齐基础薄弱点。",
            "needs_attention": "当前学习状态需关注，建议优先建立稳定学习节奏，再逐步深入。",
        }
        return mapping.get(str(state).lower(), mapping["average"])

    # ------------------------------------------------------------------
    # 同伴 / 同班对比短语
    # ------------------------------------------------------------------
    def peer_phrase(self, peer_compare: Dict[str, Any]) -> str:
        """学习者在班级中的分位数描述"""
        if not peer_compare:
            return "同班级分位数据暂不完整，当前以个体掌握度指标进行解读。"

        valid: List[tuple[str, float]] = []
        labels = {
            "mastery_peer_pct": "知识掌握分位",
            "quiz_peer_pct": "练习正确分位",
            "engagement_peer_pct": "学习投入分位",
            "consistency_peer_pct": "持续性分位",
        }
        for key in labels.keys():
            if key in peer_compare:
                try:
                    valid.append((key, float(peer_compare[key])))
                except Exception:
                    continue

        if not valid:
            return "同班级分位数据暂不完整，当前以个体掌握度指标进行解读。"

        segs = [f"{labels[k]}{v:.0%}" for k, v in valid]
        return "；".join(segs)

    # ------------------------------------------------------------------
    # 趋势短语（近期评估变化）
    # ------------------------------------------------------------------
    def trend_phrase(self, trend_recent: Dict[str, Any]) -> str:
        """近期评估趋势：含上升 / 下降 / 持平 + 具体数字"""
        if not trend_recent:
            return "近 4 次评估趋势数据不足，建议完成至少 3 轮练习后再复核。"

        labels = {
            "mastery_delta": "知识掌握变化",
            "quiz_accuracy_delta": "练习正确率变化",
            "engagement_delta": "学习投入变化",
            "confidence_delta": "信心指数变化",
        }
        segs = []
        for key, label in labels.items():
            value = trend_recent.get(key)
            try:
                num = float(value)
            except Exception:
                num = 0.0
            direction = "上升" if num > 0.01 else ("下降" if num < -0.01 else "持平")
            segs.append(f"{label}{direction}({num:+.3f})")
        return "；".join(segs)

    # ------------------------------------------------------------------
    # 维度叙事：A3 八维画像专用
    # ------------------------------------------------------------------
    def dimension_narrative(self, dim_name: str, score: float, level: Optional[str] = None) -> str:
        """单个画像维度的语义化描述"""
        tone = self.phrases_cfg.get("growth_tone_prefix", "从学习视角看，")
        category = "优势项" if score >= 0.75 else ("稳定项" if score >= 0.45 else "关注项")
        level_part = f"（识别等级：{level}）" if level else ""
        return f"{tone}{dim_name}当前得分 {score:.2f}{level_part}，属于{category}。"

    # ------------------------------------------------------------------
    # 评估建议叙事（用于 EvaluatorAgent 输出）
    # ------------------------------------------------------------------
    def advice_narrative(self, direction: str, plan_text: str) -> Dict[str, Any]:
        """把粗粒度方向 + 计划文本拆成可执行 step 列表"""
        steps = [x.strip() for x in str(plan_text).replace("；", ";").split(";") if x.strip()]
        return {
            "direction": direction,
            "detailed_plan": steps,
        }

    # ------------------------------------------------------------------
    # 综合摘要
    # ------------------------------------------------------------------
    def build_summary(self, assessment_row: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成一份学习评估的综合摘要。

        输入字段约定（与 EvaluatorAgent 输出对齐）：
        - state: excellent / good / average / needs_attention
        - mastery_overall: 0–1
        - trend_recent: dict（含 mastery_delta 等）
        - peer_compare: dict（含 mastery_peer_pct 等）
        - core_factors: list[str]（最关键的 3-5 个驱动因素）

        返回字段：state_overview / trend_overview / peer_overview / core_factors / statement
        """
        state = str(assessment_row.get("state", "average")).lower()
        mastery = _to_num(assessment_row.get("mastery_overall", 0.0))
        trend = _to_dict(assessment_row.get("trend_recent"))
        peer = _to_dict(assessment_row.get("peer_compare"))
        factors = _to_list(assessment_row.get("core_factors"))

        return {
            "state_overview": f"{self.state_text(state)} 当前综合掌握度 {mastery:.2f}。",
            "trend_overview": self.trend_phrase(trend),
            "peer_overview": self.peer_phrase(peer),
            "core_factors": factors[:5],
            "statement": "以上解读基于本周期的对话、练习与资源使用记录，不构成升学或就业建议。",
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------
_narrative: Optional[NarrativeGenerator] = None


def get_narrative_generator() -> NarrativeGenerator:
    global _narrative
    if _narrative is None:
        _narrative = NarrativeGenerator()
    return _narrative
