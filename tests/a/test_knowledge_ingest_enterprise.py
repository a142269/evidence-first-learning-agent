from __future__ import annotations

from backend.app.core.models import DocumentChunkRecord, DocumentVersionRecord
from backend.app.services import knowledge_ingest


class _Query:
    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    @staticmethod
    def first():
        return None


class _Session:
    def __init__(self):
        self.added = []
        self.flush_calls = 0
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    @staticmethod
    def query(*_args):
        return _Query()

    def add(self, item):
        # Chunks are only valid after their parent row has been flushed.
        if isinstance(item, DocumentChunkRecord):
            assert self.flush_calls == 1
        self.added.append(item)

    def flush(self):
        assert len(self.added) == 1
        assert isinstance(self.added[0], DocumentVersionRecord)
        self.flush_calls += 1

    def commit(self):
        assert self.flush_calls == 1
        self.committed = True


class _UnavailableProvider:
    available = False


def test_enterprise_persistence_flushes_document_version_before_chunks(monkeypatch):
    sessions: list[_Session] = []

    def session_factory():
        session = _Session()
        sessions.append(session)
        return session

    monkeypatch.setattr(knowledge_ingest, "SessionLocal", session_factory)
    monkeypatch.setattr(
        "backend.app.services.embedding_provider.get_embedding_provider",
        lambda: _UnavailableProvider(),
    )

    result = knowledge_ingest._persist_enterprise_version(
        document_id="document-1",
        content_hash="content-hash",
        text="a small document",
        status="indexed",
        filename="sample.md",
    )

    write_session = sessions[1]
    assert result["chunk_count"] == 1
    assert write_session.committed is True
    assert write_session.flush_calls == 1
    assert isinstance(write_session.added[0], DocumentVersionRecord)
    assert isinstance(write_session.added[1], DocumentChunkRecord)
