"""Pedagogical Bridge: B 的 pedagogical_context dict → A 的 P1.1/P1.2 dataclass

把 B（commit 5f37b6a）提供的 `services/pedagogical_context.py` 输出
（dict 形式）适配成 A 的 P1.1 `TutoringContext` 和 P1.2 `EvidencePool`，
让 A 的两个服务能直接吃 B 的上下文，不破坏任一方接口。

设计:
    * 单向桥接（B dict → A dataclass）
    * 容错：B 任一字段缺失自动跳过
    * 一站式 `bridge_full_context(user_id, query, kp_id)` 内部串联
      B 的 get_full_pedagogical_context → A 的 4 字段 + 5 source type
    * 与 critic / cov 调用方解耦：调用方拿到 dict 即可，不需要懂 A 内部
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.app.services.claim_ledger import EvidencePool, EvidenceSource
from backend.app.services.pedagogical_safety import TutoringContext

logger = logging.getLogger(__name__)


# ================================================================
# B mistake/kt → A TutoringContext
# ================================================================
def tutoring_context_from_b(
    b_full_ctx: Dict[str, Any],
    *,
    student_question: str = "",
    student_answer: Optional[str] = None,
    correct_answer: Optional[str] = None,
) -> TutoringContext:
    """从 B 的 `get_full_pedagogical_context()` 输出构造 TutoringContext。

    `b_full_ctx` 通常含 keys: ``mistake``, ``kt``, ``evidence``（按 B 实现）。

    映射规则:
        * bloom_level    ← b_full_ctx['mistake']['top_misconception_bloom']
                           or 'mistake']['recommended_variants'][0]['bloom']（如有）
        * attribution_category ← mistake 的 top error_category（如有）
        * kp_ids         ← kt['masteries'] 的 keys
        * student_answer / correct_answer 由调用方显式传入（B context 不含具体答案）
    """
    mistake = (b_full_ctx or {}).get("mistake", {}) or {}
    kt = (b_full_ctx or {}).get("kt", {}) or {}

    # bloom_level：B 的 mistake / kt 都可能含 bloom 提示，按 mistake 优先
    bloom_level: Optional[str] = None
    for hint_key in ("top_misconception_bloom", "bloom_level", "recommended_bloom"):
        if hint_key in mistake and mistake[hint_key]:
            bloom_level = str(mistake[hint_key]).lower()
            break

    # attribution_category：取 error_categories 第一个或 top_misconception
    cat = None
    if isinstance(mistake.get("error_categories"), list) and mistake["error_categories"]:
        first = mistake["error_categories"][0]
        cat = first.get("category") if isinstance(first, dict) else str(first)
    if cat is None and mistake.get("top_misconception"):
        cat = str(mistake["top_misconception"])

    # kp_ids：从 kt masteries keys 收集
    kp_ids: list[str] = []
    masteries = kt.get("masteries", {})
    if isinstance(masteries, dict):
        kp_ids = [str(k) for k in masteries.keys()]

    return TutoringContext(
        student_question=student_question,
        student_answer=student_answer,
        correct_answer=correct_answer,
        bloom_level=bloom_level,
        attribution_category=cat,
        kp_ids=kp_ids,
    )


# ================================================================
# B evidence → A EvidencePool
# ================================================================
def evidence_pool_from_b(b_full_ctx: Dict[str, Any]) -> EvidencePool:
    """从 B 的 `get_full_pedagogical_context()` 输出构造 EvidencePool。

    映射规则（5 source type）:
        * textbook    ← evidence['rag_chunks']（含 title_hint 时优先用作 ref）
                        说明：B 的 rag_chunks 字段实际是 RAG 召回，含 source=md 路径，
                        我们把 source ∈ knowledge_base 的归 textbook，其余归 rag_chunk
        * kg          ← evidence['kg_neighbors'] + evidence.get('kg_center')
        * rag_chunk   ← evidence['rag_chunks'] 中非 textbook 的
        * mistake     ← evidence['related_mistakes']
        * history     ← evidence['learning_history']
    """
    ev = (b_full_ctx or {}).get("evidence", {}) or {}

    pool = EvidencePool()

    # textbook + rag_chunk 拆分
    for c in ev.get("rag_chunks", []) or []:
        if not isinstance(c, dict):
            continue
        source = str(c.get("source", "") or "")
        content = str(c.get("content", "") or "")
        title = str(c.get("title_hint", "") or "")
        # 教材：source 里出现 knowledge_base 或 .md 视为 textbook
        ref = source or title or "rag-unknown"
        if "knowledge_base" in source or source.endswith(".md"):
            pool.textbook.append({"ref": ref, "content": content})
        else:
            pool.rag_chunk.append({"ref": ref, "content": content})

    # kg：center + neighbors 合并；id 已含 "kp:" 前缀就不再加
    def _kp_ref(raw_id: str) -> str:
        raw_id = str(raw_id or "unknown")
        return raw_id if raw_id.startswith("kp:") else f"kp:{raw_id}"

    center = ev.get("kg_center")
    if isinstance(center, dict) and center.get("id"):
        pool.kg.append({
            "ref": _kp_ref(center["id"]),
            "content": f"{center.get('name', '')} - {center.get('description', '')}".strip(" -"),
        })
    for n in ev.get("kg_neighbors", []) or []:
        if not isinstance(n, dict):
            continue
        kp_id = n.get("kp_id") or n.get("id") or "unknown"
        rel = n.get("relation_type", "")
        pool.kg.append({
            "ref": _kp_ref(kp_id),
            "content": f"KG neighbor of relation_type={rel}, kp_id={kp_id}",
        })

    # mistake
    for m in ev.get("related_mistakes", []) or []:
        if not isinstance(m, dict):
            continue
        mid = m.get("id") or "m-unknown"
        err = m.get("error_type", "")
        q = m.get("question", "")
        pool.mistake.append({
            "ref": f"mistake_id:{mid}",
            "content": f"[{err}] {q}",
        })

    # history
    for h in ev.get("learning_history", []) or []:
        if not isinstance(h, dict):
            continue
        hid = h.get("id") or h.get("path_id") or "h-unknown"
        content = h.get("summary") or h.get("content") or str(h)
        pool.history.append({
            "ref": f"path:{hid}",
            "content": str(content)[:300],
        })

    return pool


# ================================================================
# 一站式 bridge
# ================================================================
def bridge_full_context(
    user_id: str,
    *,
    query: str = "",
    kp_id: str = "",
    student_question: str = "",
    student_answer: Optional[str] = None,
    correct_answer: Optional[str] = None,
) -> Dict[str, Any]:
    """串联 B 的 get_full_pedagogical_context + 桥接成 A 的两套上下文。

    Returns:
        {
            "tutoring_context": TutoringContext (for pedagogical_safety),
            "evidence_pool":    EvidencePool   (for claim_ledger),
            "b_raw":            原始 B dict (debug / trace 用),
        }

    容错：B 模块异常时返回空 context + 空 pool（A 服务都能跑空 context）。
    """
    b_raw: Dict[str, Any] = {}
    try:
        from backend.app.services.pedagogical_context import (
            get_full_pedagogical_context,
        )
        b_raw = get_full_pedagogical_context(user_id, query=query, kp_id=kp_id) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("[pedagogical_bridge] B context unavailable, empty fallback: %s", exc)

    tc = tutoring_context_from_b(
        b_raw,
        student_question=student_question or query,
        student_answer=student_answer,
        correct_answer=correct_answer,
    )
    pool = evidence_pool_from_b(b_raw)

    return {
        "tutoring_context": tc,
        "evidence_pool": pool,
        "b_raw": b_raw,
    }
