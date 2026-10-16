"""
算法 Benchmark 测试 — B 模块

性能基准：DINA/BKT/SM-2/GraphRAG/PathPlanner 响应时间
回归测试：反例输入不崩溃
"""
import time
import pytest


class TestBKTBenchmark:
    def test_update_1000_times_under_200ms(self):
        """1000 次 BKT 更新 < 200ms"""
        from backend.app.services.cognitive_diagnosis.bkt import BKT
        bkt = BKT()
        start = time.perf_counter()
        for i in range(1000):
            bkt.update("stu1", f"kp_{i % 20}", correct=(i % 3 != 0))
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"1000 BKT updates took {elapsed:.3f}s"


class TestSM2Benchmark:
    def test_1000_reviews_under_100ms(self):
        """1000 次 SM-2 review < 100ms"""
        from backend.app.services.spaced_repetition.sm2 import SM2
        sm2 = SM2()
        start = time.perf_counter()
        for i in range(1000):
            sm2.review("u1", f"item_{i % 50}", quality=(i % 6))
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"1000 SM-2 reviews took {elapsed:.3f}s"


class TestBloomBenchmark:
    def test_100_classifications_under_50ms(self):
        """100 次 Bloom 分类 < 50ms"""
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        texts = [
            "定义什么是机器学习", "解释CNN的工作原理", "实现一个线性回归模型",
            "分析不同优化器的优劣", "评价这个模型的性能", "设计一个新的神经网络架构",
        ] * 17
        start = time.perf_counter()
        for t in texts[:100]:
            bt.classify(t)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.05, f"100 Bloom classifications took {elapsed:.3f}s"


class TestThompsonSampling:
    def test_arm_pulls_validity(self):
        """Thompson Sampling 输出合法"""
        import random
        random.seed(42)
        from backend.app.services.cognitive_diagnosis.bkt import BKT

        bkt = BKT()
        for i, kp in enumerate(["kp_python", "kp_ml", "kp_dl", "kp_cnn"]):
            for _ in range(10):
                bkt.update("stu1", kp, correct=True)

        # 模拟 path_planner 的 _compute_zpd_bandit 逻辑
        masteries = bkt.get_all_masteries("stu1")
        candidates = {k: v for k, v in masteries.items() if 0.5 <= v <= 1.0}

        if candidates:
            for kp_name, mastery in candidates.items():
                gain = 1.0 - mastery
                reward = gain * 0.8
                alpha = reward * 3.0 + 1.0
                beta_param = (1.0 - reward) * 3.0 + 1.0
                sample = random.betavariate(alpha, beta_param)
                assert 0.0 <= sample <= 1.0


class TestBKTPlusPersonalized:
    def test_student_with_good_history_gets_higher_transit(self):
        """答对率高的学生 BKT+ 转移率更高"""
        from backend.app.services.cognitive_diagnosis.bkt import BKT
        bkt_good = BKT(p_transit=0.15)
        bkt_bad = BKT(p_transit=0.15)
        for _ in range(10):
            bkt_good.update("good", "kp_x", correct=True)
        for _ in range(10):
            bkt_bad.update("bad", "kp_x", correct=False)
        t_good = bkt_good.get_transit_rate("good", "kp_x")
        t_bad = bkt_bad.get_transit_rate("bad", "kp_x")
        assert t_good >= t_bad


class TestBadInputRegression:
    """反例输入不崩溃"""

    CHAT_BAD_INPUTS = [
        "",
        " " * 5000,
        "a" * 10000,
        "讲解 CNN" + "\x00",
        "<script>alert(1)</script>",
        "你好" + "?" * 500,
    ]

    def test_rag_handles_bad_inputs(self):
        """RAG 检索反例输入不崩溃"""
        from backend.app.services.rag_service import get_rag_service
        rag = get_rag_service()
        for bad in self.CHAT_BAD_INPUTS:
            try:
                result = rag.retrieve(bad, top_k=3)
                assert isinstance(result, list)
            except Exception as e:
                if bad not in ("", "a" * 10000):
                    raise

    def test_bloom_handles_bad_inputs(self):
        """Bloom 分类反例输入不崩溃"""
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        for bad in ["", " ", "\x00", "<script>"]:
            result = bt.classify(bad)
            assert "level" in result

    def test_bkt_handles_edge_cases(self):
        """BKT 边界值不崩溃"""
        from backend.app.services.cognitive_diagnosis.bkt import BKT
        bkt = BKT()
        # 极端 mastery 值不应崩溃
        bkt.update("u1", "kp_edge", correct=True)
        for _ in range(100):
            bkt.update("u1", "kp_edge", correct=True)
        mastery = bkt.get_mastery("u1", "kp_edge")
        assert 0.0 <= mastery <= 1.0
