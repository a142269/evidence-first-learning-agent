from __future__ import annotations

import requests
import pytest

from backend.app.services.embedding_provider import (
    EmbeddingProviderError,
    OpenAICompatibleEmbeddingProvider,
)


def test_embedding_network_timeout_becomes_recoverable_provider_error(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embedding.example/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding")

    def timeout(*_args, **_kwargs):
        raise requests.exceptions.ReadTimeout("simulated provider timeout")

    monkeypatch.setattr("backend.app.services.embedding_provider.requests.post", timeout)
    monkeypatch.setattr("backend.app.services.embedding_provider.time.sleep", lambda _seconds: None)

    with pytest.raises(EmbeddingProviderError, match="embedding_provider_request_failed"):
        OpenAICompatibleEmbeddingProvider().embed_documents(["retrieval query"])


def test_embedding_retry_reserves_every_attempt(monkeypatch):
    from backend.app.agent_runtime import eval_cost_guard

    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embedding.example/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding")
    monkeypatch.setenv("EMBEDDING_DIM", "2")
    monkeypatch.setattr("backend.app.services.embedding_provider.time.sleep", lambda _seconds: None)
    reservations = []
    monkeypatch.setattr(eval_cost_guard, "reserve_embedding_call", lambda texts: reservations.append(texts))
    attempts = []

    class Response:
        status_code = 200

        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

    def post(*_args, **_kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise requests.exceptions.ReadTimeout("simulated timeout")
        return Response()

    monkeypatch.setattr("backend.app.services.embedding_provider.requests.post", post)
    assert OpenAICompatibleEmbeddingProvider().embed_documents(["query"]) == [[0.1, 0.2]]
    assert len(attempts) == len(reservations) == 2


def test_interactive_query_uses_one_bounded_attempt(monkeypatch):
    from backend.app.agent_runtime import eval_cost_guard

    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://embedding.example/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-embedding")
    monkeypatch.setenv("EMBEDDING_TIMEOUT_SECONDS", "45")
    monkeypatch.setattr(eval_cost_guard, "reserve_embedding_call", lambda _texts: None)
    calls = []

    def timeout(*_args, **kwargs):
        calls.append(kwargs["timeout"])
        raise requests.exceptions.ReadTimeout("simulated timeout")

    monkeypatch.setattr("backend.app.services.embedding_provider.requests.post", timeout)
    with pytest.raises(EmbeddingProviderError, match="embedding_provider_request_failed"):
        OpenAICompatibleEmbeddingProvider().embed_query("retrieval query")
    assert calls == [20.0]
