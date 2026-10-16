"""
Naive Baseline Model — 每个知识点的训练集平均正确率

作为最低基线，任何有意义的模型都应超越此基线。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class NaiveBaseline:
    """Per-skill average correctness baseline.

    For each skill, predict the mean correctness rate observed in training data.
    """

    def __init__(self, default_prob: float = 0.5):
        self.default_prob = default_prob
        self._skill_rates: Dict[str, float] = {}
        self._item_rates: Dict[str, float] = {}

    def fit(
        self,
        train_students: List[str],
        train_responses: Dict[str, Dict[str, int]],
        train_item_ids: List[str],
        train_skill_ids: List[str],
        train_q_matrix: np.ndarray,
    ) -> None:
        """Compute per-skill correctness rate from training data.

        Args:
            train_students: Student IDs for training split.
            train_responses: {student_id: {item_id: correct}} mapping.
            train_item_ids: All item IDs.
            train_skill_ids: All skill IDs.
            train_q_matrix: (n_items, n_skills) binary matrix.
        """
        skill_correct: Dict[str, List[int]] = {}
        item_correct: Dict[str, List[int]] = {}
        item_to_skills: Dict[str, List[str]] = {}
        for j, item_id in enumerate(train_item_ids):
            skills_for_item = [train_skill_ids[k] for k in range(len(train_skill_ids))
                              if train_q_matrix[j, k] > 0]
            item_to_skills[item_id] = skills_for_item
            for sk in skills_for_item:
                if sk not in skill_correct:
                    skill_correct[sk] = []

        for uid in train_students:
            for item_id, correct in train_responses.get(uid, {}).items():
                for sk in item_to_skills.get(item_id, []):
                    skill_correct[sk].append(correct)
                item_correct.setdefault(item_id, []).append(correct)

        self._skill_rates = {}
        for sk, vals in skill_correct.items():
            self._skill_rates[sk] = sum(vals) / len(vals) if vals else self.default_prob

        # Per-item rate (averaged over its skills) — used as primary prediction
        self._item_rates = {}
        for item_id, vals in item_correct.items():
            self._item_rates[item_id] = sum(vals) / len(vals) if vals else None
        # For items unseen in training, fall back to mean of their skills' rates
        for j, item_id in enumerate(train_item_ids):
            if item_id not in self._item_rates or self._item_rates[item_id] is None:
                skills_for_item = item_to_skills.get(item_id, [])
                if skills_for_item:
                    rates = [self._skill_rates.get(sk, self.default_prob) for sk in skills_for_item]
                    self._item_rates[item_id] = sum(rates) / len(rates)
                else:
                    self._item_rates[item_id] = self.default_prob

        logger.info("[NaiveBaseline] Computed rates for %d skills, %d items",
                    len(self._skill_rates), len(self._item_rates))

    def predict_proba(
        self,
        test_students: List[str],
        test_item_ids: List[str],
    ) -> List[float]:
        """Predict probability of correct response for each test item.

        For known items, returns the observed correctness rate in training data.
        For unknown items, falls back to default_prob.

        Args:
            test_students: Student IDs (unused by naive baseline).
            test_item_ids: Item IDs to predict for.

        Returns:
            List of predicted probabilities.
        """
        results = []
        for item_id in test_item_ids:
            rate = self._item_rates.get(item_id)
            results.append(rate if rate is not None else self.default_prob)
        return results
