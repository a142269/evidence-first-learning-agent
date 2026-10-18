import pytest

from backend.app.evaluation.claim_support import evaluate_claims


def review(name, supported=True, severe=False, relevance=None):
    return {"reviewer": name, "supported": supported, "severe_error": severe,
            "citation_relevance": relevance if relevance is not None else {"s1": True}}


def test_valid_supported_and_unsupported_claims():
    claims = [
        {"claim": "one", "source_ids": ["s1"], "reviews": [review("a"), review("b")]},
        {"claim": "two", "source_ids": [], "reviews": [review("a", False, True, {}), review("b", False, True, {})]},
    ]
    result = evaluate_claims(claims, ["s1"])
    assert result["claim_support_rate"] == 0.5
    assert result["citation_coverage"] == 0.5
    assert result["citation_precision"] == 1
    assert result["unsupported_claim_count"] == 1
    assert result["severe_error_count"] == 1


def test_missing_and_disagreeing_reviews_do_not_become_quality_scores():
    claims = [{"claim": "one", "source_ids": ["s1"], "reviews": [review("a"), review("b", False)]},
              {"claim": "two", "source_ids": ["s1"], "reviews": [review("a")]}]
    result = evaluate_claims(claims, ["s1"])
    assert result["disagreement_count"] == 1
    assert result["claim_support_rate"] is None
    assert result["citation_precision"] is None


def test_invalid_citation_cannot_support_claim():
    claims = [{"claim": "one", "source_ids": ["s1"], "reviews": [review("a"), review("b")]}]
    with pytest.raises(ValueError):
        evaluate_claims(claims, ["different"])


def test_same_reviewer_is_not_independent():
    claims = [{"claim": "one", "source_ids": ["s1"], "reviews": [review("a"), review("a")]}]
    with pytest.raises(ValueError):
        evaluate_claims(claims, ["s1"])


def test_disagreement_can_be_adjudicated_without_erasing_disagreement():
    claims = [{"claim": "one", "source_ids": ["s1"],
               "reviews": [review("a"), review("b", False)],
               "adjudication": review("c", False, True)}]
    result = evaluate_claims(claims, ["s1"])
    assert result["review_complete"]
    assert result["disagreement_count"] == 1
    assert result["claim_support_rate"] == 0
    assert result["unsupported_claim_count"] == 1
    assert result["severe_error_count"] == 1


@pytest.mark.parametrize("reviews, adjudication", [
    ([review("a")], review("c")),
    ([review("a"), review("b")], review("c")),
    ([review("a"), review("b", False)], review("a")),
])
def test_invalid_adjudication_is_rejected(reviews, adjudication):
    claims = [{"claim": "one", "source_ids": ["s1"], "reviews": reviews,
               "adjudication": adjudication}]
    with pytest.raises(ValueError):
        evaluate_claims(claims, ["s1"])


def test_adjudicator_cannot_support_claim_with_invalid_citation():
    claims = [{"claim": "one", "source_ids": ["s1"],
               "reviews": [review("a"), review("b", False)],
               "adjudication": review("c")}]
    with pytest.raises(ValueError):
        evaluate_claims(claims, ["other"])
