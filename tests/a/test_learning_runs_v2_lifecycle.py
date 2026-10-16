import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.agent_runtime import checkpointing, run_audit
from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph
from backend.app.api.v2 import access, learning_runs, run_lifecycle
from backend.app.core.models import AgentCheckpointRecord, AgentRunRecord, RetrievalLogRecord


def events(response):
    result, name = [], ""
    for line in response.text.splitlines():
        if line.startswith("event: "):
            name = line[7:]
        elif line.startswith("data: "):
            result.append((name, json.loads(line[6:])))
    return result


@pytest.fixture
def api(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'runs.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    for model in (AgentRunRecord, AgentCheckpointRecord, RetrievalLogRecord):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(run_audit, "SessionLocal", factory)
    monkeypatch.setattr(run_lifecycle, "SessionLocal", factory)
    monkeypatch.setenv("V2_AUTH_REQUIRED", "true")
    monkeypatch.setenv("V2_REQUIRE_CHECKPOINTER", "false")
    monkeypatch.setenv("V2_STUDENT_COURSES", "artificial_intelligence")
    monkeypatch.setenv("V2_TEACHER_COURSES", "artificial_intelligence")

    def principal(header):
        identities = {"Bearer alice": ("alice", "student"), "Bearer bob": ("bob", "student"),
                      "Bearer teacher": ("teacher", "teacher")}
        if not header:
            return None
        if header not in identities:
            raise HTTPException(401, "invalid_token")
        return access.V2Principal(*identities[header], True)

    monkeypatch.setattr(access, "_principal_from_authorization", principal)
    monkeypatch.setattr(run_lifecycle, "_principal_from_authorization", principal)
    from langgraph.checkpoint.memory import InMemorySaver
    saver = InMemorySaver()
    monkeypatch.setattr(checkpointing, "get_checkpointer", lambda: saver)
    monkeypatch.setattr(learning_runs, "_graph", EvidenceFirstGraph(learning_runs._runtime))
    monkeypatch.setattr(learning_runs._runtime, "retrieve", lambda *_: [
        {"chunk_id": "c1", "source": "chapter.md", "content": "private-evidence", "score": .9},
    ])

    async def generate(message, *_args):
        return "private-draft: " + message

    monkeypatch.setattr(learning_runs._runtime, "generate", generate)
    app = FastAPI()
    app.include_router(learning_runs.router)
    with TestClient(app) as client:
        yield client, factory
    engine.dispose()


def create(client, message="什么是 RAG？", review=False):
    return client.post("/api/v2/learning-runs/stream", headers={"Authorization": "Bearer alice"},
                       json={"message": message, "session_id": "same-session", "require_approval": review})


def test_live_nodes_and_persisted_result(api):
    client, factory = api
    response = create(client)
    output = events(response)
    names = [name for name, _ in output]
    assert response.status_code == 200
    assert names.index("retrieval.completed") < next(i for i, item in enumerate(output)
        if item[0] == "node.started" and item[1]["node"] == "generate")
    assert names[-1] == "run.completed"
    run_id = output[0][1]["run_id"]
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.metadata_data["thread_id"] == run_id
        assert row.session_id == "same-session"
        assert row.status == "completed"
    result = client.get(f"/api/v2/learning-runs/{run_id}", headers={"Authorization": "Bearer alice"})
    assert result.json()["result"]["citations"][0]["chunk_id"] == "c1"


def test_parallel_same_session_runs_have_distinct_checkpoints(api):
    client, factory = api
    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(lambda msg: events(create(client, msg, True)), ["解释 RAG", "解释神经网络"]))
    ids = [output[0][1]["run_id"] for output in outputs]
    assert len(set(ids)) == 2
    assert all(output[-1][0] == "review.required" for output in outputs)
    for run_id in ids:
        with factory() as db:
            row = db.get(AgentRunRecord, run_id)
            assert row.metadata_data["thread_id"] == run_id
    for run_id, question in zip(ids, ["解释 RAG", "解释神经网络"]):
        response = client.post(f"/api/v2/learning-runs/{run_id}/resume",
            headers={"Authorization": "Bearer teacher"}, json={"approved": True})
        assert question in events(response)[-1][1]["answer"]


def test_pending_review_does_not_leak_to_student_and_student_cannot_approve(api):
    client, _ = api
    response = create(client, review=True)
    assert "private-draft" not in response.text and "chapter.md" not in response.text
    run_id = events(response)[0][1]["run_id"]
    path = f"/api/v2/learning-runs/{run_id}"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer bob"}).status_code == 403
    student = client.get(path, headers={"Authorization": "Bearer alice"})
    assert student.json()["result"] == {"review_required": True}
    teacher = client.get(path, headers={"Authorization": "Bearer teacher"})
    assert "private-draft" in teacher.text
    assert client.post(path + "/resume", headers={"Authorization": "Bearer alice"},
                       json={"approved": True}).status_code == 403
    rejected = client.post(path + "/resume", headers={"Authorization": "Bearer teacher"},
                           json={"approved": False, "edited_answer": "private-rejected-text"})
    final = events(rejected)[-1][1]
    assert final["status"] == "rejected"
    assert final["evidence"] == final["citations"] == []
    assert "private-" not in rejected.text
    assert "private-" not in client.get(path, headers={"Authorization": "Bearer alice"}).text


def test_resume_reloads_from_database_and_rejects_duplicate(api, monkeypatch):
    client, _ = api
    run_id = events(create(client, review=True))[0][1]["run_id"]
    monkeypatch.setattr(learning_runs, "_graph", EvidenceFirstGraph(learning_runs._runtime))
    path = f"/api/v2/learning-runs/{run_id}/resume"
    args = {"headers": {"Authorization": "Bearer teacher"}, "json": {"approved": True}}
    assert events(client.post(path, **args))[-1][0] == "run.completed"
    assert client.post(path, **args).status_code == 409


def test_atomic_review_claim_allows_one_winner(api):
    client, _ = api
    run_id = events(create(client, review=True))[0][1]["run_id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(run_audit.claim_review, [run_id, run_id]))
    assert sorted(claims) == [False, True]


@pytest.mark.parametrize("message", ["更新我的学习画像", "请发布课程资料给全班学生", "请删除知识库资料"])
def test_review_flag_cannot_enable_writes(api, monkeypatch, message):
    client, _ = api
    def forbidden(*_args):
        raise AssertionError("must not retrieve")
    monkeypatch.setattr(learning_runs._runtime, "retrieve", forbidden)
    response = create(client, message, True)
    final = events(response)[-1][1]
    assert final["quality"]["safety_refusal"]
    assert final["evidence"] == []
    assert "review.required" not in response.text


def test_errors_are_redacted_on_stream_and_lookup(api, monkeypatch):
    client, _ = api
    async def fail(*_args):
        raise RuntimeError("sk-private postgres://secret dbpassword")
    monkeypatch.setattr(learning_runs._runtime, "generate", fail)
    response = create(client)
    run_id = events(response)[0][1]["run_id"]
    assert events(response)[-1] == ("run.failed", {"run_id": run_id, "error": "run_execution_failed"})
    assert "sk-private" not in response.text
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers={"Authorization": "Bearer alice"})
    assert saved.json()["status"] == "failed"
    assert "secret" not in saved.text


def test_database_failure_cannot_report_success(api, monkeypatch):
    client, _ = api
    def fail():
        raise RuntimeError("password-secret")
    monkeypatch.setattr(run_audit, "SessionLocal", fail)
    response = create(client)
    assert response.status_code == 503
    assert "password-secret" not in response.text


def test_review_unavailable_is_not_reported_as_successful_interrupt(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(checkpointing, "get_checkpointer", lambda: None)
    assert create(client, review=True).status_code == 503


def test_thread_id_injection_rejected(api):
    client, _ = api
    response = client.post("/api/v2/learning-runs/stream", headers={"Authorization": "Bearer alice"},
        json={"message": "hello", "thread_id": "someone-else"})
    assert response.status_code == 422


def test_event_read_enforces_owner_and_excludes_source_contents(api):
    client, _ = api
    run_id = events(create(client, review=True))[0][1]["run_id"]
    path = f"/api/v2/learning-runs/{run_id}/events"
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer bob"}).status_code == 403
    response = client.get(path, headers={"Authorization": "Bearer alice"})
    assert response.status_code == 200 and response.json()["events"]
    assert "private-" not in response.text and "chapter.md" not in response.text


def test_claimed_review_still_hides_draft_from_owner(api):
    client, _ = api
    run_id = events(create(client, review=True))[0][1]["run_id"]
    assert run_audit.claim_review(run_id)
    response = client.get(f"/api/v2/learning-runs/{run_id}", headers={"Authorization": "Bearer alice"})
    assert response.json()["status"] == "reviewing"
    assert "private-" not in response.text


@pytest.mark.asyncio
async def test_graph_interrupt_directly(api):
    state = await learning_runs._graph.invoke({"run_id": "direct", "thread_id": "direct",
        "message": "RAG", "course_id": "artificial_intelligence", "user_id": "alice", "require_approval": True})
    assert state["__interrupt__"]


@pytest.mark.asyncio
async def test_sync_retrieval_does_not_block_event_loop():
    import threading
    entered, release = threading.Event(), threading.Event()
    class Runtime:
        def retrieve(self, *_):
            entered.set()
            assert release.wait(2)
            return []
    graph = EvidenceFirstGraph(Runtime())
    task = asyncio.create_task(graph._retrieve({"message": "x", "course_id": "ai"}))
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        assert not task.done()
    finally:
        release.set()
    assert await task == {"evidence": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("target_status", ["completed", "awaiting_approval", "interrupted"])
async def test_stream_disconnect_preserves_persisted_outcome(monkeypatch, target_status):
    saved = []

    async def save(record):
        saved.append((record.status, dict(record.result)))

    async def operation(_on_event):
        if target_status == "awaiting_approval":
            return {"__interrupt__": [{"reason": "learning_content_review"}]}
        return {"answer": "saved answer"}

    monkeypatch.setattr(run_lifecycle, "finish", save)
    monkeypatch.setattr(run_audit, "log_retrieval", lambda **kwargs: None)
    record = run_lifecycle.RunRecord("disconnect", run_lifecycle.LearningRunRequest(message="RAG"))
    stream = run_lifecycle.stream_result(record, operation)
    assert "run.started" in await stream.__anext__()
    if target_status != "interrupted":
        delivered = await stream.__anext__()
        assert ("answer.delta" if target_status == "completed" else "review.required") in delivered
    await stream.aclose()
    assert len(saved) == 1
    assert saved[0][0] == target_status
    if target_status == "completed":
        assert saved[0][1]["answer"] == "saved answer"
