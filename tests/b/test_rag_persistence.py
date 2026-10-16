"""RAG index persistence tests (v6 B-P1-2).

Verifies DB-backed TF-IDF index lifecycle:
- build + search round-trip
- incremental updates (insert / update / skip / drop) via content_hash
- course_filter
- force_rebuild
- stats
- RAGService integration (prefers DB backend over JSON)
"""
from __future__ import annotations

import pytest

from backend.app.core.database import configure_database, init_db, SessionLocal
from backend.app.core import models  # noqa: F401  ensure models registered


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    """Redirect global engine to a per-test temp SQLite file."""
    db_path = tmp_path / "rag_test.db"
    configure_database(f"sqlite:///{db_path.as_posix()}")
    init_db()
    # reset IndexManager singleton so it re-reads from the new DB
    from backend.app.services.rag import index_manager as im_mod
    im_mod._index_manager = None
    yield
    SessionLocal.remove_all() if hasattr(SessionLocal, "remove_all") else None


def _sample_chunks():
    return [
        {
            "chunk_id": "py_basics::chunk-1",
            "source": "python/basics.md",
            "course": "python",
            "title_hint": "变量与类型",
            "text": "Python 变量无需声明类型，动态类型是核心特性。整数浮点数字符串都是内置类型。",
        },
        {
            "chunk_id": "py_basics::chunk-2",
            "source": "python/basics.md",
            "course": "python",
            "title_hint": "控制流",
            "text": "if for while 是 Python 的控制流语句。缩进决定代码块，不用大括号。",
        },
        {
            "chunk_id": "ai_intro::chunk-1",
            "source": "ai/intro.md",
            "course": "artificial_intelligence",
            "title_hint": "什么是AI",
            "text": "人工智能是研究让机器具备智能行为的学科。机器学习深度学习是其子领域。",
        },
    ]


# ── IndexManager core ──────────────────────────────────────────────

def test_index_manager_build_and_search_roundtrip():
    from backend.app.services.rag.index_manager import IndexManager
    mgr = IndexManager()
    result = mgr.build(_sample_chunks())
    assert result["chunk_count"] == 3
    assert result["inserted"] == 3
    with SessionLocal() as session:
        assert all(row.doc_freq == {} for row in session.query(models.ChunkVectorRecord))

    hits = mgr.search("Python 变量类型", top_k=2)
    assert len(hits) >= 1
    assert "变量" in hits[0].content or "类型" in hits[0].content
    assert hits[0].source.startswith("python/")


def test_index_manager_idempotent_skip():
    from backend.app.services.rag.index_manager import IndexManager
    mgr = IndexManager()
    mgr.build(_sample_chunks())
    # second build with identical corpus → all skipped
    result = mgr.build(_sample_chunks())
    assert result["skipped"] == 3
    assert result["inserted"] == 0
    assert result["updated"] == 0


def test_index_manager_incremental_update_modified_chunk():
    from backend.app.services.rag.index_manager import IndexManager
    mgr = IndexManager()
    mgr.build(_sample_chunks())
    chunks = _sample_chunks()
    chunks[0]["text"] = "Python 是动态类型语言，变量类型在运行时确定。list dict tuple 是容器类型。"
    result = mgr.build(chunks)
    assert result["updated"] == 1
    assert result["skipped"] == 2
    # search reflects new content
    hits = mgr.search("容器类型 list", top_k=2)
    assert any("容器" in h.content or "list" in h.content for h in hits)


def test_index_manager_incremental_insert_and_drop():
    from backend.app.services.rag.index_manager import IndexManager
    mgr = IndexManager()
    mgr.build(_sample_chunks())
    # add one, remove one
    chunks = _sample_chunks()[:2] + [{
        "chunk_id": "py_oop::chunk-1",
        "source": "python/oop.md",
        "course": "python",
        "title_hint": "面向对象",
        "text": "类与对象是面向对象编程的基础。继承封装多态是三大特性。",
    }]
    result = mgr.build(chunks)
    assert result["inserted"] == 1
    assert result["dropped"] == 1
    assert result["chunk_count"] == 3
    # dropped chunk no longer retrievable
    hits = mgr.search("人工智能 机器学习", top_k=5)
    assert all("ai_intro" not in h.chunk_id for h in hits)


def test_index_manager_course_filter():
    from backend.app.services.rag.index_manager import IndexManager
    mgr = IndexManager()
    mgr.build(_sample_chunks())
    hits = mgr.search("类型", top_k=5, course_filter="artificial_intelligence")
    assert len(hits) >= 1
    assert all(h.course == "artificial_intelligence" for h in hits)


def test_index_manager_force_rebuild():
    from backend.app.services.rag.index_manager import IndexManager
    mgr = IndexManager()
    mgr.build(_sample_chunks())
    result = mgr.build(_sample_chunks(), force_rebuild=True)
    # force_rebuild drops all then re-inserts
    assert result["inserted"] == 3
    assert result["updated"] == 0


def test_index_manager_stats():
    from backend.app.services.rag.index_manager import IndexManager
    mgr = IndexManager()
    mgr.build(_sample_chunks())
    s = mgr.stats()
    assert s["total_chunks"] == 3
    assert s["total_vectors"] == 3
    assert s["backend"] == "sqlite_db"
    assert "python" in s["by_course"]
    assert "artificial_intelligence" in s["by_course"]


def test_index_manager_empty_query_returns_empty():
    from backend.app.services.rag.index_manager import IndexManager
    mgr = IndexManager()
    mgr.build(_sample_chunks())
    assert mgr.search("", top_k=5) == []
    assert mgr.search("   ", top_k=5) == []


# ── RAGService integration ─────────────────────────────────────────

def test_rag_service_uses_db_backend(tmp_path, monkeypatch):
    """RAGService._init_backend should prefer the DB backend."""
    from backend.app.services.rag_service import RAGService

    # point knowledge root at a tiny temp corpus
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "python").mkdir()
    (kb / "python" / "basics.md").write_text(
        "# 变量\nPython 变量动态类型。\n\n# 控制流\nif for while 缩进代码块。", encoding="utf-8"
    )
    svc = RAGService(knowledge_root=kb, persist_path=tmp_path / "idx.json")
    svc.load()
    assert svc._backend_name == "sqlite_db", f"expected sqlite_db, got {svc._backend_name}"
    results = svc.retrieve("Python 变量", top_k=2)
    assert len(results) >= 1
    assert "变量" in results[0]["content"]


def test_rag_service_rebuild_picks_up_new_files(tmp_path):
    from backend.app.services.rag_service import RAGService

    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "python").mkdir()
    (kb / "python" / "basics.md").write_text("# 基础\nPython 基础语法。", encoding="utf-8")
    svc = RAGService(knowledge_root=kb, persist_path=tmp_path / "idx.json")
    svc.load()
    assert svc._backend_name == "sqlite_db"

    # add a new file and rebuild (force_rebuild re-collects chunks from disk)
    (kb / "python" / "oop.md").write_text(
        "# 面向对象编程\n类与对象是面向对象编程的基础概念。继承封装多态是三大核心特性。"
        "Python 用 class 关键字定义类，支持单继承和多继承。", encoding="utf-8"
    )
    svc.load(force_rebuild=True)
    results = svc.retrieve("面向对象 继承", top_k=5)
    assert any("面向对象" in r["content"] or "继承" in r["content"] for r in results)
