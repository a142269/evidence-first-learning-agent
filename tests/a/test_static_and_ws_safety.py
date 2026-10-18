"""Security regressions for static-file serving and the legacy V1 websocket.

Covers the 2026-10-18 audit findings F1 (SPA catch-all traversal), F3 (V1
websocket bypassing the production allowlist) and F5 (operational surfaces in
production).  No network, no providers.
"""
import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse


class _FakeWebSocket:
    def __init__(self) -> None:
        self.closed: tuple[int, str] | None = None
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = (code, reason)


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>index</html>", encoding="utf-8")
    nested = dist / "integrated-map"
    nested.mkdir()
    (nested / "page.html").write_text("<html>page</html>", encoding="utf-8")
    return dist


def test_resolve_dist_candidate_blocks_traversal(tmp_path):
    from backend.app import main

    dist = _make_dist(tmp_path)
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")

    assert main._resolve_dist_candidate(dist, "index.html") == (dist / "index.html").resolve()
    assert main._resolve_dist_candidate(dist, "integrated-map/page.html") == \
        (dist / "integrated-map/page.html").resolve()
    for traversal in ("../outside.txt", "..\\outside.txt", "integrated-map/../../outside.txt",
                      "../..//outside.txt", "./../outside.txt"):
        assert main._resolve_dist_candidate(dist, traversal) is None, traversal
    # Missing in-dist paths still resolve inside; the caller only serves files.
    candidate = main._resolve_dist_candidate(dist, "missing/page")
    assert candidate is not None and candidate.is_relative_to(dist.resolve())


def test_spa_fallback_refuses_traversal_and_serves_spa_routes(tmp_path, monkeypatch):
    from backend.app import main

    route = getattr(main, "_spa_fallback", None)
    if route is None:
        pytest.skip("frontend dist is not mounted in this checkout")
    dist = _make_dist(tmp_path)
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(main, "_FRONTEND_DIST", dist)

    traversal = asyncio.run(route("../secret.txt"))
    assert traversal.status_code == 404
    nested_traversal = asyncio.run(route("integrated-map/../../secret.txt"))
    assert nested_traversal.status_code == 404
    assert asyncio.run(route("integrated-map/page.html")).status_code == 200
    # Unknown Vue Router paths fall back to index.html, not to arbitrary files.
    assert asyncio.run(route("unknown/spa/path")).status_code == 200


def test_mobile_websocket_fails_closed_in_production(monkeypatch):
    from backend.app.api.v1 import mobile

    monkeypatch.setenv("APP_ENV", "production")
    socket = _FakeWebSocket()
    asyncio.run(mobile.mobile_websocket(socket))
    assert socket.accepted is False
    assert socket.closed == (4403, "v1_route_unavailable_in_production")


def test_mobile_websocket_still_accepts_in_development(monkeypatch):
    from backend.app.api.v1 import mobile

    monkeypatch.setenv("APP_ENV", "development")
    socket = _FakeWebSocket()
    # Development mode accepts and then fails the auth-frame wait; the fake
    # socket raises on receive_json only if called, so patch it to a timeout.
    async def _timeout():
        raise asyncio.TimeoutError

    socket.receive_json = _timeout  # type: ignore[attr-defined]
    asyncio.run(mobile.mobile_websocket(socket))
    assert socket.accepted is True
    assert socket.closed is None


# F5: operational surfaces in production (docs/OpenAPI hidden, metrics admin-only).
@dataclass
class _Session:
    role: str


def _request(method: str, path: str, *, authorization: str | None = None) -> Request:
    headers = [(b"authorization", authorization.encode())] if authorization else []
    return Request({"type": "http", "method": method, "path": path, "headers": headers,
                    "query_string": b"", "server": ("localhost", 80), "scheme": "http"})


async def _reached(_request: Request) -> JSONResponse:
    return JSONResponse({"reached": True})


def test_production_hides_docs_and_openapi(monkeypatch):
    from backend.app import main

    monkeypatch.setenv("APP_ENV", "production")
    for path in ("/docs", "/docs/", "/docs/oauth2-redirect", "/redoc", "/openapi.json"):
        response = asyncio.run(main._require_auth_for_api(_request("GET", path), _reached))
        assert response.status_code == 404, path


def test_development_keeps_docs_available(monkeypatch):
    from backend.app import main

    monkeypatch.setenv("APP_ENV", "development")
    response = asyncio.run(main._require_auth_for_api(_request("GET", "/docs"), _reached))
    assert response.status_code == 200


def test_production_metrics_require_privileged_role(monkeypatch):
    from backend.app import main

    monkeypatch.setenv("APP_ENV", "production")

    def parse(header: str | None) -> str:
        if not header:
            raise HTTPException(401, "authorization_required")
        return header

    monkeypatch.setattr(main, "_parse_bearer_token", parse)
    monkeypatch.setattr(main, "_get_session",
                        lambda token: _Session("teacher" if "teacher" in token else "student"))

    assert asyncio.run(main._require_auth_for_api(_request("GET", "/metrics"), _reached)).status_code == 401
    student = asyncio.run(main._require_auth_for_api(
        _request("GET", "/metrics/llm-cost", authorization="Bearer student"), _reached))
    assert student.status_code == 403 and student.body
    teacher = asyncio.run(main._require_auth_for_api(
        _request("GET", "/metrics", authorization="Bearer teacher"), _reached))
    assert teacher.status_code == 200

