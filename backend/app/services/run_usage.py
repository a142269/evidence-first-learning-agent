"""Read-only projection of the per-run model accounting that is already persisted.

Provider usage is written by ``backend/app/agent_runtime/usage_meter.py`` into
``agent_runs.metadata["result"]["budget"]``; nothing in this module recomputes a
price or invents a token count. Values the provider never returned stay ``null``
and are labelled ``unknown``, so an absent measurement can never be mistaken for
a zero-cost run.
"""
from __future__ import annotations

import math
from typing import Any

MEASURED = "measured"
PARTIAL = "partial"
UNKNOWN = "unknown"
ESTIMATED = "estimated"

USAGE_STATUSES = (MEASURED, PARTIAL, UNKNOWN)
COST_STATUSES = (ESTIMATED, UNKNOWN)


def _count(value: Any) -> int | None:
    """Accept only a real non-negative integer; anything else is 'not recorded'."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _number(value: Any) -> int | float | None:
    """Accept a finite non-negative number; counts stay on ``_count``, which is int-only."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _amount(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _budget_of(metadata: dict[str, Any]) -> dict[str, Any]:
    return _mapping(_mapping(metadata.get("result")).get("budget"))


def _cost_of(budget: dict[str, Any]) -> dict[str, Any]:
    raw = budget.get("cost")
    if not isinstance(raw, dict):
        return {"status": UNKNOWN, "currency": "CNY", "reason": "cost_not_recorded"}
    status = raw.get("status") if raw.get("status") in COST_STATUSES else UNKNOWN
    projected: dict[str, Any] = {"status": status, "currency": raw.get("currency") or "CNY"}
    amount = _amount(raw.get("amount_cny"))
    if status == ESTIMATED and amount is not None:
        projected["amount_cny"] = amount
    portion = _amount(raw.get("measured_portion_cny"))
    if portion is not None:
        projected["measured_portion_cny"] = portion
    if projected["status"] == UNKNOWN and amount is None and portion is None:
        projected["reason"] = ("cost_status_invalid" if raw.get("status") not in COST_STATUSES
                               else "no_cost_amount_recorded")
    elif status == ESTIMATED and amount is None:
        # The producer claimed an estimate but no usable amount survived ``_amount``; the
        # status is theirs to keep, so the absence is spelled out instead of left implicit.
        projected["reason"] = "no_cost_amount_recorded"
    return projected


def summarize_run_usage(row: Any) -> dict[str, Any]:
    """Project one persisted ``AgentRunRecord`` into a usage/cost summary."""
    metadata = _mapping(row.metadata_data)
    result = _mapping(metadata.get("result"))
    budget = _budget_of(metadata)
    input_tokens = _count(budget.get("actual_input_tokens"))
    output_tokens = _count(budget.get("actual_output_tokens"))
    unknown_calls = _count(budget.get("usage_unknown_calls"))
    measured = input_tokens is not None or output_tokens is not None
    if measured and unknown_calls:
        usage_status = PARTIAL
    elif measured:
        usage_status = MEASURED
    else:
        usage_status = UNKNOWN
    request = _mapping(metadata.get("request"))
    cost = _cost_of(budget)
    return {
        "run_id": row.id,
        "course_id": request.get("course_id"),
        "workflow_type": row.workflow_type,
        "run_status": row.status,
        "created_at": row.created_at,
        "duration_ms": _count(row.duration_ms),
        "reported_latency_ms": _number(result.get("latency_ms")),
        "model_calls": _count(budget.get("model_calls")),
        "tool_calls": _count(row.tool_calls),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "usage_unknown_calls": unknown_calls,
        "usage_status": usage_status,
        "cost_status": cost["status"],
        "cost_cny": cost.get("amount_cny"),
        "cost": cost,
        "budget_recorded": bool(budget),
    }


def aggregate_run_usage(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Total only over runs that carry real measurements, and count the rest."""
    with_tokens = [item for item in summaries
                   if item["input_tokens"] is not None or item["output_tokens"] is not None]
    estimated = [item["cost_cny"] for item in summaries
                 if item["cost_status"] == ESTIMATED and item["cost_cny"] is not None]
    return {
        "runs": len(summaries),
        "budget_recorded_runs": sum(1 for item in summaries if item["budget_recorded"]),
        "usage_status": {status: sum(1 for item in summaries if item["usage_status"] == status)
                        for status in USAGE_STATUSES},
        "cost_status": {status: sum(1 for item in summaries if item["cost_status"] == status)
                        for status in COST_STATUSES},
        "input_tokens": sum(item["input_tokens"] or 0 for item in with_tokens),
        "output_tokens": sum(item["output_tokens"] or 0 for item in with_tokens),
        "usage_unknown_calls": sum(item["usage_unknown_calls"] or 0 for item in summaries),
        "runs_without_token_data": len(summaries) - len(with_tokens),
        "cost_cny_estimated_sum": round(sum(estimated), 6),
        "runs_without_estimated_cost": len(summaries) - len(estimated),
        "note": ("Token and cost totals cover only runs with a recorded measurement; "
                 "unknown entries are counted separately and never treated as zero."),
    }
