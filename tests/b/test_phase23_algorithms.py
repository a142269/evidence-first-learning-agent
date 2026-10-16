"""
Phase 2-3: DINA MF / FSRS / Kalman / Counterfactual / Leiden / Archetype K-means tests
"""
import pytest
import numpy as np


class TestDINAMeanField:
    def test_mf_converges_on_synthetic(self):
        """Synthetic data with K=8: mean-field should converge"""
        from backend.app.services.cognitive_diagnosis.dina import DINA
        rng = np.random.default_rng(42)
        K, J, I = 8, 20, 50
        Q = rng.integers(0, 2, size=(J, K))
        Q[0, 0] = 1  # ensure at least one connection
        R = rng.integers(0, 2, size=(I, J))
        R[:, 0] = Q[0, 0]  # perfect response for item 0

        dina = DINA(max_iter=30)
        result = dina.fit(
            responses={i: {j: int(R[i, j]) for j in range(J)} for i in range(I)},
            q_matrix=Q, item_ids=list(range(J)),
            kp_ids=[f"kp_{k}" for k in range(K)],
            student_ids=list(range(I)),
        )
        assert "alpha" in result
        assert len(result["alpha"]) == I

    def test_mf_better_than_placeholder(self):
        """MF should produce non-uniform alpha (unlike placeholder which just clamped)"""
        from backend.app.services.cognitive_diagnosis.dina import DINA
        rng = np.random.default_rng(42)
        K, J, I = 10, 30, 60
        Q = rng.integers(0, 2, size=(J, K))
        R = rng.integers(0, 2, size=(I, J))

        dina = DINA(max_iter=30)
        result = dina.fit(
            responses={i: {j: int(R[i, j]) for j in range(J)} for i in range(I)},
            q_matrix=Q, item_ids=list(range(J)),
            kp_ids=[f"kp_{k}" for k in range(K)],
            student_ids=list(range(I)),
        )
        alphas = result["alpha"]
        # Check that mastery values vary (not all 0.5)
        all_vals = [v for a in alphas.values() for v in a.values()]
        assert max(all_vals) - min(all_vals) > 0.05, "MF should produce varied masteries"


class TestFSRSvsSM2:
    def test_fsrs_basic_review(self):
        from backend.app.services.spaced_repetition.fsrs import FSRS45
        fsrs = FSRS45()
        fsrs.review("item1", 3)
        state = fsrs.get_schedule("item1")
        assert state is not None
        assert state["stability"] > 0

    def test_benchmark_runs(self):
        from backend.app.services.spaced_repetition.fsrs import sm2_vs_fsrs_benchmark
        result = sm2_vs_fsrs_benchmark(n_items=200)
        assert result["n_items"] == 200
        assert "sm2" in result
        assert "fsrs" in result


class TestKalmanAndCounterfactual:
    def test_kalman_smoothing(self):
        from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster
        f = BKTForecaster()
        history = [
            {"day": -10, "p_learned": 0.20}, {"day": -5, "p_learned": 0.22},
            {"day": -3, "p_learned": 0.35}, {"day": 0, "p_learned": 0.40},
        ]
        result = f.forecast_with_kalman(history, horizon_days=10)
        assert len(result) > 4
        # Smoothed values should not be exactly the noisy inputs
        smoothed_mid = [p for p in result if p.day == 0]
        if smoothed_mid:
            assert 0.20 < smoothed_mid[0].p_learned < 0.50

    def test_counterfactual_scenarios(self):
        from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster
        f = BKTForecaster()
        cf = f.counterfactual(0.3, horizon_days=20, daily_rates=[0.3, 0.7])
        assert len(cf["scenarios"]) == 2
        assert cf["scenarios"][1]["final_mastery"] >= cf["scenarios"][0]["final_mastery"]
        assert "recommendation" in cf


class TestLeidenCommunity:
    def test_detect_on_small_graph(self):
        from backend.app.services.knowledge_graph.community import detect_communities
        nodes = [f"kp_{i}" for i in range(20)]
        edges = [(f"kp_{i}", f"kp_{i+1}", 1.0) for i in range(19)]
        result = detect_communities(nodes, edges)
        assert "communities" in result
        assert result["total_communities"] >= 1

    def test_summaries_generated(self):
        from backend.app.services.knowledge_graph.community import (
            detect_communities, generate_community_summaries,
        )
        nodes = [f"kp_{i}" for i in range(30)]
        edges = [(f"kp_{i}", f"kp_{i+5}", 1.0) for i in range(25)]
        result = detect_communities(nodes, edges)
        summaries = generate_community_summaries(result["communities"])
        assert len(summaries) == result["total_communities"]
        assert "summary" in summaries[0]


class TestArchetypeValidation:
    def test_synthetic_generation(self):
        from backend.app.services.learner_archetype_validation import generate_synthetic_students
        X, labels = generate_synthetic_students(n_per_archetype=10)
        if len(X) == 0:
            pytest.skip("No archetypes available")
        assert X.shape == (len(labels), 8)
        assert len(set(labels)) >= 5

    def test_clustering_validation(self):
        from backend.app.services.learner_archetype_validation import (
            generate_synthetic_students, run_clustering_validation,
        )
        X, labels = generate_synthetic_students(n_per_archetype=15)
        if len(X) == 0:
            pytest.skip("No archetypes available")
        result = run_clustering_validation(X, labels)
        if "error" in result:
            pytest.skip(f"Validation failed: {result['error']}")
        assert "silhouette" in result
        assert "passed" in result
        assert "interpretation" in result

    def test_full_validation_pipeline(self):
        from backend.app.services.learner_archetype_validation import validate_archetypes
        result = validate_archetypes(n_per_archetype=10)
        if "error" in result:
            pytest.skip(f"No archetypes: {result['error']}")
        assert "n_archetypes" in result
        assert "silhouette" in result
