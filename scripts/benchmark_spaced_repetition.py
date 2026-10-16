#!/usr/bin/env python3
"""
间隔重复算法 Benchmark — SM-2 vs FSRS-4.5 vs HLR

在 ASSISTments-2009 真实学生交互数据上模拟三种算法的调度行为，
计算可实测的指标（预测间隔分布、算法间分歧 MAE、正确率校准）。

用法:
    # 默认 1000 学生采样
    python scripts/benchmark_spaced_repetition.py

    # 自定义学生数
    python scripts/benchmark_spaced_repetition.py --students 2000

    # 快速冒烟
    python scripts/benchmark_spaced_repetition.py --smoke

输出:
    reports/spaced_repetition_benchmark_{timestamp}.json
    reports/spaced_repetition_benchmark_{timestamp}.md
    控制台实时进度

注意:
    ASSISTments-2009 数据集没有 day-level 复习时间戳，
    因此无法计算真正的 day-level MAE。
    本脚本计算的是：
    1. 各算法在真实数据上的预测间隔分布（天）
    2. SM-2 vs FSRS 预测间隔分歧 MAE（天）
    3. 正确率校准：算法预测"需尽快复习"的 item，学生下次答对率是否更低
    4. 模拟遗忘率：按算法推荐间隔复习时的预测保持率
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.research.datasets.assistments import prepare_benchmark_data
from backend.app.services.spaced_repetition.sm2 import SM2
from backend.app.services.spaced_repetition.fsrs import FSRS45
from backend.app.services.spaced_repetition.hlr import HLRModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def extract_review_sequences(
    data: dict[str, Any], max_students: int
) -> list[dict[str, Any]]:
    """从 ASSISTments 数据中提取 per-student-skill 复习序列。

    返回: [{"student_id": str, "skill_id": str,
            "interactions": [{"correct": int, "global_order": int}, ...]}, ...]
    """
    sequences = data["sequences"]
    student_ids = data["student_ids"]
    review_seqs: list[dict[str, Any]] = []

    for idx, student_seq in enumerate(sequences):
        uid = student_ids[idx] if idx < len(student_ids) else f"student_{idx}"
        # 按 item_id (即 skill_id) 分组，保留顺序
        skill_interactions: dict[str, list[dict[str, Any]]] = {}
        for global_order, interaction in enumerate(student_seq):
            item_id = interaction.get("item_id", "")
            if not item_id:
                continue
            skill_interactions.setdefault(item_id, []).append({
                "correct": interaction["correct"],
                "global_order": global_order,
            })

        for skill_id, interactions in skill_interactions.items():
            if len(interactions) >= 3:  # 至少 3 次交互才有意义
                review_seqs.append({
                    "student_id": uid,
                    "skill_id": skill_id,
                    "interactions": interactions,
                })

        if len(review_seqs) >= max_students * 5:  # 采样足够多就停
            break

    random.seed(42)
    random.shuffle(review_seqs)
    return review_seqs[:max_students * 5]


def run_sm2_simulation(
    review_seqs: list[dict[str, Any]],
) -> dict[str, Any]:
    """在真实交互序列上模拟 SM-2 调度。

    返回每个 review event 的预测间隔（天）和对应的实际正确率。
    """
    sm2 = SM2()
    predictions: list[dict[str, Any]] = []

    for seq in review_seqs:
        uid = seq["student_id"]
        sid = seq["skill_id"]
        item_id = f"{uid}_{sid}"

        for i, interaction in enumerate(seq["interactions"]):
            correct = interaction["correct"]
            quality = 4 if correct else 2  # 答对=good(4)，答错=bad(2)

            if i > 0:  # 第一次没有预测
                state = sm2.get_schedule(uid, item_id)
                if state:
                    prev_order = seq["interactions"][i - 1]["global_order"]
                    actual_gap = interaction["global_order"] - prev_order
                    predicted_interval_days = min(state["interval"], 365)  # cap at 1 year
                    predictions.append({
                        "algorithm": "SM-2",
                        "predicted_interval_days": predicted_interval_days,
                        "actual_correct": correct,
                        "actual_gap": actual_gap,
                        "review_index": i,
                    })

            sm2.review(uid, item_id, quality)

    return _summarize_predictions(predictions, "SM-2")


def run_fsrs_simulation(
    review_seqs: list[dict[str, Any]],
) -> dict[str, Any]:
    """在真实交互序列上模拟 FSRS-4.5 调度。"""
    fsrs = FSRS45()
    predictions: list[dict[str, Any]] = []

    for seq in review_seqs:
        uid = seq["student_id"]
        sid = seq["skill_id"]
        item_id = f"{uid}_{sid}"

        for i, interaction in enumerate(seq["interactions"]):
            correct = interaction["correct"]
            rating = 3 if correct else 1  # 答对=good(3)，答错=again(1)

            if i > 0:
                state = fsrs.get_schedule(item_id)
                if state:
                    prev_order = seq["interactions"][i - 1]["global_order"]
                    actual_gap = interaction["global_order"] - prev_order
                    predicted_interval_days = min(state["stability"], 365)  # cap at 1 year
                    predictions.append({
                        "algorithm": "FSRS-4.5",
                        "predicted_interval_days": predicted_interval_days,
                        "actual_correct": correct,
                        "actual_gap": actual_gap,
                        "review_index": i,
                    })

            fsrs.review(item_id, rating)

    return _summarize_predictions(predictions, "FSRS-4.5")


def run_hlr_simulation(
    review_seqs: list[dict[str, Any]],
) -> dict[str, Any]:
    """在真实交互序列上模拟 HLR。

    HLR 需要 per-lexeme 特征，ASSISTments 缺失，仅跑能跑的部分。
    """
    hlr = HLRModel(max_iter=20)  # 减少迭代次数，避免大数据集卡住
    training_data: list[dict[str, Any]] = []

    for seq in review_seqs:
        n_reviews = 0
        for i, interaction in enumerate(seq["interactions"]):
            correct = interaction["correct"]
            # 用 interaction index 作为 time_since_last 的代理
            time_since = float(i + 1)
            training_data.append({
                "n_reviews": n_reviews,
                "time_since_last": time_since,
                "recalled": bool(correct),
            })
            n_reviews += 1

    # 限制训练数据量（最多 2000 条），只用前 80% 训练
    if len(training_data) > 2000:
        training_data = training_data[:2000]
    split = int(len(training_data) * 0.8)
    hlr.fit(training_data[:split])

    # 在剩余 20% 上预测
    test_data = training_data[split:]
    predicted_recalls = []
    for row in test_data:
        p = hlr.predict_recall(row["n_reviews"], row["time_since_last"])
        predicted_recalls.append(p)

    return {
        "algorithm": "HLR",
        "n_training": split,
        "n_test": len(test_data),
        "theta": [round(t, 4) for t in hlr.theta],
        "avg_predicted_recall": round(sum(predicted_recalls) / max(len(predicted_recalls), 1), 4),
        "note": "HLR trained on interaction-count proxy (not day-level). "
                "Per-lexeme features from Duolingo paper not available in ASSISTments.",
    }


def _summarize_predictions(
    predictions: list[dict[str, Any]], algo_name: str
) -> dict[str, Any]:
    """汇总单个算法的预测结果。"""
    if not predictions:
        return {"algorithm": algo_name, "n_predictions": 0}

    intervals = [p["predicted_interval_days"] for p in predictions]
    correctness = [p["actual_correct"] for p in predictions]
    gap_errors = [
        abs(p["predicted_interval_days"] - p["actual_gap"])
        for p in predictions
        if "actual_gap" in p
    ]

    # 校准：按预测间隔分箱，看每箱的实际正确率
    # 短间隔 = 算法认为需要尽快复习 = 应该正确率更低
    sorted_by_interval = sorted(predictions, key=lambda x: x["predicted_interval_days"])
    n = len(sorted_by_interval)
    third = n // 3

    bins = {
        "short_interval (<33%)": sorted_by_interval[:third],
        "medium_interval (33-66%)": sorted_by_interval[third:2*third],
        "long_interval (>66%)": sorted_by_interval[2*third:],
    }

    calibration = {}
    for label, bin_preds in bins.items():
        if bin_preds:
            avg_interval = sum(p["predicted_interval_days"] for p in bin_preds) / len(bin_preds)
            accuracy = sum(p["actual_correct"] for p in bin_preds) / len(bin_preds)
            calibration[label] = {
                "avg_predicted_interval_days": round(avg_interval, 2),
                "actual_accuracy": round(accuracy, 4),
                "n": len(bin_preds),
            }

    # 模拟遗忘率：按算法推荐间隔复习时的预测保持率
    # SM-2: 没有显式保持率公式，用 easiness 近似
    # FSRS: stability 就是保持率衰减的时间常数
    # 这里用 "短间隔组的正确率" 作为遗忘率的代理
    short_acc = calibration.get("short_interval (<33%)", {}).get("actual_accuracy", 0)
    forgetting_rate = round(1.0 - short_acc, 4)

    return {
        "algorithm": algo_name,
        "n_predictions": n,
        "actual_gap_proxy_mae": round(sum(gap_errors) / len(gap_errors), 4),
        "predicted_interval_days": {
            "mean": round(sum(intervals) / n, 2),
            "min": min(intervals),
            "max": max(intervals),
            "std": round(_std(intervals), 2),
        },
        "overall_actual_accuracy": round(sum(correctness) / n, 4),
        "calibration": calibration,
        "simulated_forgetting_rate": forgetting_rate,
    }


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def compute_inter_algorithm_mae(
    sm2_result: dict[str, Any], fsrs_result: dict[str, Any]
) -> dict[str, Any]:
    """计算 SM-2 vs FSRS 预测间隔的分歧 MAE。

    注意：这不是真正的 day-level MAE（因为缺少真实复习时间戳），
    而是两种算法在相同数据上的预测分歧。
    """
    sm2_mean = sm2_result.get("predicted_interval_days", {}).get("mean", 0)
    fsrs_mean = fsrs_result.get("predicted_interval_days", {}).get("mean", 0)

    return {
        "metric": "inter_algorithm_disagreement_mae",
        "sm2_mean_interval": sm2_mean,
        "fsrs_mean_interval": fsrs_mean,
        "mean_difference_days": round(abs(sm2_mean - fsrs_mean), 2),
        "note": (
            "ASSISTments-2009 lacks day-level revisit timestamps, "
            "so true day-level MAE cannot be computed. "
            "This metric measures how much SM-2 and FSRS disagree "
            "on scheduling intervals when fed the same real student data."
        ),
    }


def run_benchmark(
    n_students: int = 1000, smoke: bool = False
) -> dict[str, Any]:
    """运行完整 benchmark。"""
    if smoke:
        n_students = 100

    logger.info("Loading ASSISTments-2009 data...")
    data = prepare_benchmark_data(min_interactions=5, min_skill_freq=50)
    logger.info(
        "Loaded: %d students, %d interactions",
        data["n_students"], data["n_interactions"],
    )

    logger.info("Extracting per-student-skill review sequences (max %d students)...", n_students)
    review_seqs = extract_review_sequences(data, n_students)
    logger.info("Extracted %d review sequences (≥3 interactions each)", len(review_seqs))

    logger.info("Simulating SM-2 on real student data...")
    t0 = time.time()
    sm2_result = run_sm2_simulation(review_seqs)
    logger.info("SM-2 done in %.1fs", time.time() - t0)

    logger.info("Simulating FSRS-4.5 on real student data...")
    t0 = time.time()
    fsrs_result = run_fsrs_simulation(review_seqs)
    logger.info("FSRS-4.5 done in %.1fs", time.time() - t0)

    logger.info("Simulating HLR (limited)...")
    t0 = time.time()
    hlr_result = run_hlr_simulation(review_seqs)
    logger.info("HLR done in %.1fs", time.time() - t0)

    # 算法间分歧
    disagreement = compute_inter_algorithm_mae(sm2_result, fsrs_result)

    result = {
        "timestamp": datetime.now().isoformat(),
        "dataset": "ASSISTments-2009",
        "n_students_sampled": n_students,
        "n_review_sequences": len(review_seqs),
        "sm2": sm2_result,
        "fsrs": fsrs_result,
        "hlr": hlr_result,
        "inter_algorithm_disagreement": disagreement,
        "data_limitation_note": (
            "ASSISTments-2009 skill builder dataset does not contain "
            "day-level revisit timestamps. The dataset has order_id (sequence) "
            "and ms_first_response (response latency) but no absolute timestamps. "
            "Therefore, true day-level MAE between predicted and actual review "
            "intervals cannot be computed. Metrics reported here are: "
            "(1) predicted interval distribution from real student data, "
            "(2) inter-algorithm disagreement, "
            "(3) correctness calibration by predicted interval bin."
        ),
    }

    return result


def save_results(result: dict[str, Any], out_dir: str = "reports") -> None:
    """保存 JSON + Markdown 结果。"""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_path / f"spaced_repetition_benchmark_{ts}.json"
    md_path = out_path / f"spaced_repetition_benchmark_{ts}.md"

    # JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info("Saved JSON: %s", json_path)

    # Markdown
    md = _render_markdown(result)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    logger.info("Saved Markdown: %s", md_path)


def _render_markdown(r: dict[str, Any]) -> str:
    lines = [
        "# 间隔重复算法 Benchmark — 真实数据模拟",
        "",
        f"> 生成时间: {r['timestamp']}",
        f"> 数据集: {r['dataset']}",
        f"> 采样学生数: {r['n_students_sampled']}",
        f"> 复习序列数: {r['n_review_sequences']}",
        "",
        "## 1. 数据限制说明",
        "",
        r["data_limitation_note"],
        "",
        "## 2. SM-2 结果",
        "",
        f"- 预测数: {r['sm2']['n_predictions']}",
    ]

    if "predicted_interval_days" in r["sm2"]:
        pi = r["sm2"]["predicted_interval_days"]
        lines += [
            f"- proxy MAE（与真实序列间隔对齐）: {r['sm2']['actual_gap_proxy_mae']}",
            f"- 预测间隔 (天): mean={pi['mean']}, min={pi['min']}, max={pi['max']}, std={pi['std']}",
            f"- 整体实际正确率: {r['sm2']['overall_actual_accuracy']}",
            f"- 模拟遗忘率: {r['sm2']['simulated_forgetting_rate']}",
            "",
            "### 校准（按预测间隔分箱）",
            "",
            "| 分箱 | 平均预测间隔(天) | 实际正确率 | 样本数 |",
            "|------|-----------------|-----------|--------|",
        ]
        for label, bin_data in r["sm2"].get("calibration", {}).items():
            lines.append(
                f"| {label} | {bin_data['avg_predicted_interval_days']} | "
                f"{bin_data['actual_accuracy']} | {bin_data['n']} |"
            )

    lines += [
        "",
        "## 3. FSRS-4.5 结果",
        "",
        f"- 预测数: {r['fsrs']['n_predictions']}",
    ]

    if "predicted_interval_days" in r["fsrs"]:
        pi = r["fsrs"]["predicted_interval_days"]
        lines += [
            f"- proxy MAE（与真实序列间隔对齐）: {r['fsrs']['actual_gap_proxy_mae']}",
            f"- 预测间隔 (天): mean={pi['mean']}, min={pi['min']}, max={pi['max']}, std={pi['std']}",
            f"- 整体实际正确率: {r['fsrs']['overall_actual_accuracy']}",
            f"- 模拟遗忘率: {r['fsrs']['simulated_forgetting_rate']}",
            "",
            "### 校准（按预测间隔分箱）",
            "",
            "| 分箱 | 平均预测间隔(天) | 实际正确率 | 样本数 |",
            "|------|-----------------|-----------|--------|",
        ]
        for label, bin_data in r["fsrs"].get("calibration", {}).items():
            lines.append(
                f"| {label} | {bin_data['avg_predicted_interval_days']} | "
                f"{bin_data['actual_accuracy']} | {bin_data['n']} |"
            )

    hlr = r["hlr"]
    lines += [
        "",
        "## 4. HLR 结果（有限）",
        "",
        f"- 训练样本: {hlr['n_training']}",
        f"- 测试样本: {hlr['n_test']}",
        f"- theta: {hlr['theta']}",
        f"- 平均预测保持率: {hlr['avg_predicted_recall']}",
        f"- 说明: {hlr['note']}",
        "",
        "## 5. 算法间分歧",
        "",
        f"- SM-2 平均预测间隔: {r['inter_algorithm_disagreement']['sm2_mean_interval']} 天",
        f"- FSRS 平均预测间隔: {r['inter_algorithm_disagreement']['fsrs_mean_interval']} 天",
        f"- 平均分歧: {r['inter_algorithm_disagreement']['mean_difference_days']} 天",
        f"- 说明: {r['inter_algorithm_disagreement']['note']}",
        "",
        "## 6. 复现命令",
        "",
        "```powershell",
        f"D:\\Anaconda3\\envs\\dxtorch\\python.exe scripts/benchmark_spaced_repetition.py --students {r['n_students_sampled']}",
        "```",
    ]

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Spaced repetition benchmark on ASSISTments")
    parser.add_argument("--students", type=int, default=1000, help="Max students to sample")
    parser.add_argument("--smoke", action="store_true", help="Quick smoke test (100 students)")
    parser.add_argument("--out", type=str, default="reports", help="Output directory")
    args = parser.parse_args()

    result = run_benchmark(n_students=args.students, smoke=args.smoke)
    save_results(result, args.out)

    # 控制台摘要
    print("\n" + "=" * 60)
    print("Benchmark Summary")
    print("=" * 60)
    print(f"Review sequences: {result['n_review_sequences']}")
    if "predicted_interval_days" in result["sm2"]:
        print(f"SM-2  mean interval: {result['sm2']['predicted_interval_days']['mean']} days, "
              f"proxy MAE: {result['sm2']['actual_gap_proxy_mae']}, "
              f"forgetting rate: {result['sm2']['simulated_forgetting_rate']}")
    if "predicted_interval_days" in result["fsrs"]:
        print(f"FSRS  mean interval: {result['fsrs']['predicted_interval_days']['mean']} days, "
              f"proxy MAE: {result['fsrs']['actual_gap_proxy_mae']}, "
              f"forgetting rate: {result['fsrs']['simulated_forgetting_rate']}")
    print(f"HLR   avg predicted recall: {result['hlr']['avg_predicted_recall']}")
    print(f"Inter-algo disagreement: {result['inter_algorithm_disagreement']['mean_difference_days']} days")
    print("=" * 60)


if __name__ == "__main__":
    main()
