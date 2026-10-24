import pytest

from backend.app.evaluation.claim_support import evaluate_claims, evaluate_rule_based_support


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


def test_rule_based_support_accepts_cited_shared_evidence():
    evidence = [{"chunk_id": "c1", "content":
                 "检索增强生成先检索课程材料，再依据证据组织回答，并标注引用来源，便于读者核对；"
                 "课程材料说明检索的作用。"}]
    result = evaluate_rule_based_support(
        [{"text": "检索增强生成先检索课程材料，再依据证据组织回答。", "source_ids": ["c1"]}],
        evidence,
    )
    assert result["passed"]
    assert result["citation_support"] == 1.0
    assert result["evidence_strength"] == 1.0
    assert result["evaluated_items"] == 1 and result["unsupported_items"] == 0


def test_rule_based_support_rejects_unrelated_long_evidence():
    evidence = [{"chunk_id": "c1", "content":
                 "微积分与线性代数的矩阵分解、特征值计算和概率分布公式推导，均属纯数学内容，"
                 "不涉及任何教学讲解方法。"}]
    result = evaluate_rule_based_support(
        [{"text": "检索增强生成先检索课程材料，再依据证据组织回答。", "source_ids": ["c1"]}],
        evidence,
    )
    assert not result["passed"]
    assert result["evidence_strength"] == 0.0
    assert result["unsupported_items"] == 1
    assert "evidence_unsupported" in result["reasons"]


def test_rule_based_support_rejects_missing_and_invalid_citations():
    evidence = [{"chunk_id": "c1", "content": "课程证据"}]
    missing = evaluate_rule_based_support([{"text": "一句讲解", "source_ids": []}], evidence)
    assert not missing["passed"] and "citation_missing" in missing["reasons"]
    invalid = evaluate_rule_based_support([{"text": "一句讲解", "source_ids": ["c2"]}], evidence)
    assert not invalid["passed"] and "citation_invalid" in invalid["reasons"]
    assert invalid["citation_support"] == 0.0


def test_rule_based_support_does_not_judge_short_fixture_evidence():
    # Tiny fixtures are indistinguishable from metadata stubs; the rule reports
    # "not judged" instead of inventing a lexical support verdict.
    result = evaluate_rule_based_support(
        [{"text": "完全无关的讲解文本", "source_ids": ["c1"]}],
        [{"chunk_id": "c1", "content": "课程证据"}],
    )
    assert result["passed"] and result["evidence_strength"] is None
