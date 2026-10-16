from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
import pytest


@pytest.fixture()
def deletion_client(tmp_path) -> tuple[TestClient, str, str]:
    from backend.app.api.v1 import auth, resources
    from backend.app.core.database import configure_database, init_db

    db_path = tmp_path / "student-deletion.db"
    configure_database(f"sqlite:///{db_path.as_posix()}")
    init_db()
    resources._resources.clear()

    account = f"test-student-{uuid4().hex[:8]}"
    password = "secure123"
    client = TestClient(__import__("backend.app.main", fromlist=["app"]).app)
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "account": account,
            "password": password,
            "display_name": "待删除测试生",
            "role": "student",
            "profile_answers": {"goal": {"target": "测试删除"}},
        },
    )
    assert registered.status_code == 200, registered.text

    student_token = registered.json()["access_token"]
    teacher_token = client.post(
        "/api/v1/auth/login",
        json={"account": "teacher", "password": "123456"},
    ).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {teacher_token}"})

    yield client, account, student_token

    from backend.app.services.student_data_deletion import delete_student_data

    delete_student_data(account)
    auth._REGISTERED_ACCOUNTS.pop(account, None)
    auth._SESSIONS.pop(student_token, None)


def test_teacher_deletes_registered_account_and_private_records(
    deletion_client: tuple[TestClient, str, str],
) -> None:
    from backend.app.api.v1 import auth, resources
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import (
        AssessmentRecord,
        ChatHistoryRecord,
        GroupChatMessageRecord,
        LearningPathRecord,
        MistakeRecord,
        ResourceRecord,
    )

    client, account, student_token = deletion_client
    with SessionLocal() as db:
        db.add_all(
            [
                AssessmentRecord(user_id=account, topic="测试", duration=12),
                ChatHistoryRecord(
                    session_id="sess-delete-me",
                    user_id=account,
                    role="user",
                    content="测试消息",
                ),
                LearningPathRecord(id="path-delete-me", user_id=account),
                MistakeRecord(id="mistake-delete-me", user_id=account),
                ResourceRecord(id="resource-delete-me", user_id=account),
                GroupChatMessageRecord(
                    id="group-delete-me",
                    room_id=f"artificial_intelligence:{account}",
                    sender_id="teacher",
                    sender_name="王老师",
                ),
            ]
        )
        db.commit()
    resources._resources["resource-delete-me"] = {
        "id": "resource-delete-me",
        "user_id": account,
    }

    response = client.delete(f"/api/v1/teacher/students/{account}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "deleted"
    assert payload["account_removed"] is True
    assert payload["deleted_total"] >= 7
    assert account not in auth._REGISTERED_ACCOUNTS
    assert student_token not in auth._SESSIONS
    assert "resource-delete-me" not in resources._resources

    with SessionLocal() as db:
        assert db.query(AssessmentRecord).filter_by(user_id=account).count() == 0
        assert db.query(ChatHistoryRecord).filter_by(user_id=account).count() == 0
        assert db.query(LearningPathRecord).filter_by(user_id=account).count() == 0
        assert db.query(MistakeRecord).filter_by(user_id=account).count() == 0
        assert db.query(ResourceRecord).filter_by(user_id=account).count() == 0
        assert (
            db.query(GroupChatMessageRecord)
            .filter_by(room_id=f"artificial_intelligence:{account}")
            .count()
            == 0
        )

    relogin = client.post(
        "/api/v1/auth/login",
        json={"account": account, "password": "secure123"},
    )
    assert relogin.status_code == 401


@pytest.mark.parametrize("account", ["demo-student-1", "demo-student-21"])
def test_builtin_demo_students_are_protected(
    deletion_client: tuple[TestClient, str, str],
    account: str,
) -> None:
    client, _, _ = deletion_client
    response = client.delete(f"/api/v1/teacher/students/{account}")
    assert response.status_code == 409
    assert response.json()["detail"] == "protected_demo_account"
