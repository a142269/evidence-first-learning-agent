"""QWEN-221: one tool catalog, deny-by-default runtime, unified audit.

Every case here is offline: the execution surface is replaced by a spy wherever a
refusal has to be proven, so a refused call proves itself by never being reached
and no test needs a database, a model, or the network.
"""
from __future__ import annotations

import ast
from dataclasses import fields
import time
from pathlib import Path

import pytest

from backend.app.services.agent_tools.registry import (
    ToolRegistry, _request_hash, _traced_call, get_tool_trace, reset_tool_trace,
)
from backend.app.services import v2_learning_tools
from backend.app.services.tool_audit import (
    AUDIT_EVENT_KEYS, MAX_EVENTS, ToolAuditLog, build_event, get_tool_audit_log,
    record_tool_event, reset_tool_audit_log,
)
from backend.app.services.tool_catalog import (
    GRAPH_ROLES, INTERNAL_ROLE, ROLE_PERMISSIONS, TOOL_CATALOG, TOOL_VERSION_V1,
    TOOL_VERSION_V2, ToolArgs, decide_access, matrix_violations, source_specs, tools_for_role,
)
from backend.app.services.v2_learning_tools import (
    DEFAULT_SEARCH_TIMEOUT_SECONDS, DEFAULT_TIMEOUT_SECONDS, ToolContext, ToolResult,
    V2LearningTools,
)

MCP_SOURCE = Path(__file__).resolve().parents[2] / "backend" / "app" / "mcp_readonly.py"

V1_NAMES = [spec.name for spec in source_specs("v1")]
V2_NAMES = [spec.name for spec in source_specs("v2")]

# Verbatim pre-catalog whitelist (v2_learning_tools.ROLE_TOOLS before 221).
# The catalog must reproduce it exactly: nothing newly permitted, nothing newly revoked.
BASELINE_ROLE_TOOLS = {
    "planner": frozenset({"get_learning_profile", "get_recent_mistakes", "get_prerequisites"}),
    "tutor": frozenset({"search_course_evidence"}),
    "practice": frozenset(),
    "reviewer": frozenset(),
}

# Arguments that are legal for each tool, so the matrix sweep only varies the role.
VALID_ARGS = {"search_course_evidence": {"query": "RAG"},
              "get_prerequisites": {"knowledge_point_id": "kp-1"}}


class _Executor:
    """Stands in for V2LearningTools._execute and records whether it was reached."""

    def __init__(self, *, data=None, error: BaseException | None = None, delay: float = 0.0):
        self.calls = []
        self._data = data
        self._error = error
        self._delay = delay

    def __call__(self, context, name, args):
        self.calls.append((context, name, args))
        if self._delay:
            time.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return self._data if self._data is not None else [{"chunk_id": f"{name}-1"}]


def _tools(*, retrieve=None, executor=None, **timeouts) -> V2LearningTools:
    tools = V2LearningTools(retrieve or (lambda query, course: [{"chunk_id": "own-1"}]), **timeouts)
    if executor is not None:
        tools._execute = executor
    return tools


def _context(role: str, *, run_id="run-1", user_id="alice", course_id="course-a") -> ToolContext:
    return ToolContext(run_id=run_id, user_id=user_id, course_id=course_id, role=role)


def _events() -> list[dict]:
    return get_tool_audit_log().recent(limit=500)


@pytest.fixture(autouse=True)
def _isolated_logs():
    reset_tool_audit_log()
    reset_tool_trace()
    yield
    reset_tool_audit_log()
    reset_tool_trace()


def test_catalog_is_the_only_declaration_of_the_nine_tools():
    assert V1_NAMES == ["lookup_knowledge_point", "query_knowledge_graph", "execute_code",
                        "search_resources", "generate_learning_materials"]
    assert V2_NAMES == ["search_course_evidence", "get_learning_profile",
                        "get_recent_mistakes", "get_prerequisites"]
    assert set(TOOL_CATALOG) == set(V1_NAMES) | set(V2_NAMES)
    assert len(TOOL_CATALOG) == 9
    for name, spec in TOOL_CATALOG.items():
        assert spec.name == name
        assert spec.source in {"v1", "v2"}
        assert spec.version == (TOOL_VERSION_V2 if spec.source == "v2" else TOOL_VERSION_V1)
        assert spec.description and spec.permission_key
        assert spec.allowed_roles, f"{name} would be unreachable by anyone"
        assert isinstance(spec.side_effect, bool)


def test_baseline_permission_matrix_equals_the_pre_catalog_whitelist():
    assert matrix_violations() == []
    assert {role: tools_for_role(role) for role in GRAPH_ROLES} == BASELINE_ROLE_TOOLS
    assert tools_for_role(INTERNAL_ROLE) == frozenset(V1_NAMES)
    for role in GRAPH_ROLES:
        for name in V1_NAMES:
            assert decide_access(role, name).allowed is False
    for name in V1_NAMES:
        assert decide_access(INTERNAL_ROLE, name).allowed is True
    for name in V2_NAMES:
        # The internal V1 role never gains the learner-scoped read-only tools.
        assert decide_access(INTERNAL_ROLE, name).allowed is False
        assert decide_access(INTERNAL_ROLE, name).reason == "role_not_allowed"


async def test_matrix_refuses_every_unlisted_role_tool_pair_without_execution():
    refusals = []
    for role in GRAPH_ROLES:
        for name in sorted(TOOL_CATALOG):
            executor = _Executor()
            result = await _tools(executor=executor).call(
                _context(role), name, VALID_ARGS.get(name, {}))
            decision = decide_access(role, name)
            if name in BASELINE_ROLE_TOOLS[role]:
                assert decision.allowed is True
                assert result.status == "success"
                assert executor.calls[-1][1] == name
            else:
                assert decision.reason == "role_not_allowed"
                assert result.status == "denied" and result.data is None
                assert result.audit()["result_count"] == 0
                assert executor.calls == []
                refusals.append(name)
    assert len(refusals) == 4 * 9 - sum(len(tools) for tools in BASELINE_ROLE_TOOLS.values())
    counts = get_tool_audit_log().counts()
    assert counts["total"] == 36
    assert counts["refused"] == len(refusals)
    assert counts["by_decision"] == {"granted": 36 - len(refusals), "role_not_allowed": len(refusals)}


async def test_unknown_tool_and_unknown_role_are_refused_at_the_runtime_gate():
    executor = _Executor()
    tools = _tools(executor=executor)
    dropped = await tools.call(_context("planner"), "drop_course_grants", {})
    assert dropped.status == "denied" and dropped.data is None
    assert dropped.version == TOOL_VERSION_V2
    student = await tools.call(_context("student"), "get_learning_profile", {})
    assert student.status == "denied"
    assert executor.calls == []
    assert [e["decision"] for e in _events()] == ["unknown_role", "unknown_tool"]
    unknown = [e for e in _events() if e["decision"] == "unknown_tool"][0]
    assert unknown["tool"] == "drop_course_grants"
    assert unknown["source"] == unknown["version"] == unknown["permission_key"] == ""
    assert unknown["side_effect"] is False and unknown["timeout_seconds"] is None


async def test_refusals_keep_the_stable_error_surface():
    result = await _tools().call(_context("tutor"), "get_learning_profile", {})
    assert {f.name for f in fields(ToolResult)} == {
        "name", "version", "status", "data", "latency_ms", "request_hash"}
    assert result.audit() == {"tool": "get_learning_profile", "version": TOOL_VERSION_V2,
                              "status": "denied", "latency_ms": result.latency_ms,
                              "request_hash": result.request_hash, "result_count": 0}


async def test_illegal_arguments_are_refused_by_the_catalog_schema():
    executor = _Executor()
    tools = _tools(executor=executor)
    cases = [
        ("tutor", "search_course_evidence", {"query": "RAG", "user_id": "mallory"}),
        ("tutor", "search_course_evidence", {"query": ""}),
        ("tutor", "search_course_evidence", {"query": "   "}),
        ("tutor", "search_course_evidence", {"query": "x" * 501}),
        ("tutor", "search_course_evidence", {}),
        ("planner", "get_learning_profile", {"user_id": "alice"}),
        ("planner", "get_prerequisites", {"knowledge_point_id": 7}),
        ("planner", "get_prerequisites", {"knowledge_point_id": ""}),
    ]
    for role, name, arguments in cases:
        result = await tools.call(_context(role), name, arguments)
        assert result.status == "invalid_args", (name, arguments)
        assert result.data is None
    assert executor.calls == []
    events = _events()
    assert len(events) == len(cases)
    for event in events:
        assert (event["status"], event["decision"], event["reason"]) == (
            "invalid_args", "granted", "args_schema_rejected")
        assert "mallory" not in str(event) and "user_id" not in str(event)


async def test_empty_scope_is_a_refusal_never_a_wider_default():
    executor = _Executor()
    tools = _tools(executor=executor)
    for user_id, course_id in (("", "course-a"), ("alice", ""), ("", "")):
        result = await tools.call(
            _context("tutor", user_id=user_id, course_id=course_id), "search_course_evidence",
            {"query": "RAG"})
        assert result.status == "denied"
    assert executor.calls == []
    assert {e["reason"] for e in _events()} == {"missing_scope"}


async def test_timeout_and_truncation_limits_come_from_the_specs():
    assert DEFAULT_SEARCH_TIMEOUT_SECONDS == TOOL_CATALOG["search_course_evidence"].timeout_seconds
    assert DEFAULT_SEARCH_TIMEOUT_SECONDS > 20
    assert TOOL_CATALOG["search_course_evidence"].timeout_class == "search"
    assert DEFAULT_TIMEOUT_SECONDS == TOOL_CATALOG["get_learning_profile"].timeout_seconds

    timed_out = await _tools(executor=_Executor(delay=0.05), search_timeout_seconds=0.001).call(
        _context("tutor"), "search_course_evidence", {"query": "RAG"})
    assert timed_out.status == "timeout" and timed_out.data is None
    assert _events()[0]["reason"] == "timeout"

    limit = TOOL_CATALOG["search_course_evidence"].max_result_items
    eight = _tools(retrieve=lambda query, course: [{"chunk_id": f"c{index}"} for index in range(8)])
    truncated = await eight.call(_context("tutor"), "search_course_evidence", {"query": "RAG"})
    assert len(truncated.data) == limit == 5

    failed = await _tools(executor=_Executor(error=RuntimeError("database is locked"))).call(
        _context("planner"), "get_learning_profile", {})
    assert failed.status == "failed" and failed.data is None
    event = _events()[0]
    assert event["reason"] == "execution_failed"
    assert "locked" not in str(event)

    revoked = await _tools(executor=_Executor(error=PermissionError("course_access_denied"))).call(
        _context("planner"), "get_learning_profile", {})
    assert revoked.status == "denied"
    assert _events()[0]["reason"] == "course_access_denied"


async def test_one_unified_audit_event_per_call_whatever_the_outcome():
    calls = [
        ("tutor", "search_course_evidence", {"query": "RAG"}, "success", "granted"),
        ("tutor", "get_learning_profile", {}, "denied", "role_not_allowed"),
        ("planner", "drop_course_grants", {}, "denied", "unknown_tool"),
        ("planner", "get_recent_mistakes", {"user_id": "alice"}, "invalid_args", "granted"),
        ("tutor", "search_course_evidence", {"query": "RAG"}, "denied", "granted"),
        ("planner", "get_learning_profile", {}, "failed", "granted"),
    ]
    for index, (role, name, arguments, _, _) in enumerate(calls):
        await _tools(executor=_Executor(
            error=RuntimeError("boom") if index == 5 else None)).call(
            _context(role, user_id="" if index == 4 else "alice"), name, arguments)

    counts = get_tool_audit_log().counts()
    assert counts["total"] == 6 and counts["refused"] == 2 and counts["granted"] == 4
    assert counts["by_status"] == {"success": 1, "denied": 3, "invalid_args": 1, "failed": 1}
    assert counts["by_tool"] == {"search_course_evidence": 2, "get_learning_profile": 2,
                                 "drop_course_grants": 1, "get_recent_mistakes": 1}
    events = _events()
    assert all(set(event) == set(AUDIT_EVENT_KEYS) for event in events)
    assert len(AUDIT_EVENT_KEYS) == 14
    assert [(event["tool"], event["status"], event["decision"]) for event in events] == \
        list(reversed([(name, status, decision) for _, name, _, status, decision in calls]))
    assert [d["tool"] for d in get_tool_audit_log().recent(tool="get_learning_profile")] == \
        ["get_learning_profile"] * 2
    assert get_tool_audit_log().recent(decision="unknown_tool")[0]["status"] == "denied"


async def test_audit_metadata_is_derived_from_the_catalog_not_the_caller():
    await _tools().call(_context("tutor", run_id="run-42"), "search_course_evidence", {"query": "RAG"})
    event = _events()[0]
    assert (event["source"], event["version"], event["permission_key"]) == (
        "v2", TOOL_VERSION_V2, "course:evidence:search")
    assert event["side_effect"] is False and event["timeout_seconds"] == 30.0
    assert event["run_id"] == "run-42" and event["session_id"] == "" and event["role"] == "tutor"
    assert len(event["request_hash"]) == 16
    int(event["request_hash"], 16)


def test_v1_surface_executes_only_catalog_registered_tools():
    ran = []
    for name in V1_NAMES:
        assert _traced_call(name, lambda: ran.append(name)) is None
    assert ran == V1_NAMES

    handler = []
    refused = _traced_call("query_student_passwords", lambda: handler.append(1), kp_name="alice")
    assert refused == {"success": False, "error": "tool_access_denied: unknown_tool",
                       "tool": "query_student_passwords"}
    assert handler == []
    event = _events()[0]
    assert (event["tool"], event["status"], event["decision"]) == (
        "query_student_passwords", "denied", "unknown_tool")
    assert event["session_id"] == ""
    trace = get_tool_trace().recent()[0]
    assert trace["error"] == "tool_access_denied: unknown_tool"
    assert trace["args"] == {} and trace["success"] is False


def test_v1_granted_calls_keep_their_error_surface_and_record_class_names_only():
    assert _traced_call("execute_code", lambda: {"ok": True}) == {"ok": True}
    failed = _traced_call("search_resources",
                          lambda: (_ for _ in ()).throw(ValueError("resource index offline")))
    assert failed == {"success": False, "error": "ValueError: resource index offline",
                      "tool": "search_resources"}
    events = _events()
    assert [event["status"] for event in events] == ["failed", "success"]
    assert events[0]["reason"] == "ValueError"
    assert "offline" not in str(events)
    execute = [event for event in events if event["tool"] == "execute_code"][0]
    assert execute["side_effect"] is True and execute["timeout_seconds"] is None
    assert (execute["source"], execute["version"]) == ("v1", TOOL_VERSION_V1)
    assert _request_hash("execute_code", {"b": 2, "a": 1}) == _request_hash("execute_code", {"a": 1, "b": 2})
    assert _request_hash("execute_code", {"a": 1}) != _request_hash("execute_code", {"a": 2})


def test_registry_openai_export_is_a_projection_of_the_catalog():
    registry = ToolRegistry()
    assert [item.schema.name for item in registry.list_a_tools()] == V1_NAMES
    assert registry.to_openai_tools() == [
        {"type": "function", "function": {
            "name": spec.name, "description": spec.description,
            "parameters": {"type": "object", "properties": spec.parameters,
                           "required": list(spec.required)}}}
        for spec in source_specs("v1")]


def test_mcp_adapter_exposes_exactly_the_catalog_mcp_tools():
    exposed = {}
    for node in ast.walk(ast.parse(MCP_SOURCE.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for decorator in node.decorator_list:
                func = decorator.func if isinstance(decorator, ast.Call) else decorator
                if isinstance(func, ast.Attribute) and func.attr == "tool":
                    exposed[node.name] = [argument.arg for argument in node.args.args]
    assert set(exposed) == set(V2_NAMES)
    assert all(TOOL_CATALOG[name].mcp_exposed for name in exposed)
    assert not any(TOOL_CATALOG[name].mcp_exposed for name in V1_NAMES)
    for name, arguments in exposed.items():
        allowed = set(TOOL_CATALOG[name].args_model.model_fields)
        assert set(arguments) <= allowed, (name, arguments)


def test_the_scattered_role_whitelist_and_schema_map_are_gone():
    # 221 replaces them; keeping a copy here would mean a second place to forget.
    assert not hasattr(v2_learning_tools, "ROLE_TOOLS")
    assert not hasattr(v2_learning_tools, "SCHEMAS")
    assert v2_learning_tools.TOOL_VERSION == TOOL_VERSION_V2
    for name, value in vars(v2_learning_tools).items():
        if isinstance(value, dict) and value and set(value) <= set(TOOL_CATALOG):
            assert name == "TOOL_CATALOG", f"{name} is a second tool-name registry"


def test_v2_arguments_use_pydantic_models_while_v1_keeps_json_schema():
    for spec in source_specs("v2"):
        assert issubclass(spec.args_model, ToolArgs)
        assert not spec.parameters and not spec.required
    for spec in source_specs("v1"):
        assert spec.args_model is None
        assert spec.parameters and isinstance(spec.required, tuple) and spec.required
        for key in spec.required:
            assert key in spec.parameters, f"{spec.name} requires an undeclared {key}"


def test_roles_without_grants_and_principal_roles_are_documented():
    assert ROLE_PERMISSIONS["practice"] == ROLE_PERMISSIONS["reviewer"] == frozenset()
    assert set(ROLE_PERMISSIONS) == set(GRAPH_ROLES) | {INTERNAL_ROLE}
    # Principal roles (student/teacher/admin) are an HTTP access concern; they are
    # not tool roles, so naming one at the tool runtime is a refusal, not a grant.
    for principal in ("student", "teacher", "admin"):
        assert principal not in ROLE_PERMISSIONS
        for name in sorted(TOOL_CATALOG):
            assert decide_access(principal, name).reason == "unknown_role"


def test_audit_api_accepts_no_argument_values_and_refuses_shape_drift():
    spec = TOOL_CATALOG["get_learning_profile"]
    with pytest.raises(TypeError):
        record_tool_event(tool="x", spec=spec, role="planner", status="denied", decision="granted",
                          latency_ms=1, request_hash="hash", query="secret question")
    event = build_event(tool="x", spec=spec, role="planner", status="denied", decision="granted",
                        latency_ms=1, request_hash="hash")
    log = ToolAuditLog(max_size=4)
    assert MAX_EVENTS == 500
    for index in range(6):
        log.record({**event, "tool": f"tool-{index}"})
    assert log.counts()["total"] == 4
    assert log.recent()[0]["tool"] == "tool-5"
    with pytest.raises(ValueError, match="shape drift"):
        log.record({**event, "prompt": "learner essay"})
    with pytest.raises(ValueError, match="shape drift"):
        log.record({key: value for key, value in event.items() if key != "reason"})
    assert log.counts()["total"] == 4
