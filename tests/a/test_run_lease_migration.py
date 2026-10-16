"""Lease migration preserves historical runs on fresh and existing SQLite DBs."""
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.mark.parametrize("existing", [False, True])
def test_lease_upgrade_roundtrip_preserves_run_data(tmp_path, existing):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261013_0007_run_execution_leases.py"
    spec = importlib.util.spec_from_file_location("lease_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")
    try:
        with engine.begin() as connection:
            if existing:
                connection.execute(text("CREATE TABLE agent_runs (id VARCHAR(128) PRIMARY KEY, status VARCHAR(32), metadata JSON, created_at FLOAT)"))
                connection.execute(text("INSERT INTO agent_runs VALUES ('historical', 'completed', '{\"answer\":\"keep\"}', 123)"))
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                module.upgrade()  # Compatible with prior create_all / already present columns.
                if not existing:
                    connection.execute(text("INSERT INTO agent_runs (id, status, metadata, created_at) VALUES ('historical', 'completed', '{\"answer\":\"keep\"}', 123)"))
                assert {"execution_id", "lease_expires_at"}.issubset({col["name"] for col in inspect(connection).get_columns("agent_runs")})
                module.downgrade()
                assert "execution_id" not in {col["name"] for col in inspect(connection).get_columns("agent_runs")}
                assert connection.execute(text("SELECT status, metadata, created_at FROM agent_runs WHERE id='historical'")).one() == ("completed", '{"answer":"keep"}', 123)
                module.upgrade()
                assert "ix_agent_run_lease" in {item["name"] for item in inspect(connection).get_indexes("agent_runs")}
    finally:
        engine.dispose()
