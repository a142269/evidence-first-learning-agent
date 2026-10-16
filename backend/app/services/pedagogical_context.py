"""
Pedagogical Safety Context Service — B 提供，供 A 的 chat/with-cov 和 critic agent 调用

Exposes mistake attribution + KT context as a unified interface for:
  - P1.1 Pedagogical Safety / Scaffolding Guard (A main, B provides context)
  - P1.2 Claim Ledger / Evidence Trail (A+B)
  - P1.3 Misconception Graph (A+B)

All methods return JSON-serializable dicts suitable for injection into AgentContext.extra.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_mistake_context(user_id: str, kp_id: str = "") -> Dict[str, Any]:
    """Return structured mistake attribution context for a student.

    Used by pedagogical safety guard to check:
      - Has the student made mistakes on this topic before?
      - What error categories persist?
      - Are there unresolved misconceptions?

    Returns:
        {"has_mistakes": bool, "error_categories": [...], "unresolved_count": int,
         "top_misconception": str, "recommended_variants": [...]}
    """
    try:
        from backend.app.api.v1.mistakes import _gather_user_records
        records = _gather_user_records(user_id)
        unresolved = [r for r in records if not r.get("resolved", False)]

        if kp_id:
            unresolved = [r for r in unresolved if r.get("kp_id") == kp_id]

        categories = {}
        for r in unresolved:
            cat = r.get("error_type", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        top_cat = max(categories, key=categories.get) if categories else ""

        return {
            "has_mistakes": len(unresolved) > 0,
            "error_categories": sorted(categories.keys()),
            "error_counts": categories,
            "unresolved_count": len(unresolved),
            "top_misconception": top_cat,
            "sample_mistakes": [
                {"question": r.get("question", "")[:120],
                 "student_answer": r.get("student_answer", "")[:120],
                 "error_type": r.get("error_type", "")}
                for r in unresolved[:3]
            ],
        }
    except Exception as exc:
        logger.warning("[pedagogical_context] mistake context failed: %s", exc)
        return {"has_mistakes": False, "error": str(exc)}


def get_kt_context(user_id: str, kp_id: str = "") -> Dict[str, Any]:
    """Return knowledge tracing context — current mastery + trend + DINA snapshot.

    Used by:
      - Pedagogical safety guard (is the student ready for this topic?)
      - Claim ledger (how confident is the mastery estimate?)
      - Misconception graph (what's the pre/post mastery delta?)

    Returns:
        {"masteries": {kp_id: p_learned}, "trends": {kp_id: trend},
         "dina_snapshot": {kp_id: {mastery, slip, guess}}}
    """
    result: Dict[str, Any] = {"masteries": {}, "trends": {}, "dina_snapshot": {}}

    # BKT mastery
    try:
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt
        bkt = get_bkt()
        if kp_id:
            result["masteries"][kp_id] = round(bkt.get_mastery(user_id, kp_id), 4)
            result["trends"][kp_id] = bkt.trend(user_id, kp_id)
        else:
            result["masteries"] = {k: round(v, 4) for k, v in bkt.get_all_masteries(user_id).items()}
            result["trends"] = {k: bkt.trend(user_id, k) for k in result["masteries"]}
    except Exception as exc:
        logger.warning("[pedagogical_context] BKT context failed: %s", exc)

    # DINA snapshot
    try:
        from backend.app.services.cognitive_diagnosis.state_repository import get_state_repo
        repo = get_state_repo()
        dina_full = repo.load_dina_snapshot(user_id)
        if kp_id and kp_id in dina_full:
            result["dina_snapshot"] = {kp_id: dina_full[kp_id]}
        else:
            result["dina_snapshot"] = dina_full
    except Exception as exc:
        logger.warning("[pedagogical_context] DINA context failed: %s", exc)

    return result


def get_evidence_context(user_id: str, query: str = "", kp_id: str = "") -> Dict[str, Any]:
    """Return evidence trail context — KG neighbors + RAG chunks + learning history.

    Used by:
      - P1.2 Claim Ledger (source type: textbook/RAG/mistake/history)
      - P1.3 Misconception Graph (KG neighbors of the wrong concept)

    Returns:
        {"kg_neighbors": [...], "rag_chunks": [...], "learning_history": [...],
         "related_mistakes": [...]}
    """
    result: Dict[str, Any] = {
        "kg_neighbors": [],
        "rag_chunks": [],
        "learning_history": [],
        "related_mistakes": [],
    }

    # KG neighbors
    if kp_id:
        try:
            from backend.app.services.knowledge_graph.store import get_kg_store
            kg = get_kg_store()
            neighbors = kg.get_neighbors(kp_id, direction="both")
            kp_row = kg.get_kp(kp_id)
            result["kg_neighbors"] = [
                {"kp_id": n["kp_id"], "relation_type": n["relation_type"],
                 "direction": n["direction"], "weight": n["weight"]}
                for n in neighbors[:10]
            ]
            if kp_row:
                result["kg_center"] = {
                    "id": kp_row.id, "name": kp_row.name,
                    "course": kp_row.course, "description": kp_row.description,
                }
        except Exception as exc:
            logger.warning("[pedagogical_context] KG context failed: %s", exc)

    # RAG chunks
    if query:
        try:
            from backend.app.services.rag_service import get_rag_service
            rag = get_rag_service()
            chunks = rag.retrieve(query, top_k=3)
            result["rag_chunks"] = [
                {"source": c.get("source", ""), "title_hint": c.get("title_hint", ""),
                 "content": c.get("content", "")[:300]}
                for c in chunks
            ]
        except Exception as exc:
            logger.warning("[pedagogical_context] RAG context failed: %s", exc)

    # Related mistakes
    try:
        from backend.app.api.v1.mistakes import _gather_user_records
        records = _gather_user_records(user_id)
        unresolved = [r for r in records if not r.get("resolved", False)]
        if kp_id:
            unresolved = [r for r in unresolved if r.get("kp_id") == kp_id]
        result["related_mistakes"] = [
            {"id": r.get("id"), "error_type": r.get("error_type", ""),
             "question": r.get("question", "")[:100]}
            for r in unresolved[:5]
        ]
    except Exception as exc:
        logger.warning("[pedagogical_context] mistake evidence failed: %s", exc)

    return result


def get_full_pedagogical_context(user_id: str, query: str = "", kp_id: str = "") -> Dict[str, Any]:
    """One-call convenience: return all pedagogical context for A's agents.

    This is the primary interface for Demo Cockpit and AgentContext.extra injection.
    """
    return {
        "mistake_context": get_mistake_context(user_id, kp_id),
        "kt_context": get_kt_context(user_id, kp_id),
        "evidence_context": get_evidence_context(user_id, query, kp_id),
    }
