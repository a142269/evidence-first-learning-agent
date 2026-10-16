"""Telemetry 指标系统测试 (v7 — 匹配 A 的 TelemetryRegistry API)."""
from __future__ import annotations

import pytest

from backend.app.core.telemetry import (
    Counter, Histogram, Gauge, TelemetryRegistry,
    get_telemetry, reset_telemetry, Timer,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    """每测试用全新 registry，避免指标累积污染。"""
    reset_telemetry()
    yield
    reset_telemetry()


def test_counter_increments():
    reg = get_telemetry()
    c = reg.counter("test_counter", "help")
    c.inc(provider="spark", status="ok")
    c.inc(provider="spark", status="ok")
    c.inc(provider="spark", status="err")
    assert c.value(provider="spark", status="ok") == 2.0
    assert c.value(provider="spark", status="err") == 1.0


def test_counter_inc_value():
    c = Counter("c2")
    c.inc(5.0, x="a")
    assert c.value(x="a") == 5.0


def test_histogram_observe_records():
    reg = get_telemetry()
    h = reg.histogram("test_hist", "help")
    h.observe(0.1, stage="s1")
    h.observe(0.3, stage="s1")
    h.observe(0.05, stage="s2")
    lines = h.export()
    assert any("test_hist_bucket" in line for line in lines)
    assert any("test_hist_sum" in line for line in lines)
    assert any("test_hist_count" in line for line in lines)


def test_gauge_set_and_inc():
    reg = get_telemetry()
    g = reg.gauge("test_gauge", "help")
    g.set(10.0, kind="active")
    assert g.value(kind="active") == 10.0
    g.inc(5.0, kind="active")
    assert g.value(kind="active") == 15.0
    g.dec(3.0, kind="active")
    assert g.value(kind="active") == 12.0


def test_export_prometheus_format():
    reg = get_telemetry()
    reg.counter("prom_counter", "demo").inc(x="1")
    text = reg.export_prometheus()
    assert "# HELP prom_counter" in text
    assert "# TYPE prom_counter counter" in text
    assert 'prom_counter{x="1"}' in text


def test_default_metrics_bootstrapped():
    """get_telemetry 首次调用应预注册业务指标。"""
    reg = get_telemetry()
    text = reg.export_prometheus()
    assert "llm_calls_total" in text
    assert "artifact_generated_total" in text
    assert "agent_failure_total" in text
    assert "pipeline_stages_total" in text


def test_timer_records_duration():
    reg = get_telemetry()
    # ensure histogram exists before timing
    reg.histogram("timed_op", "help")
    with Timer("timed_op", stage="x"):
        pass
    text = reg.export_prometheus()
    assert "timed_op_count" in text


def test_timer_auto_creates_histogram():
    """Timer 自动注册 histogram。"""
    with Timer("auto_op", stage="y"):
        pass
    text = get_telemetry().export_prometheus()
    assert "auto_op_count" in text


def test_learning_state_store_uses_timer(tmp_path):
    """learning_state_store.upsert_profile 经 Timer 记录耗时。"""
    from backend.app.core.database import configure_database, init_db
    from backend.app.core import models  # noqa: F401
    configure_database(f"sqlite:///{(tmp_path / 'ls.db').as_posix()}")
    init_db()
    from backend.app.services import learning_state_store as store
    store.upsert_profile("u_tele", {"knowledge_base": {"score": 0.5}})
    text = get_telemetry().export_prometheus()
    assert "learning_state_duration_seconds" in text
