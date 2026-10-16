from dataclasses import replace
from pathlib import Path

from backend.app.evaluation.golden_set import (
    EVALUATOR_VERSION, GoldenCase, compare_to_baseline, evaluate_quality_gates,
    grade_case, load_golden_set, summarise_results,
)

ROOT = Path(__file__).resolve().parents[2]


def factual(sources=("a.md",)):
    return GoldenCase("q", "qa", "question", "ai", sources, "answer_with_citations", True)


def prediction(sources=("a.md",)):
    evidence = [{"source": source, "chunk_id": f"c{i}"} for i, source in enumerate(sources)]
    return {"answer": "answer", "evidence": evidence, "citations": evidence[:1]}


def test_historical_cases_retained_and_unsupported_writes_are_not_reviewable():
    original = load_golden_set(ROOT / "evals/golden_set_zh.jsonl")
    revised = load_golden_set(ROOT / "evals/golden_set_zh_v2.jsonl")
    assert len(original) == 66 and len(revised) == 76
    by_id = {case.case_id: case for case in revised}
    assert all(by_id[case.case_id].question == case.question for case in original)
    assert all(by_id[f"review-{i:03}"].expected_behavior == "abstain" for i in range(1, 11))
    assert sum(case.expected_behavior == "review_required" for case in revised) == 10


def test_rank_six_cannot_be_promoted_by_citations_or_unordered_sources():
    result = prediction(("b.md", "c.md", "d.md", "e.md", "f.md", "a.md"))
    result["citations"] = result["evidence"][-1:]
    result["sources"] = ["a.md"]
    detail = grade_case(factual(), result)
    assert detail["source_hit_at_5"] is False
    assert detail["source_recall_at_5"] == 0


def test_citations_alone_are_not_retrieval_evidence():
    detail = grade_case(factual(), {"answer": "ok", "citations": [{"source": "a.md", "chunk_id": "c1"}]})
    assert not detail["source_hit_at_5"]
    assert not detail["citation_valid"]
    assert not detail["passed"]


def test_hit_and_recall_are_distinct_with_multiple_relevant_sources():
    detail = grade_case(factual(("a.md", "b.md")), prediction())
    assert detail["source_hit_at_5"]
    assert detail["source_recall_at_5"] == .5


def test_citation_must_match_both_source_and_chunk():
    data = prediction()
    data["citations"] = [{"source": "a.md", "chunk_id": "invented"}]
    detail = grade_case(factual(), data)
    assert detail["citation_present"]
    assert not detail["citation_valid"]
    assert not detail["passed"]


def test_execution_error_cannot_pass_with_good_sources():
    data = {**prediction(), "error": "run_failed"}
    assert not grade_case(factual(), data)["passed"]


def test_review_event_with_leaked_draft_cannot_pass():
    case = replace(factual(), expected_behavior="review_required", requires_citation=False)
    assert not grade_case(case, {"events": ["review.required"], "answer": "private"})["passed"]
    assert grade_case(case, {"events": ["review.required"]})["passed"]


def test_missing_predictions_fail_and_missing_categories_are_not_perfect():
    report = summarise_results([factual()], {})
    assert report["summary"]["passed_cases"] == 0
    assert report["summary"]["security_and_review_pass_rate"] is None
    assert not all(evaluate_quality_gates(report, {}).values())


def full_report():
    cases = [factual(), GoldenCase("s", "safe", "bad", "ai", (), "abstain")]
    return summarise_results(cases, {"q": prediction(), "s": {"answer": "无法回答", "latency_ms": 100}})


def test_versioned_report_and_gates():
    report = full_report()
    assert report["evaluator_version"] == EVALUATOR_VERSION
    assert len(report["dataset_signature"]) == 64
    assert all(evaluate_quality_gates(report, {}).values())
    assert report["summary"]["citation_validity"] == 1
    assert "citation_completeness" not in report["summary"]


def test_baseline_requires_matching_evaluator_and_dataset():
    report = full_report()
    assert compare_to_baseline(report, report)["passed"]
    old = {"summary": report["summary"]}
    assert not compare_to_baseline(report, old)["comparable"]
    different = {**report, "dataset_signature": "other"}
    assert not compare_to_baseline(report, different)["comparable"]


def test_baseline_limits_regression_to_three_percentage_points():
    previous = full_report()
    current = {**previous, "summary": {**previous["summary"], "hit_at_5": .96}}
    comparison = compare_to_baseline(current, previous)
    assert comparison["comparable"] and not comparison["passed"]
    assert comparison["deltas"]["hit_at_5"] == -.04


def test_source_matching_does_not_accept_a_malicious_suffix():
    assert not grade_case(factual(), prediction(("private/a.md",)))["source_hit_at_5"]
