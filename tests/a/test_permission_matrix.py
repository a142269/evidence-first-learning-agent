"""QWEN-321: the V2 route permission matrix - coverage, well-formedness, refusals.

The matrix is a declaration layer: runtime authorisation is unchanged, so the
tests pin (a) every served V2 route being declared, (b) malformed declarations
failing verification, (c) the role/course/run/tool dimensions of each policy,
and (d) real refusal paths on the reviewer-only admin surface.
"""
from __future__ import annotations

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.v2 import access, permission_matrix, run_usage_admin
from backend.app.core import database
from backend.app.core.models import AgentRunRecord
from backend.app.services.tool_catalog import source_specs

EXPECTED_ROUTES = {
    ("POST", "/api/v2/learning-runs/stream"),
    ("POST", "/api/v2/learning-runs/enqueue"),
    ("GET", "/api/v2/learning-runs/{run_id}"),
    ("POST", "/api/v2/learning-runs/{run_id}/cancel"),
    ("POST", "/api/v2/learning-runs/{run_id}/continue"),
    ("GET", "/api/v2/learning-runs/{run_id}/events"),
    ("POST", "/api/v2/learning-runs/{run_id}/resume"),
    ("POST", "/api/v2/learning-runs/{run_id}/reconcile"),
    ("GET", "/api/v2/admin/run-usage"),
    ("GET", "/api/v2/admin/run-usage/{run_id}"),
}


def _main_app():
    from backend.app.main import app

    return app


def test_every_v2_route_is_declared_and_verification_is_clean():
    app = _main_app()
    actual = permission_matrix.actual_v2_routes(app)
    assert actual == EXPECTED_ROUTES
    assert actual == set(permission_matrix.POLICY_BY_ROUTE)
    assert permission_matrix.verify_route_policies(app) == []


def test_route_count_is_pinned_at_ten():
    assert len(permission_matrix.ROUTE_POLICIES) == 10


def test_undeclared_route_fails_verification():
    probe = APIRouter()

    @probe.get("/api/v2/learning-runs/{run_id}/export")
    async def export_run(run_id: str):  # pragma: no cover - never executed
        return {"run_id": run_id}

    probe_app = FastAPI()
    probe_app.include_router(probe)
    problems = permission_matrix.verify_route_policies(probe_app)
    assert "undeclared_route: GET /api/v2/learning-runs/{run_id}/export" in problems


def test_stale_declaration_fails_verification():
    app = _main_app()
    ghost = permission_matrix.RoutePolicy(
        "GET", "/api/v2/admin/run-usage-legacy",
        roles=frozenset({"teacher", "admin"}), auth="required",
        course_scope=False, run_ownership="none")
    problems = permission_matrix.verify_route_policies(
        app, policies=permission_matrix.ROUTE_POLICIES + (ghost,))
    assert "stale_declaration: GET /api/v2/admin/run-usage-legacy" in problems
    assert not any(problem.startswith("undeclared_route") for problem in problems)


def test_malformed_policy_fields_fail_verification():
    app = _main_app()
    bad = permission_matrix.RoutePolicy(
        "POST", "/api/v2/learning-runs/stream",
        roles=frozenset({"wizard"}), auth="sometimes", course_scope=True,
        run_ownership="maybe", tools=frozenset({"made:up:key"}))
    problems = permission_matrix.verify_route_policies(app, policies=(bad,))
    joined = "\n".join(problems)
    assert "unknown roles ['wizard']" in joined
    assert "invalid auth 'sometimes'" in joined
    assert "invalid run_ownership 'maybe'" in joined
    assert "tools outside ToolRegistry ['made:up:key']" in joined
    # Every other served route is now undeclared by this trimmed policy set.
    assert len([p for p in problems if p.startswith("undeclared_route")]) == 9

    demo_required = permission_matrix.RoutePolicy(
        "GET", "/api/v2/admin/run-usage",
        roles=frozenset({"demo"}), auth="required", course_scope=False,
        run_ownership="none")
    demo_problems = permission_matrix.verify_route_policies(app, policies=(demo_required,))
    assert any("demo role is only valid with optional auth" in p for p in demo_problems)


def test_tools_come_from_tool_registry_truth():
    catalog_keys = frozenset(spec.permission_key for spec in source_specs("v2"))
    assert permission_matrix.V2_TOOL_KEYS == catalog_keys
    assert len(catalog_keys) == 4  # planner 3 + tutor 1, single source: tool_catalog
    for policy in permission_matrix.ROUTE_POLICIES:
        if policy.path in {"/api/v2/learning-runs/stream", "/api/v2/learning-runs/enqueue"}:
            assert policy.tools == catalog_keys  # graph execution reaches every v2 tool
        else:
            assert policy.tools == frozenset()  # no model/tool execution on these paths


def test_role_course_and_run_dimensions_match_runtime_guards():
    by_route = permission_matrix.POLICY_BY_ROUTE

    reviewer = {key for key, policy in by_route.items()
                if policy.run_ownership == "reviewer_only"}
    assert reviewer == {("POST", "/api/v2/learning-runs/{run_id}/resume"),
                        ("POST", "/api/v2/learning-runs/{run_id}/reconcile")}
    for key in reviewer:
        assert by_route[key].roles == {"teacher", "admin"}
        assert by_route[key].auth == "required"
        assert by_route[key].course_scope is True

    admin_surface = {key for key, policy in by_route.items()
                     if key[1].startswith("/api/v2/admin/")}
    assert admin_surface == {("GET", "/api/v2/admin/run-usage"),
                             ("GET", "/api/v2/admin/run-usage/{run_id}")}
    for key in admin_surface:
        assert by_route[key].roles == {"teacher", "admin"}
        assert by_route[key].auth == "required"
        assert by_route[key].course_scope is False  # global read-only projection

    owner = {key for key, policy in by_route.items()
             if policy.run_ownership == "owner_or_reviewer"}
    assert len(owner) == 4  # get / cancel / continue / events
    for key in owner:
        assert by_route[key].roles == {"student", "teacher", "admin"}
        assert by_route[key].auth == "required"
        assert by_route[key].course_scope is True

    for key, policy in by_route.items():
        if policy.run_ownership == "creator":
            assert policy.roles == {"demo", "student", "teacher", "admin"}
            assert policy.auth == "optional" and policy.course_scope is True
            assert policy.tools  # creation surfaces execute the graph


@pytest.fixture
def admin_api(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'matrix.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    AgentRunRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    identities = {"Bearer teacher": ("teacher", "teacher"),
                  "Bearer admin": ("admin", "admin"),
                  "Bearer alice": ("alice", "student")}

    def principal(header):
        if not header:
            return None
        if header not in identities:
            raise HTTPException(401, "invalid_token")
        return access.V2Principal(*identities[header], True)

    monkeypatch.setattr(access, "_principal_from_authorization", principal)
    app = FastAPI()
    app.include_router(run_usage_admin.router)
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_role_dimension_refusals_on_admin_run_usage(admin_api):
    # Student: authenticated but holds no reviewer role -> 403.
    assert admin_api.get("/api/v2/admin/run-usage",
                         headers={"Authorization": "Bearer alice"}).status_code == 403
    # Anonymous: no token, matrix declares auth=required -> 401.
    assert admin_api.get("/api/v2/admin/run-usage").status_code == 401
    # Positive control: declared reviewer roles get through the gate.
    assert admin_api.get("/api/v2/admin/run-usage",
                         headers={"Authorization": "Bearer teacher"}).status_code == 200


def test_role_dimension_refusals_on_single_run_usage(admin_api):
    assert admin_api.get("/api/v2/admin/run-usage/run-x",
                         headers={"Authorization": "Bearer alice"}).status_code == 403
    assert admin_api.get("/api/v2/admin/run-usage/run-x").status_code == 401
