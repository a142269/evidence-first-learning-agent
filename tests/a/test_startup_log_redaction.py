import logging

import pytest


@pytest.mark.asyncio
async def test_startup_warnings_do_not_include_exception_secrets(monkeypatch, caplog):
    from backend.app import main
    from backend.app.agent_runtime import checkpointing, run_leases
    from backend.app.core import database, observability
    from backend.app.services import rag_service

    secret = "startup-private-token-must-not-appear"

    def fail(*args, **kwargs):
        raise RuntimeError(secret)

    async def initialize():
        return None

    monkeypatch.setattr(main, "validate_deployment", lambda: None)
    monkeypatch.setattr(observability, "configure_observability", lambda: None)
    monkeypatch.setattr(database, "init_db", lambda: None)
    monkeypatch.setattr(checkpointing, "initialize_checkpointer", initialize)
    monkeypatch.setattr(run_leases, "expire_batch", lambda: None)
    monkeypatch.setattr(rag_service, "get_rag_service", fail)
    monkeypatch.setattr(database, "SessionLocal", fail)
    monkeypatch.setattr(main, "_ensure_course_resources", fail)
    monkeypatch.setattr(main, "_scan_and_register_existing_artifacts", fail)

    with caplog.at_level(logging.WARNING, logger=main.LOGGER.name):
        await main._warmup()
    assert secret not in caplog.text
    assert caplog.text.count("RuntimeError") == 4


def test_resource_database_errors_do_not_log_exception_contents(monkeypatch, caplog):
    from backend.app.api.v1 import resources

    secret = "database-private-token-must-not-appear"

    def fail():
        raise RuntimeError(secret)

    monkeypatch.setattr(resources, "_db_available", True)
    monkeypatch.setattr(resources, "_resources", {})
    monkeypatch.setattr(resources, "SessionLocal", fail)
    with caplog.at_level(logging.WARNING, logger=resources.logger.name):
        resources._load_from_db()
        resources.persist_resource({"id": "test-resource"})
        resources.get_resource_dict("not-cached")
        resources.delete_resource_record("not-cached")
    assert secret not in caplog.text
    assert caplog.text.count("RuntimeError") == 4
