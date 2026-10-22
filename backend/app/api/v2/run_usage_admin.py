"""Admin-only read-only visibility of per-run model usage and cost (QWEN-104).

Students never see this surface: every route first resolves a real login session
and then requires the teacher/admin role via ``authorize_reviewer``. The handlers
only read ``agent_runs`` and project the accounting that execution already wrote,
so a request cannot start work, spend tokens, or change a run.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from backend.app.api.v2 import access
from backend.app.core.models import AgentRunRecord
from backend.app.services.run_usage import aggregate_run_usage, summarize_run_usage

router = APIRouter(prefix="/api/v2/admin", tags=["admin-v2"])


async def _reviewer_principal(authorization: str | None) -> access.V2Principal:
    try:
        principal = await asyncio.to_thread(access._principal_from_authorization, authorization)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="authorization_required") from None
    if principal is None:
        raise HTTPException(status_code=401, detail="authorization_required")
    access.authorize_reviewer(principal=principal)
    return principal


def _read_usage(run_id: str | None, *, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    from sqlalchemy import func, select

    from backend.app.core import database

    with database.SessionLocal() as session:
        if run_id is not None:
            row = session.get(AgentRunRecord, run_id)
            if row is None:
                raise HTTPException(status_code=404, detail="run_not_found")
            return [summarize_run_usage(row)], 1
        rows = session.scalars(select(AgentRunRecord).order_by(
            AgentRunRecord.created_at.desc(), AgentRunRecord.id.asc())
            .limit(limit).offset(offset)).all()
        total = session.scalar(select(func.count()).select_from(AgentRunRecord))
        return [summarize_run_usage(row) for row in rows], int(total or 0)


@router.get("/run-usage")
async def list_run_usage(http_request: Request, limit: int = Query(default=50, ge=1, le=200),
                         offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
    await _reviewer_principal(http_request.headers.get("Authorization"))
    try:
        runs, total = await asyncio.to_thread(_read_usage, None, limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None
    return {"runs": runs, "total": total, "limit": limit, "offset": offset,
            "aggregates_scope": "current_page", "aggregates": aggregate_run_usage(runs)}


@router.get("/run-usage/{run_id}")
async def get_run_usage(http_request: Request, run_id: str) -> dict[str, Any]:
    await _reviewer_principal(http_request.headers.get("Authorization"))
    try:
        runs, _ = await asyncio.to_thread(_read_usage, run_id, limit=1, offset=0)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None
    return runs[0]
