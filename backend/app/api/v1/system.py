# ruff: noqa: B008
"""A-owned `/api/v1/system/*` routes for evaluator-facing demos.

Currently exposes the T1.2 variant generation endpoint. Lives outside
`mistakes.py` (B-owned) so we can iterate without touching B files.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from backend.app.services.variant_generator import (
    VariantGenerationRequest,
    VariantGenerator,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["system"])

_DEMO_SAMPLES_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "variant_demo_samples.json"
)


def _resolve_mistake(mistake_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Try the request body first, then fall back to in-memory + DB lookup."""
    record: dict[str, Any] = {
        "id": mistake_id,
        "user_id": str(payload.get("user_id", "")),
        "kp_id": str(payload.get("kp_id", "")),
        "kp_name": str(payload.get("kp_name", "")),
        "question": str(payload.get("question", "")),
        "student_answer": str(payload.get("student_answer", "")),
        "correct_answer": str(payload.get("correct_answer", "")),
    }
    if record["question"] and record["correct_answer"]:
        return record

    try:
        from backend.app.api.v1 import mistakes as mistake_api

        looked_up = mistake_api._find_mistake(mistake_id)
    except Exception as exc:
        logger.warning("[system/variant] mistake lookup failed: %s", exc)
        looked_up = None

    if looked_up:
        for key in ("user_id", "kp_id", "question", "student_answer", "correct_answer"):
            record[key] = record[key] or str(looked_up.get(key, ""))
    return record


@router.post("/variant/{mistake_id}")
def generate_variant(
    mistake_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    count: int = Query(default=3, ge=1, le=5),
) -> dict[str, Any]:
    """Generate Bloom-leveled variants for a single mistake (A's T1.2 endpoint).

    Body fields (all optional — looked up from mistakes storage when omitted):
      * user_id, kp_id, kp_name
      * question, student_answer, correct_answer
      * count (1-5, default 3)
    """
    record = _resolve_mistake(mistake_id, payload)
    if not record["question"] or not record["correct_answer"]:
        raise HTTPException(
            status_code=400,
            detail="question_and_correct_answer_required",
        )
    request = VariantGenerationRequest(
        user_id=record["user_id"] or "anonymous-student",
        mistake_id=mistake_id,
        question=record["question"],
        student_answer=record["student_answer"],
        correct_answer=record["correct_answer"],
        kp_id=record["kp_id"],
        kp_name=record["kp_name"],
        count=int(payload.get("count", count)),
    )
    package = VariantGenerator().generate(request)
    package["source_endpoint"] = "system.variant"
    return package


@router.get("/variant/demo-samples")
def variant_demo_samples() -> dict[str, Any]:
    """Five curated mistake samples used to show off the variant loop."""
    if not _DEMO_SAMPLES_PATH.exists():
        return {"samples": [], "total": 0}
    payload = json.loads(_DEMO_SAMPLES_PATH.read_text(encoding="utf-8"))
    samples = payload.get("samples", [])
    return {"samples": samples, "total": len(samples)}
