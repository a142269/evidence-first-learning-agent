"""Server-owned identity and course access for V2 learning runs.

The request payload may describe a session, but it must never be treated as
the source of truth for a user's identity.  Enterprise Compose enables this
check by default; the explicit optional mode keeps the pre-existing offline
demo usable without a login service.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.deployment_policy import production_mode


@dataclass(frozen=True)
class V2Principal:
    user_id: str
    role: str
    authenticated: bool


def _auth_required() -> bool:
    return production_mode() or os.getenv("V2_AUTH_REQUIRED", "false").strip().lower() in {"1", "true", "yes"}


def _database_course_scope() -> bool:
    # Production cannot opt back into the shared demo allowlist.
    mode = os.getenv("V2_COURSE_AUTH_MODE", "environment").strip().lower()
    if mode not in {"environment", "database"}:
        raise HTTPException(status_code=503, detail="course_auth_configuration_invalid")
    return production_mode() or mode == "database"


def _student_courses() -> frozenset[str]:
    values = (item.strip() for item in os.getenv("V2_STUDENT_COURSES", "artificial_intelligence").split(","))
    return frozenset(item for item in values if item)


def _teacher_courses() -> frozenset[str]:
    # Explicit development-only compatibility with existing demos.
    values = os.getenv("V2_TEACHER_COURSES", "artificial_intelligence").split(",")
    return frozenset(item.strip() for item in values if item.strip())


def _principal_from_authorization(authorization: str | None) -> V2Principal | None:
    if not authorization:
        return None
    from backend.app.api.v1.auth import _get_session, _parse_bearer_token

    session = _get_session(_parse_bearer_token(authorization))
    return V2Principal(user_id=session.account, role=session.role, authenticated=True)


def resolve_v2_principal(
    *, authorization: str | None, requested_user_id: str, requested_course_id: str
) -> tuple[V2Principal, str]:
    """Resolve trusted identity and reject spoofed identity/course access."""
    principal = _principal_from_authorization(authorization)
    requested_user_id = requested_user_id.strip() or "anonymous"
    course_id = requested_course_id.strip()
    if not course_id:
        raise HTTPException(status_code=422, detail="course_id_required")
    if principal is None:
        if _auth_required():
            raise HTTPException(status_code=401, detail="authorization_required")
        principal = V2Principal(user_id=requested_user_id, role="demo", authenticated=False)
    elif requested_user_id not in {"anonymous", principal.user_id}:
        raise HTTPException(status_code=403, detail="user_identity_mismatch")
    if _database_course_scope():
        if not principal.authenticated:
            raise HTTPException(status_code=401, detail="authorization_required")
        from backend.app.repositories.auth_repo import AuthRepository
        try:
            permitted = AuthRepository().has_course(principal.user_id, course_id)
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="course_auth_storage_unavailable") from exc
    else:
        courses = _teacher_courses() if principal.role in {"teacher", "admin"} else _student_courses()
        permitted = course_id in courses
    if not permitted:
        raise HTTPException(status_code=403, detail="course_access_denied")
    return principal, course_id


def authorize_run_owner(*, principal: V2Principal, run_user_id: str) -> None:
    """Students may resume only their own run; teachers may review any run."""
    if not principal.authenticated:
        raise HTTPException(status_code=401, detail="authorization_required")
    if principal.role in {"teacher", "admin"}:
        return
    if run_user_id != principal.user_id:
        raise HTTPException(status_code=403, detail="run_access_denied")


def authorize_reviewer(*, principal: V2Principal) -> None:
    if not principal.authenticated:
        raise HTTPException(status_code=401, detail="authorization_required")
    if principal.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer_role_required")
