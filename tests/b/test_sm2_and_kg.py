"""
SM-2 间隔重复 + 知识图谱测试
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.core import models  # noqa: F401


class TestSM2:
    def test_initial_state(self):
        from backend.app.services.spaced_repetition.sm2 import SM2
        sm2 = SM2()
        state = sm2.get_schedule("u1", "item1")
        assert state is None  # 未学习过

    def test_quality_5_jumps_to_interval_6(self):
        from backend.app.services.spaced_repetition.sm2 import SM2
        sm2 = SM2()
        sm2.review("u1", "item1", quality=5)  # rep=1, interval=1
        state = sm2.review("u1", "item1", quality=5)  # rep=2, interval=6
        assert state["interval"] == 6
        assert state["repetitions"] == 2

    def test_quality_below_3_resets(self):
        from backend.app.services.spaced_repetition.sm2 import SM2
        sm2 = SM2()
        sm2.review("u1", "item_r", quality=5)
        sm2.review("u1", "item_r", quality=5)
        state = sm2.review("u1", "item_r", quality=1)  # reset
        assert state["repetitions"] == 0
        assert state["interval"] == 1

    def test_due_items_and_stats(self):
        from backend.app.services.spaced_repetition.sm2 import SM2
        import time
        sm2 = SM2()
        sm2.review("u1", "due_now", quality=0)
        # 应该立刻到期
        due = sm2.daily_review_list("u1")
        assert "due_now" in due
        stats = sm2.stats("u1")
        assert stats["total_items"] >= 1


class TestKnowledgeGraph:
    def test_store_upsert_and_query(self):
        from backend.app.core.database import configure_database
        from backend.app.services.knowledge_graph.store import KnowledgeGraphStore
        import tempfile, os

        tmp = tempfile.mkdtemp()
        try:
            db_url = f"sqlite:///{tmp}/kg_test.db"
            configure_database(db_url)
            Base.metadata.create_all(bind=create_engine(db_url))

            store = KnowledgeGraphStore()
            store.upsert_kp("kp_test", "Python变量", course="python")
            kp = store.get_kp("kp_test")
            assert kp is not None
            assert kp.name == "Python变量"
            assert store.kp_count() >= 1
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_relations_and_neighbors(self):
        from backend.app.core.database import configure_database
        from backend.app.services.knowledge_graph.store import KnowledgeGraphStore
        import tempfile, os, shutil

        tmp = tempfile.mkdtemp()
        try:
            db_url = f"sqlite:///{tmp}/kg_test2.db"
            configure_database(db_url)
            Base.metadata.create_all(bind=create_engine(db_url))

            store = KnowledgeGraphStore()
            store.upsert_kp("kp_a", "Python基础", course="python")
            store.upsert_kp("kp_b", "面向对象", course="python")
            store.add_relation("kp_a", "kp_b", "prerequisite")
            assert store.relation_count() >= 1

            neighbors = store.get_neighbors("kp_a", direction="out")
            assert len(neighbors) >= 1
            assert neighbors[0]["kp_id"] == "kp_b"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
