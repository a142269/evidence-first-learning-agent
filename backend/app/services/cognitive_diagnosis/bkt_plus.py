"""BKT+ per-student / per-skill parameter estimation (Yudelson 2013).

Extends standard BKT with individual student parameters:
  - L0_s: student-specific initial mastery
  - T_s: student-specific learning rate
  - S_k: skill-specific slip (kept per-skill for identifiability)
  - G_k: skill-specific guess

Fitting: Moment estimation + EM refinement on per-student × per-skill cells.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BKTPlus:
    """BKT+ model with per-student and per-skill parameters."""

    def __init__(self, max_iter: int = 20, tolerance: float = 1e-3):
        self.max_iter = max_iter
        self.tolerance = tolerance
        # Parameters
        self._l0: Dict[str, float] = {}      # per student
        self._t: Dict[str, float] = {}        # per student
        self._slip: Dict[str, float] = {}     # per skill
        self._guess: Dict[str, float] = {}    # per skill

    def fit(self, data: dict[str, list[dict[str, Any]]]) -> None:
        """
        Fit BKT+ parameters.
        :param data: {student_id: [{skill_id, correct, timestamp}, ...]}
        """
        # Collect per-student × per-skill statistics
        student_skills: Dict[str, Dict[str, list[int]]] = {}
        for sid, seq in data.items():
            if sid not in student_skills:
                student_skills[sid] = {}
            for entry in seq:
                skill = entry.get("skill_id", "")
                if skill not in student_skills[sid]:
                    student_skills[sid][skill] = []
                student_skills[sid][skill].append(1 if entry.get("correct") else 0)

        # Initialize per-skill slip/guess from overall data
        all_skills = set()
        for sid, skills in student_skills.items():
            all_skills.update(skills.keys())

        for skill in all_skills:
            all_responses = []
            for sid, skills in student_skills.items():
                if skill in skills:
                    all_responses.extend(skills[skill])
            if all_responses:
                correct_rate = sum(all_responses) / len(all_responses)
                self._guess[skill] = max(0.05, min(0.4, correct_rate * 0.5))
                self._slip[skill] = max(0.01, min(0.3, (1 - correct_rate) * 0.5))
            else:
                self._guess[skill] = 0.2
                self._slip[skill] = 0.1

        # Initialize per-student L0 and T from their first skill
        for sid, skills in student_skills.items():
            first_skill = next(iter(skills))
            responses = skills[first_skill]
            if responses:
                self._l0[sid] = max(0.05, min(0.5, sum(responses[:3]) / max(1, len(responses[:3]))))
                # Learning rate: count transitions from incorrect to correct
                transitions = sum(
                    1 for i in range(1, len(responses))
                    if responses[i - 1] == 0 and responses[i] == 1
                )
                self._t[sid] = max(0.05, min(0.5, transitions / max(1, len(responses) - 1)))
            else:
                self._l0[sid] = 0.3
                self._t[sid] = 0.1

        # EM refinement (simplified: 1-2 iterations for speed)
        for _ in range(min(self.max_iter, 5)):
            # E-step: compute mastery posterior for each student × skill
            for sid, skills in student_skills.items():
                for skill, responses in skills.items():
                    mastery = self._l0.get(sid, 0.3)
                    slip = self._slip.get(skill, 0.1)
                    guess = self._guess.get(skill, 0.2)
                    t = self._t.get(sid, 0.1)

                    weights = []
                    for c in responses:
                        eta = mastery
                        if c:
                            p_obs_l = 1 - slip
                            p_obs_nl = guess
                        else:
                            p_obs_l = slip
                            p_obs_nl = 1 - guess
                        denom = p_obs_l * eta + p_obs_nl * (1 - eta)
                        if denom > 1e-9:
                            mastery = p_obs_l * eta / denom
                        weights.append((mastery, c))
                        mastery = min(0.99, mastery + (1 - mastery) * t)

                    # M-step: update slip/guess with shrinkage toward prior
                    sum_eta = sum(e for e, _ in weights)
                    if sum_eta > 1e-6:
                        new_slip = sum(e * (1 - c) for e, c in weights) / sum_eta
                        self._slip[skill] = 0.7 * self._slip[skill] + 0.3 * max(0.01, min(0.35, new_slip))

                    sum_not_eta = sum(1 - e for e, _ in weights)
                    if sum_not_eta > 1e-6:
                        new_guess = sum((1 - e) * c for e, c in weights) / sum_not_eta
                        self._guess[skill] = 0.7 * self._guess[skill] + 0.3 * max(0.05, min(0.4, new_guess))

        logger.info("[BKT+] fit: %d students, %d skills", len(self._l0), len(self._slip))

    def predict(self, student_id: str, skill_id: str, history: list[int]) -> float:
        """Predict next-step correctness probability."""
        mastery = self._l0.get(student_id, 0.3)
        slip = self._slip.get(skill_id, 0.1)
        guess = self._guess.get(skill_id, 0.2)
        t = self._t.get(student_id, 0.1)

        for c in history:
            p_correct = mastery * (1 - slip) + (1 - mastery) * guess
            if c:
                p_obs_l, p_obs_nl = 1 - slip, guess
            else:
                p_obs_l, p_obs_nl = slip, 1 - guess
            denom = mastery * p_obs_l + (1 - mastery) * p_obs_nl
            if denom > 1e-9:
                mastery = mastery * p_obs_l / denom
            mastery = min(0.99, mastery + (1 - mastery) * t)

        return mastery * (1 - slip) + (1 - mastery) * guess

    def get_params(self, student_id: str, skill_id: str) -> dict[str, float]:
        return {
            "L0": self._l0.get(student_id, 0.3),
            "T": self._t.get(student_id, 0.1),
            "S": self._slip.get(skill_id, 0.1),
            "G": self._guess.get(skill_id, 0.2),
        }

    def params_summary(self) -> dict[str, Any]:
        return {
            "n_students": len(self._l0),
            "n_skills": len(self._slip),
            "avg_L0": round(sum(self._l0.values()) / max(1, len(self._l0)), 4),
            "avg_T": round(sum(self._t.values()) / max(1, len(self._t)), 4),
            "avg_S": round(sum(self._slip.values()) / max(1, len(self._slip)), 4),
            "avg_G": round(sum(self._guess.values()) / max(1, len(self._guess)), 4),
        }


def bkt_plus_adapter_fit(data: dict[str, list[dict[str, Any]]]) -> BKTPlus:
    """Convenience wrapper for benchmark use."""
    model = BKTPlus()
    model.fit(data)
    return model
