"""Plan P1-1 / P1-6：Agent 工具调用 trace API

GET /api/v1/agent-tools/trace
  ?session_id=... &limit=20
  返回 [{tool, args, success, latency_ms, timestamp, error}, ...]

GET /api/v1/agent-tools/trace/stats
  ?session_id=...
  返回 {total, success, failed, success_rate, by_tool}
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query

from backend.app.services.agent_tools.registry import (
    get_tool_trace,
    reset_tool_trace,
)

router = APIRouter(prefix="/agent-tools", tags=["agent-tools"])


@router.get("/trace")
def get_trace(
    session_id: str = Query(default="", description="可选 session 过滤"),
    limit: int = Query(default=20, ge=1, le=200),
) -> Dict[str, Any]:
    items = get_tool_trace().recent(session_id=session_id, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/trace/stats")
def get_trace_stats(session_id: str = Query(default="")) -> Dict[str, Any]:
    return get_tool_trace().stats(session_id=session_id)


@router.post("/trace/clear")
def clear_trace(session_id: str = Query(default="")) -> Dict[str, Any]:
    get_tool_trace().clear(session_id=session_id)
    return {"ok": True}
