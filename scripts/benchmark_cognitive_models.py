#!/usr/bin/env python3
"""
认知诊断模型 Benchmark — DINA / BKT / DKT / Naive 在 ASSISTments-2009 上对照

用法:
    # 跑全部四模型（DKT 较慢，约 20-40 分钟）
    python scripts/benchmark_cognitive_models.py

    # 只跑快速模型（DINA + BKT + Naive，跳过 DKT）
    python scripts/benchmark_cognitive_models.py --models dina,bkt,naive

    # 自定义 fold 数和输出目录
    python scripts/benchmark_cognitive_models.py --folds 5 --out reports/

    # 快速冒烟测试（1 fold + 采样学生）
    python scripts/benchmark_cognitive_models.py --smoke

输出:
    reports/benchmark_{timestamp}.json  — 完整结果（每 fold 每模型）
    reports/benchmark_{timestamp}.md    — Markdown 对比表
    控制台                              — 实时进度
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.research.datasets.assistments import prepare_benchmark_data
from backend.app.research.evaluation.adapters import (
    BKTAdapter,
    DINAAdapter,
    DKTAdapter,
    NaiveModelAdapter,
    SAKTAdapter,
)
from backend.app.research.evaluation.cross_validation import run_cross_validation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("benchmark")


MODEL_REGISTRY = {
    "naive": lambda: NaiveModelAdapter(),
    "bkt": lambda: BKTAdapter(),
    "dina": lambda: DINAAdapter(max_iter=100, n_super=12),
    "dkt": lambda: DKTAdapter(hidden_dim=128, n_layers=2, max_epochs=50, batch_size=64),
    "sakt": lambda: SAKTAdapter(embed_dim=128, num_heads=8, num_layers=1, max_epochs=30, batch_size=64),
}


def format_sm2_fsrs_hlr_markdown(report: dict) -> str:
    """Render the spaced-repetition comparison as display-ready markdown."""
    sm2 = report.get("sm2", {})
    fsrs = report.get("fsrs", {})
    hlr = report.get("hlr", {})

    lines = [
        "# SM-2 vs FSRS vs HLR",
        "",
        f"- n_items: {report.get('n_items', 0)}",
        "",
        "## Summary",
        "",
        "| Model | Key metrics |",
        "|------|-------------|",
        f"| SM-2 | {sm2} |",
        f"| FSRS | {fsrs} |",
        f"| HLR | {hlr} |",
        "",
        "## Interpretation",
        "",
        str(report.get("note", "")),
    ]
    return "\n".join(lines)


def run_benchmark(
    models: list[str],
    n_folds: int,
    smoke: bool,
    out_dir: Path,
) -> dict:
    """Run benchmark for selected models and return aggregated results."""
    # Load data once (shared across all models)
    logger.info("=" * 60)
    logger.info("Loading ASSISTments-2009 dataset...")
    t0 = time.perf_counter()
    data = prepare_benchmark_data(
        min_interactions=5 if not smoke else 50,
        min_skill_freq=50 if not smoke else 500,
    )
    logger.info(
        "Data loaded in %.1fs: %d students, %d skills, %d items, %d interactions",
        time.perf_counter() - t0,
        data["n_students"], data["n_skills"],
        data["n_items"], data["n_interactions"],
    )

    if smoke:
        # Subsample students for fast smoke test
        import random
        random.seed(42)
        all_students = list(data["responses"].keys())
        keep = random.sample(all_students, min(200, len(all_students)))
        keep_set = set(keep)
        # Rebuild all data structures consistently for the subsample
        seq_by_student = {
            sid: seq for sid, seq in zip(data["student_ids"], data["sequences"])
        }
        data["student_ids"] = keep
        data["responses"] = {s: data["responses"][s] for s in keep}
        data["sequences"] = [seq_by_student[s] for s in keep if s in seq_by_student]
        logger.info("[smoke] Subsampled to %d students", len(keep))
        n_folds = min(n_folds, 2)

    all_results = {}
    for model_name in models:
        if model_name not in MODEL_REGISTRY:
            logger.warning("Unknown model: %s, skipping", model_name)
            continue

        logger.info("=" * 60)
        logger.info("Benchmarking model: %s", model_name.upper())
        adapter = MODEL_REGISTRY[model_name]()

        try:
            t_start = time.perf_counter()
            result = run_cross_validation(data, adapter, n_folds=n_folds, seed=42)
            result["total_wall_time"] = time.perf_counter() - t_start
            all_results[model_name] = result
        except Exception as e:
            logger.error("Model %s failed: %s", model_name, e, exc_info=True)
            all_results[model_name] = {"error": str(e), "model": model_name}

    # Summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "dataset": {
            "name": "ASSISTments-2009",
            "n_students": data["n_students"],
            "n_skills": data["n_skills"],
            "n_items": data["n_items"],
            "n_interactions": data["n_interactions"],
        },
        "config": {
            "n_folds": n_folds,
            "smoke": smoke,
            "models": models,
        },
        "results": all_results,
    }
    return summary


def save_results(summary: dict, out_dir: Path) -> tuple[Path, Path]:
    """Save results as JSON and Markdown report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = out_dir / f"benchmark_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    logger.info("JSON saved: %s", json_path)

    md_path = out_dir / f"benchmark_{ts}.md"
    md = format_markdown_report(summary)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    logger.info("Markdown saved: %s", md_path)

    return json_path, md_path


def format_markdown_report(summary: dict) -> str:
    """Format benchmark summary as a Markdown comparison report."""
    lines = []
    lines.append("# 认知诊断模型 Benchmark 报告")
    lines.append("")
    lines.append(f"> 生成时间：{summary['timestamp']}")
    lines.append(f"> 数据集：{summary['dataset']['name']}")
    lines.append("")
    lines.append("## 数据集概况")
    lines.append("")
    lines.append(f"- 学生数：{summary['dataset']['n_students']}")
    lines.append(f"- 知识点数：{summary['dataset']['n_skills']}")
    lines.append(f"- 题目数：{summary['dataset']['n_items']}")
    lines.append(f"- 交互总数：{summary['dataset']['n_interactions']}")
    lines.append(f"- 交叉验证折数：{summary['config']['n_folds']}")
    lines.append("")

    lines.append("## 总体结果对比")
    lines.append("")
    lines.append("| 模型 | AUC ↑ | RMSE ↓ | Accuracy ↑ | 训练时间(s) | 测试样本数 |")
    lines.append("|------|-------|--------|-----------|------------|-----------|")

    for model_name, result in summary["results"].items():
        if "error" in result:
            lines.append(f"| {model_name} | ❌ ERROR | - | - | - | - |")
            continue
        m = result.get("mean_metrics", {})
        s = result.get("std_metrics", {})
        overall = result.get("overall_metrics", {})
        train_times = [fr.get("train_time", 0) for fr in result.get("fold_results", [])]
        total_train = sum(train_times)
        auc_str = f"{m.get('auc', 0):.4f} ± {s.get('auc', 0):.4f}"
        rmse_str = f"{m.get('rmse', 0):.4f} ± {s.get('rmse', 0):.4f}"
        acc_str = f"{m.get('accuracy', 0):.4f} ± {s.get('accuracy', 0):.4f}"
        n = result.get("total_test_samples", 0)
        lines.append(
            f"| **{model_name}** | {auc_str} | {rmse_str} | {acc_str} | "
            f"{total_train:.1f} | {n} |"
        )

    lines.append("")
    lines.append("## 各 Fold 详细结果")
    lines.append("")
    for model_name, result in summary["results"].items():
        if "error" in result:
            continue
        lines.append(f"### {model_name}")
        lines.append("")
        lines.append("| Fold | AUC | RMSE | Accuracy | 训练时间(s) | 训练学生 | 测试学生 |")
        lines.append("|------|-----|------|----------|------------|---------|---------|")
        for fr in result.get("fold_results", []):
            lines.append(
                f"| {fr['fold']+1} | {fr['auc']:.4f} | {fr['rmse']:.4f} | "
                f"{fr['accuracy']:.4f} | {fr.get('train_time', 0):.1f} | "
                f"{fr.get('n_train', 0)} | {fr.get('n_test', 0)} |"
            )
        lines.append("")

    lines.append("## 参考论文报告值（ASSISTments-2009）")
    lines.append("")
    lines.append("| 模型 | 论文报告 AUC | 来源 |")
    lines.append("|------|-------------|------|")
    lines.append("| DKT | 0.80 - 0.86 | Piech et al. NIPS 2015 |")
    lines.append("| DINA | 0.75 - 0.82 | 多篇 EDM 论文 |")
    lines.append("| BKT | 0.65 - 0.75 | Corbett & Anderson 1995 复现 |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="认知诊断模型 Benchmark（ASSISTments-2009）"
    )
    parser.add_argument(
        "--models",
        default="naive,bkt,dina,dkt",
        help="逗号分隔的模型名（naive/bkt/dina/dkt），默认全部",
    )
    parser.add_argument(
        "--folds", type=int, default=5, help="交叉验证折数，默认 5"
    )
    parser.add_argument(
        "--out", default="reports", help="结果输出目录，默认 reports/"
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="冒烟测试模式（采样 200 学生 + 2 fold）",
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    out_dir = Path(args.out)

    logger.info("Benchmark 配置: models=%s, folds=%d, smoke=%s",
                models, args.folds, args.smoke)

    summary = run_benchmark(models, args.folds, args.smoke, out_dir)
    json_path, md_path = save_results(summary, out_dir)

    # Print summary table to console
    logger.info("=" * 60)
    logger.info("Benchmark 完成！结果汇总：")
    logger.info("=" * 60)
    print()
    print(f"{'模型':<10} {'AUC':<18} {'RMSE':<18} {'Accuracy':<18}")
    print("-" * 64)
    for model_name, result in summary["results"].items():
        if "error" in result:
            print(f"{model_name:<10} ERROR: {result['error'][:40]}")
            continue
        m = result.get("mean_metrics", {})
        s = result.get("std_metrics", {})
        print(
            f"{model_name:<10} "
            f"{m.get('auc', 0):.4f} ± {s.get('auc', 0):.4f}    "
            f"{m.get('rmse', 0):.4f} ± {s.get('rmse', 0):.4f}    "
            f"{m.get('accuracy', 0):.4f} ± {s.get('accuracy', 0):.4f}"
        )
    print()
    print(f"详细报告: {md_path}")
    print(f"原始数据: {json_path}")


if __name__ == "__main__":
    main()
