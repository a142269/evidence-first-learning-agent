"""HLR (Half-Life Regression) — Settles 2016 ACL.

Core idea: model recall probability as
    p_recall = 2^(-t / h)
where h is "half-life" (days until recall probability drops to 50%).

Parameters: theta = [bias, feature_weights...]
Logistic loss: L = sum( (p_true - p_pred)^2 ) + lambda * ||theta||^2
"""
from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class HLRModel:
    """Half-Life Regression for spaced repetition."""

    def __init__(self, learning_rate: float = 0.01, regularization: float = 0.01, max_iter: int = 100):
        self.lr = learning_rate
        self.lam = regularization
        self.max_iter = max_iter
        # theta = [bias, n_reviews_weight, time_since_last_weight]
        self.theta = [0.0, 0.0, 0.0]

    def _features(self, n_reviews: int, time_since_last: float) -> list[float]:
        """Feature vector: [1, log(n_reviews+1), log(time_since_last+1)]"""
        return [1.0, math.log(n_reviews + 1), math.log(time_since_last + 1)]

    def _predict_h(self, feats: list[float]) -> float:
        """Predict half-life from features."""
        return max(0.1, math.exp(sum(t * f for t, f in zip(self.theta, feats))))

    def predict_recall(self, n_reviews: int, time_since_last: float) -> float:
        """Predict recall probability after time_since_last days."""
        h = self._predict_h(self._features(n_reviews, time_since_last))
        return math.pow(2.0, -time_since_last / h)

    def fit(self, data: list[dict[str, Any]]) -> None:
        """Fit theta on list of {n_reviews, time_since_last, recalled}."""
        for _ in range(self.max_iter):
            grad = [0.0, 0.0, 0.0]
            for row in data:
                feats = self._features(row["n_reviews"], row["time_since_last"])
                h = self._predict_h(feats)
                p_pred = math.pow(2.0, -row["time_since_last"] / h)
                p_true = 1.0 if row["recalled"] else 0.0
                error = p_pred - p_true
                # dL/dh * dh/dtheta
                dloss = error * p_pred * math.log(2) * row["time_since_last"] / (h * h)
                for j in range(len(self.theta)):
                    grad[j] += dloss * h * feats[j] + self.lam * self.theta[j]

            for j in range(len(self.theta)):
                self.theta[j] -= self.lr * grad[j] / max(len(data), 1)

    def review(self, n_reviews: int, time_since_last: float, recalled: bool) -> float:
        """Update model after one review observation."""
        self.fit([{"n_reviews": n_reviews, "time_since_last": time_since_last, "recalled": recalled}])
        return self.predict_recall(n_reviews + 1, 0.0)

    def next_interval(self, n_reviews: int, target_p: float = 0.9) -> float:
        """Recommend next interval to achieve target recall probability."""
        h = self._predict_h(self._features(n_reviews, 0))
        if target_p >= 1.0:
            return 0.1
        return -h * math.log2(target_p)


def sm2_vs_fsrs_vs_hlr_report(n_items: int = 200) -> dict[str, Any]:
    """Generate three-way comparison report."""
    import random
    from backend.app.services.spaced_repetition.sm2 import SM2
    from backend.app.services.spaced_repetition.fsrs import FSRS45

    random.seed(42)
    sm2 = SM2()
    fsrs = FSRS45()
    hlr = HLRModel()

    # Generate synthetic review history
    history = []
    for i in range(n_items):
        item = f"item_{i % 50}"
        recalled = random.random() > 0.3
        q = random.choices([0, 1, 2, 3, 4, 5], weights=[5, 10, 15, 30, 25, 15])[0]
        sm2.review("u1", item, q)
        r_fsrs = min(4, max(1, q - 1))
        fsrs.review(item, r_fsrs)
        history.append({"n_reviews": i % 5 + 1, "time_since_last": random.uniform(1, 30), "recalled": recalled})

    hlr.fit(history)

    return {
        "n_items": n_items,
        "sm2": sm2.stats("u1"),
        "fsrs": fsrs.stats(),
        "hlr": {
            "theta": [round(t, 4) for t in hlr.theta],
            "avg_predicted_recall": round(
                sum(hlr.predict_recall(h["n_reviews"], h["time_since_last"]) for h in history) / len(history), 4
            ),
        },
        "note": "HLR models half-life directly; SM-2 uses 1-param easiness; FSRS-4.5 uses 17-param memory model.",
    }
