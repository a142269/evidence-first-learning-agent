from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.api.v1 import mistakes as mistakes_api
from backend.app.main import app


RECORDS = [
    {"id": "m-ai", "kp_id": "transformer/attention", "error_type": "concept", "question": "AI"},
    {"id": "m-py", "kp_id": "python_basics/decorator", "error_type": "concept", "question": "Python"},
    {"id": "m-unknown", "kp_id": "unmapped/topic", "error_type": "concept", "question": "Unknown"},
]


def _course_map(_kp_ids: set[str]) -> dict[str, str]:
    return {
        "transformer/attention": "artificial_intelligence",
        "python_basics/decorator": "python_programming",
    }


def test_filter_records_keeps_everything_for_all_courses(monkeypatch):
    monkeypatch.setattr(mistakes_api, "_load_course_by_kp", _course_map)

    result = mistakes_api._filter_records_by_course(RECORDS, "")

    assert [item["id"] for item in result] == ["m-ai", "m-py", "m-unknown"]
    assert [item["course"] for item in result] == [
        "artificial_intelligence",
        "python_programming",
        "",
    ]


def test_filter_records_returns_only_selected_course_and_adds_course(monkeypatch):
    monkeypatch.setattr(mistakes_api, "_load_course_by_kp", _course_map)

    result = mistakes_api._filter_records_by_course(RECORDS, "python_programming")

    assert [item["id"] for item in result] == ["m-py"]
    assert result[0]["course"] == "python_programming"


def test_list_and_heatmap_share_course_filter(monkeypatch):
    monkeypatch.setattr(mistakes_api, "_gather_user_records", lambda _user_id: RECORDS)
    monkeypatch.setattr(mistakes_api, "_load_course_by_kp", _course_map)
    client = TestClient(app)

    listed = client.get(
        "/api/v1/mistakes/course-filter-user",
        params={"course": "python_programming", "limit": 100},
    )
    heatmap = client.get(
        "/api/v1/mistakes/heatmap",
        params={"user_id": "course-filter-user", "course": "python_programming"},
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["mistakes"]] == ["m-py"]
    assert listed.json()["total"] == 1
    assert heatmap.status_code == 200
    assert heatmap.json()["total_mistakes"] == 1


def test_unknown_course_is_rejected():
    response = TestClient(app).get(
        "/api/v1/mistakes/course-filter-user",
        params={"course": "not-a-course"},
    )

    assert response.status_code == 422
