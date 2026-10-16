"""
Peer matching engine — Innovation #6 (v6 B-P3-3).

Finds *complementary* learning partners rather than similar ones: a good peer
for you is strong where you are weak AND weak where you are strong, so both
sides gain. This is the opposite of typical "find similar students" CF.

Design (v6 spec):
- 8-dimension learner profile → numeric 0-1 vector
- Complementarity scoring: bidirectional mutual-gain metric
- Tutor mode: one-directional (strong-where-you-are-weak)
- Privacy: all matches are *suggestions* only — both sides must consent.
  No private data is exposed in the suggestion payload (only archetype +
  complementary dimensions, never raw scores).

Academic alignment:
- Complementarity framing: Johnson & Johnson 1999 (cooperative learning,
  complementary roles improve outcomes)
- Hybrid CF + content-based: Burke 2002 (hybrid recommender systems)

Usage:
    matcher = get_peer_matcher()
    peers = matcher.find_complementary_peers(user_id="u1", limit=5)
    tutors = matcher.find_tutors(user_id="u1", limit=3)
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.database import SessionLocal
from backend.app.core.models import ProfileRecord, LearningPathRecord
from backend.app.repositories.profile_repo import ProfileRepository

logger = logging.getLogger(__name__)


# ── 8 long-term profile dimensions (matches AppConfig.profile_dimensions) ──
PROFILE_DIMENSIONS = [
    "knowledge_base",
    "cognitive_style",
    "learning_preference",
    "weak_points",
    "learning_goal",
    "time_management",
    "self_efficacy",
    "interaction_pattern",
]

# Dimensions where higher = stronger (for tutor logic we invert weak_points).
_INVERTED = {"weak_points"}


def _extract_score(dim_data: Any) -> float:
    """Pull a 0-1 score out of a profile dimension dict.

    Accepts {"score": 0.7}, {"level": "中级"} (mapped), or a bare number.
    """
    if isinstance(dim_data, (int, float)):
        return max(0.0, min(1.0, float(dim_data)))
    if not isinstance(dim_data, dict):
        return 0.5
    if "score" in dim_data:
        try:
            return max(0.0, min(1.0, float(dim_data["score"])))
        except (TypeError, ValueError):
            pass
    level = str(dim_data.get("level", "")).strip()
    level_map = {"初级": 0.3, "基础": 0.3, "中级": 0.6, "中阶": 0.6,
                 "高级": 0.9, "高阶": 0.9, "专家": 0.95}
    if level in level_map:
        return level_map[level]
    return 0.5


def profile_to_vector(profile: Dict[str, Any]) -> List[float]:
    """Convert an 8-dim profile dict into a normalized 0-1 vector.

    weak_points is inverted so that "high weak_points score" means *fewer*
    weaknesses (stronger) — keeping all dimensions "higher = stronger".
    """
    vec: List[float] = []
    for dim in PROFILE_DIMENSIONS:
        score = _extract_score(profile.get(dim, {}))
        if dim in _INVERTED:
            score = 1.0 - score  # fewer weaknesses = stronger
        vec.append(score)
    return vec


def _complementarity(a_vec: List[float], b_vec: List[float]) -> Tuple[float, float, float]:
    """Compute directional + mutual complementarity.

    Returns:
        (a_helps_b, b_helps_a, mutual)
        - a_helps_b: how much a can teach b (a strong where b weak), in [0,1]
        - b_helps_a: symmetric
        - mutual: bidirectional gain = harmonic mean, rewards balance
    """
    a_helps_b = 0.0
    b_helps_a = 0.0
    n = len(a_vec)
    for i in range(n):
        a_helps_b += max(0.0, a_vec[i] - b_vec[i])
        b_helps_a += max(0.0, b_vec[i] - a_vec[i])
    a_helps_b /= n  # normalize to [0,1]
    b_helps_a /= n
    # harmonic mean rewards balanced two-way complementarity over one-sided
    if a_helps_b + b_helps_a > 0:
        mutual = 2 * a_helps_b * b_helps_a / (a_helps_b + b_helps_a)
    else:
        mutual = 0.0
    return a_helps_b, b_helps_a, mutual


def _complementary_dims(a_vec: List[float], b_vec: List[float]) -> Dict[str, List[str]]:
    """Return which dimensions each side can teach the other (for explanation)."""
    a_teaches: List[str] = []
    b_teaches: List[str] = []
    for i, dim in enumerate(PROFILE_DIMENSIONS):
        if a_vec[i] - b_vec[i] > 0.15:
            a_teaches.append(dim)
        if b_vec[i] - a_vec[i] > 0.15:
            b_teaches.append(dim)
    return {"you_can_teach": a_teaches, "they_can_teach": b_teaches}


def _same_cohort(a_profile: Dict[str, Any], b_profile: Dict[str, Any]) -> bool:
    """同专业同年级是演示对比的重要协作信号，但不泄露班级明细。"""
    a = a_profile.get("academic_context") or {}
    b = b_profile.get("academic_context") or {}
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    same_major = bool(a.get("major")) and a.get("major") == b.get("major")
    same_grade = (
        bool(a.get("grade")) and a.get("grade") == b.get("grade")
    ) or (
        bool(a.get("enrollment_year"))
        and a.get("enrollment_year") == b.get("enrollment_year")
    )
    return same_major and same_grade


def _with_demo_seed(user_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    if not user_id.startswith("demo-student-"):
        return profile
    try:
        from backend.app.api.v1.profile import _seed_profiles

        seed = _seed_profiles().get(user_id, {})
    except Exception:
        return profile
    merged = dict(seed)
    for key, value in profile.items():
        base = merged.get(key)
        if isinstance(base, dict) and isinstance(value, dict):
            merged[key] = {**base, **value}
        elif value not in (None, "", [], {}):
            merged[key] = value
    return merged


class PeerMatcher:
    """Complementary peer & tutor matching over stored learner profiles."""

    def __init__(self, profile_repo: Optional[ProfileRepository] = None):
        self._repo = profile_repo or ProfileRepository()

    # ------------------------------------------------------------------
    # Candidate loading
    # ------------------------------------------------------------------
    def _load_all_profiles(self, exclude_user: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Load all profiles from DB, keyed by user_id."""
        out: Dict[str, Dict[str, Any]] = {}
        with SessionLocal() as session:
            rows = session.query(ProfileRecord).all()
            for row in rows:
                if exclude_user and row.user_id == exclude_user:
                    continue
                if row.profile_data:
                    out[row.user_id] = _with_demo_seed(row.user_id, dict(row.profile_data))
        return out

    def _load_behavior_overlap(self, user_id: str) -> Dict[str, float]:
        """Item-based CF signal: shared learning-path topics with other users.

        Returns {other_user_id: overlap_score} for users sharing path topics.
        """
        overlaps: Dict[str, float] = {}
        with SessionLocal() as session:
            my_paths = session.query(LearningPathRecord).filter(
                LearningPathRecord.user_id == user_id
            ).all()
            my_topics: set = set()
            for p in my_paths:
                for stage in (p.stages or []):
                    t = stage.get("topic") or stage.get("title") if isinstance(stage, dict) else None
                    if t:
                        my_topics.add(t)
            if not my_topics:
                return overlaps
            other_paths = session.query(LearningPathRecord).filter(
                LearningPathRecord.user_id != user_id
            ).all()
            for p in other_paths:
                their_topics: set = set()
                for stage in (p.stages or []):
                    t = stage.get("topic") or stage.get("title") if isinstance(stage, dict) else None
                    if t:
                        their_topics.add(t)
                common = my_topics & their_topics
                if common:
                    overlaps[p.user_id] = len(common) / len(my_topics | their_topics)
        return overlaps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def find_complementary_peers(
        self,
        user_id: str,
        limit: int = 5,
        candidates: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Recommend peers whose strengths/weaknesses complement yours.

        Combines content-based complementarity (60%) with behavior CF overlap
        (40%). Returns suggestions sorted by hybrid score.
        """
        my_profile = _with_demo_seed(user_id, self._repo.get(user_id) or {})
        if not my_profile:
            return []
        my_vec = profile_to_vector(my_profile)

        pool = candidates if candidates is not None else self._load_all_profiles(exclude_user=user_id)
        cf_overlap = self._load_behavior_overlap(user_id)

        scored: List[Dict[str, Any]] = []
        for uid, prof in pool.items():
            their_vec = profile_to_vector(prof)
            a_helps, b_helps, mutual = _complementarity(my_vec, their_vec)
            cf = cf_overlap.get(uid, 0.0)
            # hybrid: complementarity content signal + CF collaborative signal
            same_cohort = _same_cohort(my_profile, prof)
            hybrid = min(1.0, 0.6 * mutual + 0.4 * cf + (0.25 if same_cohort else 0.0))
            if hybrid <= 0:
                continue
            dims = _complementary_dims(my_vec, their_vec)
            scored.append({
                "user_id": uid,
                "score": round(hybrid, 4),
                "complementarity": round(mutual, 4),
                "behavior_overlap": round(cf, 4),
                "you_can_teach": dims["you_can_teach"],
                "they_can_teach": dims["they_can_teach"],
                "archetype_code": str(prof.get("_archetype_code", "")),
                "same_cohort": same_cohort,
                # privacy: no raw scores exposed
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def find_tutors(
        self,
        user_id: str,
        limit: int = 3,
        candidates: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Recommend tutors: users strong where YOU are weak (one-directional)."""
        my_profile = _with_demo_seed(user_id, self._repo.get(user_id) or {})
        if not my_profile:
            return []
        my_vec = profile_to_vector(my_profile)

        pool = candidates if candidates is not None else self._load_all_profiles(exclude_user=user_id)

        scored: List[Dict[str, Any]] = []
        for uid, prof in pool.items():
            their_vec = profile_to_vector(prof)
            a_helps, b_helps, _ = _complementarity(my_vec, their_vec)
            # tutor = how much THEY can teach YOU
            if b_helps <= 0:
                continue
            dims = _complementary_dims(my_vec, their_vec)
            scored.append({
                "user_id": uid,
                "score": round(b_helps, 4),
                "they_can_teach": dims["they_can_teach"],
                "archetype_code": str(prof.get("_archetype_code", "")),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]


# ── Singleton ──────────────────────────────────────────────────────
_matcher: Optional[PeerMatcher] = None


def get_peer_matcher() -> PeerMatcher:
    global _matcher
    if _matcher is None:
        _matcher = PeerMatcher()
    return _matcher
