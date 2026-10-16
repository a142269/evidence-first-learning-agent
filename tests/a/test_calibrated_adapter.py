"""Contract + numeric tests for CalibratedAdapter (Platt-scaling wrapper)."""
from __future__ import annotations

import numpy as np
import pytest

from backend.app.research.evaluation.calibrated_adapter import (
    CalibratedAdapter,
    _logreg_1d,
)


# ---------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------
class _BiasedAdapter:
    """Returns probabilities tightly clustered around 0.5 - mimicking dina_a's
    calibration failure mode. Output for a (synthetic) student is a function
    of how many '1' responses precede each step."""

    name = "biased"

    def __init__(self, slope: float = 0.05, base: float = 0.5) -> None:
        self.slope = slope
        self.base = base
        self._train_time = 0.0
        self._fit_called = False

    def fit(self, data, train_students):
        self._train_time = 0.01
        self._fit_called = True

    def predict_proba(self, data, test_students):
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        out: list[float] = []
        for uid in test_students:
            seq = seq_by_student[uid]
            run = 0
            for entry in seq:
                run += entry["correct"]
                # Tightly compressed around base
                p = self.base + self.slope * (run / max(1, len(seq)) - 0.5)
                p = float(np.clip(p, 0.05, 0.95))
                out.append(p)
        return out

    def get_train_time(self):
        return self._train_time


def _toy_data(n_students: int = 60, n_steps: int = 30, seed: int = 0):
    rng = np.random.default_rng(seed)
    student_ids = [f"u{i}" for i in range(n_students)]
    sequences = []
    skill_ids = ["s0"]
    for i in range(n_students):
        skill_level = i / n_students  # ramp 0->1
        seq = []
        for _ in range(n_steps):
            correct = int(rng.random() < skill_level)
            seq.append({"item_id": "s0", "skill_id": "s0", "correct": correct})
        sequences.append(seq)
    return {
        "student_ids": student_ids,
        "sequences": sequences,
        "skill_ids": skill_ids,
        "item_ids": skill_ids,
        "q_matrix": np.eye(1),
        "n_students": n_students,
        "n_skills": 1,
        "n_items": 1,
        "n_interactions": n_students * n_steps,
    }


# ---------------------------------------------------------------
# Contract
# ---------------------------------------------------------------
def test_name_includes_platt_suffix():
    inner = _BiasedAdapter()
    wrapped = CalibratedAdapter(inner)
    assert wrapped.name == "biased+Platt"


def test_rejects_invalid_hold_out():
    with pytest.raises(ValueError):
        CalibratedAdapter(_BiasedAdapter(), hold_out=0.0)
    with pytest.raises(ValueError):
        CalibratedAdapter(_BiasedAdapter(), hold_out=1.0)


def test_fit_forwards_to_base_and_learns_calibration():
    data = _toy_data()
    inner = _BiasedAdapter()
    wrapped = CalibratedAdapter(inner, hold_out=0.3)
    wrapped.fit(data, data["student_ids"][:50])

    assert inner._fit_called, "base adapter fit() should be invoked"
    assert wrapped._a is not None and wrapped._b is not None, "calibration must be fitted"


def test_predict_returns_valid_probabilities():
    data = _toy_data()
    wrapped = CalibratedAdapter(_BiasedAdapter(), hold_out=0.3)
    wrapped.fit(data, data["student_ids"][:50])
    probs = wrapped.predict_proba(data, data["student_ids"][50:])
    arr = np.array(probs)
    assert arr.size > 0
    assert ((arr >= 0.0) & (arr <= 1.0)).all()


def test_calibration_expands_probability_range():
    """The point of Platt scaling: a biased adapter clustered near 0.5 should
    have its calibrated output spread out toward 0 and 1."""
    data = _toy_data()
    inner = _BiasedAdapter(slope=0.05)
    wrapped = CalibratedAdapter(inner, hold_out=0.3)
    wrapped.fit(data, data["student_ids"][:50])

    raw = np.array(inner.predict_proba(data, data["student_ids"][50:]))
    cal = np.array(wrapped.predict_proba(data, data["student_ids"][50:]))

    # Raw probs are clustered tightly; calibrated spread should be larger.
    raw_std = float(raw.std())
    cal_std = float(cal.std())
    assert cal_std > raw_std, (
        f"calibration should expand probability range: raw_std={raw_std:.4f}, cal_std={cal_std:.4f}"
    )


def test_calibration_preserves_monotonic_ranking():
    """Platt scaling is a monotone transform - the ranking (and hence AUC)
    must not change."""
    data = _toy_data()
    inner = _BiasedAdapter()
    wrapped = CalibratedAdapter(inner, hold_out=0.3)
    wrapped.fit(data, data["student_ids"][:50])

    raw = inner.predict_proba(data, data["student_ids"][50:])
    cal = wrapped.predict_proba(data, data["student_ids"][50:])

    raw_order = np.argsort(raw)
    cal_order = np.argsort(cal)
    assert (raw_order == cal_order).all(), "calibration must preserve ranking"


def test_too_small_holdout_raises():
    data = _toy_data(n_students=3)
    wrapped = CalibratedAdapter(_BiasedAdapter(), hold_out=0.3)
    with pytest.raises(ValueError):
        wrapped.fit(data, data["student_ids"])


def test_get_train_time_forwards():
    wrapped = CalibratedAdapter(_BiasedAdapter())
    wrapped.fit(_toy_data(), _toy_data()["student_ids"][:40])
    assert wrapped.get_train_time() > 0.0


# ---------------------------------------------------------------
# Newton-Raphson 1D logistic regression
# ---------------------------------------------------------------
def test_logreg_1d_recovers_known_logistic():
    """Generate y from y = sigmoid(a x + b) with known (a, b), check recovery."""
    rng = np.random.default_rng(0)
    n = 2000
    x = rng.normal(size=n)
    a_true, b_true = 1.8, -0.4
    p = 1.0 / (1.0 + np.exp(-(a_true * x + b_true)))
    y = (rng.random(n) < p).astype(int)
    a_hat, b_hat = _logreg_1d(x, y, max_iter=200)
    assert abs(a_hat - a_true) < 0.2, f"a estimate off: {a_hat} vs {a_true}"
    assert abs(b_hat - b_true) < 0.2, f"b estimate off: {b_hat} vs {b_true}"


def test_logreg_1d_handles_degenerate_uniform_labels():
    """All-ones (or all-zeros) labels should not crash the solver."""
    x = np.linspace(-2, 2, 100)
    y_all_one = np.ones(100, dtype=int)
    a, b = _logreg_1d(x, y_all_one, max_iter=50)
    # Should return finite parameters even if they tend to infinity in theory.
    assert np.isfinite(a) and np.isfinite(b)


# ---------------------------------------------------------------
# Integration: CalibratedAdapter inside run_cross_validation
# ---------------------------------------------------------------
def test_works_inside_run_cross_validation():
    """The wrapper must plug straight into the same evaluation pipeline that
    benchmark_dina_real uses, with no extra glue code."""
    from backend.app.research.evaluation.cross_validation import run_cross_validation

    data = _toy_data(n_students=40, n_steps=20)
    wrapped = CalibratedAdapter(_BiasedAdapter(), hold_out=0.25)
    result = run_cross_validation(data, wrapped, n_folds=2, seed=0)

    assert result["model"] == "biased+Platt"
    assert "mean_metrics" in result
    auc = result["mean_metrics"]["auc"]
    assert 0.0 <= auc <= 1.0
    assert result["n_folds"] == 2
