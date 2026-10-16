"""Plan D · 3.3 — 间隔重复 API 端点

把 SM2 / FSRS / HLR 后端服务暴露给前端 PathView / ProfileView 复习模块。

端点
====
GET  /api/v1/spaced-repetition/daily/{user_id}
     → 今日到期复习的知识点列表（含难易度/间隔/到期时间/算法来源 + 优先级）
POST /api/v1/spaced-repetition/review
     body: {user_id, item_id, algorithm: "sm2"|"fsrs"|"hlr", quality: 0-5}
     → 更新调度 + 返回新状态
GET  /api/v1/spaced-repetition/stats/{user_id}
     → 学习者复习统计
GET  /api/v1/spaced-repetition/schedule/{user_id}/{item_id}
     → 单知识点详情
GET  /api/v1/spaced-repetition/recommend/{user_id}
     → 复习推荐 Top-N（按 priority_score 排序，含 reason 解释）
POST /api/v1/spaced-repetition/enqueue
     body: {user_id, item_id} → 快速加入复习队列

设计依据
========
* SM2 / FSRS / HLR 已实现于 services/spaced_repetition/
* 答错或初学 = quality=0 路径调 add_to_review_queue
* 算法选择：默认 sm2；fsrs/hlr 通过 stats.algorithm 字段透传
* Plan D · 3.3 — 复习优先级融合 SM2 调度 + BKT 掌握度，
  priority_score = 0.6 * overdue_factor + 0.4 * (1 - mastery)
"""
from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.spaced_repetition import get_sm2
from backend.app.services.spaced_repetition.forgetting_curve import (
    next_review_recommendation,
    retention_at_intervals,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spaced-repetition", tags=["spaced-repetition"])


@lru_cache(maxsize=1)
def _review_knowledge_catalog() -> Dict[str, Dict[str, Any]]:
    """Load canonical graph labels instead of exposing opaque KP ids to UI."""
    try:
        from backend.app.services.course_registry import get_course_registry

        # 聚合全部课程的知识点图谱（旧全局文件 + 各课程级文件）
        return {
            str(kp_id): dict(meta)
            for kp_id, meta in get_course_registry().load_map_nodes().items()
            if isinstance(meta, dict)
        }
    except Exception as exc:
        logger.warning("[spaced_repetition] knowledge catalog unavailable: %s", exc)
        return {}


@lru_cache(maxsize=512)
def _review_item_context(item_id: str) -> Dict[str, Any]:
    meta = _review_knowledge_catalog().get(str(item_id), {})
    objectives = [str(item) for item in (meta.get("learning_objectives") or []) if item]
    knowledge_point = {
        "id": str(item_id),
        "name": str(meta.get("name") or item_id),
        "description": "；".join(objectives),
    }

    question_payload: Dict[str, Any] | None = None
    try:
        from backend.app.services.knowledge_index import get_knowledge_index

        questions = get_knowledge_index().practice_for_kp(str(item_id), n=1)
        if questions:
            question = questions[0]
            question_payload = {
                "id": str(question.get("id") or ""),
                "stem": str(question.get("stem") or question.get("question") or ""),
                "options": [str(option) for option in (question.get("options") or [])],
                "type": str(question.get("type") or ""),
                "difficulty": question.get("difficulty"),
                "bloom": str(question.get("bloom") or ""),
                "kp_id": str(question.get("kp_id") or ""),
                "kp_name": str(question.get("kp_name") or knowledge_point["name"]),
            }
    except Exception as exc:
        logger.warning("[spaced_repetition] question lookup failed for %s: %s", item_id, exc)

    return {"knowledge_point": knowledge_point, "question": question_payload}


# ============================================================
# 数据模型
# ============================================================
class ReviewIn(BaseModel):
    user_id: str = Field(..., description="学习者 ID")
    item_id: str = Field(..., description="知识点 ID")
    algorithm: str = Field("sm2", description="算法: sm2 / fsrs / hlr")
    item_type: str = "knowledge_point"
    duration_minutes: float = Field(0, ge=0, le=1440)
    before_mastery: Optional[float] = Field(None, ge=0, le=1)
    after_mastery: Optional[float] = Field(None, ge=0, le=1)
    quality: int = Field(
        0, ge=0, le=5,
        description="回答质量 0-5（0=完全不会, 5=完全正确）",
    )


# ============================================================
# GET /daily/{user_id}
# ============================================================
@router.get("/daily/{user_id}")
def get_daily(user_id: str, limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    """Plan D · 3.3 — 今日到期复习列表

    数据来源: SM2 实例的 due_items()。我们再用 RetentionCurve 给每条
    计算 7/14/30 天的留存率，前端可展示为"如不复习，几周后会忘"。

    Plan D · 3.3 — 每条同时打 priority_score (0-1) + reason
    （融合 SM2 overdue + BKT mastery，priority_score 越高越应先复习）
    """
    try:
        sm2 = get_sm2()
        items = sm2.due_items(user_id)[:limit]
    except Exception as exc:
        logger.warning(f"[spaced_repetition] SM2 load fail: {exc}")
        items = []

    enriched: List[Dict[str, Any]] = []
    for it in items:
        intervals = _retention_curve_dict(
            it.get("easiness", 2.5),
            it.get("repetitions", 0),
        )
        recommendation = next_review_recommendation(
            current_easiness=it.get("easiness", 2.5),
            current_interval=it.get("interval", 1),
            repetitions=it.get("repetitions", 0),
            last_quality=4,  # 假定最近一次还行
        )
        priority_score, reason = _compute_review_priority(user_id, it)
        enriched.append({
            "item_id": it["item_id"],
            **_review_item_context(str(it["item_id"])),
            "easiness": it.get("easiness", 2.5),
            "interval_days": it.get("interval", 1),
            "repetitions": it.get("repetitions", 0),
            "next_review_at": it.get("next_review_at"),
            "last_review_at": it.get("last_review_at"),
            "retention_curve": intervals,
            "recommendation": recommendation,
            # Plan D · 3.3 — 复习优先级
            "priority_score": round(priority_score, 3),
            "priority_reason": reason,
        })

    # 按优先级从高到低排序
    enriched.sort(key=lambda x: x["priority_score"], reverse=True)

    stats = _safe_stats(user_id)
    return {
        "user_id": user_id,
        "total_due": len(items),
        "stats": stats,
        "items": enriched,
        "algorithm": "sm2",  # 现阶段主力算法是 SM2
    }


# ============================================================
# GET /recommend/{user_id}  — 复习推荐 Top-N
# ============================================================
@router.get("/recommend/{user_id}")
def get_recommend(user_id: str, limit: int = Query(3, ge=1, le=10)) -> Dict[str, Any]:
    """Plan D · 3.3 — 复习推荐（Top-N）

    排序逻辑:
      priority_score = 0.6 * overdue_factor + 0.4 * (1 - mastery)

    - overdue_factor: SM2 调度项距今多久（0~1，0=刚到期，1=严重 overdue）
    - mastery: BKT 掌握度 0~1（无 BKT 数据时按 0.5 兜底）

    返回:
      recommendations[]: 每条 {item_id, priority_score, reason, easiness,
                              mastery, interval_days, repetitions,
                              next_review_at}
    """
    try:
        sm2 = get_sm2()
        items = sm2.due_items(user_id)
    except Exception as exc:
        logger.warning(f"[spaced_repetition] SM2 load fail: {exc}")
        items = []

    enriched = []
    for it in items:
        ps, reason = _compute_review_priority(user_id, it)
        enriched.append({
            "item_id": it["item_id"],
            "priority_score": round(ps, 3),
            "reason": reason,
            "easiness": it.get("easiness", 2.5),
            "interval_days": it.get("interval", 1),
            "repetitions": it.get("repetitions", 0),
            "next_review_at": it.get("next_review_at"),
        })

    enriched.sort(key=lambda x: x["priority_score"], reverse=True)
    return {
        "user_id": user_id,
        "recommendations": enriched[:limit],
        "total_candidates": len(enriched),
        "algorithm": "sm2",
    }


# ============================================================
# POST /review
# ============================================================
@router.post("/review")
def post_review(payload: ReviewIn) -> Dict[str, Any]:
    """Plan D · 3.3 — 提交一次复习评分

    更新 SM2 状态（plan D 阶段先接 SM2；fsrs/hlr 通过算法 router 透传）。
    """
    try:
        sm2 = get_sm2()
        previous = sm2.get_schedule(payload.user_id, payload.item_id)
        # 第一次加入队列时（state 不存在），add_to_review_queue 直接 quality=0 路径
        if previous is None:
            sm2.add_to_review_queue(payload.user_id, payload.item_id)
        state = sm2.review(payload.user_id, payload.item_id, payload.quality)
    except Exception as exc:
        logger.exception(f"[spaced_repetition] review failed: {exc}")
        raise HTTPException(status_code=500, detail=f"review failed: {exc}") from exc

    from backend.app.core.database import SessionLocal
    from backend.app.core.models import ReviewEventRecord

    before_mastery = payload.before_mastery
    if before_mastery is None and previous:
        before_mastery = previous.get("mastery")
    after_mastery = payload.after_mastery
    if after_mastery is None:
        after_mastery = state.get("mastery")
    with SessionLocal() as db:
        event = ReviewEventRecord(
            user_id=payload.user_id,
            item_id=payload.item_id,
            item_type=payload.item_type,
            rating=payload.quality,
            before_mastery=before_mastery,
            after_mastery=after_mastery,
            duration_minutes=payload.duration_minutes,
            reviewed_at=float(state.get("last_review_at") or time.time()),
            metadata_data={"algorithm": payload.algorithm, "source": "spaced-repetition-api"},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        review_event_id = event.id

    intervals = _retention_curve_dict(state.get("easiness", 2.5))
    return {
        "user_id": payload.user_id,
        "item_id": payload.item_id,
        "algorithm": payload.algorithm,
        "quality": payload.quality,
        "review_event_id": review_event_id,
        "state": {
            "easiness": state.get("easiness"),
            "interval": state.get("interval"),
            "repetitions": state.get("repetitions"),
            "next_review_at": state.get("next_review_at"),
            "last_review_at": state.get("last_review_at"),
        },
        "retention_curve": intervals,
    }


@router.get("/history/{user_id}")
def get_review_history(
    user_id: str,
    limit: int = 50,
) -> Dict[str, Any]:
    from datetime import datetime, timezone

    from backend.app.core.database import SessionLocal
    from backend.app.core.models import ReviewEventRecord

    with SessionLocal() as db:
        query = db.query(ReviewEventRecord).filter(ReviewEventRecord.user_id == user_id)
        total = query.count()
        rows = query.order_by(ReviewEventRecord.reviewed_at.desc()).limit(limit).all()
        return {
            "user_id": user_id,
            "total": total,
            "items": [
                {
                    "id": row.id,
                    "item_id": row.item_id,
                    "item_type": row.item_type,
                    "rating": row.rating,
                    "before_mastery_pct": round(float(row.before_mastery or 0) * 100, 1),
                    "after_mastery_pct": round(float(row.after_mastery or 0) * 100, 1),
                    "duration_minutes": round(float(row.duration_minutes or 0), 1),
                    "reviewed_at": float(row.reviewed_at),
                    "display_date": datetime.fromtimestamp(
                        float(row.reviewed_at), tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M"),
                    "metadata": row.metadata_data or {},
                }
                for row in rows
            ],
        }


# ============================================================
# GET /stats/{user_id}
# ============================================================
@router.get("/stats/{user_id}")
def get_stats(user_id: str) -> Dict[str, Any]:
    return _safe_stats(user_id)


# ============================================================
# GET /schedule/{user_id}/{item_id}
# ============================================================
@router.get("/schedule/{user_id}/{item_id}")
def get_schedule(user_id: str, item_id: str) -> Dict[str, Any]:
    try:
        sm2 = get_sm2()
        state = sm2.get_schedule(user_id, item_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if state is None:
        raise HTTPException(status_code=404, detail="schedule_not_found")
    intervals = _retention_curve_dict(state.get("easiness", 2.5))
    return {
        "user_id": user_id,
        "item_id": item_id,
        "state": state,
        "retention_curve": intervals,
    }


# ============================================================
# helpers
# ============================================================
def _retention_curve_dict(easiness: float = 2.5, repetitions: int = 0) -> Dict[str, float]:
    return {
        str(point["day"]): point["retention"]
        for point in retention_at_intervals(easiness, repetitions)
    }


def _safe_stats(user_id: str) -> Dict[str, Any]:
    try:
        sm2 = get_sm2()
        stats = sm2.stats(user_id)
        # 加 due_item_titles 给前端展示
        item_ids = stats.get("due_item_ids", [])
        stats["due_item_count"] = len(item_ids)
        return stats
    except Exception as exc:
        logger.warning(f"[spaced_repetition] stats fail: {exc}")
        return {
            "user_id": user_id,
            "total_items": 0,
            "due_today": 0,
            "due_item_count": 0,
            "average_easiness": 2.5,
            "due_item_ids": [],
        }


# ============================================================
# 计划与删除
# ============================================================
class EnqueueIn(BaseModel):
    user_id: str
    item_id: str


@router.post("/enqueue")
def post_enqueue(payload: EnqueueIn) -> Dict[str, Any]:
    """加入复习队列（不评分，仅占位）"""
    try:
        sm2 = get_sm2()
        sm2.add_to_review_queue(payload.user_id, payload.item_id)
        return {"status": "enqueued", "user_id": payload.user_id, "item_id": payload.item_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ============================================================
# Plan D · 3.3 — 复习优先级融合 SM2 + BKT
# ============================================================
def _compute_review_priority(user_id: str, sm2_item: Dict[str, Any]) -> tuple[float, str]:
    """Plan D · 3.3 — 计算单条复习项的优先级 + 原因

    Args:
        user_id: 学生 ID
        sm2_item: SM2 实例返回的单条 due item（含 next_review_at / interval / easiness）

    Returns:
        (priority_score, reason)
        - priority_score: 0~1，越高越应先复习
        - reason: 1 句话解释为什么这个分数（中文）
    """
    import time as _time

    # 1) overdue_factor: 距离下次复习时间多久
    next_review = sm2_item.get("next_review_at")
    interval = max(int(sm2_item.get("interval", 1) or 1), 1)
    now = _time.time()
    if next_review is None:
        overdue_factor = 0.5
    else:
        # 距下次复习过了多久（天），clamp 到 [0, 30]
        overdue_days = max(0.0, (now - float(next_review)) / 86400.0)
        overdue_factor = min(1.0, overdue_days / max(interval * 2, 7))
        # 0 表示准时/未到期；1 表示严重 overdue（间隔的 2 倍以上）

    # 2) mastery: BKT 掌握度（0~1）。无 BKT 数据时按 0.5 兜底
    mastery = 0.5
    try:
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt
        mastery = float(get_bkt().get_mastery(user_id, sm2_item["item_id"]))
    except Exception:
        mastery = 0.5

    # 3) 融合公式：overdue 权重 0.6 + mastery 反向权重 0.4
    score = 0.6 * overdue_factor + 0.4 * (1.0 - mastery)
    score = max(0.0, min(1.0, score))

    # 4) reason 中文
    reasons = []
    if overdue_factor >= 0.6:
        reasons.append(f"已逾期 ({int(overdue_factor * interval * 2)} 天未复习)")
    elif overdue_factor >= 0.2:
        reasons.append("已到复习时间")
    if mastery < 0.4:
        reasons.append(f"BKT 掌握仅 {int(mastery * 100)}%")
    elif mastery < 0.7:
        reasons.append(f"BKT 掌握 {int(mastery * 100)}%，可加强")
    if not reasons:
        reasons.append("按 SM2 调度到期")
    return score, " · ".join(reasons)
