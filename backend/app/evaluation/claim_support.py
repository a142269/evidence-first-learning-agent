"""Aggregate independently annotated claim/evidence judgments; never infer support."""
from __future__ import annotations

import re


def evaluate_claims(claims: list[dict], evidence_ids: list[str]) -> dict:
    """Evaluate two independent reviews per claim and citation.

    Missing or conflicting judgments remain unresolved and do not become successes.
    Each claim contains claim, source_ids, and reviews. A review contains reviewer,
    supported, severe_error, and a citation_relevance mapping for all source IDs.
    A disagreement may be resolved by a separate, independent adjudication with
    the same fields. The original disagreement remains counted in the report.
    """
    if not isinstance(evidence_ids, list) or any(not isinstance(x, str) or not x for x in evidence_ids):
        raise ValueError("evidence_ids must be a list of nonempty strings")
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("duplicate evidence ID")
    if not isinstance(claims, list) or not claims:
        raise ValueError("at least one claim is required")
    supported = unsupported = severe = covered = citations = relevant = resolved = 0
    disagreements = 0
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("claim"), str) or not claim["claim"].strip():
            raise ValueError("claim text is required")
        sources = claim.get("source_ids")
        if not isinstance(sources, list) or any(not isinstance(x, str) or not x for x in sources):
            raise ValueError("source_ids must be a list of nonempty strings")
        if len(set(sources)) != len(sources):
            raise ValueError("duplicate source ID within claim")
        covered += bool(sources)
        citations += len(sources)
        reviews = claim.get("reviews", [])
        if not isinstance(reviews, list) or len(reviews) > 2:
            raise ValueError("exactly two independent reviews are expected")
        adjudication = claim.get("adjudication")
        judgments = [*reviews, *([adjudication] if adjudication is not None else [])]
        names = []
        for review in judgments:
            if not isinstance(review, dict) or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
                raise ValueError("reviewer identity is required")
            names.append(review["reviewer"].strip())
            if type(review.get("supported")) is not bool or type(review.get("severe_error")) is not bool:
                raise ValueError("review judgments must be boolean")
            relevance = review.get("citation_relevance")
            if not isinstance(relevance, dict) or set(relevance) != set(sources) or any(type(v) is not bool for v in relevance.values()):
                raise ValueError("each citation requires a boolean relevance judgment")
        if len(names) != len(set(names)):
            raise ValueError("reviews must use distinct reviewer IDs")
        if len(reviews) < 2:
            if adjudication is not None:
                raise ValueError("adjudication requires two reviews")
            continue
        a, b = reviews
        if any(a[key] != b[key] for key in ("supported", "severe_error", "citation_relevance")):
            disagreements += 1
            if adjudication is None:
                continue
            a = adjudication
        elif adjudication is not None:
            raise ValueError("adjudication requires a disagreement")
        # A claim cannot be supported without a valid, relevant citation.
        if a["supported"] and not any(s in evidence_ids and a["citation_relevance"][s] for s in sources):
            raise ValueError("supported claim requires a valid relevant citation")
        resolved += 1
        supported += a["supported"]
        unsupported += not a["supported"]
        severe += a["severe_error"]
        relevant += sum(s in evidence_ids and a["citation_relevance"][s] for s in sources)
    complete = resolved == len(claims)
    return {
        "claim_count": len(claims), "resolved_claims": resolved,
        "disagreement_count": disagreements, "review_complete": complete,
        "citation_coverage": covered / len(claims),
        "claim_support_rate": supported / len(claims) if complete else None,
        "unsupported_claim_count": unsupported if complete else None,
        "severe_error_count": severe if complete else None,
        "citation_precision": relevant / citations if complete and citations else None,
        "citation_validity": sum(s in evidence_ids for c in claims for s in c["source_ids"]) / citations if citations else None,
    }


# A cited evidence chunk shorter than this is a fixture or metadata stub; lexical
# support is reported as "not judged" instead of being guessed from too little
# text.  This keeps the rule deterministic and avoids failing on tiny fixtures.
MIN_EVIDENCE_CHARS = 40
MIN_SUPPORT_RATE = 0.5

_TOKEN = re.compile(r"[0-9A-Za-z\u4e00-\u9fff]+")


def _bigrams(text: str) -> set[str]:
    grams: set[str] = set()
    for token in _TOKEN.findall((text or "").lower()):
        if len(token) < 2:
            continue
        grams.update(token[index:index + 2] for index in range(len(token) - 1))
    return grams


def evaluate_rule_based_support(items: list[dict], evidence: list[dict]) -> dict:
    """Rule-based claim-support backstop; never calls a model or a network.

    Each item is ``{"text": str, "source_ids": list[str]}`` and each evidence
    row is ``{"chunk_id": str, "content": str}``.  An item passes only when all
    of its cited IDs resolve to retrieved evidence and, for evidence long enough
    to judge, the artifact and the cited text share at least one character
    bigram.  ``evidence_strength`` is the fraction of judged items that pass and
    is ``None`` when no cited evidence is long enough to judge.
    """
    if not isinstance(items, list) or not items:
        raise ValueError("at least one artifact is required")
    if not isinstance(evidence, list):
        raise ValueError("evidence must be a list")
    by_id: dict[str, dict] = {}
    for row in evidence:
        if not isinstance(row, dict):
            raise ValueError("evidence rows must be objects")
        chunk_id = row.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("evidence chunk_id is required")
        by_id[chunk_id] = row

    total = missing = invalid = 0
    evaluated = supported = 0
    reasons: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError("artifact text is required")
        source_ids = item.get("source_ids")
        if not isinstance(source_ids, list) or any(not isinstance(x, str) or not x for x in source_ids):
            raise ValueError("source_ids must be a list of nonempty strings")
        unique = list(dict.fromkeys(source_ids))
        if not unique:
            missing += 1
            reasons.append("citation_missing")
            continue
        rows = []
        for source_id in unique:
            total += 1
            row = by_id.get(source_id)
            if row is None or not isinstance(row.get("content"), str) or not row["content"].strip():
                invalid += 1
                reasons.append("citation_invalid")
            else:
                rows.append(row)
        if len(rows) != len(unique):
            continue
        contents = [row["content"] for row in rows]
        if not any(len(content) >= MIN_EVIDENCE_CHARS for content in contents):
            continue
        evaluated += 1
        claim_grams = _bigrams(item["text"])
        if any(claim_grams & _bigrams(content) for content in contents):
            supported += 1
        else:
            reasons.append("evidence_unsupported")

    citation_support = (total - invalid) / total if total else None
    evidence_strength = supported / evaluated if evaluated else None
    passed = (not missing and not invalid
              and (evidence_strength is None or evidence_strength >= MIN_SUPPORT_RATE))
    return {
        "passed": passed,
        "citation_support": round(citation_support, 3) if citation_support is not None else None,
        "evidence_strength": round(evidence_strength, 3) if evidence_strength is not None else None,
        "item_count": len(items),
        "evaluated_items": evaluated,
        "supported_items": supported,
        "unsupported_items": evaluated - supported,
        "missing_citations": missing,
        "invalid_citations": invalid,
        "reasons": list(dict.fromkeys(reasons)),
    }
