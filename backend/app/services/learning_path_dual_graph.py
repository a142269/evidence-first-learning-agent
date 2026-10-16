"""Plan P1-2：双图学习路径规划

参考：KnowLP (arxiv 2506.22303) —— 先修图 + 语义相似图
设计：
  - 先修图（Prereq Graph）：从 KnowledgeGraphStore 拉所有 prerequisite 类型边，
    BFS 推导从 focus_kp 出发的所有前驱和后继，构成完整主链。
  - 语义相似图（Similarity Graph）：收集 related / extends / specialization /
    foundation / similar 类型边，构成可绕行的迁移路径。
  - 路径规划输出三种方案：
      main       — 严格按先修图主线，适配 mastery ≥ threshold 的 KP
      detour     — 用相似图绕开薄弱 KP
      remediation — 优先补齐 mastery < threshold 的卡点
  - 每一步带 explanation 字段，说明来源（prereq / similarity / mastery）。

输出格式（与 Plan P1-2 对齐）：
{
  "focus_kp": "transformer",
  "main_path":     [{kp_id, title, source: "prereq|similarity|mastery", reason, mastery}, ...],
  "detour_path":   [...],
  "remediation":   [...],
  "explanations":  [...],
  "kp_count":      N,
  "edge_count":    M
}
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


PREREQ_RELATIONS = {"prerequisite", "foundation", "foundational"}
SIMILAR_RELATIONS = {"related", "extends", "specialization", "similar", "contrast", "enables"}


@dataclass
class PathStep:
    kp_id: str
    name: str
    source: str          # prereq / similarity / mastery
    reason: str
    mastery: Optional[float] = None
    bloom: str = "Understand"
    stage_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kp_id": self.kp_id,
            "title": self.name,
            "source": self.source,
            "reason": self.reason,
            "mastery": round(self.mastery, 3) if isinstance(self.mastery, (int, float)) else None,
            "bloom": self.bloom,
            "stage_index": self.stage_index,
        }


class DualGraphPathPlanner:
    """先修图 + 语义相似图双图路径规划。"""

    def __init__(self, mastery_lookup: Optional[Any] = None):
        """
        mastery_lookup: 可选 callable(user_id) -> {kp_id: float}；
                        缺省时从 BKT/DINA 实时聚合（懒加载）。
        """
        self._mastery_lookup = mastery_lookup

    # ── 内部工具 ───────────────────────────────────────────
    def _get_kg_store(self):
        from backend.app.services.knowledge_graph.store import get_kg_store
        return get_kg_store()

    def _get_mastery(self, user_id: str) -> Dict[str, float]:
        if self._mastery_lookup is not None:
            try:
                return dict(self._mastery_lookup(user_id) or {})
            except Exception:  # noqa: BLE001
                return {}
        # 懒加载：从 BKT/DINA 平均
        try:
            from backend.app.core.database import SessionLocal
            from backend.app.core.models import BktStateRecord, DinaStateRecord
            out: Dict[str, float] = {}
            with SessionLocal() as db:
                for row in db.query(BktStateRecord).filter(BktStateRecord.user_id == user_id).all():
                    out[row.knowledge_point_id] = float(row.p_learned or 0.0)
                for row in db.query(DinaStateRecord).filter(DinaStateRecord.user_id == user_id).all():
                    cur = out.get(row.knowledge_point_id)
                    if cur is None:
                        out[row.knowledge_point_id] = float(row.mastery or 0.0)
                    else:
                        out[row.knowledge_point_id] = round((cur + float(row.mastery or 0.0)) / 2, 3)
            return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("[dual-graph] mastery fetch failed: %s", exc)
            return {}

    def _prereq_subgraph(self, store, focus_kp: str, max_hops: int = 5) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str, str, float]]]:
        """BFS 沿 prereq 关系扩展子图。"""
        visited: Set[str] = {focus_kp}
        edges: List[Tuple[str, str, str, float]] = []
        frontier: Set[str] = {focus_kp}

        for _ in range(max_hops):
            next_frontier: Set[str] = set()
            for kp_id in frontier:
                rels = store.list_relations(kp_id=kp_id, relation_type="prerequisite")
                for r in rels:
                    other = r.target_id if r.source_id == kp_id else r.source_id
                    edges.append((r.source_id, r.target_id, r.relation_type, r.weight))
                    if other not in visited:
                        visited.add(other)
                        next_frontier.add(other)
            frontier = next_frontier
            if not frontier:
                break

        nodes: List[Dict[str, Any]] = []
        for nid in visited:
            row = store.get_kp(nid)
            if row is not None:
                nodes.append({
                    "id": nid,
                    "name": row.name,
                    "course": row.course,
                    "bloom": (row.metadata_data or {}).get("bloom", "Understand"),
                })
        return nodes, edges

    def _similar_neighbors(self, store, focus_kp: str) -> List[Dict[str, Any]]:
        """拉语义相似图：related / extends / specialization / contrast / enables。"""
        out: List[Dict[str, Any]] = []
        try:
            for nb in store.get_neighbors(focus_kp, direction="both"):
                if nb["relation_type"] in SIMILAR_RELATIONS:
                    row = store.get_kp(nb["kp_id"])
                    out.append({
                        "kp_id": nb["kp_id"],
                        "name": getattr(row, "name", nb["kp_id"]) if row else nb["kp_id"],
                        "relation_type": nb["relation_type"],
                        "weight": nb["weight"],
                    })
        except Exception as exc:  # noqa: BLE001
            logger.warning("[dual-graph] similar_neighbors failed: %s", exc)
        return out

    # ── 公开方法 ───────────────────────────────────────────
    def plan(
        self,
        user_id: str,
        focus_kp: str,
        mastery_threshold: float = 0.6,
        max_steps: int = 8,
    ) -> Dict[str, Any]:
        """生成三套路径：主路径 / 绕行路径 / 卡点补救路径。"""
        store = self._get_kg_store()
        focus_row = store.get_kp(focus_kp)
        if focus_row is None:
            candidates = store.find_by_name(focus_kp)
            if not candidates:
                return {"error": "kp_not_found", "kp": focus_kp}
            focus_kp = candidates[0].id
            focus_row = candidates[0]

        mastery_map = self._get_mastery(user_id)

        # 1) 先修图（prereq）
        nodes, edges = self._prereq_subgraph(store, focus_kp)
        # 2) 语义相似图
        similar = self._similar_neighbors(store, focus_kp)

        # 主路径：按 BFS 距离（focus_kp 在前）+ mastery 排序
        # 简化：focus_kp → 它所有 prerequisite 前驱（incoming prereq）→ 再扩
        prereq_in = []
        for n in nodes:
            if n["id"] == focus_kp:
                continue
            in_rels = store.list_relations(kp_id=n["id"], relation_type="prerequisite")
            is_prereq_of_focus = any(
                r.target_id == focus_kp for r in in_rels
            )
            if is_prereq_of_focus:
                prereq_in.append(n)

        main_steps: List[PathStep] = []
        main_steps.append(PathStep(
            kp_id=focus_kp,
            name=focus_row.name,
            source="prereq",
            reason="目标 KP：作为学习路径的最终目标",
            mastery=mastery_map.get(focus_kp),
            bloom=(focus_row.metadata_data or {}).get("bloom", "Understand"),
            stage_index=0,
        ))
        for idx, n in enumerate(sorted(
            prereq_in,
            key=lambda x: mastery_map.get(x["id"], 0.5),
            reverse=True,
        )[: max_steps - 1]):
            m = mastery_map.get(n["id"])
            main_steps.append(PathStep(
                kp_id=n["id"],
                name=n["name"],
                source="prereq",
                reason=f"先修关系（图谱边：prerequisite）；mastery={m}",
                mastery=m,
                bloom=n["bloom"],
                stage_index=idx + 1,
            ))

        # 绕行路径：用语义相似图替代主路径里 mastery < threshold 的步骤
        weak_ids = {n["id"] for n in prereq_in if (mastery_map.get(n["id"], 0.5) < mastery_threshold)}
        detour_steps: List[PathStep] = [main_steps[0]]
        replaced: Set[str] = set()
        for n in prereq_in:
            if n["id"] in weak_ids:
                # 找相似替代
                alt = next((s for s in similar if s["kp_id"] not in replaced and s["kp_id"] != n["id"]), None)
                if alt is not None:
                    replaced.add(alt["kp_id"])
                    detour_steps.append(PathStep(
                        kp_id=alt["kp_id"],
                        name=alt["name"],
                        source="similarity",
                        reason=f"绕过薄弱 KP {n['id']}（mastery<{mastery_threshold}），"
                               f"用 {alt['relation_type']} 边迁移到 {alt['kp_id']}",
                        mastery=mastery_map.get(alt["kp_id"]),
                        bloom="Apply",
                        stage_index=len(detour_steps),
                    ))
                    continue
            detour_steps.append(PathStep(
                kp_id=n["id"], name=n["name"],
                source="prereq",
                reason="主线先修，未触发绕行条件",
                mastery=mastery_map.get(n["id"]),
                bloom=n["bloom"],
                stage_index=len(detour_steps),
            ))
        # 截断到 max_steps
        detour_steps = detour_steps[:max_steps]

        # 卡点补救路径：把 mastery < threshold 的 KP 提到最前，按 mastery 升序
        weak_steps: List[PathStep] = []
        weak_nodes = [n for n in prereq_in if mastery_map.get(n["id"], 0.5) < mastery_threshold]
        for n in sorted(weak_nodes, key=lambda x: mastery_map.get(x["id"], 0.5)):
            m = mastery_map.get(n["id"])
            weak_steps.append(PathStep(
                kp_id=n["id"],
                name=n["name"],
                source="mastery",
                reason=f"卡点 KP（mastery={m}<{mastery_threshold}），先补齐再前进",
                mastery=m,
                bloom=n["bloom"],
                stage_index=len(weak_steps),
            ))
        weak_steps.append(PathStep(
            kp_id=focus_kp,
            name=focus_row.name,
            source="prereq",
            reason="卡点补齐后再回到目标 KP",
            mastery=mastery_map.get(focus_kp),
            bloom=(focus_row.metadata_data or {}).get("bloom", "Understand"),
            stage_index=len(weak_steps),
        ))

        # explanations：把三条路径的差异汇总
        explanations = [
            {
                "kind": "main",
                "note": f"严格按先修图主线 {len(main_steps)} 步，目标 {focus_kp}",
                "weakness_handling": "不处理 mastery 阈值；适合基础扎实的学员",
            },
            {
                "kind": "detour",
                "note": f"绕行主线 {len(detour_steps)} 步，对 mastery<{mastery_threshold} 的 {len(replaced)} 个 KP 用相似图替代",
                "weakness_handling": f"用 related/extends/specialization 等边做语义迁移，保留整体目标",
            },
            {
                "kind": "remediation",
                "note": f"卡点补救 {len(weak_steps)} 步，先补齐 {len(weak_nodes)} 个薄弱 KP",
                "weakness_handling": f"按 mastery 升序排序，从最薄弱开始复习",
            },
        ]

        return {
            "user_id": user_id,
            "focus_kp": focus_kp,
            "focus_kp_name": focus_row.name,
            "mastery_threshold": mastery_threshold,
            "max_steps": max_steps,
            "main_path": [s.to_dict() for s in main_steps],
            "detour_path": [s.to_dict() for s in detour_steps],
            "remediation_path": [s.to_dict() for s in weak_steps],
            "explanations": explanations,
            "prereq_graph": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "nodes": nodes,
                "edges": [
                    {"source": s, "target": t, "type": rt, "weight": w}
                    for s, t, rt, w in edges
                ],
            },
            "similar_graph": {
                "neighbors": similar,
            },
            "stats": {
                "kp_count": len(nodes),
                "edge_count": len(edges),
                "similar_count": len(similar),
                "weak_kp_count": len(weak_nodes),
            },
        }


_planner: Optional[DualGraphPathPlanner] = None


def get_dual_graph_path_planner() -> DualGraphPathPlanner:
    global _planner
    if _planner is None:
        _planner = DualGraphPathPlanner()
    return _planner
