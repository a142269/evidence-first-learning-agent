from __future__ import annotations

import importlib.util
from pathlib import Path

import requests

from backend.app.evaluation.golden_set import GoldenCase


_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_golden_set.py"
_SPEC = importlib.util.spec_from_file_location("golden_set_runner", _SCRIPT)
assert _SPEC and _SPEC.loader
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)


def test_live_case_retries_a_transient_timeout(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            return None

        def iter_lines(self, **_kwargs):
            return iter(
                [
                    "event: run.completed",
                    'data: {"answer":"ok","citations":[]}',
                ]
            )

    calls = {"count": 0}

    def post(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.Timeout("transient timeout")
        return Response()

    monkeypatch.setattr(runner.requests, "post", post)
    monkeypatch.setattr(runner.time, "sleep", lambda *_args: None)
    result = runner.run_live_case(
        "http://example.test",
        GoldenCase("case-1", "course_qa", "question", "ai", [], "answer_with_citations"),
        timeout=1,
        retries=1,
    )

    assert calls["count"] == 2
    assert result["attempts"] == 2
    assert result["events"] == ["run.completed"]


def test_live_review_preserves_leak_evidence(monkeypatch):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def raise_for_status(self):
            pass
        def iter_lines(self, **_):
            return iter(['event: review.required',
                'data: {"approval":{"draft_answer":"secret","citations":[{"source":"private.md"}]}}'])
    monkeypatch.setattr(runner.requests, "post", lambda *_, **__: Response())
    case = GoldenCase("r", "review", "question", "ai", (), "review_required")
    result = runner.run_live_case("http://example.test", case, timeout=1)
    from backend.app.evaluation.golden_set import grade_case
    assert result["answer"] == "secret"
    assert not grade_case(case, result)["passed"]


def test_early_closed_stream_is_not_a_success(monkeypatch):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def raise_for_status(self):
            pass
        def iter_lines(self, **_):
            return iter(['event: run.started', 'data: {"run_id":"x"}'])
    monkeypatch.setattr(runner.requests, "post", lambda *_, **__: Response())
    result = runner.run_live_case("http://example.test", GoldenCase("q", "qa", "q", "ai", (), "abstain"), 1)
    assert result["error"] == "stream_ended_without_terminal_event"


def test_online_progress_resumes_without_repeating_paid_cases(monkeypatch, tmp_path):
    cases = [GoldenCase("q1", "course_qa", "first", "ai", [], "answer_with_citations"),
             GoldenCase("q2", "course_qa", "second", "ai", [], "answer_with_citations")]
    calls = []
    monkeypatch.setattr(runner, "run_live_case", lambda _url, case, *_args:
                        calls.append(case.case_id) or {"answer": case.question})
    journal = tmp_path / "progress.jsonl"
    first = runner.run_live("http://example.test", cases, 1, progress=journal)
    assert calls == ["q1", "q2"]
    assert first["q1"]["answer"] == "first"
    calls.clear()
    assert runner.run_live("http://example.test", cases, 1, progress=journal, resume=True) == first
    assert calls == []
