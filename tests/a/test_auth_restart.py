"""Cross-process real auth API, SQLite plus explicitly opted-in disposable PG."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_auth_restart_course_revoke_and_logout(tmp_path, backend):
    url = os.getenv("TEST_V2_POSTGRES_URL") if backend == "postgres" else f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    if not url:
        pytest.skip("Explicit disposable PostgreSQL required")
    def probe(payload):
        result = subprocess.run([sys.executable, str(ROOT / "tests/helpers/auth_restart_worker.py")],
            input=json.dumps(payload), cwd=ROOT, env={**os.environ, "TEST_AUTH_DATABASE_URL": url,
            "PYTHONIOENCODING": "utf-8", "PYTHONPATH": os.pathsep.join([str(ROOT), os.environ.get("PYTHONPATH", "")])},
            capture_output=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    identity = {"account": "auth-" + uuid.uuid4().hex[:20], "run_id": "auth-" + uuid.uuid4().hex}
    try:
        first = probe({**identity, "phase": "issue"})
        second = probe({**identity, "phase": "verify", "token": first["token"]})
        assert first["pid"] != second["pid"]
        assert second["session_survived_restart"] and second["revocation_verified"]
    finally:
        assert probe({**identity, "phase": "cleanup"})["cleaned"]
