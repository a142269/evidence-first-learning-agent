"""Offline learning-package contracts and explicit human-review coverage.

No model, application configuration or database is imported here. Contract
success is deliberately separate from factual correctness and task quality.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


EVALUATOR_VERSION = "learning-package-1.0"
HUMAN_CRITERIA = ("facts_supported", "exercise_answers_correct", "goal_covered", "difficulty_progression")
CATEGORIES = {"normal", "evidence_revision", "boundary_failure"}
OUTCOMES = {"completed", "review_required", "rejected", "failed"}
SCENARIOS = {"standard", "unused_evidence", "empty_then_evidence", "review_once", "same_source_chunks",
             "review_changes_sources", "repeated_search", "no_evidence", "fabricated_citation",
             "invalid_model_output", "review_twice", "model_budget_exhausted"}


@dataclass(frozen=True)
class PackageCase:
    id: str
    category: str
    split: str
    question: str
    course_id: str
    expected_outcome: str
    expected_sources: tuple[str, ...]
    scenario: str
    rubric: tuple[str, ...]
    expected_error: str = ""
    expected_revisions: int | None = None
    require_approval: bool = False


def load_rows(path: str | Path) -> dict[str, dict[str, Any]]:
    rows = {}
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            raise ValueError(f"Invalid JSON at line {number}") from None
        if not isinstance(row, dict) or not _text(row.get("id")):
            raise ValueError(f"Missing string id at line {number}")
        if row["id"] in rows:
            raise ValueError(f"Duplicate id at line {number}")
        rows[row["id"]] = row
    if not rows:
        raise ValueError("Input is empty")
    return rows


def load_cases(path: str | Path) -> list[PackageCase]:
    cases = []
    for row in load_rows(path).values():
        if (not all(_text(row.get(key)) for key in ("category", "split", "expected_outcome", "scenario"))
                or row.get("category") not in CATEGORIES or row.get("split") not in {"dev", "holdout"}
                or row.get("expected_outcome") not in OUTCOMES
                or row["scenario"] not in SCENARIOS
                or not all(_text(row.get(key)) for key in ("question", "course_id"))
                or not _strings(row.get("rubric")) or not row["rubric"]
                or not _strings(row.get("expected_sources"))):
            raise ValueError("Invalid learning-package case contract")
        outcome = row["expected_outcome"]
        if outcome == "completed" and not row["expected_sources"]:
            raise ValueError("Completed case needs annotated sources")
        if outcome == "failed" and not _text(row.get("expected_error")):
            raise ValueError("Failure case needs an exact error code")
        if type(row.get("require_approval", False)) is not bool:
            raise ValueError("require_approval must be boolean")
        if outcome == "review_required" and not row.get("require_approval"):
            raise ValueError("Review case must request approval")
        revision = row.get("expected_revisions")
        if revision is not None and (type(revision) is not int or revision not in (0, 1)):
            raise ValueError("Invalid revision expectation")
        try:
            cases.append(PackageCase(**{**row, "expected_sources": tuple(row["expected_sources"]),
                                       "rubric": tuple(row["rubric"])}))
        except TypeError:
            raise ValueError("Unknown or missing case fields") from None
    return cases


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _strings(value):
    return isinstance(value, list) and all(_text(item) for item in value)


def _source(value):
    return value.replace("\\", "/").removeprefix("knowledge_base/")


def _identities(items):
    if not isinstance(items, list):
        return None
    if not all(isinstance(item, dict) and _text(item.get("chunk_id")) and _text(item.get("source"))
               for item in items):
        return None
    return [(item["chunk_id"], _source(item["source"])) for item in items]


def fingerprint(case: PackageCase, prediction: Mapping[str, Any]) -> str:
    """Bind human judgements to this exact case, evidence and delivered content."""
    payload = {"case": asdict(case), "prediction": prediction}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _completed_checks(case, result):
    package = result.get("learning_package")
    package = package if isinstance(package, dict) else {}
    plan = package.get("plan", {})
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    plan_valid = (isinstance(steps, list) and len(steps) == 2
                  and all(isinstance(step, dict) and _text(step.get("id"))
                          and _text(step.get("goal")) for step in steps))
    if plan_valid:
        tutor, practice = steps
        plan_valid = (tutor.get("role") == "tutor" and practice.get("role") == "practice"
                      and tutor["id"] != practice["id"] and tutor.get("depends_on") == []
                      and practice.get("depends_on") == [tutor["id"]])
    lesson, exercises = package.get("lesson"), package.get("exercises")
    shape_valid = (isinstance(lesson, dict) and _text(lesson.get("explanation"))
                   and isinstance(exercises, list) and len(exercises) == 3
                   and all(isinstance(item, dict) and all(_text(item.get(key))
                           for key in ("question", "answer", "explanation")) for item in exercises))
    evidence = _identities(result.get("evidence"))
    evidence_valid = bool(evidence) and len({item[0] for item in evidence}) == len(evidence)
    mapping_valid = bool(shape_valid and evidence_valid)
    used = []
    if mapping_valid:
        by_id = dict(evidence)
        for artifact in [lesson, *exercises]:
            ids, citations = artifact.get("source_ids"), _identities(artifact.get("citations"))
            if not _strings(ids) or not ids or any(item not in by_id for item in ids):
                mapping_valid = False
                break
            expected = [(item, by_id[item]) for item in dict.fromkeys(ids)]
            if citations != expected:
                mapping_valid = False
            used.extend(expected)
    union_valid = mapping_valid and _identities(result.get("citations")) == list(dict.fromkeys(used))
    sources = {source for _, source in evidence} if evidence_valid else set()
    expected_sources = {_source(item) for item in case.expected_sources}
    coverage = len(sources & expected_sources) / len(expected_sources) if expected_sources else None
    review = package.get("review")
    revisions = package.get("revisions")
    review_valid = (isinstance(review, dict) and review.get("approved") is True
                    and review.get("issues") == [] and type(revisions) is int and revisions in (0, 1)
                    and (case.expected_revisions is None or revisions == case.expected_revisions))
    budget = result.get("budget")
    limits = {"model_calls": (1, 12), "tool_calls": (1, 3), "input_chars": (1, 100_000),
              "output_token_limit": (1, 12 * 2048)}
    budget_valid = isinstance(budget, dict) and all(
        type(budget.get(key)) is int and minimum <= budget[key] <= maximum
        for key, (minimum, maximum) in limits.items())
    if budget_valid:
        budget_valid = budget["output_token_limit"] == budget["model_calls"] * 2048
    scenario_valid = True
    if case.scenario == "unused_evidence":
        scenario_valid = bool(mapping_valid and set(evidence) - set(used))
    elif case.scenario == "same_source_chunks":
        scenario_valid = mapping_valid and len({chunk for chunk, _ in used}) > len({source for _, source in used})
    elif case.scenario == "empty_then_evidence":
        scenario_valid = budget_valid and budget["tool_calls"] >= 2
    elif case.scenario == "repeated_search":
        scenario_valid = budget_valid and result.get("tool_stop_reason") == "repeated_search"
    elif case.scenario in {"review_once", "review_changes_sources"}:
        scenario_valid = review_valid and revisions == 1
    return {
        "answer_present": _text(result.get("answer")), "plan_valid": bool(plan_valid),
        "package_shape_valid": bool(shape_valid), "evidence_valid": bool(evidence_valid),
        "artifact_citations_valid": bool(mapping_valid), "final_citation_union_valid": bool(union_valid),
        "expected_sources_retrieved": coverage == 1.0, "review_contract_valid": bool(review_valid),
        "reported_budget_valid": bool(budget_valid),
        "scenario_observables_valid": bool(scenario_valid),
    }, coverage


def grade_case(case: PackageCase, prediction: Mapping[str, Any], review=None):
    result = prediction.get("result", {})
    result = result if isinstance(result, dict) else {}
    events = prediction.get("events", [])
    valid_events = _strings(events)
    terminals = [item for item in events if item in {"run.completed", "run.failed", "review.required"}] if valid_events else []
    expected_event = {"completed": "run.completed", "rejected": "run.completed",
                      "failed": "run.failed", "review_required": "review.required"}[case.expected_outcome]
    checks = {"terminal_valid": terminals == [expected_event] and bool(events) and events[-1] == expected_event,
              "scenario_matches": prediction.get("scenario") == case.scenario,
              "prediction_present": bool(prediction)}
    if "collection" in prediction:
        collection = prediction["collection"]
        collection_checks = collection.get("checks") if isinstance(collection, dict) else None
        checks["collection_valid"] = (isinstance(collection_checks, dict) and bool(collection_checks)
                                      and all(value is True for value in collection_checks.values()))
    # Hidden drafts can leak via top-level fields or a nested approval object.
    protected_fields = ("learning_package", "evidence", "citations", "approval", "artifacts", "draft_answer", "sources")
    coverage = None
    if case.expected_outcome == "completed":
        checks["completed_status"] = result.get("status") == "completed" and not result.get("error")
        package_checks, coverage = _completed_checks(case, result)
        checks.update(package_checks)
    else:
        checks["no_protected_content"] = not any(result.get(key) for key in protected_fields)
        checks["no_streamed_draft"] = "answer.delta" not in events if valid_events and case.expected_outcome != "rejected" else True
        if case.expected_outcome == "failed":
            checks["expected_error"] = result.get("error") == case.expected_error
            checks["no_answer"] = not result.get("answer")
        elif case.expected_outcome == "review_required":
            checks["no_answer"] = not result.get("answer") and not result.get("error")
        else:
            quality = result.get("quality", {})
            checks["safe_rejection"] = (result.get("status") == "rejected" and _text(result.get("answer"))
                                         and not result.get("error") and isinstance(quality, dict)
                                         and (quality.get("safety_refusal") is True or quality.get("review_rejected") is True))
    contract_passed = all(checks.values())
    digest = fingerprint(case, prediction)
    human_valid = (case.expected_outcome == "completed" and isinstance(review, dict)
                   and review.get("prediction_fingerprint") == digest and _text(review.get("reviewer"))
                   and all(type(review.get(key)) is bool for key in HUMAN_CRITERIA))
    human_passed = all(review[key] for key in HUMAN_CRITERIA) if human_valid else None
    return {"id": case.id, "category": case.category, "split": case.split,
            "expected_outcome": case.expected_outcome, "scenario": case.scenario,
            "contract_passed": contract_passed, "checks": checks,
            "expected_source_coverage": coverage, "prediction_fingerprint": digest,
            "human_review_valid": human_valid, "human_quality_passed": human_passed,
            "human_review_error": "missing_or_stale_review" if case.expected_outcome == "completed" and not human_valid else None,
            "learning_quality_passed": bool(contract_passed and human_passed) if human_valid else None}


def review_template(cases, predictions):
    return [{"id": case.id, "prediction_fingerprint": fingerprint(case, predictions[case.id]),
             "reviewer": "", **dict.fromkeys(HUMAN_CRITERIA), "rubric": list(case.rubric), "notes": ""}
            for case in cases if case.expected_outcome == "completed" and case.id in predictions]


def summarise(cases, predictions, reviews=None, *, prediction_kind="synthetic"):
    if prediction_kind not in {"synthetic", "recorded"}:
        raise ValueError("Invalid prediction kind")
    cases = list(cases)
    if not cases:
        raise ValueError("No cases selected")
    reviews = reviews or {}
    if prediction_kind == "recorded" and any(
        isinstance(row.get("collection"), dict) and row["collection"].get("mode") == "synthetic_asgi"
        for row in predictions.values()
    ):
        raise ValueError("Synthetic ASGI collection cannot be relabelled as recorded model output")
    details = [grade_case(case, predictions.get(case.id, {}), reviews.get(case.id)) for case in cases]
    completed = [item for item in details if item["expected_outcome"] == "completed"]
    reviewed = [item for item in completed if item["human_review_valid"]]
    quality_complete = bool(completed) and len(reviewed) == len(completed)
    latencies = sorted(row["result"]["latency_ms"] for row in predictions.values()
                       if row.get("id") in {case.id for case in cases} and isinstance(row.get("result"), dict)
                       and type(row["result"].get("latency_ms")) in (int, float)
                       and math.isfinite(row["result"]["latency_ms"]) and row["result"]["latency_ms"] >= 0)
    summary = {
        "case_count": len(details), "contract_passed_cases": sum(item["contract_passed"] for item in details),
        "contract_pass_rate": sum(item["contract_passed"] for item in details) / len(details),
        "completed_case_count": len(completed), "human_reviewed_cases": len(reviewed),
        "human_review_coverage": len(reviewed) / len(completed) if completed else None,
        "learning_quality_pass_rate": sum(item["learning_quality_passed"] for item in reviewed) / len(completed) if quality_complete else None,
        "recorded_p50_latency_ms": latencies[math.ceil(len(latencies) * .5) - 1] if latencies and prediction_kind == "recorded" else None,
        "recorded_p95_latency_ms": latencies[math.ceil(len(latencies) * .95) - 1] if latencies and prediction_kind == "recorded" else None,
    }
    signature = hashlib.sha256(json.dumps([asdict(case) for case in cases], sort_keys=True,
                                          ensure_ascii=False).encode("utf-8")).hexdigest()
    groups = {category: {"case_count": sum(item["category"] == category for item in details),
                         "contract_passed_cases": sum(item["category"] == category and item["contract_passed"] for item in details)}
              for category in sorted(CATEGORIES)}
    return {"evaluator_version": EVALUATOR_VERSION, "dataset_signature": signature,
            "evaluation_mode": "offline_replay", "prediction_kind": prediction_kind,
            "summary": summary, "groups": groups, "cases": details,
            "notes": ["Contract pass rate is NOT cloud quality acceptance or factual correctness.",
                      "Source coverage uses accumulated multi-search evidence, NOT ranked Recall@5.",
                      "Budgets are reported counters, NOT measured token usage or cost.",
                      "Scenario labels and final counters cannot prove that the required fault injection actually ran.",
                      "Human review is external, fingerprint-bound, and cannot be replaced by model Reviewer approval."]}
