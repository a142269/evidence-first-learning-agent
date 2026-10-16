"""Actual solo Worker process contract with a local broker and stubbed ingestion."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_duplicate_delivery_and_expired_lease_recovery(tmp_path):
    root = Path(__file__).resolve().parents[2]
    probe = root / "tests" / "helpers" / "celery_ingestion_worker_probe.py"
    run_dir = tmp_path / "celery-probe"
    env = {**os.environ, "CELERY_PROBE_ROOT": str(run_dir)}
    result = subprocess.run([sys.executable, str(probe)], cwd=root, env=env,
                            capture_output=True, text=True, timeout=110, check=False)
    logs = "\n".join(path.read_text(encoding="utf-8", errors="replace")[-2000:]
                     for path in sorted(run_dir.glob("*.log")))
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}\n{logs}"
    assert "duplicate_delivery: completed once" in result.stdout
    assert "process_crash: expired lease reclaimed" in result.stdout
