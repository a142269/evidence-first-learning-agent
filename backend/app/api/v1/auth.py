from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.app.core.passwords import hash_password, needs_rehash, verify_password
from backend.app.core.deployment_policy import production_mode
from backend.app.repositories.auth_repo import AuthRepository, CredentialsChanged

router = APIRouter(prefix="/auth", tags=["auth"])

# 角色体系统一为 student / teacher 两类（2026-07-16 平台化改造）。
# * 旧 counselor 概念由 teacher 取代；
# * admin 与 teacher 功能完全一致，两种身份合并：admin 账号仍可登录，
#   但会话角色一律归一化为 teacher，前后端不再区分管理员端。
Role = Literal["student", "teacher"]

_LEGACY_ROLE_MAP = {"counselor": "teacher", "admin": "teacher"}


def normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    role = role.strip().lower()
    return _LEGACY_ROLE_MAP.get(role, role)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mask_account(account: str) -> str:
    if len(account) <= 2:
        return account
    return f"{account[:2]}***{account[-1]}"


class LoginRequest(BaseModel):
    account: str
    password: str
    # 兼容旧值 counselor（登录时映射为 teacher）
    role: Literal["student", "teacher", "admin", "counselor"] | None = None
    remember: bool = False


class AuthUser(BaseModel):
    account: str
    display_name: str
    role: Role


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: str
    user: AuthUser
    profile_initialized: bool = False
    profile_completeness: float = 0.0


@dataclass
class _AccountRecord:
    account: str
    password_hash: str
    role: str
    display_name: str


@dataclass
class _SessionRecord:
    token: str
    account: str
    role: str
    display_name: str
    expires_at: datetime


DEFAULT_ACCOUNTS: dict[str, _AccountRecord] = {
    "student": _AccountRecord(
        account=os.getenv("AUTH_STUDENT_ACCOUNT", "demo-student-1"),
        password_hash=_sha256(os.getenv("AUTH_STUDENT_PASSWORD", "123456")),
        role="student",
        display_name="杜同学",
    ),
    "student_compare": _AccountRecord(
        account=os.getenv("AUTH_COMPARE_STUDENT_ACCOUNT", "demo-student-21"),
        password_hash=_sha256(os.getenv("AUTH_COMPARE_STUDENT_PASSWORD", "123456")),
        role="student",
        display_name="林同学",
    ),
    "teacher": _AccountRecord(
        account=os.getenv("AUTH_TEACHER_ACCOUNT", "teacher"),
        password_hash=_sha256(os.getenv("AUTH_TEACHER_PASSWORD", "123456")),
        role="teacher",
        display_name="王老师",
    ),
    # 旧演示账号 counselor 继续可登录，角色映射为 teacher
    "counselor": _AccountRecord(
        account=os.getenv("AUTH_COUNSELOR_ACCOUNT", "counselor"),
        password_hash=_sha256(os.getenv("AUTH_COUNSELOR_PASSWORD", "123456")),
        role="teacher",
        display_name="辅导员账号",
    ),
    "admin": _AccountRecord(
        account=os.getenv("AUTH_ADMIN_ACCOUNT", "admin"),
        password_hash=_sha256(os.getenv("AUTH_ADMIN_PASSWORD", "123456")),
        role="admin",
        display_name="教务管理账号",
    ),
}

# Compatibility for older callers that clear this mapping. Never an auth authority.
_SESSIONS: dict[str, _SessionRecord] = {}

# Compatibility cache for older callers; authentication always reads the database.
_REGISTERED_ACCOUNTS: dict[str, _AccountRecord] = {}


def _load_persisted_account(account: str) -> _AccountRecord | None:
    from backend.app.repositories.account_repo import AccountRepository

    stored = AccountRepository().get(account)
    if stored is None:
        return None
    return _AccountRecord(
        account=stored.account,
        password_hash=stored.password_hash,
        role=stored.role,
        display_name=stored.display_name,
    )


def _save_registered_account(record: _AccountRecord, *, revoke_sessions: bool = False, create_only: bool = False) -> None:
    # 正常服务启动时已建表；这里兜底保证 CLI / 单测直接调用注册接口也可用。
    from backend.app.core.database import init_db
    from backend.app.repositories.account_repo import AccountRepository, StoredAccount

    if not production_mode():
        init_db()
    AccountRepository().upsert(StoredAccount(
        account=record.account,
        password_hash=record.password_hash,
        role=record.role,
        display_name=record.display_name,
    ), revoke_sessions=revoke_sessions, create_only=create_only)


def _remove_persisted_account(account: str) -> bool:
    from backend.app.repositories.account_repo import AccountRepository

    return AccountRepository().delete(account)


def _find_account(account: str) -> _AccountRecord | None:
    """Read registered credentials from DB; built-in accounts are development only."""
    matched = next(
        (item for item in DEFAULT_ACCOUNTS.values() if item.account == account),
        None,
    ) if not production_mode() else None
    if matched is not None:
        return matched
    try:
        persisted = _load_persisted_account(account)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="auth_storage_unavailable") from exc
    if persisted is not None:
        _REGISTERED_ACCOUNTS[account] = persisted
    return persisted


def is_default_account(account: str) -> bool:
    """Return whether an account is a built-in account that must not be deleted."""
    normalized = account.strip()
    return any(item.account == normalized for item in DEFAULT_ACCOUNTS.values())


def remove_registered_student_account(account: str) -> bool:
    """Remove a runtime student account and invalidate all of its sessions.

    Student learning records are persisted separately in SQLite and are deleted
    by the teacher student-data service. Built-in demo/teacher accounts are
    deliberately protected here as a second line of defence.
    """
    normalized = account.strip()
    if not normalized or is_default_account(normalized):
        return False

    record = _load_persisted_account(normalized)
    if record is not None and normalize_role(record.role) != "student":
        return False

    removed = _REGISTERED_ACCOUNTS.pop(normalized, None) is not None
    removed = _remove_persisted_account(normalized) or removed
    stale_tokens = [
        token for token, session in _SESSIONS.items()
        if session.account == normalized
    ]
    for token in stale_tokens:
        _SESSIONS.pop(token, None)
    return removed


def restore_student_account(account: str, password: str) -> _AccountRecord:
    """由教师恢复已有学习数据对应的学生登录账号，并使后续重启可持续登录。"""
    normalized = account.strip()
    if not normalized or is_default_account(normalized):
        raise ValueError("account_not_recoverable")
    if len(password.strip()) < 6:
        raise ValueError("password_too_short")

    from backend.app.repositories.profile_repo import ProfileRepository

    profile = ProfileRepository().get(normalized)
    if not profile:
        raise ValueError("student_data_not_found")

    existing = _find_account(normalized)
    if existing is not None and normalize_role(existing.role) != "student":
        raise ValueError("student_role_required")

    record = _AccountRecord(
        account=normalized,
        password_hash=hash_password(password.strip()),
        role="student",
        display_name=(
            existing.display_name
            if existing
            else str(profile.get("display_name") or profile.get("nickname") or normalized)
        ),
    )
    _save_registered_account(record, revoke_sessions=True)
    _REGISTERED_ACCOUNTS[normalized] = record
    for token, session in list(_SESSIONS.items()):
        if session.account == normalized:
            _SESSIONS.pop(token, None)
    return record


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="authorization_required")

    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="authorization_invalid")

    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(status_code=401, detail="authorization_invalid")
    return token


def _get_session(token: str) -> _SessionRecord:
    try:
        stored = AuthRepository().get(token)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="auth_storage_unavailable") from exc
    if stored is None or (stored["builtin"] and production_mode()):
        raise HTTPException(status_code=401, detail="session_not_found")
    expires_at = datetime.fromtimestamp(stored["expires_at"], timezone.utc)
    if expires_at <= _utc_now():
        raise HTTPException(status_code=401, detail="session_expired")
    return _SessionRecord(token=token, account=stored["account"], role=stored["role"],
                          display_name=stored["display_name"], expires_at=expires_at)


def _issue_session(record: _AccountRecord, expires_at: datetime, *, password: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    builtin = not production_mode() and any(record is item for item in DEFAULT_ACCOUNTS.values())
    upgraded = hash_password(password) if password is not None and not builtin and needs_rehash(record.password_hash) else None
    try:
        AuthRepository().issue(token=token, account=record.account,
            role=normalize_role(record.role) or "student", display_name=record.display_name,
            expires_at=expires_at.timestamp(), builtin=builtin,
            expected_hash=record.password_hash, upgraded_hash=upgraded)
    except CredentialsChanged as exc:
        raise HTTPException(status_code=401, detail="credentials_changed") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="auth_storage_unavailable") from exc
    return token


def _to_user(record: _AccountRecord | _SessionRecord) -> AuthUser:
    return AuthUser(
        account=record.account,
        display_name=record.display_name,
        role=normalize_role(record.role) or "student",
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    account = payload.account.strip()
    password = payload.password.strip()
    if not account or not password:
        raise HTTPException(status_code=400, detail="account_password_required")

    repository = AuthRepository()
    try:
        if not repository.check_login(account):
            raise HTTPException(status_code=429, detail="login_rate_limited")
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="auth_storage_unavailable") from exc

    def reject(detail: str) -> None:
        try:
            repository.failed_login(account)
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="auth_storage_unavailable") from exc
        raise HTTPException(status_code=401, detail=detail)

    matched = _find_account(account)
    if matched is None:
        reject("account_not_found")

    # admin 归一化为 teacher（_LEGACY_ROLE_MAP），教师/管理员入口完全等价
    requested_role = normalize_role(payload.role)
    account_role = normalize_role(matched.role)
    role_compatible = requested_role == account_role
    if requested_role and not role_compatible:
        reject("role_mismatch")

    if not verify_password(password, matched.password_hash):
        reject("password_invalid")

    ttl = timedelta(days=7 if payload.remember else 1)
    expires_at = _utc_now() + ttl
    token = _issue_session(matched, expires_at, password=password)
    try:
        repository.successful_login(account)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="auth_storage_unavailable") from exc

    return LoginResponse(
        access_token=token,
        expires_at=expires_at.isoformat(),
        user=_to_user(matched),
    )


class RegisterRequest(BaseModel):
    account: str
    password: str
    display_name: str = ""
    role: Literal["student", "teacher"] = "student"
    profile_answers: dict[str, Any] = Field(default_factory=dict)


@router.post("/register", response_model=LoginResponse)
def register(payload: RegisterRequest) -> LoginResponse:
    """Persist a registered account and issue a restart-safe opaque session."""
    if production_mode() and payload.role != "student":
        raise HTTPException(status_code=403, detail="teacher_registration_disabled")
    account = payload.account.strip()
    password = payload.password.strip()
    if not account or not password:
        raise HTTPException(status_code=400, detail="account_password_required")
    if len(account) < 3 or len(account) > 32:
        raise HTTPException(status_code=400, detail="account_length_invalid")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="password_too_short")
    if _find_account(account) is not None:
        raise HTTPException(status_code=409, detail="account_exists")

    display_name = payload.display_name.strip() or account
    record = _AccountRecord(
        account=account,
        password_hash=hash_password(password),
        role=payload.role,
        display_name=display_name,
    )
    try:
        _save_registered_account(record, create_only=True)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="account_exists") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="account_persistence_failed") from exc
    _REGISTERED_ACCOUNTS[account] = record

    profile_initialized = False
    profile_completeness = 0.0
    if record.role == "student":
        try:
            from backend.app.repositories.profile_repo import ProfileRepository
            from backend.app.services.onboarding_profile import build_initial_profile
            from backend.app.services.profile_schema import calculate_profile_completeness

            initial_profile = build_initial_profile(
                payload.profile_answers,
                display_name=display_name,
            )
            ProfileRepository().replace(
                account,
                initial_profile,
                source="registration_onboarding",
            )
            filled, _total, profile_completeness = calculate_profile_completeness(
                initial_profile
            )
            profile_initialized = filled > 0
        except Exception as exc:
            _REGISTERED_ACCOUNTS.pop(account, None)
            _remove_persisted_account(account)
            raise HTTPException(
                status_code=500,
                detail="profile_initialization_failed",
            ) from exc

    expires_at = _utc_now() + timedelta(days=1)
    token = _issue_session(record, expires_at)
    return LoginResponse(
        access_token=token,
        expires_at=expires_at.isoformat(),
        user=_to_user(record),
        profile_initialized=profile_initialized,
        profile_completeness=profile_completeness,
    )


@router.get("/me", response_model=AuthUser)
def me(authorization: str | None = Header(default=None)) -> AuthUser:
    token = _parse_bearer_token(authorization)
    session = _get_session(token)
    return _to_user(session)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _parse_bearer_token(authorization)
    session = _get_session(token)
    try:
        AuthRepository().revoke(token)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="auth_storage_unavailable") from exc
    _SESSIONS.pop(token, None)
    return {"status": "ok", "account": _mask_account(session.account)}
