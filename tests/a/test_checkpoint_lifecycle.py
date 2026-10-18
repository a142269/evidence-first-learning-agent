import asyncio

import pytest

from backend.app.agent_runtime import checkpointing


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("private connection string"), asyncio.CancelledError()])
async def test_failed_setup_closes_entered_context(monkeypatch, caplog, failure):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    class Context:
        closed = False

        async def __aenter__(self):
            return self

        async def setup(self):
            raise failure

        async def __aexit__(self, *args):
            self.closed = True

    context = Context()
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setattr(checkpointing, "_context", None)
    monkeypatch.setattr(checkpointing, "_checkpointer", None)
    monkeypatch.setattr(AsyncPostgresSaver, "from_conn_string", lambda _: context)
    if isinstance(failure, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            await checkpointing.initialize_checkpointer()
    else:
        assert await checkpointing.initialize_checkpointer() is False
    assert context.closed
    assert checkpointing.get_checkpointer() is None
    assert "private connection string" not in caplog.text


@pytest.mark.asyncio
async def test_successful_setup_closes_on_shutdown(monkeypatch):
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    class Context:
        closed = False

        async def __aenter__(self):
            return self

        async def setup(self):
            pass

        async def __aexit__(self, *args):
            self.closed = True

    context = Context()
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/db")
    monkeypatch.setattr(checkpointing, "_context", None)
    monkeypatch.setattr(checkpointing, "_checkpointer", None)
    monkeypatch.setattr(AsyncPostgresSaver, "from_conn_string", lambda _: context)
    assert await checkpointing.initialize_checkpointer() is True
    assert checkpointing.get_checkpointer() is context
    await checkpointing.shutdown_checkpointer()
    assert context.closed
    assert checkpointing.get_checkpointer() is None
