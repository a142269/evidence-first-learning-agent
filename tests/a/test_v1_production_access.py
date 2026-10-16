"""Production V1 compatibility surface is explicit and fails closed."""
from dataclasses import dataclass

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.core.v1_production_access import v1_route_allowed


@pytest.mark.parametrize("method,path,role,allowed", [
    ("POST", "/api/v1/auth/login", None, True),
    ("POST", "/api/v1/auth/register", None, True),
    ("GET", "/api/v1/auth/me", "student", True),
    ("POST", "/api/v1/auth/logout", "teacher", True),
    ("GET", "/api/v1/knowledge/courses", "student", True),
    ("GET", "/api/v1/resources/list", "student", True),
    ("GET", "/api/v1/resources/types", "teacher", True),
    ("POST", "/api/v1/resources/save", "student", True),
    ("GET", "/api/v1/resources/res-1", "student", True),
    ("GET", "/api/v1/resources/res-1/download", "student", True),
    ("DELETE", "/api/v1/resources/res-1", "student", True),
    ("POST", "/api/v1/knowledge/index/course", "student", False),
    ("GET", "/api/v1/profile/other-user", "student", False),
    ("POST", "/api/v1/assessment/other-user/record", "student", False),
    ("GET", "/api/v1/teacher/students", "teacher", False),
    ("GET", "/api/v1/teacher/knowledge/courses", "teacher", False),
    ("GET", "/api/v1/resources/list", "teacher", False),
    ("POST", "/api/v1/resources/save", "teacher", False),
    ("PUT", "/api/v1/auth/login", None, False),
    ("GET", "/api/v1/resources/res-1/download/extra", "student", False),
    ("GET", "/api/v1/new-feature", "student", False),
])
def test_production_v1_route_policy(method, path, role, allowed):
    assert v1_route_allowed(method, path, role) is allowed


@dataclass
class _Session:
    role: str


def _request(method: str, path: str, *, authorized: bool = True) -> Request:
    headers = [(b"authorization", b"Bearer test-token")] if authorized else []
    return Request({"type": "http", "method": method, "path": path,
                    "headers": headers, "query_string": b"",
                    "server": ("localhost", 80), "scheme": "http"})


@pytest.mark.asyncio
@pytest.mark.parametrize("role,path,expected", [
    ("student", "/api/v1/resources/list", 200),
    ("student", "/api/v1/profile/another", 403),
    ("student", "/api/v1/knowledge/index/course", 403),
    ("teacher", "/api/v1/teacher/knowledge/courses", 403),
    ("teacher", "/api/v1/resources/list", 403),
])
async def test_production_middleware_enforces_route_policy(monkeypatch, role, path, expected):
    from backend.app import main

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(main, "_parse_bearer_token", lambda _: "test-token")
    monkeypatch.setattr(main, "_get_session", lambda _: _Session(role))

    async def reached(_request):
        return JSONResponse({"reached": True})

    response = await main._require_auth_for_api(_request("GET", path), reached)
    assert response.status_code == expected


@pytest.mark.asyncio
async def test_production_public_auth_method_is_exact(monkeypatch):
    from backend.app import main

    monkeypatch.setenv("APP_ENV", "production")

    async def reached(_request):
        return JSONResponse({"reached": True})

    assert (await main._require_auth_for_api(
        _request("POST", "/api/v1/auth/login", authorized=False), reached
    )).status_code == 200
    assert (await main._require_auth_for_api(
        _request("PUT", "/api/v1/auth/login", authorized=False), reached
    )).status_code == 403


@pytest.mark.asyncio
async def test_development_legacy_route_stays_available(monkeypatch):
    from backend.app import main

    monkeypatch.setenv("APP_ENV", "development")

    async def reached(_request):
        return JSONResponse({"reached": True})

    response = await main._require_auth_for_api(
        _request("GET", "/api/v1/profile/somebody", authorized=False), reached
    )
    assert response.status_code == 200
