"""Append-only audit log for tool access decisions, refusals included.

The V1 registry kept a display-oriented trace (``ToolCallTrace``) and the V2
broker returned a per-call ``audit()`` dictionary that only reached the run state
when the call *succeeded* far enough to be returned. Refusals - unknown tool, role
not allowed, missing scope - were therefore invisible. ``V2LearningTools`` and
``_traced_call`` now both write one event per call here, whatever the outcome, so
the record of who was refused what lives in exactly one place.

Events never carry prompts, argument values, retrieved text, or identifiers beyond
the run/session scope already visible to the caller: ``request_hash`` is a digest.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Any, Optional

from backend.app.services.tool_catalog import ToolSpec

MAX_EVENTS = 500

AUDIT_EVENT_KEYS = frozenset({
    "tool", "source", "version", "role", "run_id", "session_id", "status", "decision",
    "reason", "permission_key", "side_effect", "timeout_seconds", "latency_ms",
    "request_hash",
})


def build_event(*, tool: str, spec: Optional[ToolSpec], role: str, status: str,
                decision: str, latency_ms: int, request_hash: str, reason: str = "",
                run_id: str = "", session_id: str = "") -> dict[str, Any]:
    """Derive every metadata field from the catalog spec, never from a caller copy.

    ``tool`` is the *attempted* name: an unknown-tool refusal has no spec, and the
    audit still has to record which name was tried.
    """
    return {
        "tool": tool,
        "source": spec.source if spec is not None else "",
        "version": spec.version if spec is not None else "",
        "role": role,
        "run_id": run_id,
        "session_id": session_id,
        "status": status,
        "decision": decision,
        "reason": reason,
        "permission_key": spec.permission_key if spec is not None else "",
        "side_effect": bool(spec.side_effect) if spec is not None else False,
        "timeout_seconds": spec.timeout_seconds if spec is not None else None,
        "latency_ms": int(latency_ms),
        "request_hash": request_hash,
    }


class ToolAuditLog:
    def __init__(self, max_size: int = MAX_EVENTS) -> None:
        self._max = int(max_size)
        self._lock = threading.RLock()
        self._events: deque[dict[str, Any]] = deque(maxlen=self._max)

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        missing = AUDIT_EVENT_KEYS - set(event)
        extra = set(event) - AUDIT_EVENT_KEYS
        if missing or extra:
            raise ValueError(f"tool audit event shape drift: missing={sorted(missing)} extra={sorted(extra)}")
        with self._lock:
            self._events.append(dict(event))
        return event

    def recent(self, *, tool: str = "", decision: str = "", limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._events)
        if tool:
            items = [item for item in items if item["tool"] == tool]
        if decision:
            items = [item for item in items if item["decision"] == decision]
        items.reverse()
        return items[:limit]

    def counts(self) -> dict[str, Any]:
        with self._lock:
            items = list(self._events)
        by_status: dict[str, int] = {}
        by_decision: dict[str, int] = {}
        by_tool: dict[str, int] = {}
        for item in items:
            by_status[item["status"]] = by_status.get(item["status"], 0) + 1
            by_decision[item["decision"]] = by_decision.get(item["decision"], 0) + 1
            by_tool[item["tool"]] = by_tool.get(item["tool"], 0) + 1
        refused = sum(count for decision, count in by_decision.items() if decision != "granted")
        return {
            "total": len(items),
            "granted": len(items) - refused,
            "refused": refused,
            "by_status": by_status,
            "by_decision": by_decision,
            "by_tool": by_tool,
        }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


_log = ToolAuditLog()


def get_tool_audit_log() -> ToolAuditLog:
    return _log


def record_tool_event(*, tool: str, spec: Optional[ToolSpec], role: str, status: str,
                      decision: str, latency_ms: int, request_hash: str, reason: str = "",
                      run_id: str = "", session_id: str = "") -> dict[str, Any]:
    return _log.record(build_event(
        tool=tool, spec=spec, role=role, status=status, decision=decision,
        latency_ms=latency_ms, request_hash=request_hash, reason=reason,
        run_id=run_id, session_id=session_id))


def reset_tool_audit_log() -> None:
    _log.clear()
