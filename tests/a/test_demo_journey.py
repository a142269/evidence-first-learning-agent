"""Tests for the T1.6 evaluator-facing demo journey CLI."""
# ruff: noqa: RUF001
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from scripts import demo_journey


_DEMO_USERS = ("demo-student-1", "demo-student-2", "demo-student-3")


def _run(
    user_id: str,
    tmp_path: Path,
    extra_args: list[str] | None = None,
) -> int:
    args = [
        user_id,
        "--skip-stream",
        "--skip-report",
        "--report-dir",
        str(tmp_path),
    ]
    if extra_args:
        args.extend(extra_args)
    return demo_journey.main(args)


def test_demo_journey_runs_to_completion_for_demo_student_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    start = time.time()
    exit_code = _run("demo-student-1", tmp_path)
    duration = time.time() - start

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Demo Journey: demo-student-1" in captured.out
    assert "1. 登录与学情画像获取" in captured.out
    assert "4. 错题 → 变式题" in captured.out
    assert "Demo 完成" in captured.out
    assert duration < 30.0, f"demo journey took {duration:.2f}s (>30s budget)"


def test_demo_journey_handles_three_demo_students(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for user_id in _DEMO_USERS:
        capsys.readouterr()  # drain previous output
        exit_code = _run(user_id, tmp_path)
        assert exit_code == 0, f"demo_journey failed for {user_id}"
        captured = capsys.readouterr()
        assert f"Demo Journey: {user_id}" in captured.out


def test_demo_journey_default_enables_offline_mode(
    tmp_path: Path,
) -> None:
    """Running without --no-offline must set A3_OFFLINE_DEMO=1 in the process env."""
    os.environ.pop("A3_OFFLINE_DEMO", None)
    try:
        exit_code = _run("demo-student-2", tmp_path)
        assert exit_code == 0
        assert os.environ.get("A3_OFFLINE_DEMO") == "1"
    finally:
        os.environ.pop("A3_OFFLINE_DEMO", None)


def test_demo_journey_skip_flags_print_skip_banners(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = _run("demo-student-1", tmp_path)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "2. 多 Agent 辩论 SSE 流（已跳过）" in captured.out
    assert "5. 学习诊断报告（已跳过）" in captured.out


def test_demo_journey_variant_step_uses_real_demo_sample(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Step 4 must pick a sample from /system/variant/demo-samples and succeed."""
    exit_code = _run("demo-student-1", tmp_path)
    assert exit_code == 0
    captured = capsys.readouterr()
    # On success the step prints OK + error type + bloom label.
    assert "OK 错因" in captured.out
    assert "推荐 Bloom" in captured.out
