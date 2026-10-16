from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.models import DocumentChunkRecord, DocumentVersionRecord, KnowledgeDocumentRecord
from backend.app.services import vector_reindex


def test_model_switch_copies_audited_chunks_to_new_version(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'vectors.db').as_posix()}")
    for model in (KnowledgeDocumentRecord, DocumentVersionRecord, DocumentChunkRecord):
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as db:
        db.add(KnowledgeDocumentRecord(id="doc", course="course", filename="lesson.md",
                                       status="indexed", uploaded_by="teacher"))
        db.flush()
        db.add(DocumentVersionRecord(id="old", document_id="doc", version=1,
                                     content_hash="same", status="indexed", parser_name="md",
                                     metadata_data={"embedding": {"status": "embedded",
                                                                  "model": "retired", "dimension": 1024}}))
        db.flush()
        db.add(DocumentChunkRecord(id="old-chunk", document_version_id="old", ordinal=0,
                                   content="audited content", content_hash="hash",
                                   embedding=[0.0] * 1024))
    monkeypatch.setattr(vector_reindex, "SessionLocal", sessions)
    calls = []
    provider = SimpleNamespace(available=True, model="flash", dimension=1024,
        provider_name="fixture", batch_size=10,
        embed_documents=lambda texts: calls.extend(texts) or [[1.0] + [0.0] * 1023 for _ in texts])
    monkeypatch.setattr(vector_reindex, "get_embedding_provider", lambda: provider)
    result = vector_reindex.reembed_document("doc")
    assert result["status"] == "embedded" and result["version"] == 2
    assert vector_reindex.reembed_document("doc")["status"] == "unchanged"
    assert calls == ["audited content"]
    with sessions() as db:
        versions = db.query(DocumentVersionRecord).order_by(DocumentVersionRecord.version).all()
        assert [item.version for item in versions] == [1, 2]
        assert versions[1].metadata_data["reembedded_from"] == "old"
        chunks = db.query(DocumentChunkRecord).order_by(DocumentChunkRecord.id).all()
        assert len(chunks) == 2
        assert {item.content for item in chunks} == {"audited content"}
    engine.dispose()


def test_failed_reembedding_keeps_old_version(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'failure.db').as_posix()}")
    for model in (KnowledgeDocumentRecord, DocumentVersionRecord, DocumentChunkRecord):
        model.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as db:
        db.add(KnowledgeDocumentRecord(id="doc", course="course", filename="lesson.md",
                                       status="indexed", uploaded_by="teacher"))
        db.flush()
        db.add(DocumentVersionRecord(id="old", document_id="doc", version=1,
                                     content_hash="same", status="indexed"))
        db.flush()
        db.add(DocumentChunkRecord(id="old-chunk", document_version_id="old", ordinal=0,
                                   content="audited content", content_hash="hash"))
    monkeypatch.setattr(vector_reindex, "SessionLocal", sessions)
    def fail(_texts):
        raise RuntimeError("provider_unavailable")
    monkeypatch.setattr(vector_reindex, "get_embedding_provider", lambda: SimpleNamespace(
        available=True, model="flash", dimension=1024, batch_size=10,
        embed_documents=fail))
    with pytest.raises(RuntimeError, match="provider_unavailable"):
        vector_reindex.reembed_document("doc")
    with sessions() as db:
        assert db.query(DocumentVersionRecord).count() == 1
        assert db.query(DocumentChunkRecord).count() == 1
    engine.dispose()
