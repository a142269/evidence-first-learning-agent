"""
Hybrid recommendation engine for social learning (Innovation #6 companion).

Wraps PeerMatcher with:
- explainable recommendation reasons (natural-language rationale per match)
- privacy sanitization (strip raw scores before API exposure)
- configurable blend weight between content-based & CF signals

Academic alignment: Burke 2002 hybrid recommender taxonomy —
weighted hybrid of content-based (profile complementarity) and
collaborative (behavior overlap) methods.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.app.services.social.peer_matching import (
    PeerMatcher,
    PROFILE_DIMENSIONS,
    get_peer_matcher,
)

# Human-readable labels for the 8 profile dimensions (zh)
_DIM_LABELS = {
    "knowledge_base": "知识基础",
    "cognitive_style": "认知风格",
    "learning_preference": "学习偏好",
    "weak_points": "薄弱环节",
    "learning_goal": "学习目标",
    "time_management": "时间管理",
    "self_efficacy": "自我效能",
    "interaction_pattern": "交互模式",
}


class RecommendationEngine:
    """Explainable hybrid recommender over PeerMatcher output."""

    def __init__(self, matcher: Optional[PeerMatcher] = None):
        self._matcher = matcher or get_peer_matcher()

    # ------------------------------------------------------------------
    # Explanation
    # ------------------------------------------------------------------
    @staticmethod
    def explain_peer(match: Dict[str, Any]) -> str:
        """Generate a one-sentence rationale for a peer suggestion."""
        you_teach = match.get("you_can_teach", [])
        they_teach = match.get("they_can_teach", [])
        parts: List[str] = []
        if they_teach:
            labels = "、".join(_DIM_LABELS.get(d, d) for d in they_teach[:3])
            parts.append(f"对方可在{labels}上帮助你")
        if you_teach:
            labels = "、".join(_DIM_LABELS.get(d, d) for d in you_teach[:3])
            parts.append(f"你可在{labels}上反哺对方")
        if not parts:
            parts.append(
                "同专业同年级，可对比不同学习基础与方向"
                if match.get("same_cohort")
                else "双方学习行为高度互补"
            )
        return "；".join(parts) + "。"

    @staticmethod
    def explain_tutor(match: Dict[str, Any]) -> str:
        """Generate rationale for a tutor suggestion."""
        they_teach = match.get("they_can_teach", [])
        if they_teach:
            labels = "、".join(_DIM_LABELS.get(d, d) for d in they_teach[:3])
            return f"对方在{labels}上较强，可针对性辅导你。"
        return "对方整体能力较强，适合作为导师。"

    # ------------------------------------------------------------------
    # Privacy sanitization
    # ------------------------------------------------------------------
    @staticmethod
    def sanitize(matches: List[Dict[str, Any]], kind: str = "peer") -> List[Dict[str, Any]]:
        """Strip internal scores, keep only user-facing fields.

        Privacy design (v6 spec): suggestions expose only user_id +
        complementary dimensions + a rationale — never raw profile scores.
        """
        clean: List[Dict[str, Any]] = []
        for m in matches:
            entry = {
                "user_id": m.get("user_id"),
                "reason": (RecommendationEngine.explain_peer(m) if kind == "peer"
                           else RecommendationEngine.explain_tutor(m)),
            }
            if kind == "peer":
                entry["you_can_teach"] = m.get("you_can_teach", [])
                entry["they_can_teach"] = m.get("they_can_teach", [])
                entry["same_cohort"] = bool(m.get("same_cohort"))
            else:
                entry["they_can_teach"] = m.get("they_can_teach", [])
            clean.append(entry)
        return clean

    # ------------------------------------------------------------------
    # High-level recommend
    # ------------------------------------------------------------------
    def recommend_peers(
        self, user_id: str, limit: int = 5, explain: bool = True
    ) -> List[Dict[str, Any]]:
        raw = self._matcher.find_complementary_peers(user_id, limit=limit)
        return self.sanitize(raw, kind="peer") if explain else raw

    def recommend_tutors(
        self, user_id: str, limit: int = 3, explain: bool = True
    ) -> List[Dict[str, Any]]:
        raw = self._matcher.find_tutors(user_id, limit=limit)
        return self.sanitize(raw, kind="tutor") if explain else raw
