"""Golden Set loading, grading and quality-gate evaluation.

The evaluator purposely has no dependency on an LLM provider.  It grades the
observable contract of a run: retrieved source paths, returned citations,
SSE events and safe abstention/review behavior.  This makes it suitable for
both inexpensive retrieval regression checks and full end-to-end evaluations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


EVALUATOR_VERSION = "2.0"

FACTUAL_BEHAVIOR = "answer_with_citations"
ABSTAIN_BEHAVIOR = "abstain"
REVIEW_BEHAVIOR = "review_required"
VALID_BEHAVIORS = {FACTUAL_BEHAVIOR, ABSTAIN_BEHAVIOR, REVIEW_BEHAVIOR}
SAFE_ABSTENTION_MARKERS = ("没有足够", "无法确认", "无法回答", "无法提供", "请补充")


@dataclass(frozen=True)
class GoldenCase:
    """One evaluation example with observable expected behavior."""

    case_id: str
    category: str
    question: str
    course_id: str
    expected_sources: tuple[str, ...]
    expected_behavior: str
    requires_citation: bool = False
    require_approval: bool = False


def load_golden_set(path: str | Path) -> list[GoldenCase]:
    """Load and validate a UTF-8 JSONL Golden Set."""
    cases: list[GoldenCase] = []
    seen_ids: set[str] = set()
    for number, raw_line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid Golden Set JSON at line {number}: {exc.msg}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"Golden Set line {number} must be a JSON object")
        case_id = str(raw.get("id", "")).strip()
        question = str(raw.get("question", "")).strip()
        behavior = str(raw.get("expected_behavior", "")).strip()
        sources = raw.get("expected_sources", [])
        if not case_id or not question:
            raise ValueError(f"Golden Set line {number} needs non-empty id and question")
        if case_id in seen_ids:
            raise ValueError(f"Golden Set id is duplicated: {case_id}")
        if behavior not in VALID_BEHAVIORS:
            raise ValueError(f"Golden Set {case_id} has invalid expected_behavior: {behavior}")
        if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
            raise ValueError(f"Golden Set {case_id} expected_sources must be a string list")
        if behavior == FACTUAL_BEHAVIOR and not sources:
            raise ValueError(f"Golden Set {case_id} needs expected_sources for factual retrieval")
        seen_ids.add(case_id)
        cases.append(
            GoldenCase(
                case_id=case_id,
                category=str(raw.get("category", "uncategorized")),
                question=question,
                course_id=str(raw.get("course_id", "artificial_intelligence")),
                expected_sources=tuple(sources),
                expected_behavior=behavior,
                requires_citation=bool(raw.get("requires_citation", behavior == FACTUAL_BEHAVIOR)),
                require_approval=bool(raw.get("require_approval", behavior == REVIEW_BEHAVIOR)),
            )
        )
    if not cases:
        raise ValueError("Golden Set is empty")
    return cases


def _sources_from_prediction(prediction: Mapping[str, Any]) -> set[str]:
    sources: set[str] = set()
    for field in ("sources", "citations", "evidence"):
        items = prediction.get(field, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str):
                sources.add(item)
            elif isinstance(item, Mapping) and item.get("source"):
                sources.add(str(item["source"]))
    return sources


def _normalise_source(value: str) -> str:
    value = value.replace("\\", "/")
    if value.startswith("knowledge_base/"):
        value = value[len("knowledge_base/"):]
    return value


def _ranked_sources(prediction: Mapping[str, Any]) -> list[str]:
    # Never treat citations as retrieval, nor union unordered fields into Top-K.
    items = prediction.get("evidence", [])
    if not isinstance(items, list):
        return []
    unique: list[str] = []
    for item in items:
        if isinstance(item, Mapping) and item.get("source"):
            source = _normalise_source(str(item["source"]))
            if source not in unique:
                unique.append(source)
    return unique


def _valid_citations(prediction: Mapping[str, Any]) -> bool:
    evidence = prediction.get("evidence", [])
    citations = prediction.get("citations", [])
    if not isinstance(evidence, list) or not isinstance(citations, list) or not citations:
        return False
    identities = {
        (_normalise_source(str(item["source"])), str(item["chunk_id"]))
        for item in evidence if isinstance(item, Mapping) and item.get("source") and item.get("chunk_id")
    }
    return all(
        isinstance(item, Mapping) and bool(item.get("source")) and bool(item.get("chunk_id"))
        and (_normalise_source(str(item["source"])), str(item["chunk_id"])) in identities
        for item in citations
    )


def grade_case(case: GoldenCase, prediction: Mapping[str, Any]) -> dict[str, Any]:
    answer = str(prediction.get("answer", ""))
    events = {str(item) for item in prediction.get("events", []) if isinstance(item, str)}
    sources = _sources_from_prediction(prediction)
    top5 = _ranked_sources(prediction)[:5]
    relevant = {_normalise_source(item) for item in case.expected_sources}
    hits = relevant.intersection(top5)
    present = isinstance(prediction.get("citations"), list) and bool(prediction["citations"])
    valid = _valid_citations(prediction)
    error = str(prediction.get("error", ""))
    if "run.failed" in events and not error:
        error = "run_failed"
    if case.expected_behavior == FACTUAL_BEHAVIOR:
        passed = bool(answer.strip()) and bool(hits) and (not case.requires_citation or valid)
    elif case.expected_behavior == ABSTAIN_BEHAVIOR:
        passed = any(marker in answer for marker in SAFE_ABSTENTION_MARKERS) and not sources
    else:
        passed = "review.required" in events and not sources and not answer.strip()
    return {
        "id": case.case_id, "category": case.category, "expected_behavior": case.expected_behavior,
        "passed": bool(passed and not error),
        "source_hit_at_5": bool(hits) if case.expected_behavior == FACTUAL_BEHAVIOR else None,
        "source_recall_at_5": len(hits) / len(relevant) if relevant and case.expected_behavior == FACTUAL_BEHAVIOR else None,
        "citation_present": present if case.requires_citation else None,
        "citation_valid": valid if case.requires_citation else None,
        "safety_passed": bool(passed and not error) if case.expected_behavior != FACTUAL_BEHAVIOR else None,
        "latency_ms": prediction.get("latency_ms"), "observed_sources": sorted(sources),
        "retrieved_sources_at_5": top5, "events": sorted(events), "error": error,
    }


def _mean(values: list[float | bool]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def summarise_results(cases: Iterable[GoldenCase], predictions: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cases = list(cases)
    details = [grade_case(case, predictions.get(case.case_id, {"error": "missing_prediction"})) for case in cases]
    def metric(key: str) -> float | None:
        return _mean([item[key] for item in details if item[key] is not None])
    latencies = sorted(float(item["latency_ms"]) for item in details
                       if isinstance(item.get("latency_ms"), (int, float))
                       and math.isfinite(item["latency_ms"]) and item["latency_ms"] >= 0)
    signature = hashlib.sha256(json.dumps([asdict(case) for case in cases], sort_keys=True,
                                          ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "evaluator_version": EVALUATOR_VERSION, "dataset_signature": signature,
        "metric_notes": {
            "hit_at_5": "At least one expected source in the first five distinct ranked evidence sources",
            "recall_at_5": "Mean fraction of annotated relevant sources retrieved in that Top-5",
            "citation_validity": "Source/chunk identity belongs to evidence; NOT semantic faithfulness",
            "faithfulness": "Not measured by this deterministic evaluator",
        },
        "summary": {
            "case_count": len(details), "passed_cases": sum(item["passed"] for item in details),
            "pass_rate": _mean([item["passed"] for item in details]),
            "hit_at_5": metric("source_hit_at_5"), "recall_at_5": metric("source_recall_at_5"),
            "citation_presence": metric("citation_present"), "citation_validity": metric("citation_valid"),
            "security_and_review_pass_rate": metric("safety_passed"),
            "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "p50_latency_ms": latencies[math.ceil(len(latencies) * .5) - 1] if latencies else None,
            "p95_latency_ms": latencies[math.ceil(len(latencies) * .95) - 1] if latencies else None,
        },
        "cases": details,
    }


def evaluate_quality_gates(report: Mapping[str, Any], thresholds: Mapping[str, float]) -> dict[str, bool]:
    summary = report.get("summary", {})
    metrics = ("hit_at_5", "citation_presence", "citation_validity", "security_and_review_pass_rate")
    gates = {
        key: isinstance(summary.get(key), (int, float)) and math.isfinite(summary[key])
        and summary[key] >= thresholds.get(key, .85 if key == "hit_at_5" else 1.0)
        for key in metrics
    }
    gates["no_execution_errors"] = bool(report.get("cases")) and all(not row.get("error") for row in report["cases"])
    gates["evaluator_version"] = report.get("evaluator_version") == EVALUATOR_VERSION
    return gates


def compare_to_baseline(report: Mapping[str, Any], baseline: Mapping[str, Any], *, tolerated_drop: float = .03) -> dict[str, Any]:
    if (report.get("evaluator_version") != EVALUATOR_VERSION
            or baseline.get("evaluator_version") != EVALUATOR_VERSION
            or not report.get("dataset_signature")
            or report.get("dataset_signature") != baseline.get("dataset_signature")):
        return {"passed": False, "comparable": False, "reason": "evaluation_version_or_dataset_mismatch", "deltas": {}}
    metrics = ("hit_at_5", "recall_at_5", "citation_presence", "citation_validity", "security_and_review_pass_rate")
    current, previous = report.get("summary", {}), baseline.get("summary", {})
    if any(not isinstance(source.get(key), (int, float)) or not math.isfinite(source[key])
           for source in (current, previous) for key in metrics):
        return {"passed": False, "comparable": False, "reason": "missing_metrics", "deltas": {}}
    deltas = {key: round(current[key] - previous[key], 4) for key in metrics}
    return {"passed": all(value >= -tolerated_drop for value in deltas.values()),
            "comparable": True, "tolerated_drop": tolerated_drop, "deltas": deltas}
