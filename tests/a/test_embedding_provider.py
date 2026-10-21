from __future__ import annotations

from backend.app.services.embedding_provider import OpenAICompatibleEmbeddingProvider


class _Response:
    status_code = 200

    @staticmethod
    def json():
        return {
            "data": [
                {"index": 1, "embedding": [0.2, 0.3]},
                {"index": 0, "embedding": [0.0, 0.1]},
            ]
        }


def test_openai_compatible_embedding_provider_orders_vectors(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://provider.example.com/v1/")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding")
    monkeypatch.setenv("EMBEDDING_DIM", "2")
    monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)

    sent = {}

    def fake_post(url, **kwargs):
        sent["url"] = url
        sent.update(kwargs)
        return _Response()

    monkeypatch.setattr("backend.app.services.embedding_provider.requests.post", fake_post)
    provider = OpenAICompatibleEmbeddingProvider()

    assert provider.embed_documents(["first", "second"]) == [[0.0, 0.1], [0.2, 0.3]]
    assert sent["url"] == "https://provider.example.com/v1/embeddings"
    assert sent["json"]["dimensions"] == 2
    assert sent["headers"]["Authorization"] == "Bearer test-key"
    assert provider.batch_size == 10
