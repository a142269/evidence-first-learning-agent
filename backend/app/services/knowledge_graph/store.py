"""
知识图谱持久化层 —— B 拥有

提供知识点实体（KnowledgePointRecord）和关系（KnowledgeRelationRecord）的 CRUD。
GraphRAG builder 和 retriever 通过本模块读写数据库。
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any, Callable, List, Optional

from backend.app.core import database
from backend.app.core.models import KnowledgePointRecord, KnowledgeRelationRecord


class KnowledgeGraphStore:
    """知识点图谱的数据库读写封装"""

    def __init__(self, session_factory: Callable | None = None):
        self.session_factory = session_factory

    def _session(self):
        factory = self.session_factory or database.SessionLocal
        return factory()

    # ── 知识点 ──────────────────────────────────────────

    def upsert_kp(self, kp_id: str, name: str, course: str = "",
                  description: str = "", bloom_level: str = "",
                  metadata: dict | None = None) -> KnowledgePointRecord:
        with self._session() as db:
            try:
                row = db.get(KnowledgePointRecord, kp_id)
                if row is None:
                    row = KnowledgePointRecord(id=kp_id)
                    db.add(row)
                row.name = name
                row.course = course
                row.description = description
                row.bloom_level = bloom_level
                row.metadata_data = deepcopy(metadata or {})
                db.commit()
                db.refresh(row)
                return row
            except Exception:
                db.rollback()
                raise

    def get_kp(self, kp_id: str) -> Optional[KnowledgePointRecord]:
        with self._session() as db:
            return db.get(KnowledgePointRecord, kp_id)

    def find_by_name(self, name: str, course: str = "") -> List[KnowledgePointRecord]:
        with self._session() as db:
            q = db.query(KnowledgePointRecord).filter(KnowledgePointRecord.name == name)
            if course:
                q = q.filter(KnowledgePointRecord.course == course)
            return q.all()

    def list_kps(self, course: str = "") -> List[KnowledgePointRecord]:
        with self._session() as db:
            q = db.query(KnowledgePointRecord)
            if course:
                q = q.filter(KnowledgePointRecord.course == course)
            return q.all()

    def kp_count(self) -> int:
        with self._session() as db:
            return db.query(KnowledgePointRecord).count()

    # ── 关系 ────────────────────────────────────────────

    def add_relation(self, source_id: str, target_id: str,
                     relation_type: str, weight: float = 1.0) -> KnowledgeRelationRecord:
        with self._session() as db:
            try:
                # 幂等：已有同类型关系则跳过
                existing = (
                    db.query(KnowledgeRelationRecord)
                    .filter(
                        KnowledgeRelationRecord.source_id == source_id,
                        KnowledgeRelationRecord.target_id == target_id,
                        KnowledgeRelationRecord.relation_type == relation_type,
                    )
                    .one_or_none()
                )
                if existing:
                    return existing
                row = KnowledgeRelationRecord(
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=relation_type,
                    weight=weight,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return row
            except Exception:
                db.rollback()
                raise

    def list_relations(self, kp_id: str = "", relation_type: str = "") -> List[KnowledgeRelationRecord]:
        with self._session() as db:
            q = db.query(KnowledgeRelationRecord)
            if kp_id:
                q = q.filter(
                    (KnowledgeRelationRecord.source_id == kp_id)
                    | (KnowledgeRelationRecord.target_id == kp_id)
                )
            if relation_type:
                q = q.filter(KnowledgeRelationRecord.relation_type == relation_type)
            return q.all()

    def relation_count(self) -> int:
        with self._session() as db:
            return db.query(KnowledgeRelationRecord).count()

    # ── 邻接查询（供 GraphRAG retriever 用）────────────

    def get_neighbors(self, kp_id: str, direction: str = "both") -> List[dict]:
        """获取某知识点的邻居（含关系类型和权重）。

        direction: "out" / "in" / "both"
        返回 [{"kp_id": ..., "relation_type": ..., "weight": ...}, ...]
        """
        with self._session() as db:
            neighbors: List[dict] = []
            if direction in ("out", "both"):
                out_rels = (
                    db.query(KnowledgeRelationRecord)
                    .filter(KnowledgeRelationRecord.source_id == kp_id)
                    .all()
                )
                for rel in out_rels:
                    neighbors.append({
                        "kp_id": rel.target_id,
                        "relation_type": rel.relation_type,
                        "weight": rel.weight,
                        "direction": "out",
                    })
            if direction in ("in", "both"):
                in_rels = (
                    db.query(KnowledgeRelationRecord)
                    .filter(KnowledgeRelationRecord.target_id == kp_id)
                    .all()
                )
                for rel in in_rels:
                    neighbors.append({
                        "kp_id": rel.source_id,
                        "relation_type": rel.relation_type,
                        "weight": rel.weight,
                        "direction": "in",
                    })
            return neighbors

    def get_subgraph(self, seed_kp_ids: List[str], hops: int = 2) -> dict:
        """BFS 扩展获取子图。

        返回 {"nodes": {kp_id: row}, "edges": [(src, tgt, type, weight), ...]}
        """
        visited: set = set()
        edges: List[tuple] = []
        frontier = set(seed_kp_ids)

        for _ in range(hops):
            next_frontier: set = set()
            for kp_id in frontier:
                if kp_id in visited:
                    continue
                visited.add(kp_id)
                neighbors = self.get_neighbors(kp_id, direction="both")
                for nb in neighbors:
                    nid = nb["kp_id"]
                    edges.append((kp_id, nid, nb["relation_type"], nb["weight"]))
                    if nid not in visited:
                        next_frontier.add(nid)
            frontier = next_frontier
            if not frontier:
                break

        visited.update(frontier)
        nodes: dict = {}
        for nid in visited:
            row = self.get_kp(nid)
            if row:
                nodes[nid] = row
        return {"nodes": nodes, "edges": edges}


# 模块级单例
_store: Optional[KnowledgeGraphStore] = None


def get_kg_store() -> KnowledgeGraphStore:
    global _store
    if _store is None:
        _store = KnowledgeGraphStore()
    return _store
