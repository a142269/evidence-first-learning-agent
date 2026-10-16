"""Real PostgreSQL version-scope query without paid embeddings."""
import os
import uuid

import pytest
from sqlalchemy import delete, text

from backend.app.core import database
from backend.app.core.models import DocumentVersionRecord, KnowledgeDocumentRecord
from backend.app.services import enterprise_retriever


def test_retriever_ignores_old_indexed_version_and_wrong_course(monkeypatch):
    url = os.getenv("TEST_V2_POSTGRES_URL")
    if not url:
        pytest.skip("Requires disposable PostgreSQL URL")
    from alembic import command
    from alembic.config import Config
    monkeypatch.setenv("DATABASE_URL", url.replace("postgresql://", "postgresql+psycopg://", 1))
    command.upgrade(Config("alembic.ini"), "head")
    old_url = database.DATABASE_URL
    database.configure_database(url.replace("postgresql://", "postgresql+psycopg://", 1))
    monkeypatch.setattr(enterprise_retriever, "DATABASE_URL", database.DATABASE_URL)
    prefix = uuid.uuid4().hex
    doc_id, foreign_id, retired_id = f"doc-{prefix}", f"foreign-{prefix}", f"retired-{prefix}"
    vector = [1.0] + [0.0] * 1023
    fake = type("Embedding", (), {"available": True, "model": "flash-fixture",
        "embed_documents": lambda self, values: [vector for _ in values]})()
    monkeypatch.setattr(enterprise_retriever, "get_embedding_provider", lambda: fake)
    try:
        with database.SessionLocal.begin() as db:
            db.add_all([
                KnowledgeDocumentRecord(id=doc_id, course="artificial_intelligence", filename="chapter.md",
                                        storage_key="chapter.md", status="indexed"),
                KnowledgeDocumentRecord(id=foreign_id, course="other_course", filename="foreign.md",
                                        storage_key="foreign.md", status="indexed"),
                KnowledgeDocumentRecord(id=retired_id, course="artificial_intelligence", filename="retired.md",
                                        storage_key="retired.md", status="indexed"),
            ])
            db.flush()
            db.add_all([
                DocumentVersionRecord(id=f"old-{prefix}", document_id=doc_id, version=1,
                                      content_hash="old", status="indexed",
                                      metadata_data={"embedding": {"model": "retired-fixture"}}),
                DocumentVersionRecord(id=f"new-{prefix}", document_id=doc_id, version=2,
                                      content_hash="new", status="indexed",
                                      metadata_data={"embedding": {"model": "flash-fixture"}}),
                DocumentVersionRecord(id=f"other-{prefix}", document_id=foreign_id, version=1,
                                      content_hash="other", status="indexed",
                                      metadata_data={"embedding": {"model": "flash-fixture"}}),
                DocumentVersionRecord(id=f"retired-{prefix}", document_id=retired_id, version=1,
                                      content_hash="retired", status="indexed",
                                      metadata_data={"embedding": {"model": "retired-fixture"}}),
            ])
            db.flush()
            for version, chunk, content in (("old", "oldchunk", "obsolete content"),
                                            ("new", "newchunk", "current content"),
                                            ("other", "otherchunk", "other content"),
                                            ("retired", "retiredchunk", "retired model content")):
                db.execute(text("INSERT INTO document_chunks "
                                "(id, document_version_id, ordinal, content, content_hash, embedding, metadata, created_at) "
                                "VALUES (:id, :version_id, 0, :content, :hash, CAST(:vector AS vector), '{}', 1)"),
                           {"id": f"{chunk}-{prefix}", "version_id": f"{version}-{prefix}",
                            "content": content, "hash": version,
                            "vector": enterprise_retriever.EnterpriseRetriever._vector_literal(vector)})
        retriever = enterprise_retriever.EnterpriseRetriever()
        for strategy in ("dense", "hybrid", "hybrid_diverse"):
            hits = retriever.retrieve("current", course_id="artificial_intelligence",
                                      strategy=strategy)
            assert [hit["chunk_id"] for hit in hits] == [f"newchunk-{prefix}"]
    finally:
        with database.SessionLocal.begin() as db:
            db.execute(delete(KnowledgeDocumentRecord).where(
                KnowledgeDocumentRecord.id.in_((doc_id, foreign_id, retired_id))))
        database.engine.dispose()
        database.configure_database(old_url)
