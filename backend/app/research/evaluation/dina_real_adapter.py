"""A-owned DINA adapter that uses the *real* DINA EM output for prediction.

Background
----------
The existing `DINAAdapter` (B-owned) compresses 77 ASSISTments skills into
n_super=6 super-skills before fitting DINA, then predicts with a
"last-5 correct rate" heuristic. The heuristic ignores the slip/guess that
DINA actually learned and ignores the Q-matrix entirely. Result on
ASSISTments-2009: AUC = 0.5389, worse than the Naive baseline (0.5816).

This adapter exposes the *canonical* DINA prediction:

    master(i, j) = prod_k alpha_{i,k} ** Q_{j,k}
    P(correct = 1 | student=i, item=j) = (1 - slip_j) * master + guess_j * (1 - master)

For test students whose responses are not part of the EM fit, we walk their
sequence chronologically. For each prediction step we use the *current
running estimate* of alpha (initialized at the population prior, updated by
a single-shot Bayesian step after observing the previous response). This
matches the standard "next-step prediction" protocol used in the KT
literature (Piech et al., 2015; Wang et al., 2017).

The adapter is additive — it sits alongside `DINAAdapter` and shares the
same `fit / predict_proba / get_train_time / name` interface used by
`run_cross_validation`. A side-by-side comparison report is produced by
`scripts/benchmark_dina_real.py`.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


_MIN_MASTERY = 0.05
_MAX_MASTERY = 0.95


def _skill_lookup(entry: Dict[str, Any], skill_ids: List[str]) -> Optional[str]:
    """Resolve an interaction entry to one of the dataset skill_ids.

    ASSISTments rows expose either `skill_id` or `item_id` as the skill key
    (when item_granularity="skill" the two coincide). This helper hides the
    branching so the adapter logic stays clean.
    """
    candidate = entry.get("skill_id") or entry.get("item_id")
    if candidate is None:
        return None
    sid = str(candidate)
    if sid in skill_ids:
        return sid
    return None


class RealDINAAdapter:
    """DINA adapter that uses the actual EM-fitted parameters at predict time."""

    def __init__(
        self,
        max_iter: int = 100,
        tolerance: float = 1e-4,
        prior_alpha: float = 0.5,
        bayes_step: float = 0.6,
    ) -> None:
        """
        Args:
            max_iter: EM iterations passed to the underlying DINA solver.
            tolerance: log-likelihood convergence tolerance.
            prior_alpha: initial mastery for unseen (student, skill) pairs.
            bayes_step: weight given to the most recent observation when
                updating the running alpha estimate. 1.0 → memoryless,
                0.0 → frozen. Values around 0.5-0.7 work well empirically.
        """
        self.max_iter = max_iter
        self.tolerance = tolerance
        self.prior_alpha = prior_alpha
        self.bayes_step = bayes_step

        self._slip: Dict[str, float] = {}
        self._guess: Dict[str, float] = {}
        self._train_time: float = 0.0
        self._skill_to_idx: Dict[str, int] = {}
        self._q_matrix: Optional[np.ndarray[Any, np.dtype[Any]]] = None
        self._item_ids: Optional[List[str]] = None
        self._skill_ids: Optional[List[str]] = None

    @property
    def name(self) -> str:
        return "RealDINA"

    # ------------------------------------------------------------
    # fit: run DINA EM over the training students' full response set
    # ------------------------------------------------------------
    def fit(self, data: Dict[str, Any], train_students: List[str]) -> None:
        from backend.app.services.cognitive_diagnosis.dina import DINA

        self._q_matrix = np.asarray(data["q_matrix"], dtype=float)
        self._item_ids = list(data["item_ids"])
        self._skill_ids = list(data["skill_ids"])
        self._skill_to_idx = {sid: i for i, sid in enumerate(self._skill_ids)}

        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        item_set = set(self._item_ids)

        responses: Dict[str, Dict[str, int]] = {}
        for uid in train_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            r: Dict[str, int] = {}
            for entry in seq:
                item = entry.get("item_id")
                if item is None or item not in item_set:
                    continue
                r[str(item)] = int(entry["correct"])
            if r:
                responses[uid_str] = r

        dina = DINA(max_iter=self.max_iter, tolerance=self.tolerance)  # type: ignore[no-untyped-call]
        start = time.perf_counter()
        dina.fit(  # type: ignore[no-untyped-call]
            responses,
            self._q_matrix,
            self._item_ids,
            self._skill_ids,
            list(responses.keys()),
        )
        self._train_time = time.perf_counter() - start

        # Cache slip / guess for fast lookup at predict time. Items unseen by
        # the fit (none here, since we pass the full item list, but defensive)
        # fall back to the priors used during DINA initialisation.
        for item in self._item_ids:
            self._slip[item] = float(dina.slip_.get(item, 0.1))
            self._guess[item] = float(dina.guess_.get(item, 0.2))

        logger.info(
            "[RealDINA] fit: %d students, %d items, %d skills, %.2fs, converged=%s",
            len(responses),
            len(self._item_ids),
            len(self._skill_ids),
            self._train_time,
            dina.converged_,
        )

    # ------------------------------------------------------------
    # predict_proba: walk each test student's sequence, maintaining a
    # running alpha estimate and emitting the canonical DINA probability
    # at every step.
    # ------------------------------------------------------------
    def predict_proba(self, data: Dict[str, Any], test_students: List[str]) -> List[float]:
        if self._q_matrix is None or self._item_ids is None:
            error_msg = "RealDINAAdapter.predict_proba called before fit()"
            raise RuntimeError(error_msg)

        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        assert self._item_ids is not None  # narrowed by guard above
        assert self._q_matrix is not None
        assert self._skill_ids is not None
        item_index: Dict[str, int] = {iid: idx for idx, iid in enumerate(self._item_ids)}

        probs: List[float] = []
        for uid in test_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            alpha = np.full(len(self._skill_ids), self.prior_alpha)
            for entry in seq:
                item = entry.get("item_id")
                idx = item_index.get(str(item)) if item is not None else None
                if idx is None:
                    probs.append(0.5)
                    continue

                q_row = self._q_matrix[idx]
                # ideal mastery: prod_k alpha_k ** q_row_k. Q-matrix is
                # binary, so this is a product over the skills the item taps.
                if q_row.sum() == 0:
                    master = 1.0
                else:
                    mask = q_row > 0.5
                    master = float(np.prod(alpha[mask]))
                master = max(_MIN_MASTERY, min(_MAX_MASTERY, master))

                slip = self._slip.get(str(item), 0.1)
                guess = self._guess.get(str(item), 0.2)
                prob = (1.0 - slip) * master + guess * (1.0 - master)
                probs.append(float(prob))

                # Online Bayesian-style update on the alpha vector. After
                # seeing the actual response we tug the per-skill estimates
                # toward the observed correctness (correct → up, wrong → down)
                # for the skills the item taps. The pull strength is
                # `bayes_step`. This is a deliberately lightweight surrogate
                # for a true Bayesian update (which would need posterior
                # inference over 2^K latent classes).
                correct = int(entry["correct"])
                if q_row.sum() > 0:
                    target = float(correct)
                    mask_idx = np.where(q_row > 0.5)[0]
                    alpha[mask_idx] = (
                        (1.0 - self.bayes_step) * alpha[mask_idx]
                        + self.bayes_step * target
                    )
                    np.clip(alpha, _MIN_MASTERY, _MAX_MASTERY, out=alpha)
        return probs

    def get_train_time(self) -> float:
        return self._train_time
