"""Public surface of the diagnosis reporter package.

The reporter is split into:
  * `_helpers`      — ASCII / scoring helpers
  * `_models`       — frozen dataclasses for the report payload
  * `_markdown`     — Markdown rendering
  * `_json_payload` — JSON serialisation + schema validator
  * `reporter`      — orchestrator (DiagnosisReporter)

Legacy single-underscore helpers (`_bar`, `_stars`, `_slugify`) are
re-exported because earlier tests import them directly.
"""
# ruff: noqa: RUF001
from __future__ import annotations

from ._helpers import bar as _bar
from ._helpers import slugify as _slugify
from ._helpers import stars as _stars
from ._json_payload import SCHEMA_VERSION, build_json_payload, validate_report_json
from ._models import (
    BloomBundle,
    BloomCell,
    DiagnosisReport,
    ForecastBundle,
    IntegrationStatus,
    MasteryRow,
    RecommendationBundle,
    ReportQuestion,
    ReportWriteResult,
)
from .reporter import DiagnosisReporter

__all__ = [
    "SCHEMA_VERSION",
    "BloomBundle",
    "BloomCell",
    "DiagnosisReport",
    "DiagnosisReporter",
    "ForecastBundle",
    "IntegrationStatus",
    "MasteryRow",
    "RecommendationBundle",
    "ReportQuestion",
    "ReportWriteResult",
    "_bar",
    "_slugify",
    "_stars",
    "build_json_payload",
    "validate_report_json",
]
