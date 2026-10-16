"""Active Learning — Uncertainty Sampling for next-best-question recommendation.

Based on Settles 2009 Active Learning Survey.
Core idea: pick the question whose predicted correctness probability is closest to 0.5
(maximum entropy → highest information gain).

Uses existing BKT / DINA states from StateRepository + QuestionBank.
"""
from __future__ import annotations

import logging
import math
from typing import Any

from backend.app.services.question_bank import QuestionBank, get_question_bank

logger = logging.getLogger(__name__)


def _binary_entropy(p: float) -> float:
    """Shannon entropy of a Bernoulli trial with probability p."""
    p = max(1e-9, min(1 - 1e-9, p))
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def _bkt_predict_correct(p_learned: float, p_slip: float, p_guess: float) -> float:
    """BKT probability of correct answer: P(correct) = p_learned*(1-p_slip) + (1-p_learned)*p_guess."""
    return p_learned * (1 - p_slip) + (1 - p_learned) * p_guess


def _dina_predict_correct(mastery: float, slip: float, guess: float) -> float:
    """DINA probability of correct answer: P(correct) = (1-slip)*mastery + guess*(1-mastery)."""
    return (1 - slip) * mastery + guess * (1 - mastery)


class UncertaintySampler:
    """Active Learning sampler: select the question with maximum predicted entropy."""

    def __init__(self, bank: QuestionBank | None = None):
        self.bank = bank or get_question_bank()

    def recommend(
        self,
        user_id: str,
        mastery_map: dict[str, float],
        param_map: dict[str, dict[str, float]] | None = None,
        kp_filter: str | None = None,
        bloom_filter: str | None = None,
        top_k: int = 5,
        strategy: str = "entropy",
    ) -> list[dict[str, Any]]:
        """
        Return the top-k questions with highest information gain.

        :param mastery_map: {kp_id: p_learned_or_mastery} from BKT or DINA
        :param param_map:   {kp_id: {"slip": ..., "guess": ...}} from BKT or DINA
        :param strategy:    "entropy" | "margin" | "least_confident"
        """
        if not mastery_map:
            # Fallback: random sample from question bank
            pool = self.bank.filter(kp_id=kp_filter, bloom=bloom_filter)
            if not pool:
                return []
            import random
            rng = random.Random(hash(user_id) & 0x7FFFFFFF)
            picked = rng.sample(pool, k=min(top_k, len(pool)))
            return [{"question": q, "score": 0.5, "reason": "random_fallback"} for q in picked]

        # Build candidate pool
        if kp_filter:
            pool = self.bank.filter(kp_id=kp_filter, bloom=bloom_filter)
        else:
            pool = self.bank.filter(kp_id=None, bloom=bloom_filter)

        if not pool:
            return []

        scored = []
        for q in pool:
            kp_id = q.get("kp_id", "")
            mastery = mastery_map.get(kp_id, 0.5)
            params = (param_map or {}).get(kp_id, {})
            slip = params.get("slip", 0.1)
            guess = params.get("guess", 0.2)

            p_correct = _bkt_predict_correct(mastery, slip, guess)
            # Also try DINA formula if params differ; for BKT they are similar
            # Use entropy as default uncertainty measure
            if strategy == "entropy":
                score = _binary_entropy(p_correct)
            elif strategy == "margin":
                score = 1.0 - abs(p_correct - 0.5) * 2.0
            elif strategy == "least_confident":
                score = 1.0 - max(p_correct, 1 - p_correct)
            else:
                score = _binary_entropy(p_correct)

            scored.append({
                "question": q,
                "score": round(score, 4),
                "p_correct": round(p_correct, 4),
                "reason": f"{strategy}_uncertainty",
                "kp_id": kp_id,
                "bloom": q.get("bloom", ""),
            })

        # Sort by score descending (higher uncertainty = more informative)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


class ActiveLearningService:
    """High-level service that wraps UncertaintySampler + state hydration."""

    def __init__(self, bank: QuestionBank | None = None):
        self.sampler = UncertaintySampler(bank=bank)

    def next_best_questions(
        self,
        user_id: str,
        kp_id: str | None = None,
        bloom: str | None = None,
        top_k: int = 5,
        strategy: str = "entropy",
    ) -> dict[str, Any]:
        """
        Query user's BKT/DINA states from StateRepository, then run uncertainty sampling.
        """
        from backend.app.services.cognitive_diagnosis.state_repository import get_state_repo

        repo = get_state_repo()
        # Try BKT first, then DINA fallback
        bkt_states = repo.load_all_bkt(user_id)
        dina_states = repo.load_dina_snapshot(user_id)

        mastery_map: dict[str, float] = {}
        param_map: dict[str, dict[str, float]] = {}

        if bkt_states:
            for kp, state in bkt_states.items():
                mastery_map[kp] = state.get("p_learned", 0.3)
                param_map[kp] = {
                    "slip": state.get("p_slip", 0.1),
                    "guess": state.get("p_guess", 0.2),
                }
        elif dina_states:
            for kp, state in dina_states.items():
                mastery_map[kp] = state.get("mastery", 0.3)
                param_map[kp] = {
                    "slip": state.get("slip", 0.1),
                    "guess": state.get("guess", 0.2),
                }

        recommendations = self.sampler.recommend(
            user_id=user_id,
            mastery_map=mastery_map,
            param_map=param_map,
            kp_filter=kp_id,
            bloom_filter=bloom,
            top_k=top_k,
            strategy=strategy,
        )

        # Learning paths and BKT use graph IDs (for example AI_015), while the
        # curated question bank keeps stable semantic IDs (multimodal_llm).
        # Reuse the canonical knowledge-index mapping when a direct lookup is
        # empty, and normalize the returned question back to the graph ID so
        # answering it updates the same learner-state node that triggered it.
        if kp_id and not recommendations:
            try:
                from backend.app.services.knowledge_index import get_knowledge_index

                mapped_questions = get_knowledge_index().practice_for_kp(
                    kp_id,
                    n=top_k,
                    bloom=bloom,
                    seed=hash((user_id, kp_id)) & 0x7FFFFFFF,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[active-learning] graph-to-bank mapping failed: %s", exc)
                mapped_questions = []

            mastery = float(mastery_map.get(kp_id, 0.5))
            params = param_map.get(kp_id, {})
            p_correct = _bkt_predict_correct(
                mastery,
                float(params.get("slip", 0.1)),
                float(params.get("guess", 0.2)),
            )
            if strategy == "margin":
                score = 1.0 - abs(p_correct - 0.5) * 2.0
            elif strategy == "least_confident":
                score = 1.0 - max(p_correct, 1 - p_correct)
            else:
                score = _binary_entropy(p_correct)
            for question in mapped_questions:
                bank_kp_id = str(question.get("kp_id") or "")
                normalized_question = {
                    **question,
                    "bank_kp_id": bank_kp_id,
                    "kp_id": kp_id,
                }
                recommendations.append({
                    "question": normalized_question,
                    "score": round(score, 4),
                    "p_correct": round(p_correct, 4),
                    "reason": f"{strategy}_uncertainty_mapped",
                    "kp_id": kp_id,
                    "bank_kp_id": bank_kp_id,
                    "bloom": normalized_question.get("bloom", ""),
                })

        return {
            "user_id": user_id,
            "strategy": strategy,
            "top_k": top_k,
            "based_on": "bkt" if bkt_states else ("dina" if dina_states else "random"),
            "recommendations": recommendations,
        }


# ── module singleton ──
_al_service: ActiveLearningService | None = None


def get_active_learning_service() -> ActiveLearningService:
    global _al_service
    if _al_service is None:
        _al_service = ActiveLearningService()
    return _al_service
