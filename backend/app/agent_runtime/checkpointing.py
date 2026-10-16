"""Optional PostgreSQL checkpoint lifecycle for the LangGraph flagship flow."""
from __future__ import annotations

import logging
import os
from typing import Any

LOGGER = logging.getLogger(__name__)
_context: Any | None = None
_checkpointer: Any | None = None


def _postgres_uri(database_url: str) -> str:
    """Translate SQLAlchemy's psycopg URL into the URI LangGraph expects."""
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


async def initialize_checkpointer() -> bool:
    """Start an async saver only for PostgreSQL; SQLite demos remain stateless."""
    global _context, _checkpointer
    if _checkpointer is not None:
        return True
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        return False
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        context = AsyncPostgresSaver.from_conn_string(_postgres_uri(database_url))
        checkpointer = await context.__aenter__()
        await checkpointer.setup()
        _context = context
        _checkpointer = checkpointer
        LOGGER.info("LangGraph PostgreSQL checkpointer initialized")
        return True
    except Exception as exc:  # pragma: no cover - deployment dependency failure
        reason = "windows_event_loop" if "proactor" in str(exc).lower() else "database_interface"
        LOGGER.warning("LangGraph PostgreSQL checkpointer unavailable (%s:%s)", type(exc).__name__, reason)
        return False


def get_checkpointer() -> Any | None:
    return _checkpointer


async def shutdown_checkpointer() -> None:
    """Close the underlying pool when FastAPI shuts down."""
    global _context, _checkpointer
    if _context is not None:
        await _context.__aexit__(None, None, None)
    _context = None
    _checkpointer = None
