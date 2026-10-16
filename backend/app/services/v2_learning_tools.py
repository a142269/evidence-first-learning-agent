"""Read-only, course-scoped business tools for the V2 learning workflow."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import time
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.core.deployment_policy import production_mode
from backend.app.core.models import (
    BktStateRecord, KnowledgePointRecord, KnowledgeRelationRecord, MistakeRecord, ProfileRecord,
)
from backend.app.repositories.auth_repo import AuthRepository


TOOL_VERSION = "v2-readonly-1"
ROLE_TOOLS: dict[str, frozenset[str]] = {
    "planner": frozenset({"get_learning_profile", "get_recent_mistakes", "get_prerequisites"}),
    "tutor": frozenset({"search_course_evidence"}),
    "practice": frozenset(),
    "reviewer": frozenset(),
}


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchArgs(_Args):
    query: str = Field(min_length=1, max_length=500)


class EmptyArgs(_Args):
    pass


class PrerequisiteArgs(_Args):
    knowledge_point_id: str = Field(min_length=1, max_length=128)


SCHEMAS: dict[str, type[_Args]] = {
    "search_course_evidence": SearchArgs,
    "get_learning_profile": EmptyArgs,
    "get_recent_mistakes": EmptyArgs,
    "get_prerequisites": PrerequisiteArgs,
}


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
                 *, timeout_seconds: float = 10.0, search_timeout_seconds: float = 30.0,
                 session_factory=SessionLocal):
        self.retrieve = retrieve
        self.timeout_seconds = timeout_seconds
        self.search_timeout_seconds = search_timeout_seconds
        self.session_factory = session_factory

    async def call(self, context: ToolContext, name: str, arguments: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        request_hash = hashlib.sha256(
            f"{context.run_id}:{context.role}:{name}:{sorted((arguments or {}).items())}".encode()
        ).hexdigest()[:16]

        def result(status: str, data: Any = None) -> ToolResult:
            return ToolResult(name=name, version=TOOL_VERSION, status=status, data=data,
                              latency_ms=int((time.perf_counter() - started) * 1000),
                              request_hash=request_hash)

        if name not in ROLE_TOOLS.get(context.role, frozenset()) or not context.course_id or not context.user_id:
            return result("denied")
        schema = SCHEMAS.get(name)
        if schema is None:
            return result("denied")
        try:
            parsed = schema.model_validate(arguments or {})
        except ValidationError:
            return result("invalid_args")
        try:
            timeout = self.search_timeout_seconds if name == "search_course_evidence" else self.timeout_seconds
            data = await asyncio.wait_for(asyncio.to_thread(
                self._execute, context, name, parsed), timeout=timeout)
        except asyncio.TimeoutError:
            return result("timeout")
        except PermissionError:
            return result("denied")
        except Exception:
            return result("failed")
        return result("success" if data else "no_data", data)

    def _execute(self, context: ToolContext, name: str, args: _Args) -> Any:
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
            return self.retrieve(args.query, context.course_id)[:5]

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
