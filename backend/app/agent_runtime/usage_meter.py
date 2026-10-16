"""Per-run V2 model accounting; missing provider usage stays explicitly unknown."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import os
from typing import Any


def _tariff() -> tuple[Decimal, Decimal] | None:
    try:
        input_price = Decimal(os.getenv("V2_LLM_INPUT_CNY_PER_MILLION", ""))
        output_price = Decimal(os.getenv("V2_LLM_OUTPUT_CNY_PER_MILLION", ""))
        if input_price < 0 or output_price < 0:
            return None
        return input_price, output_price
    except (InvalidOperation, ValueError):
        return None


def record_model_usage(budget: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """Account for one completed call without inventing tokens or provider prices."""
    updated = dict(budget)
    usage = response.get("usage")
    if not isinstance(usage, dict):
        updated["usage_unknown_calls"] = updated.get("usage_unknown_calls", 0) + 1
    else:
        updated["actual_input_tokens"] = updated.get("actual_input_tokens", 0) + usage["input_tokens"]
        updated["actual_output_tokens"] = updated.get("actual_output_tokens", 0) + usage["output_tokens"]
    tariff = _tariff()
    if tariff is None:
        updated["cost"] = {"status": "unknown", "currency": "CNY"}
    elif updated.get("usage_unknown_calls", 0):
        updated["cost"] = {"status": "unknown", "currency": "CNY",
                           "measured_portion_cny": _measured_cost(updated, tariff)}
    else:
        updated["cost"] = {"status": "estimated", "currency": "CNY",
                           "amount_cny": _measured_cost(updated, tariff)}
    return updated


def _measured_cost(budget: dict[str, Any], tariff: tuple[Decimal, Decimal]) -> float:
    total = (Decimal(budget.get("actual_input_tokens", 0)) * tariff[0]
             + Decimal(budget.get("actual_output_tokens", 0)) * tariff[1]) / Decimal(1_000_000)
    return float(total.quantize(Decimal("0.000001")))
