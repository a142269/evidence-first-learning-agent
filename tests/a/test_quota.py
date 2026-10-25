"""QWEN-324: per-user / per-course quotas with stable 429 semantics.

Service-level cases run against a fresh ``QuotaStore`` with an injectable
clock (window reset is deterministic); route-level cases prove the 429 shape
and that ordinary requests pass untouched.
"""
from __future__ import annotations

import pytest

from backend.app.services import quota
from tests.a.test_learning_runs_v2_lifecycle import api as api, events  # noqa: F401


@pytest.fixture
def store():
    fresh = quota.QuotaStore()
    quota._STORE = fresh
    yield fresh
    quota._STORE = quota.QuotaStore()


class _Clock:
    def __init__(self, start: float = 1_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(store):
    tick = _Clock()
    store._clock = tick
    return tick


def test_request_limit_blocks_and_window_resets(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_REQUESTS_PER_MINUTE", "2")
    assert store.check_run_creation("alice", "courseA").allowed
    assert store.check_run_creation("alice", "courseA").allowed
    denied = store.check_run_creation("alice", "courseA")
    assert not denied.allowed
    assert (denied.dimension, denied.scope, denied.window_seconds) == ("requests", "user", 60)
    assert denied.error_code == "quota_exceeded"
    assert 0 < denied.retry_after <= 60
    clock.now += 61  # window slides past every entry
    assert store.check_run_creation("alice", "courseA").allowed


def test_token_limit_blocks_new_run_for_same_user_and_course(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_TOKENS_PER_HOUR", "1000")
    store.record_run_usage("alice", "courseA", tokens=1000, cost_cny=0.01)
    denied = store.check_run_creation("alice", "courseA")
    assert not denied.allowed
    assert (denied.dimension, denied.scope) == ("tokens", "user_course")
    assert denied.verdict["tokens"]["used"] == 1000


def test_token_limit_is_isolated_per_course(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_TOKENS_PER_HOUR", "1000")
    store.record_run_usage("alice", "courseA", tokens=1000, cost_cny=0.01)
    assert store.check_run_creation("alice", "courseB").allowed  # other course unaffected


def test_token_limit_is_isolated_per_user(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_TOKENS_PER_HOUR", "1000")
    store.record_run_usage("alice", "courseA", tokens=1000, cost_cny=0.01)
    assert store.check_run_creation("bob", "courseA").allowed  # other user unaffected


def test_cost_limit_denies_only_fully_measured_windows(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_COST_CNY_PER_DAY", "1.0")
    store.record_run_usage("alice", "courseA", tokens=10, cost_cny=0.6)
    store.record_run_usage("alice", "courseA", tokens=10, cost_cny=0.6)
    denied = store.check_run_creation("alice", "courseA")
    assert not denied.allowed
    assert (denied.dimension, denied.scope) == ("cost", "user")
    assert denied.verdict["cost"]["measured_cny"] == pytest.approx(1.2)


def test_unknown_cost_is_never_treated_as_zero(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_COST_CNY_PER_DAY", "1.0")
    store.record_run_usage("alice", "courseA", tokens=10, cost_cny=0.6)
    store.record_run_usage("alice", "courseA", tokens=10)  # provider reported nothing
    decision = store.check_run_creation("alice", "courseA")
    assert decision.allowed  # unknown makes the cost dimension unmeasurable, not free
    assert decision.verdict["cost"]["status"] == "unknown"
    assert decision.verdict["cost"]["unknown_runs"] == 1
    assert decision.verdict["cost"]["measured_cny"] == pytest.approx(0.6)


def test_snapshot_reports_window_occupancy(store, clock):
    store.check_run_creation("alice", "courseA")
    store.record_run_usage("alice", "courseA", tokens=500, cost_cny=0.2)
    view = store.snapshot("alice", "courseA")
    assert view["requests"]["used"] == 1
    assert view["tokens"]["used"] == 500
    assert view["cost"]["measured_cny"] == pytest.approx(0.2)
    assert view["cost"]["unknown_runs"] == 0
    assert "limits" in store.snapshot()


def test_disabled_quota_allows_everything(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_ENABLED", "false")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_MINUTE", "1")
    for _ in range(5):
        assert quota.check_run_creation("alice", "courseA").allowed
    assert quota.check_run_creation("alice", "courseA").verdict == {"disabled": True}


def test_default_is_off_until_explicitly_enabled(store, clock, monkeypatch):
    """Opt-in default (QWEN-321 spirit): no surface changes until enabled."""
    monkeypatch.delenv("QUOTA_ENABLED", raising=False)
    for _ in range(5):
        assert quota.check_run_creation("alice", "courseA").allowed  # untouched by default
    monkeypatch.setenv("QUOTA_ENABLED", "true")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_MINUTE", "2")
    assert store.check_run_creation("alice", "courseA").allowed
    assert store.check_run_creation("alice", "courseA").allowed
    assert not store.check_run_creation("alice", "courseA").allowed


def test_record_from_budget_keeps_unknown_costs_unknown(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_ENABLED", "true")
    monkeypatch.setenv("QUOTA_COST_CNY_PER_DAY", "1.0")
    quota.record_from_budget("alice", "courseA", {
        "actual_input_tokens": 100, "actual_output_tokens": 50,
        "cost": {"status": "unknown", "currency": "CNY"}})
    decision = store.check_run_creation("alice", "courseA")
    assert decision.allowed
    assert decision.verdict["tokens"]["used"] == 150
    assert decision.verdict["cost"]["status"] == "unknown"

    quota.record_from_budget("alice", "courseA", {
        "actual_input_tokens": 10,
        "cost": {"status": "estimated", "currency": "CNY", "amount_cny": 0.5}})
    view = store.snapshot("alice", "courseA")
    assert view["tokens"]["used"] == 160
    assert view["cost"]["measured_cny"] == pytest.approx(0.5)


def test_malformed_budget_is_ignored(store, clock, monkeypatch):
    monkeypatch.setenv("QUOTA_ENABLED", "true")
    quota.record_from_budget("alice", "courseA", {"actual_input_tokens": "many", "cost": 3})
    quota.record_from_budget("alice", "courseA", None)
    view = store.snapshot("alice", "courseA")
    assert view["tokens"]["used"] == 0
    assert view["cost"]["unknown_runs"] == 2  # a run settled, its cost is unknown


def test_stream_returns_429_with_retry_after_then_recovers(api, store, clock, monkeypatch):
    client, _ = api
    monkeypatch.setenv("QUOTA_ENABLED", "true")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_MINUTE", "1")
    first = client.post("/api/v2/learning-runs/stream", headers={"Authorization": "Bearer alice"},
                        json={"message": "解释 RAG", "course_id": "artificial_intelligence"})
    assert first.status_code == 200  # normal request passes untouched
    second = client.post("/api/v2/learning-runs/stream", headers={"Authorization": "Bearer alice"},
                         json={"message": "解释 RAG", "course_id": "artificial_intelligence"})
    assert second.status_code == 429
    assert second.json()["detail"] == "quota_exceeded"
    assert 0 < int(second.headers["Retry-After"]) <= 60
    clock.now += 61
    third = client.post("/api/v2/learning-runs/stream", headers={"Authorization": "Bearer alice"},
                        json={"message": "解释 RAG", "course_id": "artificial_intelligence"})
    assert third.status_code == 200  # window reset restores normal service


def test_enqueue_is_quota_fenced_too(api, store, clock, monkeypatch):
    client, _ = api
    monkeypatch.setenv("QUOTA_ENABLED", "true")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_MINUTE", "1")
    first = client.post("/api/v2/learning-runs/enqueue", headers={"Authorization": "Bearer alice"},
                        json={"message": "解释 RAG", "course_id": "artificial_intelligence"})
    assert first.status_code == 200
    second = client.post("/api/v2/learning-runs/enqueue", headers={"Authorization": "Bearer alice"},
                         json={"message": "解释 RAG", "course_id": "artificial_intelligence"})
    assert second.status_code == 429
    assert second.json()["detail"] == "quota_exceeded"


def test_quota_isolation_between_users_on_routes(api, store, clock, monkeypatch):
    client, _ = api
    monkeypatch.setenv("QUOTA_ENABLED", "true")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_MINUTE", "1")
    assert client.post("/api/v2/learning-runs/enqueue", headers={"Authorization": "Bearer alice"},
                       json={"message": "解释 RAG", "course_id": "artificial_intelligence"}).status_code == 200
    assert client.post("/api/v2/learning-runs/enqueue", headers={"Authorization": "Bearer alice"},
                       json={"message": "解释 RAG", "course_id": "artificial_intelligence"}).status_code == 429
    # bob has his own windows
    assert client.post("/api/v2/learning-runs/enqueue", headers={"Authorization": "Bearer teacher"},
                       json={"message": "解释 RAG", "course_id": "artificial_intelligence"}).status_code == 200


def test_reads_are_not_quota_fenced(api, store, clock, monkeypatch):
    """Quotas fence run creation only; run reads stay untouched."""
    client, _ = api
    monkeypatch.setenv("QUOTA_ENABLED", "true")
    monkeypatch.setenv("QUOTA_REQUESTS_PER_MINUTE", "1")
    created = client.post("/api/v2/learning-runs/stream", headers={"Authorization": "Bearer alice"},
                          json={"message": "解释 RAG", "course_id": "artificial_intelligence"})
    assert created.status_code == 200
    run_id = events(created)[0][1]["run_id"]
    # This is the second request from alice this minute — a creation would 429.
    lookup = client.get(f"/api/v2/learning-runs/{run_id}", headers={"Authorization": "Bearer alice"})
    assert lookup.status_code == 200
