"""Tests for the demo-asset health-check CLI."""
# ruff: noqa: RUF001
from __future__ import annotations

import json

import pytest

from scripts import verify_demo_assets as cli


def test_individual_checks_all_pass() -> None:
    results = cli.run_all()
    failed = [r for r in results if not r.ok]
    assert not failed, "failed checks: " + "; ".join(f"{r.name} -> {r.detail}" for r in failed)
    # 6/24: 加 P1.1 + P1.2 后 11→13；再加 Cockpit 聚合端点后 → 14
    assert len(results) >= 14


def test_cockpit_check_registered() -> None:
    from scripts import verify_demo_assets as cli
    names = {n for n, _ in cli.CHECKS}
    assert any("Cockpit" in n for n in names), names


def test_p1_1_pedagogical_safety_check_registered() -> None:
    names = {n for n, _ in cli.CHECKS}
    assert any("PedagogicalSafety" in n for n in names), names


def test_p1_2_claim_ledger_check_registered() -> None:
    names = {n for n, _ in cli.CHECKS}
    assert any("ClaimLedger" in n for n in names), names


def test_render_text_summary_contains_all_checks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    results = cli.run_all()
    summary = cli.render_text(results)
    assert "Demo Assets Health Check" in summary
    for result in results:
        assert result.name in summary


def test_render_json_is_valid_and_complete() -> None:
    results = cli.run_all()
    payload = json.loads(cli.render_json(results))
    assert payload["total"] == len(results)
    assert payload["passed"] == sum(1 for r in results if r.ok)
    assert isinstance(payload["results"], list)


def test_cli_main_zero_exit_when_healthy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main([])
    captured = capsys.readouterr()
    assert exit_code == 0, f"non-zero exit:\n{captured.out}"
    assert "checks passed" in captured.out


def test_cli_main_json_mode_outputs_parseable_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["passed"] == payload["total"]


def test_failing_check_propagates_to_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _bad() -> dict[str, object]:
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(cli, "CHECKS", [("synthetic_failure", _bad)])
    exit_code = cli.main([])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "FAIL" in captured.out
    assert "simulated failure" in captured.out
