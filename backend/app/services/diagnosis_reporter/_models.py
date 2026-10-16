"""Dataclasses describing the structured diagnosis report."""
# ruff: noqa: RUF001
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.services.cognitive_diagnosis.bkt_forecaster import ForecastPoint


@dataclass(frozen=True)
class MasteryRow:
    kp_id: str
    name: str
    course: str
    bloom: str
    difficulty: int
    realdina: float
    bkt: float | None
    combined: float


@dataclass(frozen=True)
class ReportQuestion:
    question_id: str
    kp_id: str
    kp_name: str
    bloom: str
    difficulty: int
    stem: str
    selection_score: float | None = None
    selection_reason: str | None = None


@dataclass(frozen=True)
class BloomCell:
    cognitive: str
    cognitive_label: str
    knowledge_dim: str
    knowledge_label: str
    count: int
    sub_levels: list[str]


@dataclass(frozen=True)
class IntegrationStatus:
    """Whether an optional B-owned service was actually invoked."""

    available: bool
    source: str
    fallback_reason: str | None = None


@dataclass(frozen=True)
class RecommendationBundle:
    questions: list[ReportQuestion]
    status: IntegrationStatus


@dataclass(frozen=True)
class ForecastBundle:
    focus_kp_id: str
    focus_kp_name: str
    horizon_days: int
    points: list[ForecastPoint]
    milestones: list[dict[str, Any]]
    status: IntegrationStatus


@dataclass(frozen=True)
class BloomBundle:
    cells: list[BloomCell]
    cognitive_totals: dict[str, int]
    status: IntegrationStatus


@dataclass(frozen=True)
class DiagnosisReport:
    user_id: str
    nickname: str
    archetype: str
    generated_at: datetime
    focus_kp_id: str
    markdown: str
    json_payload: dict[str, Any]
    profile_scores: list[tuple[str, float]]
    mastery_rows: list[MasteryRow]
    strengths: list[MasteryRow]
    weaknesses: list[MasteryRow]
    forecast: ForecastBundle
    recommendations: RecommendationBundle
    bloom: BloomBundle
    integrations: dict[str, IntegrationStatus] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportWriteResult:
    markdown_path: Path | None
    json_path: Path | None
    pdf_path: Path | None
    report: DiagnosisReport
