"""
认知诊断模块测试：DINA / BKT / Bloom
"""
import pytest
from sqlalchemy import create_engine


class TestBloomTaxonomy:
    def test_classify_remember(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("请列举Python的三种基本数据类型")
        assert result["level"] in ("remember", "understand")

    def test_classify_create(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        bt = BloomTaxonomy()
        result = bt.classify("设计一个学生管理系统，包含增删改查功能")
        assert result["level"] in ("create", "apply", "analyze")

    def test_level_index_and_weight(self):
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
        assert BloomTaxonomy.level_index("remember") == 0
        assert BloomTaxonomy.level_index("create") == 5
        assert BloomTaxonomy.level_difficulty_weight("create") > BloomTaxonomy.level_difficulty_weight("remember")


class TestBKT:
    def test_update_increases_mastery_on_correct(self):
        from backend.app.services.cognitive_diagnosis.bkt import BKT
        bkt = BKT()
        initial = bkt.get_mastery("stu1", "kp_python")
        bkt.update("stu1", "kp_python", correct=True)
        after_correct = bkt.get_mastery("stu1", "kp_python")
        assert after_correct >= initial

    def test_update_decreases_mastery_on_wrong(self):
        from backend.app.services.cognitive_diagnosis.bkt import BKT
        # 先答对几次把 mastery 提上去
        bkt = BKT(p_initial=0.5)
        for _ in range(3):
            bkt.update("stu1", "kp_ml", correct=True)
        high = bkt.get_mastery("stu1", "kp_ml")
        bkt.update("stu1", "kp_ml", correct=False)
        after_wrong = bkt.get_mastery("stu1", "kp_ml")
        assert after_wrong < high

    def test_trend_detection(self):
        from backend.app.services.cognitive_diagnosis.bkt import BKT
        bkt = BKT(p_initial=0.3)
        for _ in range(5):
            bkt.update("stu1", "kp_dl", correct=True)
        assert bkt.trend("stu1", "kp_dl") == "improving"


class TestDINA:
    def test_q_matrix_shape(self):
        from backend.app.services.cognitive_diagnosis.dina import DINA
        dina = DINA()
        items = [
            {"item_id": 1, "kp_ids": ["kp_a", "kp_b"]},
            {"item_id": 2, "kp_ids": ["kp_a"]},
        ]
        Q = dina.build_q_matrix(items, ["kp_a", "kp_b"])
        assert Q.shape == (2, 2)
        assert Q[0, 0] == 1 and Q[0, 1] == 1

    def test_fallback_on_insufficient_data(self):
        from backend.app.services.cognitive_diagnosis.dina import diagnose_student
        result = diagnose_student(
            responses={1: {1: 1}},
            items=[{"item_id": 1, "kp_ids": ["kp_a"]}],
            kp_ids=["kp_a"],
            student_ids=[1],
        )
        assert "alpha" in result
        assert 1 in result["alpha"]
