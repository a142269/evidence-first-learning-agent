import sys
from types import SimpleNamespace

import pytest

from backend.app.agent_runtime.eval_cost_guard import reserve_embedding_call, reserve_model_call


def test_budget_fail_closed_and_atomic_reservation(monkeypatch):
    monkeypatch.setenv("V2_EVAL_BUDGET_CNY", "0.01")
    with pytest.raises(RuntimeError, match="eval_budget_configuration_required"):
        reserve_model_call([{"content": "x"}], 100)
    monkeypatch.setenv("V2_EVAL_BUDGET_ID", "fixed-test")
    monkeypatch.setenv("V2_EVAL_INPUT_CNY_PER_MILLION_UPPER", "100")
    monkeypatch.setenv("V2_EVAL_OUTPUT_CNY_PER_MILLION_UPPER", "100")
    calls = []
    class FakeRedis:
        def eval(self, script, keys, key, amount, ceiling):
            calls.append((keys, key, amount, ceiling))
            return -1
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=SimpleNamespace(
        from_url=lambda *args, **kwargs: FakeRedis())))
    with pytest.raises(RuntimeError, match="eval_budget_exceeded"):
        reserve_model_call([{"content": "x"}], 100)
    assert calls[0][0] == 1
    assert calls[0][2] > 0
    assert calls[0][3] == 10000


def test_guard_is_opt_in(monkeypatch):
    monkeypatch.delenv("V2_EVAL_BUDGET_CNY", raising=False)
    reserve_model_call([{"content": "anything"}], 1)


def test_embedding_uses_same_campaign_budget_and_fails_closed(monkeypatch):
    monkeypatch.setenv("V2_EVAL_BUDGET_CNY", "0.01")
    monkeypatch.setenv("V2_EVAL_BUDGET_ID", "fixed-test")
    monkeypatch.setenv("V2_EVAL_EMBED_CNY_PER_MILLION_UPPER", "100")
    calls = []
    class FakeRedis:
        def eval(self, script, keys, key, amount, ceiling):
            calls.append((key, amount, ceiling))
            return -1
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(Redis=SimpleNamespace(
        from_url=lambda *args, **kwargs: FakeRedis())))
    with pytest.raises(RuntimeError, match="eval_budget_exceeded"):
        reserve_embedding_call(["课程学习检索"])
    assert len(calls) == 1
    assert calls[0][0] == "triple-u:v2-eval-budget:fixed-test"
    assert calls[0][2] == 10000
    assert calls[0][1] > 0
