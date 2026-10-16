import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
from sqlalchemy import select

from backend.app.agent_runtime import run_audit, run_leases
from backend.app.api.v2 import learning_runs
from backend.app.core.models import AgentRunRecord, AgentCheckpointRecord
from tests.a.test_learning_runs_v2_lifecycle import api as api, create, events
from tests.a.test_learning_run_reconciliation import failed_run, repair


def leased():
    run_id, token = uuid.uuid4().hex, uuid.uuid4().hex
    run_audit.start_run(run_id=run_id, session_id=run_id, user_id="alice", execution_id=token)
    return run_id, token


def expire_clock(factory, run_id):
    with factory() as db:
        db.get(AgentRunRecord, run_id).lease_expires_at = 0
        db.commit()


def test_renew_does_not_revive_expired_lease(api):
    _, factory = api
    run_id, token = leased()
    run_leases.renew(run_id, token)
    expire_clock(factory, run_id)
    with pytest.raises(run_audit.RunStateConflict):
        run_leases.renew(run_id, token)
    assert run_leases.expire(run_id)
    assert not run_leases.expire(run_id)
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "interrupted" and row.lease_expires_at is None
        assert row.metadata_data["result"]["error"] == "execution_lease_expired"


@pytest.mark.parametrize("operation", ["finish", "event", "retrieval"])
def test_expired_executor_cannot_publish(api, operation):
    _, factory = api
    run_id, token = leased()
    expire_clock(factory, run_id)
    with pytest.raises(run_audit.RunStateConflict):
        if operation == "finish":
            run_audit.finish_run(run_id=run_id, status="completed", result={}, started_at=0, execution_id=token)
        elif operation == "event":
            run_audit.checkpoint(run_id=run_id, thread_id=run_id, node_name="generate",
                                 status="node.completed", execution_id=token)
        else:
            run_audit.log_retrieval(run_id=run_id, query="x", evidence=[], latency_ms=0, execution_id=token)
    with factory() as db:
        assert db.get(AgentRunRecord, run_id).status == "running"


def test_review_rotates_token_and_fences_previous_executor(api):
    _, factory = api
    run_id, previous = leased()
    run_audit.finish_run(run_id=run_id, status="awaiting_approval", result={}, started_at=0, execution_id=previous)
    current = uuid.uuid4().hex
    assert run_audit.claim_review(run_id, current)
    with pytest.raises(run_audit.RunStateConflict):
        run_audit.finish_run(run_id=run_id, status="failed", result={}, started_at=0, execution_id=previous)
    run_leases.renew(run_id, current)
    with factory() as db:
        assert db.get(AgentRunRecord, run_id).execution_id == current


def test_startup_sweep_only_retires_expired_executions(api):
    _, factory = api
    expired, _ = leased()
    live, _ = leased()
    legacy = uuid.uuid4().hex
    run_audit.start_run(run_id=legacy, session_id=legacy, user_id="alice")
    expire_clock(factory, expired)
    assert run_leases.expire_batch() == 1
    assert run_leases.expire_batch() == 0
    with factory() as db:
        assert db.get(AgentRunRecord, live).status == "running"
        assert db.get(AgentRunRecord, legacy).status == "running"


def test_concurrent_expiration_emits_one_audit(api):
    _, factory = api
    run_id, _ = leased()
    expire_clock(factory, run_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run_leases.expire, [run_id, run_id]))
    assert sorted(results) == [False, True]
    with factory() as db:
        assert len(db.scalars(select(AgentCheckpointRecord).where(
            AgentCheckpointRecord.run_id == run_id, AgentCheckpointRecord.status == "run.lease_expired")).all()) == 1


def test_expired_running_run_with_final_checkpoint_can_reconcile(api, monkeypatch):
    client, factory = api
    run_id = failed_run(client, monkeypatch)
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        row.status, row.lease_expires_at = "running", 0
        db.commit()
    response = repair(client, run_id)
    assert response.status_code == 200 and response.json()["status"] == "completed"


def test_expired_review_claim_cannot_restore_checkpoint_from_previous_execution(api):
    client, factory = api
    run_id = events(create(client, review=True))[0][1]["run_id"]
    assert run_audit.claim_review(run_id, "new-execution-not-started")
    expire_clock(factory, run_id)
    response = repair(client, run_id)
    assert response.status_code == 409 and response.json()["detail"] == "checkpoint_identity_mismatch"


def test_heartbeat_failure_cancels_graph_and_prevents_success(api, monkeypatch):
    client, factory = api
    stopped = []
    async def generate(*_args):
        try:
            await asyncio.sleep(3)
            return "should not deliver"
        finally:
            stopped.append(True)
    original = run_leases.renew
    calls = []
    def renew(run_id, token):
        calls.append(run_id)
        if len(calls) > 1:
            expire_clock(factory, run_id)
        original(run_id, token)
    monkeypatch.setattr(run_leases, "renew", renew)
    monkeypatch.setattr(run_leases, "HEARTBEAT_SECONDS", .05)
    monkeypatch.setattr(learning_runs._runtime, "generate", generate)
    response = create(client)
    assert stopped and len(calls) >= 2
    assert events(response)[-1][1]["error"] == "execution_lease_lost"
    assert "run.completed" not in response.text


def test_final_delivery_releases_lease_but_preserves_execution_identity(api):
    client, factory = api
    run_id = events(create(client))[0][1]["run_id"]
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.execution_id and row.lease_expires_at is None and row.status == "completed"
