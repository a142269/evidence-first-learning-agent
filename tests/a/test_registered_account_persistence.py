from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_registered_account_can_login_after_memory_cache_is_cleared(tmp_path) -> None:
    from backend.app.api.v1 import auth
    from backend.app.core.database import DATABASE_URL, configure_database, init_db
    from backend.app.main import app

    previous_database = DATABASE_URL
    configure_database(f"sqlite:///{(tmp_path / 'accounts.db').as_posix()}")
    init_db()
    account = f"persist-{uuid4().hex[:10]}"
    client = TestClient(app)
    try:
        registered = client.post(
            "/api/v1/auth/register",
            json={
                "account": account,
                "password": "secure123",
                "display_name": "持久化学生",
                "role": "student",
                "profile_answers": {"goal": {"target": "验证账号持久化"}},
            },
        )
        assert registered.status_code == 200, registered.text

        # 模拟后端重启：运行内存被清空，登录应从 SQLite 的 registered_accounts 读取。
        auth._REGISTERED_ACCOUNTS.clear()
        login = client.post(
            "/api/v1/auth/login",
            json={"account": account, "password": "secure123", "role": "student"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["user"]["display_name"] == "持久化学生"
    finally:
        auth._REGISTERED_ACCOUNTS.pop(account, None)
        configure_database(previous_database)


def test_teacher_can_recover_an_orphaned_student_account(tmp_path) -> None:
    from backend.app.api.v1 import auth
    from backend.app.core.database import DATABASE_URL, configure_database, init_db
    from backend.app.main import app
    from backend.app.repositories.profile_repo import ProfileRepository

    previous_database = DATABASE_URL
    configure_database(f"sqlite:///{(tmp_path / 'recover.db').as_posix()}")
    init_db()
    account = f"orphan-{uuid4().hex[:10]}"
    ProfileRepository().replace(account, {"display_name": "待恢复学生"}, source="test")
    client = TestClient(app)
    try:
        teacher = client.post(
            "/api/v1/auth/login",
            json={"account": "teacher", "password": "123456", "role": "teacher"},
        )
        client.headers.update({"Authorization": f"Bearer {teacher.json()['access_token']}"})
        restored = client.post(
            f"/api/v1/teacher/students/{account}/restore-account",
            json={"new_password": "new-pass-123"},
        )
        assert restored.status_code == 200, restored.text

        client.headers.clear()
        auth._REGISTERED_ACCOUNTS.clear()
        login = client.post(
            "/api/v1/auth/login",
            json={"account": account, "password": "new-pass-123", "role": "student"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["user"]["display_name"] == "待恢复学生"
    finally:
        auth._REGISTERED_ACCOUNTS.pop(account, None)
        configure_database(previous_database)
