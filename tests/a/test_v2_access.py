from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.app.api.v2 import access


def test_enterprise_mode_requires_bearer_authentication(monkeypatch):
    monkeypatch.setenv("V2_AUTH_REQUIRED", "true")

    with pytest.raises(HTTPException) as exc_info:
        access.resolve_v2_principal(
            authorization=None,
            requested_user_id="anonymous",
            requested_course_id="artificial_intelligence",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "authorization_required"


def test_authenticated_identity_cannot_be_spoofed_from_body(monkeypatch):
    monkeypatch.setenv("V2_AUTH_REQUIRED", "true")
    monkeypatch.setattr(
        access,
        "_principal_from_authorization",
        lambda _header: access.V2Principal("student-a", "student", True),
    )

    with pytest.raises(HTTPException) as exc_info:
        access.resolve_v2_principal(
            authorization="Bearer test-token",
            requested_user_id="student-b",
            requested_course_id="artificial_intelligence",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "user_identity_mismatch"


def test_student_and_teacher_courses_are_server_scoped(monkeypatch):
    monkeypatch.setenv("V2_AUTH_REQUIRED", "true")
    monkeypatch.setenv("V2_STUDENT_COURSES", "artificial_intelligence")
    monkeypatch.setattr(
        access,
        "_principal_from_authorization",
        lambda _header: access.V2Principal("student-a", "student", True),
    )

    with pytest.raises(HTTPException) as exc_info:
        access.resolve_v2_principal(
            authorization="Bearer student", requested_user_id="anonymous", requested_course_id="python"
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "course_access_denied"
    monkeypatch.setattr(
        access,
        "_principal_from_authorization",
        lambda _header: access.V2Principal("teacher-a", "teacher", True),
    )
    with pytest.raises(HTTPException):
        access.resolve_v2_principal(
            authorization="Bearer teacher", requested_user_id="anonymous", requested_course_id="python"
        )
    monkeypatch.setenv("V2_TEACHER_COURSES", "python")
    principal, course_id = access.resolve_v2_principal(
        authorization="Bearer teacher", requested_user_id="anonymous", requested_course_id="python"
    )
    assert principal.user_id == "teacher-a"
    assert course_id == "python"
