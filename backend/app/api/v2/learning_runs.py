"""Authenticated, isolated learning runs with live node events."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.agent_runtime import run_audit, run_leases, run_queue
from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph
from backend.app.agent_runtime.learning_package import LearningPackageGraph
from backend.app.agent_runtime.conversation_memory import load_conversation_memory
from backend.app.api.v2 import run_lifecycle
from backend.app.api.v2.access import authorize_reviewer, resolve_v2_principal
from backend.app.api.v2.run_lifecycle import (
    LearningRunRequest, ReviewDecision, RunRecord, WORKFLOW_VERSION,
    authorized_run, event, public_record, stream_result,
)
from backend.app.core.observability import learning_run_span

router = APIRouter(prefix="/api/v2/learning-runs", tags=["learning-runs-v2"])


class LearningRuntime:
    @staticmethod
    def _distinct_sources(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep one best chunk per source before cross-retriever fusion.

        Teacher uploads exist in both the legacy corpus and PostgreSQL during
        the migration period.  Fusing by chunk ID would count that same source
        twice and can let a small diagnostic upload crowd out course chapters.
        Evidence is cited at document/source granularity, so source-level
        diversity is the useful unit for the final top-k.
        """
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in hits:
            source = str(hit.get("source") or hit.get("chunk_id") or "")
            if not source or source in seen:
                continue
            seen.add(source)
            unique.append(hit)
        return unique

    def retrieve(self, message: str, course_id: str) -> list[dict[str, Any]]:
        from backend.app.services.enterprise_retriever import (
            get_enterprise_retriever,
            reciprocal_rank_fusion,
        )
        from backend.app.services.rag_service import get_rag_service

        enterprise_hits = get_enterprise_retriever().retrieve(
            message, course_id=course_id, top_k=20
        )
        legacy_hits = get_rag_service().retrieve(message, top_k=25, course_filter=course_id)
        if not enterprise_hits:
            return self._distinct_sources(legacy_hits)[:5]
        if not legacy_hits:
            return self._distinct_sources(enterprise_hits)[:5]
        # Uploaded pgvector documents are the V2 priority path, but the
        # existing curated course corpus remains useful evidence.  Fusing
        # both rankings keeps a small upload collection from hiding chapters
        # that have not yet been migrated to PostgreSQL.
        for item in legacy_hits:
            item.setdefault("retriever", "legacy_rag")
        # The source key intentionally replaces the normally finer-grained
        # chunk key here; see _distinct_sources for migration-period rationale.
        fused = reciprocal_rank_fusion(
            [
                self._distinct_sources(enterprise_hits),
                self._distinct_sources(legacy_hits),
            ],
            key_field="source",
        )[:5]
        # A high-confidence Chinese phrase match can be pushed below five by
        # sources that appear in both indexes. Keep that verified source in
        # the final evidence window used for citations.
        rescued = next((item for item in enterprise_hits if item.get("lexical_rescue")), None)
        if rescued and not any(item.get("source") == rescued.get("source") for item in fused):
            return [rescued, *fused[:4]]
        return fused

    async def generate(
        self, message: str, evidence: list[dict[str, Any]], user_id: str = "", history: list | None = None
    ) -> str | dict[str, Any]:
        if not evidence:
            return "知识库中没有足够的可验证资料。请补充课程、章节或上传相关材料后再提问。"
        context = "\n\n".join(item.get("content", "")[:1200] for item in evidence[:3])
        from backend.app.core.llm_client import LLMClient

        profile_context = await asyncio.to_thread(self._profile_context, user_id)
        prompt = (
            "你是高校课程助教。仅根据提供的课程资料回答; 无法确认时明确说明。"
            "回答使用中文, 分点说明, 不要编造来源。\n\n资料:\n"
            f"{context}\n\n学习画像摘要:\n{profile_context}\n\n问题: {message}"
        )
        return await LLMClient().achat_strict_with_usage([
            {"role": "system", "content": "历史对话仅用于理解指代与学习偏好；事实回答须以本轮课程资料为依据。"},
            *(history or []), {"role": "user", "content": prompt},
        ])

    @staticmethod
    async def complete_structured(messages: list[dict[str, str]], *, max_tokens: int) -> dict[str, Any]:
        from backend.app.core.llm_client import LLMClient
        return await LLMClient().achat_strict_with_usage(
            messages, temperature=0.2, max_tokens=max_tokens, json_object=True)

    async def call_tool(self, state: dict[str, Any], *, role: str, name: str,
                        arguments: dict[str, Any]):
        from backend.app.services.v2_learning_tools import ToolContext, V2LearningTools

        return await V2LearningTools(self.retrieve, session_factory=run_lifecycle.SessionLocal).call(
            ToolContext(run_id=state["run_id"], user_id=state["user_id"],
                        course_id=state["course_id"], role=role), name, arguments)

    @staticmethod
    def _profile_context(user_id: str) -> str:
        if not user_id or user_id == "anonymous":
            return "未提供画像，使用通用教学解释。"
        try:
            from backend.app.core.database import SessionLocal
            from backend.app.core.models import ProfileRecord

            with SessionLocal() as session:
                profile = session.get(ProfileRecord, user_id)
                if profile and profile.profile_data:
                    preference = profile.profile_data.get("learning_preference", {})
                    if isinstance(preference, dict):
                        safe = {key: str(preference[key])[:80] for key in ("mode", "depth")
                                if key in preference}
                        if safe:
                            return json.dumps(safe, ensure_ascii=False)
        except Exception:  # pragma: no cover - profile context is optional
            pass
        return "未找到已保存画像，使用通用教学解释。"

    @staticmethod
    def citations(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": item.get("chunk_id", ""),
                "source": item.get("source", ""),
                "label": item.get("title_hint") or item.get("source", "知识库片段"),
                "score": item.get("score", 0),
            }
            for item in evidence
        ]


_runtime = LearningRuntime()
_graph = EvidenceFirstGraph(_runtime)
_package_graph = LearningPackageGraph(_runtime)


def _requires_checkpointer() -> bool:
    default = "true" if os.getenv("DATABASE_URL", "").startswith("postgresql") else "false"
    return os.getenv("V2_REQUIRE_CHECKPOINTER", default).lower() in {"true", "1"}


@router.post("/stream")
async def stream_learning_run(http_request: Request, request: LearningRunRequest) -> StreamingResponse:
    principal, course_id = await asyncio.to_thread(resolve_v2_principal,
        authorization=http_request.headers.get("Authorization"),
        requested_user_id=request.user_id, requested_course_id=request.course_id,
    )
    if request.mode == "learning_package" and not principal.authenticated:
        raise HTTPException(status_code=401, detail="authorization_required")
    graph = _package_graph if request.mode == "learning_package" else _graph
    if request.mode == "learning_package" and not graph._builder_available:
        raise HTTPException(status_code=503, detail="learning_package_unavailable")
    key = http_request.headers.get("Idempotency-Key", "").strip()
    if key and not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
        raise HTTPException(status_code=422, detail="invalid_idempotency_key")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest() if key else None
    fingerprint = hashlib.sha256((request.model_dump_json() + principal.user_id + course_id)
                                 .encode("utf-8")).hexdigest() if key else None

    async def idempotent_replay(existing_id: str) -> StreamingResponse:
        record = await asyncio.to_thread(run_lifecycle.load_run, existing_id)
        if record is None:
            raise HTTPException(status_code=503, detail="run_persistence_unavailable")

        async def frames():
            yield event("run.started", {"run_id": record.run_id,
                                        "session_id": record.request.session_id,
                                        "idempotent_replay": True})
            if record.status in {"completed", "partially_completed", "rejected"}:
                yield event("run.completed", {"run_id": record.run_id, "status": record.status,
                                              **record.result})
            elif record.status == "awaiting_approval":
                yield event("review.required", {"run_id": record.run_id,
                                                "reason": "learning_content_review"})
            elif record.status in {"failed", "interrupted"}:
                yield event("run.failed", {"run_id": record.run_id,
                                           "error": record.result.get("error", "run_execution_failed")})
            else:
                yield event("run.in_progress", {"run_id": record.run_id, "status": record.status})

        return StreamingResponse(frames(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    if digest:
        try:
            existing = await asyncio.to_thread(run_audit.find_idempotent_run, principal.user_id, digest)
        except run_audit.RunPersistenceError:
            raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None
        if existing:
            if existing[1] != fingerprint:
                raise HTTPException(status_code=409, detail="idempotency_key_conflict")
            return await idempotent_replay(existing[0])
    run_id = str(uuid.uuid4())
    request = request.model_copy(update={"user_id": principal.user_id, "course_id": course_id,
                                          "session_id": request.session_id.strip() or run_id})
    blocked = graph._guard({"message": request.message})["safety_blocked"]
    if (_requires_checkpointer() or (request.require_approval and not blocked)) and not graph.supports_human_review():
        raise HTTPException(status_code=503, detail="durable_review_unavailable")
    run = RunRecord(run_id=run_id, thread_id=run_id, request=request, execution_id=uuid.uuid4().hex)
    try:
        history, memory_ids = ([], [])
        if principal.authenticated and not blocked:
            history, memory_ids = await asyncio.to_thread(
                load_conversation_memory, run_lifecycle.SessionLocal, user_id=principal.user_id,
                session_id=request.session_id, course_id=course_id, before=run.started_at,
            )
        await asyncio.to_thread(
            run_audit.start_run, run_id=run_id, session_id=request.session_id or run_id,
            execution_id=run.execution_id,
            idempotency_digest=digest, request_fingerprint=fingerprint,
            user_id=principal.user_id, metadata={
                "request": request.model_dump(), "thread_id": run_id,
                "workflow_version": WORKFLOW_VERSION,
                "memory_eligible": principal.authenticated,
            },
        )
    except run_audit.RunPersistenceError:
        if digest:
            try:
                existing = await asyncio.to_thread(run_audit.find_idempotent_run, principal.user_id, digest)
            except run_audit.RunPersistenceError:
                existing = None
            if existing:
                if existing[1] != fingerprint:
                    raise HTTPException(status_code=409, detail="idempotency_key_conflict") from None
                return await idempotent_replay(existing[0])
        raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None

    async def operation(on_event):
        with learning_run_span("learning_run", run_id=run_id, course_id=course_id):
            state = {
                "run_id": run_id, "thread_id": run_id, "message": request.message,
                "execution_id": run.execution_id,
                "course_id": course_id, "user_id": principal.user_id,
                "require_approval": request.require_approval,
                "history": history, "memory_run_ids": memory_ids,
            }
            if request.mode == "learning_package" and not blocked:
                state["profile_context"] = await asyncio.to_thread(_runtime._profile_context, principal.user_id)
            return await graph.invoke(state, on_event=on_event)

    return StreamingResponse(stream_result(run, operation, timeout=180 if request.mode == "learning_package" else 60), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/enqueue")
async def enqueue_learning_run(http_request: Request, request: LearningRunRequest) -> dict[str, Any]:
    """Queue a run for worker execution (QWEN-301); returns a queryable run id.

    Creation and execution are decoupled: this endpoint only persists a
    ``queued`` run.  A queue worker claims it later (at-least-once) and settles
    it through the same graph, lease and delivery contract as ``/stream``.
    The synchronous ``/stream`` endpoint keeps its existing behaviour.
    """
    principal, course_id = await asyncio.to_thread(resolve_v2_principal,
        authorization=http_request.headers.get("Authorization"),
        requested_user_id=request.user_id, requested_course_id=request.course_id,
    )
    if request.mode == "learning_package" and not principal.authenticated:
        raise HTTPException(status_code=401, detail="authorization_required")
    graph = _package_graph if request.mode == "learning_package" else _graph
    if request.mode == "learning_package" and not graph._builder_available:
        raise HTTPException(status_code=503, detail="learning_package_unavailable")
    run_id = str(uuid.uuid4())
    request = request.model_copy(update={"user_id": principal.user_id, "course_id": course_id,
                                          "session_id": request.session_id.strip() or run_id})
    try:
        await asyncio.to_thread(
            run_audit.queue_run, run_id=run_id, session_id=request.session_id or run_id,
            user_id=principal.user_id, metadata={
                "request": request.model_dump(), "thread_id": run_id,
                "workflow_version": WORKFLOW_VERSION,
                "memory_eligible": principal.authenticated,
                "queue": {"enqueued_at": time.time()},
            })
    except run_audit.RunPersistenceError:
        raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None
    return {"run_id": run_id, "status": "queued", "session_id": request.session_id,
            "workflow_version": WORKFLOW_VERSION}


@router.post("/{run_id}/cancel")
async def cancel_learning_run(http_request: Request, run_id: str) -> dict[str, Any]:
    """Cancel a queue-originated run; running workers are fenced off by the lease."""
    record, _principal = await authorized_run(http_request.headers.get("Authorization"), run_id)
    if record.status not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="run_not_cancellable")
    try:
        queued = await asyncio.to_thread(run_queue.queue_origin, run_id)
        if not queued:
            raise HTTPException(status_code=409, detail="run_not_queued")
        cancelled = await asyncio.to_thread(run_queue.cancel_run, run_id)
    except run_audit.RunPersistenceError:
        raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None
    if not cancelled:
        # Lost the race against a claim or another canceller.
        raise HTTPException(status_code=409, detail="run_not_cancellable")
    return {"run_id": run_id, "status": "cancelled"}


@router.get("/{run_id}")
async def get_learning_run(http_request: Request, run_id: str) -> dict[str, Any]:
    record, principal = await authorized_run(http_request.headers.get("Authorization"), run_id)
    return public_record(record, principal)


@router.post("/{run_id}/resume")
async def resume_learning_run(http_request: Request, run_id: str, decision: ReviewDecision) -> StreamingResponse:
    record, principal = await authorized_run(http_request.headers.get("Authorization"), run_id)
    authorize_reviewer(principal=principal)
    if record.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail="run_not_awaiting_approval")
    # Old shared session checkpoints cannot safely be attributed to a single run.
    if record.thread_id != run_id or record.workflow_version != WORKFLOW_VERSION:
        raise HTTPException(status_code=409, detail="legacy_run_restart_required")
    graph = _package_graph if record.request.mode == "learning_package" else _graph
    if not graph.supports_human_review():
        raise HTTPException(status_code=503, detail="durable_review_unavailable")
    try:
        execution_id = uuid.uuid4().hex
        claimed = await asyncio.to_thread(run_audit.claim_review, run_id, execution_id)
    except run_audit.RunPersistenceError:
        raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None
    if not claimed:
        raise HTTPException(status_code=409, detail="run_not_awaiting_approval")
    record.status = "reviewing"
    record.execution_id = execution_id

    async def operation(on_event):
        return await graph.resume(record.thread_id, decision.model_dump(), on_event=on_event, execution_id=execution_id)

    return StreamingResponse(stream_result(record, operation, decision=decision),
                             media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


@router.post("/{run_id}/continue")
async def continue_learning_run(http_request: Request, run_id: str) -> StreamingResponse:
    """Continue a non-review task from its last committed Graph node boundary."""
    record, _principal = await authorized_run(http_request.headers.get("Authorization"), run_id)
    if record.status in {"running", "reviewing"}:
        try:
            if await asyncio.to_thread(run_leases.expire, run_id):
                record, _principal = await authorized_run(http_request.headers.get("Authorization"), run_id)
        except run_audit.RunPersistenceError:
            raise HTTPException(503, "run_persistence_unavailable") from None
    if record.status not in {"failed", "interrupted"}:
        raise HTTPException(409, "run_not_continuable")
    if record.thread_id != run_id or record.workflow_version != WORKFLOW_VERSION:
        raise HTTPException(409, "legacy_run_restart_required")
    graph = _package_graph if record.request.mode == "learning_package" else _graph
    if not graph.supports_human_review():
        raise HTTPException(503, "durable_review_unavailable")
    try:
        state = await graph.unfinished_checkpoint(record.thread_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    except Exception:
        raise HTTPException(503, "checkpoint_unavailable") from None
    expected = {"run_id": run_id, "thread_id": record.thread_id,
                "user_id": record.request.user_id, "course_id": record.request.course_id,
                "message": record.request.message, "execution_id": record.execution_id}
    if any(state.get(name) != value for name, value in expected.items()):
        raise HTTPException(409, "checkpoint_identity_mismatch")
    previous_execution_id = record.execution_id
    execution_id = uuid.uuid4().hex
    try:
        claimed = await asyncio.to_thread(run_leases.claim_continuation,
            run_id, previous_execution_id, execution_id)
    except run_audit.RunPersistenceError:
        raise HTTPException(503, "run_persistence_unavailable") from None
    if not claimed:
        raise HTTPException(409, "run_state_changed")
    record.status = "running"
    record.execution_id = execution_id

    async def operation(on_event):
        return await graph.continue_unfinished(record.thread_id,
            previous_execution_id=previous_execution_id, execution_id=execution_id,
            on_event=on_event)

    return StreamingResponse(stream_result(record, operation,
        timeout=180 if record.request.mode == "learning_package" else 60,
        continuation=True), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{run_id}/events")
async def get_learning_run_events(http_request: Request, run_id: str,
                                  after: int = Query(default=0, ge=0),
                                  limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    await authorized_run(http_request.headers.get("Authorization"), run_id)

    def read():
        from sqlalchemy import select
        from backend.app.api.v2.run_lifecycle import SessionLocal
        from backend.app.core.models import AgentCheckpointRecord
        with SessionLocal() as session:
            query = select(AgentCheckpointRecord).where(AgentCheckpointRecord.run_id == run_id)
            if after:
                query = query.where(AgentCheckpointRecord.sequence > after)
            rows = session.scalars(query.order_by(
                AgentCheckpointRecord.sequence, AgentCheckpointRecord.created_at,
                AgentCheckpointRecord.id).limit(limit)).all()
            return [{"id": row.id, "node": row.node_name, "status": row.status,
                     "event_sequence": row.sequence,
                     "created_at": row.created_at,
                     "data": {key: value for key, value in (row.state_data or {}).items()
                              if key in {"node", "latency_ms", "evidence_count", "tool_calls",
                                         "tool", "version", "status", "request_hash", "result_count"}}} for row in rows]
    try:
        items = await asyncio.to_thread(read)
    except Exception:
        raise HTTPException(status_code=503, detail="run_persistence_unavailable") from None
    return {"run_id": run_id, "events": items}


@router.post("/{run_id}/reconcile")
async def reconcile_learning_run(http_request: Request, run_id: str) -> dict[str, Any]:
    """Repair a failed/interrupted run from settled state without executing the graph."""
    record, principal = await authorized_run(http_request.headers.get("Authorization"), run_id)
    authorize_reviewer(principal=principal)
    if record.status in {"running", "reviewing"}:
        try:
            expired = await asyncio.to_thread(run_leases.expire, run_id)
        except run_audit.RunPersistenceError:
            raise HTTPException(503, "run_persistence_unavailable") from None
        if expired:
            record, principal = await authorized_run(http_request.headers.get("Authorization"), run_id)
    if record.status not in {"failed", "interrupted"}:
        raise HTTPException(409, "run_not_reconcilable")
    if record.thread_id != run_id or record.workflow_version != WORKFLOW_VERSION:
        raise HTTPException(409, "legacy_run_restart_required")
    graph = _package_graph if record.request.mode == "learning_package" else _graph
    if not graph.supports_human_review():
        raise HTTPException(503, "durable_review_unavailable")
    try:
        state = await graph.settled_checkpoint(record.thread_id)
    except ValueError:
        raise HTTPException(409, "checkpoint_not_settled") from None
    except Exception:
        raise HTTPException(503, "checkpoint_unavailable") from None
    identity = {"run_id": run_id, "thread_id": record.thread_id,
                "user_id": record.request.user_id, "course_id": record.request.course_id,
                "message": record.request.message, "require_approval": record.request.require_approval}
    if record.execution_id:
        identity["execution_id"] = record.execution_id
    if any(state.get(key) != value for key, value in identity.items()):
        raise HTTPException(409, "checkpoint_identity_mismatch")
    if (record.request.require_approval and not state.get("safety_blocked")
            and not state.get("__interrupt__") and state.get("review_status") not in {"approved", "rejected"}):
        raise HTTPException(409, "checkpoint_not_settled")
    previous_status = record.status
    run_lifecycle.apply_settled_state(record, state)
    try:
        await asyncio.to_thread(run_audit.finish_run, run_id=run_id, status=record.status,
            result={"request": record.request.model_dump(), "result": record.result},
            started_at=record.started_at, expected_status=previous_status)
    except run_audit.RunStateConflict:
        raise HTTPException(409, "run_state_changed") from None
    except run_audit.RunPersistenceError:
        raise HTTPException(503, "run_persistence_unavailable") from None
    return public_record(record, principal)
