"""QWEN-201: the memory migration upgrades twice, downgrades clean and re-upgrades."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

MEMORY_TABLES = {"user_memories", "memory_events"}


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261023_0012_user_memories.py"
    spec = importlib.util.spec_from_file_location("user_memory_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ops(connection):
    """A fresh Operations context per phase; the CM object is not re-enterable."""
    return Operations.context(MigrationContext.configure(connection))


@pytest.mark.parametrize("existing", [False, True])
def test_memory_migration_roundtrip(tmp_path, existing):
    module = _migration()
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")
    if existing:
        # init_db() builds tables with create_all, so upgrade() must detect them and skip.
        from backend.app.core import models  # noqa: F401
        from backend.app.core.database import Base
        Base.metadata.create_all(bind=engine)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE unrelated_probe (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO unrelated_probe VALUES (7)"))

            with _ops(connection):
                module.upgrade()
                module.upgrade()
            inspector = inspect(connection)
            assert MEMORY_TABLES.issubset(set(inspector.get_table_names()))
            assert {"id", "user_id", "kind", "content", "source_type", "source_run_id",
                    "confidence", "expires_at", "status", "created_at",
                    "updated_at"} == {column["name"] for column in
                                      inspector.get_columns("user_memories")}
            assert {"id", "memory_id", "action", "actor", "reason",
                    "created_at"} == {column["name"] for column in
                                      inspector.get_columns("memory_events")}
            assert "uq_user_memory_active" in {index["name"] for index in
                                               inspector.get_indexes("user_memories")}

            connection.execute(text("INSERT INTO user_memories (id, user_id, kind, content, "
                                    "source_type, status, created_at, updated_at) VALUES "
                                    "('m-1', 'learner-9', 'weak_point', 'keep', "
                                    "'rule_extraction', 'active', 1, 1)"))
            connection.execute(text("INSERT INTO memory_events (memory_id, action, actor, "
                                    "reason, created_at) VALUES ('m-1', 'confirmed', "
                                    "'teacher-1', 'role:teacher', 1)"))
            assert connection.execute(text("SELECT count(*) FROM memory_events")).scalar() == 1

            with _ops(connection):
                module.downgrade()
            assert MEMORY_TABLES.isdisjoint(set(inspect(connection).get_table_names()))
            assert connection.execute(text("SELECT id FROM unrelated_probe")).scalar() == 7

            with _ops(connection):
                module.upgrade()
            assert MEMORY_TABLES.issubset(set(inspect(connection).get_table_names()))
            assert connection.execute(text("SELECT count(*) FROM user_memories")).scalar() == 0
            assert connection.execute(text("SELECT id FROM unrelated_probe")).scalar() == 7
    finally:
        engine.dispose()


def test_partial_unique_index_only_guards_active_rows(tmp_path):
    """The dedupe rule is one live memory per (user, kind); retired rows must not block it."""
    module = _migration()
    engine = create_engine(f"sqlite:///{(tmp_path / 'dedupe.db').as_posix()}")
    insert = text("INSERT INTO user_memories (id, user_id, kind, content, source_type, status, "
                  "created_at, updated_at) VALUES (:memory_id, 'learner-9', 'weak_point', "
                  ":body, 'rule_extraction', :state, 1, 1)")
    try:
        with engine.begin() as connection:
            with _ops(connection):
                module.upgrade()
            connection.execute(insert, {"memory_id": "m-1", "body": "first", "state": "active"})
            with pytest.raises(IntegrityError) as blocked:
                connection.execute(insert, {"memory_id": "m-2", "body": "second",
                                            "state": "active"})
            assert "UNIQUE constraint failed" in str(blocked.value)
            # A retired row shares the (user, kind) slot: the guard sees active rows only.
            connection.execute(insert, {"memory_id": "m-0", "body": "oldest", "state": "revoked"})
            # Revoking the live row is what frees the slot for the next one.
            connection.execute(text("UPDATE user_memories SET status = 'revoked' "
                                    "WHERE id = 'm-1'"))
            connection.execute(insert, {"memory_id": "m-3", "body": "newest", "state": "active"})
            assert connection.execute(text(
                "SELECT count(*) FROM user_memories WHERE status = 'active'")).scalar() == 1
            assert connection.execute(text("SELECT count(*) FROM user_memories")).scalar() == 3
    finally:
        engine.dispose()
