import pytest

from backend.app.evaluation.ablation_report import RUBRICS, summarize_ablation


def run(arm="single", **changes):
    row = {"case_id": "a", "arm": arm, "completed": True,
           "config": {"model": "m", "knowledge_snapshot": "sha256:x", "max_output_tokens": 100, "max_cost_cny": 1},
           "evidence_sha256": "evidence-a", "latency_ms": 10, "cost_cny": 0.1, "model_calls": 1, "invalid_tool_calls": 0,
           "reviews": [{"reviewer": name, **dict.fromkeys(RUBRICS, True)} for name in ("a", "b")]}
    row.update(changes)
    return row


def test_missing_arms_and_reviews_are_unknown():
    report = summarize_ablation([{"id": "a"}], [run(reviews=[])])
    assert report["arms"]["single"]["quality_pass_rate"] is None
    assert report["arms"]["full"]["task_success_rate"] is None


def test_review_disagreement_and_unknown_cost_are_not_treated_as_zero():
    row = run(cost_cny=None)
    row["reviews"][1]["facts_supported"] = False
    report = summarize_ablation([{"id": "a"}], [row])
    assert report["arms"]["single"]["quality_pass_rate"] is None
    assert report["arms"]["single"]["mean_cost_cny"] is None


def test_failed_task_counts_as_failure():
    report = summarize_ablation([{"id": "a"}], [run(completed=False, reviews=[])])
    assert report["arms"]["single"]["task_success_rate"] == 0
    assert report["arms"]["single"]["quality_pass_rate"] == 0


def test_mismatched_configuration_is_rejected():
    other = run("full")
    other["config"]["model"] = "other"
    with pytest.raises(ValueError):
        summarize_ablation([{"id": "a"}], [run(), other])


def test_mismatched_evidence_is_rejected():
    with pytest.raises(ValueError):
        summarize_ablation([{"id": "a"}], [run(), run("full", evidence_sha256="other")])


def test_unknown_profile_does_not_erase_other_reviewed_metrics():
    row = run()
    for review in row["reviews"]:
        review["profile_fit"] = None
    group = summarize_ablation([{"id": "a"}], [row])["arms"]["single"]
    assert group["profile_fit_rate"] is None
    assert group["facts_supported_rate"] == 1
    assert group["quality_pass_rate"] is None


def test_reviewer_revision_rate_counts_rejected_runs():
    row = run("full", result={"reviewer_initially_rejected": True, "reviewer_revision_succeeded": False})
    group = summarize_ablation([{"id": "a"}], [row])["arms"]["full"]
    assert group["reviewer_rejected_count"] == 1
    assert group["reviewer_revision_success_rate"] == 0


def test_adjudication_resolves_disagreement_without_hiding_it_or_filling_unknown():
    row = run()
    row["reviews"][1]["facts_supported"] = False
    row["reviews"][0]["profile_fit"] = row["reviews"][1]["profile_fit"] = None
    row["adjudication"] = {"reviewer": "c", **dict.fromkeys(RUBRICS, True)}
    row["adjudication"]["facts_supported"] = False
    group = summarize_ablation([{"id": "a"}], [row])["arms"]["single"]
    assert group["review_disagreement_count"] == 1
    assert group["facts_supported_rate"] == 0
    assert group["profile_fit_rate"] is None
    assert group["quality_pass_rate"] is None


def test_adjudication_must_be_independent_and_have_a_disagreement():
    row = run(adjudication={"reviewer": "c", **dict.fromkeys(RUBRICS, True)})
    with pytest.raises(ValueError):
        summarize_ablation([{"id": "a"}], [row])
    row["reviews"][1]["facts_supported"] = False
    row["adjudication"]["reviewer"] = "a"
    with pytest.raises(ValueError):
        summarize_ablation([{"id": "a"}], [row])
