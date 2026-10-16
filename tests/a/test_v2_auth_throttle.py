import time

import pytest
from fastapi import HTTPException

from backend.app.api.v1 import auth
from backend.app.core import database
from backend.app.core.models import AuthSessionRecord, LoginAttemptRecord
from backend.app.repositories.auth_repo import AuthRepository, token_digest


@pytest.fixture(autouse=True)
def isolated_auth(tmp_path, monkeypatch):
    previous = database.DATABASE_URL
    monkeypatch.setenv("APP_ENV", "development")
    database.configure_database(f"sqlite:///{(tmp_path / 'auth.db').as_posix()}")
    database.init_db()
    yield
    database.engine.dispose()
    database.configure_database(previous)


def test_login_throttle_persists_failures_and_unlocks_after_window():
    for _ in range(5):
        with pytest.raises(HTTPException) as error:
            auth.login(auth.LoginRequest(account="teacher", password="wrong"))
        assert error.value.status_code == 401
    with pytest.raises(HTTPException) as error:
        auth.login(auth.LoginRequest(account="teacher", password="123456"))
    assert error.value.status_code == 429
    repository = AuthRepository()
    with database.SessionLocal.begin() as db:
        row = db.get(LoginAttemptRecord, repository._account_digest("teacher"))
        assert row.failures == 5
        row.window_start = time.time() - 901
        row.locked_until = time.time() - 1
    assert auth.login(auth.LoginRequest(account="teacher", password="123456")).user.role == "teacher"
    with database.SessionLocal() as db:
        assert db.get(LoginAttemptRecord, repository._account_digest("teacher")) is None


def test_expired_session_cleanup_removes_stale_rows():
    repository = AuthRepository()
    repository.issue(token="expired-token", account="teacher", role="teacher",
                     display_name="Teacher", expires_at=time.time() - 1, builtin=True)
    with database.SessionLocal() as db:
        assert db.get(AuthSessionRecord, token_digest("expired-token")) is not None
    repository.cleanup_expired()
    with database.SessionLocal() as db:
        assert db.get(AuthSessionRecord, token_digest("expired-token")) is None
