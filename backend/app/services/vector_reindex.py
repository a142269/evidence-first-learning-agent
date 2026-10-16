"""Re-embed an already audited document into a new immutable vector version.

Used for provider/model migration, including teacher uploads. Source chunks
are read from the latest indexed version; the original audit and file are not
reinterpreted. The old version stays available until all new vectors commit.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.core.models import DocumentChunkRecord, DocumentVersionRecord, KnowledgeDocumentRecord
from backend.app.services.embedding_provider import get_embedding_provider


def reembed_document(document_id: str) -> dict:
    provider = get_embedding_provider()
    if not provider.available:
        raise RuntimeError("embedding_provider_not_configured")
    with SessionLocal() as db:
        document = db.get(KnowledgeDocumentRecord, document_id)
        if document is None or document.status != "indexed":
            raise ValueError("indexed_document_required")
        latest = db.scalars(select(DocumentVersionRecord).where(
            DocumentVersionRecord.document_id == document_id).order_by(
                DocumentVersionRecord.version.desc())).first()
        if latest is None or latest.status != "indexed":
            raise ValueError("indexed_version_required")
        previous_embedding = (latest.metadata_data or {}).get("embedding", {})
        if (previous_embedding.get("status") == "embedded"
                and previous_embedding.get("model") == provider.model
                and previous_embedding.get("dimension") == provider.dimension):
            return {"document_id": document_id, "version": latest.version, "status": "unchanged"}
        source_id = latest.id
        source_version = latest.version
        content_hash = latest.content_hash
        parser_name = latest.parser_name
        metadata = dict(latest.metadata_data or {})
        chunks = db.scalars(select(DocumentChunkRecord).where(
            DocumentChunkRecord.document_version_id == source_id).order_by(
                DocumentChunkRecord.ordinal)).all()
        source_chunks = [(item.ordinal, item.content, item.content_hash,
                          dict(item.metadata_data or {})) for item in chunks]
    if not source_chunks:
        raise ValueError("document_chunks_required")
    vectors = []
    for start in range(0, len(source_chunks), provider.batch_size):
        vectors.extend(provider.embed_documents(
            [item[1] for item in source_chunks[start:start + provider.batch_size]]))
    if len(vectors) != len(source_chunks) or any(len(vector) != provider.dimension for vector in vectors):
        raise RuntimeError("embedding_count_mismatch")
    with SessionLocal.begin() as db:
        document = db.scalars(select(KnowledgeDocumentRecord).where(
            KnowledgeDocumentRecord.id == document_id).with_for_update()).first()
        if document is None or document.status != "indexed":
            raise ValueError("indexed_document_required")
        current = db.scalars(select(DocumentVersionRecord).where(
            DocumentVersionRecord.document_id == document_id).order_by(
                DocumentVersionRecord.version.desc())).first()
        if current is None or current.id != source_id:
            raise RuntimeError("document_version_changed_during_reindex")
        version_id = f"docver-{uuid.uuid4().hex[:16]}"
        metadata["embedding"] = {"status": "embedded", "provider": provider.provider_name,
                                 "model": provider.model, "dimension": provider.dimension}
        metadata["reembedded_from"] = source_id
        db.add(DocumentVersionRecord(id=version_id, document_id=document_id,
            version=source_version + 1, content_hash=content_hash, status="indexed",
            parser_name=parser_name, metadata_data=metadata))
        db.flush()
        for (ordinal, content, chunk_hash, chunk_metadata), vector in zip(source_chunks, vectors):
            db.add(DocumentChunkRecord(id=f"docchunk-{uuid.uuid4().hex[:18]}",
                document_version_id=version_id, ordinal=ordinal, content=content,
                content_hash=chunk_hash, embedding=vector, metadata_data=chunk_metadata))
        document.chunk_count = len(source_chunks)
    return {"document_id": document_id, "version": source_version + 1,
            "status": "embedded", "chunk_count": len(source_chunks)}
