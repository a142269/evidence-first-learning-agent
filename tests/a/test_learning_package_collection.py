import asyncio
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.app.evaluation.learning_package import grade_case, load_cases, summarise
from backend.app.evaluation.package_collection import collect_cases, offline_api, parse_sse
from scripts.collect_learning_package import main

ROOT = Path(__file__).resolve().parents[2]
CASES = load_cases(ROOT / "evals/learning_package_cases_v1.jsonl")


@pytest.fixture(scope="module")
def collected(tmp_path_factory):
    path = tmp_path_factory.mktemp("collection") / "runs.sqlite3"
    return asyncio.run(collect_cases(CASES, path))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_all_cases_execute_real_workflow_contracts(case, collected):
    prediction = collected[case.id]
    detail = grade_case(case, prediction)
    assert detail["contract_passed"], detail
    assert prediction["collection"]["mode"] == "synthetic_asgi"
    assert all(value is True for value in prediction["collection"]["checks"].values())
    assert prediction["node_audit"]
    assert prediction["events"] == [frame["name"] for frame in prediction["sse_frames"]]
    assert prediction["result"] == prediction["sse_frames"][-1]["data"]
    assert detail["learning_quality_passed"] is None


def test_injected_empty_search_and_repeated_search_use_actual_calls(collected):
    empty = collected["lp-evidence-003"]
    searches = [item for item in empty["injection_trace"] if item["kind"] == "retrieval"]
    assert searches[0]["chunk_ids"] == [] and searches[1]["chunk_ids"] == ["c1"]
    assert searches[0]["query"] != searches[1]["query"]
    repeated = collected["lp-evidence-008"]
    assert sum(item["kind"] == "retrieval" for item in repeated["injection_trace"]) == 1
    assert repeated["result"]["tool_stop_reason"] == "repeated_search"


def test_revision_trace_proves_changed_source_and_downstream_dependency(collected):
    row = collected["lp-evidence-007"]
    models = [item for item in row["injection_trace"] if item["kind"] == "model"]
    lessons = [item["output"] for item in models if isinstance(item["output"], dict) and "explanation" in item["output"]]
    practices = [item for item in models if item["role"] == "Practice"]
    assert lessons[0]["source_ids"] == ["unused"] and lessons[1]["source_ids"] == ["c1"]
    assert practices[1]["dependencies"] == {"tutor": lessons[1]}
    assert practices[1]["review_feedback"]
    assert [item["chunk_id"] for item in row["result"]["citations"]] == ["c1"]


def test_safe_declines_call_no_providers_and_review_stream_has_no_draft(collected):
    for key in ("lp-boundary-003", "lp-boundary-007"):
        assert collected[key]["injection_trace"] == []
        assert collected[key]["persisted_status"] == "rejected"
    pending = collected["lp-boundary-004"]
    assert pending["events"][-1] == "review.required"
    assert pending["persisted_status"] == "awaiting_approval"
    assert "answer.delta" not in pending["events"]
    assert "draft_answer" not in json.dumps(pending["sse_frames"])
    assert "evidence" not in pending["result"]


def test_model_budget_failure_stops_before_extra_call(collected):
    row = collected["lp-boundary-008"]
    assert len([item for item in row["injection_trace"] if item["kind"] == "model"]) == 2
    assert row["result"]["error"] == "learning_package_budget_exceeded"
    assert row["persisted_status"] == "failed"


def test_synthetic_collection_cannot_be_relabelled_as_cloud_recordings(collected):
    with pytest.raises(ValueError, match="cannot be relabelled"):
        summarise(CASES, collected, prediction_kind="recorded")
    report = summarise(CASES, collected)
    assert report["summary"]["case_count"] == 24
    assert report["summary"]["completed_case_count"] == 16
    assert report["summary"]["learning_quality_pass_rate"] is None
    assert report["summary"]["recorded_p50_latency_ms"] is None


def test_failed_injection_or_persistence_checks_fail_evaluation(collected):
    case = CASES[0]
    row = deepcopy(collected[case.id])
    row["collection"]["checks"]["persisted_result_matches"] = False
    assert not grade_case(case, row)["contract_passed"]
    row["collection"]["checks"] = {}
    assert not grade_case(case, row)["contract_passed"]


def test_offline_environment_ignores_credentials_and_restores_patches(tmp_path, monkeypatch):
    from backend.app.core import config
    from backend.app.api.v2 import learning_runs
    import httpx
    import requests

    original_runtime = learning_runs._runtime
    original_config = config._config
    monkeypatch.setenv("OPENAI_API_KEY", "test-sentinel-not-a-real-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test-only.invalid/forbidden")
    monkeypatch.setattr(config, "load_dotenv", lambda *_a, **_kw: pytest.fail("dotenv must not be read"))
    with offline_api(tmp_path / "isolated.sqlite3"):
        assert config.get_config().llm.openai_api_key == ""
        with pytest.raises(RuntimeError, match="offline_network_disabled"):
            httpx.get("http://should-never-connect.invalid")
        with pytest.raises(RuntimeError, match="offline_network_disabled"):
            requests.get("http://should-never-connect.invalid")
    assert learning_runs._runtime is original_runtime and config._config is original_config
    import os
    assert os.environ["DATABASE_URL"] == "postgresql://test-only.invalid/forbidden"


def test_sse_frames_preserve_crlf_and_multiline_data():
    raw = 'event: run.completed\r\ndata: {"status":\r\ndata: "completed"}\r\n\r\n'
    assert parse_sse(raw) == [{"name": "run.completed", "data": {"status": "completed"}}]
    with pytest.raises(ValueError):
        parse_sse('event: run.completed\ndata: []\n\n')


def test_collector_flushes_each_actual_prediction_before_next_case(tmp_path):
    received = []
    result = asyncio.run(collect_cases(CASES[:2], tmp_path / "runs.sqlite3", received.append))
    assert [row["id"] for row in received] == [case.id for case in CASES[:2]]
    assert all(row is result[row["id"]] for row in received)
    assert len({row["result"]["run_id"] for row in received}) == 2


def test_cli_collects_and_refuses_overwrite(tmp_path, capsys):
    path = tmp_path / "new-output"
    args = ["--case-id", "lp-boundary-003", "--output-dir", str(path)]
    assert main(args) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["collection_mode"] == "synthetic_asgi"
    assert (path / "runs.sqlite3").exists()
    before = (path / "predictions.jsonl").read_bytes()
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2 and (path / "predictions.jsonl").read_bytes() == before


def test_cli_invalid_case_selection_creates_no_output(tmp_path):
    path = tmp_path / "not-created"
    # A held-out case must not silently run in the default development split.
    with pytest.raises(SystemExit) as exc:
        main(["--case-id", "lp-normal-005", "--output-dir", str(path)])
    assert exc.value.code == 2 and not path.exists()
