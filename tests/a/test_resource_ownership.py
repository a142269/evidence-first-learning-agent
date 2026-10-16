"""Legacy resource writes must not let a student target another account."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request


def _request(method: str) -> Request:
    return Request({"type": "http", "method": method, "path": "/api/v1/resources",
                    "headers": [(b"authorization", b"Bearer test-token")],
                    "query_string": b"", "server": ("localhost", 80), "scheme": "http"})


def test_student_cannot_forge_resource_owner_or_publish_scope(monkeypatch):
    from backend.app.api.v1 import auth, resources

    monkeypatch.setattr(auth, "_get_session", lambda _token: SimpleNamespace(
        account="student-a", role="student"))
    monkeypatch.setattr(resources, "_resources", {})
    monkeypatch.setattr(resources, "_db_available", False)
    request = _request("POST")

    with pytest.raises(HTTPException) as spoofed:
        resources.save_resource(request, {"user_id": "student-b", "title": "foreign"})
    assert spoofed.value.status_code == 403
    with pytest.raises(HTTPException) as published:
        resources.save_resource(request, {"title": "shared", "metadata": {
            "scope": "course", "status": "published"}})
    assert published.value.status_code == 403

    created = resources.save_resource(request, {"title": "private"})["resource"]
    assert created["user_id"] == "student-a"
    assert created["id"] in resources._resources


def test_student_delete_is_limited_to_personal_resources(monkeypatch):
    from backend.app.api.v1 import auth, resources

    monkeypatch.setattr(auth, "_get_session", lambda _token: SimpleNamespace(
        account="student-a", role="student"))
    records = {
        "mine": {"id": "mine", "user_id": "student-a", "metadata": {}},
        "other": {"id": "other", "user_id": "student-b", "metadata": {}},
        "shared": {"id": "shared", "user_id": "student-a", "metadata": {
            "scope": "course", "status": "published"}},
    }
    monkeypatch.setattr(resources, "_resources", records)
    monkeypatch.setattr(resources, "_db_available", False)
    request = _request("DELETE")

    for resource_id in ("other", "shared"):
        with pytest.raises(HTTPException) as denied:
            resources.delete_resource(resource_id, request)
        assert denied.value.status_code == 404
        assert resource_id in records
    assert resources.delete_resource("mine", request)["status"] == "deleted"
    assert "mine" not in records


def test_http_resource_write_routes_enforce_student_owner(monkeypatch):
    from backend.app.api.v1 import auth, resources
    from backend.app.main import app

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(auth, "_get_session", lambda _token: SimpleNamespace(
        account="student-a", role="student"))
    monkeypatch.setattr(resources, "_resources", {})
    monkeypatch.setattr(resources, "_db_available", False)
    client = TestClient(app, headers={"Authorization": "Bearer test-token"})

    assert client.post("/api/v1/resources/save", json={
        "user_id": "student-b", "title": "foreign"}).status_code == 403
    own = client.post("/api/v1/resources/save", json={"title": "mine"})
    assert own.status_code == 200
    resource_id = own.json()["resource_id"]
    assert own.json()["resource"]["user_id"] == "student-a"
    assert client.delete(f"/api/v1/resources/{resource_id}").json()["status"] == "deleted"


def test_teacher_draft_assigned_to_student_is_not_visible(monkeypatch):
    from backend.app.api.v1 import resources

    monkeypatch.setenv("APP_ENV", "development")
    record = {"user_id": "student-a", "metadata": {
        "scope": "student", "status": "draft", "target_user_ids": ["student-a"]}}
    assert not resources._visible_to_student(record, "student-a")
    record["metadata"]["status"] = "published"
    assert resources._visible_to_student(record, "student-a")
    record["metadata"]["target_user_ids"] = ["student-b"]
    assert not resources._visible_to_student(record, "student-a")


def test_production_resource_routes_follow_course_grants(monkeypatch, tmp_path):
    from backend.app.api.v1 import auth, resources
    from backend.app import main
    from backend.app.repositories.auth_repo import AuthRepository

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(auth, "_get_session", lambda _token: SimpleNamespace(
        account="student-a", role="student"))
    monkeypatch.setattr(main, "_get_session", auth._get_session)
    grants = {"course-a"}
    monkeypatch.setattr(AuthRepository, "has_course", lambda _self, account, course:
                        account == "student-a" and course in grants)
    monkeypatch.setattr(resources, "_db_available", False)
    monkeypatch.setattr(resources, "_TEACHER_UPLOAD_ROOT", tmp_path)
    (tmp_path / "course.txt").write_text("attachment", encoding="utf-8")

    def record(name, course):
        return {"id": name, "user_id": "", "title": name,
                "metadata": {"scope": "course", "status": "published", "course": course,
                             "attachment": {"storage_key": "course.txt", "filename": "course.txt"}}}

    records = {"allowed": record("allowed", "course-a"),
               "denied": record("denied", "course-b"),
               "draft": {"id": "draft", "user_id": "student-a", "title": "draft",
                         "metadata": {"scope": "student", "status": "draft", "course": "course-a",
                                      "target_user_ids": ["student-a"]}}}
    monkeypatch.setattr(resources, "_resources", records)
    client = TestClient(main.app, headers={"Authorization": "Bearer test-token"})

    listed = client.get("/api/v1/resources/list")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["resources"]] == ["allowed"]
    assert client.get("/api/v1/resources/allowed").status_code == 200
    assert client.get("/api/v1/resources/allowed/download").content == b"attachment"
    assert client.get("/api/v1/resources/denied").status_code == 404
    assert client.get("/api/v1/resources/denied/download").status_code == 404
    assert client.get("/api/v1/resources/draft").status_code == 404

    grants.clear()
    assert client.get("/api/v1/resources/allowed").status_code == 404
    assert client.get("/api/v1/resources/allowed/download").status_code == 404


def test_production_resource_revocation_uses_persistent_grants(monkeypatch, tmp_path):
    from backend.app.api.v1 import resources
    from backend.app.core import database
    from backend.app.core.passwords import hash_password
    from backend.app.main import app
    from backend.app.repositories.account_repo import AccountRepository, StoredAccount
    from backend.app.repositories.auth_repo import AuthRepository

    previous_url = database.DATABASE_URL
    database.configure_database(f"sqlite:///{(tmp_path / 'resource-auth.db').as_posix()}")
    database.init_db()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(resources, "_db_available", False)
    monkeypatch.setattr(resources, "_resources", {
        "granted-course-resource": {
            "id": "granted-course-resource", "user_id": "", "title": "course",
            "metadata": {"scope": "course", "status": "published", "course": "course-a"},
        },
    })
    try:
        AccountRepository().upsert(StoredAccount(
            "student-a", hash_password("test-password"), "student", "Student A"), create_only=True)
        client = TestClient(app)
        response = client.post("/api/v1/auth/login", json={
            "account": "student-a", "password": "test-password"})
        assert response.status_code == 200, response.text
        client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
        assert client.get("/api/v1/resources/granted-course-resource").status_code == 404

        AuthRepository().grant_course("student-a", "course-a")
        assert client.get("/api/v1/resources/granted-course-resource").status_code == 200
        AuthRepository().revoke_course("student-a", "course-a")
        assert client.get("/api/v1/resources/granted-course-resource").status_code == 404
    finally:
        database.engine.dispose()
        database.configure_database(previous_url)


def test_production_recommendations_reject_spoofed_student_or_course(monkeypatch):
    from backend.app import main
    from backend.app.api.v1 import auth
    from backend.app.repositories.auth_repo import AuthRepository

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(auth, "_get_session", lambda _token: SimpleNamespace(
        account="student-a", role="student"))
    monkeypatch.setattr(main, "_get_session", auth._get_session)
    monkeypatch.setattr(AuthRepository, "has_course", lambda _self, _account, course:
                        course == "course-a")
    client = TestClient(main.app, headers={"Authorization": "Bearer test-token"})
    assert client.get("/api/v1/insights/recommendations", params={
        "user_id": "student-b", "course": "course-a"}).status_code == 403
    assert client.get("/api/v1/insights/recommendations", params={
        "user_id": "student-a", "course": "course-b"}).status_code == 403
