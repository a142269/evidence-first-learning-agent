"""Cloud embedding adapter for OpenAI-compatible providers.

Credentials are read only from the environment.  This keeps the portfolio
deployment provider-neutral: Qwen, OpenAI and other compatible endpoints can
be selected without changing application code.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


class EmbeddingProviderError(RuntimeError):
    """A configured embedding provider could not return usable vectors."""


class OpenAICompatibleEmbeddingProvider:
    """Small, synchronous client intended for Celery ingestion jobs."""

    def __init__(self) -> None:
        self.base_url = os.getenv("EMBEDDING_BASE_URL", "").strip().rstrip("/")
        self.api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
        self.model = os.getenv("EMBEDDING_MODEL", "").strip()
        self.dimension = int(os.getenv("EMBEDDING_DIM", "1024"))
        self.timeout_seconds = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "45"))
        # text-embedding-v4 accepts 10 inputs per request; qwen3.7 accepts 20.
        # Keep the safe cross-provider default and let deployment config opt in.
        self.batch_size = max(1, min(int(os.getenv("EMBEDDING_BATCH_SIZE", "10")), 20))

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    def embed_query(self, text: str) -> list[float]:
        """Bound interactive retrieval so a provider stall cannot consume the Run deadline."""
        return self.embed_documents([text], max_attempts=1,
                                    timeout_seconds=min(self.timeout_seconds, 20.0))[0]

    def embed_documents(self, texts: list[str], *, max_attempts: int = 3,
                        timeout_seconds: float | None = None) -> list[list[float]]:
        if not texts:
            return []
        if not self.available:
            raise EmbeddingProviderError("embedding_provider_not_configured")
        from backend.app.agent_runtime.eval_cost_guard import reserve_embedding_call
        attempts = max(1, min(max_attempts, 3))
        response = None
        for attempt in range(attempts):
            # Reserve each attempt. A timed-out request may still have been
            # accepted and billed by the provider.
            reserve_embedding_call(texts)
            try:
                response = requests.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "input": texts, "dimensions": self.dimension},
                    timeout=self.timeout_seconds if timeout_seconds is None else timeout_seconds,
                )
            except requests.RequestException as exc:
                LOGGER.warning("embedding request failed (%s), attempt %s/%s",
                               type(exc).__name__, attempt + 1, attempts)
                if attempt + 1 == attempts:
                    raise EmbeddingProviderError("embedding_provider_request_failed") from exc
                time.sleep(2 ** attempt)
                continue
            if response.status_code not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                break
            LOGGER.warning("embedding provider transient HTTP %s, attempt %s/%s",
                           response.status_code, attempt + 1, attempts)
            time.sleep(2 ** attempt)
        assert response is not None
        if response.status_code >= 400:
            raise EmbeddingProviderError(
                f"embedding_provider_http_{response.status_code}"
            )
        try:
            payload: dict[str, Any] = response.json()
            items = sorted(payload["data"], key=lambda item: int(item["index"]))
            vectors = [list(map(float, item["embedding"])) for item in items]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingProviderError("embedding_provider_invalid_response") from exc
        if len(vectors) != len(texts) or any(len(vector) != self.dimension for vector in vectors):
            raise EmbeddingProviderError(
                f"embedding_dimension_mismatch_expected_{self.dimension}"
            )
        return vectors


def get_embedding_provider() -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider()
