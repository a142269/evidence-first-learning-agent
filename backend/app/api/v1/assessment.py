"""
Assessment API - B owns /api/v1/assessment/*

Persistence: prefers AssessmentRepository (SQLite), falls back to in-memory list.
Chat API accesses _assessments directly for backward compatibility.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from fastapi import APIRouter, Body

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assessment", tags=["assessment"])

_repository = None
_assessments: dict[str, list] = {}  # chat.py backward-compat entry point

try:
    from backend.app.repositories.assessment_repo import AssessmentRepository
    _repository = AssessmentRepository()
except ImportError:
    logger.warning("[assessment] Repository unavailable, using in-memory storage")


@router.get("/{user_id}")
def get_assessment(user_id: str):
    if _repository is not None:
        return _repository.summary(user_id)

    records = _assessments.get(user_id, [])
    quiz_scores = [r["score"] for r in records if r.get("type") == "quiz" and "score" in r]
    avg = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 0
    completed_task_ids = list(dict.fromkeys(
        str((record.get("metadata") or {}).get("task_id", ""))
        for record in records
        if record.get("type") == "task_completed" and (record.get("metadata") or {}).get("task_id")
    ))
    return {
        "user_id": user_id,
        "total_sessions": len(records),
        "quiz_avg_score": round(avg, 1),
        "resources_used": sum(1 for r in records if r.get("type") == "resource_view"),
        "questions_asked": sum(1 for r in records if r.get("type") == "question"),
        "completed_task_ids": completed_task_ids,
        "recent_records": records[-10:],
    }


@router.post("/{user_id}/record")
def add_record(user_id: str, payload: dict[str, Any] = Body(...)):
    record = {
        "external_id": payload.get("external_id"),
        "type": payload.get("type", "activity"),
        "score": payload.get("score"),
        "topic": payload.get("topic", ""),
        "duration": payload.get("duration", 0),
        "timestamp": time.time(),
        "metadata": payload.get("metadata", {}),
    }
    if _repository is not None:
        saved = _repository.add(user_id, record)
    else:
        if user_id not in _assessments:
            _assessments[user_id] = []
        _assessments[user_id].append(record)
        saved = record
    return {"status": "recorded", "record": saved}
