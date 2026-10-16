"""Tests for the T1.1 learning diagnosis report generator."""
# ruff: noqa: RUF001
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.app.services.diagnosis_reporter import (
    DiagnosisReporter,
    SCHEMA_VERSION,
    _bar,
    _slugify,
    _stars,
    validate_report_json,
)
from backend.app.services.diagnosis_reporter._helpers import archetype_from_nickname
from scripts import generate_diagnosis_report as cli

FIXED_TIME = datetime(2026, 6, 28, 9, 0, tzinfo=timezone.utc)
DEMO_USERS = (
    "demo-student-1",
    "demo-student-2",
    "demo-student-3",
    "demo-student-4",
    "demo-student-5",
)
REQUIRED_HEADINGS = (
    "## 1. 学习者画像",
    "## 2. 当前掌握度",
    "## 3. 强弱项 Top-3",
    "## 4. 学习路径建议",
    "## 5. 未来 30 天预测",
    "## 6. 错题风险分析",
    "## 7. 建议练习题",
    "## 8. Bloom 6×3 分布",
)


# ---------------------------------------------------------------------------
# Markdown structure
# ---------------------------------------------------------------------------
def test_build_report_contains_eight_required_sections() -> None:
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    for heading in REQUIRED_HEADINGS:
        assert heading in report.markdown, f"missing section: {heading}"


def test_profile_radar_has_eight_dimensions_and_archetype() -> None:
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    assert len(report.profile_scores) == 8
    assert all(0.0 <= score <= 1.0 for _, score in report.profile_scores)
    assert report.archetype == "进阶型"


def test_mastery_rows_cover_twenty_seed_kps() -> None:
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    assert len(report.mastery_rows) == 20
    assert {row.kp_id for row in report.mastery_rows} >= {"cnn", "transformer", "rag"}


def test_strengths_and_weaknesses_are_ranked() -> None:
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    strength_values = [row.combined for row in report.strengths]
    weakness_values = [row.combined for row in report.weaknesses]
    assert strength_values == sorted(strength_values, reverse=True)
    assert weakness_values == sorted(weakness_values)


def test_recommended_questions_are_five_unique_items() -> None:
    report = DiagnosisReporter().build_report("demo-student-2", generated_at=FIXED_TIME)
    questions = report.recommendations.questions
    qids = [question.question_id for question in questions]
    assert len(qids) == 5
    assert len(set(qids)) == 5
    assert all(question.stem for question in questions)


def test_forecast_contains_day_30_for_focus_kp() -> None:
    report = DiagnosisReporter().build_report(
        "demo-student-1",
        generated_at=FIXED_TIME,
        focus_kp_id="cnn",
    )
    assert report.focus_kp_id == "cnn"
    assert report.forecast.status.available
    assert report.forecast.points[-1].day == 30
    assert report.forecast.points[-1].p_learned >= report.forecast.points[0].p_learned


def test_kp_names_are_rendered_in_mastery_table() -> None:
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    assert "卷积神经网络 (`cnn`)" in report.markdown
    assert "检索增强生成 (RAG)" in report.markdown


def test_report_is_deterministic_for_same_timestamp() -> None:
    reporter = DiagnosisReporter()
    first = reporter.build_report("demo-student-4", generated_at=FIXED_TIME)
    second = reporter.build_report("demo-student-4", generated_at=FIXED_TIME)
    assert first.markdown == second.markdown
    assert first.json_payload == second.json_payload


def test_unknown_user_uses_fallback_profile() -> None:
    report = DiagnosisReporter().build_report("ghost-user", generated_at=FIXED_TIME)
    assert report.nickname == "ghost-user（临时画像）"
    assert report.archetype == "临时画像"
    assert len(report.mastery_rows) == 20
    assert len(report.recommendations.questions) == 5


def test_ascii_helpers_are_bounded_and_slug_is_safe() -> None:
    assert _bar(1.5, width=4) == "[####] 100%"
    assert _stars(-0.1) == "-----"
    assert _slugify("demo student/1") == "demo-student-1"


# ---------------------------------------------------------------------------
# Write paths + dual format
# ---------------------------------------------------------------------------
def test_write_report_creates_markdown_and_json(tmp_path: Path) -> None:
    result = DiagnosisReporter().write_report(
        "demo-student-1",
        output_dir=tmp_path,
        generated_at=FIXED_TIME,
    )
    assert result.markdown_path is not None
    assert result.json_path is not None
    assert result.markdown_path.exists()
    assert result.json_path.exists()
    assert result.markdown_path.name == "demo-student-1_20260628.md"
    assert result.json_path.name == "demo-student-1_20260628.json"
    md_text = result.markdown_path.read_text(encoding="utf-8")
    assert "学习诊断报告：杜同学" in md_text
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["user_id"] == "demo-student-1"


def test_write_report_respects_format_only_json(tmp_path: Path) -> None:
    result = DiagnosisReporter().write_report(
        "demo-student-2",
        output_dir=tmp_path,
        generated_at=FIXED_TIME,
        formats=("json",),
    )
    assert result.markdown_path is None
    assert result.json_path is not None
    assert result.json_path.exists()


def test_write_report_rejects_unknown_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported output formats"):
        DiagnosisReporter().write_report(
            "demo-student-1",
            output_dir=tmp_path,
            generated_at=FIXED_TIME,
            formats=("pdf",),
        )


def test_all_five_demo_students_render_both_formats(tmp_path: Path) -> None:
    reporter = DiagnosisReporter()
    written: list[tuple[Path, Path]] = []
    for user_id in DEMO_USERS:
        result = reporter.write_report(
            user_id,
            output_dir=tmp_path,
            generated_at=FIXED_TIME,
        )
        assert result.markdown_path is not None
        assert result.json_path is not None
        assert result.markdown_path.exists()
        assert result.json_path.exists()
        written.append((result.markdown_path, result.json_path))
    assert len(written) == 5
    assert {p.name for p, _ in written} == {f"{u}_20260628.md" for u in DEMO_USERS}


# ---------------------------------------------------------------------------
# JSON schema validation
# ---------------------------------------------------------------------------
def test_json_payload_passes_schema_validator() -> None:
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    issues = validate_report_json(report.json_payload)
    assert issues == [], f"validator issues: {issues}"


def test_validator_flags_missing_sections() -> None:
    bad_payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "user_id": "x",
        "nickname": "x",
        "archetype": "x",
        "generated_at": "2026-06-28T00:00:00+00:00",
        "focus_kp_id": "x",
        "sections": {},
        "integrations": {},
    }
    issues = validate_report_json(bad_payload)
    assert any("missing section" in issue for issue in issues)


def test_validator_flags_wrong_schema_version() -> None:
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    bad = dict(report.json_payload)
    bad["schema_version"] = "0.0"
    assert any("schema_version mismatch" in issue for issue in validate_report_json(bad))


def test_validator_runs_for_every_demo_student() -> None:
    reporter = DiagnosisReporter()
    for user_id in DEMO_USERS:
        report = reporter.build_report(user_id, generated_at=FIXED_TIME)
        assert validate_report_json(report.json_payload) == []


# ---------------------------------------------------------------------------
# B-service integration + Bloom 6×3 + forecast fallbacks
# ---------------------------------------------------------------------------
def test_recommendations_use_uncertainty_sampler_when_available() -> None:
    report = DiagnosisReporter().build_report("demo-student-3", generated_at=FIXED_TIME)
    status = report.recommendations.status
    assert status.available
    assert "uncertainty_sampler" in status.source
    scores = [q.selection_score for q in report.recommendations.questions]
    assert all(score is not None and 0.0 <= score <= 1.0 for score in scores)


def test_bloom_6x3_distribution_uses_5_recommendations() -> None:
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    bloom = report.bloom
    assert bloom.status.available
    total = sum(cell.count for cell in bloom.cells)
    assert total == len(report.recommendations.questions) == 5
    assert all(cell.knowledge_dim for cell in bloom.cells)


def test_forecast_section_falls_back_when_forecaster_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services.diagnosis_reporter import reporter as reporter_module

    class _Broken:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("simulated forecaster crash")

    monkeypatch.setattr(reporter_module, "BKTForecaster", _Broken)
    report = DiagnosisReporter().build_report("demo-student-1", generated_at=FIXED_TIME)
    assert not report.forecast.status.available
    assert "simulated forecaster crash" in (report.forecast.status.fallback_reason or "")
    assert "N/A (B 服务未就绪)" in report.markdown


# ---------------------------------------------------------------------------
# Helpers + CLI
# ---------------------------------------------------------------------------
def test_archetype_extracted_from_chinese_nickname() -> None:
    assert archetype_from_nickname("小明（自驱型）") == "自驱型"
    assert archetype_from_nickname("小红 (追赶型)") == "追赶型"
    assert archetype_from_nickname("匿名学习者") is None


def test_cli_parse_format_arg_accepts_aliases() -> None:
    assert DiagnosisReporter.parse_format_arg("both") == ("md", "json")
    assert DiagnosisReporter.parse_format_arg("markdown") == ("md",)
    assert DiagnosisReporter.parse_format_arg("json") == ("json",)
    with pytest.raises(ValueError):
        DiagnosisReporter.parse_format_arg("pdf")


def test_cli_main_writes_both_formats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = cli.main(
        [
            "--user",
            "demo-student-2",
            "--out-dir",
            str(tmp_path),
            "--format",
            "both",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Markdown report:" in captured.out
    assert "JSON report" in captured.out
    written = sorted(p.name for p in tmp_path.iterdir())
    today_segment = datetime.now(timezone.utc).strftime("%Y%m%d")
    assert f"demo-student-2_{today_segment}.md" in written
    assert f"demo-student-2_{today_segment}.json" in written
