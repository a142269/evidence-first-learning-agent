# ruff: noqa: RUF001, RUF002, RUF003, B008
"""
Mistakes API — B owns /api/v1/mistakes/*

Intelligent mistake review: 8-category rule classification, structured Bloom variants,
SM-2 auto-enqueue, heatmap matrix.

CRITICAL: static routes (/categories, /heatmap) MUST be defined before
dynamic routes (/{user_id}, /{mistake_id}) to avoid FastAPI route shadowing.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Literal
import uuid

from fastapi import APIRouter, Body, HTTPException, Query

from backend.app.services.mistake_review import (
    ERROR_CATEGORIES,
    build_heatmap_matrix,
    classify_error,
    classify_with_llm,
    generate_variants,
)
from backend.app.services.variant_generator import VariantGenerator, request_from_record

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mistakes", tags=["mistakes"])
MistakeCourse = Literal["", "artificial_intelligence", "python_programming"]

# ── Storage ────────────────────────────────────────────
_mistakes: dict[str, list] = {}
_db_available = True

try:
    from backend.app.core.database import SessionLocal
    from backend.app.core.models import MistakeRecord
except ImportError:
    _db_available = False
    logger.warning("[mistakes] database unavailable, using in-memory storage")


def _fallback_course_for_kp(kp_id: str) -> str:
    normalized = kp_id.strip().lower()
    if normalized.startswith(("py_", "python_", "python/", "python_basics/")):
        return "python_programming"
    if normalized.startswith((
        "ai_", "ml_", "ml/", "ml_fundamentals/", "cnn/", "rag/",
        "transformer/", "neural_networks/", "deep_learning/",
    )):
        return "artificial_intelligence"
    return ""


def _load_course_by_kp(kp_ids: set[str]) -> dict[str, str]:
    course_by_kp = {kp_id: _fallback_course_for_kp(kp_id) for kp_id in kp_ids if kp_id}
    if not _db_available or not kp_ids:
        return course_by_kp
    try:
        from backend.app.core.models import KnowledgePointRecord

        with SessionLocal() as db:
            rows = (
                db.query(KnowledgePointRecord.id, KnowledgePointRecord.course)
                .filter(KnowledgePointRecord.id.in_(kp_ids))
                .all()
            )
        course_by_kp.update({str(kp_id): str(course or "") for kp_id, course in rows})
    except Exception as exc:
        logger.warning("[mistakes] knowledge-point course lookup failed: %s", exc)
    return course_by_kp


def _filter_records_by_course(records: list[dict], course: str = "") -> list[dict]:
    kp_ids = {str(record.get("kp_id") or "") for record in records}
    course_by_kp = _load_course_by_kp(kp_ids)
    annotated = [
        {
            **record,
            "course": course_by_kp.get(str(record.get("kp_id") or ""), ""),
        }
        for record in records
    ]
    if not course:
        return annotated
    return [record for record in annotated if record["course"] == course]


# ═══════════════════════════════════════════════════════
# Static routes FIRST (before /{dynamic} patterns)
# ═══════════════════════════════════════════════════════

@router.get("/categories")
def error_categories():
    """Get the 8 error category list."""
    return {"categories": ERROR_CATEGORIES}


@router.get("/heatmap")
def mistake_heatmap(
    user_id: str = Query(..., description="Student ID"),
    course: MistakeCourse = Query(default=""),
):
    """Mistake distribution heatmap: knowledge point × error category."""
    records = _filter_records_by_course(_gather_user_records(user_id), course)
    result = build_heatmap_matrix(records)
    result["user_id"] = user_id
    return result


@router.post("/seed")
def seed_mistakes(user_id: str = Query(..., description="Student ID to seed mistakes for")):
    """Batch import seed mistake data for a user.

    Loads 30 curated mistakes covering 8 error categories from
    data/seed_mistakes.json and persists them to DB + in-memory.
    Idempotent: skips mistakes that already exist for this user.
    """
    import json
    from pathlib import Path

    seed_path = Path(__file__).resolve().parents[4] / "data" / "seed_mistakes.json"
    if not seed_path.exists():
        raise HTTPException(status_code=404, detail="seed_mistakes.json not found")

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    all_samples = payload.get("mistakes", [])

    # Filter for this user, or use all if user not specifically in seed
    user_samples = [s for s in all_samples if s.get("user_id") == user_id]
    if not user_samples:
        # Use demo-student-1's data for any user (reuse seed data)
        user_samples = [s for s in all_samples if s.get("user_id") == "demo-student-1"]

    if not user_samples:
        raise HTTPException(status_code=404, detail="no seed data available")

    # Check existing count to avoid duplicate seeding
    existing = _gather_user_records(user_id)
    existing_questions = {r.get("question", "") for r in existing}

    imported = 0
    skipped = 0
    base_time = time.time() - 30 * 24 * 3600  # spread over last 30 days

    for i, s in enumerate(user_samples):
        question = s.get("question", "")
        if question in existing_questions:
            skipped += 1
            continue

        mistake_id = f"seed_mistake_{uuid.uuid4().hex[:10]}"
        created_at = base_time + i * 3600 * 6  # 6h apart
        error_type = s.get("error_type", "unknown")
        if error_type not in ERROR_CATEGORIES:
            error_type = "unknown"

        # Some mistakes marked as resolved (every 5th)
        resolved = (i % 5 == 4)

        # Persist to DB
        if _db_available:
            try:
                with SessionLocal() as db:
                    row = MistakeRecord(
                        id=mistake_id,
                        user_id=user_id,
                        knowledge_point_id=s.get("kp_id", ""),
                        question_data={
                            "question": question,
                            "student_answer": s.get("student_answer", ""),
                            "correct_answer": s.get("correct_answer", ""),
                        },
                        error_type=error_type,
                        analysis="",
                        created_at=created_at,
                        resolved_at=created_at if resolved else None,
                    )
                    db.add(row)
                    db.commit()
            except Exception as exc:
                logger.warning("[mistakes] seed DB persist failed for %s: %s", mistake_id, exc)

        # In-memory
        if user_id not in _mistakes:
            _mistakes[user_id] = []
        _mistakes[user_id].append({
            "id": mistake_id,
            "user_id": user_id,
            "kp_id": s.get("kp_id", ""),
            "question": question,
            "student_answer": s.get("student_answer", ""),
            "correct_answer": s.get("correct_answer", ""),
            "error_type": error_type,
            "analysis": "",
            "created_at": created_at,
            "resolved": resolved,
        })

        # Auto-enqueue in SM-2
        try:
            from backend.app.services.spaced_repetition.sm2 import get_sm2
            get_sm2().add_to_review_queue(user_id, mistake_id)
        except Exception:
            pass

        imported += 1

    logger.info("[mistakes] seeded %d mistakes for %s (skipped %d duplicates)", imported, user_id, skipped)
    return {
        "user_id": user_id,
        "imported": imported,
        "skipped": skipped,
        "total_after": len(_gather_user_records(user_id)),
    }


# ═══════════════════════════════════════════════════════
# Dynamic routes (/{user_id}, /{mistake_id}/...)
# ═══════════════════════════════════════════════════════

@router.post("/insights/{user_id}")
def mistake_insights(user_id: str, course: MistakeCourse = Query(default="")):
    """LLM 驱动的错题智能分析：总结 + 薄弱知识点 + 推荐类似题/资料 + 学习评估。

    汇总学生全部错题，调用大模型（或规则 fallback）生成结构化分析报告。
    """
    from backend.app.services.mistake_insights import generate_mistake_insights

    records = _insight_candidate_records(
        _filter_records_by_course(_gather_user_records(user_id), course)
    )
    result = generate_mistake_insights(records, user_id)
    return result


@router.get("/insights/{user_id}")
def get_mistake_insights(user_id: str, course: MistakeCourse = Query(default="")):
    """GET 版本：同 POST /insights/{user_id}，便于前端低频刷新。"""
    from backend.app.services.mistake_insights import generate_mistake_insights

    records = _insight_candidate_records(
        _filter_records_by_course(_gather_user_records(user_id), course)
    )
    result = generate_mistake_insights(records, user_id)
    return result


@router.get("/{user_id}")
def list_mistakes(
    user_id: str,
    category: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
    course: MistakeCourse = Query(default=""),
):
    """List mistakes for a user, optionally filtered by error category."""
    records = _filter_records_by_course(_gather_user_records(user_id), course)
    if category:
        records = [r for r in records if r.get("error_type") == category]
    return {"mistakes": records[:limit], "total": len(records)}


@router.post("/record")
def record_mistake(payload: dict[str, Any] = Body(...)):
    """Record a mistake and auto-enqueue it in the SM-2 review queue."""
    user_id = str(payload.get("user_id", ""))
    kp_id = str(payload.get("kp_id", ""))
    question = str(payload.get("question", ""))
    student_answer = str(payload.get("student_answer", ""))
    correct_answer = str(payload.get("correct_answer", ""))
    error_type = str(payload.get("error_type", "unknown"))

    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")

    if error_type not in ERROR_CATEGORIES:
        error_type = "unknown"

    mistake_id = f"mistake_{uuid.uuid4().hex[:10]}"
    now = time.time()

    # ── Persist to database ──
    if _db_available:
        try:
            with SessionLocal() as db:
                row = MistakeRecord(
                    id=mistake_id,
                    user_id=user_id,
                    knowledge_point_id=kp_id if kp_id else None,
                    question_data={
                        "question": question,
                        "student_answer": student_answer,
                        "correct_answer": correct_answer,
                    },
                    error_type=error_type,
                    analysis="",
                    created_at=now,
                )
                db.add(row)
                db.commit()
                logger.debug("[mistakes] persisted %s to DB", mistake_id)
        except Exception as exc:
            logger.warning("[mistakes] DB persist failed for %s: %s", mistake_id, exc)

    # ── In-memory fallback ──
    if user_id not in _mistakes:
        _mistakes[user_id] = []
    _mistakes[user_id].append({
        "id": mistake_id,
        "user_id": user_id,
        "kp_id": kp_id,
        "question": question,
        "student_answer": student_answer,
        "correct_answer": correct_answer,
        "error_type": error_type,
        "analysis": "",
        "created_at": now,
        "resolved": False,
    })

    # ── Auto-enqueue in SM-2 review queue ──
    try:
        from backend.app.services.spaced_repetition.sm2 import get_sm2
        get_sm2().add_to_review_queue(user_id, mistake_id)
        logger.debug("[mistakes] enqueued %s in SM-2", mistake_id)
    except Exception as exc:
        logger.warning("[mistakes] SM-2 enqueue failed for %s: %s", mistake_id, exc)

    return {"mistake_id": mistake_id, "status": "recorded", "in_review_queue": True}


def _build_llm_call(max_tokens: int = 300, temperature: float = 0.2):
    """Shared LLM callable for analyze / variants / remediation.

    Returns None when LLM unavailable → services fall back to rule/template,
    否则归因和变式会退化成千篇一律的模板输出（"输出死板"问题根源）。
    """
    try:
        from backend.app.core.llm_client import LLMClient
        _client = LLMClient()

        def _llm_call(system: str, user: str) -> str:
            return _client.chat(
                [{"role": "system", "content": system},
                 {"role": "user", "content": user}],
                temperature=temperature, max_tokens=max_tokens,
            )
        return _llm_call
    except Exception as exc:
        logger.info("[mistakes] LLM unavailable, rule-only: %s", exc)
        return None


@router.post("/{mistake_id}/analyze")
def analyze_mistake(mistake_id: str):
    """Run mistake classification (8 categories) with LLM enhancement and persist result.

    Uses classify_with_llm() which runs rule-based classification first,
    then asks LLM to override when rule confidence < 0.80.
    The LLM receives the full question + student answer + correct answer,
    so it can produce nuanced, per-mistake attributions instead of
    always hitting the same "short answer" rule.
    """
    record = _find_mistake(mistake_id)
    if not record:
        raise HTTPException(status_code=404, detail="mistake not found")

    question = record.get("question", "")
    student_answer = record.get("student_answer", "")
    correct_answer = record.get("correct_answer", "")

    llm_call = _build_llm_call()

    analysis = classify_with_llm(
        student_answer=student_answer,
        correct_answer=correct_answer,
        question=question,
        llm_call=llm_call,
    )

    # Persist
    _update_mistake(mistake_id, error_type=analysis["error_type"], analysis=analysis["detail"])

    return {"mistake_id": mistake_id, "analysis": analysis}


@router.post("/{mistake_id}/variants")
def make_variants(mistake_id: str):
    """Generate 3 Bloom-leveled variant questions with answers and explanations."""
    record = _find_mistake(mistake_id)
    if not record:
        raise HTTPException(status_code=404, detail="mistake not found")

    # 传入 llm_call：变式由大模型针对本题实际生成（Bloom 分层），
    # LLM 不可用时才回退规则模板
    variants = generate_variants(
        question=record.get("question", ""),
        correct_answer=record.get("correct_answer", ""),
        kp_id=record.get("kp_id", ""),
        kp_name="",
        count=3,
        llm_call=_build_llm_call(max_tokens=1200, temperature=0.6),
    )

    return {"mistake_id": mistake_id, "variants": variants}


@router.post("/{mistake_id}/remediation")
def remediate_mistake(
    mistake_id: str,
    count: int = Query(default=3, ge=1, le=5),
):
    """Generate attribution + mastery-aware variant recommendation for one mistake."""
    record = _find_mistake(mistake_id)
    if not record:
        raise HTTPException(status_code=404, detail="mistake not found")

    package = VariantGenerator().generate(
        request_from_record(record, count=count),
        llm_call=_build_llm_call(max_tokens=1200, temperature=0.5),
    )
    _update_mistake(
        mistake_id,
        error_type=package["attribution"]["error_type"],
        analysis=package["attribution"]["detail"],
    )
    return package


@router.post("/{mistake_id}/resolve")
def resolve_mistake(mistake_id: str):
    """Mark a mistake as resolved (student has mastered the concept)."""
    record = _find_mistake(mistake_id)
    if not record:
        raise HTTPException(status_code=404, detail="mistake not found")

    now = time.time()
    if _db_available:
        try:
            with SessionLocal() as db:
                row = db.get(MistakeRecord, mistake_id)
                if row:
                    row.resolved_at = now
                    db.commit()
                    logger.debug("[mistakes] resolved %s in DB", mistake_id)
        except Exception as exc:
            logger.warning("[mistakes] DB resolve failed for %s: %s", mistake_id, exc)

    # In-memory
    for records in _mistakes.values():
        for r in records:
            if r.get("id") == mistake_id:
                r["resolved"] = True
                break

    return {"mistake_id": mistake_id, "status": "resolved"}


@router.get("/{mistake_id}/attribution")
def get_attribution(mistake_id: str):
    """获取错题归因（8 分类双通道 + Bloom 建议）。

    T1.2-B 错题变式闭环的 B 端输出：
    - 错因 8 分类（英文，与 A 的 variant_generator 接口约定一致）
    - 规则 + LLM 双通道归因
    - 建议补救路径 + 推荐 Bloom 巩固等级
    """
    from backend.app.services.attribution_engine import (
        ATTRIBUTION_CATEGORIES,
        CATEGORY_LABELS,
        get_attribution_engine,
    )

    record = _find_mistake(mistake_id)
    if not record:
        raise HTTPException(status_code=404, detail="mistake not found")

    question = record.get("question") or (record.get("question_data") or {}).get("question", "")
    user_answer = record.get("student_answer", "")
    correct_answer = record.get("correct_answer", "")
    kp_ids = record.get("kp_ids") or [record.get("knowledge_point_id", "")]

    engine = get_attribution_engine()
    result = engine.attribute(
        question=question,
        user_answer=user_answer,
        correct_answer=correct_answer,
        user_id=record.get("user_id", ""),
        kp_ids=kp_ids,
    )

    # 推荐 Bloom 巩固等级：当前等级 → 略低 1 级
    bloom_order = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
    current_bloom = record.get("bloom_level", "understand")
    try:
        idx = bloom_order.index(current_bloom)
    except ValueError:
        idx = 1
    recommended_bloom = bloom_order[max(0, idx - 1)]

    # 补救建议（英文分类映射）
    remediation = {
        "concept_confusion": "建议对比相似概念的核心差异，制作概念对比表。",
        "careless": "建议检查计算步骤的符号和数值，用草稿纸分步演算。",
        "ambiguous_question": "建议逐句分析题目条件，圈出关键词后再作答。",
        "input_error": "建议检查输入格式，确认答案完整性后重新提交。",
        "boundary_unclear": "建议精读定义中的边界条件，特别关注反例。",
        "prerequisite_missing": "建议复习先修知识的基础定义，再做巩固题。",
        "procedural_slip": "建议分步练习，每步验证后再继续。",
        "unknown": "建议针对该知识点进行专项练习。",
    }

    return {
        "mistake_id": mistake_id,
        "category": result.category,
        "confidence": result.confidence,
        "evidence": result.evidence,
        "source": result.source,
        "category_label": CATEGORY_LABELS.get(result.category, ""),
        "recommended_bloom_level": recommended_bloom,
        "remediation_advice": remediation.get(
            result.category, "建议针对该知识点进行专项练习。"
        ),
        "all_categories": ATTRIBUTION_CATEGORIES,
    }




# ═══════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════

def _question_text(question_data: dict[str, Any] | None) -> str:
    data = question_data or {}
    return str(data.get("question") or data.get("stem") or "")


def _gather_user_records(user_id: str) -> list[dict]:
    """Collect mistake records from DB + in-memory, merge dedup."""
    records: dict[str, dict] = {}

    if _db_available:
        try:
            with SessionLocal() as db:
                rows = (
                    db.query(MistakeRecord)
                    .filter(MistakeRecord.user_id == user_id)
                    .order_by(MistakeRecord.created_at.desc())
                    .all()
                )
                for r in rows:
                    records[r.id] = {
                        "id": r.id,
                        "user_id": r.user_id,
                        "kp_id": r.knowledge_point_id,
                        "question": _question_text(r.question_data),
                        "student_answer": r.question_data.get("student_answer", ""),
                        "correct_answer": r.question_data.get("correct_answer", ""),
                        "error_type": r.error_type,
                        "analysis": r.analysis,
                        "created_at": r.created_at,
                        "resolved_at": r.resolved_at,
                        "resolved": r.resolved_at is not None,
                    }
        except Exception as exc:
            logger.warning("[mistakes] DB list failed for %s: %s", user_id, exc)

    for r in _mistakes.get(user_id, []):
        if r["id"] not in records:
            records[r["id"]] = dict(r)

    return sorted(records.values(), key=lambda x: x.get("created_at", 0), reverse=True)


def _insight_candidate_records(records: list[dict]) -> list[dict]:
    """Prefer currently unresolved mistakes for AI insights.

    The student profile insight panel is meant to surface active remediation
    targets. If every record is already resolved, keep historical records as a
    fallback so the panel can still summarize learning history instead of going
    blank.
    """
    unresolved = [
        record
        for record in records
        if not record.get("resolved") and not record.get("resolved_at")
    ]
    return unresolved or records


def _find_mistake(mistake_id: str) -> dict | None:
    """Find a single mistake by ID across DB and in-memory stores."""
    if _db_available:
        try:
            with SessionLocal() as db:
                row = db.get(MistakeRecord, mistake_id)
                if row:
                    return {
                        "id": row.id,
                        "user_id": row.user_id,
                        "kp_id": row.knowledge_point_id,
                        "question": _question_text(row.question_data),
                        "student_answer": row.question_data.get("student_answer", ""),
                        "correct_answer": row.question_data.get("correct_answer", ""),
                        "error_type": row.error_type,
                        "analysis": row.analysis,
                    }
        except Exception as exc:
            logger.warning("[mistakes] DB lookup failed for %s: %s", mistake_id, exc)

    for records in _mistakes.values():
        for r in records:
            if r.get("id") == mistake_id:
                return dict(r)

    return None


def _update_mistake(mistake_id: str, **kwargs) -> None:
    """Update mistake fields in DB and in-memory."""
    if _db_available:
        try:
            with SessionLocal() as db:
                row = db.get(MistakeRecord, mistake_id)
                if row:
                    for key, value in kwargs.items():
                        if hasattr(row, key):
                            setattr(row, key, value)
                    db.commit()
        except Exception as exc:
            logger.warning("[mistakes] DB update failed for %s: %s", mistake_id, exc)

    for records in _mistakes.values():
        for r in records:
            if r.get("id") == mistake_id:
                r.update(kwargs)
                break
