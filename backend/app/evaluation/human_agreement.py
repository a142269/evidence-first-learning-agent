"""Pure statistics and validation for blinded two-reviewer human agreement.

No file, database, model or application import happens here: the CLI shells in
``scripts/human_eval/`` own I/O, this module owns the arithmetic. Formulas are
fixed by docs/HUMAN_EVAL_DESIGN_2026-10-19.md section 6 as ruled by Lead on
2026-10-19, and missing judgements stay ``None`` - an undefined kappa is never
written as 0 and never coerced to False.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Mapping, Optional, Sequence

# One reviewer-A / reviewer-B judgement pair for a single rubric metric.
Pair = tuple[bool, bool]

EVALUATOR_VERSION = "human-agreement-1.0"
BOOTSTRAP_REPLICATES = 2000
Z_SCORE_95 = 1.96

# Fields that would let a reviewer re-identify which arm or case a packet item
# came from, or read the reference answer. Turns the "no arm in the packet"
# test assertion into a runtime gate.
LEAK_FORBIDDEN_KEYS = ("arm", "case_id", "expected_sources", "expected_outcome", "answer", "answers")

STATUS_COMPUTED = "computed"
STATUS_UNDEFINED = "undefined"
REASON_NO_COMMON_ITEMS = "no_common_items"
REASON_DEGENERATE_MARGINALS = "degenerate_marginals"
REASON_INCOMPLETE = "incomplete_review"
PROFILE_FIT_LIMITATION = ("profile_fit: the task set carries no learner profile, so this coefficient "
                          "cannot support any claim about personalisation (evals/CLAIM_AND_ABLATION.md:47).")


def canonical_digest(value: object) -> str:
    """Return the stable sha256 used for packets, evidence and manifests."""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     allow_nan=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _is_strict_bool(value: object) -> bool:
    return type(value) is bool


def find_leaked_keys(value: object, forbidden: Sequence[str] = LEAK_FORBIDDEN_KEYS) -> tuple[str, ...]:
    """Collect reference keys hidden anywhere inside a JSON-like packet value."""
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and key in forbidden:
                found.add(key)
            found.update(find_leaked_keys(nested, forbidden))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(find_leaked_keys(nested, forbidden))
    return tuple(sorted(found))


def score_completeness(scores: Mapping[str, Any], metrics: Sequence[str]) -> str:
    """Classify one reviewer's scores for one item as blank, complete or partial.

    ``partial`` is a review the reviewer started and abandoned; it is never
    treated as a set of ``False`` judgements.
    """
    if set(scores) != set(metrics):
        raise ValueError("score keys must match the rubric exactly")
    values = [scores[key] for key in metrics]
    if any(not (_is_strict_bool(value) or value is None) for value in values):
        raise ValueError("score values must be strictly boolean or null")
    if all(value is None for value in values):
        return "blank"
    if all(_is_strict_bool(value) for value in values):
        return "complete"
    return "partial"


def wilson_interval(successes: int, trials: int, z: float = Z_SCORE_95) -> Optional[tuple[float, float]]:
    """95% Wilson score interval for a binomial proportion; None when undefined."""
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("successes must lie inside 0..trials")
    if trials == 0:
        return None
    rate = successes / trials
    denominator = 1 + z * z / trials
    centre = (rate + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials * trials)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _counts(pairs: Sequence[Pair]) -> tuple[int, int, int, int]:
    both_yes = sum(1 for a, b in pairs if a and b)
    yes_a = sum(1 for a, _ in pairs if a)
    yes_b = sum(1 for _, b in pairs if b)
    agree = sum(1 for a, b in pairs if a == b)
    return both_yes, yes_a, yes_b, agree


def kappa_point(pairs: Sequence[Pair]) -> dict[str, Any]:
    """Cohen's kappa plus the diagnostics that make a low value readable.

    With 2x2 counts a=both yes, b=A yes/B no, c=A no/B yes, d=both no over N
    pairs: po=(a+d)/N, pe=p_A1*p_B1+p_A0*p_B0, kappa=(po-pe)/(1-pe),
    prevalence=(2a+b+c)/(2N) (the overall positive rate; near 0 or 1 it explains
    a low kappa without any real disagreement) and bias=|b-c|/N (the gap
    between the reviewers' positive marginals).
    """
    total = len(pairs)
    if total == 0:
        return {"n": 0, "po": None, "pe": None, "kappa": None, "prevalence": None, "bias": None,
                "agreements": 0, "status": STATUS_UNDEFINED, "reason": REASON_NO_COMMON_ITEMS}
    both_yes, yes_a, yes_b, agree = _counts(pairs)
    po = agree / total
    positive_a, positive_b = yes_a / total, yes_b / total
    pe = positive_a * positive_b + (1 - positive_a) * (1 - positive_b)
    prevalence = (yes_a + yes_b) / (2 * total)
    bias = abs(yes_a - yes_b) / total
    result: dict[str, Any] = {"n": total, "po": po, "pe": pe, "prevalence": prevalence, "bias": bias,
                              "agreements": agree}
    if pe >= 1.0:
        result.update(kappa=None, status=STATUS_UNDEFINED, reason=REASON_DEGENERATE_MARGINALS)
        return result
    result.update(kappa=(po - pe) / (1 - pe), status=STATUS_COMPUTED, reason=None)
    return result


def _percentile(ordered: Sequence[float], fraction: float) -> float:
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_kappa_interval(pairs: Sequence[Pair], seed: int,
                             replicates: int = BOOTSTRAP_REPLICATES) -> Optional[tuple[float, float]]:
    """Item-level nonparametric bootstrap: percentile 2.5/97.5 of kappa.

    Degenerate resamples (undefined marginals) are dropped instead of being
    counted as 0; if every resample is degenerate the interval is None.
    """
    total = len(pairs)
    if total == 0 or replicates < 2:
        return None
    generator = random.Random(seed)
    values: list[float] = []
    for _ in range(replicates):
        resample = [pairs[generator.randrange(total)] for _ in range(total)]
        point = kappa_point(resample)
        if point["status"] == STATUS_COMPUTED:
            values.append(point["kappa"])
    if not values:
        return None
    values.sort()
    return (_percentile(values, 0.025), _percentile(values, 0.975))


def metric_agreement(pairs: Sequence[Pair], seed: int,
                     replicates: int = BOOTSTRAP_REPLICATES) -> dict[str, Any]:
    """Per-metric agreement block: point estimates, Wilson interval for po, bootstrap CI for kappa."""
    point = kappa_point(pairs)
    interval = bootstrap_kappa_interval(pairs, seed, replicates) if point["status"] == STATUS_COMPUTED else None
    interval_po = wilson_interval(int(point["agreements"]), int(point["n"]))
    result = dict(point)
    result["po_ci_95"] = list(interval_po) if interval_po is not None else None
    result["kappa_ci_95"] = list(interval) if interval else None
    result["bootstrap_replicates"] = replicates if interval else 0
    return result


def resolve_judgement(first: Any, second: Any, adjudicated: Any = None) -> Optional[bool]:
    """Third-reviewer semantics identical to ablation_report.py:75-84 (kept in sync by hand).

    Agreement resolves to the shared value, disagreement resolves only to a
    strictly boolean adjudication, anything else stays None.
    """
    if not _is_strict_bool(first) or not _is_strict_bool(second):
        return None
    if first == second:
        return bool(first)
    return bool(adjudicated) if _is_strict_bool(adjudicated) else None


def _aligned_pairs(items: Sequence[Mapping[str, Any]], metric: str) -> list[Pair]:
    pairs: list[Pair] = []
    for item in items:
        first = item["judgements"]["a"].get(metric)
        second = item["judgements"]["b"].get(metric)
        if _is_strict_bool(first) and _is_strict_bool(second):
            pairs.append((first, second))
    return pairs


def _resolved(item: Mapping[str, Any], metric: str) -> Optional[bool]:
    decision = item.get("adjudication") or {}
    return resolve_judgement(item["judgements"]["a"].get(metric), item["judgements"]["b"].get(metric),
                             decision.get(metric))


def build_agreement_report(items: Sequence[Mapping[str, Any]], metrics: Sequence[str], arms: Sequence[str],
                           *, seed: int, inputs: Mapping[str, Any], replicates: int = BOOTSTRAP_REPLICATES,
                           reviewers: Sequence[str] = ("a", "b")) -> dict[str, Any]:
    """Assemble the publishable agreement report from private aligned review items."""
    per_metric: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    for metric in metrics:
        pairs = _aligned_pairs(items, metric)
        block = metric_agreement(pairs, seed, replicates)
        if metric == "profile_fit" and block["status"] == STATUS_COMPUTED:
            block["reason"] = block["reason"] or "profile_fit_uninterpretable_without_learner_profile"
        per_metric[metric] = block
        filled = {role: sum(1 for item in items if _is_strict_bool(item["judgements"][role].get(metric)))
                  for role in reviewers}
        coverage[metric] = {"paired_items": len(pairs), **{f"scored_by_{role}": filled[role] for role in reviewers}}

    disagreements = [{"case_id": item["case_id"], "arm": item["arm"], "blind_id_a": item["blind_id_a"],
                      "blind_id_b": item["blind_id_b"], "metric": metric}
                     for item in items for metric in metrics
                     if _is_strict_bool(item["judgements"]["a"].get(metric))
                     and _is_strict_bool(item["judgements"]["b"].get(metric))
                     and item["judgements"]["a"][metric] != item["judgements"]["b"][metric]]

    adjudicated_items = [item for item in items if isinstance(item.get("adjudication"), Mapping)
                         and item["adjudication"]]
    unresolved = sum(1 for item in items for metric in metrics if _resolved(item, metric) is None)
    review_complete = bool(items) and unresolved == 0

    quality = {}
    for arm in arms:
        selected = [item for item in items if item["arm"] == arm]
        complete = bool(selected) and all(_resolved(item, metric) is not None
                                         for item in selected for metric in metrics)
        quality[arm] = (sum(all(_resolved(item, metric) for metric in metrics) for item in selected) / len(selected)
                        if review_complete and complete else None)

    limitations = [
        f"{len(items)} review items come from {len({item['case_id'] for item in items})} cases x "
        f"{len({item['arm'] for item in items})} arms; a review item is not an independent question, so "
        "item-level counts must not be read as distinct-task evidence.",
        "Reviewers are not authenticated and independence is asserted by the protocol, not proven by the tool "
        "(evals/CLAIM_AND_ABLATION.md:27).",
        "Nulls are unknown judgements; they are excluded from paired counts and never read as False.",
        PROFILE_FIT_LIMITATION,
    ]
    if not review_complete:
        limitations.append("review_complete=false: quality pass rates stay null, they are not failures.")

    return {
        "evaluation_mode": "human_agreement_offline",
        "evaluator_version": EVALUATOR_VERSION,
        "inputs": dict(inputs),
        "randomness": {"bootstrap_seed": seed, "bootstrap_replicates": replicates,
                       "bootstrap_method": "item-level nonparametric resample, percentile 2.5/97.5"},
        "item_count": len(items),
        "metrics": list(metrics),
        "coverage": coverage,
        "review_complete": review_complete,
        "per_metric": per_metric,
        "disagreements": disagreements,
        "adjudication": {"items_with_adjudication": len(adjudicated_items),
                         "unresolved_metric_judgements": unresolved},
        "quality_pass_rate_by_arm": quality,
        "quality_denominator": "scored review items of this arm; unscored or unresolved judgements keep the rate null",
        "limitations": limitations,
    }
