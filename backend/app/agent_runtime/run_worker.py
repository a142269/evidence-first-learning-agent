"""Queue worker: claim one run, execute it with the production graph, settle it.

QWEN-301.  The worker reuses the exact runtime the API uses
(``learning_runs._graph`` / ``_package_graph``), the same lease heartbeat as
the streaming path (``run_leases.renew``), the same retrieval audit
(``run_audit.log_retrieval``) and the same delivery contract
(``run_lifecycle.apply_settled_state``).  Terminal writes are fenced by the
claim's ``execution_id`` and guarded on ``status == 'running'`` so a cancelled
or re-claimed run is never clobbered.

Execution semantics are at-least-once: a worker that dies mid-run leaves an
expired lease which another worker re-claims; no exactly-once claim is made.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Callable

from backend.app.agent_runtime import run_audit, run_leases, run_queue
from backend.app.agent_runtime.learning_package import PackageFailure
from backend.app.api.v2 import run_lifecycle
from backend.app.core.models import AgentCheckpointRecord, AgentRunRecord

LOGGER = logging.getLogger(__name__)
ANSWER_TIMEOUT_SECONDS = 60
PACKAGE_TIMEOUT_SECONDS = 180
# Mirrors run_audit.finish_run's terminal event names for the shared statuses.
_TERMINAL_EVENTS = {"completed": "run.completed", "partially_completed": "run.completed",
                    "awaiting_approval": "review.required", "failed": "run.failed",
                    "interrupted": "run.interrupted", "rejected": "run.completed"}


def _default_graph(mode: str):
    from backend.app.api.v2 import learning_runs

    return learning_runs._package_graph if mode == "learning_package" else learning_runs._graph


def _conflict_outcome(run_id: str) -> str:
    """A fenced write lost the run; never overwrite the current owner's state."""
    current = run_lifecycle.load_run(run_id)
    if current is not None and current.status == "cancelled":
        return "cancelled"
    return "lost_lease"


def _finish_guarded(record, execution_id: str, *, status: str, result: dict[str, Any]) -> str:
    """Publish the terminal state, fenced on the claim's lease and status.

    Unlike ``run_audit.finish_run(expected_status=...)`` this adds no
    ``run.reconciled`` audit row: a worker completion is not a reconciliation.
    """
    def write(session) -> None:
        run_leases.fence(session, record.run_id, execution_id)
        row = session.get(AgentRunRecord, record.run_id)
        package = result.get("learning_package") or {}
        for key, value in dict(
            status=status,
            duration_ms=int((time.time() - record.started_at) * 1000),
            success_count=int(status == "completed"),
            lease_expires_at=None,
            tool_calls=int(result.get("budget", {}).get("tool_calls", 0)),
            artifact_count=int(bool(package.get("lesson"))) + int(bool(package.get("exercises"))),
            metadata_data={**(row.metadata_data or {}), "request": record.request.model_dump(),
                           "result": result},
        ).items():
            setattr(row, key, value)
        sequence = run_audit._next_event_sequence(session, record.run_id)
        session.add(AgentCheckpointRecord(
            id=str(uuid.uuid4()), run_id=record.run_id, thread_id=record.run_id,
            node_name="lifecycle", status=_TERMINAL_EVENTS.get(status, "run.status_changed"),
            sequence=sequence, state_data={"status": status}))

    try:
        run_queue._safe_write_retrying(write)
    except run_audit.RunStateConflict:
        return _conflict_outcome(record.run_id)
    return status


async def _execute_claimed(record, execution_id: str, graph, timeout_seconds: float):
    """Run the claimed graph with the streaming path's heartbeat + timeout."""
    from backend.app.agent_runtime.conversation_memory import load_conversation_memory

    state: dict[str, Any] = {
        "run_id": record.run_id, "thread_id": record.thread_id or record.run_id,
        "message": record.request.message, "execution_id": execution_id,
        "course_id": record.request.course_id, "user_id": record.request.user_id,
        "require_approval": record.request.require_approval,
        "history": [], "memory_run_ids": [],
    }
    retrieval_ms = 0

    async def on_event(name: str, data: dict[str, Any]) -> None:
        nonlocal retrieval_ms
        if name == "retrieval.completed":
            retrieval_ms += data["latency_ms"]
        await asyncio.to_thread(
            run_audit.checkpoint, run_id=record.run_id, thread_id=record.thread_id or record.run_id,
            node_name=data.get("node", "retrieve"), status=name, state_data=data,
            execution_id=execution_id)

    blocked = graph._guard({"message": record.request.message})["safety_blocked"]
    if not blocked and record.request.user_id and record.request.user_id != "anonymous":
        history, memory_ids = await asyncio.to_thread(
            load_conversation_memory, run_lifecycle.SessionLocal,
            user_id=record.request.user_id, session_id=record.request.session_id,
            course_id=record.request.course_id, before=record.started_at)
        state.update({"history": history, "memory_run_ids": memory_ids})
        if record.request.mode == "learning_package":
            profile = getattr(graph.runtime, "_profile_context", None)
            if callable(profile):
                state["profile_context"] = await asyncio.to_thread(profile, record.request.user_id)

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(run_leases.HEARTBEAT_SECONDS)
            await asyncio.to_thread(run_leases.renew, record.run_id, execution_id)

    async def supervised() -> dict[str, Any]:
        graph_task = asyncio.create_task(graph.invoke(state, on_event=on_event))
        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            done, _ = await asyncio.wait({graph_task, heartbeat_task},
                                         return_when=asyncio.FIRST_COMPLETED)
            if heartbeat_task in done:
                # Propagate the lease/DB failure; the finally block cancels the graph.
                await heartbeat_task
            return await graph_task
        finally:
            for task in (graph_task, heartbeat_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(graph_task, heartbeat_task, return_exceptions=True)

    return await asyncio.wait_for(supervised(), timeout=timeout_seconds), retrieval_ms


def work_once(worker_id: str = "", *, graph_lookup: Callable[[str], Any] | None = None,
              timeout_seconds: float | None = None) -> str:
    """Claim and execute at most one queued run; returns a stable outcome name.

    Outcomes: ``idle`` (nothing runnable), a settled run status
    (``completed`` / ``partially_completed`` / ``awaiting_approval`` /
    ``failed``), ``cancelled`` (cancelled mid-flight; not overwritten),
    ``lost_lease`` (another worker owns the run), ``missing`` or
    ``persistence_unavailable`` (no terminal write was possible).
    """
    claim = run_queue.claim_next_run(worker_id)
    if claim is None:
        return "idle"
    run_id, execution_id = claim["run_id"], claim["execution_id"]
    record = run_lifecycle.load_run(run_id)
    if record is None:
        return "missing"
    mode = record.request.mode
    graph = (graph_lookup or _default_graph)(mode)
    timeout = (timeout_seconds if timeout_seconds is not None else
               PACKAGE_TIMEOUT_SECONDS if mode == "learning_package" else ANSWER_TIMEOUT_SECONDS)
    try:
        state, retrieval_ms = asyncio.run(
            _execute_claimed(record, execution_id, graph, timeout))
    except asyncio.TimeoutError:
        return _finish_guarded(record, execution_id, status="failed",
                               result={"error": "run_timeout"})
    except run_audit.RunStateConflict:
        return _conflict_outcome(run_id)
    except run_audit.RunPersistenceError:
        return "persistence_unavailable"
    except PackageFailure as exc:
        # Exception text is never persisted; only the stable code is.
        return _finish_guarded(record, execution_id, status="failed", result={"error": exc.code})
    except Exception as exc:
        LOGGER.error("Run %s failed (%s)", run_id, type(exc).__name__)
        return _finish_guarded(record, execution_id, status="failed",
                               result={"error": "run_execution_failed"})
    try:
        run_audit.log_retrieval(run_id=run_id, query=record.request.message,
                                evidence=state.get("evidence", []), latency_ms=retrieval_ms,
                                execution_id=execution_id)
    except run_audit.RunStateConflict:
        return _conflict_outcome(run_id)
    run_lifecycle.apply_settled_state(record, state)
    return _finish_guarded(record, execution_id, status=record.status, result=record.result)


def work_forever(worker_id: str = "", *, poll_seconds: float = 2.0,
                 graph_lookup: Callable[[str], Any] | None = None) -> None:
    """Worker main loop; a persistence outage sleeps and retries, never exits."""
    while True:
        try:
            outcome = work_once(worker_id, graph_lookup=graph_lookup)
        except run_audit.RunPersistenceError:
            outcome = "persistence_unavailable"
        if outcome == "idle":
            time.sleep(poll_seconds)
        elif outcome == "persistence_unavailable":
            time.sleep(poll_seconds)
