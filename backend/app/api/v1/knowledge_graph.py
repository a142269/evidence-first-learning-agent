"""
知识图谱 API - B owns /api/v1/knowledge-graph/*
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])

_kg_store = None
_graph_retriever = None

try:
    from backend.app.services.knowledge_graph.store import get_kg_store
    from backend.app.services.knowledge_graph.retriever import get_graph_retriever
    _kg_store = get_kg_store()
    _graph_retriever = get_graph_retriever()
except ImportError:
    logger.warning("[knowledge-graph] KG service not available")


def _kp_dict(kp) -> dict[str, Any]:
    # bloom_level 不是 ORM 列，存放在 metadata JSON 中
    meta = getattr(kp, "metadata_data", None) or {}
    return {"id": kp.id, "name": kp.name, "course": kp.course,
            "description": kp.description,
            "bloom_level": meta.get("bloom_level", "")}


@router.get("/kps")
def list_kps(course: str = Query(default="")):
    if _kg_store is None:
        return {"kps": [], "total": 0, "note": "KG service not available"}
    kps = _kg_store.list_kps(course=course) if course else _kg_store.list_kps()
    return {"kps": [_kp_dict(kp) for kp in kps], "total": len(kps)}


@router.get("/kps/{kp_id}")
def get_kp(kp_id: str):
    if _kg_store is None:
        return {"error": "KG service not available"}
    kp = _kg_store.get_kp(kp_id)
    if not kp:
        return {"error": "not_found"}
    return {"kp": _kp_dict(kp),
            "neighbors": _kg_store.get_neighbors(kp_id)}


@router.get("/lookup")
def lookup_kp(name: str = Query(default=""), course: str = Query(default="")):
    if _kg_store is None:
        return {"results": [], "total": 0, "note": "KG service not available"}
    results = _kg_store.find_by_name(name, course)
    return {"results": [_kp_dict(kp) for kp in results], "total": len(results)}


@router.get("/search")
def graph_search(q: str = Query(default=""), course: str = Query(default=""),
                 mode: str = Query(default="hybrid"), top_k: int = Query(default=5, ge=1, le=20)):
    if _graph_retriever is None:
        return {"query": q, "results": [], "total": 0, "note": "GraphRAG not available"}
    results = _graph_retriever.retrieve(q, top_k=top_k, course=course, mode=mode)
    payload = []
    for r in results:
        kp_ids = r.get("kp_ids") or []
        primary_kp = kp_ids[0] if kp_ids else ""
        # 命中的知识点节点补充课程/Bloom 元信息，让前端能显示标题
        primary_name = ""
        primary_course = ""
        primary_bloom = ""
        primary_desc = ""
        if primary_kp and _kg_store is not None:
            kp_obj = _kg_store.get_kp(primary_kp)
            if kp_obj is not None:
                primary_name = getattr(kp_obj, "name", "") or ""
                primary_course = getattr(kp_obj, "course", "") or ""
                primary_bloom = getattr(kp_obj, "bloom_level", "") or ""
                primary_desc = getattr(kp_obj, "description", "") or ""
        raw_content = r.get("content", "") or ""
        title = r.get("title_hint") or primary_name or primary_kp or (raw_content[:24] + "…" if len(raw_content) > 24 else raw_content) or "召回片段"
        description = primary_desc or (raw_content[:160] + ("…" if len(raw_content) > 160 else ""))
        payload.append({
            "id": primary_kp or r.get("source", ""),
            "kp_id": primary_kp,
            "name": title,
            "title_hint": r.get("title_hint", ""),
            "description": description,
            "content": raw_content[:500],
            "source": r.get("source", ""),
            "score": r.get("score", 0),
            "course": primary_course,
            "bloom_level": primary_bloom,
            "kp_ids": kp_ids,
        })
    return {"query": q, "mode": mode, "results": payload, "total": len(payload)}


@router.get("/stats")
def kg_stats():
    if _graph_retriever is None:
        return {"kp_count": 0, "relation_count": 0, "note": "KG service not available"}
    return _graph_retriever.stats()


@router.get("/3d")
def get_3d_graph(
    user_id: str = Query(..., description="学生 ID"),
    course: str = Query(default="artificial_intelligence"),
    max_nodes: int = Query(80, le=200),
):
    """3D 知识图谱数据 — 供前端 Three.js 力导向图渲染

    nodes: id / name / mastery / bloom_level / bloom_color / size_hint
    edges: source / target / relation / weight
    stats: total / mastered / in_progress / untouched
    """
    if _kg_store is None:
        return {"nodes": [], "edges": [], "stats": {}, "note": "KG not available"}

    kps = _kg_store.list_kps(course=course)[:max_nodes]
    kp_ids = [kp.id for kp in kps]
    rels = []
    for kp_id in kp_ids:
        rels.extend(_kg_store.list_relations(kp_id=kp_id))

    # BKT mastery + 趋势 + 答题次数
    masteries: dict[str, float] = {}
    bkt_trends: dict[str, str] = {}
    bkt_attempts: dict[str, int] = {}
    try:
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt
        bkt = get_bkt()
        masteries = bkt.get_all_masteries(user_id)
        # Plan D · 3.4 — 每个 KP 取趋势 + 答题次数（轻量计算）
        for kp_id in kp_ids:
            try:
                bkt_trends[kp_id] = bkt.trend(user_id, kp_id)
                history = bkt.get_history(user_id, kp_id)
                bkt_attempts[kp_id] = len(history)
            except Exception:
                bkt_trends[kp_id] = "stable"
                bkt_attempts[kp_id] = 0
    except Exception:
        pass

    # Bloom colors
    try:
        from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BLOOM_COLORS
    except ImportError:
        BLOOM_COLORS = {"remember": "#94a3b8", "understand": "#60a5fa", "apply": "#34d399",
                        "analyze": "#fbbf24", "evaluate": "#fb923c", "create": "#f87171"}

    nodes = []
    for kp in kps:
        mastery = masteries.get(kp.id, 0.0)
        # bloom_level 存在 metadata_data 字段里（KnowledgePointRecord 无独立列）
        meta = (kp.metadata_data or {}) if hasattr(kp, "metadata_data") else {}
        bloom = (getattr(kp, "bloom_level", None) or meta.get("bloom_level")
                 or meta.get("bloom") or "understand")
        nodes.append({
            "id": kp.id,
            "name": kp.name,
            "mastery": round(mastery, 3),
            "bloom_level": bloom,
            "bloom_color": BLOOM_COLORS.get(bloom, "#94a3b8"),
            "size_hint": 8 + int(mastery * 20),
            "course": kp.course,
            # Plan D · 3.4 — BKT mastery hover 用
            "bkt_trend": bkt_trends.get(kp.id, "stable"),
            "bkt_attempts": bkt_attempts.get(kp.id, 0),
        })

    edges = [
        {"source": r.source_id, "target": r.target_id,
         "relation": r.relation_type, "weight": r.weight}
        for r in rels
    ]

    mastered = sum(1 for n in nodes if n["mastery"] >= 0.8)
    in_progress = sum(1 for n in nodes if 0.3 <= n["mastery"] < 0.8)
    untouched = sum(1 for n in nodes if n["mastery"] < 0.3)

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_kps": len(nodes),
            "mastered_kps": mastered,
            "in_progress_kps": in_progress,
            "untouched_kps": untouched,
        },
    }


@router.get("/neighbors")
def get_neighbors(
    kp: str = Query(..., description="知识点 ID 或名称"),
    depth: int = Query(2, ge=1, le=4, description="BFS 扩展深度"),
    direction: str = Query("prereq", description="关系方向：prereq / postreq / both"),
    course: str = Query(default=""),
):
    """KG 引导推荐：根据当前 KP 推荐相邻节点。

    用法：学生学完 cnn 后系统主动推荐 rnn / transformer。
    """
    if _kg_store is None:
        return {"error": "KG service not available"}

    # 若传入的是名称，先解析为 ID
    kp_id = kp
    if not _kg_store.get_kp(kp_id):
        results = _kg_store.find_by_name(kp_id, course=course)
        if results:
            kp_id = results[0].id
        else:
            return {"error": "kp_not_found", "kp": kp}

    # 方向映射
    dir_map = {"prereq": "out", "postreq": "in", "both": "both"}
    store_dir = dir_map.get(direction, "both")

    subgraph = _kg_store.get_subgraph([kp_id], hops=depth)
    nodes = []
    for nid, row in subgraph["nodes"].items():
        if nid == kp_id:
            continue
        meta = row.metadata_data or {} if hasattr(row, "metadata_data") else {}
        bloom = meta.get("bloom_level", "understand")
        nodes.append({
            "id": nid,
            "name": row.name,
            "course": row.course,
            "bloom_level": bloom,
            "relation_path": [
                {"source": s, "target": t, "relation": r, "weight": w}
                for s, t, r, w in subgraph["edges"]
                if s == kp_id and t == nid or s == nid and t == kp_id
            ],
        })

    # 按与中心节点的关系权重排序（取第一条边权重）
    nodes.sort(
        key=lambda n: (
            n["relation_path"][0]["weight"] if n["relation_path"] else 0
        ),
        reverse=True,
    )

    return {
        "center_kp": kp_id,
        "depth": depth,
        "direction": direction,
        "recommended": nodes,
        "total": len(nodes),
    }
