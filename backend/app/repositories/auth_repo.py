"""Persistent session and course authorization operations; no bearer token logging."""
import hashlib
import time

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from backend.app.core.database import SessionLocal
from backend.app.core.models import AuthSessionRecord, CourseGrantRecord, LoginAttemptRecord, RegisteredAccountRecord


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class CredentialsChanged(ValueError):
    pass


class AuthRepository:
    LOGIN_WINDOW_SECONDS = 900
    LOGIN_MAX_FAILURES = 5

    @staticmethod
    def _account_digest(account):
        return hashlib.sha256(account.strip().lower().encode("utf-8")).hexdigest()

    def check_login(self, account):
        with SessionLocal() as db:
            row = db.get(LoginAttemptRecord, self._account_digest(account))
            return row is None or row.locked_until <= time.time()

    def failed_login(self, account):
        digest = self._account_digest(account)
        for attempt in range(2):
            try:
                with SessionLocal.begin() as db:
                    now = time.time()
                    row = db.get(LoginAttemptRecord, digest, with_for_update=True)
                    if row is None:
                        db.add(LoginAttemptRecord(account_hash=digest, window_start=now,
                                                  failures=1, locked_until=0))
                    else:
                        if now - row.window_start >= self.LOGIN_WINDOW_SECONDS:
                            row.window_start = now
                            row.failures = 0
                            row.locked_until = 0
                        row.failures += 1
                        if row.failures >= self.LOGIN_MAX_FAILURES:
                            row.locked_until = now + self.LOGIN_WINDOW_SECONDS
                return
            except IntegrityError:
                if attempt:
                    raise

    def successful_login(self, account):
        with SessionLocal.begin() as db:
            db.execute(delete(LoginAttemptRecord).where(
                LoginAttemptRecord.account_hash == self._account_digest(account)))

    def cleanup_expired(self):
        """Remove expired opaque sessions and stale throttle counters."""
        now = time.time()
        with SessionLocal.begin() as db:
            db.execute(delete(AuthSessionRecord).where(AuthSessionRecord.expires_at <= now))
            db.execute(delete(LoginAttemptRecord).where(
                LoginAttemptRecord.window_start < now - self.LOGIN_WINDOW_SECONDS,
                LoginAttemptRecord.locked_until <= now))

    def issue(self, *, token, account, role, display_name, expires_at, builtin=False,
              expected_hash=None, upgraded_hash=None):
        with SessionLocal.begin() as db:
            db.execute(delete(AuthSessionRecord).where(AuthSessionRecord.expires_at <= time.time()))
            if not builtin:
                # Lock the account with a conditional update in the same transaction
                # as session creation. A racing reset/delete cannot revive old credentials.
                changed = db.execute(update(RegisteredAccountRecord).where(
                    RegisteredAccountRecord.account == account,
                    RegisteredAccountRecord.password_hash == expected_hash,
                    RegisteredAccountRecord.role.in_([role, "admin", "counselor"] if role == "teacher" else [role]),
                ).values(password_hash=upgraded_hash or expected_hash))
                if changed.rowcount != 1:
                    raise CredentialsChanged("credentials_changed")
            db.add(AuthSessionRecord(token_hash=token_digest(token), account=account,
                role=role, display_name=display_name, expires_at=expires_at, builtin=builtin))

    def get(self, token):
        with SessionLocal() as db:
            row = db.get(AuthSessionRecord, token_digest(token))
            if row is None:
                return None
            return dict(account=row.account, role=row.role, display_name=row.display_name,
                        expires_at=row.expires_at, builtin=row.builtin)

    def revoke(self, token):
        with SessionLocal.begin() as db:
            db.execute(delete(AuthSessionRecord).where(AuthSessionRecord.token_hash == token_digest(token)))

    def has_course(self, account, course_id):
        with SessionLocal() as db:
            return db.get(CourseGrantRecord, (account, course_id)) is not None

    def grant_course(self, account, course_id):
        with SessionLocal.begin() as db:
            # The trusted CLI requires a real registered account (never a client-supplied role).
            if db.get(RegisteredAccountRecord, account, with_for_update=True) is None:
                raise ValueError("account_not_found")
            if db.get(CourseGrantRecord, (account, course_id)) is None:
                db.add(CourseGrantRecord(account=account, course_id=course_id, granted_at=time.time()))

    def revoke_course(self, account, course_id):
        with SessionLocal.begin() as db:
            db.execute(delete(CourseGrantRecord).where(
                CourseGrantRecord.account == account, CourseGrantRecord.course_id == course_id))
