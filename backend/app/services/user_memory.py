"""Confirmation-gated long-term memory for a single learner.

The model may only ``propose``: a proposal is an in-memory dict and never touches a
session. The one path that writes is ``confirm``, which demands an explicit human
actor, and every state change leaves a row in ``memory_events``. A run that did not
finish completely can never become memory, so a partial or failed delivery cannot
teach the system something wrong about a learner that survives the run itself.
"""
from __future__ import annotations

import math
import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from backend.app.core.models import AgentRunRecord, MemoryEventRecord, UserMemoryRecord

ACTIVE = "active"
REVOKED = "revoked"
MEMORY_STATUSES = (ACTIVE, REVOKED)

CONFIRMED = "confirmed"
SUPERSEDED = "superseded"
MEMORY_EVENT_ACTIONS = (CONFIRMED, SUPERSEDED, REVOKED)

# Lead's ruling is "user or teacher confirms"; anything else — including an agent
# principal — is refused rather than treated as an implicit human approval.
HUMAN_ACTOR_ROLES = ("student", "teacher")

# Only a fully delivered run may seed a memory. partially_completed, failed,
# awaiting_approval, reviewing, interrupted and rejected all stay out.
MEMORY_ELIGIBLE_RUN_STATUS = "completed"

_LIMITS = {"user_id": 128, "kind": 64, "source_type": 32, "source_run_id": 128,
           "actor": 128, "reason": 256}


class MemoryPolicyViolation(RuntimeError):
    """A write was refused by policy; the code is stable and carries no DB text."""


class MemoryPersistenceError(RuntimeError):
    """The memory store was unreachable, so nothing can be claimed about a write."""


def _now() -> float:
    return time.time()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryPolicyViolation(f"{field}_required")
    text = value.strip()
    if len(text) > _LIMITS[field]:
        raise MemoryPolicyViolation(f"{field}_too_long")
    return text


def _number(value: Any, *, lower: float, upper: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MemoryPolicyViolation("confidence_must_be_a_number")
    if not math.isfinite(value) or value < lower or value > upper:
        raise MemoryPolicyViolation("confidence_out_of_range")
    return float(value)


def _ttl(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MemoryPolicyViolation("ttl_must_be_a_number")
    if not math.isfinite(value) or value <= 0:
        raise MemoryPolicyViolation("ttl_must_be_positive")
    return float(value)


def _project(row: UserMemoryRecord) -> dict[str, Any]:
    moment = _now()
    return {
        "memory_id": row.id,
        "user_id": row.user_id,
        "kind": row.kind,
        "content": row.content,
        "source_type": row.source_type,
        "source_run_id": row.source_run_id,
        "confidence": row.confidence,
        "status": row.status,
        "expires_at": row.expires_at,
        "expired": row.expires_at is not None and row.expires_at <= moment,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "persisted": True,
    }


def _content(value: Any) -> str:
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        raise MemoryPolicyViolation("content_required")
    return text


def propose(*, user_id: str, kind: str, content: str, source_type: str = "rule_extraction",
            source_run_id: str | None = None, confidence: float | None = None,
            ttl_seconds: float | None = None) -> dict[str, Any]:
    """Shape a candidate memory. Nothing here reaches the database.

    ``expires_at`` is deliberately not frozen yet: an unconfirmed proposal can sit
    anywhere in the pipeline, so its TTL is measured from the moment a human confirms
    it, not from the moment it was drafted.
    """
    return {
        "proposal_id": str(uuid.uuid4()),
        "record": "proposed",
        "persisted": False,
        "user_id": _text(user_id, "user_id"),
        "kind": _text(kind, "kind"),
        "content": _content(content),
        "source_type": _text(source_type, "source_type"),
        "source_run_id": _text(source_run_id, "source_run_id") if source_run_id else None,
        "confidence": _number(confidence, lower=0.0, upper=1.0),
        "ttl_seconds": _ttl(ttl_seconds),
    }


def _check_source_run(session, source_run_id: str | None) -> None:
    if not source_run_id:
        return
    run = session.get(AgentRunRecord, source_run_id)
    if run is None:
        raise MemoryPolicyViolation("source_run_not_found")
    if run.status != MEMORY_ELIGIBLE_RUN_STATUS:
        raise MemoryPolicyViolation("source_run_not_completed")


def confirm(session_factory: Callable[[], Any], proposal: dict[str, Any], *,
            actor: str, actor_role: str) -> dict[str, Any]:
    """Persist a proposal as an active memory — only on an explicit human actor."""
    if not isinstance(proposal, dict) or proposal.get("record") != "proposed":
        raise MemoryPolicyViolation("confirmation_requires_a_proposal")
    actor_text = _text(actor, "actor")
    role = (actor_role or "").strip()
    if role not in HUMAN_ACTOR_ROLES:
        raise MemoryPolicyViolation("confirmation_requires_human_actor")

    now = _now()
    memory_id = str(uuid.uuid4())
    ttl = proposal.get("ttl_seconds")
    values = {
        "id": memory_id,
        "user_id": _text(proposal.get("user_id"), "user_id"),
        "kind": _text(proposal.get("kind"), "kind"),
        "content": _content(proposal.get("content")),
        "source_type": _text(proposal.get("source_type"), "source_type"),
        "source_run_id": proposal.get("source_run_id"),
        "confidence": proposal.get("confidence"),
        "status": ACTIVE,
        "expires_at": now + float(ttl) if ttl else None,
        "created_at": now,
        "updated_at": now,
    }

    try:
        with session_factory() as session:
            _check_source_run(session, values["source_run_id"])
            prior = session.scalars(select(UserMemoryRecord).where(
                UserMemoryRecord.user_id == values["user_id"],
                UserMemoryRecord.kind == values["kind"],
                UserMemoryRecord.status == ACTIVE,
                UserMemoryRecord.id != memory_id,
            ).with_for_update()).all()
            # One live memory per (user, kind): the older row is revoked in the same
            # transaction so the audit trail still shows what the system used to believe.
            for row in prior:
                stale = row.expires_at is not None and row.expires_at <= now
                row.status = REVOKED
                row.updated_at = now
                session.add(MemoryEventRecord(
                    memory_id=row.id, action=SUPERSEDED, actor=actor_text,
                    reason="ttl_expired" if stale else f"superseded_by:{memory_id}",
                    created_at=now))
            session.add(UserMemoryRecord(**values))
            session.add(MemoryEventRecord(memory_id=memory_id, action=CONFIRMED,
                                          actor=actor_text, reason=f"role:{role}",
                                          created_at=now))
            session.commit()
            return _project(session.get(UserMemoryRecord, memory_id))
    except MemoryPolicyViolation:
        raise
    except Exception as exc:
        raise MemoryPersistenceError("memory_persistence_unavailable") from exc


def revoke(session_factory: Callable[[], Any], memory_id: str, *,
           actor: str, actor_role: str, reason: str = "") -> dict[str, Any]:
    """Retire a memory while keeping both the row and its audit trail readable."""
    actor_text = _text(actor, "actor")
    role = (actor_role or "").strip()
    if role not in HUMAN_ACTOR_ROLES:
        raise MemoryPolicyViolation("revocation_requires_human_actor")
    memory_key = (memory_id or "").strip() if isinstance(memory_id, str) else ""
    if not memory_key:
        raise MemoryPolicyViolation("memory_id_required")
    note = (reason or "").strip()[:_LIMITS["reason"]]

    now = _now()
    try:
        with session_factory() as session:
            row = session.get(UserMemoryRecord, memory_key, with_for_update=True)
            if row is None:
                raise MemoryPolicyViolation("memory_not_found")
            if row.status != ACTIVE:
                # Already retired: no second event, so a re-played revoke cannot
                # inflate the audit trail.
                return {**_project(row), "changed": False}
            row.status = REVOKED
            row.updated_at = now
            session.add(MemoryEventRecord(memory_id=row.id, action=REVOKED,
                                          actor=actor_text, reason=note or f"role:{role}",
                                          created_at=now))
            session.commit()
            return {**_project(session.get(UserMemoryRecord, memory_key)), "changed": True}
    except MemoryPolicyViolation:
        raise
    except Exception as exc:
        raise MemoryPersistenceError("memory_persistence_unavailable") from exc


def active_memories(session_factory: Callable[[], Any], user_id: str, *,
                    kind: str | None = None,
                    now: float | None = None) -> list[dict[str, Any]]:
    """Readable memories for one learner: revoked and TTL-expired rows are excluded."""
    user = _text(user_id, "user_id")
    moment = _now() if now is None else float(now)
    try:
        with session_factory() as session:
            rows = session.scalars(select(UserMemoryRecord).where(
                UserMemoryRecord.user_id == user,
                UserMemoryRecord.status == ACTIVE,
                (UserMemoryRecord.expires_at.is_(None)
                 | (UserMemoryRecord.expires_at > moment)),
                *([UserMemoryRecord.kind == _text(kind, "kind")] if kind else []),
            ).order_by(UserMemoryRecord.created_at.desc(), UserMemoryRecord.id.desc())).all()
            return [_project(row) for row in rows]
    except MemoryPolicyViolation:
        raise
    except Exception as exc:
        raise MemoryPersistenceError("memory_persistence_unavailable") from exc


def memory_audit(session_factory: Callable[[], Any], memory_id: str) -> list[dict[str, Any]]:
    """Every recorded action on one memory, oldest first."""
    key = (memory_id or "").strip()
    if not key:
        raise MemoryPolicyViolation("memory_id_required")
    try:
        with session_factory() as session:
            rows = session.scalars(select(MemoryEventRecord)
                                   .where(MemoryEventRecord.memory_id == key)
                                   .order_by(MemoryEventRecord.id)).all()
            return [{"event_id": row.id, "memory_id": row.memory_id, "action": row.action,
                     "actor": row.actor, "reason": row.reason, "created_at": row.created_at}
                    for row in rows]
    except Exception as exc:
        raise MemoryPersistenceError("memory_persistence_unavailable") from exc
