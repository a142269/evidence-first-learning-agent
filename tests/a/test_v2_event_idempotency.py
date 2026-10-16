from tests.a.test_learning_runs_v2_lifecycle import api as api, events


def test_events_have_durable_monotonic_sequence_and_after_cursor(api):
    client, _ = api
    response = client.post("/api/v2/learning-runs/stream",
        headers={"Authorization": "Bearer alice"},
        json={"message": "解释 RAG", "course_id": "artificial_intelligence"})
    emitted = events(response)
    run_id = emitted[0][1]["run_id"]
    sequences = [data["event_sequence"] for name, data in emitted
                 if isinstance(data.get("event_sequence"), int)]
    assert sequences == sorted(set(sequences))
    assert sequences[0] == 1 and "id: 1\n" in response.text
    saved = client.get(f"/api/v2/learning-runs/{run_id}/events?after=1",
                       headers={"Authorization": "Bearer alice"}).json()["events"]
    assert [item["event_sequence"] for item in saved] == sorted(
        item["event_sequence"] for item in saved)
    assert all(item["event_sequence"] > 1 for item in saved)
    assert saved[-1]["status"] == "run.completed"


def test_idempotency_key_replays_result_without_new_model_call(api):
    client, factory = api
    headers = {"Authorization": "Bearer alice", "Idempotency-Key": "learning-request-001"}
    payload = {"message": "解释 RAG", "course_id": "artificial_intelligence"}
    first = events(client.post("/api/v2/learning-runs/stream", headers=headers, json=payload))
    second = events(client.post("/api/v2/learning-runs/stream", headers=headers, json=payload))
    assert first[-1][0] == second[-1][0] == "run.completed"
    assert first[0][1]["run_id"] == second[0][1]["run_id"]
    assert second[0][1]["idempotent_replay"] is True
    from backend.app.core.models import AgentRunRecord
    with factory() as db:
        assert db.query(AgentRunRecord).count() == 1
    conflict = client.post("/api/v2/learning-runs/stream", headers=headers,
                           json={"message": "另一个问题", "course_id": "artificial_intelligence"})
    assert conflict.status_code == 409 and conflict.json()["detail"] == "idempotency_key_conflict"
