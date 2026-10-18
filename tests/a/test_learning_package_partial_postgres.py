"""Opt-in PostgreSQL restart test for a partially completed learning package.

Requires an explicitly designated disposable PostgreSQL database
(TEST_V2_POSTGRES_URL). No cloud calls: the workflow is scripted and the resume
process forbids retrieval/model execution.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "tests/helpers/partial_package_checkpoint_worker.py"


def worker(phase, thread_id):
    env = {**os.environ,
           "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": os.pathsep.join([str(ROOT), os.environ.get("PYTHONPATH", "")])}
    result = subprocess.run([sys.executable, str(WORKER), phase, thread_id],
                            cwd=ROOT, env=env, capture_output=True, text=True,
                            encoding="utf-8", timeout=60)
    expected = 73 if phase == "suspend" else 0
    assert result.returncode == expected, f"{phase} worker failed (exit {result.returncode}): {result.stderr}"
    return json.loads(result.stdout)


def test_partial_package_review_survives_postgres_process_exit():
    if not os.getenv("TEST_V2_POSTGRES_URL"):
        pytest.skip("Requires an explicitly designated disposable PostgreSQL database")
    thread_id = "partial-package-restart-test-" + uuid.uuid4().hex
    try:
        paused = worker("suspend", thread_id)
        resumed = worker("resume", thread_id)
    finally:
        assert worker("cleanup", thread_id)["deleted"]

    assert paused["pid"] != resumed["pid"]
    assert paused["next"] == ["approval"] and resumed["next"] == []
    assert paused["checkpoint_id"] == resumed["restored_checkpoint_id"]

    before, after = paused["state"], resumed["state"]
    withheld = {"status": "partially_completed", "delivered_parts": ["lesson", "practice"],
                "withheld_parts": [], "withheld_exercise_numbers": [2],
                "reason": "exercise_not_approved"}
    assert before["partial_completion"] == withheld
    assert after["partial_completion"] == withheld
    assert len(before["learning_package"]["exercises"]) == 2
    assert after["learning_package"] == before["learning_package"]
    assert after["review_status"] == "approved"
    assert after["quality"]["partial_completion"] is True
    # Review-approved partial delivery is still not a full-package pass claim.
    assert after["quality"]["human_edited"] is False
    # The teacher review payload also carried the delivery boundary.
    assert paused["review"]["partial_completion"] == withheld
    assert len(paused["review"]["citations"]) == 1
