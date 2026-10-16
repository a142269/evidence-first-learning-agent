from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.models import (
    DocumentChunkRecord, DocumentVersionRecord, IngestionTaskRecord, KnowledgeDocumentRecord,
)
from backend.app.repositories.ingestion_tasks import IngestionTasks
from backend.app.services import knowledge_ingest


@pytest.fixture
def storage(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'ingestion.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    for model in (IngestionTaskRecord, KnowledgeDocumentRecord, DocumentVersionRecord, DocumentChunkRecord):
        model.__table__.create(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def test_task_key_is_content_bound_and_worker_claim_is_fenced(storage):
    repo = IngestionTasks(storage)
    args = dict(uploader="teacher", course_id="course-a", filename="intro.md",
                data=b"hello", deep_audit=False, key="upload-key-001")
    first, created = repo.create_or_get(**args)
    assert created and first["status"] == "queued"
    repeated, created = repo.create_or_get(**args)
    assert not created and repeated["task_id"] == first["task_id"]
    with pytest.raises(ValueError, match="idempotency_key_conflict"):
        repo.create_or_get(**{**args, "data": b"changed"})
    task_id = first["task_id"]
    assert repo.claim(task_id, "worker-one")
    assert not repo.claim(task_id, "worker-two")
    assert not repo.complete(task_id, "worker-two", {"status": "indexed"})
    assert repo.complete(task_id, "worker-one", {"status": "indexed", "id": "doc"})
    assert not repo.claim(task_id, "worker-two")
    assert repo.get(task_id)["result"]["id"] == "doc"


@pytest.mark.asyncio
async def test_worker_retry_returns_same_logical_document_and_version(storage, tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge_ingest, "SessionLocal", storage)
    registry = SimpleNamespace(root=tmp_path,
        get_course=lambda _course: {"id": "course-a"}, invalidate=lambda: None)
    monkeypatch.setattr(knowledge_ingest, "get_course_registry", lambda: registry)
    monkeypatch.setattr(knowledge_ingest, "get_knowledge_guard", lambda: SimpleNamespace(
        audit_document=lambda *_args, **_kwargs: {"verdict": "accepted", "issues": []}))
    from backend.app.services import rag_service, embedding_provider
    monkeypatch.setattr(rag_service, "get_rag_service", lambda: SimpleNamespace(refresh=lambda: None))
    monkeypatch.setattr(embedding_provider, "get_embedding_provider", lambda: SimpleNamespace(available=False))
    task_id = "12345678-1234-1234-1234-123456789abc"
    kwargs = dict(course="course-a", filename="intro.md", data=b"RAG uses retrieval evidence.",
                  uploaded_by="teacher", task_id=task_id)
    first = await knowledge_ingest.ingest_document(**kwargs)
    second = await knowledge_ingest.ingest_document(**kwargs)
    assert first["id"] == second["id"]
    assert first["version"]["id"] == second["version"]["id"]
    with storage() as db:
        assert db.query(KnowledgeDocumentRecord).count() == 1
        assert db.query(DocumentVersionRecord).count() == 1


def test_curated_backfill_creates_new_vector_version_when_model_changes(storage, monkeypatch):
    monkeypatch.setattr(knowledge_ingest, "SessionLocal", storage)
    from backend.app.services import embedding_provider
    selected = {"model": "older-embedding"}
    class FakeProvider:
        available = True
        batch_size = 10
        provider_name = "fixture"
        dimension = 1024

        @property
        def model(self):
            return selected["model"]

        def embed_documents(self, texts):
            return [[1.0] + [0.0] * 1023 for _ in texts]

    monkeypatch.setattr(embedding_provider, "get_embedding_provider", FakeProvider)
    kwargs = dict(course="course-a", storage_key="course-a/lesson.md", text="# Lesson\nCurrent text")
    first = knowledge_ingest.backfill_curated_markdown(**kwargs)
    selected["model"] = "flash-embedding"
    second = knowledge_ingest.backfill_curated_markdown(**kwargs)
    third = knowledge_ingest.backfill_curated_markdown(**kwargs)
    assert first["version"] == 1
    assert second["version"] == 2
    assert third["status"] == "unchanged" and third["version"] == 2
    with storage() as db:
        versions = db.query(DocumentVersionRecord).order_by(DocumentVersionRecord.version).all()
        assert [item.metadata_data["embedding"]["model"] for item in versions] == [
            "older-embedding", "flash-embedding"]
