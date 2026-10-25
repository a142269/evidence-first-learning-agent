"""Per-user and per-course quotas for V2 run creation (QWEN-324).

Three independently configurable sliding windows fence new runs created via
``POST /api/v2/learning-runs/stream`` and ``/enqueue``:

  * requests per user per minute  (counted at creation),
  * tokens per user+course per hour (accounted when a run settles, from the
    budget that ``usage_meter`` already wrote),
  * measured cost per user per day (CNY; only ``estimated`` amounts accrue).

Costs the provider never reported stay ``unknown``: they are counted as
unknown runs in the snapshot and verdict, never as a zero, and while any
unknown run is inside the window the cost dimension cannot claim an exceed
(it simply is not measurable yet).

Storage is the in-process sliding-window store below (thread-safe; the API is
a single FastAPI process).  Windows slide by entry: as soon as an entry is
older than its window it drops out, so "reset" is continuous.  Cross-process
consistency for multi-worker deployments is out of scope here (observation
surface, QWEN-341).  Over-limit creation gets a stable ``429 quota_exceeded``
with ``Retry-After``; everything else is untouched.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import logging
import math
import os
import threading
import time
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

REQUEST_WINDOW_SECONDS = 60
TOKEN_WINDOW_SECONDS = 3600
COST_WINDOW_SECONDS = 86400

# Baseline constants, documented in docs/CLAIMS_LEDGER.md §41.0 and
# overridable per deployment via environment variables.
DEFAULT_REQUESTS_PER_MINUTE = 60
DEFAULT_TOKENS_PER_HOUR = 500_000
DEFAULT_COST_CNY_PER_DAY = 5.0

_ERROR_CODE = "quota_exceeded"


def enabled() -> bool:
    """Quota fencing is opt-in (same spirit as the QWEN-321 runtime gate).

    ``QUOTA_ENABLED`` must be set truthy for the windows to apply; the default
    keeps every existing surface — demo and auth-required alike — untouched.
    """
    return os.getenv("QUOTA_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _positive_int(env_name: str, default: int) -> int:
    try:
        value = int(os.getenv(env_name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _positive_float(env_name: str, default: float) -> float:
    try:
        value = float(os.getenv(env_name, ""))
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


def limits() -> dict[str, int | float]:
    """Current limits, re-read on every check so deployments can retune live."""
    return {
        "requests_per_minute": _positive_int("QUOTA_REQUESTS_PER_MINUTE",
                                             DEFAULT_REQUESTS_PER_MINUTE),
        "tokens_per_hour": _positive_int("QUOTA_TOKENS_PER_HOUR", DEFAULT_TOKENS_PER_HOUR),
        "cost_cny_per_day": _positive_float("QUOTA_COST_CNY_PER_DAY", DEFAULT_COST_CNY_PER_DAY),
    }


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    dimension: str = ""  # "requests" | "tokens" | "cost" when refused
    scope: str = ""      # "user" | "user_course" when refused
    window_seconds: int = 0
    retry_after: int = 0
    verdict: dict[str, Any] = field(default_factory=dict)

    @property
    def error_code(self) -> str:
        return _ERROR_CODE


def _prune(entries: deque, window: int, now: float) -> None:
    while entries and now - entries[0][0] >= window:
        entries.popleft()


class QuotaStore:
    """Sliding-window counters; injectable clock keeps tests deterministic."""

    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._lock = threading.Lock()
        self._requests: dict[str, deque[tuple[float, int]]] = {}
        self._tokens: dict[tuple[str, str], deque[tuple[float, int]]] = {}
        self._costs: dict[str, deque[tuple[float, float | None]]] = {}

    def check_run_creation(self, user_id: str, course_id: str) -> QuotaDecision:
        now = self._clock()
        cap = limits()
        with self._lock:
            requests = self._requests.setdefault(user_id, deque())
            _prune(requests, REQUEST_WINDOW_SECONDS, now)
            tokens = self._tokens.setdefault((user_id, course_id), deque())
            _prune(tokens, TOKEN_WINDOW_SECONDS, now)
            costs = self._costs.setdefault(user_id, deque())
            _prune(costs, COST_WINDOW_SECONDS, now)

            used_requests = sum(count for _, count in requests)
            used_tokens = sum(count for _, count in tokens)
            amounts = [amount for _, amount in costs if amount is not None]
            unknown_runs = sum(1 for _, amount in costs if amount is None)
            verdict = {
                "requests": {"used": used_requests, "limit": cap["requests_per_minute"],
                             "window_seconds": REQUEST_WINDOW_SECONDS},
                "tokens": {"used": used_tokens, "limit": cap["tokens_per_hour"],
                           "window_seconds": TOKEN_WINDOW_SECONDS},
                "cost": {"measured_cny": round(sum(amounts), 6),
                         "limit_cny": cap["cost_cny_per_day"],
                         "unknown_runs": unknown_runs,
                         "status": ("unknown" if unknown_runs else "measurable"),
                         "window_seconds": COST_WINDOW_SECONDS},
            }

            if used_requests >= cap["requests_per_minute"]:
                return QuotaDecision(False, "requests", "user", REQUEST_WINDOW_SECONDS,
                                     REQUEST_WINDOW_SECONDS, verdict)
            if used_tokens >= cap["tokens_per_hour"]:
                return QuotaDecision(False, "tokens", "user_course", TOKEN_WINDOW_SECONDS,
                                     TOKEN_WINDOW_SECONDS, verdict)
            # Cost can only deny when every run in the window reported a usable
            # amount; unknown runs make the dimension unmeasurable, never zero.
            if amounts and not unknown_runs and sum(amounts) >= cap["cost_cny_per_day"]:
                return QuotaDecision(False, "cost", "user", COST_WINDOW_SECONDS,
                                     COST_WINDOW_SECONDS, verdict)

            requests.append((now, 1))
            verdict["requests"]["used"] += 1
            return QuotaDecision(True, verdict=verdict)

    def record_run_usage(self, user_id: str, course_id: str, *,
                         tokens: int = 0, cost_cny: float | None = None) -> None:
        """Account one settled run; ``cost_cny=None`` is an unknown, not a zero."""
        now = self._clock()
        with self._lock:
            if tokens > 0:
                self._tokens.setdefault((user_id, course_id), deque()).append((now, int(tokens)))
            self._costs.setdefault(user_id, deque()).append(
                (now, None if cost_cny is None else float(cost_cny)))

    def snapshot(self, user_id: str | None = None,
                 course_id: str | None = None) -> dict[str, Any]:
        """Read-only view of current window occupancy (metrics/log surface)."""
        now = self._clock()
        cap = limits()
        with self._lock:
            if user_id is None:
                return {
                    "users": len(self._requests),
                    "user_course_pairs": len(self._tokens),
                    "limits": cap,
                }
            requests = self._requests.get(user_id, deque())
            _prune(requests, REQUEST_WINDOW_SECONDS, now)
            used_requests = sum(count for _, count in requests)
            if course_id is None:
                used_tokens = sum(count for entries in self._tokens.values()
                                  for _, count in entries)
            else:
                tokens = self._tokens.get((user_id, course_id), deque())
                _prune(tokens, TOKEN_WINDOW_SECONDS, now)
                used_tokens = sum(count for _, count in tokens)
            costs = self._costs.get(user_id, deque())
            _prune(costs, COST_WINDOW_SECONDS, now)
            amounts = [amount for _, amount in costs if amount is not None]
            return {
                "user_id": user_id,
                "requests": {"used": used_requests, "limit": cap["requests_per_minute"],
                             "window_seconds": REQUEST_WINDOW_SECONDS},
                "tokens": {"used": used_tokens, "limit": cap["tokens_per_hour"],
                           "window_seconds": TOKEN_WINDOW_SECONDS},
                "cost": {"measured_cny": round(sum(amounts), 6),
                         "limit_cny": cap["cost_cny_per_day"],
                         "unknown_runs": sum(1 for _, amount in costs if amount is None),
                         "window_seconds": COST_WINDOW_SECONDS},
            }


_STORE = QuotaStore()


def check_run_creation(user_id: str, course_id: str) -> QuotaDecision:
    if not enabled():
        return QuotaDecision(True, verdict={"disabled": True})
    return _STORE.check_run_creation(user_id, course_id)


def record_run_usage(user_id: str, course_id: str, *,
                     tokens: int = 0, cost_cny: float | None = None) -> None:
    if not enabled():
        return
    _STORE.record_run_usage(user_id, course_id, tokens=tokens, cost_cny=cost_cny)


def record_from_budget(user_id: str, course_id: str, budget: dict[str, Any] | None) -> None:
    """Project one settled run's ``result.budget`` into the windows.

    Token counts that the provider never returned are simply absent (never a
    zero fill-in); a cost that is not a finite ``estimated`` amount records as
    unknown so the cost dimension stays honest.
    """
    if not isinstance(budget, dict):
        budget = {}
    tokens = 0
    for key in ("actual_input_tokens", "actual_output_tokens"):
        value = budget.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            tokens += value
    cost = budget.get("cost")
    cost_cny = None
    if isinstance(cost, dict) and cost.get("status") == "estimated":
        amount = cost.get("amount_cny")
        if isinstance(amount, (int, float)) and not isinstance(amount, bool) \
                and math.isfinite(amount) and amount >= 0:
            cost_cny = float(amount)
    record_run_usage(user_id, course_id, tokens=tokens, cost_cny=cost_cny)


def snapshot(user_id: str | None = None, course_id: str | None = None) -> dict[str, Any]:
    return _STORE.snapshot(user_id=user_id, course_id=course_id)


def emit_startup_warning() -> None:
    """One line at startup when fencing is off — no secrets, no config values."""
    if not enabled():
        LOGGER.warning(
            "Quota fencing is disabled: per-user request/token/cost limits are "
            "inactive. Set QUOTA_ENABLED=true to enable (recommended for "
            "production deployments)."
        )
