"""Opt-in PostgreSQL/application-process restart tests; no cloud calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "tests/helpers/checkpoint_restart_worker.py"


def worker(phase, thread_id, scenario, decision="approve"):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT), os.environ.get("PYTHONPATH", "")])}
    result = subprocess.run(
        [sys.executable, str(WORKER), phase, thread_id, scenario, decision],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45,
    )
    expected = 73 if phase == "suspend" else 0
    assert result.returncode == expected, f"{phase} worker failed (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


@pytest.fixture
def thread_id():
    if not os.getenv("TEST_V2_POSTGRES_URL"):
        pytest.skip("Requires an explicitly designated disposable PostgreSQL database")
    identifier = "checkpoint-restart-test-" + uuid.uuid4().hex
    yield identifier
    # Delete only this test's thread; no schema/database or other runs are removed.
    assert worker("cleanup", identifier, "answer")["deleted"]


def recover(thread_id, scenario, decision):
    paused = worker("suspend", thread_id, scenario)
    resumed = worker("resume", thread_id, scenario, decision)
    assert paused["pid"] != resumed["pid"]
    assert paused["next"] == ["approval"] and resumed["next"] == []
    assert paused["checkpoint_id"] == resumed["restored_checkpoint_id"]
    return paused, resumed["state"]


def test_postgres_answer_review_survives_process_exit(thread_id):
    paused, state = recover(thread_id, "answer", "approve")
    assert state["review_status"] == "approved"
    assert "test answer" in state["answer"]
    assert state["citations"] == paused["review"]["citations"]


@pytest.mark.parametrize("scenario", ["unused_evidence", "review_changes_sources"])
@pytest.mark.parametrize("decision", ["approve", "edit", "reject"])
def test_postgres_package_review_survives_process_exit(thread_id, scenario, decision):
    paused, state = recover(thread_id, scenario, decision)
    initial = paused["state"]
    assert "unused" in {item["chunk_id"] for item in initial["evidence"]}
    assert "unused" not in {item["chunk_id"] for item in paused["review"]["citations"]}
    assert state["budget"] == initial["budget"]
    assert state["revisions"] == initial["revisions"] == int(scenario == "review_changes_sources")
    if decision == "approve":
        assert state["review_status"] == "approved"
        package = state["learning_package"]
        assert package == initial["learning_package"]
        artifacts = [package["lesson"], *package["exercises"]]
        used_ids = {source_id for artifact in artifacts for source_id in artifact["source_ids"]}
        assert {item["chunk_id"] for item in state["citations"]} == used_ids
        assert state["citations"] == paused["review"]["citations"]
        for artifact in artifacts:
            assert {item["chunk_id"] for item in artifact["citations"]} == set(artifact["source_ids"])
        assert state["quality"]["reviewer_passed"] is True
    else:
        assert state["learning_package"] == {}
        assert state["citations"] == []
        if decision == "edit":
            assert state["answer"] == "教师修改后的测试答案"
            assert state["review_status"] == "approved"
            assert state["quality"]["human_edited"] is True
            assert state["quality"]["reviewer_passed"] is False
        else:
            assert state["review_status"] == "rejected"
            assert state["quality"]["review_rejected"] is True
            assert state["evidence"] == []
            assert state["answer"] != initial["answer"]
