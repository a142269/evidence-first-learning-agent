from __future__ import annotations

from backend.app.api.v2.learning_runs import LearningRuntime


def test_learning_runtime_fuses_enterprise_and_legacy_evidence(monkeypatch):
    class Enterprise:
        def retrieve(self, *_args, **_kwargs):
            return [{"chunk_id": "upload-1", "source": "uploads/teacher.md", "score": 0.8}]

    class Legacy:
        def retrieve(self, *_args, **_kwargs):
            return [
                {
                    "chunk_id": "chapter-9",
                    "source": "artificial_intelligence/chapters/09_rag.md",
                    "score": 0.9,
                }
            ]

    monkeypatch.setattr(
        "backend.app.services.enterprise_retriever.get_enterprise_retriever", lambda: Enterprise()
    )
    monkeypatch.setattr("backend.app.services.rag_service.get_rag_service", lambda: Legacy())

    hits = LearningRuntime().retrieve("RAG 的基本流程", "artificial_intelligence")

    assert {item["source"] for item in hits} == {
        "uploads/teacher.md",
        "artificial_intelligence/chapters/09_rag.md",
    }


def test_learning_runtime_deduplicates_a_document_present_in_both_indexes(monkeypatch):
    class Enterprise:
        def retrieve(self, *_args, **_kwargs):
            return [{"chunk_id": "pg-upload", "source": "uploads/teacher.md", "score": 0.9}]

    class Legacy:
        def retrieve(self, *_args, **_kwargs):
            return [
                {"chunk_id": "legacy-upload", "source": "uploads/teacher.md", "score": 0.9},
                {"chunk_id": "chapter-9", "source": "artificial_intelligence/chapters/09_rag.md", "score": 0.8},
            ]

    monkeypatch.setattr(
        "backend.app.services.enterprise_retriever.get_enterprise_retriever", lambda: Enterprise()
    )
    monkeypatch.setattr("backend.app.services.rag_service.get_rag_service", lambda: Legacy())

    hits = LearningRuntime().retrieve("RAG", "artificial_intelligence")

    assert [item["source"] for item in hits].count("uploads/teacher.md") == 1
    assert any(item["source"].endswith("09_rag.md") for item in hits)


def test_learning_runtime_keeps_confident_chinese_source_after_cross_index_fusion(monkeypatch):
    class Enterprise:
        def retrieve(self, *_args, **_kwargs):
            return ([{"chunk_id": "exact", "source": "chapters/exact.md", "score": 46,
                      "lexical_rescue": True}] + [
                {"chunk_id": f"pg-{index}", "source": f"chapters/{index}.md"}
                for index in range(5)
            ])

    class Legacy:
        def retrieve(self, *_args, **_kwargs):
            return [
                {"chunk_id": f"legacy-{index}", "source": f"chapters/{index}.md"}
                for index in range(5)
            ]

    monkeypatch.setattr(
        "backend.app.services.enterprise_retriever.get_enterprise_retriever", lambda: Enterprise()
    )
    monkeypatch.setattr("backend.app.services.rag_service.get_rag_service", lambda: Legacy())
    hits = LearningRuntime().retrieve("探索与利用的矛盾是什么？", "artificial_intelligence")
    assert len(hits) == 5
    assert hits[0]["source"] == "chapters/exact.md"
