"""Persistent run queue and worker leases for QWEN-301 (create/execute decoupling).

The queue is a state machine on the existing ``agent_runs`` row - no new table
or column:

    queued ──claim──▶ running ──finish──▶ completed / partially_completed /
                                          awaiting_approval / failed
    queued ──cancel──▶ cancelled
    running ──cancel──▶ cancelled (execution_id rotated so the old worker is
                                  fenced off by run_leases.fence)
    running/interrupted with an expired lease ──claim──▶ running (at-least-once;
                                  attempts bounded by MAX_ATTEMPTS)

Claims are single conditional UPDATEs (the run_leases pattern), so two workers
can never both win the same run on SQLite or PostgreSQL.  Delivery is
at-least-once: after a worker crash another worker re-claims the expired
execution, and the dead worker's fenced writes fail with RunStateConflict.
Exactly-once is NOT claimed or implemented.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.app.agent_runtime import run_audit, run_leases
from backend.app.core.models import AgentCheckpointRecord, AgentRunRecord
from backend.app.services import run_metrics

# Baseline constants; final values are up to the Lead.
MAX_ATTEMPTS = 2
# A run whose claim attempts are exhausted fails with this stable queue-only code.
ATTEMPTS_EXHAUSTED = "run_queue_attempts_exhausted"
QUEUE_STATUSES = ("queued", "running", "interrupted")


def _safe_write_retrying(callback, *, attempts: int = 3) -> None:
    """Run one queued write, retrying SQLite event-sequence races.

    On SQLite ``SELECT ... FOR UPDATE`` does not lock rows, so a concurrent
    writer on the same run (a canceller, or a zombie worker's last checkpoint)
    can take the same checkpoint sequence; the loser hits the unique
    ``(run_id, sequence)`` index.  Retrying re-reads the run and re-allocates
    the sequence.  PostgreSQL locks the run row in ``_next_event_sequence``
    and does not need the retry.
    """
    last: BaseException | None = None
    for _ in range(attempts):
        try:
            run_audit._safe_write(callback)
            return
        except run_audit.RunPersistenceError as exc:
            if not isinstance(exc.__cause__, IntegrityError):
                raise
            last = exc
    raise run_audit.RunPersistenceError("run_persistence_unavailable") from last


def _queue_meta(row: AgentRunRecord) -> dict[str, Any]:
    metadata = dict(row.metadata_data or {})
    metadata["queue"] = dict(metadata.get("queue") or {})
    return metadata


def _retire_exhausted(session, run_id: str, execution_id: str, worker_id: str,
                      metadata: dict[str, Any]) -> None:
    """Fail a run whose attempts were exhausted, inside the claim transaction."""
    metadata["queue"].update({"retired_by": worker_id})
    metadata["result"] = {"error": ATTEMPTS_EXHAUSTED}
    sequence = run_audit._next_event_sequence(session, run_id)
    session.execute(update(AgentRunRecord).where(AgentRunRecord.id == run_id).values(
        status="failed", execution_id=execution_id, lease_expires_at=None,
        metadata_data=metadata,
    ).execution_options(synchronize_session=False))
    session.add(AgentCheckpointRecord(
        id=str(uuid.uuid4()), run_id=run_id, thread_id=run_id,
        node_name="queue", status="run.queue_exhausted", sequence=sequence,
        state_data={"attempts": metadata["queue"].get("attempts", 0)},
    ))


def claim_next_run(worker_id: str = "", *, limit: int = 5) -> dict[str, Any] | None:
    """Atomically claim the next runnable queue entry for one worker.

    Returns ``{"run_id", "execution_id", "attempts"}`` or ``None`` when the
    queue has nothing runnable.  Candidates are queued runs and previously
    claimed runs whose lease expired (crashed workers); the winner is decided
    by a single conditional UPDATE per candidate, so concurrent workers never
    double-claim.  A claim past ``MAX_ATTEMPTS`` retires the run as failed
    instead of executing it again.
    """
    claimed: dict[str, Any] | None = None

    def write(session) -> None:
        nonlocal claimed
        # One authoritative DB-clock value for both Python-side candidate
        # checks and the SQL claim conditions.
        now = session.scalar(select(run_leases.db_now(session)))
        rows = session.execute(select(AgentRunRecord).where(
            AgentRunRecord.status.in_(QUEUE_STATUSES),
        ).order_by(AgentRunRecord.created_at, AgentRunRecord.id).limit(limit * 3)).all()
        # QWEN-341: pending-depth gauge from the same scan (scan-window cap).
        run_metrics.set_queue_pending(sum(
            1 for (row,) in rows
            if row.status == "queued" and (row.metadata_data or {}).get("queue", {}).get("enqueued_at")
        ))
        for (row,) in rows:
            # Only runs created through the queue endpoint are claimable; a
            # legacy interrupted run keeps its /continue + reconcile semantics.
            if not (row.metadata_data or {}).get("queue", {}).get("enqueued_at"):
                continue
            expired = (row.status != "queued"
                       and (row.lease_expires_at is None or row.lease_expires_at <= now))
            if row.status == "queued" or expired:
                execution_id = uuid.uuid4().hex
                conditions = [AgentRunRecord.id == row.id]
                if row.status == "running":
                    # Never steal a live lease; the candidate list may be stale.
                    conditions.append(AgentRunRecord.lease_expires_at <= now)
                else:
                    conditions.append(AgentRunRecord.status == row.status)
                changed = session.execute(update(AgentRunRecord).where(*conditions).values(
                    status="running", execution_id=execution_id,
                    lease_expires_at=now + run_leases.LEASE_SECONDS,
                ).execution_options(synchronize_session=False)).rowcount
                if changed != 1:
                    continue  # Lost the race; try the next candidate.
                session.expire(row)
                metadata = _queue_meta(row)
                attempts = int(metadata["queue"].get("attempts", 0)) + 1
                metadata["queue"].update({"attempts": attempts, "worker_id": worker_id,
                                          "claimed_at": time.time()})
                session.execute(update(AgentRunRecord).where(
                    AgentRunRecord.id == row.id).values(metadata_data=metadata)
                    .execution_options(synchronize_session=False))
                if attempts > MAX_ATTEMPTS:
                    _retire_exhausted(session, row.id, execution_id, worker_id, metadata)
                    continue
                sequence = run_audit._next_event_sequence(session, row.id)
                session.add(AgentCheckpointRecord(
                    id=str(uuid.uuid4()), run_id=row.id, thread_id=row.id,
                    node_name="queue", status="run.claimed", sequence=sequence,
                    state_data={"attempts": attempts, "worker_id": worker_id},
                ))
                claimed = {"run_id": row.id, "execution_id": execution_id,
                           "attempts": attempts}
                run_metrics.record_queue_claim()
                return

    _safe_write_retrying(write)
    return claimed


def is_queued_run(metadata: dict[str, Any] | None) -> bool:
    """True when the run was created through the queue endpoint."""
    return bool((metadata or {}).get("queue", {}).get("enqueued_at"))


def queue_origin(run_id: str) -> bool:
    """DB-side queue-origin check for API endpoints (RunRecord has no metadata)."""
    try:
        with run_audit.SessionLocal() as session:
            row = session.get(AgentRunRecord, run_id)
            return row is not None and is_queued_run(row.metadata_data)
    except Exception as exc:
        raise run_audit.RunPersistenceError("run_persistence_unavailable") from exc


def cancel_run(run_id: str) -> bool:
    """Cancel a queued or actively running run; terminal runs return False.

    For a running execution the cancellation rotates ``execution_id`` and
    clears the lease in the same atomic UPDATE, so the executing worker's next
    fenced write (heartbeat or result) fails with RunStateConflict and the
    cancelled status survives.  Exactly one concurrent canceller wins.
    """
    cancelled = False

    def write(session) -> None:
        nonlocal cancelled
        row = session.get(AgentRunRecord, run_id)
        if row is None or row.status not in {"queued", "running"}:
            return
        conditions = [AgentRunRecord.id == run_id, AgentRunRecord.status == row.status]
        if row.status == "running":
            # Only cancel while the row is still the one we observed.
            conditions.append(AgentRunRecord.execution_id == row.execution_id)
        changed = session.execute(update(AgentRunRecord).where(*conditions).values(
            status="cancelled", execution_id="cancelled-" + uuid.uuid4().hex,
            lease_expires_at=None,
            metadata_data={**(row.metadata_data or {}), "result": {"cancelled": True}},
        ).execution_options(synchronize_session=False)).rowcount
        if changed != 1:
            return
        cancelled = True
        sequence = run_audit._next_event_sequence(session, run_id)
        session.add(AgentCheckpointRecord(
            id=str(uuid.uuid4()), run_id=run_id, thread_id=run_id,
            node_name="queue", status="run.cancelled", sequence=sequence,
            state_data={"from_status": row.status},
        ))

    _safe_write_retrying(write)
    return cancelled
