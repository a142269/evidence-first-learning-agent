from __future__ import annotations

import json

from scripts import collect_learning_package_online as collector


def test_complete_resume_does_not_login_or_repeat_requests(monkeypatch, tmp_path):
    progress = tmp_path / "progress.jsonl"
    progress.write_text(json.dumps({
        "id": "lp-normal-001",
        "scenario": "standard",
        "events": ["run.failed"],
        "result": {"error": "recorded_failure"},
    }) + "\n", encoding="utf-8")

    def unexpected(*_args, **_kwargs):
        raise AssertionError("complete resume must not access the API")

    monkeypatch.setattr(collector, "_login", unexpected)
    monkeypatch.setattr(collector, "_collect", unexpected)
    report = tmp_path / "report.json"
    review = tmp_path / "review.jsonl"
    result = collector.main([
        "--base-url", "http://example.invalid",
        "--case-id", "lp-normal-001",
        "--resume",
        "--progress", str(progress),
        "--report", str(report),
        "--review-template", str(review),
    ])

    assert result == 1
    assert json.loads(report.read_text(encoding="utf-8"))["summary"]["case_count"] == 1
    assert review.exists()
