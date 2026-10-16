"""Fault injection at the Graph/Run persistence boundary; no live providers."""
import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from backend.app.agent_runtime import checkpointing, run_audit
from backend.app.api.v2 import learning_runs, run_lifecycle
from backend.app.core.models import AgentCheckpointRecord, AgentRunRecord
from tests.a.test_learning_runs_v2_lifecycle import api as api, create, events
from tests.a.test_learning_package import (
    scripted as scripted, package, PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS,
)

TEACHER = {"Authorization": "Bearer teacher"}


def fail_next_finish(monkeypatch, status):
    original = run_audit.finish_run
    failures = []

    def write(**kwargs):
        if kwargs["status"] == status and not failures:
            failures.append(status)
            raise run_audit.RunPersistenceError("injected_result_write_failure")
        return original(**kwargs)

    monkeypatch.setattr(run_audit, "finish_run", write)
    return failures


def failed_run(client, monkeypatch, review=False):
    failures = fail_next_finish(monkeypatch, "awaiting_approval" if review else "completed")
    response = create(client, review=review)
    assert failures and events(response)[-1][0] == "run.failed"
    assert "private-draft" not in response.text
    return events(response)[0][1]["run_id"]


def repair(client, run_id, headers=TEACHER):
    return client.post(f"/api/v2/learning-runs/{run_id}/reconcile", headers=headers)


def forbid_execution(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("reconciliation must not invoke model or retrieval")
    monkeypatch.setattr(learning_runs._runtime, "retrieve", forbidden)
    monkeypatch.setattr(learning_runs._runtime, "generate", forbidden)
    monkeypatch.setattr(learning_runs._runtime, "complete_structured", forbidden)


def test_repair_completed_checkpoint_after_result_write_failure(api, monkeypatch):
    client, factory = api
    run_id = failed_run(client, monkeypatch)
    forbid_execution(monkeypatch)
    response = repair(client, run_id)
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["result"]["citations"][0]["chunk_id"] == "c1"
    assert repair(client, run_id).status_code == 409
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.success_count == 1 and row.metadata_data["result"] == response.json()["result"]
        audit = db.scalars(select(AgentCheckpointRecord).where(
            AgentCheckpointRecord.run_id == run_id, AgentCheckpointRecord.status == "run.reconciled")).all()
        assert len(audit) == 1
        assert audit[0].state_data == {"from_status": "failed", "to_status": "completed"}


def test_repair_pending_checkpoint_keeps_student_draft_hidden(api, monkeypatch):
    client, _ = api
    run_id = failed_run(client, monkeypatch, review=True)
    forbid_execution(monkeypatch)
    response = repair(client, run_id)
    assert response.status_code == 200 and response.json()["status"] == "awaiting_approval"
    assert "private-draft" in response.text
    student = client.get(f"/api/v2/learning-runs/{run_id}", headers={"Authorization": "Bearer alice"})
    assert student.json()["result"] == {"review_required": True}
    assert "private-" not in student.text
    resumed = client.post(f"/api/v2/learning-runs/{run_id}/resume", headers=TEACHER, json={"approved": True})
    assert events(resumed)[-1][0] == "run.completed"


@pytest.mark.parametrize("decision", [{"approved": True}, {"approved": True, "edited_answer": "教师替换答案"},
                                     {"approved": False, "edited_answer": "private-rejected-text"}])
def test_repair_after_review_does_not_change_saved_decision(api, monkeypatch, decision):
    client, _ = api
    run_id = events(create(client, review=True))[0][1]["run_id"]
    fail_next_finish(monkeypatch, "completed" if decision["approved"] else "rejected")
    resumed = client.post(f"/api/v2/learning-runs/{run_id}/resume", headers=TEACHER, json=decision)
    assert events(resumed)[-1][0] == "run.failed"
    forbid_execution(monkeypatch)
    response = repair(client, run_id)
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["review"] == {"approved": decision["approved"]}
    if not decision["approved"]:
        assert body["status"] == "rejected"
        assert body["result"]["citations"] == body["result"]["evidence"] == []
        assert "private-" not in response.text
    elif decision.get("edited_answer"):
        assert "教师替换答案" in body["result"]["answer"]


@pytest.mark.parametrize("headers,code", [({}, 401), ({"Authorization": "Bearer alice"}, 403),
                                        ({"Authorization": "Bearer bob"}, 403)])
def test_repair_requires_reviewer(api, monkeypatch, headers, code):
    client, _ = api
    run_id = failed_run(client, monkeypatch)
    assert repair(client, run_id, headers).status_code == code


@pytest.mark.parametrize("status", ["running", "reviewing", "completed", "rejected", "awaiting_approval"])
def test_active_or_settled_runs_cannot_be_repaired(api, status):
    client, factory = api
    run_id = events(create(client))[0][1]["run_id"]
    with factory() as db:
        db.get(AgentRunRecord, run_id).status = status
        db.commit()
    response = repair(client, run_id)
    assert response.status_code == 409 and response.json()["detail"] == "run_not_reconcilable"


def test_interrupted_run_can_be_repaired(api, monkeypatch):
    client, factory = api
    run_id = failed_run(client, monkeypatch)
    with factory() as db:
        db.get(AgentRunRecord, run_id).status = "interrupted"
        db.commit()
    assert repair(client, run_id).json()["status"] == "completed"


def test_non_terminal_checkpoint_is_not_replayed(api, monkeypatch):
    client, _ = api
    async def fail(*_args):
        raise RuntimeError("model failed")
    monkeypatch.setattr(learning_runs._runtime, "generate", fail)
    run_id = events(create(client))[0][1]["run_id"]
    response = repair(client, run_id)
    assert response.status_code == 409 and response.json()["detail"] == "checkpoint_not_settled"


@pytest.mark.parametrize("field,value", [("user_id", "bob"), ("course_id", "foreign-course"),
                                        ("thread_id", "foreign-thread"), ("require_approval", True)])
def test_checkpoint_identity_mismatch_is_rejected(api, monkeypatch, field, value):
    client, _ = api
    run_id = failed_run(client, monkeypatch)
    state = client.portal.call(learning_runs._graph.settled_checkpoint, run_id)
    async def snapshot(_thread_id):
        return {**state, field: value}
    monkeypatch.setattr(learning_runs._graph, "settled_checkpoint", snapshot)
    response = repair(client, run_id)
    assert response.status_code == 409 and response.json()["detail"] == "checkpoint_identity_mismatch"


def test_checkpoint_failure_is_redacted_and_keeps_run_failed(api, monkeypatch):
    client, _ = api
    run_id = failed_run(client, monkeypatch)
    async def fail(_thread_id):
        raise RuntimeError("private-dsn-password")
    monkeypatch.setattr(learning_runs._graph, "settled_checkpoint", fail)
    response = repair(client, run_id)
    assert response.status_code == 503 and response.json()["detail"] == "checkpoint_unavailable"
    assert "private" not in response.text


def test_absent_checkpointer_is_unavailable(api, monkeypatch):
    client, _ = api
    run_id = failed_run(client, monkeypatch)
    monkeypatch.setattr(checkpointing, "get_checkpointer", lambda: None)
    assert repair(client, run_id).status_code == 503


def test_missing_checkpoint_does_not_create_result(api, monkeypatch):
    client, _ = api
    run_id = failed_run(client, monkeypatch)
    client.portal.call(checkpointing.get_checkpointer().adelete_thread, run_id)
    response = repair(client, run_id)
    assert response.status_code == 409 and response.json()["detail"] == "checkpoint_not_settled"


def test_legacy_workflow_cannot_be_reconciled(api, monkeypatch):
    client, factory = api
    run_id = failed_run(client, monkeypatch)
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        row.metadata_data = {**row.metadata_data, "workflow_version": "legacy"}
        db.commit()
    response = repair(client, run_id)
    assert response.status_code == 409 and response.json()["detail"] == "legacy_run_restart_required"


def test_settled_result_cannot_bypass_required_review(api, monkeypatch):
    client, _ = api
    run_id = failed_run(client, monkeypatch, review=True)
    state = client.portal.call(learning_runs._graph.settled_checkpoint, run_id)
    state.pop("__interrupt__")
    async def snapshot(_thread_id):
        return state
    monkeypatch.setattr(learning_runs._graph, "settled_checkpoint", snapshot)
    response = repair(client, run_id)
    assert response.status_code == 409 and response.json()["detail"] == "checkpoint_not_settled"


@pytest.mark.parametrize("decision", [{"approved": True}, {"approved": True, "edited_answer": "教师修改学习包"},
                                     {"approved": False}])
def test_package_repair_preserves_citation_and_review_contract(scripted, monkeypatch, decision):
    client, _, replies, _ = scripted
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    run_id = events(package(client, review=True))[0][1]["run_id"]
    fail_next_finish(monkeypatch, "completed" if decision["approved"] else "rejected")
    response = client.post(f"/api/v2/learning-runs/{run_id}/resume", headers=TEACHER, json=decision)
    assert events(response)[-1][0] == "run.failed"
    forbid_execution(monkeypatch)
    response = repair(client, run_id)
    assert response.status_code == 200
    result = response.json()["result"]
    if decision == {"approved": True}:
        learning_package = result["learning_package"]
        for artifact in [learning_package["lesson"], *learning_package["exercises"]]:
            assert artifact["citations"] == result["citations"]
        assert result["budget"]["model_calls"] == 6
    else:
        assert "learning_package" not in result
        assert result["citations"] == []
        if decision["approved"]:
            assert result["answer"] == "教师修改学习包"
            assert result["quality"]["human_edited"] is True
        else:
            assert response.json()["status"] == "rejected" and result["evidence"] == []


def test_status_changed_during_snapshot_cannot_be_overwritten(api, monkeypatch):
    client, factory = api
    run_id = failed_run(client, monkeypatch)
    original = learning_runs._graph.settled_checkpoint
    async def snapshot(thread_id):
        state = await original(thread_id)
        with factory() as db:
            db.get(AgentRunRecord, run_id).status = "reviewing"
            db.commit()
        return state
    monkeypatch.setattr(learning_runs._graph, "settled_checkpoint", snapshot)
    response = repair(client, run_id)
    assert response.status_code == 409 and response.json()["detail"] == "run_state_changed"
    with factory() as db:
        assert db.get(AgentRunRecord, run_id).status == "reviewing"


def test_concurrent_repair_has_one_winner(api, monkeypatch):
    client, factory = api
    run_id = failed_run(client, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: repair(client, run_id), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    with factory() as db:
        assert len(db.scalars(select(AgentCheckpointRecord).where(
            AgentCheckpointRecord.run_id == run_id, AgentCheckpointRecord.status == "run.reconciled")).all()) == 1


def test_recovery_audit_failure_rolls_back_status(api, monkeypatch):
    client, factory = api
    run_id = failed_run(client, monkeypatch)
    from sqlalchemy import event
    def fail_audit(_mapper, _connection, target):
        if target.status == "run.reconciled":
            raise RuntimeError("private-db-error")
    event.listen(AgentCheckpointRecord, "before_insert", fail_audit)
    try:
        response = repair(client, run_id)
    finally:
        event.remove(AgentCheckpointRecord, "before_insert", fail_audit)
    assert response.status_code == 503 and "private" not in response.text
    with factory() as db:
        assert db.get(AgentRunRecord, run_id).status == "failed"


@pytest.mark.asyncio
async def test_disconnect_stops_graph_before_recording_interrupted(monkeypatch):
    started, stopped = asyncio.Event(), asyncio.Event()
    async def operation(_on_event):
        started.set()
        try:
            await asyncio.Future()
        finally:
            stopped.set()
    async def save(record):
        assert stopped.is_set()
        assert record.status == "interrupted"
    monkeypatch.setattr(run_lifecycle, "finish", save)
    record = run_lifecycle.RunRecord("cancel", run_lifecycle.LearningRunRequest(message="RAG"))
    stream = run_lifecycle.stream_result(record, operation)
    await stream.__anext__()
    pending = asyncio.create_task(stream.__anext__())
    await started.wait()
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
