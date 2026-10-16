"""
测试: ConvergenceTracker — 辩论收敛追踪研究工具 (Week2 Day6-7)

覆盖:
- RoundSnapshot / ConvergenceAnalysis 数据模型
- StatsUtils: mean/std/slope/mann_kendall/norm_cdf
- ConvergenceTracker: start/record/analyze/aggregate/export
- 收敛类型分类: fast/slow/oscillating/stuck/divergent
- 边界: 空session / 单轮 / 无效ID
- SyntheticQuery: 50题各类统计
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from backend.app.services.debate.convergence_tracker import (
    DIM_BLOOM,
    DIM_CITATION,
    DIM_FACTUAL,
    DIM_PEDAGOGY,
    TRACKED_DIMENSIONS,
    ConvergenceAnalysis,
    ConvergenceTracker,
    ConvergenceType,
    RoundSnapshot,
    StatsUtils,
    get_convergence_tracker,
    reset_tracker,
)
from backend.app.services.debate.synthetic_queries import (
    SYNTHETIC_QUERIES,
    SyntheticQuery,
    category_stats,
    get_all,
    get_balanced_sample,
    get_queries_by_category,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_tracker()


# ================================================================
# StatsUtils
# ================================================================
class TestStatsUtils:
    def test_mean(self):
        assert StatsUtils.mean([1.0, 2.0, 3.0]) == 2.0
        assert StatsUtils.mean([]) == 0.0

    def test_std(self):
        assert StatsUtils.std([1.0, 1.0, 1.0]) == 0.0
        assert StatsUtils.std([0.0, 1.0]) > 0.0
        assert StatsUtils.std([]) == 0.0
        assert StatsUtils.std([1.0]) == 0.0  # n=1

    def test_linear_slope_increasing(self):
        slope = StatsUtils.linear_slope([0.3, 0.4, 0.5, 0.6])
        assert slope > 0.05  # 正斜率

    def test_linear_slope_decreasing(self):
        slope = StatsUtils.linear_slope([0.8, 0.7, 0.6, 0.5])
        assert slope < -0.05

    def test_linear_slope_flat(self):
        slope = StatsUtils.linear_slope([0.5, 0.5, 0.5])
        assert abs(slope) < 0.01

    def test_mann_kendall_significant_trend(self):
        """单调递增 → p 值小"""
        p = StatsUtils.mann_kendall_p_value([0.3, 0.5, 0.6, 0.7, 0.85, 0.9])
        assert p < 0.05  # 显著趋势

    def test_mann_kendall_increasing(self):
        """严格单调递增 → p ≈ 0.009"""
        p = StatsUtils.mann_kendall_p_value([1.0, 2.0, 3.0, 4.0, 5.0])
        assert p < 0.05

    def test_mann_kendall_flat(self):
        """平坦 → p ≈ 1.0"""
        p = StatsUtils.mann_kendall_p_value([0.5, 0.5, 0.5, 0.5])
        # 全 tie → S=0 → p 接近 1
        assert p > 0.1

    def test_mann_kendall_small_n(self):
        """n < 3 → p = 1.0"""
        p = StatsUtils.mann_kendall_p_value([0.5, 0.6])
        assert p == 1.0


# ================================================================
# ConvergenceType 分类
# ================================================================
class TestConvergenceClassification:
    def test_fast(self):
        t = StatsUtils.classify_convergence([0.7, 0.85], [2])
        assert t == ConvergenceType.FAST

    def test_slow(self):
        t = StatsUtils.classify_convergence([0.3, 0.5, 0.65, 0.8], [4])
        assert t == ConvergenceType.SLOW

    def test_divergent(self):
        t = StatsUtils.classify_convergence([0.8, 0.6, 0.4], [])
        assert t == ConvergenceType.DIVERGENT

    def test_oscillating(self):
        t = StatsUtils.classify_convergence([0.4, 0.7, 0.3, 0.7], [])
        assert t == ConvergenceType.OSCILLATING

    def test_stuck(self):
        t = StatsUtils.classify_convergence([0.3, 0.3, 0.35, 0.3], [])
        assert t == ConvergenceType.STUCK


# ================================================================
# RoundSnapshot + ConvergenceAnalysis
# ================================================================
class TestDataModels:
    def test_round_snapshot(self):
        rs = RoundSnapshot(
            round_num=1, overall_score=0.75, passed=False,
            dimension_scores={"factual": 0.8, "pedagogy": 0.6, "bloom": 0.7, "citation": 0.5},
        )
        assert rs.overall_score == 0.75
        assert rs.dimension_scores["factual"] == 0.8

    def test_analysis_to_dict(self):
        a = ConvergenceAnalysis(
            session_id="test", query_text="q", total_rounds=2, passed=True,
            final_score=0.85, mean_score=0.8, std_score=0.05,
            score_trend_slope=0.05, score_trend_p_value=0.02,
            convergence_type=ConvergenceType.FAST, convergence_round=2,
            rounds_until_pass=2, dimension_trends={"factual": 0.1},
        )
        d = a.to_dict()
        assert d["convergence_type"] == "fast"
        assert d["passed"] is True


# ================================================================
# ConvergenceTracker 集成
# ================================================================
class TestConvergenceTracker:
    @pytest.fixture
    def tracker(self, tmp_path):
        return ConvergenceTracker(output_dir=str(tmp_path))

    def test_start_and_record(self, tracker):
        tracker.start_session("deb_001", "讲解CNN", "theory")
        tracker.record_round(
            "deb_001", 1,
            dimension_scores={"factual": 0.8, "pedagogy": 0.6, "bloom": 0.7, "citation": 0.5},
            overall_score=0.65, passed=False, issue_count=3,
        )
        tracker.record_round(
            "deb_001", 2,
            dimension_scores={"factual": 0.9, "pedagogy": 0.8, "bloom": 0.85, "citation": 0.7},
            overall_score=0.85, passed=True, issue_count=0,
        )
        assert tracker.session_count() == 1

    def test_analyze_fast_convergence(self, tracker):
        tracker.start_session("deb_fast", "讲解CNN", "theory")
        tracker.record_round("deb_fast", 1,
            {"factual": 0.7, "pedagogy": 0.6, "bloom": 0.6, "citation": 0.5},
            0.6, False, 3)
        tracker.record_round("deb_fast", 2,
            {"factual": 0.9, "pedagogy": 0.85, "bloom": 0.8, "citation": 0.75},
            0.85, True, 0)

        analysis = tracker.analyze("deb_fast")
        assert analysis.convergence_type == ConvergenceType.FAST
        assert analysis.passed is True
        assert analysis.total_rounds == 2
        assert analysis.score_trend_slope > 0  # 改善趋势

    def test_analyze_stuck(self, tracker):
        tracker.start_session("deb_stuck", "AI怎么学？", "ambiguous")
        for r in range(1, 5):
            tracker.record_round("deb_stuck", r,
                {"factual": 0.3, "pedagogy": 0.2, "bloom": 0.2, "citation": 0.1},
                0.25, False, 5)

        analysis = tracker.analyze("deb_stuck")
        assert analysis.convergence_type == ConvergenceType.STUCK
        assert analysis.passed is False

    def test_dimension_trends(self, tracker):
        tracker.start_session("deb_trend", "对比CNN和RNN", "compare")
        tracker.record_round("deb_trend", 1,
            {"factual": 0.6, "pedagogy": 0.5, "bloom": 0.7, "citation": 0.3},
            0.55, False, 4)
        tracker.record_round("deb_trend", 2,
            {"factual": 0.9, "pedagogy": 0.8, "bloom": 0.9, "citation": 0.7},
            0.85, True, 0)

        analysis = tracker.analyze("deb_trend")
        # 所有维度都应改善
        for trend in analysis.dimension_trends.values():
            assert trend >= 0

    def test_aggregate_stats(self, tracker):
        # fast
        tracker.start_session("s1", "q1", "theory")
        tracker.record_round("s1", 1, {d: 0.7 for d in TRACKED_DIMENSIONS}, 0.7, False, 1)
        tracker.record_round("s1", 2, {d: 0.9 for d in TRACKED_DIMENSIONS}, 0.9, True, 0)

        # stuck (intentionally low scores)
        tracker.start_session("s2", "q2", "ambiguous")
        tracker.record_round("s2", 1, {d: 0.2 for d in TRACKED_DIMENSIONS}, 0.2, False, 5)
        tracker.record_round("s2", 2, {d: 0.2 for d in TRACKED_DIMENSIONS}, 0.2, False, 5)

        stats = tracker.aggregate_stats()
        assert stats["total_sessions"] == 2
        assert stats["pass_rate"] == 0.5
        assert "fast" in stats["convergence_distribution"]
        assert "stuck" in stats["convergence_distribution"]

    def test_unknown_session(self, tracker):
        """未知 session 不崩溃"""
        tracker.record_round("nonexistent", 1,
            {"factual": 0.5, "pedagogy": 0.5, "bloom": 0.5, "citation": 0.5},
            0.5, False, 0)
        analysis = tracker.analyze("nonexistent")
        assert analysis.total_rounds == 0

    def test_export_jsonl(self, tracker):
        tracker.start_session("deb_export", "测试", "test")
        tracker.record_round("deb_export", 1,
            {d: 0.8 for d in TRACKED_DIMENSIONS}, 0.8, True, 0)

        path = tracker.export_jsonl("test_export.jsonl")
        assert Path(path).exists()
        with open(path) as f:
            line = f.readline()
            data = json.loads(line)
            assert data["session_id"] == "deb_export"
            assert data["passed"] is True

    def test_export_summary_markdown(self, tracker):
        tracker.start_session("deb_md", "测试", "test")
        tracker.record_round("deb_md", 1,
            {d: 0.9 for d in TRACKED_DIMENSIONS}, 0.9, True, 0)

        path = tracker.export_summary_markdown("test_report.md")
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "收敛性研究" in content
        assert "通过率" in content

    def test_reset(self, tracker):
        tracker.start_session("x", "q", "cat")
        tracker.record_round("x", 1, {d: 0.5 for d in TRACKED_DIMENSIONS}, 0.5, False, 0)
        tracker.reset()
        assert tracker.session_count() == 0

    def test_singleton(self):
        t1 = get_convergence_tracker()
        t2 = get_convergence_tracker()
        assert t1 is t2


# ================================================================
# SyntheticQuery 库
# ================================================================
class TestSyntheticQueries:
    def test_total_50(self):
        assert len(SYNTHETIC_QUERIES) == 50

    def test_5_categories(self):
        cats = set(q.category for q in SYNTHETIC_QUERIES)
        assert cats == {"theory", "code", "ambiguous", "compare", "edge"}

    def test_each_category_10(self):
        for cat in ["theory", "code", "ambiguous", "compare", "edge"]:
            assert len(get_queries_by_category(cat)) == 10

    def test_balanced_sample(self):
        sample = get_balanced_sample(n_per_category=3)
        # 5 categories × 3 = 15
        assert len(sample) == 15
        cats = set(q.category for q in sample)
        assert len(cats) == 5

    def test_category_stats(self):
        stats = category_stats()
        assert len(stats) == 5
        for cat, info in stats.items():
            assert info["count"] == 10
            assert "avg_expected_rounds" in info

    def test_edge_highest_expected_rounds(self):
        """边缘类预期轮数最高"""
        stats = category_stats()
        edge_avg = stats["edge"]["avg_expected_rounds"]
        theory_avg = stats["theory"]["avg_expected_rounds"]
        assert edge_avg >= theory_avg

    def test_all_queries_have_required_fields(self):
        for q in SYNTHETIC_QUERIES:
            assert q.id
            assert q.text
            assert q.category in {"theory", "code", "ambiguous", "compare", "edge"}
            assert q.hardest_dimension in TRACKED_DIMENSIONS
            assert q.stagnation_risk in {"low", "medium", "high"}

    def test_get_all_returns_copy(self):
        all_q = get_all()
        assert len(all_q) == 50
        # 不应修改原始列表
        all_q.pop()
        assert len(SYNTHETIC_QUERIES) == 50
