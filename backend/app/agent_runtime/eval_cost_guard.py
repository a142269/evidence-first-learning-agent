"""Fail-closed, Redis-backed upper-bound reservation for paid V2 evaluations.

This is opt-in via V2_EVAL_BUDGET_CNY. Reservations are never refunded:
if a connection fails after the provider accepts a request, billing is unknown.
The operator must set tariff upper bounds for the selected model and currency.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING
import os


def reserve_model_call(messages: list[dict], max_tokens: int) -> None:
    raw_limit = os.getenv("V2_EVAL_BUDGET_CNY", "").strip()
    if not raw_limit:
        return
    try:
        limit = Decimal(raw_limit)
        input_rate = Decimal(os.environ["V2_EVAL_INPUT_CNY_PER_MILLION_UPPER"])
        output_rate = Decimal(os.environ["V2_EVAL_OUTPUT_CNY_PER_MILLION_UPPER"])
        campaign = os.environ["V2_EVAL_BUDGET_ID"].strip()
        if not campaign or any(value <= 0 for value in (limit, input_rate, output_rate)):
            raise ValueError("invalid_eval_budget")
    except (KeyError, InvalidOperation, ValueError):
        raise RuntimeError("eval_budget_configuration_required") from None
    # A UTF-8 byte is a conservative upper bound for ordinary text token count.
    # Add 1024 bytes/message for chat framing and provider-specific metadata.
    upper_input = sum(len(str(message.get("content", "")).encode("utf-8")) + 1024
                      for message in messages)
    _reserve(limit, campaign, Decimal(upper_input) * input_rate
             + Decimal(max_tokens) * output_rate)


def reserve_embedding_call(texts: list[str]) -> None:
    raw_limit = os.getenv("V2_EVAL_BUDGET_CNY", "").strip()
    if not raw_limit:
        return
    try:
        limit = Decimal(raw_limit)
        rate = Decimal(os.environ["V2_EVAL_EMBED_CNY_PER_MILLION_UPPER"])
        campaign = os.environ["V2_EVAL_BUDGET_ID"].strip()
        if not campaign or limit <= 0 or rate <= 0:
            raise ValueError("invalid_eval_budget")
    except (KeyError, InvalidOperation, ValueError):
        raise RuntimeError("eval_budget_configuration_required") from None
    upper_input = sum(len(value.encode("utf-8")) + 1024 for value in texts)
    _reserve(limit, campaign, Decimal(upper_input) * rate)


def _reserve(limit: Decimal, campaign: str, million_token_cost: Decimal) -> None:
    reserve_cny = million_token_cost / Decimal(1_000_000)
    amount = int((reserve_cny * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
    ceiling = int((limit * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
    try:
        import redis
        client = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
                                      socket_connect_timeout=2, socket_timeout=2)
        reserved = client.eval(
            "local prior=tonumber(redis.call('GET',KEYS[1]) or '0'); "
            "local charge=tonumber(ARGV[1]); local limit=tonumber(ARGV[2]); "
            "if prior+charge>limit then return -1 end; "
            "return redis.call('INCRBY',KEYS[1],charge)",
            1, f"triple-u:v2-eval-budget:{campaign}", amount, ceiling)
    except Exception:
        raise RuntimeError("eval_budget_storage_unavailable") from None
    if reserved == -1:
        raise RuntimeError("eval_budget_exceeded")
