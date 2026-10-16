"""
Social learning API — Innovation #6 (v6 B-P3-3).

B owns /api/v1/social/*

Endpoints:
  GET /social/peer-suggestions   — complementary study partners
  GET /social/tutor-suggestions  — one-directional tutor recommendations

Privacy: all responses are sanitized — only user_id + complementary
dimensions + a natural-language reason are exposed. No raw profile scores.
All matches are suggestions requiring mutual consent.
"""
from __future__ import annotations

import logging
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/social", tags=["social"])


def _get_engine():
    from backend.app.services.social.recommendation_engine import RecommendationEngine
    return RecommendationEngine()


@lru_cache(maxsize=1)
def _demo_names() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4] / "data"
    names: dict[str, str] = {}
    for filename, key in (("seed.json", "students"), ("seed_extended.json", "extra_students")):
        try:
            payload = json.loads((root / filename).read_text(encoding="utf-8"))
        except Exception:
            continue
        for student in payload.get(key, []):
            if student.get("user_id"):
                names[str(student["user_id"])] = str(student.get("nickname") or student["user_id"])
    return names


def _enrich_peer_names(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = _demo_names()
    return [{**item, "display_name": names.get(str(item.get("user_id")), str(item.get("user_id") or "学习伙伴"))} for item in results]


def _mentor_directory(limit: int) -> list[dict[str, Any]]:
    """只返回真实教师角色或系统内 AI 导师，绝不把学生包装成导师。"""
    mentors = [
        {
            "user_id": "teacher",
            "display_name": "王老师",
            "role": "课程教师",
            "score": 0.96,
            "reason": "适合进行课程路径复核、学习进度诊断与阶段性反馈。",
        },
        {
            "user_id": "agent-zhiling",
            "display_name": "智灵",
            "role": "AI 概念导师",
            "score": 0.91,
            "reason": "适合拆解公式、前置知识与抽象概念，并通过追问检查理解。",
        },
        {
            "user_id": "agent-ajiang",
            "display_name": "阿匠",
            "role": "AI 工程导师",
            "score": 0.88,
            "reason": "适合提供可运行代码、调试步骤与工程化学习资源。",
        },
    ]
    return mentors[:limit]


@router.get("/peer-suggestions")
def peer_suggestions(
    user_id: str = Query(..., description="学生 ID"),
    limit: int = Query(5, ge=1, le=20),
    explain: bool = Query(True, description="返回自然语言推荐理由"),
) -> dict:
    """推荐互补学习伙伴。

    基于画像互补度（60%）+ 学习行为协同过滤（40%）混合排序。
    互补 = 你强他弱 + 他强你弱的双向互利，而非找相似的人。
    """
    try:
        engine = _get_engine()
        results = _enrich_peer_names(engine.recommend_peers(user_id, limit=limit, explain=explain))
        return {
            "user_id": user_id,
            "suggestions": results,
            "total": len(results),
            "privacy_note": "所有匹配均为建议，需双方同意后建立学习关系。",
        }
    except Exception as exc:
        logger.warning(f"[social] peer-suggestions failed: {exc}")
        return {"user_id": user_id, "suggestions": [], "total": 0, "error": str(exc)}


@router.get("/tutor-suggestions")
def tutor_suggestions(
    user_id: str = Query(..., description="学生 ID"),
    limit: int = Query(3, ge=1, le=10),
    explain: bool = Query(True, description="返回自然语言推荐理由"),
) -> dict:
    """推荐课程教师与系统 AI 导师；学生只会出现在同伴列表。"""
    try:
        results = _mentor_directory(limit)
        return {
            "user_id": user_id,
            "suggestions": results,
            "total": len(results),
            "privacy_note": "所有匹配均为建议，需双方同意后建立辅导关系。",
        }
    except Exception as exc:
        logger.warning(f"[social] tutor-suggestions failed: {exc}")
        return {"user_id": user_id, "suggestions": [], "total": 0, "error": str(exc)}
