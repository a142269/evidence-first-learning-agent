"""
GraphRAG retriever with graph, TF-IDF, hybrid, and RAG-Fusion modes.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import OperationalError

from backend.app.services.knowledge_graph.store import KnowledgeGraphStore, get_kg_store
from backend.app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


class GraphRetriever:
    """Graph-enhanced retrieval over the knowledge graph and RAG chunks."""

    def __init__(
        self,
        kg_store: Optional[KnowledgeGraphStore] = None,
        rag_service=None,
    ):
        self.kg = kg_store or get_kg_store()
        self.rag = rag_service or get_rag_service()

    def _match_entities(self, query: str, course: str = "") -> List[str]:
        """Return the most likely knowledge-point ids mentioned by the query."""
        matched: List[tuple[int, str]] = []
        query_lower = query.lower()

        try:
            knowledge_points = self.kg.list_kps(course=course)
        except OperationalError as exc:
            logger.warning("[GraphRAG] knowledge graph schema unavailable: %s", exc)
            return []

        for kp in knowledge_points:
            name = kp.name.lower()
            score = 0
            if name == query_lower:
                score = 100
            elif name in query_lower:
                score = 80
            elif query_lower in name:
                score = 60
            else:
                overlap = len(set(name) & set(query_lower))
                score = min(overlap * 2, 30)
            if score >= 20:
                matched.append((score, kp.id))

        matched.sort(key=lambda item: item[0], reverse=True)
        return [kp_id for _, kp_id in matched[:5]]

    def _collect_graph_chunks(
        self,
        node_names: List[str],
        seed_ids: List[str],
        subgraph: Dict[str, Any],
        course: str,
    ) -> Dict[str, Dict[str, Any]]:
        graph_chunks: Dict[str, Dict[str, Any]] = {}

        for name in node_names[:10]:
            tfidf_results = self.rag.retrieve(name, top_k=2, course_filter=course)
            for chunk in tfidf_results:
                cid = chunk.get("chunk_id", chunk.get("source", ""))
                if not cid or cid in graph_chunks:
                    continue
                graph_score = 0.4
                if any(seed_name in name for seed_name in node_names[: len(seed_ids)]):
                    graph_score = 1.0
                graph_chunks[cid] = {
                    **chunk,
                    "graph_score": graph_score,
                    "kp_ids": list(subgraph["nodes"].keys()),
                    "relation_paths": [
                        {"source": source, "target": target, "type": relation}
                        for source, target, relation, _ in subgraph["edges"][:10]
                    ],
                }

        return graph_chunks

    def _reciprocal_rank_fuse(
        self,
        ranked_lists: List[tuple[str, List[Dict[str, Any]]]],
        graph_chunks: Dict[str, Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        fused: Dict[str, Dict[str, Any]] = {}
        rrf_k = 60.0

        for label, chunks in ranked_lists:
            for rank, chunk in enumerate(chunks, start=1):
                cid = chunk.get("chunk_id", chunk.get("source", ""))
                if not cid:
                    continue
                entry = fused.setdefault(
                    cid,
                    {
                        **chunk,
                        "graph_score": graph_chunks.get(cid, {}).get("graph_score", 0.0),
                        "rag_fusion_score": 0.0,
                        "rag_fusion_ranks": [],
                    },
                )
                entry["rag_fusion_score"] += 1.0 / (rrf_k + rank)
                entry["rag_fusion_ranks"].append(f"{label}#{rank}")
                if cid in graph_chunks:
                    entry["kp_ids"] = graph_chunks[cid].get("kp_ids", [])
                    entry["relation_paths"] = graph_chunks[cid].get("relation_paths", [])

        results = sorted(
            fused.values(),
            key=lambda item: (
                item.get("rag_fusion_score", 0.0),
                item.get("graph_score", 0.0),
                item.get("score", 0.0),
            ),
            reverse=True,
        )[:top_k]
        for item in results:
            item["score"] = item.get("rag_fusion_score", 0.0)
        return results

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        course: str = "",
        mode: str = "hybrid",
    ) -> List[Dict[str, Any]]:
        """Retrieve ranked chunks for a query.

        Modes:
        - `tfidf`: plain RAG retrieval
        - `graph`: graph-only ranking
        - `hybrid`: weighted graph + TF-IDF scoring
        - `rag_fusion`: reciprocal-rank fusion over query and graph entity expansions
        """
        if mode == "tfidf":
            return self.rag.retrieve(query, top_k=top_k, course_filter=course)

        seed_ids = self._match_entities(query, course=course)
        if not seed_ids:
            logger.debug("[GraphRAG] no entity hit, fallback to TF-IDF")
            return self.rag.retrieve(query, top_k=top_k, course_filter=course)

        subgraph = self.kg.get_subgraph(seed_ids, hops=2)
        if not subgraph["nodes"]:
            return self.rag.retrieve(query, top_k=top_k, course_filter=course)

        node_names = [node.name for node in subgraph["nodes"].values()]
        graph_chunks = self._collect_graph_chunks(
            node_names=node_names,
            seed_ids=seed_ids,
            subgraph=subgraph,
            course=course,
        )

        if mode == "graph":
            results = sorted(
                graph_chunks.values(),
                key=lambda item: (item["graph_score"], item.get("score", 0.0)),
                reverse=True,
            )[:top_k]
            for item in results:
                item["score"] = item["graph_score"]
            return results

        if mode == "rag_fusion":
            ranked_lists: List[tuple[str, List[Dict[str, Any]]]] = [
                (
                    f"query:{query}",
                    self.rag.retrieve(query, top_k=top_k * 2, course_filter=course),
                )
            ]
            for name in node_names[: min(len(node_names), 4)]:
                ranked_lists.append(
                    (
                        f"entity:{name}",
                        self.rag.retrieve(name, top_k=top_k * 2, course_filter=course),
                    )
                )

            results = self._reciprocal_rank_fuse(
                ranked_lists=ranked_lists,
                graph_chunks=graph_chunks,
                top_k=top_k,
            )
            if results:
                return results
            return self.rag.retrieve(query, top_k=top_k, course_filter=course)

        tfidf_only = self.rag.retrieve(query, top_k=top_k * 2, course_filter=course)
        merged: Dict[str, Dict[str, Any]] = {}

        for chunk in tfidf_only:
            cid = chunk.get("chunk_id", chunk.get("source", ""))
            if not cid:
                continue
            tfidf_score = chunk.get("score", 0.0)
            graph_score = graph_chunks.get(cid, {}).get("graph_score", 0.0)
            merged[cid] = {
                **chunk,
                "graph_score": graph_score,
                "hybrid_score": 0.6 * graph_score + 0.4 * tfidf_score,
            }
            if cid in graph_chunks:
                merged[cid]["kp_ids"] = graph_chunks[cid].get("kp_ids", [])
                merged[cid]["relation_paths"] = graph_chunks[cid].get("relation_paths", [])

        for cid, graph_chunk in graph_chunks.items():
            if cid not in merged:
                merged[cid] = {
                    **graph_chunk,
                    "hybrid_score": graph_chunk["graph_score"] * 0.6,
                }

        results = sorted(
            merged.values(),
            key=lambda item: item.get("hybrid_score", 0.0),
            reverse=True,
        )[:top_k]
        for item in results:
            item["score"] = item.get("hybrid_score", item.get("graph_score", 0.0))
        return results

    def stats(self) -> Dict[str, Any]:
        return {
            "kp_count": self.kg.kp_count(),
            "relation_count": self.kg.relation_count(),
            "rag_stats": self.rag.stats(),
        }

    def find_neighbors(
        self,
        kp_id: str,
        depth: int = 2,
        direction: str = "prereq",
        course: str = "",
    ) -> Dict[str, Any]:
        """Recommend nearby knowledge points via BFS subgraph expansion."""
        resolved_id = kp_id
        if not self.kg.get_kp(resolved_id):
            results = self.kg.find_by_name(resolved_id, course=course)
            if results:
                resolved_id = results[0].id
            else:
                return {"error": "kp_not_found", "kp": kp_id}

        subgraph = self.kg.get_subgraph([resolved_id], hops=depth)

        nodes: List[Dict[str, Any]] = []
        for nid, row in subgraph["nodes"].items():
            if nid == resolved_id:
                continue
            meta = row.metadata_data or {} if hasattr(row, "metadata_data") else {}
            bloom = meta.get("bloom_level", "understand")
            nodes.append(
                {
                    "id": nid,
                    "name": row.name,
                    "course": row.course,
                    "bloom_level": bloom,
                    "relation_path": [
                        {"source": source, "target": target, "relation": relation, "weight": weight}
                        for source, target, relation, weight in subgraph["edges"]
                        if (source == resolved_id and target == nid) or (source == nid and target == resolved_id)
                    ],
                }
            )

        nodes.sort(
            key=lambda node: node["relation_path"][0]["weight"] if node["relation_path"] else 0.0,
            reverse=True,
        )

        return {
            "center_kp": resolved_id,
            "depth": depth,
            "direction": direction,
            "recommended": nodes,
            "total": len(nodes),
        }


_retriever: Optional[GraphRetriever] = None


def get_graph_retriever() -> GraphRetriever:
    global _retriever
    if _retriever is None:
        _retriever = GraphRetriever()
    return _retriever
