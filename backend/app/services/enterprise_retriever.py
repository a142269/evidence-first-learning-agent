"""PostgreSQL/pgvector retrieval for the evidence-first V2 learning run.

The V1 RAG index remains an explicit fallback for built-in/offline material.
This retriever gives asynchronously uploaded, versioned teacher documents a
production path: cloud embedding -> pgvector dense candidates + PostgreSQL FTS
-> reciprocal-rank fusion (RRF) -> cited evidence.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable

from sqlalchemy import text

from backend.app.core.database import DATABASE_URL, SessionLocal
from backend.app.services.embedding_provider import (
    EmbeddingProviderError,
    get_embedding_provider,
)

LOGGER = logging.getLogger(__name__)
RRF_K = 60
RETRIEVAL_STRATEGIES = frozenset({"dense", "hybrid", "hybrid_diverse"})
_CHINESE_QUESTION_WORDS = re.compile(r"是什么|为什么|有什么|有哪些|什么|如何|怎么|做什么")


def chinese_search_grams(query: str) -> list[str]:
    """Extract short Chinese phrases for a bounded substring fallback.

    PostgreSQL's ``simple`` text search treats an unsegmented Chinese question
    as one lexeme, which rarely matches a passage containing the answer.
    """
    chinese = re.findall(r"[\u4e00-\u9fff]+", _CHINESE_QUESTION_WORDS.sub(" ", query))
    if sum(map(len, chinese)) > 24:
        return []
    grams = {
        phrase[start:start + size]
        for phrase in chinese
        for size in (2, 3, 4)
        for start in range(max(0, len(phrase) - size + 1))
    }
    return sorted(grams, key=lambda gram: (-len(gram), gram))


def confident_chinese_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Only promote a source with much stronger phrase evidence than peers."""
    if not candidates:
        return None
    first = candidates[0]
    first_score = float(first.get("score") or 0)
    second_score = float(candidates[1].get("score") or 0) if len(candidates) > 1 else 0
    return first if first_score > 0 and first_score >= 2.5 * max(1, second_score) else None


def diversify_candidates(candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    """Deterministic greedy selection that discourages same-document near duplicates."""
    remaining = list(candidates)
    selected: list[dict[str, Any]] = []
    def terms(item: dict[str, Any]) -> set[str]:
        return set(re.findall(r"[\w\u4e00-\u9fff]+", str(item.get("content", "")).lower()))
    while remaining and len(selected) < top_k:
        def utility(item: dict[str, Any]) -> float:
            if not selected:
                return float(item.get("score") or 0)
            item_terms = terms(item)
            similarity = max(
                (len(item_terms & terms(prev)) / max(1, len(item_terms | terms(prev))))
                for prev in selected
            )
            same_source = any(item.get("source") == prev.get("source") for prev in selected)
            return float(item.get("score") or 0) - 0.015 * similarity - (0.01 if same_source else 0)
        best = max(range(len(remaining)), key=lambda i: (utility(remaining[i]), -i))
        selected.append(remaining.pop(best))
    return selected


def reciprocal_rank_fusion(
    rankings: Iterable[Iterable[dict[str, Any]]], *, k: int = RRF_K, key_field: str = "chunk_id"
) -> list[dict[str, Any]]:
    """Fuse independently-ranked candidates without assuming comparable scores.

    ``key_field`` is normally ``chunk_id``.  A caller combining an old and a
    new index can use ``source`` to de-duplicate the same document represented
    under two different chunk identifiers.
    """
    if k < 0:
        raise ValueError("RRF k must be non-negative")
    fused: dict[str, dict[str, Any]] = {}
    for ranking_index, ranking in enumerate(rankings):
        seen: set[str] = set()
        for rank, item in enumerate(ranking, start=1):
            identity = str(item.get(key_field, ""))
            if not identity or identity in seen:
                continue
            seen.add(identity)
            if identity not in fused:
                fused[identity] = {**item, "score": 0.0, "rank_contributions": []}
            target = fused[identity]
            target["score"] += 1.0 / (k + rank)
            target["rank_contributions"].append({
                "ranking": ranking_index, "rank": rank, "raw_score": item.get("score"),
            })
    return sorted(fused.values(), key=lambda item: float(item.get("score", 0.0)), reverse=True)


class EnterpriseRetriever:
    """Best-effort hybrid retriever; failures deliberately fall back to V1 RAG."""

    @property
    def available(self) -> bool:
        return DATABASE_URL.startswith("postgresql") and get_embedding_provider().available

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(f"{value:.10g}" for value in vector) + "]"

    @staticmethod
    def _normalise(row: dict[str, Any]) -> dict[str, Any]:
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        source = str(row.get("storage_key") or row.get("filename") or "教师上传资料")
        return {
            "chunk_id": str(row["chunk_id"]),
            "content": str(row["content"]),
            "source": source,
            "course": str(row["course"]),
            "title_hint": str(row.get("filename") or source),
            "metadata": metadata,
            "score": float(row.get("score") or 0.0),
            "retriever": "pgvector_hybrid_rrf",
        }

    def _chinese_candidates(self, *, query: str, course_id: str,
                            embedding_model: str, limit: int) -> list[dict[str, Any]]:
        grams = chinese_search_grams(query)
        if not grams:
            return []
        sql = text("""
            WITH terms AS (
              SELECT value AS gram FROM jsonb_array_elements_text(CAST(:grams AS jsonb))
            ), scored AS (
              SELECT dc.id AS chunk_id, dc.content, dc.metadata, kd.course,
                     kd.filename, kd.storage_key,
                     (SELECT COALESCE(SUM(length(gram) * length(gram)), 0)
                      FROM terms WHERE strpos(dc.content, gram) > 0) AS score
              FROM document_chunks AS dc
              JOIN document_versions AS dv ON dv.id = dc.document_version_id
              JOIN knowledge_documents AS kd ON kd.id = dv.document_id
              WHERE kd.course = :course_id
                AND kd.status = 'indexed' AND dv.status = 'indexed'
                AND dv.version = (SELECT MAX(newer.version) FROM document_versions AS newer
                                  WHERE newer.document_id = kd.id AND newer.status = 'indexed')
                AND dv.metadata -> 'embedding' ->> 'model' = :embedding_model
                AND dc.embedding IS NOT NULL
            ), ranked AS (
              SELECT *, row_number() OVER (PARTITION BY storage_key ORDER BY score DESC) AS source_rank
              FROM scored WHERE score > 0
            )
            SELECT chunk_id, content, metadata, course, filename, storage_key, score
            FROM ranked WHERE source_rank = 1 ORDER BY score DESC LIMIT :limit
        """)
        with SessionLocal() as session:
            return [self._normalise(dict(row)) for row in session.execute(sql, {
                "grams": json.dumps(grams, ensure_ascii=False),
                "course_id": course_id,
                "embedding_model": embedding_model,
                "limit": limit,
            }).mappings()]

    def retrieve(self, query: str, *, course_id: str, top_k: int = 5,
                 strategy: str = "hybrid") -> list[dict[str, Any]]:
        if strategy not in RETRIEVAL_STRATEGIES:
            raise ValueError("unsupported_retrieval_strategy")
        if not query.strip() or not self.available:
            return []
        try:
            provider = get_embedding_provider()
            vector = (provider.embed_query(query) if hasattr(provider, "embed_query")
                      else provider.embed_documents([query])[0])
        except (EmbeddingProviderError, IndexError) as exc:
            LOGGER.warning("[enterprise-rag] query embedding unavailable: %s", exc)
            return []

        candidate_limit = max(top_k * 4, 10)
        params = {
            "course_id": course_id,
            "embedding": self._vector_literal(vector),
            "embedding_model": get_embedding_provider().model,
            "query": query,
            "limit": candidate_limit,
        }
        dense_sql = text(
            """
            SELECT dc.id AS chunk_id, dc.content, dc.metadata, kd.course,
                   kd.filename, kd.storage_key,
                   1 - (dc.embedding <=> CAST(:embedding AS vector)) AS score
            FROM document_chunks AS dc
            JOIN document_versions AS dv ON dv.id = dc.document_version_id
            JOIN knowledge_documents AS kd ON kd.id = dv.document_id
            WHERE kd.course = :course_id
              AND kd.status = 'indexed'
              AND dv.status = 'indexed'
              AND dv.version = (SELECT MAX(newer.version) FROM document_versions AS newer
                                WHERE newer.document_id = kd.id AND newer.status = 'indexed')
              AND dv.metadata -> 'embedding' ->> 'model' = :embedding_model
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        )
        lexical_sql = text(
            """
            SELECT dc.id AS chunk_id, dc.content, dc.metadata, kd.course,
                   kd.filename, kd.storage_key,
                   ts_rank_cd(
                     to_tsvector('simple', dc.content),
                     websearch_to_tsquery('simple', :query)
                   ) AS score
            FROM document_chunks AS dc
            JOIN document_versions AS dv ON dv.id = dc.document_version_id
            JOIN knowledge_documents AS kd ON kd.id = dv.document_id
            WHERE kd.course = :course_id
              AND kd.status = 'indexed'
              AND dv.status = 'indexed'
              AND dv.version = (SELECT MAX(newer.version) FROM document_versions AS newer
                                WHERE newer.document_id = kd.id AND newer.status = 'indexed')
              AND to_tsvector('simple', dc.content)
                  @@ websearch_to_tsquery('simple', :query)
            ORDER BY score DESC
            LIMIT :limit
            """
        )
        try:
            with SessionLocal() as session:
                dense = [self._normalise(dict(row)) for row in session.execute(dense_sql, params).mappings()]
                lexical = ([self._normalise(dict(row)) for row in session.execute(lexical_sql, params).mappings()]
                           if strategy != "dense" else [])
        except Exception as exc:  # Database availability must not break V1 RAG.
            LOGGER.warning("[enterprise-rag] PostgreSQL retrieval unavailable: %s", exc)
            return []
        if strategy == "dense":
            return dense[:top_k]
        fused = reciprocal_rank_fusion([dense, lexical])
        if strategy == "hybrid_diverse":
            selected = diversify_candidates(fused, top_k)
        else:
            selected = fused[:top_k]
        if not lexical and chinese_search_grams(query):
            try:
                candidates = self._chinese_candidates(
                    query=query, course_id=course_id,
                    embedding_model=params["embedding_model"], limit=max(top_k * 4, 10),
                )
                rescue = confident_chinese_candidate(candidates)
                if rescue:
                    remaining = [item for item in selected if item["source"] != rescue["source"]]
                    return [{**rescue, "lexical_rescue": True}, *remaining[:top_k - 1]]
            except Exception as exc:  # Lexical fallback cannot block dense retrieval.
                LOGGER.warning("[enterprise-rag] Chinese lexical fallback unavailable: %s", exc)
        return selected


_enterprise_retriever: EnterpriseRetriever | None = None


def get_enterprise_retriever() -> EnterpriseRetriever:
    global _enterprise_retriever
    if _enterprise_retriever is None:
        _enterprise_retriever = EnterpriseRetriever()
    return _enterprise_retriever
