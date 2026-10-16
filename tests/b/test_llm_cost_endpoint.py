"""LLM 成本统计端点测试 (v7 Day 2)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.telemetry import get_telemetry, reset_telemetry


@pytest.fixture(autouse=True)
def _fresh_telemetry():
    reset_telemetry()
    yield
    reset_telemetry()


@pytest.fixture(scope="module")
def client():
    from backend.app.main import app
    return TestClient(app)


def test_llm_cost_endpoint_returns_zero_initially(client):
    """无调用时返回全零。"""
    resp = client.get("/metrics/llm-cost")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_calls"] == 0
    assert body["total_cost_yuan"] == 0.0
    assert body["total_tokens_input"] == 0
    assert body["total_tokens_output"] == 0
    assert "by_provider" in body
    assert "pricing_reference" in body
    assert "note" in body


def test_llm_cost_aggregates_after_recorded_calls(client):
    """记录若干 LLM 调用后，端点聚合输出。"""
    reg = get_telemetry()
    # 模拟 3 次星火调用（2 成功 1 失败）+ token
    calls = reg.counter("llm_calls_total")
    calls.inc(provider="spark", status="success")
    calls.inc(provider="spark", status="success")
    calls.inc(provider="spark", status="failed")
    tokens = reg.counter("llm_tokens_total")
    # 直接操作内部值模拟 token 累积（测试简化）
    tokens._values[(("provider", "spark"), ("type", "input"))] = 5000
    tokens._values[(("provider", "spark"), ("type", "output"))] = 3000

    resp = client.get("/metrics/llm-cost")
    body = resp.json()
    assert body["total_calls"] == 3
    assert body["total_tokens_input"] == 5000
    assert body["total_tokens_output"] == 3000
    # spark 定价 0.018 元/千 token → (5000+3000)/1000 * 0.018 = 0.144
    assert body["total_cost_yuan"] > 0
    spark_entry = next(e for e in body["by_provider"] if e["provider"] == "spark")
    assert spark_entry["calls"] == 3
    assert spark_entry["success"] == 2
    assert spark_entry["failed"] == 1
    assert spark_entry["cost_yuan"] > 0


def test_llm_cost_multi_provider_aggregation(client):
    """多 provider 分别统计。"""
    reg = get_telemetry()
    calls = reg.counter("llm_calls_total")
    calls.inc(provider="spark", status="success")
    calls.inc(provider="openai_compatible", status="success")
    tokens = reg.counter("llm_tokens_total")
    tokens._values[(("provider", "spark"), ("type", "input"))] = 1000
    tokens._values[(("provider", "openai_compatible"), ("type", "output"))] = 2000

    resp = client.get("/metrics/llm-cost")
    body = resp.json()
    assert body["total_calls"] == 2
    providers = {e["provider"] for e in body["by_provider"]}
    assert "spark" in providers
    assert "openai_compatible" in providers


def test_llm_cost_endpoint_accessible_without_auth(client):
    """端点在 /metrics 下，不走 /api/v1 鉴权。"""
    resp = client.get("/metrics/llm-cost")
    assert resp.status_code == 200
