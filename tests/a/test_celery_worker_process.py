"""Actual solo Worker process contract with a local broker and stubbed ingestion."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest

# kombu 的 filesystem:// broker 在 Windows 上需要 pywin32 的 pywintypes；
# 共享测试环境不安装 pywin32，因此这里条件跳过，Linux CI 与 nightly 继续覆盖本契约。
needs_pywintypes = sys.platform == "win32" and importlib.util.find_spec("pywintypes") is None
pytestmark = pytest.mark.skipif(
    needs_pywintypes,
    reason="kombu filesystem broker requires pywin32 on Windows; covered by Linux CI and nightly",
)


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
