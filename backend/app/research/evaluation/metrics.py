"""
评估指标模块 — Cognitive Diagnosis Benchmark

提供 AUC、RMSE、Accuracy 三大指标，
符合 Piech et al. (2015) 和 DeChalambet et al. (2024) 的标准评测协议。
"""
from __future__ import annotations

import logging
from typing import List

import numpy as np
from sklearn.metrics import roc_auc_score, mean_squared_error, accuracy_score

logger = logging.getLogger(__name__)


def compute_auc(y_true: List[int], y_prob: List[float]) -> float:
    """Compute Area Under the ROC Curve.

    Args:
        y_true: Binary labels (0 or 1).
        y_prob: Predicted probabilities.

    Returns:
        AUC score in [0, 1].

    Raises:
        ValueError: If labels are not binary or only one class present.
    """
    arr_true = np.array(y_true, dtype=int)
    arr_prob = np.array(y_prob, dtype=float)

    unique_labels = set(arr_true)
    if not unique_labels.issubset({0, 1}):
        raise ValueError(
            f"y_true must contain only 0 and 1, got {unique_labels}"
        )
    if len(unique_labels) < 2:
        raise ValueError("Need both classes in y_true for AUC")

    return float(roc_auc_score(arr_true, arr_prob))


def compute_rmse(y_true: List[int], y_prob: List[float]) -> float:
    """Compute Root Mean Squared Error.

    Args:
        y_true: Binary labels (0 or 1).
        y_prob: Predicted probabilities.

    Returns:
        RMSE in [0, 1].
    """
    return float(np.sqrt(mean_squared_error(y_true, y_prob)))


def compute_accuracy(y_true: List[int], y_pred: List[int]) -> float:
    """Compute classification accuracy.

    Args:
        y_true: Binary labels.
        y_pred: Predicted binary labels (threshold already applied).

    Returns:
        Accuracy in [0, 1].
    """
    return float(accuracy_score(y_true, y_pred))


def compute_all_metrics(
    y_true: List[int],
    y_prob: List[float],
) -> dict:
    """Compute all metrics at once.

    Args:
        y_true: Binary labels.
        y_prob: Predicted probabilities.

    Returns:
        dict with keys: auc, rmse, accuracy, n_samples.
    """
    y_pred = [1 if p >= 0.5 else 0 for p in y_prob]
    return {
        "auc": compute_auc(y_true, y_prob),
        "rmse": compute_rmse(y_true, y_prob),
        "accuracy": compute_accuracy(y_true, y_pred),
        "n_samples": len(y_true),
    }
