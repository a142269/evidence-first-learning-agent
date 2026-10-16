"""
bloom_taxonomy.py + forgetting_curve.py dedicated tests

B3: 提升 bloom 从 58% 覆盖，forgetting_curve 从 40% 覆盖
"""
import pytest


# ═══════════════════════════════════════════════════════
# Bloom Taxonomy — 6 层级 + 子层级 + Knowledge Dim + 3D Grid
# ═══════════════════════════════════════════════════════

class TestBloomClassify:
    def test_remember_keywords(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("请列举 Python 的三种基本数据类型")
        assert result["level"] == "remember"
        assert result["label"] == "记忆"

    def test_understand_keywords(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("请解释 CNN 的工作原理并举例说明")
        assert result["level"] == "understand"

    def test_apply_keywords(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("请实现一个线性回归模型")
        assert result["level"] == "apply"

    def test_analyze_keywords(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("请分析 SGD 和 Adam 优化器的优劣")
        assert result["level"] == "analyze"

    def test_evaluate_keywords(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("请评价这个模型的设计，论证其优缺点")
        assert result["level"] == "evaluate"

    def test_create_keywords(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("请设计一个全新的神经网络架构")
        assert result["level"] == "create"

    def test_returns_all_six_scores(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("解释 CNN 的工作原理")
        for lvl in ["remember", "understand", "apply", "analyze", "evaluate", "create"]:
            assert lvl in result["scores"]

    def test_empty_text_returns_valid(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("")
        assert result["level"] in ["remember", "understand", "apply", "analyze", "evaluate", "create"]

    def test_classify_question_shortcut(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy, BLOOM_LEVELS
        bt = BloomTaxonomy()
        lvl = bt.classify_question("请实现一个排序算法")
        assert lvl in BLOOM_LEVELS

    def test_english_keywords(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("implement a binary search tree")
        assert result["level"] == "apply"


class TestClassifyDetailed:
    def test_returns_sub_level(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify_detailed("请解释什么是机器学习")
        assert "sub_level" in result
        assert result["sub_level"] in ["recognizing", "recalling", "interpreting", "exemplifying",
            "classifying", "summarizing", "inferring", "comparing", "explaining",
            "executing", "implementing", "differentiating", "organizing", "attributing",
            "checking", "critiquing", "generating", "planning", "producing"]

    def test_detects_procedural_knowledge(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify_detailed("请编写代码实现这个算法")
        assert result["knowledge_dimension"] == "procedural"
        assert "knowledge_label" in result

    def test_detects_conceptual_knowledge(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify_detailed("这个理论的核心概念是什么")
        assert result["knowledge_dimension"] == "conceptual"

    def test_detects_factual_knowledge(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify_detailed("今天是星期一")
        assert result["knowledge_dimension"] == "factual"


class TestBloomHelpers:
    def test_level_index_mapping(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        assert BloomTaxonomy.level_index("remember") == 0
        assert BloomTaxonomy.level_index("understand") == 1
        assert BloomTaxonomy.level_index("create") == 5

    def test_level_index_unknown_returns_1(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        assert BloomTaxonomy.level_index("nonexistent") == 1

    def test_difficulty_weight_monotonic(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        weights = [BloomTaxonomy.level_difficulty_weight(lv) for lv in
                   ["remember", "understand", "apply", "analyze", "evaluate", "create"]]
        for i in range(len(weights) - 1):
            assert weights[i] <= weights[i + 1], f"weight not monotonic at {i}: {weights}"

    def test_bloom_3d_grid_returns_valid_data_uri(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        uri = bt.bloom_3d_grid_svg()
        assert uri.startswith("data:image/svg+xml;base64,")
        assert len(uri) > 500

    def test_bloom_colors_has_all_six_levels(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BLOOM_COLORS
        for lvl in ["remember", "understand", "apply", "analyze", "evaluate", "create"]:
            assert lvl in BLOOM_COLORS

    def test_bloom_labels_has_all_six_levels(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BLOOM_LABELS
        assert len(BLOOM_LABELS) == 6


# ═══════════════════════════════════════════════════════
# Forgetting Curve — 记忆保留率 / 时间点 / 复习推荐
# ═══════════════════════════════════════════════════════

class TestForgettingCurveRetention:
    def test_day_zero_is_full_retention(self):
        from backend.app.services.spaced_repetition.forgetting_curve import forgetting_curve_retention
        r = forgetting_curve_retention(0.0, easiness=2.5, repetitions=0)
        assert r == 1.0

    def test_retention_decreases_over_time(self):
        from backend.app.services.spaced_repetition.forgetting_curve import forgetting_curve_retention
        r1 = forgetting_curve_retention(1.0)
        r10 = forgetting_curve_retention(10.0)
        assert r10 < r1

    def test_higher_easiness_retains_longer(self):
        from backend.app.services.spaced_repetition.forgetting_curve import forgetting_curve_retention
        r_low = forgetting_curve_retention(5.0, easiness=1.5, repetitions=0)
        r_high = forgetting_curve_retention(5.0, easiness=3.0, repetitions=0)
        assert r_high > r_low

    def test_more_repetitions_retains_longer(self):
        from backend.app.services.spaced_repetition.forgetting_curve import forgetting_curve_retention
        r_low = forgetting_curve_retention(5.0, easiness=2.5, repetitions=0)
        r_high = forgetting_curve_retention(5.0, easiness=2.5, repetitions=10)
        assert r_high > r_low

    def test_negative_days_treated_as_zero(self):
        from backend.app.services.spaced_repetition.forgetting_curve import forgetting_curve_retention
        r = forgetting_curve_retention(-5.0)  # should not crash
        assert r >= 0.0

    def test_memory_strength_floor(self):
        from backend.app.services.spaced_repetition.forgetting_curve import forgetting_curve_retention
        r = forgetting_curve_retention(30.0, easiness=0.01, repetitions=0)
        assert 0.0 <= r <= 1.0


class TestRetentionAtIntervals:
    def test_default_intervals(self):
        from backend.app.services.spaced_repetition.forgetting_curve import retention_at_intervals
        points = retention_at_intervals()
        assert len(points) == 10
        assert points[0]["retention"] == 1.0

    def test_custom_intervals(self):
        from backend.app.services.spaced_repetition.forgetting_curve import retention_at_intervals
        points = retention_at_intervals(days=[0, 7, 30])
        assert len(points) == 3
        assert points[0]["day"] == 0

    def test_monotonic_decrease(self):
        from backend.app.services.spaced_repetition.forgetting_curve import retention_at_intervals
        points = retention_at_intervals()
        for i in range(len(points) - 1):
            assert points[i]["retention"] >= points[i + 1]["retention"]


class TestNextReviewRecommendation:
    def test_recommends_reasonable_days(self):
        from backend.app.services.spaced_repetition.forgetting_curve import next_review_recommendation
        result = next_review_recommendation(retention_threshold=0.7, easiness=2.5, repetitions=0)
        assert result["recommended_days"] > 0
        assert result["recommended_days"] < 30
        assert result["memory_strength"] > 0

    def test_higher_threshold_means_earlier_review(self):
        from backend.app.services.spaced_repetition.forgetting_curve import next_review_recommendation
        r09 = next_review_recommendation(retention_threshold=0.9)
        r05 = next_review_recommendation(retention_threshold=0.5)
        assert r09["recommended_days"] < r05["recommended_days"]

    def test_returns_all_keys(self):
        from backend.app.services.spaced_repetition.forgetting_curve import next_review_recommendation
        result = next_review_recommendation()
        for key in ["recommended_days", "retention_at_recommendation", "memory_strength"]:
            assert key in result

    def test_very_low_threshold_still_valid(self):
        from backend.app.services.spaced_repetition.forgetting_curve import next_review_recommendation
        result = next_review_recommendation(retention_threshold=0.01)
        assert result["recommended_days"] > 0
