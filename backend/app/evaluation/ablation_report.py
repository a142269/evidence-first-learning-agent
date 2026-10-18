"""Summarize paired ablation observations without inventing missing quality data."""
from __future__ import annotations

import math
import statistics

ARMS = ("single", "without_reviewer", "full")
RUBRICS = ("facts_supported", "exercise_answers_correct", "goal_covered", "difficulty_progression", "profile_fit")


def summarize_ablation(cases: list[dict], runs: list[dict]) -> dict:
    ids = {case["id"] for case in cases}
    if not ids or len(ids) != len(cases):
        raise ValueError("case IDs must be unique and nonempty")
    rows = {}
    configurations = set()
    evidence_by_case = {}
    for row in runs:
        key = (row.get("case_id"), row.get("arm"))
        if key[0] not in ids or key[1] not in ARMS or key in rows:
            raise ValueError("unknown or duplicate run")
        config = row.get("config")
        if not isinstance(config, dict):
            raise ValueError("fixed config required")
        config_key = tuple(config.get(key) for key in ("model", "knowledge_snapshot", "max_output_tokens", "max_cost_cny"))
        if any(value is None or value == "" for value in config_key[:3]):
            raise ValueError("fixed configuration is incomplete")
        if not isinstance(config_key[0], str) or not isinstance(config_key[1], str):
            raise ValueError("model and snapshot must be strings")
        for value in (config_key[2],) + (() if config_key[3] is None else (config_key[3],)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("budgets must be positive finite numbers")
        configurations.add(config_key)
        if type(row.get("completed")) is not bool:
            raise ValueError("completed must be boolean")
        evidence = row.get("evidence_sha256")
        if evidence is None and row["completed"]:
            raise ValueError("completed runs require evidence")
        if evidence is not None and (not isinstance(evidence, str) or not evidence):
            raise ValueError("invalid evidence digest")
        if key[0] in evidence_by_case and evidence_by_case[key[0]] != evidence:
            raise ValueError("evidence must match across arms")
        evidence_by_case[key[0]] = evidence
        for metric in ("latency_ms", "model_calls", "cost_cny", "invalid_tool_calls"):
            value = row.get(metric)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise ValueError("invalid numeric metric")
        reviews = row.get("reviews", [])
        if not isinstance(reviews, list) or len(reviews) > 2:
            raise ValueError("at most two independent reviews")
        adjudication = row.get("adjudication")
        judgments = [*reviews, *([adjudication] if adjudication is not None else [])]
        names = []
        for review in judgments:
            if not isinstance(review, dict) or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
                raise ValueError("reviewer identity required")
            names.append(review["reviewer"].strip())
            if any(metric not in review or (review[metric] is not None and type(review[metric]) is not bool) for metric in RUBRICS):
                raise ValueError("rubric values must be boolean or unknown")
        if len(names) != len(set(names)):
            raise ValueError("reviewer identities must be distinct")
        if adjudication is not None and (
            not row["completed"] or len(reviews) != 2 or
            not any(type(reviews[0][k]) is bool and type(reviews[1][k]) is bool
                    and reviews[0][k] != reviews[1][k] for k in RUBRICS)
        ):
            raise ValueError("adjudication requires two disagreeing reviews of a completed run")
        rows[key] = row
    if len(configurations) > 1:
        raise ValueError("models, snapshot and budgets must match across all runs")
    def average(values):
        return statistics.fmean(values) if len(values) == len(ids) else None

    def resolved_score(row, metric):
        reviews = row.get("reviews", [])
        if not row["completed"] or len(reviews) != 2:
            return None
        a, b = (review[metric] for review in reviews)
        if type(a) is not bool or type(b) is not bool:
            return None
        if a == b:
            return a
        decision = row.get("adjudication")
        return decision[metric] if decision is not None else None

    groups = {}
    for arm in ARMS:
        selected = [rows[(case_id, arm)] for case_id in ids if (case_id, arm) in rows]
        complete_reviews = [r for r in selected if r["completed"]
                            and all(type(resolved_score(r, k)) is bool for k in RUBRICS)]
        fully_reviewed = len(selected) == len(ids) and all(not r["completed"] or r in complete_reviews for r in selected)
        latencies = sorted(r["latency_ms"] for r in selected if r.get("latency_ms") is not None)
        groups[arm] = {
            "run_count": len(selected), "case_count": len(ids),
            "task_success_rate": sum(r["completed"] for r in selected) / len(ids) if len(selected) == len(ids) else None,
            "quality_pass_rate": sum(all(resolved_score(r, k) for k in RUBRICS) for r in complete_reviews) / len(ids) if fully_reviewed else None,
            "human_reviewed_completed": len(complete_reviews),
            "review_disagreement_count": sum(any(type(r["reviews"][0][k]) is bool and
                type(r["reviews"][1][k]) is bool and r["reviews"][0][k] != r["reviews"][1][k]
                for k in RUBRICS) for r in selected if len(r.get("reviews", [])) == 2),
            "mean_model_calls": average([r["model_calls"] for r in selected if r.get("model_calls") is not None]),
            "mean_cost_cny": average([r["cost_cny"] for r in selected if r.get("cost_cny") is not None]),
            "mean_invalid_tool_calls": average([r["invalid_tool_calls"] for r in selected if r.get("invalid_tool_calls") is not None]),
            "p50_latency_ms": statistics.median(latencies) if len(latencies) == len(ids) else None,
            "p95_latency_ms": latencies[math.ceil(0.95 * len(latencies)) - 1] if len(latencies) == len(ids) else None,
        }
        if arm == "full":
            outcomes = [r.get("result", {}).get("reviewer_revision_succeeded") for r in selected
                        if r.get("result", {}).get("reviewer_initially_rejected") is True]
            groups[arm]["reviewer_revision_success_rate"] = (sum(value is True for value in outcomes) / len(outcomes)
                                                              if outcomes and all(type(value) is bool for value in outcomes) else None)
            groups[arm]["reviewer_rejected_count"] = len(outcomes)
        else:
            groups[arm]["reviewer_revision_success_rate"] = None
        for metric in RUBRICS:
            metric_reviews = [r for r in selected if type(resolved_score(r, metric)) is bool]
            metric_complete = len(selected) == len(ids) and all(not r["completed"] or r in metric_reviews for r in selected)
            groups[arm][metric + "_rate"] = sum(resolved_score(r, metric) for r in metric_reviews) / len(ids) if metric_complete else None
    return {"case_count": len(ids), "configuration": list(next(iter(configurations))) if configurations else None,
            "arms": groups, "quality_denominator": "all cases; failed runs count as failures"}
