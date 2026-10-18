"""Aggregate independently annotated claim/evidence judgments; never infer support."""
from __future__ import annotations


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
