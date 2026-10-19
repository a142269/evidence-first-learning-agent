import pytest

from backend.app.evaluation.human_agreement import (
    REASON_DEGENERATE_MARGINALS,
    REASON_NO_COMMON_ITEMS,
    bootstrap_kappa_interval,
    build_agreement_report,
    canonical_digest,
    find_leaked_keys,
    kappa_point,
    metric_agreement,
    resolve_judgement,
    score_completeness,
    wilson_interval,
)

RUBRICS = ("facts_supported", "exercise_answers_correct", "goal_covered", "difficulty_progression", "profile_fit")


def test_kappa_matches_the_hand_computed_case():
    # n=8, six agreements, and marginals that give pe=0.5 -> po=0.75, kappa=0.5.
    pairs = [(True, True), (True, True), (True, True), (True, False),
             (False, True), (False, False), (False, False), (False, False)]
    point = kappa_point(pairs)
    assert point["n"] == 8
    assert point["po"] == pytest.approx(0.75)
    assert point["pe"] == pytest.approx(0.5)
    assert point["kappa"] == pytest.approx(0.5)
    assert point["prevalence"] == pytest.approx(0.5)
    assert point["bias"] == pytest.approx(0.0)
    assert point["status"] == "computed"


def test_perfect_agreement_is_degenerate_and_reported_as_null():
    point = kappa_point([(True, True)] * 4)
    assert point["po"] == 1.0
    assert point["pe"] == 1.0
    assert point["kappa"] is None
    assert point["status"] == "undefined"
    assert point["reason"] == REASON_DEGENERATE_MARGINALS


def test_empty_intersection_is_null_and_not_zero():
    point = kappa_point([])
    assert point == {"n": 0, "po": None, "pe": None, "kappa": None, "prevalence": None, "bias": None,
                     "agreements": 0, "status": "undefined", "reason": REASON_NO_COMMON_ITEMS}


@pytest.mark.parametrize(("successes", "trials"), [(6, 8), (8, 8), (0, 8), (1, 30)])
def test_wilson_interval_stays_inside_unit_range(successes, trials):
    low, high = wilson_interval(successes, trials)
    assert 0.0 <= low <= high <= 1.0
    assert successes / trials <= high


def test_wilson_interval_is_none_without_items():
    assert wilson_interval(0, 0) is None


def test_bootstrap_interval_is_reproducible_and_bounded():
    pairs = [(True, True), (True, False), (False, True), (False, False)] * 5
    first = bootstrap_kappa_interval(pairs, seed=7, replicates=200)
    second = bootstrap_kappa_interval(pairs, seed=7, replicates=200)
    assert first == second
    low, high = first
    assert -1.0 <= low <= kappa_point(pairs)["kappa"] <= high <= 1.0
    assert bootstrap_kappa_interval(pairs, seed=8, replicates=200) != first


def test_bootstrap_drops_degenerate_resamples_instead_of_counting_zero():
    assert bootstrap_kappa_interval([(True, True)] * 4, seed=1, replicates=50) is None


def test_metric_block_reports_both_intervals_and_keeps_the_sample_size():
    pairs = [(True, True), (True, False), (False, True), (False, False)]
    block = metric_agreement(pairs, seed=3, replicates=100)
    assert block["n"] == 4
    assert block["po_ci_95"][0] < block["po"] < block["po_ci_95"][1]
    assert block["kappa_ci_95"][0] <= block["kappa"] <= block["kappa_ci_95"][1]
    empty = metric_agreement([], seed=3, replicates=100)
    assert empty["kappa"] is None and empty["po_ci_95"] is None and empty["kappa_ci_95"] is None


def test_resolve_judgement_follows_the_ablation_report_semantics():
    assert resolve_judgement(True, True) is True
    assert resolve_judgement(False, False) is False
    assert resolve_judgement(True, False) is None
    assert resolve_judgement(True, False, True) is True
    assert resolve_judgement(True, None) is None
    assert resolve_judgement(None, None, True) is None


def test_score_completeness_separates_blank_partial_and_complete():
    assert score_completeness(dict.fromkeys(RUBRICS), RUBRICS) == "blank"
    assert score_completeness(dict.fromkeys(RUBRICS, True), RUBRICS) == "complete"
    partial = dict.fromkeys(RUBRICS, True)
    partial["profile_fit"] = None
    assert score_completeness(partial, RUBRICS) == "partial"
    with pytest.raises(ValueError, match="strictly boolean"):
        score_completeness({**partial, "goal_covered": "true"}, RUBRICS)
    with pytest.raises(ValueError, match="rubric"):
        score_completeness({"facts_supported": True}, RUBRICS)


def test_leak_scan_reaches_nested_reference_fields():
    leaked = find_leaked_keys({"package": {"steps": [{"arm": "full"}]}, "evidence": [{"expected_sources": ["s"]}]})
    assert leaked == ("arm", "expected_sources")
    assert find_leaked_keys({"package": {"plan": {"goal": "ok"}}}) == ()


def aligned_rows(first, second, **overrides):
    rows = []
    for index, arm in enumerate(("single", "without_reviewer", "full")):
        row = {"case_id": f"c{index // 2}", "arm": arm, "blind_id_a": f"a-{index + 1:03d}",
               "blind_id_b": f"b-{index + 1:03d}",
               "judgements": {"a": dict.fromkeys(RUBRICS, first), "b": dict.fromkeys(RUBRICS, second)}}
        row.update(overrides)
        rows.append(row)
    return rows


def test_report_keeps_quality_rates_null_until_every_judgement_resolves():
    report = build_agreement_report(aligned_rows(True, True), RUBRICS, ("single", "without_reviewer", "full"),
                                    seed=11, inputs={"runs_sha256": "x"}, replicates=50)
    assert report["review_complete"] is True
    assert report["quality_pass_rate_by_arm"]["single"] == 1.0
    assert report["per_metric"]["facts_supported"]["kappa"] is None

    incomplete = aligned_rows(True, True)
    incomplete[0]["judgements"]["a"]["goal_covered"] = None
    report = build_agreement_report(incomplete, RUBRICS, ("single",), seed=11, inputs={}, replicates=50)
    assert report["review_complete"] is False
    assert report["quality_pass_rate_by_arm"]["single"] is None
    assert report["coverage"]["goal_covered"]["paired_items"] == 2
    assert any("null" in item for item in report["limitations"])


def test_report_uses_adjudication_to_resolve_disagreement_without_calling_it_agreement():
    rows = aligned_rows(True, True)
    rows[0]["judgements"]["b"]["facts_supported"] = False
    rows[0]["adjudication"] = dict.fromkeys(RUBRICS, True)
    report = build_agreement_report(rows, RUBRICS, ("single",), seed=5, inputs={}, replicates=50)
    assert len(report["disagreements"]) == 1
    assert report["review_complete"] is True
    assert report["quality_pass_rate_by_arm"]["single"] == 1.0
    assert report["per_metric"]["facts_supported"]["kappa"] == 0.0

    unresolved = build_agreement_report([dict(row) for row in aligned_rows(True, True)][:1], RUBRICS, ("single",),
                                        seed=5, inputs={}, replicates=50)
    rows[0].pop("adjudication")
    pending = build_agreement_report(rows, RUBRICS, ("single",), seed=5, inputs={}, replicates=50)
    assert pending["review_complete"] is False
    assert unresolved["review_complete"] is True


def test_profile_fit_limitation_is_always_carried():
    report = build_agreement_report(aligned_rows(True, False), RUBRICS, ("single",), seed=2, inputs={},
                                    replicates=50)
    assert any("profile_fit" in item for item in report["limitations"])
    assert report["per_metric"]["profile_fit"]["reason"] == "profile_fit_uninterpretable_without_learner_profile"


def test_canonical_digest_is_order_insensitive():
    assert canonical_digest({"a": 1, "b": [2, 3]}) == canonical_digest({"b": [2, 3], "a": 1})
    assert canonical_digest({"a": 1}) != canonical_digest({"a": 2})
