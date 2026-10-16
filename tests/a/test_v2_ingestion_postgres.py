"""Disposable PostgreSQL ingest/version smoke without provider calls."""
from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from backend.app.core import database
from backend.app.core.models import DocumentChunkRecord, DocumentVersionRecord, KnowledgeDocumentRecord
from backend.app.services import knowledge_ingest


@pytest.mark.asyncio
async def test_postgres_repeated_ingest_reuses_embedded_version(monkeypatch, tmp_path):
    url = os.getenv("TEST_V2_POSTGRES_URL")
    if not url:
        pytest.skip("Requires disposable PostgreSQL URL")
    from alembic import command
    from alembic.config import Config

    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    previous_url = database.DATABASE_URL
    database.configure_database(url)
    monkeypatch.setattr(knowledge_ingest, "SessionLocal", database.SessionLocal)
    registry = SimpleNamespace(root=tmp_path,
        get_course=lambda _course: {"id": "artificial_intelligence"}, invalidate=lambda: None)
    monkeypatch.setattr(knowledge_ingest, "get_course_registry", lambda: registry)
    monkeypatch.setattr(knowledge_ingest, "get_knowledge_guard", lambda: SimpleNamespace(
        audit_document=lambda *_args, **_kwargs: {"verdict": "accepted", "issues": []}))
    from backend.app.services import rag_service, embedding_provider
    monkeypatch.setattr(rag_service, "get_rag_service", lambda: SimpleNamespace(
        refresh=lambda: None,
        count_source_chunks=lambda _source: 1,
    ))
    calls = []
    fake = SimpleNamespace(available=True, batch_size=10, provider_name="fixture", model="fixture",
                           dimension=1024,
                           embed_documents=lambda texts: calls.extend(texts) or [[1.0] + [0.0] * 1023 for _ in texts])
    monkeypatch.setattr(embedding_provider, "get_embedding_provider", lambda: fake)
    task_id = str(uuid.uuid4())
    doc_id = f"kbdoc-{task_id.replace('-', '')}"
    kwargs = dict(course="artificial_intelligence", filename="lesson.md",
                  data=b"# Lesson\n\nEvidence for a course lesson.",
                  uploaded_by="teacher", task_id=task_id)
    try:
        first = await knowledge_ingest.ingest_document(**kwargs)
        second = await knowledge_ingest.ingest_document(**kwargs)
        assert first["id"] == second["id"] == doc_id
        assert first["version"]["id"] == second["version"]["id"]
        assert len(calls) == 1
        with database.SessionLocal() as db:
            versions = db.scalars(select(DocumentVersionRecord).where(
                DocumentVersionRecord.document_id == doc_id)).all()
            assert len(versions) == 1
            assert versions[0].metadata_data["embedding"]["status"] == "embedded"
            chunks = db.scalars(select(DocumentChunkRecord).where(
                DocumentChunkRecord.document_version_id == versions[0].id)).all()
            assert len(chunks) == 1 and chunks[0].embedding is not None
        from backend.app.services import vector_reindex
        monkeypatch.setattr(vector_reindex, "SessionLocal", database.SessionLocal)
        monkeypatch.setattr(vector_reindex, "get_embedding_provider", lambda: fake)
        fake.model = "fixture-flash"
        migrated = vector_reindex.reembed_document(doc_id)
        assert migrated["status"] == "embedded" and migrated["version"] == 2
        assert vector_reindex.reembed_document(doc_id)["status"] == "unchanged"
        with database.SessionLocal() as db:
            versions = db.scalars(select(DocumentVersionRecord).where(
                DocumentVersionRecord.document_id == doc_id).order_by(
                    DocumentVersionRecord.version)).all()
            assert [item.metadata_data["embedding"]["model"] for item in versions] == [
                "fixture", "fixture-flash"]
    finally:
        with database.SessionLocal.begin() as db:
            versions = select(DocumentVersionRecord.id).where(DocumentVersionRecord.document_id == doc_id)
            db.execute(delete(DocumentChunkRecord).where(DocumentChunkRecord.document_version_id.in_(versions)))
            db.execute(delete(DocumentVersionRecord).where(DocumentVersionRecord.document_id == doc_id))
            db.execute(delete(KnowledgeDocumentRecord).where(KnowledgeDocumentRecord.id == doc_id))
        database.engine.dispose()
        database.configure_database(previous_url)
