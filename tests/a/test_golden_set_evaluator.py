from pathlib import Path

from backend.app.evaluation.golden_set import (
    compare_to_baseline,
    evaluate_quality_gates,
    load_golden_set,
    summarise_results,
)


ROOT = Path(__file__).resolve().parents[2]


def test_golden_set_has_more_than_sixty_unique_chinese_cases():
    cases = load_golden_set(ROOT / "evals" / "golden_set_zh.jsonl")

    assert len(cases) >= 60
    assert len({case.case_id for case in cases}) == len(cases)
    assert sum(case.expected_behavior == "answer_with_citations" for case in cases) == 48
    assert sum(case.expected_behavior == "abstain" for case in cases) == 8
    assert sum(case.expected_behavior == "review_required" for case in cases) == 10


def test_evaluator_scores_retrieval_citation_and_safety_contracts():
    cases = load_golden_set(ROOT / "evals" / "golden_set_zh.jsonl")[:3]
    predictions = {
        "qa-001": {
            "evidence": [{"source": "artificial_intelligence/人工智能导论.md", "chunk_id": "c1"}],
            "citations": [{"source": "artificial_intelligence/人工智能导论.md", "chunk_id": "c1"}],
            "answer": "人工智能是研究智能系统的学科。",
            "latency_ms": 120,
        },
        "qa-002": {
            "evidence": [{"source": "artificial_intelligence/人工智能导论.md", "chunk_id": "c2"}],
            "citations": [{"source": "artificial_intelligence/人工智能导论.md", "chunk_id": "c2"}],
            "answer": "三者的能力范围不同。",
            "latency_ms": 180,
        },
        "qa-003": {
            "evidence": [{"source": "artificial_intelligence/chapters/00_ai_overview.md", "chunk_id": "c3"}],
            "citations": [{"source": "artificial_intelligence/chapters/00_ai_overview.md", "chunk_id": "c3"}],
            "answer": "图灵测试评估机器的对话表现。",
            "latency_ms": 210,
        },
    }

    report = summarise_results(cases, predictions)

    assert report["summary"]["hit_at_5"] == 1.0
    assert report["summary"]["citation_presence"] == 1.0
    assert evaluate_quality_gates(report, {})["hit_at_5"]


def test_legacy_unversioned_baselines_are_not_comparable():
    current = {
        "summary": {
            "recall_at_5": 0.86,
            "citation_completeness": 1.0,
            "security_and_review_pass_rate": 1.0,
        }
    }
    baseline = {
        "summary": {
            "recall_at_5": 0.9,
            "citation_completeness": 1.0,
            "security_and_review_pass_rate": 1.0,
        }
    }

    comparison = compare_to_baseline(current, baseline, tolerated_drop=0.03)

    assert comparison["passed"] is False
    assert comparison["comparable"] is False
