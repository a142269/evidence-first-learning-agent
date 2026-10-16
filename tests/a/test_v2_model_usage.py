from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.agent_runtime.usage_meter import record_model_usage
from backend.app.core.llm_client import LLMClient


def test_usage_tokens_are_actual_while_configured_tariff_cost_is_estimated(monkeypatch):
    monkeypatch.setenv("V2_LLM_INPUT_CNY_PER_MILLION", "1")
    monkeypatch.setenv("V2_LLM_OUTPUT_CNY_PER_MILLION", "2")
    budget = record_model_usage({"model_calls": 1}, {"usage": {"input_tokens": 1000,
                                                                  "output_tokens": 500}})
    assert budget["cost"] == {"status": "estimated", "currency": "CNY", "amount_cny": 0.002}
    budget = record_model_usage(budget, {"usage": None})
    assert budget["usage_unknown_calls"] == 1
    assert budget["cost"]["status"] == "unknown"
    assert budget["cost"]["measured_portion_cny"] == 0.002


@pytest.mark.asyncio
async def test_v2_model_never_substitutes_mock_content_after_provider_error(monkeypatch):
    import requests

    def fail(*_args, **_kwargs):
        raise requests.ConnectionError("secret-provider-url")

    monkeypatch.setattr(requests, "post", fail)
    client = LLMClient(config=SimpleNamespace(provider="openai_compatible",
        openai_base_url="https://example.invalid", openai_api_key="placeholder",
        openai_model="model", timeout=1, openai_extra_body=None))
    with pytest.raises(RuntimeError, match="v2_model_request_failed") as exc:
        await client.achat_strict_with_usage([{"role": "user", "content": "hello"}])
    assert "secret-provider-url" not in str(exc.value)


@pytest.mark.asyncio
async def test_v2_deepseek_requests_final_answer_with_small_token_cap(monkeypatch):
    import requests

    from backend.app.agent_runtime import eval_cost_guard

    monkeypatch.setattr(eval_cost_guard, "reserve_model_call", lambda *_: None)
    sent = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "测试通过"}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 4}}

    def post(_url, **kwargs):
        sent.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(requests, "post", post)
    client = LLMClient(config=SimpleNamespace(provider="openai_compatible",
        openai_base_url="https://example.invalid", openai_api_key="placeholder",
        openai_model="deepseek-flash", timeout=1, openai_extra_body=None))
    result = await client.achat_strict_with_usage(
        [{"role": "user", "content": "hello"}], max_tokens=32, json_object=True
    )
    assert result["text"] == "测试通过"
    assert sent[0]["thinking"] == {"type": "disabled"}
    assert sent[0]["response_format"] == {"type": "json_object"}
    assert sent[0]["max_tokens"] == 32
