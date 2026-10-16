"""Explicit disposable DB required. Models/identity are mocked; SQL and API are real."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def probe(phase, scenario="", run_id=""):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": os.pathsep.join([str(ROOT), os.environ.get("PYTHONPATH", "")])}
    result = subprocess.run([sys.executable, str(ROOT / "tests/helpers/postgres_api_recovery_worker.py"),
        phase, scenario, run_id], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == (74 if phase == "crash" else 0), result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def migrated():
    if not os.getenv("TEST_V2_POSTGRES_URL"):
        pytest.skip("Requires an explicitly designated disposable PostgreSQL database")
    assert probe("migrate")["migration_roundtrip"]


@pytest.mark.parametrize("scenario", ["pending", "completed", "approve", "edit", "reject"])
def test_postgres_api_recovers_after_checkpoint_commit_and_process_exit(migrated, scenario):
    crashed = probe("crash", scenario)
    try:
        recovered = probe("recover", scenario, crashed["run_id"])
        assert recovered["pid"] != crashed["pid"]
        assert recovered["stale_writer_blocked"]
    finally:
        assert probe("cleanup", scenario, crashed["run_id"])["deleted"]
