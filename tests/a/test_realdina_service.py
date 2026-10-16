"""Tests for RealDINAService (Day 8 wire-in)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.realdina_service import (
    RealDINAService,
    _MAX_MASTERY,
    _MIN_MASTERY,
    _PRIOR_MASTERY,
    get_realdina_service,
    reset_realdina_service,
)


@pytest.fixture
def fresh_service() -> RealDINAService:
    reset_realdina_service()
    return RealDINAService()


# ---------------------------------------------------------------
# Loading & fallback
# ---------------------------------------------------------------
def test_loads_synthesized_snapshots_when_no_precompute(fresh_service: RealDINAService):
    """No data/realdina_snapshots.json -> synthesize from seed_extended."""
    seed = json.loads(fresh_service.seed_path.read_text(encoding="utf-8"))
    assert fresh_service.known_users == sorted(seed["assessment_recipe"]["students"])
    assert {f"demo-student-{i}" for i in range(1, 6)}.issubset(fresh_service.known_users)
    assert len(fresh_service.kp_universe) == 20
    assert fresh_service.meta["source"] == "seed_synthesis"


def test_snapshot_values_in_valid_range(fresh_service: RealDINAService):
    for uid in fresh_service.known_users:
        snap = fresh_service.snapshot_for(uid)
        for kp, mast in snap.items():
            assert _MIN_MASTERY <= mast <= _MAX_MASTERY, (
                f"{uid}/{kp} mastery {mast} out of [{_MIN_MASTERY}, {_MAX_MASTERY}]"
            )


def test_loads_explicit_precompute_file(tmp_path):
    """If data/realdina_snapshots.json exists, use it instead of seed synthesis."""
    snap_path = tmp_path / "snap.json"
    snap_path.write_text(
        json.dumps({
            "_meta": {"source": "test", "version": "v1"},
            "snapshots": {
                "alice": {"python_basics": 0.91, "cnn": 0.42},
                "bob": {"python_basics": 0.55, "rnn": 0.66},
            },
        }),
        encoding="utf-8",
    )
    svc = RealDINAService(snapshot_path=snap_path)
    assert set(svc.known_users) == {"alice", "bob"}
    assert svc.meta["source"] == "test"
    assert svc.mastery("alice", "python_basics") == pytest.approx(0.91)
    assert svc.mastery("bob", "rnn") == pytest.approx(0.66)


# ---------------------------------------------------------------
# Read interface
# ---------------------------------------------------------------
def test_mastery_returns_prior_for_unknown_kp(fresh_service: RealDINAService):
    assert fresh_service.mastery("demo-student-1", "no_such_kp") == _PRIOR_MASTERY


def test_mastery_returns_prior_for_unknown_user(fresh_service: RealDINAService):
    assert fresh_service.mastery("ghost-user", "cnn") == _PRIOR_MASTERY


def test_top_strengths_returns_descending_by_mastery(fresh_service: RealDINAService):
    strengths = fresh_service.top_strengths("demo-student-1", k=5)
    assert len(strengths) == 5
    masteries = [m for _, m in strengths]
    assert masteries == sorted(masteries, reverse=True)


def test_top_weaknesses_returns_ascending(fresh_service: RealDINAService):
    weak = fresh_service.top_weaknesses("demo-student-1", k=5)
    masteries = [m for _, m in weak]
    assert masteries == sorted(masteries)


def test_top_strengths_for_unknown_user_returns_empty(fresh_service: RealDINAService):
    assert fresh_service.top_strengths("ghost-user") == []
    assert fresh_service.top_weaknesses("ghost-user") == []


def test_strong_student_outscores_weak_student(fresh_service: RealDINAService):
    """demo-student-3 has mastery_bias 0.88, demo-student-2 has 0.52.
    Mean mastery should follow."""
    s3 = fresh_service.snapshot_for("demo-student-3")
    s2 = fresh_service.snapshot_for("demo-student-2")
    mean_s3 = sum(s3.values()) / len(s3)
    mean_s2 = sum(s2.values()) / len(s2)
    assert mean_s3 > mean_s2 + 0.2, (
        f"expected student-3 (bias 0.88) > student-2 (bias 0.52) by >0.2, "
        f"got {mean_s3:.3f} vs {mean_s2:.3f}"
    )


# ---------------------------------------------------------------
# Online update path
# ---------------------------------------------------------------
def test_record_response_correct_increases_mastery(fresh_service: RealDINAService):
    initial = fresh_service.mastery("new-user", "cnn")
    fresh_service.record_response("new-user", ["cnn"], correct=True)
    after = fresh_service.mastery("new-user", "cnn")
    assert after > initial


def test_record_response_wrong_decreases_mastery(fresh_service: RealDINAService):
    initial = fresh_service.mastery("new-user", "cnn")
    fresh_service.record_response("new-user", ["cnn"], correct=False)
    after = fresh_service.mastery("new-user", "cnn")
    assert after < initial


def test_record_response_clamps_to_bounds(fresh_service: RealDINAService):
    """A long streak of correct responses must not exceed _MAX_MASTERY."""
    for _ in range(50):
        fresh_service.record_response("streak-user", ["cnn"], correct=True)
    assert fresh_service.mastery("streak-user", "cnn") <= _MAX_MASTERY
    for _ in range(50):
        fresh_service.record_response("streak-user", ["cnn"], correct=False)
    assert fresh_service.mastery("streak-user", "cnn") >= _MIN_MASTERY


def test_record_response_with_empty_kp_list_is_noop(fresh_service: RealDINAService):
    before = fresh_service.snapshot_for("demo-student-1")
    result = fresh_service.record_response("demo-student-1", [], correct=True)
    after = fresh_service.snapshot_for("demo-student-1")
    assert result == before
    assert after == before


def test_record_response_overrides_precomputed_for_same_kp(fresh_service: RealDINAService):
    """Online update should shadow the precomputed value for that user/KP."""
    uid = "demo-student-1"
    initial = fresh_service.mastery(uid, "cnn")
    fresh_service.record_response(uid, ["cnn"], correct=False)
    after = fresh_service.mastery(uid, "cnn")
    # The merged snapshot reports the updated value.
    assert after < initial
    # Other KPs are untouched.
    initial_other = fresh_service.mastery(uid, "transformer")
    after_other = fresh_service.mastery(uid, "transformer")
    assert after_other == initial_other


# ---------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------
def test_get_realdina_service_is_singleton():
    reset_realdina_service()
    a = get_realdina_service()
    b = get_realdina_service()
    assert a is b


def test_reset_clears_singleton():
    a = get_realdina_service()
    reset_realdina_service()
    b = get_realdina_service()
    assert a is not b
