from collections import Counter
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from backend.app.evaluation.learning_package import (
    HUMAN_CRITERIA, PackageCase, fingerprint, grade_case, load_cases, load_rows,
    review_template, summarise,
)
from scripts.evaluate_learning_package import main


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def case():
    return PackageCase("sample", "normal", "dev", "解释 RAG 并出三道练习", "artificial_intelligence",
                       "completed", ("chapter.md",), "standard", ("内容必须有证据支持",))


@pytest.fixture
def prediction():
    citation = {"chunk_id": "c1", "source": "chapter.md", "label": "chapter.md", "score": 0}
    artifact = {"explanation": "课程讲解与解析", "source_ids": ["c1"], "citations": [citation]}
    return {"id": "sample", "scenario": "standard", "events": ["run.started", "run.completed"], "result": {
        "status": "completed", "answer": "学习讲解、练习与来源", "latency_ms": 123,
        "evidence": [{**citation, "content": "正确的课程证据"},
                     {"chunk_id": "unused", "source": "unused.md", "content": "未被引用的证据"}],
        "citations": [citation],
        "budget": {"model_calls": 6, "tool_calls": 1, "input_chars": 1000, "output_token_limit": 12288},
        "learning_package": {
            "plan": {"steps": [
                {"id": "tutor", "role": "tutor", "goal": "讲解", "depends_on": []},
                {"id": "practice", "role": "practice", "goal": "练习", "depends_on": ["tutor"]},
            ]},
            "lesson": deepcopy(artifact), "exercises": [
                {**deepcopy(artifact), "question": f"题目 {i}", "answer": "答案"} for i in range(3)
            ], "review": {"approved": True, "issues": []}, "revisions": 0,
        },
    }}


def test_dataset_has_fixed_balanced_splits_and_real_source_paths():
    cases = load_cases(ROOT / "evals/learning_package_cases_v1.jsonl")
    assert len(cases) == 24
    assert Counter((case.category, case.split) for case in cases) == {
        (category, split): 4 for category in ("normal", "evidence_revision", "boundary_failure")
        for split in ("dev", "holdout")
    }
    assert all((ROOT / "knowledge_base" / source).is_file() for case in cases for source in case.expected_sources)
    assert all(case.scenario != "standard" for case in cases if case.expected_outcome == "failed")


def test_valid_contract_does_not_claim_semantic_quality(case, prediction):
    row = grade_case(case, prediction)
    assert row["contract_passed"]
    assert row["human_quality_passed"] is None and row["learning_quality_passed"] is None
    report = summarise([case], {case.id: prediction})
    assert report["evaluation_mode"] == "offline_replay"
    assert report["summary"]["contract_pass_rate"] == 1
    assert report["summary"]["human_review_coverage"] == 0
    assert report["summary"]["learning_quality_pass_rate"] is None
    assert report["summary"]["recorded_p50_latency_ms"] is None


@pytest.mark.parametrize("mutation", ["unused_final", "missing_final", "duplicate_final", "wrong_source",
                                     "missing_item_citation", "unknown_id", "missing_exercise", "blank_answer",
                                     "cycle", "excess_searches", "bool_budget", "wrong_output_budget", "failed_event",
                                     "no_terminal", "multiple_terminals", "rejected_reviewer", "extra_revision"])
def test_bad_contracts_cannot_pass(case, prediction, mutation):
    result = prediction["result"]
    package = result["learning_package"]
    if mutation == "unused_final":
        result["citations"].append(result["evidence"][1])
    elif mutation == "missing_final":
        result["citations"] = []
    elif mutation == "duplicate_final":
        result["citations"] *= 2
    elif mutation == "wrong_source":
        package["lesson"]["citations"][0]["source"] = "forged.md"
    elif mutation == "missing_item_citation":
        package["exercises"][1]["citations"] = []
    elif mutation == "unknown_id":
        package["exercises"][0]["source_ids"] = ["fabricated"]
    elif mutation == "missing_exercise":
        package["exercises"].pop()
    elif mutation == "blank_answer":
        package["exercises"][2]["answer"] = " "
    elif mutation == "cycle":
        package["plan"]["steps"][0]["depends_on"] = ["practice"]
    elif mutation == "excess_searches":
        result["budget"]["tool_calls"] = 4
    elif mutation == "bool_budget":
        result["budget"]["model_calls"] = True
    elif mutation == "wrong_output_budget":
        result["budget"]["output_token_limit"] = 1
    elif mutation == "failed_event":
        prediction["events"] = ["run.failed"]
    elif mutation == "no_terminal":
        prediction["events"] = ["run.started"]
    elif mutation == "multiple_terminals":
        prediction["events"] += ["run.completed"]
    elif mutation == "rejected_reviewer":
        package["review"]["approved"] = False
    else:
        package["revisions"] = 2
    assert not grade_case(case, prediction)["contract_passed"]


def test_same_source_distinct_chunks_are_not_collapsed(case, prediction):
    result = prediction["result"]
    second = {"chunk_id": "c2", "source": "chapter.md"}
    result["evidence"].append(second)
    exercise = result["learning_package"]["exercises"][0]
    exercise.update(source_ids=["c2", "c2"], citations=[second])
    result["citations"].append(second)
    assert grade_case(case, prediction)["contract_passed"]
    result["citations"].pop()
    assert not grade_case(case, prediction)["contract_passed"]


@pytest.mark.parametrize("outcome,event,error,status", [
    ("failed", "run.failed", "learning_package_no_evidence", None),
    ("review_required", "review.required", "", None),
    ("rejected", "run.completed", "", "rejected"),
])
def test_expected_failure_or_review_is_not_package_success(case, outcome, event, error, status):
    case = replace(case, expected_outcome=outcome, expected_error=error, expected_sources=())
    prediction = {"id": case.id, "scenario": "standard", "events": [event], "result": {}}
    if error:
        prediction["result"]["error"] = error
    if status:
        prediction["result"].update(status=status, answer="无法回答或执行该请求", quality={"safety_refusal": True})
    assert grade_case(case, prediction)["contract_passed"]
    assert summarise([case], {case.id: prediction})["summary"]["learning_quality_pass_rate"] is None
    prediction["result"]["approval"] = {"draft_answer": "secret"}
    assert not grade_case(case, prediction)["contract_passed"]


def test_wrong_error_and_draft_delta_fail_expected_failure(case):
    case = replace(case, expected_outcome="failed", expected_error="learning_package_no_evidence")
    prediction = {"scenario": "standard", "events": ["run.failed"], "result": {"error": "run_timeout"}}
    assert not grade_case(case, prediction)["contract_passed"]
    prediction["result"]["error"] = case.expected_error
    prediction["events"].insert(0, "answer.delta")
    assert not grade_case(case, prediction)["contract_passed"]


@pytest.mark.parametrize("field,value", [("learning_package", None), ("evidence", "oops"), ("budget", []),
                                        ("citations", [None]), ("status", None)])
def test_malformed_results_fail_without_crashing(case, prediction, field, value):
    prediction["result"][field] = value
    assert not grade_case(case, prediction)["contract_passed"]


def test_missing_predictions_and_missing_rubric_scores_are_not_perfect(case, prediction):
    report = summarise([case], {})
    assert report["summary"]["contract_pass_rate"] == 0
    blank = review_template([case], {case.id: prediction})[0]
    assert all(blank[key] is None for key in HUMAN_CRITERIA)
    assert not grade_case(case, prediction, blank)["human_review_valid"]


def test_human_review_fingerprint_prevents_reusing_stale_approval(case, prediction):
    review = {"id": case.id, "reviewer": "test-human", "prediction_fingerprint": fingerprint(case, prediction),
              **dict.fromkeys(HUMAN_CRITERIA, True)}
    assert grade_case(case, prediction, review)["learning_quality_passed"]
    review["exercise_answers_correct"] = False
    assert grade_case(case, prediction, review)["learning_quality_passed"] is False
    prediction["result"]["answer"] = "changed"
    assert not grade_case(case, prediction, review)["human_review_valid"]


def test_partial_human_reviews_do_not_create_full_quality_metric(case, prediction):
    second = replace(case, id="other")
    review = {"reviewer": "test-human", "prediction_fingerprint": fingerprint(case, prediction),
              **dict.fromkeys(HUMAN_CRITERIA, True)}
    report = summarise([case, second], {case.id: prediction, second.id: {**prediction, "id": second.id}}, {case.id: review})
    assert report["summary"]["human_review_coverage"] == .5
    assert report["summary"]["learning_quality_pass_rate"] is None


def test_dataset_and_split_changes_change_signature(case, prediction):
    report = summarise([case], {case.id: prediction})
    other = summarise([replace(case, split="holdout")], {case.id: prediction})
    assert report["dataset_signature"] != other["dataset_signature"]


@pytest.mark.parametrize("scenario", ["unused_evidence", "same_source_chunks", "empty_then_evidence",
                                     "repeated_search", "review_once", "review_changes_sources"])
def test_scenario_labels_alone_do_not_satisfy_observable_preconditions(case, prediction, scenario):
    case = replace(case, scenario=scenario)
    prediction["scenario"] = scenario
    if scenario == "unused_evidence":
        prediction["result"]["evidence"].pop()
    assert not grade_case(case, prediction)["checks"]["scenario_observables_valid"]


def test_recorded_latency_is_not_synthetic_performance(case, prediction):
    report = summarise([case], {case.id: prediction}, prediction_kind="recorded")
    assert report["summary"]["recorded_p50_latency_ms"] == 123
    prediction["result"]["latency_ms"] = -1
    assert summarise([case], {case.id: prediction}, prediction_kind="recorded")["summary"]["recorded_p95_latency_ms"] is None


def write_rows(path, rows):
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


def test_duplicate_prediction_ids_are_rejected(tmp_path):
    path = tmp_path / "predictions.jsonl"
    write_rows(path, [{"id": "duplicate"}, {"id": "duplicate"}])
    with pytest.raises(ValueError, match="Duplicate"):
        load_rows(path)


@pytest.mark.parametrize("field,value", [("category", []), ("expected_outcome", "success"),
                                        ("scenario", "unspecified"), ("expected_sources", []),
                                        ("expected_revisions", True), ("require_approval", "true")])
def test_invalid_case_metadata_fails_closed(case, tmp_path, field, value):
    from dataclasses import asdict
    path = tmp_path / "cases.jsonl"
    write_rows(path, [{**asdict(case), field: value}])
    with pytest.raises(ValueError):
        load_cases(path)


def test_cli_replays_offline_and_refuses_to_overwrite(case, prediction, tmp_path, monkeypatch):
    import socket
    from dataclasses import asdict
    monkeypatch.setattr(socket, "create_connection", lambda *_a, **_kw: pytest.fail("network forbidden"))
    cases_path, input_path = tmp_path / "cases.jsonl", tmp_path / "input.jsonl"
    output_path, review_path = tmp_path / "report.json", tmp_path / "review.jsonl"
    write_rows(cases_path, [asdict(case)])
    write_rows(input_path, [prediction])
    args = ["--cases", str(cases_path), "--predictions", str(input_path), "--output", str(output_path),
            "--review-template", str(review_path), "--enforce-contracts"]
    assert main(args) == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["evaluation_mode"] == "offline_replay" and report["prediction_kind"] == "synthetic"
    assert report["summary"]["learning_quality_pass_rate"] is None
    assert load_rows(review_path)[case.id]["facts_supported"] is None
    original = output_path.read_bytes()
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2 and output_path.read_bytes() == original


def test_cli_default_dev_split_and_unreviewed_gate_fail(tmp_path):
    prediction_path = tmp_path / "predictions.jsonl"
    write_rows(prediction_path, [{"id": "lp-normal-001", "scenario": "standard", "events": [], "result": {}}])
    report_path = tmp_path / "report.json"
    assert main(["--predictions", str(prediction_path), "--output", str(report_path), "--enforce-human-review"]) == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["split"] == "dev" and report["summary"]["case_count"] == 12
    assert all(row["split"] == "dev" for row in report["cases"])


def test_cli_validation_has_no_evaluation_results(capsys):
    assert main(["--validate-only", "--split", "all"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"case_count": 24, "split": "all", "evaluation_performed": False}


def test_cli_refuses_unknown_predictions_and_output_input_collision(case, prediction, tmp_path):
    from dataclasses import asdict
    cases_path, input_path = tmp_path / "cases.jsonl", tmp_path / "input.jsonl"
    write_rows(cases_path, [asdict(case)])
    write_rows(input_path, [prediction])
    original = input_path.read_bytes()
    with pytest.raises(SystemExit) as exc:
        main(["--cases", str(cases_path), "--predictions", str(input_path), "--output", str(input_path)])
    assert exc.value.code == 2 and input_path.read_bytes() == original
    write_rows(input_path, [{**prediction, "id": "unknown"}])
    with pytest.raises(SystemExit) as exc:
        main(["--cases", str(cases_path), "--predictions", str(input_path), "--output", str(tmp_path / "new.json")])
    assert exc.value.code == 2 and not (tmp_path / "new.json").exists()
