"""Declarative permission matrix for every V2 route (QWEN-321).

One declaration per route answers: which roles may call it, whether a real
login is required, whether the request must hold course authorisation, how run
ownership is enforced, and which registry tools its execution surface can reach.

This is a declaration layer, not a new enforcement path: the runtime guards
(``resolve_v2_principal``, ``authorize_run_owner``, ``authorize_reviewer`` and
``tool_catalog.decide_access``) keep their existing behaviour, so declared
routes behave exactly as before.  Anything *undeclared* is the failure mode:
``verify_route_policies`` compares the FastAPI route table against this matrix,
and CI runs that check as a hard gate so a new or renamed V2 route cannot ship
without being reviewed against this file.

Tool declarations reference the single tool truth (``tool_catalog``) by
permission key; no second tool registry is created here.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.app.services.tool_catalog import source_specs

# Roles that exist at the route layer: session.role is one of
# student/teacher/admin, and "demo" is the unauthenticated principal that
# ``resolve_v2_principal`` synthesises when auth is optional (non-production).
KNOWN_ROLES = frozenset({"demo", "student", "teacher", "admin"})

# The V2 execution surface reaches exactly the ToolRegistry's v2 tools, by
# permission key.  Derived from the catalog, never re-listed by hand.
V2_TOOL_KEYS = frozenset(spec.permission_key for spec in source_specs("v2"))

_RUN_TOOLS = frozenset(V2_TOOL_KEYS)


@dataclass(frozen=True)
class RoutePolicy:
    method: str
    path: str
    roles: frozenset[str]
    auth: str  # "required" | "optional"
    course_scope: bool  # request must pass course authorisation
    run_ownership: str  # "creator" | "owner_or_reviewer" | "reviewer_only" | "none"
    tools: frozenset[str] = frozenset()
    note: str = ""


ROUTE_POLICIES: tuple[RoutePolicy, ...] = (
    # --- creation: any role, auth optional (demo mode), creator owns the run.
    RoutePolicy(
        "POST", "/api/v2/learning-runs/stream",
        roles=frozenset({"demo", "student", "teacher", "admin"}),
        auth="optional", course_scope=True, run_ownership="creator", tools=_RUN_TOOLS,
        note="mode=learning_package additionally requires an authenticated principal",
    ),
    RoutePolicy(
        "POST", "/api/v2/learning-runs/enqueue",
        roles=frozenset({"demo", "student", "teacher", "admin"}),
        auth="optional", course_scope=True, run_ownership="creator", tools=_RUN_TOOLS,
        note="mode=learning_package additionally requires an authenticated principal",
    ),
    # --- run reads / lifecycle: any authenticated role, owner or reviewer.
    RoutePolicy(
        "GET", "/api/v2/learning-runs/{run_id}",
        roles=frozenset({"student", "teacher", "admin"}),
        auth="required", course_scope=True, run_ownership="owner_or_reviewer",
    ),
    RoutePolicy(
        "POST", "/api/v2/learning-runs/{run_id}/cancel",
        roles=frozenset({"student", "teacher", "admin"}),
        auth="required", course_scope=True, run_ownership="owner_or_reviewer",
    ),
    RoutePolicy(
        "POST", "/api/v2/learning-runs/{run_id}/continue",
        roles=frozenset({"student", "teacher", "admin"}),
        auth="required", course_scope=True, run_ownership="owner_or_reviewer",
    ),
    RoutePolicy(
        "GET", "/api/v2/learning-runs/{run_id}/events",
        roles=frozenset({"student", "teacher", "admin"}),
        auth="required", course_scope=True, run_ownership="owner_or_reviewer",
    ),
    # --- teacher review surfaces: reviewer role only.
    RoutePolicy(
        "POST", "/api/v2/learning-runs/{run_id}/resume",
        roles=frozenset({"teacher", "admin"}),
        auth="required", course_scope=True, run_ownership="reviewer_only",
    ),
    RoutePolicy(
        "POST", "/api/v2/learning-runs/{run_id}/reconcile",
        roles=frozenset({"teacher", "admin"}),
        auth="required", course_scope=True, run_ownership="reviewer_only",
    ),
    # --- admin read-only usage: no course scope, global projection.
    RoutePolicy(
        "GET", "/api/v2/admin/run-usage",
        roles=frozenset({"teacher", "admin"}),
        auth="required", course_scope=False, run_ownership="none",
    ),
    RoutePolicy(
        "GET", "/api/v2/admin/run-usage/{run_id}",
        roles=frozenset({"teacher", "admin"}),
        auth="required", course_scope=False, run_ownership="none",
    ),
)

POLICY_BY_ROUTE = {(policy.method, policy.path): policy for policy in ROUTE_POLICIES}

_VALID_AUTH = frozenset({"required", "optional"})
_VALID_OWNERSHIP = frozenset({"creator", "owner_or_reviewer", "reviewer_only", "none"})


def _declared_routes(policies: tuple[RoutePolicy, ...]) -> set[tuple[str, str]]:
    declared = {(policy.method, policy.path) for policy in policies}
    if len(declared) != len(policies):
        raise ValueError("duplicate (method, path) in ROUTE_POLICIES")
    return declared


def actual_v2_routes(app) -> set[tuple[str, str]]:
    """The (method, path) pairs the app really serves under /api/v2.

    Read from the generated OpenAPI schema: recent FastAPI versions wrap
    ``include_router`` in a lazy ``_IncludedRouter``, so the raw route table
    no longer lists included routes; the schema is the public, version-stable
    projection of what the app actually serves.
    """
    schema = app.openapi()
    actual: set[tuple[str, str]] = set()
    for path, methods in schema.get("paths", {}).items():
        if not path.startswith("/api/v2"):
            continue
        for method in methods:
            upper = method.upper()
            if upper in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                actual.add((upper, path))
    return actual


def verify_route_policies(app, policies: tuple[RoutePolicy, ...] = ROUTE_POLICIES) -> list[str]:
    """Every V2 route must be declared; every declaration must be well-formed.

    Returns a list of problems; empty means the matrix and the app agree and
    every declaration passes its field checks.
    """
    problems: list[str] = []
    actual = actual_v2_routes(app)
    declared = _declared_routes(policies)
    for item in sorted(actual - declared):
        problems.append(f"undeclared_route: {item[0]} {item[1]}")
    for item in sorted(declared - actual):
        problems.append(f"stale_declaration: {item[0]} {item[1]}")

    catalog_keys = frozenset(spec.permission_key for spec in source_specs("v2"))
    by_route = {(p.method, p.path): p for p in policies}
    for key, policy in sorted(by_route.items()):
        label = f"{key[0]} {key[1]}"
        if not policy.roles:
            problems.append(f"{label}: empty roles")
        unknown = policy.roles - KNOWN_ROLES
        if unknown:
            problems.append(f"{label}: unknown roles {sorted(unknown)}")
        if policy.auth not in _VALID_AUTH:
            problems.append(f"{label}: invalid auth {policy.auth!r}")
        if policy.run_ownership not in _VALID_OWNERSHIP:
            problems.append(f"{label}: invalid run_ownership {policy.run_ownership!r}")
        if policy.auth == "optional" and "demo" not in policy.roles:
            problems.append(f"{label}: optional auth but demo role not declared")
        if policy.auth == "required" and "demo" in policy.roles:
            problems.append(f"{label}: demo role is only valid with optional auth")
        outside = policy.tools - catalog_keys
        if outside:
            problems.append(f"{label}: tools outside ToolRegistry {sorted(outside)}")
    return problems


# Sanity: the module must stay import-light and deterministic.  Guard against
# accidental duplicate declarations right at import time.
assert len(POLICY_BY_ROUTE) == len(ROUTE_POLICIES), "duplicate route declaration"
assert all(policy.tools <= V2_TOOL_KEYS for policy in ROUTE_POLICIES), \
    "route tools must come from the ToolRegistry v2 surface"
