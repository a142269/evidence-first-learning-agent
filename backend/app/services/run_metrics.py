"""Run-level metrics for QWEN-341 (metrics & alerting).

A thin recording layer over ``backend.app.core.telemetry`` covering:

  * settled run outcomes and mode          → ``learning_runs_total{mode,status}``
  * end-to-end run latency                 → ``learning_run_duration_seconds{mode}``
  * classified failures                    → ``learning_run_errors_total{code}``
  * tool invocations                       → ``learning_tool_calls_total{tool,status}``
  * queue claims / pending depth           → ``queue_claimed_total`` /
                                             ``learning_queue_pending_runs``
  * per-run measured cost or unknown       → ``run_cost_yuan_total{mode}`` /
                                             ``run_cost_unknown_runs_total{mode}``
  * quota refusals                         → ``quota_rejected_total{dimension}``

Everything is exposed through the existing ``/metrics`` endpoint (Prometheus
text exposition, privileged-role-only in production).  Costs the provider
never reported stay unknown — counted, never zero-filled (same contract as
the QWEN-324 quota windows).

Recording is fire-and-forget: a metrics failure must never break run
delivery, so every recorder swallows unexpected shapes.
"""
from __future__ import annotations

import math
from typing import Any

from backend.app.core.telemetry import get_telemetry

# Package runs are allowed up to 180 s (run_worker.PACKAGE_TIMEOUT_SECONDS);
# buckets cover the answer path and overflow into the head buckets.
_RUN_BUCKETS = (0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 180.0, 300.0)


def _measured_cost_cny(budget: Any) -> float | None:
    """Finite ``estimated`` CNY amount from a run budget; anything else is unknown."""
    cost = budget.get("cost") if isinstance(budget, dict) else None
    if not isinstance(cost, dict) or cost.get("status") != "estimated":
        return None
    amount = cost.get("amount_cny")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None
    amount = float(amount)
    return amount if math.isfinite(amount) and amount >= 0 else None


def record_settled(record: Any) -> None:
    """One settled run outcome (completed / partially_completed / rejected).

    Called from the shared ``apply_settled_state`` delivery contract, so both
    the streaming path and the queue worker settle exactly once here.
    ``awaiting_approval`` runs are not settled yet and are not counted.
    """
    try:
        reg = get_telemetry()
        mode = getattr(getattr(record, "request", None), "mode", "") or "unknown"
        status = getattr(record, "status", "") or "unknown"
        reg.counter("learning_runs_total").inc(mode=mode, status=status)
        result = getattr(record, "result", None)
        latency_ms = result.get("latency_ms") if isinstance(result, dict) else None
        if isinstance(latency_ms, (int, float)) and not isinstance(latency_ms, bool) \
                and latency_ms >= 0:
            reg.histogram("learning_run_duration_seconds", buckets=_RUN_BUCKETS).observe(
                latency_ms / 1000.0, mode=mode)
        budget = result.get("budget") if isinstance(result, dict) else None
        cost = _measured_cost_cny(budget)
        if cost is None:
            reg.counter("run_cost_unknown_runs_total").inc(mode=mode)
        else:
            reg.counter("run_cost_yuan_total").inc(cost, mode=mode)
    except Exception:  # pragma: no cover - metrics must never break delivery
        pass


def record_error(code: str) -> None:
    """One classified run failure (stable error code, never exception text)."""
    try:
        get_telemetry().counter("learning_run_errors_total").inc(code=code or "unknown")
    except Exception:  # pragma: no cover
        pass


def record_tool_call(name: str, status: str) -> None:
    """One V2 learning-tool invocation outcome."""
    try:
        get_telemetry().counter("learning_tool_calls_total").inc(
            tool=name or "unknown", status=status or "unknown")
    except Exception:  # pragma: no cover
        pass


def record_queue_claim() -> None:
    """One successful queue claim by a worker."""
    try:
        get_telemetry().counter("queue_claimed_total").inc()
    except Exception:  # pragma: no cover
        pass


def set_queue_pending(count: int) -> None:
    """Queue-origin queued runs seen in the latest claim scan (scan-window cap)."""
    try:
        get_telemetry().gauge("learning_queue_pending_runs").set(max(0, int(count)))
    except Exception:  # pragma: no cover
        pass


def record_quota_rejection(dimension: str) -> None:
    """One run creation refused by a quota dimension (requests/tokens/cost)."""
    try:
        get_telemetry().counter("quota_rejected_total").inc(dimension=dimension or "unknown")
    except Exception:  # pragma: no cover
        pass
