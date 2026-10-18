"""Durable lifecycle records for evidence-first learning runs."""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import logging
import time
from typing import Any
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.core.models import AgentCheckpointRecord, AgentRunRecord, RetrievalLogRecord
from backend.app.agent_runtime import run_leases

LOGGER = logging.getLogger(__name__)


class RunPersistenceError(RuntimeError):
    """A required lifecycle write failed; never expose database exception text."""


class RunStateConflict(RuntimeError):
    """Another writer changed the lifecycle state before reconciliation committed."""


def _safe_write(callback: Callable[[Session], None]) -> None:
    try:
        with SessionLocal() as session:
            callback(session)
            session.commit()
    except RunStateConflict:
        raise
    except Exception as exc:
        LOGGER.error("Learning-run persistence failed (%s)", type(exc).__name__)
        raise RunPersistenceError("run_persistence_unavailable") from exc


def _next_event_sequence(session: Session, run_id: str) -> int:
    row = session.get(AgentRunRecord, run_id, with_for_update=True)
    if row is None:
        raise RunPersistenceError("run_not_found")
    row.event_sequence = (row.event_sequence or 0) + 1
    return row.event_sequence


def start_run(
    *,
    run_id: str,
    session_id: str,
    user_id: str,
    metadata: dict[str, Any] | None = None,
    execution_id: str = "",
    idempotency_digest: str | None = None,
    request_fingerprint: str | None = None,
) -> None:
    def write(session: Session) -> None:
        package = (metadata or {}).get("request", {}).get("mode") == "learning_package"
        session.add(
            AgentRunRecord(
                id=run_id,
                session_id=session_id,
                user_id=user_id,
                workflow_type="learning_package" if package else "evidence_first_learning",
                agents=["planner", "tutor", "practice", "reviewer"] if package else ["retrieval", "tutor", "citation_review"],
                status="running",
                execution_id=execution_id or None,
                event_sequence=1,
                idempotency_digest=idempotency_digest,
                request_fingerprint=request_fingerprint,
                lease_expires_at=run_leases.db_now(session) + run_leases.LEASE_SECONDS if execution_id else None,
                metadata_data=metadata or {},
            )
        )
        session.add(AgentCheckpointRecord(
            id=str(uuid.uuid4()), run_id=run_id, thread_id=run_id,
            node_name="started", status="run.started", sequence=1,
        ))

    _safe_write(write)


def find_idempotent_run(user_id: str, digest: str) -> tuple[str, str] | None:
    try:
        with SessionLocal() as session:
            row = session.scalars(select(AgentRunRecord).where(
                AgentRunRecord.user_id == user_id,
                AgentRunRecord.idempotency_digest == digest,
            ).limit(1)).first()
            return (row.id, row.request_fingerprint or "") if row else None
    except Exception as exc:
        raise RunPersistenceError("run_persistence_unavailable") from exc


def checkpoint(*, run_id: str, thread_id: str, node_name: str, status: str,
               state_data: dict[str, Any] | None = None, execution_id: str = "") -> int:
    sequence = 0
    def write(session: Session) -> None:
        nonlocal sequence
        run_leases.fence(session, run_id, execution_id)
        sequence = _next_event_sequence(session, run_id)
        session.add(
            AgentCheckpointRecord(
                id=str(uuid.uuid4()),
                run_id=run_id,
                thread_id=thread_id[:128],
                node_name=node_name,
                status=status,
                sequence=sequence,
                state_data=state_data or {},
            )
        )

    _safe_write(write)
    return sequence


def log_retrieval(
    *, run_id: str, query: str, evidence: list[dict[str, Any]], latency_ms: int, execution_id: str = ""
) -> None:
    def write(session: Session) -> None:
        run_leases.fence(session, run_id, execution_id)
        session.add(
            RetrievalLogRecord(
                id=str(uuid.uuid4()),
                run_id=run_id,
                query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
                evidence=evidence,
                latency_ms=latency_ms,
            )
        )

    _safe_write(write)


def finish_run(*, run_id: str, status: str, result: dict[str, Any], started_at: float,
               expected_status: str | None = None, execution_id: str = "") -> int:
    duration_ms = int((time.time() - started_at) * 1000)
    sequence = 0

    def write(session: Session) -> None:
        nonlocal sequence
        run_leases.fence(session, run_id, execution_id)
        record = session.get(AgentRunRecord, run_id)
        if record is None:
            raise RunPersistenceError("run_not_found")
        output = result.get("result", {})
        package = output.get("learning_package") or {}
        values = dict(status=status, duration_ms=duration_ms,
                      # Only a full delivery counts as success; partially_completed
                      # is recorded as its own status and kept out of this counter.
                      success_count=int(status == "completed"),
                      lease_expires_at=None,
                      metadata_data={**(record.metadata_data or {}), **result},
                      tool_calls=int(output.get("budget", {}).get("tool_calls", 0)),
                      artifact_count=int(bool(package.get("lesson"))) + int(bool(package.get("exercises"))))
        if expected_status is None:
            for key, value in values.items():
                setattr(record, key, value)
        else:
            from sqlalchemy import update
            changed = session.execute(update(AgentRunRecord)
                .where(AgentRunRecord.id == run_id, AgentRunRecord.status == expected_status)
                .values(**values).execution_options(synchronize_session=False)).rowcount
            if changed != 1:
                raise RunStateConflict("run_state_changed")
            # Lifecycle update and recovery audit commit in the same transaction.
            session.add(AgentCheckpointRecord(
                id=str(uuid.uuid4()), run_id=run_id, thread_id=run_id,
                node_name="reconcile", status="run.reconciled",
                state_data={"from_status": expected_status, "to_status": status},
            ))

        sequence = _next_event_sequence(session, run_id)
        terminal_event = {"completed": "run.completed", "partially_completed": "run.completed",
                          "awaiting_approval": "review.required",
                          "failed": "run.failed", "interrupted": "run.interrupted",
                          "rejected": "run.completed"}.get(status, "run.status_changed")
        session.add(AgentCheckpointRecord(
            id=str(uuid.uuid4()), run_id=run_id, thread_id=run_id,
            node_name="lifecycle", status=terminal_event, sequence=sequence,
            state_data={"status": status},
        ))

    _safe_write(write)
    return sequence


def claim_review(run_id: str, execution_id: str = "") -> bool:
    """Atomically claim a pending review across processes, not just one cache."""
    from sqlalchemy import update

    try:
        with SessionLocal() as session:
            changed = session.execute(
                update(AgentRunRecord)
                .where(AgentRunRecord.id == run_id, AgentRunRecord.status == "awaiting_approval")
                .values(status="reviewing", execution_id=execution_id or uuid.uuid4().hex,
                        lease_expires_at=run_leases.db_now(session) + run_leases.LEASE_SECONDS)
            ).rowcount
            session.commit()
            return changed == 1
    except Exception as exc:
        raise RunPersistenceError("run_persistence_unavailable") from exc
