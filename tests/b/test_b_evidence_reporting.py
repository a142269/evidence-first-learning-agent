"""Regression tests for B-side evidence report generation."""
from __future__ import annotations

from backend.app.services.spaced_repetition.hlr import sm2_vs_fsrs_vs_hlr_report
from scripts import benchmark_cognitive_models


def test_benchmark_script_registers_sakt() -> None:
    """SAKT should be available in the shared benchmark entry point."""
    assert "sakt" in benchmark_cognitive_models.MODEL_REGISTRY
    adapter = benchmark_cognitive_models.MODEL_REGISTRY["sakt"]()
    assert adapter.name == "SAKT"


def test_hlr_report_can_be_rendered_as_markdown() -> None:
    """Three-way scheduler comparison should have a stable markdown renderer."""
    report = sm2_vs_fsrs_vs_hlr_report(n_items=20)
    markdown = benchmark_cognitive_models.format_sm2_fsrs_hlr_markdown(report)

    assert "# SM-2 vs FSRS vs HLR" in markdown
    assert "avg_predicted_recall" in markdown
    assert "FSRS" in markdown
