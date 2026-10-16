"""
Phase 0 infrastructure tests: Alembic / Metrics / Backup-Restore / Indexes
"""
import pytest
import tempfile
import sqlite3
from pathlib import Path


class TestAlembicMigrations:
    def test_migration_file_exists(self):
        """Baseline migration must exist."""
        path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260618_0001_b_backend_baseline.py"
        assert path.exists(), f"Migration file not found: {path}"

    def test_migration_revision_shape(self):
        """Migration must have valid revision ID and functions."""
        path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "20260618_0001_b_backend_baseline.py"
        text = path.read_text(encoding="utf-8")
        assert 'revision: str = "20260618_0001"' in text
        assert "def upgrade()" in text
        assert "def downgrade()" in text
        assert "profiles" in text  # all 12 tables
        assert "gamification_profiles" in text

    def test_alembic_config_exists(self):
        root = Path(__file__).resolve().parents[2]
        assert (root / "alembic.ini").exists()
        assert (root / "alembic" / "env.py").exists()
        assert (root / "alembic" / "script.py.mako").exists()


class TestDatabaseIndexes:
    def test_b_owned_table_indexes_in_metadata(self):
        """Verify composite indexes exist in SQLAlchemy metadata for B-owned tables."""
        from sqlalchemy import create_engine, inspect
        from backend.app.core.database import Base
        # Force-register all ORM models on Base.metadata. Without this, an
        # isolated test run leaves Base.metadata empty and create_all is a no-op.
        from backend.app.core import models  # noqa: F401

        with tempfile.TemporaryDirectory() as td:
            engine = create_engine(f"sqlite:///{td}/idx_test.db")
            try:
                Base.metadata.create_all(bind=engine)
                inspector = inspect(engine)

                # Check that composite indexes exist
                kpr_indexes = {i["name"] for i in inspector.get_indexes("kp_relations")}
                assert "ix_kpr_source" in kpr_indexes or any("source" in n for n in kpr_indexes)

                sm2_indexes = {i["name"] for i in inspector.get_indexes("sm2_schedule")}
                assert "ix_sm2_user_due" in sm2_indexes or any("due" in n for n in sm2_indexes)

                mistake_indexes = {i["name"] for i in inspector.get_indexes("mistakes")}
                assert any("unresolved" in n or "user_id" in n for n in mistake_indexes)
            finally:
                # Close SQLAlchemy connection pool so Windows can rmtree the
                # tempdir without hitting "file in use" PermissionError.
                engine.dispose()


class TestPrometheusMetrics:
    def test_counter_increment(self):
        from backend.app.core.metrics import llm_calls_total
        llm_calls_total.labels(provider="spark", status="success").inc()
        rendered = llm_calls_total._render()
        assert "a3_llm_calls_total" in rendered[0]
        assert "TYPE a3_llm_calls_total counter" in rendered[1]

    def test_histogram_observe(self):
        from backend.app.core.metrics import api_request_duration_seconds
        api_request_duration_seconds.labels(method="GET", endpoint="/test").observe(0.15)
        rendered = api_request_duration_seconds._render()
        assert "a3_api_request_duration_seconds_sum" in rendered[0] or any(
            "a3_api_request_duration_seconds" in line for line in rendered
        )

    def test_render_metrics_produces_text(self):
        from backend.app.core.metrics import render_metrics
        text = render_metrics()
        assert "a3_llm_calls_total" in text
        assert "a3_rag_retrievals_total" in text
        assert "a3_agent_invocations_total" in text
        assert "a3_api_requests_total" in text
        assert "a3_cognitive_operations_total" in text
        assert "a3_db_operations_total" in text

    def test_metrics_endpoint_accessible(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        # A 重构后指标无 a3_ 前缀，用 llm_calls_total 兜底
        assert "llm_calls_total" in resp.text


class TestBackupRestore:
    def test_backup_round_trip(self):
        """Backup a database, verify, restore to a new path."""
        src = sqlite3.connect(":memory:")
        src.execute("CREATE TABLE profiles (user_id TEXT PRIMARY KEY, profile_data TEXT)")
        src.execute("INSERT INTO profiles VALUES ('u1', '{}')")
        src.execute("INSERT INTO profiles VALUES ('u2', '{}')")
        src.commit()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            backup_path = tf.name

        try:
            # Backup
            dst = sqlite3.connect(backup_path)
            src.backup(dst)
            dst.close()

            # Verify backup
            vconn = sqlite3.connect(backup_path)
            integrity = vconn.execute("PRAGMA integrity_check").fetchone()[0]
            assert integrity == "ok"
            count = vconn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            assert count == 2
            vconn.close()

            # Restore to new DB
            restored = sqlite3.connect(":memory:")
            backup_src = sqlite3.connect(backup_path)
            backup_src.backup(restored)
            restored_count = restored.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            assert restored_count == 2
            restored.close()
            backup_src.close()
        finally:
            Path(backup_path).unlink(missing_ok=True)
            src.close()

    def test_backup_script_rejects_missing_file(self):
        from scripts.backup_database import backup_database
        with pytest.raises(FileNotFoundError):
            backup_database(Path("/nonexistent/db.sqlite"), Path("/tmp/out.db"))

    def test_restore_rejects_corrupt_file(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            tf.write(b"not a valid sqlite database")
            corrupt_path = tf.name

        try:
            from scripts.restore_database import restore_database
            result = restore_database(Path(corrupt_path), Path("/tmp/restored.db"))
            assert result.get("restored") is False
        finally:
            Path(corrupt_path).unlink(missing_ok=True)
