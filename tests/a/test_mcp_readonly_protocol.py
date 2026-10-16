"""Optional pinned-SDK protocol checks for the local read-only adapter."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

pytest.importorskip("mcp")

from mcp.client import ClientSession  # noqa: E402
from mcp.client._memory import InMemoryTransport  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

from backend.app.core import database  # noqa: E402
from backend.app.core.models import CourseGrantRecord  # noqa: E402
from backend.app.mcp_readonly import create_server  # noqa: E402
from backend.app.repositories.auth_repo import AuthRepository  # noqa: E402
from backend.app.services.v2_learning_tools import (  # noqa: E402
    TOOL_VERSION, ToolResult, V2LearningTools,
)


def _payload(result) -> dict:
    return json.loads(result.content[0].text)


class _Broker:
    def __init__(self):
        self.calls = []

    async def call(self, scope, name, arguments):
        self.calls.append((scope, name, arguments))
        if name == "search_course_evidence":
            status, data = "success", [{"chunk_id": "own-course-1"}]
        elif name == "get_prerequisites" and not arguments.get("knowledge_point_id"):
            status, data = "invalid_args", None
        else:
            status, data = "no_data", None
        return ToolResult(name, TOOL_VERSION, status, data, 0, "protocol-test")


@pytest.mark.asyncio
async def test_mcp_client_discovers_and_calls_scoped_readonly_tools(monkeypatch):
    monkeypatch.setenv("V2_MCP_RUN_ID", "test-run")
    monkeypatch.setenv("V2_MCP_USER_ID", "alice")
    monkeypatch.setenv("V2_MCP_COURSE_ID", "course-a")
    broker = _Broker()
    async with InMemoryTransport(create_server(broker=broker)) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert names == {"get_learning_profile", "get_recent_mistakes",
                             "get_prerequisites", "search_course_evidence"}
            assert _payload(await client.call_tool("search_course_evidence", {"query": "RAG"})) == {
                "status": "success", "data": [{"chunk_id": "own-course-1"}]}
            assert _payload(await client.call_tool("get_prerequisites", {
                "knowledge_point_id": ""})) == {"status": "invalid_args", "data": None}
    assert all(scope.run_id == "test-run" and scope.user_id == "alice" and
               scope.course_id == "course-a" for scope, _, _ in broker.calls)


@pytest.mark.asyncio
async def test_mcp_stdio_client_rechecks_revoked_course_grant(tmp_path, monkeypatch):
    db_path = tmp_path / "mcp.sqlite"
    database_url = f"sqlite:///{db_path.as_posix()}"
    previous_url = database.DATABASE_URL
    database.configure_database(database_url)
    database.init_db()
    monkeypatch.setenv("V2_MCP_RUN_ID", "test-run")
    monkeypatch.setenv("V2_MCP_USER_ID", "alice")
    monkeypatch.setenv("V2_MCP_COURSE_ID", "course-a")
    monkeypatch.setenv("V2_COURSE_AUTH_MODE", "database")
    try:
        with database.SessionLocal.begin() as db:
            db.add(CourseGrantRecord(account="alice", course_id="course-a"))
        broker = V2LearningTools(retrieve=lambda query, course: [
            {"chunk_id": "course-a-1", "course_id": course}])
        async with InMemoryTransport(create_server(broker=broker)) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                assert _payload(await client.call_tool("search_course_evidence", {
                    "query": "RAG"}))["status"] == "success"
                AuthRepository().revoke_course("alice", "course-a")
                assert _payload(await client.call_tool("search_course_evidence", {
                    "query": "RAG"})) == {"status": "denied", "data": None}

        params = StdioServerParameters(command=sys.executable,
            args=["-m", "backend.app.mcp_readonly"],
            cwd=str(Path(__file__).resolve().parents[2]), env={
                "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
                "DATABASE_URL": database_url, "A3_OFFLINE_DEMO": "1",
                "V2_COURSE_AUTH_MODE": "database", "V2_MCP_RUN_ID": "test-run",
                "V2_MCP_USER_ID": "alice", "V2_MCP_COURSE_ID": "course-a",
            })
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                assert len((await client.list_tools()).tools) == 4
                assert _payload(await client.call_tool("get_learning_profile", {})) == {
                    "status": "denied", "data": None}
    finally:
        database.engine.dispose()
        database.configure_database(previous_url)
