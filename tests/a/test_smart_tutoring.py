from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_smart_tutor_ask_closes_multimodal_record_loop():
    client = TestClient(app)

    response = client.post(
        "/api/v1/smart-tutor/ask",
        json={
            "user_id": "demo-student-1",
            "question": "请用图和动画讲解 CNN 卷积层为什么能提取局部特征",
            "input_type": "text",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["question_id"]
    assert body["knowledge_point"] in {"cnn", "convolution"}
    assert body["response_mode"] == "text+diagram+animation"
    assert {"profile_agent", "course_expert", "multimodal_agent"}.issubset(
        set(body["used_agents"])
    )
    assert body["outputs"]["text_answer"]
    assert body["outputs"]["diagram"]["format"] == "mermaid"
    assert body["outputs"]["video"]["status"] in {"ready", "degraded"}
    assert body["record"]["question_id"] == body["question_id"]
    assert body["record"]["knowledge_point"] == body["knowledge_point"]
    assert body["record"]["response_mode"] == body["response_mode"]
    assert body["profile_update"]["learning_progress"]["last_question_id"] == body["question_id"]
    assert body["path_update"]["next_kp"] == body["knowledge_point"]


def test_smart_tutor_records_are_queryable_by_user():
    client = TestClient(app)

    created = client.post(
        "/api/v1/smart-tutor/ask",
        json={
            "user_id": "u-smart-record",
            "question": "MLP 梯度怎么从输出层传回隐藏层？",
            "input_type": "text",
        },
    ).json()
    records = client.get("/api/v1/smart-tutor/records/u-smart-record").json()

    assert records["count"] >= 1
    assert any(item["question_id"] == created["question_id"] for item in records["records"])
