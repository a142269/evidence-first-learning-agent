"""Durable V2 run lifecycle, authorization and safe event delivery.

Transport events describe real work. Drafts and source contents are withheld
from the requester's stream until content review has passed.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
import json
import logging
import time
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.agent_runtime import run_audit, run_leases
from backend.app.agent_runtime.learning_graph import EventSink
from backend.app.api.v2.access import (
    V2Principal, _principal_from_authorization, authorize_run_owner, resolve_v2_principal,
)
from backend.app.core.database import SessionLocal
from backend.app.core.models import AgentRunRecord

LOGGER = logging.getLogger(__name__)
WORKFLOW_VERSION = "learning-workflows-v2.2"


class LearningRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=8000)
    course_id: str = Field(default="artificial_intelligence", min_length=1, max_length=128)
    session_id: str = Field(default="", max_length=128)
    user_id: str = Field(default="anonymous", max_length=128)
    require_approval: bool = False
    mode: Literal["answer", "learning_package"] = "answer"


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool = Field(strict=True)
    edited_answer: str = Field(default="", max_length=12000)
    note: str = Field(default="", max_length=1000)


@dataclass
class RunRecord:
    run_id: str
    request: LearningRunRequest
    status: str = "running"
    started_at: float = field(default_factory=time.time)
    result: dict[str, Any] = field(default_factory=dict)
    thread_id: str = ""
    workflow_version: str = WORKFLOW_VERSION
    execution_id: str = ""


def event(name: str, payload: dict[str, Any]) -> str:
    sequence = payload.get("event_sequence")
    prefix = f"id: {sequence}\n" if isinstance(sequence, int) and sequence > 0 else ""
    return f"{prefix}event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def load_run(run_id: str) -> RunRecord | None:
    try:
        with SessionLocal() as session:
            row = session.get(AgentRunRecord, run_id)
            if row is None:
                return None
            metadata = row.metadata_data or {}
            return RunRecord(
                run_id=row.id, request=LearningRunRequest.model_validate(metadata["request"]),
                status=row.status, started_at=row.created_at,
                result=metadata.get("result", {}), thread_id=metadata.get("thread_id", ""),
                workflow_version=metadata.get("workflow_version", "legacy"),
                execution_id=row.execution_id or "",
            )
    except Exception as exc:
        LOGGER.error("Run lookup failed (%s)", type(exc).__name__)
        raise run_audit.RunPersistenceError("run_persistence_unavailable") from exc


async def authorized_run(authorization: str | None, run_id: str) -> tuple[RunRecord, V2Principal]:
    # Even offline demo reads require a real login; user_id in a body is not auth.
    principal = await asyncio.to_thread(_principal_from_authorization, authorization)
    if principal is None:
        raise HTTPException(status_code=401, detail="authorization_required")
    try:
        record = await asyncio.to_thread(load_run, run_id)
    except run_audit.RunPersistenceError:
        raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None
    if record is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    principal, _ = await asyncio.to_thread(resolve_v2_principal, authorization=authorization,
        requested_user_id="anonymous", requested_course_id=record.request.course_id)
    authorize_run_owner(principal=principal, run_user_id=record.request.user_id)
    return record, principal


def public_record(record: RunRecord, principal: V2Principal) -> dict[str, Any]:
    result = dict(record.result)
    if "approval" in result and principal.role not in {"teacher", "admin"}:
        result = {"review_required": True}
    return {
        "run_id": record.run_id, "request": record.request.model_dump(),
        "status": record.status, "started_at": record.started_at, "result": result,
        "workflow_version": record.workflow_version,
    }


def interrupt_payload(state: dict[str, Any]) -> dict[str, Any]:
    pending = state.get("__interrupt__", [])
    if not pending:
        return {}
    value = getattr(pending[0], "value", pending[0])
    return value if isinstance(value, dict) else {}


async def finish(record: RunRecord) -> int:
    return await asyncio.to_thread(
        run_audit.finish_run, run_id=record.run_id, status=record.status,
        result={"request": record.request.model_dump(), "result": record.result},
        started_at=record.started_at,
        execution_id=record.execution_id,
    )


def apply_settled_state(record: RunRecord, state: dict[str, Any],
                        decision: ReviewDecision | None = None) -> None:
    """One delivery contract for live execution and persisted-state reconciliation."""
    if state.get("__interrupt__"):
        record.status = "awaiting_approval"
        record.result = {"approval": interrupt_payload(state)}
        return
    rejected = state.get("review_status") == "rejected" or bool(decision and not decision.approved)
    record.status = "rejected" if rejected or state.get("safety_blocked") else "completed"
    record.result = {
        "answer": state.get("answer", ""),
        "citations": [] if rejected else state.get("citations", []),
        "evidence": [] if rejected else state.get("evidence", []),
        "quality": state.get("quality", {}),
        "latency_ms": int((time.time() - record.started_at) * 1000),
    }
    if decision or state.get("review_status") in {"approved", "rejected"}:
        record.result["review"] = {"approved": decision.approved if decision else not rejected}
    if not rejected and not state.get("safety_blocked"):
        record.result["memory_run_ids"] = state.get("memory_run_ids", [])
        if state.get("learning_package"):
            record.result["learning_package"] = state["learning_package"]
        if state.get("tool_audit"):
            record.result["tool_audit"] = state["tool_audit"]
    if state.get("budget"):
        record.result["budget"] = state["budget"]
        if state.get("learning_package"):
            record.result["tool_stop_reason"] = state.get("tool_stop_reason", "model_finished")


async def stream_result(
    record: RunRecord, operation: Callable[[EventSink], Awaitable[dict[str, Any]]],
    *, timeout: int = 60, decision: ReviewDecision | None = None, continuation: bool = False,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()
    retrieval_ms = 0

    async def on_event(name: str, data: dict[str, Any]) -> None:
        nonlocal retrieval_ms
        if name == "retrieval.completed":
            retrieval_ms += data["latency_ms"]
        sequence = await asyncio.to_thread(
            run_audit.checkpoint, run_id=record.run_id, thread_id=record.thread_id,
            node_name=data.get("node", "retrieve"), status=name, state_data=data,
            execution_id=record.execution_id,
        )
        await queue.put((name, {"run_id": record.run_id, "event_sequence": sequence, **data}))

    async def execute() -> dict[str, Any]:
        try:
            return await asyncio.wait_for(supervised(), timeout=timeout)
        finally:
            await queue.put(None)

    async def heartbeat():
        while True:
            await asyncio.sleep(run_leases.HEARTBEAT_SECONDS)
            await asyncio.to_thread(run_leases.renew, record.run_id, record.execution_id)

    async def supervised():
        if not record.execution_id:
            return await operation(on_event)
        # Confirm ownership before any model/retrieval scheduling.
        await asyncio.to_thread(run_leases.renew, record.run_id, record.execution_id)
        graph_task = asyncio.create_task(operation(on_event))
        lease_task = asyncio.create_task(heartbeat())
        try:
            done, _ = await asyncio.wait({graph_task, lease_task}, return_when=asyncio.FIRST_COMPLETED)
            if lease_task in done:
                await lease_task  # Propagate lease/DB failure and cancel Graph below.
            return await graph_task
        finally:
            for child in (graph_task, lease_task):
                if not child.done():
                    child.cancel()
            await asyncio.gather(graph_task, lease_task, return_exceptions=True)

    task: asyncio.Task | None = None
    terminal_persisted = False
    try:
        yield event("run.started", {"run_id": record.run_id,
                                    **({} if decision or continuation else {"event_sequence": 1}),
                                    "session_id": record.request.session_id,
                                    "resumed": decision is not None or continuation})
        task = asyncio.create_task(execute())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield event(*item)
        state = await task
        await asyncio.to_thread(
            run_audit.log_retrieval, run_id=record.run_id, query=record.request.message,
            evidence=state.get("evidence", []), latency_ms=retrieval_ms,
            execution_id=record.execution_id,
        )
        apply_settled_state(record, state, decision)
        if record.status == "awaiting_approval":
            sequence = await finish(record)
            terminal_persisted = True
            yield event("review.required", {"run_id": record.run_id, "event_sequence": sequence,
                                            "reason": "learning_content_review"})
            return
        sequence = await finish(record)
        terminal_persisted = True
        # This is delivery of reviewed content, not a model-token stream.
        answer = record.result["answer"]
        for index in range(0, len(answer), 80):
            yield event("answer.delta", {"run_id": record.run_id, "delta": answer[index:index + 80]})
        yield event("run.completed", {"run_id": record.run_id, "event_sequence": sequence,
                                      "status": record.status, **record.result})
    except (asyncio.CancelledError, GeneratorExit):
        # Stop graph/checkpoint writes before making this run recoverable.
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
        if not terminal_persisted:
            record.status, record.result = "interrupted", {"error": "client_disconnected"}
            with suppress(run_audit.RunPersistenceError, run_audit.RunStateConflict):
                await asyncio.shield(finish(record))
        raise
    except Exception as exc:
        from backend.app.agent_runtime.learning_package import PackageFailure
        code = ("run_timeout" if isinstance(exc, asyncio.TimeoutError) else
                "execution_lease_lost" if isinstance(exc, run_audit.RunStateConflict) else
                "run_persistence_unavailable" if isinstance(exc, run_audit.RunPersistenceError) else
                exc.code if isinstance(exc, PackageFailure) else
                "run_execution_failed")
        # Exception messages may contain connection strings, prompts or tokens.
        LOGGER.error("Run %s failed (%s)", record.run_id, type(exc).__name__)
        record.status, record.result = "failed", {"error": code}
        with suppress(run_audit.RunPersistenceError, run_audit.RunStateConflict):
            await finish(record)
        yield event("run.failed", {"run_id": record.run_id, "error": code})
    finally:
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
