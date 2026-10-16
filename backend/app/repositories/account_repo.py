from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import delete
from sqlalchemy.exc import OperationalError

from backend.app.core.database import SessionLocal
from backend.app.core.models import AuthSessionRecord, CourseGrantRecord, RegisteredAccountRecord


@dataclass(frozen=True)
class StoredAccount:
    account: str
    password_hash: str
    role: str
    display_name: str


class AccountRepository:
    """持久化注册账号；内置演示账号仍由 auth 模块统一管理。"""

    def __init__(self, session_factory: Callable = SessionLocal):
        self.session_factory = session_factory

    def get(self, account: str) -> StoredAccount | None:
        try:
            with self.session_factory() as db:
                row = db.get(RegisteredAccountRecord, account)
                if row is None:
                    return None
                return StoredAccount(
                    account=row.account,
                    password_hash=row.password_hash,
                    role=row.role,
                    display_name=row.display_name,
                )
        except OperationalError:
            from backend.app.core.deployment_policy import production_mode
            if production_mode():
                raise
            # 首次启动、数据库尚未初始化时由注册操作创建表；登录仍可使用内置账号。
            return None

    def upsert(self, record: StoredAccount, *, revoke_sessions: bool = False, create_only: bool = False) -> StoredAccount:
        with self.session_factory() as db:
            try:
                row = None if create_only else db.get(RegisteredAccountRecord, record.account, with_for_update=True)
                credentials_changed = row is not None and (
                    row.password_hash != record.password_hash or row.role != record.role
                )
                if row is None:
                    row = RegisteredAccountRecord(account=record.account)
                    db.add(row)
                row.password_hash = record.password_hash
                row.role = record.role
                row.display_name = record.display_name
                if revoke_sessions or credentials_changed:
                    db.execute(delete(AuthSessionRecord).where(AuthSessionRecord.account == record.account))
                db.commit()
                return StoredAccount(
                    account=row.account,
                    password_hash=row.password_hash,
                    role=row.role,
                    display_name=row.display_name,
                )
            except Exception:
                db.rollback()
                raise

    def delete(self, account: str) -> bool:
        with self.session_factory() as db:
            try:
                row = db.get(RegisteredAccountRecord, account, with_for_update=True)
                if row is None:
                    return False
                db.execute(delete(AuthSessionRecord).where(AuthSessionRecord.account == account))
                db.execute(delete(CourseGrantRecord).where(CourseGrantRecord.account == account))
                db.delete(row)
                db.commit()
                return True
            except Exception:
                db.rollback()
                raise
