import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.mark.parametrize("existing", [False, True])
def test_auth_migration_preserves_accounts_and_supports_create_all(tmp_path, existing):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261014_0008_auth_sessions.py"
    spec = importlib.util.spec_from_file_location("auth_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")
    try:
        with engine.begin() as connection:
            if existing:
                from backend.app.core.models import RegisteredAccountRecord, AuthSessionRecord, CourseGrantRecord
                for model in (RegisteredAccountRecord, AuthSessionRecord, CourseGrantRecord):
                    model.__table__.create(connection)
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                connection.execute(text("INSERT INTO registered_accounts VALUES ('existing', 'keep-hash', 'student', 'keep-name', 1, 2)"))
                migration.upgrade()
                assert {"auth_sessions", "course_grants"}.issubset(inspect(connection).get_table_names())
                migration.downgrade()
                assert connection.execute(text("SELECT password_hash FROM registered_accounts WHERE account='existing'")).scalar() == "keep-hash"
                migration.upgrade()
                assert {"ix_auth_sessions_account", "ix_auth_sessions_expires_at"}.issubset({x["name"] for x in inspect(connection).get_indexes("auth_sessions")})
    finally:
        engine.dispose()
