"""
RAG index lifecycle manager — DB-backed persistence.

Replaces the JSON index file (`data/ads/rag/knowledge_index.json`) with two
SQLite tables (`knowledge_chunks` + `chunk_vectors`) managed via SQLAlchemy.

Design goals (v6 B-P1-2):
- Crash-safe persistence: index survives process restart without recompute.
- Incremental updates: only recompute TF-IDF vectors for chunks whose
  content_hash changed (new / modified knowledge base files).
- Same retrieval algorithm & ranking as the original `_JiebaTfidfBackend`
  so results stay compatible; only the storage substrate changes.
- Graceful degradation: if DB unavailable, callers fall back to JSON backend.

Public API mirrors the existing backend contract (build / search) so
`RAGService._init_backend` can pick it up transparently.
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete

from backend.app.core.database import SessionLocal
from backend.app.core.models import KnowledgeChunkRecord, ChunkVectorRecord
from backend.app.services.rag_service import (
    RetrievedChunk,
    _tokenize,
    _dot,
    _norm,
)

logger = logging.getLogger(__name__)


def _content_hash(text: str) -> str:
    """Stable hash of chunk text for incremental-update detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class IndexManager:
    """DB-backed TF-IDF index with incremental rebuild support.

    Lifecycle:
        build(chunks, force_rebuild=False)
            -> diff existing DB rows by content_hash
            -> insert new / update changed chunks + recompute their vectors
            -> drop orphaned vectors
        load()
            -> pull all (chunk, vector) rows into memory for fast cosine search
        search(query, top_k, course_filter)
            -> in-memory cosine ranking over loaded payload
    """

    def __init__(self):
        self._payload: Optional[Dict[str, Any]] = None  # mirroring JSON backend shape

    # ------------------------------------------------------------------
    # Build / rebuild
    # ------------------------------------------------------------------
    def build(
        self,
        chunks: List[Dict[str, Any]],
        force_rebuild: bool = False,
    ) -> Dict[str, Any]:
        """Persist chunks + TF-IDF vectors to DB.

        Args:
            chunks: list of dicts with keys chunk_id/source/course/text/title_hint.
            force_rebuild: if True, drop all existing rows first (full recompute).

        Returns:
            summary dict {chunk_count, inserted, updated, skipped, dropped}.
        """
        if force_rebuild:
            self._drop_all()

        incoming_ids = {c["chunk_id"] for c in chunks}
        inserted = updated = skipped = dropped = 0

        # 1. Load existing hashes to decide insert vs update vs skip
        existing_hashes: Dict[str, str] = {}
        existing_ids: set = set()
        with SessionLocal() as session:
            rows = session.execute(
                select(KnowledgeChunkRecord.chunk_id, KnowledgeChunkRecord.content_hash)
            ).all()
            for cid, chash in rows:
                existing_hashes[cid] = chash or ""
                existing_ids.add(cid)

        # 2. Compute global document frequency over the FULL incoming corpus
        #    (TF-IDF idf depends on total doc count, so we recompute idf weights
        #     for every chunk whenever the corpus changes).
        doc_n = max(1, len(chunks))
        vocabulary_df: Dict[str, int] = {}
        tokenized: List[Dict[str, Any]] = []
        for item in chunks:
            tokens = _tokenize(item["text"])
            for tok in set(tokens):
                vocabulary_df[tok] = vocabulary_df.get(tok, 0) + 1
            tokenized.append({**item, "_tokens": tokens})

        corpus_changed = self._corpus_changed(existing_hashes, chunks)
        if not corpus_changed and not force_rebuild:
            logger.info(
                "[RAG-DB] index up-to-date (%d chunks, all hashes match) — skip rebuild",
                len(chunks),
            )
            self._payload = None  # force lazy load on next search
            return {
                "chunk_count": len(chunks),
                "inserted": 0,
                "updated": 0,
                "skipped": len(chunks),
                "dropped": 0,
            }

        # 3. Recompute TF-IDF vectors for all chunks (idf is global)
        vector_payloads: Dict[str, Dict[str, Any]] = {}
        for item in tokenized:
            tokens = item["_tokens"]
            tf: Dict[str, float] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0.0) + 1.0
            total = sum(tf.values()) or 1.0
            for t in list(tf.keys()):
                tf[t] /= total
            vec: Dict[str, float] = {}
            for tok, tf_val in tf.items():
                df = vocabulary_df.get(tok, 1)
                idf = math.log((doc_n + 1) / (df + 1)) + 1.0
                vec[tok] = float(tf_val * idf)
            vector_payloads[item["chunk_id"]] = {
                "vector": vec,
                "norm": _norm(vec),
            }

        # 4. Upsert chunk rows, flush them, then write vector rows.
        #
        # ChunkVectorRecord has a foreign key to KnowledgeChunkRecord.  They do
        # not have an ORM relationship, so SQLAlchemy is otherwise free to batch
        # INSERTs in either order.  PostgreSQL checks the constraint immediately
        # and rejected a fresh bootstrap when the vector batch happened first.
        # The explicit flush makes the parent rows durable within this transaction
        # before any child vector is staged.
        with SessionLocal() as session:
            for item in tokenized:
                cid = item["chunk_id"]
                chash = _content_hash(item["text"])

                existing = session.get(KnowledgeChunkRecord, cid)
                if existing is None:
                    session.add(KnowledgeChunkRecord(
                        chunk_id=cid,
                        source=item.get("source", ""),
                        course=item.get("course", "general"),
                        title_hint=item.get("title_hint", "")[:256],
                        text=item.get("text", ""),
                        content_hash=chash,
                    ))
                    inserted += 1
                elif existing.content_hash != chash:
                    existing.source = item.get("source", "")
                    existing.course = item.get("course", "general")
                    existing.title_hint = item.get("title_hint", "")[:256]
                    existing.text = item.get("text", "")
                    existing.content_hash = chash
                    updated += 1
                else:
                    skipped += 1

            session.flush()

            for item in tokenized:
                cid = item["chunk_id"]
                vec_data = vector_payloads[cid]
                # vector row (upsert by chunk_id)
                vrow = session.execute(
                    select(ChunkVectorRecord).where(ChunkVectorRecord.chunk_id == cid)
                ).scalar_one_or_none()
                if vrow is None:
                    session.add(ChunkVectorRecord(
                        chunk_id=cid,
                        vector=vec_data["vector"],
                        norm=vec_data["norm"],
                        # IDF is already folded into vector weights; search
                        # never reads the corpus-wide DF snapshot.
                        doc_freq={},
                    ))
                else:
                    vrow.vector = vec_data["vector"]
                    vrow.norm = vec_data["norm"]
                    vrow.doc_freq = {}

            # 5. Drop orphaned chunks no longer in incoming corpus
            orphans = existing_ids - incoming_ids
            if orphans:
                session.execute(
                    delete(ChunkVectorRecord).where(ChunkVectorRecord.chunk_id.in_(orphans))
                )
                session.execute(
                    delete(KnowledgeChunkRecord).where(KnowledgeChunkRecord.chunk_id.in_(orphans))
                )
                dropped = len(orphans)

            session.commit()

        logger.info(
            "[RAG-DB] index built: %d chunks (inserted=%d updated=%d skipped=%d dropped=%d)",
            len(chunks), inserted, updated, skipped, dropped,
        )
        self._payload = None  # invalidate; lazy reload on next search
        return {
            "chunk_count": len(chunks),
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "dropped": dropped,
        }

    def _corpus_changed(
        self,
        existing_hashes: Dict[str, str],
        chunks: List[Dict[str, Any]],
    ) -> bool:
        if len(existing_hashes) != len(chunks):
            return True
        for item in chunks:
            cid = item["chunk_id"]
            if cid not in existing_hashes:
                return True
            if existing_hashes[cid] != _content_hash(item["text"]):
                return True
        return False

    def _drop_all(self) -> None:
        with SessionLocal() as session:
            session.execute(delete(ChunkVectorRecord))
            session.execute(delete(KnowledgeChunkRecord))
            session.commit()
        logger.info("[RAG-DB] cleared all index rows (force_rebuild)")

    # ------------------------------------------------------------------
    # Load / search
    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> Dict[str, Any]:
        if self._payload is not None:
            return self._payload
        with SessionLocal() as session:
            chunk_rows = session.execute(
                select(KnowledgeChunkRecord, ChunkVectorRecord)
                .outerjoin(ChunkVectorRecord, KnowledgeChunkRecord.chunk_id == ChunkVectorRecord.chunk_id)
            ).all()
            chunks_meta: List[Dict[str, Any]] = []
            for cr, vr in chunk_rows:
                if cr is None:
                    continue
                chunks_meta.append({
                    "chunk_id": cr.chunk_id,
                    "source": cr.source,
                    "course": cr.course,
                    "title_hint": cr.title_hint or "",
                    "text": cr.text or "",
                    "vector": (vr.vector if vr else {}) or {},
                    "norm": float(vr.norm) if vr else 0.0,
                })
        self._payload = {
            "status": "ready" if chunks_meta else "empty",
            "document_count": len({c["source"] for c in chunks_meta}),
            "chunk_count": len(chunks_meta),
            "indexed_at": "db",
            "chunks": chunks_meta,
        }
        logger.info("[RAG-DB] loaded %d chunks from DB", len(chunks_meta))
        return self._payload

    def search(
        self,
        query: str,
        top_k: int,
        course_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """Cosine TF-IDF search — mirrors `_JiebaTfidfBackend.search` exactly."""
        payload = self._ensure_loaded()
        chunks = payload.get("chunks", [])
        if not chunks:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []
        tf: Dict[str, float] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0.0) + 1.0
        total = sum(tf.values()) or 1.0
        query_vec = {k: v / total for k, v in tf.items()}
        query_norm = _norm(query_vec)
        if query_norm <= 0:
            return []

        query_token_set = set(tokens)
        scored: List[tuple[float, Dict[str, Any]]] = []
        for chunk in chunks:
            if course_filter and chunk.get("course") != course_filter:
                continue
            vector = chunk.get("vector", {})
            chunk_norm = float(chunk.get("norm", 0.0) or 0.0)
            if not isinstance(vector, dict) or chunk_norm <= 0:
                continue
            score = _dot(query_vec, vector) / (query_norm * chunk_norm)
            title = str(chunk.get("title_hint", ""))
            if title:
                overlap = len(query_token_set & set(_tokenize(title)))
                score += 0.05 * float(overlap)
            scored.append((float(score), chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        out: List[RetrievedChunk] = []
        for score, chunk in scored[:max(1, top_k)]:
            out.append(RetrievedChunk(
                content=str(chunk.get("text", "")),
                source=str(chunk.get("source", "")),
                course=str(chunk.get("course", "")),
                score=round(float(score), 6),
                chunk_id=str(chunk.get("chunk_id", "")),
                title_hint=str(chunk.get("title_hint", "")),
            ))
        return out

    # ------------------------------------------------------------------
    # Stats / introspection
    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        with SessionLocal() as session:
            total = session.execute(
                select(KnowledgeChunkRecord)
            ).scalars().all()
            courses: Dict[str, int] = {}
            sources: set = set()
            for c in total:
                courses[c.course] = courses.get(c.course, 0) + 1
                sources.add(c.source)
            vcount = session.execute(select(ChunkVectorRecord)).scalars().all()
        return {
            "backend": "sqlite_db",
            "total_chunks": len(total),
            "total_vectors": len(vcount),
            "document_count": len(sources),
            "by_course": courses,
            "status": "ready" if total else "empty",
        }

    def is_empty(self) -> bool:
        return self.stats()["total_chunks"] == 0


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------
_index_manager: Optional[IndexManager] = None


def get_index_manager() -> IndexManager:
    global _index_manager
    if _index_manager is None:
        _index_manager = IndexManager()
    return _index_manager
