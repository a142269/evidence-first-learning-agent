"""QWEN-341: run-level metrics recording, /metrics exposure and access boundary.

The recorders must never break delivery, so the hooks under test are the same
one-liners the streaming path, queue worker, tool dispatcher and quota fences
call.  Telemetry is reset per test; the registry re-bootstraps every default
metric name on next use.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.agent_runtime.learning_package import PackageFailure
from backend.app.core.telemetry import get_telemetry, reset_telemetry


@pytest.fixture(autouse=True)
def _fresh_telemetry():
    reset_telemetry()
    yield
    reset_telemetry()


def _record(mode="answer", status="completed", latency_ms=1500, budget=None):
    result = {"latency_ms": latency_ms}
    if budget is not None:
        result["budget"] = budget
    return SimpleNamespace(request=SimpleNamespace(mode=mode), status=status, result=result)


# ---------------------------------------------------------------- settled runs

def test_settled_run_counts_outcome_latency_and_cost():
    from backend.app.services import run_metrics

    run_metrics.record_settled(_record(mode="learning_package", latency_ms=1500,
                                       budget={"cost": {"status": "estimated",
                                                        "amount_cny": 0.5}}))
    assert get_telemetry().counter("learning_runs_total").value(
        mode="learning_package", status="completed") == 1.0
    assert get_telemetry().counter("run_cost_yuan_total").value(
        mode="learning_package") == 0.5
    export = get_telemetry().export_prometheus()
    assert 'learning_run_duration_seconds_count{mode="learning_package"} 1' in export
    assert 'learning_run_duration_seconds_sum{mode="learning_package"} 1.5' in export


def test_settled_run_without_reported_cost_stays_unknown():
    from backend.app.services import run_metrics

    run_metrics.record_settled(_record(budget={}))
    assert get_telemetry().counter("run_cost_unknown_runs_total").value(mode="answer") == 1.0
    assert get_telemetry().counter("run_cost_yuan_total").value(mode="answer") == 0.0


def test_settled_run_without_latency_skips_histogram():
    from backend.app.services import run_metrics

    run_metrics.record_settled(_record(latency_ms=None))
    assert "learning_run_duration_seconds_bucket" not in get_telemetry().export_prometheus()
    assert get_telemetry().counter("learning_runs_total").value(
        mode="answer", status="completed") == 1.0


def test_apply_settled_state_records_one_metric():
    """Integration: the shared delivery contract settles exactly one metric."""
    from backend.app.api.v2 import run_lifecycle

    record = run_lifecycle.RunRecord(
        "metrics-settle", run_lifecycle.LearningRunRequest(message="RAG"),
        started_at=time.time() - 2)
    run_lifecycle.apply_settled_state(record, {"answer": "ok", "citations": [], "evidence": []})
    assert record.status == "completed"
    assert get_telemetry().counter("learning_runs_total").value(
        mode="answer", status="completed") == 1.0
    assert 'learning_run_duration_seconds_count{mode="answer"} 1' in \
        get_telemetry().export_prometheus()


# ------------------------------------------------------- errors / tools / queue

def test_error_classification_uses_stable_codes():
    from backend.app.services import run_metrics

    run_metrics.record_error("learning_package_no_evidence")
    run_metrics.record_error("learning_package_no_evidence")
    run_metrics.record_error("")
    errors = get_telemetry().counter("learning_run_errors_total")
    assert errors.value(code="learning_package_no_evidence") == 2.0
    assert errors.value(code="unknown") == 1.0


def test_tool_call_metrics_by_tool_and_status():
    from backend.app.services import run_metrics

    run_metrics.record_tool_call("web_search", "success")
    run_metrics.record_tool_call("web_search", "denied")
    calls = get_telemetry().counter("learning_tool_calls_total")
    assert calls.value(tool="web_search", status="success") == 1.0
    assert calls.value(tool="web_search", status="denied") == 1.0


def test_queue_claim_counter_and_pending_gauge():
    from backend.app.services import run_metrics

    run_metrics.record_queue_claim()
    run_metrics.record_queue_claim()
    run_metrics.set_queue_pending(3)
    assert get_telemetry().counter("queue_claimed_total").value() == 2.0
    assert get_telemetry().gauge("learning_queue_pending_runs").value() == 3.0
    run_metrics.set_queue_pending(-1)
    assert get_telemetry().gauge("learning_queue_pending_runs").value() == 0.0


# ------------------------------------------------------------------ quota hook

def test_quota_refusal_records_dimension_metric(monkeypatch):
    from backend.app.services import quota, run_metrics

    monkeypatch.setenv("QUOTA_ENABLED", "true")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_MINUTE", "1")
    user = "metrics-quota-user"
    assert quota.check_run_creation(user, "artificial_intelligence").allowed
    refused = quota.check_run_creation(user, "artificial_intelligence")
    assert not refused.allowed and refused.dimension == "requests"
    assert get_telemetry().counter("quota_rejected_total").value(dimension="requests") == 1.0


# ------------------------------------------------------------- /metrics surface

def test_metrics_endpoint_exposes_run_metrics():
    from backend.app import main
    from backend.app.services import run_metrics
    from fastapi.testclient import TestClient

    run_metrics.record_settled(_record())
    response = TestClient(main.app).get("/metrics")
    assert response.status_code == 200
    assert "# TYPE learning_runs_total counter" in response.text
    assert "learning_run_duration_seconds_bucket" in response.text
    assert 'learning_runs_total{mode="answer",status="completed"} 1' in response.text


def test_metrics_endpoint_requires_privileged_role_in_production(monkeypatch):
    from backend.app import main
    from fastapi.testclient import TestClient

    monkeypatch.setenv("APP_ENV", "production")

    def parse(header: str | None) -> str:
        if not header:
            raise HTTPException(401, "authorization_required")
        return header

    monkeypatch.setattr(main, "_parse_bearer_token", parse)
    monkeypatch.setattr(main, "_get_session",
                        lambda token: SimpleNamespace(
                            role="teacher" if "teacher" in token else "student"))
    client = TestClient(main.app)
    assert client.get("/metrics").status_code == 401
    denied = client.get("/metrics", headers={"Authorization": "Bearer student-token"})
    assert denied.status_code == 403 and denied.json()["detail"] == "privileged_role_required"
    allowed = client.get("/metrics", headers={"Authorization": "Bearer teacher-token"})
    assert allowed.status_code == 200 and "learning_runs_total" in allowed.text


# ------------------------------------------------- stream failure hook (no DB)

@pytest.mark.asyncio
async def test_stream_failure_records_error_metric(monkeypatch):
    from backend.app.api.v2 import run_lifecycle
    from backend.app.agent_runtime import run_audit

    async def save(record):
        return 1

    async def operation(_on_event):
        raise PackageFailure("learning_package_no_evidence")

    monkeypatch.setattr(run_lifecycle, "finish", save)
    monkeypatch.setattr(run_audit, "log_retrieval", lambda **kwargs: None)
    record = run_lifecycle.RunRecord("metrics-fail", run_lifecycle.LearningRunRequest(message="RAG"))
    stream = run_lifecycle.stream_result(record, operation)
    assert "run.started" in await stream.__anext__()
    assert "run.failed" in await stream.__anext__()
    assert get_telemetry().counter("learning_run_errors_total").value(
        code="learning_package_no_evidence") == 1.0
