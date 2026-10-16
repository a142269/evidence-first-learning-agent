"""Optional local read-only MCP adapter for trusted staff tooling.

The server process receives scope from a trusted launcher via environment,
never from tool arguments. It is not an HTTP authentication endpoint and is
not exposed to the student-facing learning graph.
"""
from __future__ import annotations

import os

from backend.app.services.v2_learning_tools import ToolContext, V2LearningTools

try:
    from mcp.server import MCPServer
except ImportError as exc:  # optional pinned dependency
    raise RuntimeError("Install requirements-mcp.txt to use the local adapter") from exc


def _scope() -> ToolContext:
    values = {name: os.environ.get(name, "").strip() for name in
              ("V2_MCP_RUN_ID", "V2_MCP_USER_ID", "V2_MCP_COURSE_ID")}
    if not all(values.values()):
        raise RuntimeError("trusted_mcp_scope_required")
    return ToolContext(run_id=values["V2_MCP_RUN_ID"], user_id=values["V2_MCP_USER_ID"],
                       course_id=values["V2_MCP_COURSE_ID"], role="planner")


def create_server(*, broker: V2LearningTools | None = None) -> MCPServer:
    scope = _scope()
    if broker is None:
        from backend.app.api.v2.learning_runs import LearningRuntime
        broker = V2LearningTools(LearningRuntime().retrieve)
    server = MCPServer("Triple-U V2 course read-only")

    async def _call(name: str, arguments: dict) -> dict:
        result = await broker.call(scope, name, arguments)
        if result.status not in {"success", "no_data"}:
            return {"status": result.status, "data": None}
        return {"status": result.status, "data": result.data}

    @server.tool()
    async def get_learning_profile() -> dict:
        """Read the current learner's saved preferences and course mastery."""
        return await _call("get_learning_profile", {})

    @server.tool()
    async def get_recent_mistakes() -> dict:
        """Read recent mistakes for the trusted course scope."""
        return await _call("get_recent_mistakes", {})

    @server.tool()
    async def get_prerequisites(knowledge_point_id: str) -> dict:
        """Read prerequisite concepts for one course knowledge point."""
        return await _call("get_prerequisites", {"knowledge_point_id": knowledge_point_id})

    # Search uses the tutor role internally; the scope is still fixed at launch.
    @server.tool()
    async def search_course_evidence(query: str) -> dict:
        """Read cited course evidence within the trusted course scope."""
        tutor_scope = ToolContext(run_id=scope.run_id, user_id=scope.user_id,
                                  course_id=scope.course_id, role="tutor")
        result = await broker.call(tutor_scope, "search_course_evidence", {"query": query})
        return {"status": result.status, "data": result.data if result.status in
                {"success", "no_data"} else None}

    return server


if __name__ == "__main__":
    create_server().run(transport="stdio")
