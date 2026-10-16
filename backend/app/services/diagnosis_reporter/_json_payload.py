"""JSON serialisation + schema validation for diagnosis reports."""
# ruff: noqa: RUF001
from __future__ import annotations

from typing import Any

from ._helpers import mean
from ._models import (
    BloomBundle,
    ForecastBundle,
    IntegrationStatus,
    MasteryRow,
    RecommendationBundle,
)

SCHEMA_VERSION = "1.0"

_REQUIRED_TOP_LEVEL = (
    "schema_version",
    "user_id",
    "nickname",
    "archetype",
    "generated_at",
    "focus_kp_id",
    "sections",
    "integrations",
)

_REQUIRED_SECTIONS = (
    "profile",
    "mastery",
    "strengths",
    "weaknesses",
    "learning_path",
    "forecast",
    "mistakes",
    "recommendations",
    "bloom_6x3",
)


def build_json_payload(  # noqa: PLR0913
    *,
    user_id: str,
    nickname: str,
    archetype: str,
    generated_at_iso: str,
    focus_kp_id: str,
    profile_summary_text: str,
    profile_scores: list[tuple[str, float]],
    mastery_rows: list[MasteryRow],
    strengths: list[MasteryRow],
    weaknesses: list[MasteryRow],
    learning_path_entries: list[dict[str, Any]],
    mistake_payload: dict[str, Any],
    forecast: ForecastBundle,
    recommendations: RecommendationBundle,
    bloom: BloomBundle,
    integrations: dict[str, IntegrationStatus],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "user_id": user_id,
        "nickname": nickname,
        "archetype": archetype,
        "generated_at": generated_at_iso,
        "focus_kp_id": focus_kp_id,
        "sections": {
            "profile": {
                "summary": profile_summary_text,
                "archetype": archetype,
                "dimensions": [
                    {"name": name, "score": round(float(score), 4)}
                    for name, score in profile_scores
                ],
            },
            "mastery": {
                "kp_count": len(mastery_rows),
                "mean_combined": round(mean([row.combined for row in mastery_rows]), 4),
                "rows": [_mastery_row_to_dict(row) for row in mastery_rows],
            },
            "strengths": [_top_row_to_dict(row) for row in strengths],
            "weaknesses": [_top_row_to_dict(row) for row in weaknesses],
            "learning_path": {"items": learning_path_entries},
            "forecast": {
                "focus_kp_id": forecast.focus_kp_id,
                "focus_kp_name": forecast.focus_kp_name,
                "horizon_days": forecast.horizon_days,
                "available": forecast.status.available,
                "source": forecast.status.source,
                "fallback_reason": forecast.status.fallback_reason,
                "points": [
                    {
                        "day": int(point.day),
                        "p_learned": round(float(point.p_learned), 4),
                        "ci_low": round(float(point.ci_low), 4),
                        "ci_high": round(float(point.ci_high), 4),
                    }
                    for point in forecast.points
                ],
                "milestones": [
                    {
                        "day": int(milestone.get("day", 0)),
                        "target": float(milestone.get("target", 0.0)),
                        "label": str(milestone.get("label", "")),
                        "p_at_day": round(float(milestone.get("p_at_day", 0.0)), 4),
                    }
                    for milestone in forecast.milestones
                ],
            },
            "mistakes": mistake_payload,
            "recommendations": {
                "source": recommendations.status.source,
                "available": recommendations.status.available,
                "fallback_reason": recommendations.status.fallback_reason,
                "questions": [
                    {
                        "question_id": question.question_id,
                        "kp_id": question.kp_id,
                        "kp_name": question.kp_name,
                        "bloom": question.bloom,
                        "difficulty": int(question.difficulty),
                        "stem": question.stem,
                        "selection_score": (
                            round(question.selection_score, 4)
                            if question.selection_score is not None
                            else None
                        ),
                        "selection_reason": question.selection_reason,
                    }
                    for question in recommendations.questions
                ],
            },
            "bloom_6x3": {
                "source": bloom.status.source,
                "available": bloom.status.available,
                "fallback_reason": bloom.status.fallback_reason,
                "cells": [
                    {
                        "cognitive": cell.cognitive,
                        "cognitive_label": cell.cognitive_label,
                        "knowledge_dim": cell.knowledge_dim,
                        "knowledge_label": cell.knowledge_label,
                        "count": int(cell.count),
                        "sub_levels": list(cell.sub_levels),
                    }
                    for cell in bloom.cells
                ],
                "cognitive_totals": dict(bloom.cognitive_totals),
            },
        },
        "integrations": {
            name: {
                "available": status.available,
                "source": status.source,
                "fallback_reason": status.fallback_reason,
            }
            for name, status in integrations.items()
        },
    }


def validate_report_json(payload: dict[str, Any]) -> list[str]:
    """Return a list of structural issues; empty list means the payload is valid."""
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a dict"]

    for key in _REQUIRED_TOP_LEVEL:
        if key not in payload:
            issues.append(f"missing top-level key: {key}")

    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            f"schema_version mismatch: expected {SCHEMA_VERSION}, "
            f"got {payload.get('schema_version')!r}"
        )

    sections = payload.get("sections")
    if not isinstance(sections, dict):
        issues.append("sections must be a dict")
        return issues

    for name in _REQUIRED_SECTIONS:
        if name not in sections:
            issues.append(f"missing section: {name}")

    issues.extend(_validate_profile(sections.get("profile")))
    issues.extend(_validate_mastery(sections.get("mastery")))
    issues.extend(_validate_ranking(sections.get("strengths"), label="strengths"))
    issues.extend(_validate_ranking(sections.get("weaknesses"), label="weaknesses"))
    issues.extend(_validate_learning_path(sections.get("learning_path")))
    issues.extend(_validate_forecast(sections.get("forecast")))
    issues.extend(_validate_recommendations(sections.get("recommendations")))
    issues.extend(_validate_bloom(sections.get("bloom_6x3")))

    return issues


def _validate_profile(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["profile must be a dict"]
    issues: list[str] = []
    dims = value.get("dimensions")
    if not isinstance(dims, list) or len(dims) != 8:
        issues.append("profile.dimensions must be a list of 8 entries")
    else:
        for entry in dims:
            if not isinstance(entry, dict) or "name" not in entry or "score" not in entry:
                issues.append(f"invalid profile dimension entry: {entry!r}")
    return issues


def _validate_mastery(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["mastery must be a dict"]
    rows = value.get("rows")
    if not isinstance(rows, list) or len(rows) < 1:
        return ["mastery.rows must be a non-empty list"]
    issues: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            issues.append("mastery row must be a dict")
            continue
        for key in ("kp_id", "name", "course", "bloom", "difficulty", "realdina", "combined"):
            if key not in row:
                issues.append(f"mastery row missing key: {key}")
    return issues


def _validate_ranking(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    issues: list[str] = []
    for entry in value:
        if not isinstance(entry, dict) or "kp_id" not in entry or "score" not in entry:
            issues.append(f"invalid {label} entry: {entry!r}")
    return issues


def _validate_learning_path(value: Any) -> list[str]:
    if not isinstance(value, dict) or "items" not in value:
        return ["learning_path.items missing"]
    if not isinstance(value["items"], list):
        return ["learning_path.items must be a list"]
    return []


def _validate_forecast(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["forecast must be a dict"]
    issues: list[str] = []
    for key in ("focus_kp_id", "horizon_days", "available", "source", "points", "milestones"):
        if key not in value:
            issues.append(f"forecast missing key: {key}")
    if isinstance(value.get("points"), list):
        for point in value["points"]:
            if not isinstance(point, dict) or "day" not in point or "p_learned" not in point:
                issues.append(f"invalid forecast point: {point!r}")
    return issues


def _validate_recommendations(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["recommendations must be a dict"]
    issues: list[str] = []
    if "source" not in value:
        issues.append("recommendations.source missing")
    questions = value.get("questions")
    if not isinstance(questions, list):
        issues.append("recommendations.questions must be a list")
        return issues
    for question in questions:
        if not isinstance(question, dict):
            issues.append("recommendation question must be a dict")
            continue
        for key in ("question_id", "kp_id", "bloom", "difficulty", "stem"):
            if key not in question:
                issues.append(f"recommendation question missing key: {key}")
    return issues


def _validate_bloom(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["bloom_6x3 must be a dict"]
    issues: list[str] = []
    cells = value.get("cells")
    if not isinstance(cells, list):
        issues.append("bloom_6x3.cells must be a list")
        return issues
    for cell in cells:
        if not isinstance(cell, dict):
            issues.append("bloom_6x3 cell must be a dict")
            continue
        for key in ("cognitive", "knowledge_dim", "count"):
            if key not in cell:
                issues.append(f"bloom_6x3 cell missing key: {key}")
    return issues


def _mastery_row_to_dict(row: MasteryRow) -> dict[str, Any]:
    return {
        "kp_id": row.kp_id,
        "name": row.name,
        "course": row.course,
        "bloom": row.bloom,
        "difficulty": int(row.difficulty),
        "realdina": round(float(row.realdina), 4),
        "bkt": round(float(row.bkt), 4) if row.bkt is not None else None,
        "combined": round(float(row.combined), 4),
    }


def _top_row_to_dict(row: MasteryRow) -> dict[str, Any]:
    return {
        "kp_id": row.kp_id,
        "name": row.name,
        "score": round(float(row.combined), 4),
        "bloom": row.bloom,
        "difficulty": int(row.difficulty),
    }
