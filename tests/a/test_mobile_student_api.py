from __future__ import annotations

import time

from fastapi.testclient import TestClient
import pytest


@pytest.fixture(scope="module")
def mobile_client(tmp_path_factory):
    from backend.app.core.database import configure_database, init_db

    db_path = tmp_path_factory.mktemp("mobile") / "mobile.db"
    configure_database(f"sqlite:///{db_path.as_posix()}")
    init_db()
    from backend.app.main import app

    with TestClient(app) as client:
        yield client


def login(client: TestClient, account: str) -> str:
    response = client.post("/api/v1/auth/login", json={
        "account": account,
        "password": "123456",
    })
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def room_for(client: TestClient, token: str, predicate) -> dict:
    rooms = client.get("/api/v1/mobile/rooms", headers=auth(token)).json()["rooms"]
    return next(room for room in rooms if predicate(room))


def test_mobile_routes_require_authentication(mobile_client: TestClient):
    response = mobile_client.get("/api/v1/mobile/rooms")
    assert response.status_code == 401


def test_seed_is_idempotent_and_room_is_visible(mobile_client: TestClient):
    token = login(mobile_client, "demo-student-1")
    first = mobile_client.get("/api/v1/mobile/rooms", headers=auth(token))
    second = mobile_client.get("/api/v1/mobile/rooms", headers=auth(token))
    assert first.status_code == 200
    assert len(first.json()["rooms"]) == 8
    assert len(second.json()["rooms"]) == 8
    group = next(room for room in first.json()["rooms"] if room["room_type"] == "group")
    assert group["name"] == "人工智能课程协作群"
    assert group["member_count"] == 9
    directs = [room for room in first.json()["rooms"] if room["room_type"] == "direct"]
    assert len(directs) == 7
    assert all(room["member_count"] == 2 for room in directs)
    assert sum(room["peer"]["role"] == "agent" for room in directs) == 6
    assert sum(room["peer"]["role"] == "teacher" for room in directs) == 1
    assert all(room["unread_count"] == 0 for room in directs)
    room_id = group["id"]
    members = mobile_client.get(
        f"/api/v1/mobile/rooms/{room_id}/members", headers=auth(token),
    ).json()["members"]
    agents = [member for member in members if member["role"] == "agent"]
    assert {member["display_name"] for member in agents} == {
        "智狐 · 规划伙伴",
        "阿匠 · 资源伙伴",
        "智灵 · 讲解伙伴",
        "小龙 · 练习伙伴",
        "团团 · 评估伙伴",
        "球球 · 守护伙伴",
    }


def test_named_agent_mentions_resolve_to_group_members():
    from backend.app.api.v1.mobile import _requested_agent, _requested_agent_for_room

    assert _requested_agent("@小龙 请出一道题", []) == (
        "agent-quiz", "小龙 · 练习伙伴",
    )
    assert _requested_agent("请帮我规划", ["agent-planner"]) == (
        "agent-planner", "智狐 · 规划伙伴",
    )
    direct_agent = {
        "room_type": "direct",
        "peer": {"user_id": "agent-quiz", "display_name": "小龙 · 练习伙伴", "role": "agent"},
    }
    assert _requested_agent_for_room(direct_agent, "出一道题", ["agent-planner"]) == (
        "agent-quiz", "小龙 · 练习伙伴",
    )
    assert _requested_agent_for_room(
        {"room_type": "direct", "peer": {"user_id": "teacher", "role": "teacher"}},
        "老师您好", ["ai-assistant"],
    ) is None


def test_mobile_agent_question_is_current_and_greeting_is_concise():
    from backend.app.api.v1.mobile import (
        _greeting_reply,
        _is_short_greeting,
        _mobile_agent_prompt,
        _student_question,
    )

    question = _student_question("@智狐 你好！")
    assert question == "你好"
    assert _is_short_greeting(question)
    reply = _greeting_reply("agent-planner", "智狐 · 规划伙伴")
    assert "智狐" in reply
    assert "学习目标" in reply
    assert len(reply) < 80

    prompt = _mobile_agent_prompt("什么是机器学习？")
    assert "什么是机器学习" in prompt
    assert "只回答" in prompt
    assert "不要使用Markdown" in prompt


def test_mobile_agent_markdown_becomes_plain_chat_text():
    from backend.app.api.v1.mobile import _plain_chat_text

    markdown = "### 分析\n**重点**<br>| 方向 | 建议 |\n|---|---|\n| 复习 | 做题 |\n- [资料](https://example.com)"
    result = _plain_chat_text(markdown)
    assert result == "分析\n重点\n方向 · 建议\n复习 · 做题\n• 资料"
    assert not any(marker in result for marker in ("###", "**", "<br>", "|---"))


def test_server_identity_idempotency_reply_and_read(mobile_client: TestClient):
    token = login(mobile_client, "demo-student-1")
    room_id = room_for(
        mobile_client, token, lambda room: room["room_type"] == "group",
    )["id"]
    payload = {
        "content": "大家好",
        "message_type": "text",
        "client_message_id": "mobile-test-1",
        "mentions": [],
        "payload": {"sender_id": "forged"},
    }
    first = mobile_client.post(
        f"/api/v1/mobile/rooms/{room_id}/messages", headers=auth(token), json=payload,
    )
    duplicate = mobile_client.post(
        f"/api/v1/mobile/rooms/{room_id}/messages", headers=auth(token), json=payload,
    )
    assert first.status_code == 200
    assert first.json()["message"]["sender_id"] == "demo-student-1"
    assert duplicate.json()["message"]["id"] == first.json()["message"]["id"]

    reply = mobile_client.post(
        f"/api/v1/mobile/rooms/{room_id}/messages",
        headers=auth(token),
        json={
            "content": "补充一句",
            "message_type": "text",
            "client_message_id": "mobile-test-2",
            "reply_to_id": first.json()["message"]["id"],
        },
    )
    assert reply.status_code == 200
    assert reply.json()["message"]["reply_to_id"] == first.json()["message"]["id"]
    read = mobile_client.post(
        f"/api/v1/mobile/rooms/{room_id}/read",
        headers=auth(token),
        json={"last_message_id": reply.json()["message"]["id"]},
    )
    assert read.status_code == 200
    assert read.json()["last_message_id"] == reply.json()["message"]["id"]


def test_non_member_cannot_read_room(mobile_client: TestClient):
    owner = login(mobile_client, "demo-student-1")
    room_id = room_for(
        mobile_client,
        owner,
        lambda room: room["room_type"] == "direct" and room["peer"]["user_id"] == "agent-planner",
    )["id"]
    registered = login(mobile_client, "demo-student-21")
    response = mobile_client.get(
        f"/api/v1/mobile/rooms/{room_id}/messages", headers=auth(registered),
    )
    assert response.status_code == 403


def test_direct_agent_chat_routes_without_client_mention(
    mobile_client: TestClient, monkeypatch,
):
    from backend.app.api.v1 import mobile as mobile_api

    def discard_background(coro):
        coro.close()

    monkeypatch.setattr(mobile_api, "_start_background", discard_background)
    token = login(mobile_client, "demo-student-1")
    room_id = room_for(
        mobile_client,
        token,
        lambda room: room["room_type"] == "direct" and room["peer"]["user_id"] == "agent-planner",
    )["id"]
    with mobile_client.websocket_connect("/api/v1/mobile/ws") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        assert websocket.receive_json()["type"] == "auth.ok"
        response = mobile_client.post(
            f"/api/v1/mobile/rooms/{room_id}/messages",
            headers=auth(token),
            json={
                "content": "帮我规划今天的学习",
                "message_type": "text",
                "client_message_id": "mobile-ws-1",
                "mentions": [],
            },
        )
        assert response.status_code == 200
        event = websocket.receive_json()
        assert event["type"] == "message.created"
        assert event["message"]["content"] == "帮我规划今天的学习"
        typing = websocket.receive_json()
        assert typing == {
            "type": "agent.typing",
            "room_id": room_id,
            "agent_id": "agent-planner",
            "agent_name": "智狐 · 规划伙伴",
        }


def test_mobile_resource_scope_and_share(mobile_client: TestClient):
    from backend.app.api.v1.resources import persist_resource

    persist_resource({
        "id": "mobile-private-resource",
        "user_id": "teacher",
        "type": "document",
        "title": "移动端专属讲义",
        "content": "content",
        "content_type": "markdown",
        "agent_name": "teacher",
        "metadata": {
            "scope": "student",
            "status": "published",
            "target_user_ids": ["demo-student-1"],
            "course": "artificial_intelligence",
        },
        "tags": ["移动端"],
        "created_at": time.time(),
    })
    student = login(mobile_client, "demo-student-1")
    other = login(mobile_client, "demo-student-21")
    visible = mobile_client.get("/api/v1/mobile/resources", headers=auth(student))
    hidden = mobile_client.get(
        "/api/v1/mobile/resources/mobile-private-resource", headers=auth(other),
    )
    assert "mobile-private-resource" in [item["id"] for item in visible.json()["items"]]
    assert hidden.status_code == 404

    room_id = room_for(
        mobile_client, student, lambda room: room["room_type"] == "group",
    )["id"]
    shared = mobile_client.post(
        f"/api/v1/mobile/rooms/{room_id}/messages",
        headers=auth(student),
        json={
            "content": "",
            "message_type": "resource_card",
            "client_message_id": "mobile-resource-share-1",
            "payload": {"resource_id": "mobile-private-resource", "title": "forged"},
        },
    )
    assert shared.status_code == 200
    assert shared.json()["message"]["payload"]["title"] == "移动端专属讲义"


def test_mobile_mistake_ownership_and_loop(mobile_client: TestClient):
    student = login(mobile_client, "demo-student-1")
    other = login(mobile_client, "demo-student-21")
    created = mobile_client.post(
        "/api/v1/mobile/mistakes",
        headers=auth(student),
        json={
            "kp_id": "ml_linear_regression",
            "question": "线性回归的损失函数是什么？",
            "student_answer": "不知道",
            "correct_answer": "均方误差",
            "course": "artificial_intelligence",
        },
    )
    assert created.status_code == 200
    mistake_id = created.json()["mistake_id"]
    detail = mobile_client.get(
        f"/api/v1/mobile/mistakes/{mistake_id}", headers=auth(student),
    )
    forbidden = mobile_client.get(
        f"/api/v1/mobile/mistakes/{mistake_id}", headers=auth(other),
    )
    resolved = mobile_client.post(
        f"/api/v1/mobile/mistakes/{mistake_id}/resolve", headers=auth(student),
    )
    assert detail.status_code == 200
    assert forbidden.status_code == 404
    assert resolved.json()["status"] == "resolved"
