from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app_client(tmp_path_factory) -> TestClient:
    from backend.app.core.database import configure_database, init_db

    db_path = tmp_path_factory.mktemp("resource-course") / "resources.db"
    configure_database(f"sqlite:///{db_path.as_posix()}")
    init_db()

    from backend.app.main import app

    client = TestClient(app)
    token = client.post(
        "/api/v1/auth/login",
        json={"account": "teacher", "password": "123456"},
    ).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def _create_course_resource(client: TestClient, title: str, course: str) -> str:
    response = client.post(
        "/api/v1/teacher/resources",
        json={
            "title": title,
            "type": "document",
            "content": title,
            "course": course,
            "scope": "course",
            "status": "published",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["resource_id"]


def test_resource_list_filters_by_course(app_client: TestClient):
    ai_id = _create_course_resource(app_client, "AI course filter marker", "artificial_intelligence")
    python_id = _create_course_resource(app_client, "Python course filter marker", "python_programming")

    ai_resources = app_client.get(
        "/api/v1/resources/list",
        params={"user_id": "demo-student-1", "course": "artificial_intelligence", "limit": 100},
    ).json()["resources"]
    python_resources = app_client.get(
        "/api/v1/resources/list",
        params={"user_id": "demo-student-1", "course": "python_programming", "limit": 100},
    ).json()["resources"]

    ai_ids = {item["id"] for item in ai_resources}
    python_ids = {item["id"] for item in python_resources}
    assert ai_id in ai_ids
    assert python_id not in ai_ids
    assert python_id in python_ids
    assert ai_id not in python_ids


def test_recommendations_scan_only_selected_course(app_client: TestClient):
    _create_course_resource(app_client, "Second AI recommendation marker", "artificial_intelligence")
    ai_response = app_client.get(
        "/api/v1/insights/recommendations",
        params={"user_id": "demo-student-1", "course": "artificial_intelligence"},
    )
    python_response = app_client.get(
        "/api/v1/insights/recommendations",
        params={"user_id": "demo-student-1", "course": "python_programming"},
    )

    assert ai_response.status_code == 200, ai_response.text
    assert python_response.status_code == 200, python_response.text
    assert ai_response.json()["total_resources_scanned"] > python_response.json()["total_resources_scanned"]


def test_existing_database_backfills_both_course_resource_sets(app_client: TestClient):
    from backend.app import main
    from backend.app.api.v1 import resources as resources_api

    assert hasattr(main, "_ensure_course_resources"), "startup must backfill course resources for existing databases"
    main._ensure_course_resources()

    ai_resources = app_client.get(
        "/api/v1/resources/list",
        params={"user_id": "demo-student-1", "course": "artificial_intelligence", "limit": 100},
    ).json()["resources"]
    python_resources = app_client.get(
        "/api/v1/resources/list",
        params={"user_id": "demo-student-1", "course": "python_programming", "limit": 100},
    ).json()["resources"]

    assert any(item["id"].startswith("teacher_res_seed_course_") for item in ai_resources)
    assert any(item["id"].startswith("teacher_res_py_course_") for item in python_resources)
    assert resources_api._resources


def test_recovered_legacy_multimedia_is_assigned_to_ai_course(tmp_path):
    from backend.app import main
    from backend.app.api.v1.artifacts.registry import get_artifact_registry, reset_artifact_registry

    reset_artifact_registry()
    for directory, extension in (("mp3", "mp3"), ("pptx", "pptx"), ("mermaid_png", "png"), ("video", "mp4")):
        folder = tmp_path / "artifacts" / directory
        folder.mkdir(parents=True)
        (folder / ("sample." + extension)).write_bytes(b"test artifact")
    main._scan_and_register_existing_artifacts(tmp_path)
    records = get_artifact_registry().list(limit=1000)

    expected_types = {"mp3", "pptx", "mermaid_png", "video"}
    recovered = [record for record in records if record.type in expected_types]
    assert expected_types.issubset({record.type for record in recovered})
    assert all(record.metadata.get("course") == "artificial_intelligence" for record in recovered)
