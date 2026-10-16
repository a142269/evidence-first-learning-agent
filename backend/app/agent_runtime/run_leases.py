"""Database-clock execution leases and fenced writes for V2 runs.

Expired executions cannot publish Run results or audit events. This does not
promise exactly-once model calls or a transaction spanning LangGraph storage.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Float, cast, func, select, update

from backend.app.core.models import AgentCheckpointRecord, AgentRunRecord

LEASE_SECONDS = 45
HEARTBEAT_SECONDS = 10
ACTIVE = ("running", "reviewing")


def db_now(session):
    if session.get_bind().dialect.name == "postgresql":
        return func.extract("epoch", func.clock_timestamp())
    return cast(func.strftime("%s", "now"), Float)


def fence(session, run_id: str, execution_id: str, *, renew=False):
    """Lock/check ownership in the same transaction as the caller's write."""
    from backend.app.agent_runtime.run_audit import RunStateConflict

    if not execution_id:
        return  # Legacy non-V2 callers do not use leases.
    now = db_now(session)
    expiry = now + LEASE_SECONDS if renew else AgentRunRecord.lease_expires_at
    changed = session.execute(update(AgentRunRecord).where(
        AgentRunRecord.id == run_id, AgentRunRecord.execution_id == execution_id,
        AgentRunRecord.status.in_(ACTIVE), AgentRunRecord.lease_expires_at > now,
    ).values(lease_expires_at=expiry).execution_options(synchronize_session=False)).rowcount
    if changed != 1:
        raise RunStateConflict("execution_lease_lost")


def renew(run_id: str, execution_id: str):
    from backend.app.agent_runtime import run_audit
    run_audit._safe_write(lambda session: fence(session, run_id, execution_id, renew=True))


def claim_continuation(run_id: str, previous_execution_id: str, execution_id: str) -> bool:
    """Atomically assign a new lease to one failed/interrupted execution."""
    from backend.app.agent_runtime import run_audit

    claimed = False

    def write(session):
        nonlocal claimed
        changed = session.execute(update(AgentRunRecord).where(
            AgentRunRecord.id == run_id,
            AgentRunRecord.execution_id == previous_execution_id,
            AgentRunRecord.status.in_(("failed", "interrupted")),
        ).values(status="running", execution_id=execution_id,
                 lease_expires_at=db_now(session) + LEASE_SECONDS)
            .execution_options(synchronize_session=False)).rowcount
        if changed != 1:
            return
        claimed = True
        sequence = run_audit._next_event_sequence(session, run_id)
        session.add(AgentCheckpointRecord(id=str(uuid.uuid4()), run_id=run_id,
            thread_id=run_id, node_name="lifecycle", status="run.continued",
            sequence=sequence, state_data={}))

    run_audit._safe_write(write)
    return claimed


def expire(run_id: str) -> bool:
    """Retire an expired execution; never restart graph/model work."""
    from backend.app.agent_runtime import run_audit
    expired = False

    def write(session):
        nonlocal expired
        row = session.get(AgentRunRecord, run_id)
        if row is None:
            return
        changed = session.execute(update(AgentRunRecord).where(
            AgentRunRecord.id == run_id, AgentRunRecord.status.in_(ACTIVE),
            AgentRunRecord.execution_id == row.execution_id,
            AgentRunRecord.lease_expires_at <= db_now(session),
        ).values(status="interrupted", lease_expires_at=None,
                 metadata_data={**(row.metadata_data or {}), "result": {"error": "execution_lease_expired"}})
            .execution_options(synchronize_session=False)).rowcount
        if changed:
            expired = True
            sequence = run_audit._next_event_sequence(session, run_id)
            session.add(AgentCheckpointRecord(id=str(uuid.uuid4()), run_id=run_id,
                thread_id=run_id, node_name="lease", status="run.lease_expired",
                sequence=sequence, state_data={}))

    run_audit._safe_write(write)
    return expired


def expire_batch(limit=1000) -> int:
    """Bounded startup sweep. Remaining runs may be retired by explicit reconcile."""
    from backend.app.agent_runtime import run_audit
    try:
        with run_audit.SessionLocal() as session:
            ids = list(session.scalars(select(AgentRunRecord.id).where(
                AgentRunRecord.status.in_(ACTIVE), AgentRunRecord.lease_expires_at <= db_now(session),
            ).order_by(AgentRunRecord.lease_expires_at).limit(limit)))
        return sum(expire(run_id) for run_id in ids)
    except run_audit.RunPersistenceError:
        raise
    except Exception as exc:
        raise run_audit.RunPersistenceError("run_persistence_unavailable") from exc
