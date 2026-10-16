"""
GraphRAG hybrid and fusion tests.
"""
from types import SimpleNamespace

from sqlalchemy import create_engine

from backend.app.core import models  # noqa: F401
from backend.app.core.database import Base


class TestGraphRAGHybrid:
    def test_retriever_fallback_to_tfidf_when_no_kg(self, monkeypatch):
        from backend.app.services.knowledge_graph.retriever import GraphRetriever
        from backend.app.services.rag_service import get_rag_service

        rag = get_rag_service()
        retriever = GraphRetriever(rag_service=rag)
        monkeypatch.setattr(retriever.kg, "list_kps", lambda **kw: [])

        results = retriever.retrieve("CNN", top_k=3, mode="hybrid")

        assert isinstance(results, list)

    def test_entity_match_from_query(self):
        from backend.app.services.knowledge_graph.retriever import GraphRetriever
        from backend.app.services.rag_service import get_rag_service

        rag = get_rag_service()
        retriever = GraphRetriever(rag_service=rag)

        matched = retriever._match_entities("Python 变量", course="")

        assert isinstance(matched, list)

    def test_rag_fusion_mode_returns_rrf_ranked_results(self):
        from backend.app.services.knowledge_graph.retriever import GraphRetriever

        class FakeKG:
            def list_kps(self, course=""):
                return [
                    SimpleNamespace(id="kp_cnn", name="CNN"),
                    SimpleNamespace(id="kp_pool", name="池化"),
                ]

            def get_subgraph(self, seed_kp_ids, hops=2):
                nodes = {
                    "kp_cnn": SimpleNamespace(id="kp_cnn", name="CNN", course="ai"),
                    "kp_pool": SimpleNamespace(id="kp_pool", name="池化", course="ai"),
                }
                edges = [("kp_cnn", "kp_pool", "related", 0.8)]
                return {"nodes": nodes, "edges": edges}

        class FakeRAG:
            def retrieve(self, query, top_k=5, course_filter=""):
                tables = {
                    "CNN 卷积层 原理": [
                        {"chunk_id": "a", "source": "doc_a", "content": "A", "course": "ai", "score": 0.95},
                        {"chunk_id": "b", "source": "doc_b", "content": "B", "course": "ai", "score": 0.82},
                        {"chunk_id": "c", "source": "doc_c", "content": "C", "course": "ai", "score": 0.70},
                    ],
                    "CNN": [
                        {"chunk_id": "b", "source": "doc_b", "content": "B", "course": "ai", "score": 0.93},
                        {"chunk_id": "c", "source": "doc_c", "content": "C", "course": "ai", "score": 0.81},
                    ],
                    "池化": [
                        {"chunk_id": "b", "source": "doc_b", "content": "B", "course": "ai", "score": 0.88},
                        {"chunk_id": "a", "source": "doc_a", "content": "A", "course": "ai", "score": 0.84},
                    ],
                }
                return tables.get(query, [])[:top_k]

        retriever = GraphRetriever(kg_store=FakeKG(), rag_service=FakeRAG())

        results = retriever.retrieve("CNN 卷积层 原理", top_k=3, mode="rag_fusion")

        assert [item["chunk_id"] for item in results[:2]] == ["b", "a"]
        assert results[0]["score"] == results[0]["rag_fusion_score"]
        assert results[0]["rag_fusion_score"] > results[1]["rag_fusion_score"]
        assert any(rank.startswith("query:CNN 卷积层 原理#") for rank in results[0]["rag_fusion_ranks"])
        assert any(rank.startswith("entity:CNN#") for rank in results[0]["rag_fusion_ranks"])


class TestKnowledgeGraphStore:
    def test_upsert_and_find(self):
        import tempfile

        from backend.app.core.database import configure_database
        from backend.app.services.knowledge_graph.store import KnowledgeGraphStore

        engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/test.db")
        Base.metadata.create_all(bind=engine)
        configure_database(str(engine.url))

        store = KnowledgeGraphStore()
        store.upsert_kp("kp_gcn", "图卷积网络", course="ai", description="GCN基础")
        found = store.find_by_name("图卷积网络")

        assert len(found) >= 1

    def test_get_subgraph(self):
        import tempfile

        from backend.app.core.database import configure_database
        from backend.app.services.knowledge_graph.store import KnowledgeGraphStore

        engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/test_sub.db")
        Base.metadata.create_all(bind=engine)
        configure_database(str(engine.url))

        store = KnowledgeGraphStore()
        store.upsert_kp("n1", "节点1", course="ai")
        store.upsert_kp("n2", "节点2", course="ai")
        store.add_relation("n1", "n2", "prerequisite")
        sg = store.get_subgraph(["n1"], hops=1)

        assert len(sg["nodes"]) >= 2
        assert len(sg["edges"]) >= 1
