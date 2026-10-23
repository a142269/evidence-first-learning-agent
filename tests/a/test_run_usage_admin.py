"""QWEN-104: admin-only visibility of persisted per-run model usage and cost.

Every assertion here checks that the surface stays a pure read: values the
provider never reported must come back as ``null``/``unknown`` instead of a
zero, and no environment tariff may turn into an invented price.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.v2 import access, run_usage_admin
from backend.app.core import database
from backend.app.core.models import AgentRunRecord

LIST_PATH = "/api/v2/admin/run-usage"


def add_run(factory, run_id: str, *, budget: dict | None, created_at: float,
            status: str = "completed", duration_ms: int = 1200, tool_calls: int = 0,
            latency_ms: Any = 900, course_id: str = "artificial_intelligence") -> None:
    result: dict = {"latency_ms": latency_ms}
    if budget is not None:
        result["budget"] = budget
    with factory.begin() as db:
        db.add(AgentRunRecord(id=run_id, user_id="alice", session_id=run_id,
                              workflow_type="evidence_first_learning", status=status,
                              created_at=created_at,
                              duration_ms=duration_ms, tool_calls=tool_calls,
                              metadata_data={"request": {"course_id": course_id, "message": "private"},
                                             "result": result}))


@pytest.fixture
def api(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'usage.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    AgentRunRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.delenv("V2_LLM_INPUT_CNY_PER_MILLION", raising=False)
    monkeypatch.delenv("V2_LLM_OUTPUT_CNY_PER_MILLION", raising=False)

    identities = {"Bearer teacher": ("teacher", "teacher"), "Bearer admin": ("admin", "admin"),
                  "Bearer alice": ("alice", "student")}

    def principal(header):
        if not header:
            return None
        if header not in identities:
            raise HTTPException(401, "invalid_token")
        return access.V2Principal(*identities[header], True)

    monkeypatch.setattr(access, "_principal_from_authorization", principal)
    app = FastAPI()
    app.include_router(run_usage_admin.router)
    with TestClient(app) as client:
        yield client, factory
    engine.dispose()


def test_measured_usage_projects_tokens_calls_and_estimated_cost(api):
    client, factory = api
    add_run(factory, "run-measured", created_at=1_700.0, tool_calls=2, duration_ms=4321,
            budget={"model_calls": 3, "actual_input_tokens": 1200, "actual_output_tokens": 340,
                    "usage_unknown_calls": 0,
                    "cost": {"status": "estimated", "currency": "CNY", "amount_cny": 0.0042}})
    body = client.get(LIST_PATH, headers={"Authorization": "Bearer teacher"}).json()
    assert body["total"] == 1
    run = body["runs"][0]
    assert run["run_id"] == "run-measured"
    assert run["run_status"] == "completed" and run["workflow_type"] == "evidence_first_learning"
    assert run["course_id"] == "artificial_intelligence"
    assert run["usage_status"] == "measured"
    assert run["input_tokens"] == 1200 and run["output_tokens"] == 340
    assert run["model_calls"] == 3 and run["tool_calls"] == 2 and run["usage_unknown_calls"] == 0
    assert run["duration_ms"] == 4321 and run["reported_latency_ms"] == 900
    assert run["cost_status"] == "estimated" and run["cost_cny"] == 0.0042
    assert run["budget_recorded"] is True
    assert run["cost"] == {"status": "estimated", "currency": "CNY", "amount_cny": 0.0042}


def test_missing_provider_usage_stays_unknown_never_zero(api):
    client, factory = api
    add_run(factory, "run-unknown", created_at=1_700.0,
            budget={"model_calls": 2, "usage_unknown_calls": 2,
                    "cost": {"status": "unknown", "currency": "CNY"}})
    run = client.get(f"{LIST_PATH}/run-unknown",
                     headers={"Authorization": "Bearer admin"}).json()
    assert run["input_tokens"] is None and run["output_tokens"] is None
    assert run["usage_unknown_calls"] == 2 and run["model_calls"] == 2
    assert run["usage_status"] == "unknown" and run["cost_status"] == "unknown"
    assert run["cost_cny"] is None
    assert run["cost"]["reason"] == "no_cost_amount_recorded"


def test_partially_measured_run_separates_known_from_unknown_calls(api):
    client, factory = api
    add_run(factory, "run-partial", created_at=1_700.0,
            budget={"model_calls": 4, "actual_input_tokens": 800, "actual_output_tokens": 120,
                    "usage_unknown_calls": 1,
                    "cost": {"status": "unknown", "currency": "CNY", "measured_portion_cny": 0.001}})
    run = client.get(f"{LIST_PATH}/run-partial", headers={"Authorization": "Bearer admin"}).json()
    assert run["usage_status"] == "partial"
    assert (run["input_tokens"], run["output_tokens"], run["usage_unknown_calls"]) == (800, 120, 1)
    assert run["cost"] == {"status": "unknown", "currency": "CNY", "measured_portion_cny": 0.001}
    assert run["cost_cny"] is None


def test_run_without_any_budget_is_labelled_not_recorded(api):
    client, factory = api
    add_run(factory, "run-legacy", created_at=1_700.0, budget=None, tool_calls=5)
    run = client.get(f"{LIST_PATH}/run-legacy", headers={"Authorization": "Bearer admin"}).json()
    assert run["budget_recorded"] is False
    assert run["usage_status"] == "unknown" and run["cost_status"] == "unknown"
    assert run["cost"]["reason"] == "cost_not_recorded"
    assert run["model_calls"] is None and run["input_tokens"] is None
    # Columns keep carrying real values even when the accounting block is absent.
    assert run["tool_calls"] == 5 and run["reported_latency_ms"] == 900


def test_admin_totals_count_unmeasured_runs_instead_of_silently_zeros(api):
    client, factory = api
    add_run(factory, "run-a", created_at=1_703.0, budget={"model_calls": 1,
        "actual_input_tokens": 1000, "actual_output_tokens": 100, "usage_unknown_calls": 0,
        "cost": {"status": "estimated", "currency": "CNY", "amount_cny": 0.001}})
    add_run(factory, "run-b", created_at=1_702.0, budget={"model_calls": 2,
        "usage_unknown_calls": 2, "cost": {"status": "unknown", "currency": "CNY"}})
    add_run(factory, "run-c", created_at=1_701.0, budget=None)
    body = client.get(LIST_PATH, headers={"Authorization": "Bearer teacher"}).json()
    assert [item["run_id"] for item in body["runs"]] == ["run-a", "run-b", "run-c"]
    totals = body["aggregates"]
    assert body["aggregates_scope"] == "current_page"
    assert (totals["runs"], totals["budget_recorded_runs"]) == (3, 2)
    assert totals["usage_status"] == {"measured": 1, "partial": 0, "unknown": 2}
    assert totals["cost_status"] == {"estimated": 1, "unknown": 2}
    assert (totals["input_tokens"], totals["output_tokens"]) == (1000, 100)
    assert (totals["runs_without_token_data"], totals["runs_without_estimated_cost"]) == (2, 2)
    assert totals["usage_unknown_calls"] == 2
    assert totals["cost_cny_estimated_sum"] == pytest.approx(0.001)


def test_pagination_windows_report_page_totals_and_stable_total(api):
    client, factory = api
    for index in range(3):
        add_run(factory, f"run-{index}", created_at=1_700.0 + index, budget=None)
    first = client.get(f"{LIST_PATH}?limit=2", headers={"Authorization": "Bearer admin"}).json()
    assert [item["run_id"] for item in first["runs"]] == ["run-2", "run-1"]
    assert (first["total"], first["limit"], first["offset"]) == (3, 2, 0)
    last = client.get(f"{LIST_PATH}?limit=2&offset=2",
                      headers={"Authorization": "Bearer admin"}).json()
    assert [item["run_id"] for item in last["runs"]] == ["run-0"]
    assert last["total"] == 3 and last["aggregates"]["runs"] == 1
    assert client.get(f"{LIST_PATH}?limit=0",
                      headers={"Authorization": "Bearer admin"}).status_code == 422


def test_surface_is_admin_only_and_never_writes(api):
    client, factory = api
    add_run(factory, "run-1", created_at=1_700.0, budget={"model_calls": 1,
        "actual_input_tokens": 10, "actual_output_tokens": 1, "usage_unknown_calls": 0,
        "cost": {"status": "estimated", "currency": "CNY", "amount_cny": 0.0001}})
    assert client.get(LIST_PATH).status_code == 401
    assert client.get(LIST_PATH, headers={"Authorization": "Bearer ghost"}).status_code == 401
    denied = client.get(LIST_PATH, headers={"Authorization": "Bearer alice"})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "reviewer_role_required"
    assert client.get(f"{LIST_PATH}/run-1", headers={"Authorization": "Bearer alice"}).status_code == 403
    listed = client.get(LIST_PATH, headers={"Authorization": "Bearer admin"})
    assert "private" not in listed.text
    before = listed.json()
    assert client.get(LIST_PATH, headers={"Authorization": "Bearer teacher"}).status_code == 200
    after = client.get(LIST_PATH, headers={"Authorization": "Bearer teacher"}).json()
    assert after["runs"] == before["runs"]
    with factory() as db:
        row = db.get(AgentRunRecord, "run-1")
        assert row.metadata_data["result"]["budget"]["actual_input_tokens"] == 10
        assert db.scalar(select(func.count()).select_from(AgentRunRecord)) == 1


def test_projection_reads_only_persisted_values_ignoring_tariff_env(api, monkeypatch):
    client, factory = api
    add_run(factory, "run-1", created_at=1_700.0, budget={"model_calls": 1,
        "actual_input_tokens": 1000, "actual_output_tokens": 500, "usage_unknown_calls": 0,
        "cost": {"status": "unknown", "currency": "CNY"}})
    without = client.get(f"{LIST_PATH}/run-1", headers={"Authorization": "Bearer admin"}).json()
    monkeypatch.setenv("V2_LLM_INPUT_CNY_PER_MILLION", "2")
    monkeypatch.setenv("V2_LLM_OUTPUT_CNY_PER_MILLION", "8")
    with_tariff = client.get(f"{LIST_PATH}/run-1", headers={"Authorization": "Bearer admin"}).json()
    assert with_tariff == without
    assert with_tariff["cost_status"] == "unknown" and with_tariff["cost_cny"] is None


def test_reported_latency_keeps_measured_floats_and_rejects_non_numbers(api):
    """QWEN-104b: latency is measured (``round(elapsed * 1000, 2)``), never counted."""
    client, factory = api
    cases = {"run-int": 900, "run-float": 5803.27, "run-negative": -1,
             "run-bool": True, "run-string": "900", "run-null": None}
    for index, (run_id, latency) in enumerate(cases.items()):
        add_run(factory, run_id, created_at=1_700.0 + index, budget=None, latency_ms=latency)
    body = client.get(LIST_PATH, headers={"Authorization": "Bearer admin"}).json()
    projected = {item["run_id"]: item["reported_latency_ms"] for item in body["runs"]}
    assert projected["run-float"] == 5803.27
    assert projected["run-int"] == 900
    assert all(projected[key] is None for key in ("run-negative", "run-bool", "run-string",
                                                 "run-null"))
    # Both real values keep the type they were measured in: nothing is coerced or truncated.
    assert isinstance(projected["run-float"], float)
    assert isinstance(projected["run-int"], int)
    detail = client.get(f"{LIST_PATH}/run-float", headers={"Authorization": "Bearer admin"}).text
    assert "5803.27" in detail


def test_counts_stay_integer_only_while_latency_gains_precision(api):
    """The QWEN-104b widening is scoped to latency: a fractional count is still not recorded."""
    client, factory = api
    add_run(factory, "run-fractional", created_at=1_700.0, latency_ms=5803.27,
            budget={"model_calls": 3.0, "actual_input_tokens": 12.5, "actual_output_tokens": 1.0,
                    "usage_unknown_calls": 0.5, "cost": {"status": "unknown", "currency": "CNY"}})
    run = client.get(f"{LIST_PATH}/run-fractional",
                     headers={"Authorization": "Bearer admin"}).json()
    assert run["model_calls"] is None and run["usage_unknown_calls"] is None
    assert run["input_tokens"] is None and run["output_tokens"] is None
    assert run["usage_status"] == "unknown"
    assert run["reported_latency_ms"] == 5803.27
    assert run["duration_ms"] == 1200 and run["tool_calls"] == 0


def test_unknown_run_returns_404_and_persistence_failure_returns_503(api, monkeypatch):
    client, factory = api
    assert client.get(f"{LIST_PATH}/missing",
                      headers={"Authorization": "Bearer admin"}).status_code == 404
    add_run(factory, "run-1", created_at=1_700.0, budget=None)

    def broken():
        raise RuntimeError("database is down")

    monkeypatch.setattr(database, "SessionLocal", broken)
    assert client.get(LIST_PATH, headers={"Authorization": "Bearer admin"}).status_code == 503
    assert client.get(LIST_PATH, headers={"Authorization": "Bearer admin"}).json()["detail"] \
        == "run_persistence_unavailable"
