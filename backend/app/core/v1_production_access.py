"""Explicit V1 surface that has account and course checks in production.

Legacy V1 endpoints were built for a single-user demo. Authentication alone
does not establish ownership of the user, course, session or resource named in
a request, so new V1 routes remain closed until reviewed individually.
"""
from __future__ import annotations

import re


_AUTH_ROUTES = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/register"),
    ("GET", "/api/v1/auth/me"),
    ("POST", "/api/v1/auth/logout"),
}
_SHARED_ROUTES = {
    ("GET", "/api/v1/knowledge/courses"),
    ("GET", "/api/v1/resources/types"),
}
_STUDENT_ROUTES = {
    ("GET", "/api/v1/resources/list"),
    ("POST", "/api/v1/resources/save"),
}
_RESOURCE_DETAIL = re.compile(r"/api/v1/resources/[^/]+\Z")
_RESOURCE_DOWNLOAD = re.compile(r"/api/v1/resources/[^/]+/download\Z")


def v1_route_allowed(method: str, path: str, role: str | None) -> bool:
    """Allow only routes whose production ownership rules have been audited."""
    if (method, path) in _AUTH_ROUTES:
        return True
    if (method, path) in _SHARED_ROUTES:
        return role in {"student", "teacher", "admin"}
    if role != "student":
        return False
    if (method, path) in _STUDENT_ROUTES:
        return True
    if method == "GET":
        return bool(_RESOURCE_DETAIL.fullmatch(path) or _RESOURCE_DOWNLOAD.fullmatch(path))
    if method == "DELETE":
        return bool(_RESOURCE_DETAIL.fullmatch(path))
    return False
