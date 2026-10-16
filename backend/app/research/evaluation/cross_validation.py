"""
Student-wise K-Fold Cross Validation

Splits data by student IDs (not by individual interactions),
preventing data leakage in knowledge tracing benchmarks.

References:
    - Piech et al. (2015): "we split by student"
    - DeChalambet et al. (2024): standard KT evaluation protocol
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Generator, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def student_kfold_split(
    student_ids: List[str],
    n_folds: int = 5,
    seed: int = 42,
) -> Generator[Tuple[List[str], List[str]], None, None]:
    """Generate train/test student ID splits for K-fold CV.

    Students are shuffled (with seed for reproducibility) then partitioned.
    Each fold uses 1/K as test, rest as train.

    Args:
        student_ids: List of all student identifiers.
        n_folds: Number of folds.
        seed: Random seed for shuffling.

    Yields:
        (train_students, test_students) tuples, K times.
    """
    rng = np.random.RandomState(seed)
    shuffled = list(student_ids)
    perm = rng.permutation(len(shuffled))
    shuffled = [shuffled[i] for i in perm]

    fold_size = len(shuffled) // n_folds
    folds = []
    for i in range(n_folds):
        start = i * fold_size
        end = start + fold_size if i < n_folds - 1 else len(shuffled)
        folds.append(shuffled[start:end])

    for i in range(n_folds):
        test = folds[i]
        train = []
        for j in range(n_folds):
            if j != i:
                train.extend(folds[j])
        yield train, test


def run_cross_validation(
    data: Dict[str, Any],
    model_adapter,
    n_folds: int = 5,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run full cross-validation pipeline for one model.

    Args:
        data: Benchmark data dict from prepare_benchmark_data().
        model_adapter: Model adapter with fit(data, train_students) and
                      predict_proba(data, test_students) methods.
        n_folds: Number of CV folds.
        seed: Random seed for fold splitting.

    Returns:
        dict with fold_results, mean_metrics, std_metrics.
    """
    from backend.app.research.evaluation.metrics import compute_all_metrics

    fold_results = []
    all_y_true: List[int] = []
    all_y_prob: List[float] = []

    for fold_idx, (train_students, test_students) in enumerate(
        student_kfold_split(data["student_ids"], n_folds=n_folds, seed=seed)
    ):
        logger.info(
            "[%s] Fold %d/%d: train=%d, test=%d",
            model_adapter.name, fold_idx + 1, n_folds,
            len(train_students), len(test_students),
        )

        # Train
        model_adapter.fit(data, train_students)

        # Predict — all adapters use next-step KT protocol over sequences
        y_prob = model_adapter.predict_proba(data, test_students)

        # Collect ground truth by replaying test students' sequences
        # (same order as adapters: student → sequence steps)
        y_true = []
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        for uid in test_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            for entry in seq:
                y_true.append(entry["correct"])

        if len(y_true) != len(y_prob):
            logger.warning(
                "[%s] Fold %d: y_true=%d, y_prob=%d mismatch, truncating",
                model_adapter.name, fold_idx, len(y_true), len(y_prob),
            )
            min_len = min(len(y_true), len(y_prob))
            y_true = y_true[:min_len]
            y_prob = y_prob[:min_len]

        fold_metrics = compute_all_metrics(y_true, y_prob)
        fold_metrics["fold"] = fold_idx
        fold_metrics["train_time"] = model_adapter.get_train_time()
        fold_metrics["n_train"] = len(train_students)
        fold_metrics["n_test"] = len(test_students)
        fold_results.append(fold_metrics)

        all_y_true.extend(y_true)
        all_y_prob.extend(y_prob)

        logger.info(
            "[%s] Fold %d: AUC=%.4f, RMSE=%.4f, Acc=%.4f, train_time=%.2fs",
            model_adapter.name, fold_idx + 1,
            fold_metrics["auc"], fold_metrics["rmse"],
            fold_metrics["accuracy"], fold_metrics["train_time"],
        )

    # Aggregate
    metric_keys = ["auc", "rmse", "accuracy"]
    mean_metrics = {}
    std_metrics = {}
    for key in metric_keys:
        values = [r[key] for r in fold_results]
        mean_metrics[key] = float(np.mean(values))
        std_metrics[key] = float(np.std(values))

    overall_metrics = compute_all_metrics(all_y_true, all_y_prob)

    result = {
        "model": model_adapter.name,
        "n_folds": n_folds,
        "fold_results": fold_results,
        "mean_metrics": mean_metrics,
        "std_metrics": std_metrics,
        "overall_metrics": overall_metrics,
        "total_test_samples": len(all_y_true),
    }

    logger.info(
        "[%s] Overall: AUC=%.4f±%.4f, RMSE=%.4f±%.4f, Acc=%.4f±%.4f",
        model_adapter.name,
        mean_metrics["auc"], std_metrics["auc"],
        mean_metrics["rmse"], std_metrics["rmse"],
        mean_metrics["accuracy"], std_metrics["accuracy"],
    )

    return result
