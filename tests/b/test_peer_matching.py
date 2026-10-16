"""Peer matching & social recommendation tests (v6 B-P3-3 Innovation #6)."""
from __future__ import annotations

import pytest

from backend.app.core.database import configure_database, init_db, SessionLocal
from backend.app.core import models  # noqa: F401
from backend.app.core.models import ProfileRecord, LearningPathRecord
from backend.app.repositories.profile_repo import ProfileRepository


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    db_path = tmp_path / "social_test.db"
    configure_database(f"sqlite:///{db_path.as_posix()}")
    init_db()
    from backend.app.services.social import peer_matching as pm_mod
    pm_mod._matcher = None
    yield


def _seed_profiles():
    """Seed 4 students with deliberately complementary/identical profiles."""
    repo = ProfileRepository()
    repo.replace("u1", {
        "knowledge_base": {"score": 0.9},
        "cognitive_style": {"score": 0.5},
        "learning_preference": {"score": 0.5},
        "weak_points": {"score": 0.2},        # few weaknesses → strong (inverted 0.8)
        "learning_goal": {"score": 0.7},
        "time_management": {"score": 0.2},    # WEAK here
        "self_efficacy": {"score": 0.6},
        "interaction_pattern": {"score": 0.5},
    })
    repo.replace("u2", {
        "knowledge_base": {"score": 0.3},     # weak where u1 strong
        "cognitive_style": {"score": 0.5},
        "learning_preference": {"score": 0.5},
        "weak_points": {"score": 0.8},        # many weaknesses → weak (inverted 0.2)
        "learning_goal": {"score": 0.5},
        "time_management": {"score": 0.9},    # STRONG where u1 weak
        "self_efficacy": {"score": 0.6},
        "interaction_pattern": {"score": 0.5},
    })
    repo.replace("u3", {  # identical to u1 → low complementarity
        "knowledge_base": {"score": 0.9},
        "cognitive_style": {"score": 0.5},
        "learning_preference": {"score": 0.5},
        "weak_points": {"score": 0.2},
        "learning_goal": {"score": 0.7},
        "time_management": {"score": 0.2},
        "self_efficacy": {"score": 0.6},
        "interaction_pattern": {"score": 0.5},
    })
    repo.replace("u4", {  # strong everywhere → low mutual complementarity
        "knowledge_base": {"score": 0.95},
        "cognitive_style": {"score": 0.95},
        "learning_preference": {"score": 0.95},
        "weak_points": {"score": 0.05},       # near-zero weaknesses → very strong
        "learning_goal": {"score": 0.95},
        "time_management": {"score": 0.95},
        "self_efficacy": {"score": 0.95},
        "interaction_pattern": {"score": 0.95},
    })


# ── pure-function unit tests ───────────────────────────────────────

def test_extract_score_handles_score_level_and_number():
    from backend.app.services.social.peer_matching import _extract_score
    assert _extract_score({"score": 0.7}) == 0.7
    assert _extract_score({"level": "高级"}) == 0.9
    assert _extract_score({"level": "初级"}) == 0.3
    assert _extract_score(0.5) == 0.5
    assert _extract_score({}) == 0.5
    assert _extract_score(None) == 0.5
    assert _extract_score({"score": 1.5}) == 1.0  # clamped


def test_profile_to_vector_inverts_weak_points():
    from backend.app.services.social.peer_matching import profile_to_vector
    vec = profile_to_vector({
        "knowledge_base": {"score": 0.9},
        "weak_points": {"score": 0.9},
    })
    # weak_points.score 0.9 = many weaknesses = weak → inverted to 0.1
    assert vec[0] == 0.9  # knowledge_base unchanged
    assert abs(vec[3] - 0.1) < 1e-9  # weak_points inverted (high weakness → low strength)


def test_complementarity_symmetric_and_mutual():
    from backend.app.services.social.peer_matching import _complementarity
    a = [0.9, 0.2, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    b = [0.3, 0.9, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    a_h, b_h, mutual = _complementarity(a, b)
    assert a_h > 0  # a helps b in dim 0
    assert b_h > 0  # b helps a in dim 1
    assert mutual > 0
    # identical → no complementarity
    a_h2, b_h2, mutual2 = _complementarity(a, a)
    assert a_h2 == 0 and b_h2 == 0 and mutual2 == 0


# ── PeerMatcher with seeded DB ─────────────────────────────────────

def test_find_complementary_peers_ranks_complementary_first():
    _seed_profiles()
    from backend.app.services.social.peer_matching import get_peer_matcher
    matcher = get_peer_matcher()
    peers = matcher.find_complementary_peers("u1", limit=3)
    assert len(peers) >= 1
    # u2 is the most complementary (strong where u1 weak, weak where u1 strong)
    assert peers[0]["user_id"] == "u2"
    assert peers[0]["complementarity"] > 0
    assert "time_management" in peers[0]["they_can_teach"]


def test_find_complementary_peers_excludes_self():
    _seed_profiles()
    from backend.app.services.social.peer_matching import get_peer_matcher
    peers = get_peer_matcher().find_complementary_peers("u1", limit=10)
    assert all(p["user_id"] != "u1" for p in peers)


def test_find_tutors_ranks_strong_where_you_weak():
    _seed_profiles()
    from backend.app.services.social.peer_matching import get_peer_matcher
    tutors = get_peer_matcher().find_tutors("u1", limit=3)
    assert len(tutors) >= 1
    # u4 (all-around strong) is the top tutor; u2 also teaches time_management
    tutor_ids = [t["user_id"] for t in tutors]
    assert "u2" in tutor_ids
    u2_tutor = next(t for t in tutors if t["user_id"] == "u2")
    assert "time_management" in u2_tutor["they_can_teach"]


def test_find_complementary_peers_empty_for_unknown_user():
    from backend.app.services.social.peer_matching import get_peer_matcher
    assert get_peer_matcher().find_complementary_peers("nobody", limit=5) == []


def test_behavior_overlap_from_shared_paths():
    _seed_profiles()
    # seed a shared learning-path topic between u1 and u2
    with SessionLocal() as session:
        session.add(LearningPathRecord(
            id="p1", user_id="u1", title="路径1",
            stages=[{"topic": "Python基础"}, {"topic": "循环"}],
        ))
        session.add(LearningPathRecord(
            id="p2", user_id="u2", title="路径2",
            stages=[{"topic": "Python基础"}, {"topic": "函数"}],
        ))
        session.commit()
    from backend.app.services.social.peer_matching import get_peer_matcher
    peers = get_peer_matcher().find_complementary_peers("u1", limit=3)
    u2_match = next((p for p in peers if p["user_id"] == "u2"), None)
    assert u2_match is not None
    assert u2_match["behavior_overlap"] > 0  # CF signal picked up shared topic


# ── RecommendationEngine: explain + privacy ────────────────────────

def test_sanitize_strips_raw_scores():
    from backend.app.services.social.recommendation_engine import RecommendationEngine
    raw = [{
        "user_id": "u2", "score": 0.78, "complementarity": 0.6,
        "behavior_overlap": 0.4, "you_can_teach": ["knowledge_base"],
        "they_can_teach": ["time_management"], "archetype_code": "high_achiever",
    }]
    clean = RecommendationEngine.sanitize(raw, kind="peer")
    assert len(clean) == 1
    entry = clean[0]
    assert entry["user_id"] == "u2"
    assert "reason" in entry
    # privacy: no raw scores leak
    assert "score" not in entry
    assert "complementarity" not in entry
    assert "behavior_overlap" not in entry
    assert "archetype_code" not in entry


def test_explain_peer_mentions_dimensions():
    from backend.app.services.social.recommendation_engine import RecommendationEngine
    match = {
        "you_can_teach": ["knowledge_base"],
        "they_can_teach": ["time_management"],
    }
    reason = RecommendationEngine.explain_peer(match)
    assert "知识基础" in reason or "时间管理" in reason


def test_explain_tutor_mentions_strength():
    from backend.app.services.social.recommendation_engine import RecommendationEngine
    match = {"they_can_teach": ["time_management", "self_efficacy"]}
    reason = RecommendationEngine.explain_tutor(match)
    assert "时间管理" in reason or "自我效能" in reason


# ── API endpoint (direct call with monkeypatched engine) ───────────

def test_api_peer_suggestions_returns_sanitized():
    _seed_profiles()
    from backend.app.api.v1 import social as social_api
    from backend.app.services.social.recommendation_engine import RecommendationEngine

    def _fake_engine():
        return RecommendationEngine()
    social_api._get_engine = _fake_engine

    resp = social_api.peer_suggestions(user_id="u1", limit=3, explain=True)
    assert resp["user_id"] == "u1"
    assert resp["total"] >= 1
    assert resp["suggestions"][0]["user_id"] == "u2"
    assert "score" not in resp["suggestions"][0]  # privacy
    assert "reason" in resp["suggestions"][0]
    assert "privacy_note" in resp


def test_api_tutor_suggestions_returns_sanitized():
    _seed_profiles()
    from backend.app.api.v1 import social as social_api
    from backend.app.services.social.recommendation_engine import RecommendationEngine

    social_api._get_engine = lambda: RecommendationEngine()
    resp = social_api.tutor_suggestions(user_id="u1", limit=3, explain=True)
    assert resp["total"] >= 1
    assert all(s.get("role") in {"课程教师", "AI 概念导师", "AI 工程导师"} for s in resp["suggestions"])
    assert all(not str(s["user_id"]).startswith("demo-student-") for s in resp["suggestions"])


def test_api_peer_suggestions_empty_for_unknown_user():
    from backend.app.api.v1 import social as social_api
    from backend.app.services.social.recommendation_engine import RecommendationEngine
    social_api._get_engine = lambda: RecommendationEngine()
    resp = social_api.peer_suggestions(user_id="ghost", limit=5, explain=True)
    assert resp["total"] == 0
    assert resp["suggestions"] == []
