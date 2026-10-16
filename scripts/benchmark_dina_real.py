#!/usr/bin/env python3
"""A-owned DINA comparative benchmark.

Runs four cognitive-diagnosis adapters on the same ASSISTments-2009 fold
split and emits a side-by-side report:

* `naive`      - majority-rate baseline                  (B)
* `bkt`        - 4-parameter Bayesian Knowledge Tracing  (B)
* `dina_b`     - B's two-stage super-attribute DINA      (B)
* `dina_a`     - A's full Q-matrix DINA with online posterior update (A, new)
* `ensemble`   - mean of (dina_b, dina_a, bkt) probabilities          (A, new)

Why a separate script:
* `scripts/benchmark_cognitive_models.py` is B-owned; this one stays additive.
* We need identical fold splits to make AUC comparisons fair, so the script
  shares one `prepare_benchmark_data` call and one `student_kfold_split` seed
  across all adapters.
* The ensemble run reuses cached predictions, so adding it costs zero training.

Usage:
    # Full 5-fold on the entire filtered dataset (~10-25 min depending on dina)
    python scripts/benchmark_dina_real.py

    # Quick smoke on 200 students, 2 folds
    python scripts/benchmark_dina_real.py --smoke

    # Pick subset of models
    python scripts/benchmark_dina_real.py --models naive,bkt,dina_a,ensemble

Outputs:
    reports/dina_real_{timestamp}.json   - raw fold + overall metrics
    reports/dina_real_{timestamp}.md     - human-readable comparison table
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.research.datasets.assistments import prepare_benchmark_data
from backend.app.research.evaluation.adapters import (
    BKTAdapter,
    DINAAdapter,
    DKTAdapter,
    NaiveModelAdapter,
)
from backend.app.research.evaluation.calibrated_adapter import CalibratedAdapter
from backend.app.research.evaluation.cross_validation import student_kfold_split
from backend.app.research.evaluation.dina_real_adapter import RealDINAAdapter
from backend.app.research.evaluation.metrics import compute_all_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dina-real-bench")

REPORTS_DIR = PROJECT_ROOT / "reports"
TARGET_AUC = 0.78  # v7 plan goal


MODEL_FACTORIES = {
    "naive": lambda: NaiveModelAdapter(),
    "bkt": lambda: BKTAdapter(),
    "dina_b": lambda: DINAAdapter(max_iter=100),
    # max_iter=30 keeps RealDINA tractable on the full ASSISTments-2009
    # filter (~730 train students × 297 items mean-field VI). Smoke runs
    # showed AUC plateaus before 30 iters anyway.
    "dina_a": lambda: RealDINAAdapter(max_iter=30, bayes_step=0.5),
    "dina_a_cal": lambda: CalibratedAdapter(
        RealDINAAdapter(max_iter=30, bayes_step=0.5),
        hold_out=0.2,
    ),
    # DKT (Piech 2015) — closes the v6 Phase 2 BKT-vs-DKT comparison.
    # Cheap defaults: hidden=64, 1 LSTM layer, 20 epochs, batch=32.
    # On CPU torch this fits 730 students in ~60-180s/fold.
    "dkt": lambda: DKTAdapter(
        hidden_dim=64,
        n_layers=1,
        max_epochs=20,
        batch_size=32,
    ),
}


def _collect_truth(data: dict, test_students: list[str]) -> list[int]:
    """Replay test students' sequences in the same order adapters used."""
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


def _summarize_folds(folds: list[dict]) -> dict[str, Any]:
    """Compute mean ± std for each metric across folds."""
    summary: dict[str, Any] = {"folds": folds}
    for key in ("auc", "rmse", "accuracy"):
        vals = [f[key] for f in folds]
        summary[f"mean_{key}"] = float(np.mean(vals))
        summary[f"std_{key}"] = float(np.std(vals))
    summary["mean_train_time"] = float(np.mean([f["train_time"] for f in folds]))
    return summary


def run_benchmark(
    selected: list[str],
    n_folds: int,
    smoke: bool,
    granularity: str = "skill",
    min_item_freq: int = 20,
) -> dict[str, Any]:
    logger.info("=" * 60)
    logger.info("Loading ASSISTments-2009 (granularity=%s) ...", granularity)
    t0 = time.perf_counter()
    extra: dict[str, Any] = {"item_granularity": granularity}
    if granularity == "problem":
        extra["min_item_freq"] = min_item_freq
    data = prepare_benchmark_data(
        min_interactions=5 if not smoke else 50,
        min_skill_freq=50 if not smoke else 500,
        **extra,
    )
    logger.info(
        "Loaded in %.1fs: %d students, %d skills, %d items, %d interactions",
        time.perf_counter() - t0,
        data["n_students"], data["n_skills"],
        data["n_items"], data["n_interactions"],
    )

    if smoke:
        keep = data["student_ids"][:200]
        keep_set = set(keep)
        data["sequences"] = [
            seq for sid, seq in zip(data["student_ids"], data["sequences"])
            if sid in keep_set
        ]
        data["student_ids"] = keep
        data["n_students"] = len(keep)
        logger.info("[smoke] subsampled to %d students", data["n_students"])

    folds = list(
        student_kfold_split(data["student_ids"], n_folds=n_folds, seed=42)
    )

    # Cache per-adapter probabilities so the ensemble row reuses them.
    fold_probs: dict[str, dict[int, list[float]]] = {m: {} for m in selected if m != "ensemble"}
    fold_truth: dict[int, list[int]] = {}
    per_model_folds: dict[str, list[dict]] = {m: [] for m in selected}
    per_model_time: dict[str, float] = {m: 0.0 for m in selected}

    for fold_idx, (train_students, test_students) in enumerate(folds):
        logger.info("-" * 60)
        logger.info("Fold %d/%d: train=%d test=%d",
                    fold_idx + 1, n_folds,
                    len(train_students), len(test_students))
        truth = _collect_truth(data, test_students)
        fold_truth[fold_idx] = truth

        for name in selected:
            if name == "ensemble":
                continue
            adapter = MODEL_FACTORIES[name]()
            adapter.fit(data, train_students)
            probs = adapter.predict_proba(data, test_students)
            tt = adapter.get_train_time()
            per_model_time[name] += tt

            n = min(len(truth), len(probs))
            metrics = compute_all_metrics(truth[:n], probs[:n])
            metrics["fold"] = fold_idx
            metrics["train_time"] = tt
            metrics["n_train"] = len(train_students)
            metrics["n_test"] = len(test_students)
            per_model_folds[name].append(metrics)
            fold_probs[name][fold_idx] = probs[:n]
            logger.info(
                "[%-8s] fold %d  AUC=%.4f  RMSE=%.4f  Acc=%.4f  train=%.1fs",
                name, fold_idx + 1, metrics["auc"], metrics["rmse"],
                metrics["accuracy"], tt,
            )

        if "ensemble" in selected:
            # Ensemble = mean of probs from dina_b + dina_a + bkt that already ran
            members = [m for m in ("dina_b", "dina_a", "bkt")
                       if m in fold_probs and fold_idx in fold_probs[m]]
            if len(members) >= 2:
                arr = np.array([fold_probs[m][fold_idx] for m in members])
                ens_probs = arr.mean(axis=0).tolist()
                n = min(len(truth), len(ens_probs))
                metrics = compute_all_metrics(truth[:n], ens_probs[:n])
                metrics["fold"] = fold_idx
                metrics["train_time"] = 0.0
                metrics["n_train"] = len(train_students)
                metrics["n_test"] = len(test_students)
                metrics["members"] = members
                per_model_folds["ensemble"].append(metrics)
                logger.info(
                    "[ensemble] fold %d  AUC=%.4f  RMSE=%.4f  Acc=%.4f  (avg of %s)",
                    fold_idx + 1, metrics["auc"], metrics["rmse"],
                    metrics["accuracy"], "+".join(members),
                )

    aggregated: dict[str, Any] = {}
    for name in selected:
        if not per_model_folds[name]:
            continue
        summary = _summarize_folds(per_model_folds[name])
        summary["total_train_time"] = per_model_time.get(name, 0.0)
        aggregated[name] = summary

    q = data["q_matrix"]
    return {
        "data": {
            "n_students": data["n_students"],
            "n_skills": data["n_skills"],
            "n_items": data["n_items"],
            "n_interactions": data["n_interactions"],
            "smoke": smoke,
            "n_folds": n_folds,
            "granularity": granularity,
            "mean_q_per_item": float(q.sum(axis=1).mean()),
            "max_q_per_item": int(q.sum(axis=1).max()),
            "pct_multi_skill_items": float((q.sum(axis=1) >= 2).mean()),
        },
        "models": aggregated,
        "target_auc": TARGET_AUC,
        "timestamp": datetime.now().isoformat(),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    out: list[str] = []
    meta = report["data"]
    out.append("# DINA comparative benchmark (A's RealDINAAdapter vs baselines)\n")
    out.append(f"> Generated: {report['timestamp']}")
    out.append(f"> Dataset: ASSISTments-2009 ({'smoke' if meta['smoke'] else 'full'})")
    out.append(
        f"> Students={meta['n_students']}  Skills={meta['n_skills']}  "
        f"Items={meta['n_items']}  Interactions={meta['n_interactions']}  "
        f"Folds={meta['n_folds']}  Granularity={meta.get('granularity', 'skill')}\n"
    )
    if "mean_q_per_item" in meta:
        out.append(
            f"> Q-matrix: mean q-per-item={meta['mean_q_per_item']:.3f}, "
            f"max={meta['max_q_per_item']}, "
            f"multi-skill items={meta['pct_multi_skill_items'] * 100:.1f}%\n"
        )
    out.append(f"v7 target: AUC >= {report['target_auc']}\n")

    out.append("## Overall results")
    out.append("")
    out.append("| model | AUC | RMSE | Accuracy | mean train time (s) | hits target? |")
    out.append("|-------|-----|------|----------|---------------------|--------------|")
    for name in ("naive", "bkt", "dina_b", "dina_a", "dina_a_cal", "dkt", "ensemble"):
        if name not in report["models"]:
            continue
        m = report["models"][name]
        hit = "yes" if m["mean_auc"] >= report["target_auc"] else "no"
        out.append(
            f"| {name} | {m['mean_auc']:.4f} +/- {m['std_auc']:.4f} | "
            f"{m['mean_rmse']:.4f} | {m['mean_accuracy']:.4f} | "
            f"{m['mean_train_time']:.1f} | {hit} |"
        )

    out.append("\n## Per-fold detail\n")
    for name, summary in report["models"].items():
        out.append(f"### {name}")
        out.append("")
        out.append("| fold | AUC | RMSE | Accuracy | train time (s) | n_train | n_test |")
        out.append("|------|-----|------|----------|----------------|---------|--------|")
        for f in summary["folds"]:
            out.append(
                f"| {f['fold'] + 1} | {f['auc']:.4f} | {f['rmse']:.4f} | "
                f"{f['accuracy']:.4f} | {f['train_time']:.1f} | "
                f"{f['n_train']} | {f['n_test']} |"
            )
        out.append("")

    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="DINA A vs B vs ensemble benchmark")
    parser.add_argument(
        "--models",
        default="naive,bkt,dina_b,dina_a,dina_a_cal,dkt,ensemble",
        help="comma-separated subset of {naive,bkt,dina_b,dina_a,dina_a_cal,dkt,ensemble}",
    )
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--smoke", action="store_true",
                        help="200-student subsample + 2 folds")
    parser.add_argument("--granularity", choices=("skill", "problem"), default="skill",
                        help="item_granularity for prepare_benchmark_data")
    parser.add_argument("--min-item-freq", type=int, default=20,
                        help="min item frequency when granularity=problem")
    parser.add_argument("--out", default=str(REPORTS_DIR),
                        help="output directory for report files")
    args = parser.parse_args()

    selected = [m.strip() for m in args.models.split(",") if m.strip()]
    invalid = set(selected) - set(MODEL_FACTORIES.keys()) - {"ensemble"}
    if invalid:
        logger.error("Unknown models requested: %s", sorted(invalid))
        sys.exit(2)

    n_folds = 2 if args.smoke else args.folds

    report = run_benchmark(
        selected,
        n_folds=n_folds,
        smoke=args.smoke,
        granularity=args.granularity,
        min_item_freq=args.min_item_freq,
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"dina_real_{stamp}.json"
    md_path = out_dir / f"dina_real_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    logger.info("=" * 60)
    logger.info("Benchmark done")
    logger.info("JSON: %s", json_path)
    logger.info("MD:   %s", md_path)
    logger.info("=" * 60)

    headers = ["model", "AUC", "RMSE", "Acc", "hit?"]
    print()
    print(" ".join(f"{h:<12}" for h in headers))
    print("-" * (12 * len(headers)))
    for name in ("naive", "bkt", "dina_b", "dina_a", "dina_a_cal", "dkt", "ensemble"):
        if name not in report["models"]:
            continue
        m = report["models"][name]
        hit = "YES" if m["mean_auc"] >= TARGET_AUC else "no"
        row = [
            name,
            f"{m['mean_auc']:.4f}+/-{m['std_auc']:.4f}",
            f"{m['mean_rmse']:.4f}",
            f"{m['mean_accuracy']:.4f}",
            hit,
        ]
        print(" ".join(f"{c:<12}" for c in row))


if __name__ == "__main__":
    main()
