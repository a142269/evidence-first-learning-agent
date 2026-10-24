"""QWEN-301: run queue state machine, worker leases, cancel/timeout and crash recovery.

Every case runs offline: scripted/stub runtimes only, isolated SQLite, no
model, no network, no ``.env`` access.  Delivery semantics are at-least-once;
no exactly-once claim is asserted anywhere.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest
from sqlalchemy import select

from backend.app.agent_runtime import run_audit, run_leases, run_queue, run_worker
from backend.app.agent_runtime.learning_graph import EvidenceFirstGraph
from backend.app.api.v2 import learning_runs
from backend.app.core.models import AgentCheckpointRecord, AgentRunRecord, RetrievalLogRecord
from tests.a.test_learning_package import FINISH, LESSON, PASS, PLAN, PRACTICE, SEARCH
from tests.a.test_learning_package import scripted as scripted
from tests.a.test_learning_runs_v2_lifecycle import api as api, create, events
from backend.app.api.v2.run_lifecycle import WORKFLOW_VERSION

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests" / "helpers" / "run_queue_probe.py"
ALICE = {"Authorization": "Bearer alice"}
TEACHER = {"Authorization": "Bearer teacher"}


def citations(evidence):
    return [{"source": item["source"], "chunk_id": item["chunk_id"], "label": item["source"]}
            for item in evidence]


class StubRuntime:
    """Offline answer-mode runtime; the sleep is a class-level knob for tests."""

    citations = staticmethod(citations)
    generate_seconds = 0.0

    def retrieve(self, *_args):
        return [{"source": "queue.md", "chunk_id": "c1", "content": "队列测试证据"}]

    async def generate(self, *_args):
        if StubRuntime.generate_seconds:
            await asyncio.sleep(StubRuntime.generate_seconds)
        return "队列 worker 的测试回答"


def enqueue(client, *, session_id="queue-session", mode="answer", review=False,
             message="什么是 RAG？"):
    response = client.post("/api/v2/learning-runs/enqueue", headers=ALICE,
        json={"message": message, "session_id": session_id, "mode": mode,
              "require_approval": review})
    assert response.status_code == 200, response.text
    return response.json()


def queue_meta(factory, run_id):
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        return dict(row.metadata_data or {}).get("queue", {})


def row_status(factory, run_id):
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        return row.status, row.execution_id, row.lease_expires_at


def checkpoints(factory, run_id, status):
    with factory() as db:
        return db.query(AgentCheckpointRecord).filter_by(run_id=run_id, status=status).all()


def stub_graph(monkeypatch):
    graph = EvidenceFirstGraph(StubRuntime())
    monkeypatch.setattr(learning_runs, "_graph", graph)
    return graph


def force_lease_expiry(factory, run_id):
    with factory() as db:
        db.get(AgentRunRecord, run_id).lease_expires_at = 0
        db.commit()


def wait_for_row(factory, run_id, predicate, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with factory() as db:
            row = db.get(AgentRunRecord, run_id)
            if predicate(row):
                return row
        time.sleep(0.02)
    raise AssertionError("row never reached the expected state")


# 1. Creation is decoupled: enqueue returns a queryable id and executes nothing.
def test_enqueue_returns_queryable_queued_run(api):
    client, factory = api
    queued = enqueue(client)
    assert queued["status"] == "queued" and queued["workflow_version"]
    run_id = queued["run_id"]
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "queued" and row.execution_id is None and row.lease_expires_at is None
        assert row.workflow_type == "evidence_first_learning"
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "queued" and saved["result"] == {}
    assert [c.status for c in checkpoints(factory, run_id, "run.queued")] == ["run.queued"]
    assert not checkpoints(factory, run_id, "run.started")
    # The synchronous endpoint keeps its own contract beside the queue.
    assert events(create(client))[-1][0] == "run.completed"


def test_enqueue_package_mode_requires_login(api):
    client, _ = api
    response = client.post("/api/v2/learning-runs/enqueue",
        json={"message": "解释 RAG", "mode": "learning_package"})
    assert response.status_code == 401 and response.json()["detail"] == "authorization_required"


# 2. A worker claims, heartbeats, executes and settles through the shared contract.
def test_worker_claims_and_completes_run(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    run_id = enqueue(client)["run_id"]
    assert run_worker.work_once("w1") == "completed"
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "completed" and row.success_count == 1 and row.lease_expires_at is None
        assert row.metadata_data["result"]["answer"].startswith("队列 worker 的测试回答")
        assert row.metadata_data["result"]["citations"][0]["chunk_id"] == "c1"
        assert db.scalars(select(RetrievalLogRecord).where(
            RetrievalLogRecord.run_id == run_id)).all()
    claimed = checkpoints(factory, run_id, "run.claimed")
    assert claimed[0].state_data == {"attempts": 1, "worker_id": "w1"}
    assert len(checkpoints(factory, run_id, "run.completed")) == 1
    assert not checkpoints(factory, run_id, "run.reconciled")
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "completed" and saved["result"]["answer"]
    assert run_worker.work_once("w2") == "idle"


def test_two_workers_never_double_claim(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    StubRuntime.generate_seconds = 0.2
    try:
        run_id = enqueue(client)["run_id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(lambda worker: run_worker.work_once(worker), ["w1", "w2"]))
        assert outcomes == ["completed", "idle"]
        assert queue_meta(factory, run_id)["attempts"] == 1
    finally:
        StubRuntime.generate_seconds = 0.0


def test_heartbeat_renews_lease_during_execution(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    StubRuntime.generate_seconds = 0.5
    original = run_leases.renew
    calls = []

    def renew(run_id, execution_id):
        calls.append(execution_id)
        original(run_id, execution_id)

    monkeypatch.setattr(run_leases, "renew", renew)
    monkeypatch.setattr(run_leases, "HEARTBEAT_SECONDS", 0.05)
    try:
        run_id = enqueue(client)["run_id"]
        assert run_worker.work_once("w-heartbeat") == "completed"
    finally:
        StubRuntime.generate_seconds = 0.0
    assert len(calls) >= 3 and row_status(factory, run_id)[0] == "completed"


# 3. Timeout and cancel enter explicit states and never leak a lease.
def test_timeout_marks_run_failed(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    StubRuntime.generate_seconds = 5.0
    try:
        run_id = enqueue(client)["run_id"]
        assert run_worker.work_once("w-slow", timeout_seconds=0.2) == "failed"
    finally:
        StubRuntime.generate_seconds = 0.0
    status, execution_id, lease = row_status(factory, run_id)
    assert status == "failed" and lease is None
    with factory() as db:
        assert db.get(AgentRunRecord, run_id).metadata_data["result"] == {"error": "run_timeout"}
    assert len(checkpoints(factory, run_id, "run.failed")) == 1


def test_cancel_queued_run_is_never_claimed(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    run_id = enqueue(client)["run_id"]
    response = client.post(f"/api/v2/learning-runs/{run_id}/cancel", headers=ALICE)
    assert response.status_code == 200 and response.json()["status"] == "cancelled"
    assert run_queue.claim_next_run("w1") is None
    assert run_worker.work_once("w1") == "idle"
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "cancelled" and row.lease_expires_at is None
        assert row.metadata_data["result"] == {"cancelled": True}
    assert len(checkpoints(factory, run_id, "run.cancelled")) == 1
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "cancelled"


def test_cancel_running_run_fences_the_worker(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    StubRuntime.generate_seconds = 0.8
    run_id = enqueue(client)["run_id"]
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            executing = pool.submit(run_worker.work_once, "w-running")
            wait_for_row(factory, run_id, lambda row: row.status == "running")
            response = client.post(f"/api/v2/learning-runs/{run_id}/cancel", headers=ALICE)
            assert response.status_code == 200
            assert executing.result(timeout=10) == "cancelled"
    finally:
        StubRuntime.generate_seconds = 0.0
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "cancelled" and row.metadata_data["result"] == {"cancelled": True}
    # The fenced worker wrote no terminal event of its own.
    assert not checkpoints(factory, run_id, "run.failed")
    assert not checkpoints(factory, run_id, "run.completed")


def test_cancel_conflicts_are_stable(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    run_id = enqueue(client)["run_id"]
    assert run_worker.work_once("w1") == "completed"
    response = client.post(f"/api/v2/learning-runs/{run_id}/cancel", headers=ALICE)
    assert response.status_code == 409 and response.json()["detail"] == "run_not_cancellable"
    # A /stream-created running run keeps its own semantics: never queue-cancelled.
    legacy = uuid.uuid4().hex
    run_audit.start_run(run_id=legacy, session_id=legacy, user_id="alice", metadata={
        "request": {"message": "什么是 RAG？", "course_id": "artificial_intelligence",
                    "session_id": legacy, "user_id": "alice", "require_approval": False,
                    "mode": "answer"},
        "thread_id": legacy, "workflow_version": WORKFLOW_VERSION})
    response = client.post(f"/api/v2/learning-runs/{legacy}/cancel", headers=ALICE)
    assert response.status_code == 409 and response.json()["detail"] == "run_not_queued"


# 4. Crash recovery: an expired lease is re-claimable, at-least-once, with bounds.
def test_expired_lease_can_be_reclaimed_by_another_worker(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    run_id = enqueue(client)["run_id"]
    first = run_queue.claim_next_run("w1")
    assert first["run_id"] == run_id and first["attempts"] == 1
    force_lease_expiry(factory, run_id)
    second = run_queue.claim_next_run("w2")
    assert second["attempts"] == 2 and second["execution_id"] != first["execution_id"]
    status, execution_id, lease = row_status(factory, run_id)
    assert status == "running" and execution_id == second["execution_id"] and lease is not None
    # The dead execution is fenced: its heartbeats and results are rejected.
    with pytest.raises(run_audit.RunStateConflict):
        run_leases.renew(run_id, first["execution_id"])
    run_leases.renew(run_id, second["execution_id"])


def test_attempts_exhausted_fails_the_run(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    run_id = enqueue(client)["run_id"]
    for expected_attempts in (1, 2):
        run_queue.claim_next_run(f"w{expected_attempts}")
        force_lease_expiry(factory, run_id)
        assert queue_meta(factory, run_id)["attempts"] == expected_attempts
    assert run_queue.claim_next_run("w3") is None
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "failed" and row.lease_expires_at is None
        assert row.metadata_data["result"] == {"error": run_queue.ATTEMPTS_EXHAUSTED}
    exhausted = checkpoints(factory, run_id, "run.queue_exhausted")
    # attempts counts claims: two executions plus the third, retiring claim.
    assert exhausted[0].state_data == {"attempts": 3}
    assert queue_meta(factory, run_id)["retired_by"] == "w3"


def test_legacy_interrupted_run_is_not_reclaimed(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    legacy = events(create(client))[0][1]["run_id"]
    with factory() as db:
        row = db.get(AgentRunRecord, legacy)
        row.status, row.lease_expires_at = "running", 0
        db.commit()
    assert run_leases.expire(legacy)
    run_id = enqueue(client)["run_id"]
    assert run_queue.claim_next_run("w1")["run_id"] == run_id
    with factory() as db:
        assert db.get(AgentRunRecord, legacy).status == "interrupted"


def test_live_zombie_worker_cannot_publish_after_reclaim(api, monkeypatch):
    client, factory = api
    stub_graph(monkeypatch)
    StubRuntime.generate_seconds = 1.0
    run_id = enqueue(client)["run_id"]
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            zombie = pool.submit(run_worker.work_once, "w-zombie")
            wait_for_row(factory, run_id, lambda row: row.status == "running")
            force_lease_expiry(factory, run_id)
            assert run_worker.work_once("w-rescue") == "completed"
            assert zombie.result(timeout=10) == "lost_lease"
    finally:
        StubRuntime.generate_seconds = 0.0
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "completed" and row.success_count == 1
        assert row.metadata_data["queue"]["attempts"] == 2
        assert row.metadata_data["result"]["answer"].startswith("队列 worker 的测试回答")
    assert len(checkpoints(factory, run_id, "run.completed")) == 1


# 5. A killed worker process loses nothing: another process re-claims and finishes.
def test_killed_worker_process_is_reclaimed_and_completed(api, tmp_path):
    client, factory = api
    run_id = enqueue(client, session_id="queue-crash")["run_id"]
    with factory() as db:
        fixture_file = Path(db.get_bind().engine.url.database)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT), os.environ.get("PYTHONPATH", "")]),
           "PYTHONIOENCODING": "utf-8"}

    crashed = subprocess.Popen([sys.executable, str(PROBE), str(fixture_file), "hang"],
                               cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        wait_for_row(factory, run_id, lambda row: row.status == "running")
        meta = queue_meta(factory, run_id)
        assert meta["worker_id"] == "probe-hang" and meta["attempts"] == 1
    finally:
        crashed.kill()
        crashed.wait(timeout=10)
    force_lease_expiry(factory, run_id)
    result = subprocess.run([sys.executable, str(PROBE), str(fixture_file), "quick"],
                            cwd=ROOT, env=env, capture_output=True, encoding="utf-8", timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["outcome"] == "completed"
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "completed" and row.success_count == 1
        assert row.metadata_data["queue"]["attempts"] == 2
        assert row.metadata_data["queue"]["worker_id"] == "probe-quick"
        assert row.metadata_data["result"]["answer"].startswith("队列 worker 探针的测试回答")
    claimed = [c.state_data["worker_id"] for c in checkpoints(factory, run_id, "run.claimed")]
    assert claimed == ["probe-hang", "probe-quick"]
    assert len(checkpoints(factory, run_id, "run.completed")) == 1
    saved = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert saved["status"] == "completed"


# 6. API compatibility: a queued package run reaches human review and resumes.
def test_queued_package_run_reaches_review_and_teacher_resume(scripted):
    client, factory, replies, _ = scripted
    run_id = enqueue(client, session_id="queue-review", mode="learning_package", review=True,
                     message="解释 RAG 并给我三道练习")["run_id"]
    replies.extend([PLAN, SEARCH, FINISH, LESSON, PRACTICE, PASS])
    assert run_worker.work_once("w-package") == "awaiting_approval"
    with factory() as db:
        row = db.get(AgentRunRecord, run_id)
        assert row.status == "awaiting_approval"
        assert row.metadata_data["result"]["approval"]["run_id"] == run_id
    assert len(checkpoints(factory, run_id, "review.required")) == 1
    student = client.get(f"/api/v2/learning-runs/{run_id}", headers=ALICE).json()
    assert student["status"] == "awaiting_approval" and student["result"] == {"review_required": True}
    approved = client.post(f"/api/v2/learning-runs/{run_id}/resume", headers=TEACHER,
                           json={"approved": True})
    final = events(approved)[-1][1]
    assert events(approved)[-1][0] == "run.completed"
    assert final["status"] == "completed" and final["learning_package"]["review"]["approved"]
