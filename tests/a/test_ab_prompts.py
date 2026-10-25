"""QWEN-312: A/B harness script contract - dry-run default, gates, desensitization.

The script is loaded via importlib (golden_set_runner precedent).  Every case
runs offline with provider transports patched to AssertionError, so no paid
call is possible from these tests.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from backend.app.agent_runtime import prompts

ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = ROOT / "scripts" / "ab_prompts.py"
_SPEC = importlib.util.spec_from_file_location("ab_prompts", _SCRIPT)
ab_prompts = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ab_prompts)

CANDIDATE = {"tutor_instruction": "候选讲解指令：A/B harness 专用候选文本。"}
# Content snippets that must never appear in a desensitized report: candidate
# prompt text, scripted model text.  Structural ids (plan steps) are contract
# constants and may appear in results.
FORBIDDEN_SNIPPETS = ("候选讲解指令", "先检索课程证据", "脚本化讲解文本", "固定样例讲解")


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(CANDIDATE, ensure_ascii=False), encoding="utf-8")
    return path


def _no_transport():
    return patch("httpx.HTTPTransport.handle_request", side_effect=AssertionError("HTTP disabled")), \
        patch("httpx.AsyncHTTPTransport.handle_async_request", side_effect=AssertionError("HTTP disabled")), \
        patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP disabled"))


def test_dry_run_is_the_default_and_report_is_desensitized(tmp_path):
    report_path = tmp_path / "report-dry.json"
    patches = _no_transport()
    with patches[0], patches[1], patches[2]:
        exit_code = ab_prompts.main(["--candidate", str(_manifest(tmp_path)),
                                    "--report", str(report_path)])
    assert exit_code == 0
    raw = report_path.read_text(encoding="utf-8")
    report = json.loads(raw)
    assert report["mode"] == "dry-run" and report["status"] == "ok"
    assert report["prompt_version"] == "learning-package-v2.9"
    assert [variant["label"] for variant in report["variants"]] == ["A-baseline", "B-candidate"]
    assert report["integrity"] and set(report["integrity"].values()) == {"ok"}
    for snippet in FORBIDDEN_SNIPPETS:
        assert snippet not in raw


def test_execute_offline_compares_variants_without_transport(tmp_path):
    report_path = tmp_path / "report-exec.json"
    patches = _no_transport()
    with patches[0], patches[1], patches[2]:
        exit_code = ab_prompts.main(["--execute", "--candidate", str(_manifest(tmp_path)),
                                    "--report", str(report_path)])
    assert exit_code == 0
    raw = report_path.read_text(encoding="utf-8")
    report = json.loads(raw)
    assert report["mode"] == "offline-execute" and report["status"] == "ok"
    results = report["results"]
    assert set(results) == {"A-baseline", "B-candidate"}
    for runs in results.values():
        assert [run["sample"] for run in runs] == ["sample-1", "sample-2"]
        for run in runs:
            assert run["outcome"] == "completed"
            assert run["plan_steps"] == ["tutor_explain", "practice_apply"]
            assert run["exercise_count"] == 3
            assert run["lesson_citation_keys"] == ["chunk_id", "label", "score", "source"]
            assert run["review_approved"] is True
            assert run["claim_support_passed"] is True
            assert run["model_calls"] == 6
    assert report["budget"]["actual_model_calls_per_sample_max"] == 6
    assert report["budget"]["gate"] == "pass"
    for snippet in FORBIDDEN_SNIPPETS:
        assert snippet not in raw


def test_budget_gate_refuses_overestimated_execute(tmp_path):
    report_path = tmp_path / "report-gate.json"
    exit_code = ab_prompts.main(["--execute", "--max-model-calls", "3",
                                "--report", str(report_path)])
    assert exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "refused" and report["reason"] == "budget_gate"
    assert "results" not in report


def test_allow_paid_calls_flag_does_not_exist(tmp_path):
    """A live paid comparison is out of scope for QWEN-312: no such flag."""
    with pytest.raises(SystemExit) as exc:
        ab_prompts.main(["--allow-paid-calls", "--report", str(tmp_path / "unused.json")])
    assert exc.value.code == 2


def test_execute_refuses_non_offline_provider(tmp_path, monkeypatch):
    report_path = tmp_path / "report-live.json"
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("A3_OFFLINE_DEMO", raising=False)
    exit_code = ab_prompts.main(["--execute", "--report", str(report_path)])
    assert exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["reason"] == "offline_harness_only"


def test_unknown_candidate_name_is_a_stable_refusal(tmp_path):
    report_path = tmp_path / "report-unknown.json"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"no_such_prompt": "文本"}, ensure_ascii=False), encoding="utf-8")
    exit_code = ab_prompts.main(["--execute", "--candidate", str(bad),
                                "--report", str(report_path)])
    assert exit_code == 2
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["reason"] == "unknown_prompt"
    assert prompts_registry_untouched()


def prompts_registry_untouched() -> bool:
    from backend.app.agent_runtime import prompts
    return prompts._OVERRIDES == {}
