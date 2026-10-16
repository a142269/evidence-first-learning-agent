"""Requires an explicitly designated disposable PostgreSQL DB; no cloud calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[2]


def phase(name, run_id=""):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": os.pathsep.join([str(ROOT), os.environ.get("PYTHONPATH", "")])}
    result = subprocess.run([sys.executable, str(ROOT / "tests/helpers/unfinished_pg_worker.py"),
                             name, run_id], cwd=ROOT, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=60)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_real_postgres_resumes_pending_node_in_new_process():
    if not os.getenv("TEST_V2_POSTGRES_URL"):
        pytest.skip("Requires disposable PostgreSQL URL")
    assert phase("migrate")["migrated"]
    run_id = f"unfinished-{uuid.uuid4().hex}"
    try:
        assert phase("fail", run_id)["failed"]
        assert phase("recover", run_id)["recovered"]
    finally:
        assert phase("cleanup", run_id)["deleted"]
