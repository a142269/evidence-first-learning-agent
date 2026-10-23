"""Bounded, idempotent cross-session summary over confirmed learner memories.

``build_summary`` is pure: it takes already-read memories plus their source-run statuses
and returns a dict, so no path through it can reach a session write.
``cross_session_summary`` opens a session only to read — a summary must never become a
memory that then summarises itself.
"""
from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from backend.app.core.models import AgentRunRecord
from backend.app.services.user_memory import (
    MEMORY_ELIGIBLE_RUN_STATUS,
    MemoryPersistenceError,
    MemoryPolicyViolation,
    active_memories,
)

SUMMARY_STATUS = "summary"
EMPTY_STATUS = "empty"

DEFAULT_WINDOW = 3
MAX_WINDOW = 20
MAX_TOKENS_PER_MEMORY = 80
DEFAULT_TOKEN_BUDGET = 600
MAX_CHARS_PER_MEMORY = 320

# tiktoken is not a dependency here, so the budget is an offline heuristic: one token per
# CJK character, roughly four Latin characters per token. It gates length only and is never
# presented as a billing figure.
_CJK_RANGES = ((0x3000, 0x303F), (0x3400, 0x4DBF), (0x4E00, 0x9FFF),
               (0xF900, 0xFAFF), (0xFF00, 0xFF65))

_ELLIPSIS = "…"


def _is_cjk(ch: str) -> bool:
    return any(low <= ord(ch) <= high for low, high in _CJK_RANGES)


def estimate_tokens(text: str) -> int:
    """Deterministic offline token estimate used only to enforce the budget."""
    cjk = sum(1 for ch in text if _is_cjk(ch))
    return cjk + -(-(len(text) - cjk) // 4)


def _clip_to_tokens(text: str, cap: int) -> str:
    """Longest clipped prefix whose own estimate fits the cap; monotone in length."""
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(text[:middle] + _ELLIPSIS) <= cap:
            low = middle
        else:
            high = middle - 1
    return text[:low] + _ELLIPSIS


def _positive_int(value: Any, field: str, *, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise MemoryPolicyViolation(f"{field}_must_be_positive")
    if value > upper:
        raise MemoryPolicyViolation(f"{field}_too_large")
    return value


def _digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _shape(user: str, status: str, reason: str, *, summary: str, sections: list,
           skipped: list, window: int, token_budget: int, tokens: int,
           now: float) -> dict[str, Any]:
    return {"user_id": user, "status": status, "reason": reason, "summary": summary,
            "sections": sections,
            "used_memory_ids": [section["memory_id"] for section in sections],
            "skipped": skipped, "memory_count": len(sections), "window": window,
            "token_budget": token_budget, "estimated_tokens": tokens,
            "truncated": bool(skipped) or any(section["truncated"] for section in sections),
            "generated_at": now,
            "summary_sha256": _digest([line for line in summary.split("\n") if line]),
            "persisted": False}


def _fit(content: str) -> tuple[str, int, bool]:
    text = content[:MAX_CHARS_PER_MEMORY]
    clipped = len(text) < len(content)
    if estimate_tokens(text) > MAX_TOKENS_PER_MEMORY:
        text = _clip_to_tokens(text, MAX_TOKENS_PER_MEMORY)
        clipped = True
    return text, estimate_tokens(text), clipped


def build_summary(user_id: str, memories: list[dict[str, Any]],
                  run_statuses: dict[str, str | None], *,
                  window: int = DEFAULT_WINDOW,
                  token_budget: int = DEFAULT_TOKEN_BUDGET,
                  now: float | None = None) -> dict[str, Any]:
    """Fold readable memories into one bounded summary. Pure: no session, no model."""
    user = (user_id or "").strip() if isinstance(user_id, str) else ""
    if not user:
        raise MemoryPolicyViolation("user_id_required")
    window = _positive_int(window, "window", upper=MAX_WINDOW)
    token_budget = _positive_int(token_budget, "token_budget", upper=100_000)
    moment = time.time() if now is None else float(now)

    sections: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    used_tokens = 0

    for memory in memories[:window]:
        memory_id = str(memory.get("memory_id") or "")
        content = memory.get("content")
        if not isinstance(content, str) or not content.strip():
            skipped.append({"memory_id": memory_id, "reason": "content_missing"})
            continue
        run_id = memory.get("source_run_id")
        status = run_statuses.get(str(run_id)) if run_id else MEMORY_ELIGIBLE_RUN_STATUS
        # A memory with no provenance run was authored by hand, so there is no run to
        # re-check; anything sourced from a run must still be a completed one.
        if status != MEMORY_ELIGIBLE_RUN_STATUS:
            skipped.append({"memory_id": memory_id,
                            "reason": f"source_run_not_completed:{status}"})
            continue
        text, cost, clipped = _fit(content.strip())
        if used_tokens + cost > token_budget:
            skipped.append({"memory_id": memory_id, "reason": "token_budget"})
            continue
        used_tokens += cost
        sections.append({"kind": memory.get("kind"), "memory_id": memory_id, "text": text,
                         "source_run_id": run_id, "estimated_tokens": cost,
                         "truncated": clipped})

    skipped.extend({"memory_id": str(item.get("memory_id") or ""), "reason": "outside_window"}
                   for item in memories[window:])

    if not sections:
        reason = "no_active_memory" if not memories else "no_memory_fit_budget"
        return _shape(user, EMPTY_STATUS, reason, summary="", sections=[], skipped=skipped,
                      window=window, token_budget=token_budget, tokens=0, now=moment)

    lines = [f"- {section['kind']}：{section['text']}" for section in sections]
    return _shape(user, SUMMARY_STATUS, "ok", summary="\n".join(lines), sections=sections,
                  skipped=skipped, window=window, token_budget=token_budget,
                  tokens=used_tokens, now=moment)


def cross_session_summary(session_factory: Callable[[], Any], user_id: str, *,
                          kind: str | None = None,
                          window: int = DEFAULT_WINDOW,
                          token_budget: int = DEFAULT_TOKEN_BUDGET,
                          now: float | None = None) -> dict[str, Any]:
    """Read the readable memories, then build the summary. This session is only queried.

    One instant is taken for the whole call: the TTL filter and the reported
    ``generated_at`` must not disagree about when the read happened.
    """
    moment = time.time() if now is None else float(now)
    memories = active_memories(session_factory, user_id, kind=kind, now=moment)
    run_ids = {str(item["source_run_id"]) for item in memories if item.get("source_run_id")}
    statuses: dict[str, str | None] = {}
    if run_ids:
        try:
            with session_factory() as session:
                for run_id, status in session.execute(
                        select(AgentRunRecord.id, AgentRunRecord.status)
                        .where(AgentRunRecord.id.in_(run_ids))).all():
                    statuses[run_id] = status
        except Exception as exc:
            # Same stable code as a failed memory read: a caller must never be able to
            # tell which of the two reads broke, and never sees DB text.
            raise MemoryPersistenceError("memory_persistence_unavailable") from exc
    return build_summary(user_id, memories, statuses, window=window,
                         token_budget=token_budget, now=moment)
