"""Probability-calibration wrapper for any cognitive-diagnosis adapter.

Problem context
---------------
A's `RealDINAAdapter` ranks responses well on ASSISTments-2009 (AUC ~ 0.685)
but its raw probabilities cluster around the `prior_alpha` value (default
0.5). When thresholded at 0.5 to compute accuracy, the resulting decision
rule fires on essentially random outputs - Accuracy drops to 0.355 even
though the ranking is informative.

This wrapper rescales the base adapter's probabilities with a one-feature
logistic regression fitted on a held-out portion of the training data, a
technique known as **Platt scaling** (Platt 1999) or, with a non-parametric
back end, **isotonic regression** (Zadrozny & Elkan 2002). Calibration
keeps the AUC unchanged (it is a monotone transform) but it pulls
overconfident and underconfident predictions back toward the empirical
positive rate, which dramatically improves Accuracy/RMSE/Brier scores.

Design
------
* The wrapper is *additive* - it never touches B-owned adapters; you pass
  any adapter in at construction time.
* It owns the calibration model only; `fit()` forwards to the base
  adapter, then trains the logistic on whichever fraction of the train
  set the caller asks for (`hold_out`).
* `predict_proba()` calls the base adapter and pipes the output through
  the fitted logistic.
* It is a drop-in replacement for any adapter used by `run_cross_validation`.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


_EPS = 1e-6


class CalibratedAdapter:
    """Wraps a base cognitive-diagnosis adapter with Platt-scaling calibration."""

    def __init__(
        self,
        base_adapter: Any,
        hold_out: float = 0.2,
        max_logreg_iter: int = 200,
        random_state: int = 42,
    ) -> None:
        """
        Args:
            base_adapter: Any adapter with `fit / predict_proba / get_train_time / name`.
            hold_out: Fraction of train students reserved for fitting the
                calibration logistic. 0.2 is the Platt scaling default.
            max_logreg_iter: Iteration budget for the logistic solver.
            random_state: Seed for the hold-out split.
        """
        if not (0.0 < hold_out < 1.0):
            error_msg = f"hold_out must be in (0, 1), got {hold_out}"
            raise ValueError(error_msg)
        self.base = base_adapter
        self.hold_out = hold_out
        self.max_logreg_iter = max_logreg_iter
        self.random_state = random_state

        # Fitted calibration parameters: P_calibrated = sigmoid(a * logit(p) + b).
        # When None we fall back to raw probabilities (e.g. degenerate split).
        self._a: float | None = None
        self._b: float | None = None

    @property
    def name(self) -> str:
        return f"{self.base.name}+Platt"

    def get_train_time(self) -> float:
        return float(self.base.get_train_time())

    # ------------------------------------------------------------
    # fit
    # ------------------------------------------------------------
    def fit(self, data: dict[str, Any], train_students: list[str]) -> None:
        rng = np.random.default_rng(self.random_state)
        train_arr = np.array(train_students, dtype=object)
        n = len(train_arr)
        if n < 5:
            error_msg = f"need >=5 train students for calibration split, got {n}"
            raise ValueError(error_msg)

        idx = rng.permutation(n)
        n_holdout = max(1, int(round(self.hold_out * n)))
        holdout_ids = train_arr[idx[:n_holdout]].tolist()
        fit_ids = train_arr[idx[n_holdout:]].tolist()

        # Train the base adapter on the larger split.
        self.base.fit(data, fit_ids)

        # Score the held-out students and fit a 1-D logistic.
        probs = self.base.predict_proba(data, holdout_ids)
        truth = _collect_truth(data, holdout_ids)
        n_paired = min(len(probs), len(truth))
        probs_arr: np.ndarray[Any, np.dtype[np.float64]] = np.clip(
            np.asarray(probs[:n_paired], dtype=float), _EPS, 1.0 - _EPS
        )
        truth_arr: np.ndarray[Any, np.dtype[np.int_]] = np.asarray(truth[:n_paired], dtype=int)

        if n_paired < 20 or len(set(truth_arr.tolist())) < 2:
            logger.warning(
                "[Calibrated:%s] degenerate calibration set (n=%d, classes=%d) - "
                "falling back to identity transform",
                self.base.name, n_paired, len(set(truth_arr.tolist())),
            )
            self._a, self._b = 1.0, 0.0
            return

        # Logit-space logistic regression: y ~ a*logit(p) + b.
        logits = np.log(probs_arr / (1.0 - probs_arr))
        a, b = _logreg_1d(logits, truth_arr, max_iter=self.max_logreg_iter)
        self._a, self._b = float(a), float(b)
        logger.info(
            "[Calibrated:%s] fitted a=%.4f b=%.4f on %d held-out samples",
            self.base.name, self._a, self._b, n_paired,
        )

    # ------------------------------------------------------------
    # predict
    # ------------------------------------------------------------
    def predict_proba(self, data: dict[str, Any], test_students: list[str]) -> list[float]:
        raw = self.base.predict_proba(data, test_students)
        if self._a is None or self._b is None:
            return [float(p) for p in raw]
        arr = np.clip(np.asarray(raw, dtype=float), _EPS, 1.0 - _EPS)
        logits = np.log(arr / (1.0 - arr))
        calibrated = 1.0 / (1.0 + np.exp(-(self._a * logits + self._b)))
        return [float(p) for p in calibrated.tolist()]


def _collect_truth(data: dict[str, Any], test_students: list[str]) -> list[int]:
    """Replay test students' sequences in adapter order to align with predict_proba()."""
    seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
    truth: list[int] = []
    for uid in test_students:
        uid_str = str(uid)
        seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
        if not seq:
            continue
        for entry in seq:
            truth.append(int(entry["correct"]))
    return truth


def _logreg_1d(
    x: np.ndarray[Any, np.dtype[Any]],
    y: np.ndarray[Any, np.dtype[Any]],
    max_iter: int = 200,
    tol: float = 1e-6,
) -> tuple[float, float]:
    """Stable Newton-Raphson for one-feature logistic regression.

    Fits y ~ sigmoid(a * x + b). Pure NumPy so the wrapper picks up no
    optional dependency (sklearn would do the same job in ~3 lines but we
    keep the dependency surface minimal for the chat pipeline path).
    """
    a, b = 0.0, 0.0
    n = len(x)
    for _ in range(max_iter):
        z = a * x + b
        z = np.clip(z, -30.0, 30.0)  # avoid overflow in exp
        p = 1.0 / (1.0 + np.exp(-z))
        # Gradient
        residual = p - y
        g_a = float(np.sum(residual * x)) / n
        g_b = float(np.sum(residual)) / n
        # Hessian (diag plus off-diag term)
        w = p * (1.0 - p) + _EPS
        h_aa = float(np.sum(w * x * x)) / n
        h_ab = float(np.sum(w * x)) / n
        h_bb = float(np.sum(w)) / n
        det = h_aa * h_bb - h_ab * h_ab
        if abs(det) < 1e-12:
            break
        # Newton update: theta -= H^{-1} g
        da = (h_bb * g_a - h_ab * g_b) / det
        db = (-h_ab * g_a + h_aa * g_b) / det
        a -= da
        b -= db
        if max(abs(da), abs(db)) < tol:
            break
    return a, b
