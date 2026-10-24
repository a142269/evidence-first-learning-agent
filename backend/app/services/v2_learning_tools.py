"""Read-only, course-scoped business tools for the V2 learning workflow.

The names, allowed roles, argument schemas, timeouts and truncation limits of
these tools are not defined here: they come from the single tool catalog, and
access goes through its deny-by-default matrix. Every outcome - including each
refusal - writes one unified audit event.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import time
from typing import Any, Callable, Literal

from pydantic import ValidationError
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.core.deployment_policy import production_mode
from backend.app.core.models import (
    BktStateRecord, KnowledgePointRecord, KnowledgeRelationRecord, MistakeRecord, ProfileRecord,
)
from backend.app.repositories.auth_repo import AuthRepository
from backend.app.services.tool_audit import record_tool_event
from backend.app.services.tool_catalog import (
    TOOL_CATALOG, TOOL_VERSION_V2, ToolArgs, decide_access, v2_timeouts,
)


TOOL_VERSION = TOOL_VERSION_V2
DEFAULT_TIMEOUT_SECONDS, DEFAULT_SEARCH_TIMEOUT_SECONDS = v2_timeouts()


@dataclass(frozen=True)
class ToolContext:
    run_id: str
    user_id: str
    course_id: str
    role: str


@dataclass(frozen=True)
class ToolResult:
    name: str
    version: str
    status: Literal["success", "no_data", "denied", "invalid_args", "timeout", "failed"]
    data: Any
    latency_ms: int
    request_hash: str

    def audit(self) -> dict[str, Any]:
        # No prompt, profile, source text, bearer token or raw arguments in audit.
        return {"tool": self.name, "version": self.version, "status": self.status,
                "latency_ms": self.latency_ms, "request_hash": self.request_hash,
                "result_count": len(self.data) if isinstance(self.data, list) else int(bool(self.data))}


class V2LearningTools:
    def __init__(self, retrieve: Callable[[str, str], list[dict[str, Any]]] | None = None,
                 *, timeout_seconds: float | None = None,
                 search_timeout_seconds: float | None = None,
                 session_factory=SessionLocal):
        self.retrieve = retrieve
        self.timeout_seconds = (DEFAULT_TIMEOUT_SECONDS if timeout_seconds is None
                                else timeout_seconds)
        self.search_timeout_seconds = (DEFAULT_SEARCH_TIMEOUT_SECONDS if search_timeout_seconds is None
                                       else search_timeout_seconds)
        self.session_factory = session_factory

    async def call(self, context: ToolContext, name: str, arguments: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        request_hash = hashlib.sha256(
            f"{context.run_id}:{context.role}:{name}:{sorted((arguments or {}).items())}".encode()
        ).hexdigest()[:16]

        def finish(status: str, data: Any = None, *, decision: str, reason: str = "") -> ToolResult:
            latency_ms = int((time.perf_counter() - started) * 1000)
            record_tool_event(tool=name, spec=TOOL_CATALOG.get(name), role=context.role,
                              status=status, decision=decision, reason=reason,
                              latency_ms=latency_ms, request_hash=request_hash,
                              run_id=context.run_id)
            return ToolResult(name=name, version=TOOL_VERSION, status=status, data=data,
                              latency_ms=latency_ms, request_hash=request_hash)

        access = decide_access(context.role, name)
        if not access.allowed:
            return finish("denied", decision=access.reason)
        if not context.course_id or not context.user_id:
            # Scope is server-injected; an empty scope is a refusal, never a wider default.
            return finish("denied", decision="granted", reason="missing_scope")
        spec = access.spec
        try:
            parsed = spec.args_model.model_validate(arguments or {})
        except ValidationError:
            return finish("invalid_args", decision="granted", reason="args_schema_rejected")
        try:
            timeout = (self.search_timeout_seconds if spec.timeout_class == "search"
                       else self.timeout_seconds)
            data = await asyncio.wait_for(asyncio.to_thread(
                self._execute, context, name, parsed), timeout=timeout)
        except asyncio.TimeoutError:
            return finish("timeout", decision="granted", reason="timeout")
        except PermissionError as exc:
            return finish("denied", decision="granted", reason=str(exc) or "access_denied")
        except Exception:
            return finish("failed", decision="granted", reason="execution_failed")
        return finish("success" if data else "no_data", data, decision="granted")

    def _execute(self, context: ToolContext, name: str, args: ToolArgs) -> Any:
        # Recheck the persisted course grant at tool time, so a revoked grant
        # cannot continue accessing profile or course evidence mid-run.
        from backend.app.api.v2.access import _database_course_scope

        if production_mode() or _database_course_scope():
            if not AuthRepository().has_course(context.user_id, context.course_id):
                raise PermissionError("course_access_denied")
        if name == "search_course_evidence":
            if self.retrieve is None:
                raise RuntimeError("retriever_unavailable")
            from backend.app.services.safety.run_guard import get_learning_run_guard

            if get_learning_run_guard().decide(args.query).blocked:
                raise PermissionError("unsafe_query")
            return self.retrieve(args.query, context.course_id)[:TOOL_CATALOG[name].max_result_items]

        with self.session_factory() as db:
            if name == "get_learning_profile":
                profile = db.get(ProfileRecord, context.user_id)
                preference = (profile.profile_data or {}).get("learning_preference", {}) if profile else {}
                if not isinstance(preference, dict):
                    preference = {}
                rows = db.execute(select(BktStateRecord, KnowledgePointRecord)
                    .join(KnowledgePointRecord, KnowledgePointRecord.id == BktStateRecord.knowledge_point_id)
                    .where(BktStateRecord.user_id == context.user_id,
                           KnowledgePointRecord.course == context.course_id)
                    .order_by(BktStateRecord.p_learned.asc()).limit(5)).all()
                data = {"preference": {key: str(preference[key])[:80] for key in ("mode", "depth")
                                       if key in preference},
                        "weak_points": [{"knowledge_point_id": kp.id, "name": kp.name,
                                         "mastery": round(state.p_learned, 3),
                                         "updated_at": state.updated_at, "model": "BKT"}
                                        for state, kp in rows]}
                return data if data["preference"] or data["weak_points"] else None

            if name == "get_recent_mistakes":
                cutoff = time.time() - 30 * 86400
                rows = db.execute(select(MistakeRecord, KnowledgePointRecord)
                    .join(KnowledgePointRecord, KnowledgePointRecord.id == MistakeRecord.knowledge_point_id)
                    .where(MistakeRecord.user_id == context.user_id,
                           KnowledgePointRecord.course == context.course_id,
                           MistakeRecord.created_at >= cutoff)
                    .order_by(MistakeRecord.created_at.desc()).limit(10)).all()
                return [{"knowledge_point_id": kp.id, "name": kp.name,
                         "error_type": mistake.error_type, "created_at": mistake.created_at,
                         "resolved": mistake.resolved_at is not None}
                        for mistake, kp in rows]

            if name == "get_prerequisites":
                point = db.get(KnowledgePointRecord, args.knowledge_point_id)
                if point is None or point.course != context.course_id:
                    return None
                rows = db.execute(select(KnowledgeRelationRecord, KnowledgePointRecord)
                    .join(KnowledgePointRecord,
                          KnowledgePointRecord.id == KnowledgeRelationRecord.target_id)
                    .where(KnowledgeRelationRecord.source_id == point.id,
                           KnowledgeRelationRecord.relation_type == "prerequisite",
                           KnowledgePointRecord.course == context.course_id).limit(10)).all()
                return [{"knowledge_point_id": prerequisite.id, "name": prerequisite.name}
                        for _relation, prerequisite in rows]
        raise ValueError("unknown_tool")
