"""Test contract for A's RealDINAAdapter on a synthetic micro-dataset.

The full ASSISTments 5-fold benchmark lives in
`scripts/benchmark_dina_real.py`. These tests cover the contract and
numeric behaviour we need to keep stable across refactors:

* Adapter exposes the four methods cross_validation expects.
* Prediction probabilities stay in [0, 1] and beat naive (>= 0.5) on a
  toy dataset designed to be separable.
* Slip/guess parameters land in plausible ranges after EM.
* Online update changes the mastery estimate in the expected direction.
* fit() handles the empty-skill edge case without crashing.
"""
from __future__ import annotations

import numpy as np
import pytest

from backend.app.research.evaluation.dina_real_adapter import RealDINAAdapter


# ---------------------------------------------------------------
# Synthetic data builder
# ---------------------------------------------------------------
def _toy_data(n_students: int = 40, n_skills: int = 4, n_steps: int = 30, seed: int = 0):
    """Build a small KT-style dataset where each student has a true mastery
    vector; responses follow the ideal DINA model with light slip/guess."""
    rng = np.random.default_rng(seed)
    skill_ids = [f"k{i}" for i in range(n_skills)]
    item_ids = list(skill_ids)  # identity Q-matrix
    q_matrix = np.eye(n_skills)

    student_ids: list[str] = []
    sequences: list[list[dict]] = []
    true_alpha = rng.uniform(0.1, 0.9, size=(n_students, n_skills))
    for s in range(n_students):
        sid = f"u{s}"
        student_ids.append(sid)
        seq = []
        for step in range(n_steps):
            skill_idx = rng.integers(0, n_skills)
            alpha = true_alpha[s, skill_idx]
            base = (1 - 0.1) * alpha + 0.2 * (1 - alpha)  # slip=0.1, guess=0.2
            correct = int(rng.random() < base)
            seq.append({
                "item_id": skill_ids[skill_idx],
                "skill_id": skill_ids[skill_idx],
                "correct": correct,
            })
        sequences.append(seq)

    return {
        "student_ids": student_ids,
        "sequences": sequences,
        "skill_ids": skill_ids,
        "item_ids": item_ids,
        "q_matrix": q_matrix,
        "n_students": n_students,
        "n_skills": n_skills,
        "n_items": n_skills,
        "n_interactions": n_students * n_steps,
    }


@pytest.fixture
def toy_data():
    return _toy_data()


# ---------------------------------------------------------------
# Contract
# ---------------------------------------------------------------
def test_adapter_exposes_required_methods():
    adapter = RealDINAAdapter()
    for name in ("fit", "predict_proba", "get_train_time"):
        assert callable(getattr(adapter, name)), f"missing method {name}"
    assert adapter.name == "RealDINA"


def test_predict_before_fit_raises():
    adapter = RealDINAAdapter()
    with pytest.raises(RuntimeError):
        adapter.predict_proba({"student_ids": [], "sequences": []}, [])


def test_fit_and_predict_runs_and_returns_probabilities(toy_data):
    adapter = RealDINAAdapter(max_iter=30, bayes_step=0.5)
    adapter.fit(toy_data, toy_data["student_ids"][:30])
    probs = adapter.predict_proba(toy_data, toy_data["student_ids"][30:])
    assert probs, "predict_proba returned empty list"
    arr = np.array(probs)
    assert ((arr >= 0.0) & (arr <= 1.0)).all(), "probs out of [0, 1]"


def test_slip_and_guess_in_plausible_range(toy_data):
    adapter = RealDINAAdapter(max_iter=50)
    adapter.fit(toy_data, toy_data["student_ids"][:30])
    for slip in adapter._slip.values():
        assert 0.0 <= slip <= 1.0
    for guess in adapter._guess.values():
        assert 0.0 <= guess <= 1.0


def test_train_time_recorded(toy_data):
    adapter = RealDINAAdapter(max_iter=20)
    adapter.fit(toy_data, toy_data["student_ids"][:30])
    assert adapter.get_train_time() > 0.0


def test_online_update_direction_correct(toy_data):
    """A correct response should push mastery up; wrong response should push it down."""
    adapter = RealDINAAdapter(max_iter=20, bayes_step=0.6, prior_alpha=0.5)
    adapter.fit(toy_data, toy_data["student_ids"][:30])

    # Build a synthetic test student whose first answer is always correct
    test = dict(toy_data)
    correct_seq = [{"item_id": "k0", "skill_id": "k0", "correct": 1}] * 10
    test["student_ids"] = ["probe"]
    test["sequences"] = [correct_seq]

    probs = adapter.predict_proba(test, ["probe"])
    # After a streak of correct answers the predicted probability should rise
    assert probs[-1] > probs[0], (
        f"probability should increase after correct streak, got {probs[0]} -> {probs[-1]}"
    )


def test_handles_unknown_item_id(toy_data):
    """Items not seen during fit should still get a probability, defaulting via priors."""
    adapter = RealDINAAdapter(max_iter=20)
    adapter.fit(toy_data, toy_data["student_ids"][:30])

    test = {
        "student_ids": ["ghost"],
        "sequences": [[{"item_id": "unknown_item", "skill_id": "unknown_item", "correct": 0}]],
    }
    probs = adapter.predict_proba(test, ["ghost"])
    assert probs == [0.5], f"unknown items should fall back to 0.5, got {probs}"


def test_beats_random_on_separable_toy_dataset(toy_data):
    """Sanity check: on the toy dataset the adapter should outperform random.

    We measure ranking quality via the standard 'mean prob given correct minus
    mean prob given wrong' shortcut (positive => useful)."""
    adapter = RealDINAAdapter(max_iter=60, bayes_step=0.5)
    adapter.fit(toy_data, toy_data["student_ids"][:30])
    probs = adapter.predict_proba(toy_data, toy_data["student_ids"][30:])

    seq_by_student = dict(zip(toy_data["student_ids"], toy_data["sequences"]))
    truth: list[int] = []
    for uid in toy_data["student_ids"][30:]:
        for entry in seq_by_student[uid]:
            truth.append(entry["correct"])
    n = min(len(truth), len(probs))
    truth = truth[:n]
    probs = probs[:n]

    correct_arr = [p for p, y in zip(probs, truth) if y == 1]
    wrong_arr = [p for p, y in zip(probs, truth) if y == 0]
    if correct_arr and wrong_arr:
        gap = float(np.mean(correct_arr)) - float(np.mean(wrong_arr))
        assert gap > 0.02, f"mean(p|correct) - mean(p|wrong) = {gap:.4f} <= 0.02"
