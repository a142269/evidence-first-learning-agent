from datetime import timedelta
import hashlib
import importlib

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from backend.app.api.v1 import auth
from backend.app.api.v2 import access
from backend.app.core import database
from backend.app.core.models import AuthSessionRecord
from backend.app.core.passwords import hash_password, verify_password
from backend.app.repositories.account_repo import AccountRepository, StoredAccount
from backend.app.repositories.auth_repo import AuthRepository, CredentialsChanged, token_digest


@pytest.fixture(autouse=True)
def isolated_auth(tmp_path, monkeypatch):
    previous = database.DATABASE_URL
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("V2_AUTH_REQUIRED", "true")
    monkeypatch.setenv("V2_COURSE_AUTH_MODE", "database")
    database.configure_database(f"sqlite:///{(tmp_path / 'auth.db').as_posix()}")
    database.init_db()
    yield
    auth._REGISTERED_ACCOUNTS.clear()
    auth._SESSIONS.clear()
    database.engine.dispose()
    database.configure_database(previous)


def account(name="alice", role="student", legacy=False):
    encoded = hashlib.sha256(b"test-password").hexdigest() if legacy else hash_password("test-password")
    AccountRepository().upsert(StoredAccount(name, encoded, role, name), create_only=True)
    return encoded


def login(name="alice"):
    return auth.login(auth.LoginRequest(account=name, password="test-password"))


def test_session_survives_module_reload_and_stores_digest_only():
    account()
    token = login().access_token
    with database.SessionLocal() as db:
        rows = db.scalars(select(AuthSessionRecord)).all()
        assert len(rows) == 1
        assert rows[0].token_hash == token_digest(token)
        assert token not in str(rows[0].__dict__)
    importlib.reload(auth)
    assert auth._get_session(token).account == "alice"
    auth.logout(f"Bearer {token}")
    importlib.reload(auth)
    with pytest.raises(HTTPException) as error:
        auth._get_session(token)
    assert error.value.status_code == 401


def test_legacy_password_upgrade_is_atomic_with_login():
    old = account(legacy=True)
    with pytest.raises(HTTPException):
        auth.login(auth.LoginRequest(account="alice", password="wrong"))
    assert AccountRepository().get("alice").password_hash == old
    token = login().access_token
    upgraded = AccountRepository().get("alice").password_hash
    assert upgraded.startswith("pbkdf2_sha256$600000$")
    assert verify_password("test-password", upgraded)
    assert auth._get_session(token).account == "alice"


def test_salts_differ_and_malformed_hashes_fail_closed():
    first, second = hash_password("same"), hash_password("same")
    assert first != second and len(first) <= 128
    assert verify_password("same", first) and not verify_password("wrong", first)
    for value in ["bad", "pbkdf2_sha256$999999999$aa$bb", "pbkdf2_sha256$600000$zz$dd", "x$600000$aa$bb"]:
        assert not verify_password("same", value)


def test_expired_session_is_rejected():
    account()
    record = auth._find_account("alice")
    token = auth._issue_session(record, auth._utc_now() - timedelta(seconds=1))
    with pytest.raises(HTTPException) as error:
        auth._get_session(token)
    assert error.value.detail == "session_expired"


def test_reset_invalidates_all_sessions_and_stale_login_cannot_reissue():
    old = account()
    first, second = login().access_token, login().access_token
    AccountRepository().upsert(StoredAccount("alice", hash_password("new-password"), "student", "alice"), revoke_sessions=True)
    for token in [first, second]:
        with pytest.raises(HTTPException):
            auth._get_session(token)
    with pytest.raises(CredentialsChanged):
        AuthRepository().issue(token="stale", account="alice", role="student", display_name="alice",
            expires_at=9999999999, expected_hash=old)
    assert AuthRepository().get("stale") is None
    # Old in-process account cache cannot restore the old password.
    with pytest.raises(HTTPException):
        login()


def test_duplicate_registration_cannot_overwrite_existing_credentials():
    old = account()
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        AccountRepository().upsert(StoredAccount("alice", hash_password("attacker"), "teacher", "other"), create_only=True)
    assert AccountRepository().get("alice").password_hash == old


def test_delete_revokes_sessions_and_course_grants():
    account()
    token = login().access_token
    AuthRepository().grant_course("alice", "ai")
    assert auth.remove_registered_student_account("alice")
    assert not AuthRepository().has_course("alice", "ai")
    with pytest.raises(HTTPException):
        auth._get_session(token)


def resolve(token, course="ai"):
    return access.resolve_v2_principal(authorization=f"Bearer {token}",
        requested_user_id="anonymous", requested_course_id=course)


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_course_grants_isolate_accounts_and_revocation_applies_next_request(role):
    account("alice", role)
    account("bob", role)
    alice, bob = login("alice").access_token, login("bob").access_token
    AuthRepository().grant_course("alice", "ai")
    assert resolve(alice)[0].user_id == "alice"
    with pytest.raises(HTTPException) as error:
        resolve(bob)
    assert error.value.detail == "course_access_denied"
    AuthRepository().revoke_course("alice", "ai")
    with pytest.raises(HTTPException):
        resolve(alice)


def test_production_ignores_demo_allowlists_and_rejects_teacher_self_registration(monkeypatch):
    account()
    token = login().access_token
    demo = auth.login(auth.LoginRequest(account="teacher", password="123456")).access_token
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("V2_COURSE_AUTH_MODE", "environment")
    monkeypatch.setenv("V2_STUDENT_COURSES", "ai")
    with pytest.raises(HTTPException) as error:
        resolve(token)
    assert error.value.status_code == 403
    with pytest.raises(HTTPException):
        auth._get_session(demo)
    with pytest.raises(HTTPException) as error:
        auth.register(auth.RegisterRequest(account="new-teacher", password="password", role="teacher"))
    assert error.value.detail == "teacher_registration_disabled"


def test_storage_failures_have_safe_errors_without_cache_fallback(monkeypatch):
    account()
    token = login().access_token
    def fail(*args, **kwargs):
        raise OperationalError("sensitive-sql", {}, Exception("secret-connection-string"))
    monkeypatch.setattr(AuthRepository, "get", fail)
    with pytest.raises(HTTPException) as error:
        auth._get_session(token)
    assert error.value.status_code == 503
    assert error.value.detail == "auth_storage_unavailable"


def test_session_issuance_cannot_commit_legacy_upgrade_on_failure(monkeypatch):
    old = account(legacy=True)
    from sqlalchemy.orm import Session
    original = Session.add
    def fail_session(self, value, **kwargs):
        if isinstance(value, AuthSessionRecord):
            raise OperationalError("insert", {}, Exception("private"))
        return original(self, value, **kwargs)
    monkeypatch.setattr(Session, "add", fail_session)
    with pytest.raises(HTTPException) as error:
        login()
    assert error.value.status_code == 503
    assert AccountRepository().get("alice").password_hash == old


def test_role_change_invalidates_existing_session_even_without_explicit_flag():
    encoded = account(role="teacher")
    token = login().access_token
    AccountRepository().upsert(StoredAccount("alice", encoded, "student", "alice"))
    with pytest.raises(HTTPException):
        auth._get_session(token)


def test_student_restore_revokes_prior_tokens():
    from backend.app.repositories.profile_repo import ProfileRepository
    account()
    ProfileRepository().replace("alice", {"display_name": "Alice"}, source="test")
    token = login().access_token
    auth.restore_student_account("alice", "replacement-password")
    with pytest.raises(HTTPException):
        auth._get_session(token)
    assert auth.login(auth.LoginRequest(account="alice", password="replacement-password")).user.account == "alice"


def test_database_course_mode_rejects_anonymous_even_with_optional_auth(monkeypatch):
    monkeypatch.setenv("V2_AUTH_REQUIRED", "false")
    with pytest.raises(HTTPException) as error:
        access.resolve_v2_principal(authorization=None, requested_user_id="alice", requested_course_id="ai")
    assert error.value.status_code == 401


def test_course_storage_failure_is_not_an_allowlist_fallback(monkeypatch):
    account()
    token = login().access_token
    def fail(*args):
        raise OperationalError("secret-sql", {}, Exception("private"))
    monkeypatch.setattr(AuthRepository, "has_course", fail)
    with pytest.raises(HTTPException) as error:
        resolve(token)
    assert error.value.detail == "course_auth_storage_unavailable"
    assert error.value.status_code == 503


def test_trusted_cli_provisions_teacher_and_grants_without_overwriting(monkeypatch):
    from scripts.manage_access import main
    monkeypatch.setenv("DATABASE_URL", database.DATABASE_URL)
    monkeypatch.setattr("getpass.getpass", lambda _: "test-only-long-password")
    main(["create-teacher", "instructor"])
    response = auth.login(auth.LoginRequest(account="instructor", password="test-only-long-password"))
    assert response.user.role == "teacher"
    main(["grant", "instructor", "--course", "ai"])
    assert resolve(response.access_token)[0].role == "teacher"
    main(["revoke", "instructor", "--course", "ai"])
    with pytest.raises(HTTPException):
        resolve(response.access_token)
    with pytest.raises(SystemExit) as error:
        main(["create-teacher", "instructor"])
    assert error.value.code == 1
    assert auth._get_session(response.access_token).role == "teacher"
